"""donna_macro_discord.py — NOVA Macro Intelligence Discord Feed.

Delivers high-signal macro events to #macro-risk (DISCORD_CHANNEL_MACRO).
Reads exclusively from existing data files — no duplicate fetch logic.

Data inputs:
  donna_macro_events.json → scheduled calendar events (donna_headlines.py cycle)
  donna_risk_state.json   → VIX, regime, headline_risk, last_headline (donna_finnhub/news cycle)

Delivery triggers (call from existing loops):
  run_macro_calendar_check()  → every 5 min alongside check_todays_events()
  run_macro_morning_brief()   → once per day, pre-market (09:00–09:20 ET window)
  run_vix_volatility_check()  → every 5 min alongside finnhub cycle
  run_breaking_news_check()   → every 5 min alongside news cycle

Routing: ALL macro alerts go to DISCORD_CHANNEL_MACRO only.
#live-alerts is never touched.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests

# ── Paths ──────────────────────────────────────────────────────────────────────

from core.config import (
    MACRO_EVENTS_FILE        as _MACRO_EVENTS_FILE,
    RISK_STATE_FILE          as _RISK_STATE_FILE,
    MACRO_DISCORD_STATE_FILE as _MACRO_DISC_STATE,
)
_DISCORD_API = 'https://discord.com/api/v10'

# ── Config imports ─────────────────────────────────────────────────────────────

try:
    from core.config import (
        DISCORD_BOT_TOKEN,
        DISCORD_CHANNEL_MACRO,
        ANTHROPIC_MODEL,
        client as _anthropic_client,
        now_ny,
    )
except ImportError:
    DISCORD_BOT_TOKEN     = ''
    DISCORD_CHANNEL_MACRO = ''
    ANTHROPIC_MODEL       = 'claude-haiku-4-5-20251001'
    _anthropic_client     = None
    def now_ny():
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('America/New_York'))

# ── Severity constants ─────────────────────────────────────────────────────────

CRITICAL = 'CRITICAL'
HIGH     = 'HIGH'
MEDIUM   = 'MEDIUM'
LOW      = 'LOW'

# Embed colors per severity
_COLORS = {
    CRITICAL: 0xFF0000,   # bright red
    HIGH:     0xFF4444,   # red-orange
    MEDIUM:   0xFFBB33,   # amber
    LOW:      0x5865F2,   # indigo
}

# Severity emoji prefixes
_EMOJI = {
    CRITICAL: '🚨',
    HIGH:     '⚠️',
    MEDIUM:   '📊',
    LOW:      '📋',
}

# ── Category constants ─────────────────────────────────────────────────────────

SCHEDULED_MACRO      = 'SCHEDULED_MACRO'
FED_COMMENTARY       = 'FED_COMMENTARY'
VOLATILITY_WARNING   = 'VOLATILITY_WARNING'
BREAKING_NEWS        = 'BREAKING_NEWS'
SESSION_DOWNGRADE    = 'SESSION_DOWNGRADE'
MORNING_BRIEF        = 'MORNING_BRIEF'

_CATEGORY_LABELS = {
    SCHEDULED_MACRO:   'Scheduled Macro',
    FED_COMMENTARY:    'Fed Commentary',
    VOLATILITY_WARNING:'Volatility Warning',
    BREAKING_NEWS:     'Breaking Macro',
    SESSION_DOWNGRADE: 'Session Downgrade',
    MORNING_BRIEF:     'Daily Macro Brief',
}

# ── Event name → category/severity keyword sets ────────────────────────────────

_CRITICAL_NAMES = {
    'cpi', 'core cpi', 'consumer price index',
    'nonfarm payroll', 'nfp', 'non-farm payroll',
    'fomc', 'fomc rate', 'rate decision', 'interest rate decision', 'federal reserve rate',
    'core pce', 'pce price index',
}
_FED_NAMES = {
    'powell', 'fed speak', 'fed chair', 'fed governor', 'fed president',
    'fed minutes', 'fomc minutes', 'beige book',
    'federal reserve', 'fed statement',
}
_HIGH_NAMES = {
    'ppi', 'producer price', 'retail sales', 'gdp', 'gross domestic product',
    'unemployment rate', 'jobless claims', 'initial claims',
    'core retail', 'ism manufacturing', 'ism services',
}

_BREAKING_EMERGENCY = {
    'circuit breaker', 'trading halt', 'market halt', 'crash', 'collapse',
    'emergency', 'default', 'banking crisis', 'liquidity crisis', 'systemic',
    'war', 'attack', 'explosion', 'sanction',
}
_BREAKING_MACRO = {
    'fed ', 'federal reserve', 'fomc', 'rate hike', 'rate cut', 'rate decision',
    'cpi ', 'pce ', 'inflation data', 'nonfarm', 'payroll',
    'powell', 'treasury yield', 'recession', 'stagflation',
}

# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class MacroEvent:
    title:      str
    time_et:    str
    date:       str
    importance: str           # 'high' | 'medium' | 'low' (from calendar)
    category:   str           # our classification (SCHEDULED_MACRO etc.)
    severity:   str           # CRITICAL | HIGH | MEDIUM | LOW
    note:       str = ''      # forecast/previous from calendar
    source:     str = ''
    minutes_away: Optional[int] = None
    phase:      str = ''      # APPROACHING | IMMINENT | LIVE | SCHEDULED

    @property
    def event_key(self) -> str:
        """Stable dedup key: date + normalized title."""
        return f'{self.date}_{self.title[:40].lower().replace(" ", "_")}'


# ── State persistence ──────────────────────────────────────────────────────────

_state_lock = threading.Lock()


def _load_macro_state() -> dict:
    with _state_lock:
        try:
            if _MACRO_DISC_STATE.exists():
                return json.loads(_MACRO_DISC_STATE.read_text())
        except Exception:
            pass
        return {
            'delivered':          {},   # {event_key: {phases: [], last_ts: str}}
            'morning_brief_date': '',
            'vix_alert_ts':       '',
            'breaking_keys':      [],   # last N headline keys delivered
        }


def _save_macro_state(state: dict) -> None:
    with _state_lock:
        try:
            _MACRO_DISC_STATE.write_text(json.dumps(state, indent=2))
        except Exception:
            pass


def _read_json(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default or {}


# ── Severity + category classification ────────────────────────────────────────

def _classify_event(event: dict) -> tuple[str, str]:
    """
    Returns (severity, category) for a calendar event.
    Calendar importance 'high' + name match → CRITICAL or HIGH.
    """
    title = event.get('title', '').lower()
    imp   = event.get('importance', '').lower()

    # Category
    if any(k in title for k in _FED_NAMES):
        category = FED_COMMENTARY
    else:
        category = SCHEDULED_MACRO

    # Severity
    if imp == 'high' and any(k in title for k in _CRITICAL_NAMES):
        return CRITICAL, category
    if imp == 'high' and any(k in title for k in _HIGH_NAMES):
        return HIGH, category
    if imp == 'high':
        return HIGH, category
    if imp == 'medium':
        return MEDIUM, category
    return LOW, category


def _classify_breaking(headline: str) -> tuple[str, str]:
    """Returns (severity, category) for a breaking news headline."""
    t = headline.lower()
    if any(k in t for k in _BREAKING_EMERGENCY):
        return CRITICAL, BREAKING_NEWS
    if any(k in t for k in _BREAKING_MACRO):
        return HIGH, BREAKING_NEWS
    return MEDIUM, BREAKING_NEWS


def _classify_vix(vix: float, vix_pct: float) -> str:
    """Returns severity for a VIX spike event."""
    if vix >= 30 or vix_pct >= 15:
        return CRITICAL
    if vix >= 25 or vix_pct >= 8:
        return HIGH
    return MEDIUM


# ── Phase computation ──────────────────────────────────────────────────────────

def _compute_phase_and_mins(time_et: str) -> tuple[str, Optional[int]]:
    """
    Compute event lifecycle phase relative to now.

    UPCOMING      > 30 min away    — informational only
    APPROACHING   10–30 min away   — governance active, prepare
    IMMINENT      0–10 min away    — governance active, stand aside
    LIVE          0–15 min past    — governance active, stand aside
    POST_COOLDOWN 15–30 min past   — governance active, cooldown
    EXPIRED       > 30 min past    — informational only, no governance
    """
    try:
        now = now_ny()
        h, m = [int(x) for x in time_et.split(':')]
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        mins = int((target - now).total_seconds() // 60)
        if mins < -30:
            return 'EXPIRED', mins
        if mins < -15:
            return 'POST_COOLDOWN', mins
        if mins < 0:
            return 'LIVE', mins
        if mins <= 10:
            return 'IMMINENT', mins
        if mins <= 30:
            return 'APPROACHING', mins
        return 'SCHEDULED', mins
    except Exception:
        return 'UNKNOWN', None


# Phases that influence live governance (session quality, ORB, execution actions)
_GOVERNANCE_PHASES = {'APPROACHING', 'IMMINENT', 'LIVE', 'POST_COOLDOWN'}
# Phases that count toward session quality grade (includes far-future today events)
_SESSION_QUALITY_PHASES = {'SCHEDULED', 'APPROACHING', 'IMMINENT', 'LIVE', 'POST_COOLDOWN'}


# ── Operational state model ────────────────────────────────────────────────────

def compute_macro_state() -> dict:
    """
    Derive operational macro state from raw data files.

    This is the source of truth for both Discord embeds and the future NOVA app.
    Embeds are consumers of this state — not the other way around.
    """
    macro_data = _read_json(_MACRO_EVENTS_FILE)
    risk_state = _read_json(_RISK_STATE_FILE)
    now        = now_ny()
    today      = now.strftime('%Y-%m-%d')

    all_events   = macro_data.get('events', [])
    today_events = sorted(
        [e for e in all_events if e.get('date') == today],
        key=lambda e: e.get('time_et', ''),
    )
    high_events = [e for e in today_events if e.get('importance') == 'high']

    # Session-quality-active high events: scheduled or in governance window (not expired)
    sq_high_events = [
        e for e in high_events
        if _compute_phase_and_mins(e.get('time_et', ''))[0] in _SESSION_QUALITY_PHASES
    ]

    # Next event in active governance window (includes post-event cooldown)
    next_event      = None
    active_phase    = 'CLEAR'
    minutes_to_next = None
    for ev in today_events:
        phase, mins = _compute_phase_and_mins(ev.get('time_et', ''))
        if phase in _GOVERNANCE_PHASES:
            next_event, active_phase, minutes_to_next = ev, phase, mins
            break

    # Market snapshot
    snap     = risk_state.get('market_snapshot', {})
    vix_data = snap.get('VIX', {})
    nq_data  = snap.get('NQ', {})
    es_data  = snap.get('ES', {})
    vix      = float(vix_data.get('last') or 0)
    vix_pct  = float(vix_data.get('pct')  or 0)
    nq_pct   = float(nq_data.get('pct')   or 0)
    es_pct   = float(es_data.get('pct')   or 0)
    regime   = risk_state.get('market_regime', 'UNKNOWN')
    us10y    = float((snap.get('US10Y') or {}).get('last') or 0)

    # Session quality — uses lifecycle-aware events only (expired events don't count)
    if len(sq_high_events) >= 2 or vix >= 25:
        sq, sq_reason = 'C', (f'{len(sq_high_events)} HIGH events active' if len(sq_high_events) >= 2 else f'VIX {vix:.0f}')
    elif len(sq_high_events) == 1:
        sq, sq_reason = 'B', f'{sq_high_events[0]["title"]} at {sq_high_events[0]["time_et"]} ET'
    elif risk_state.get('red_folder_week') or vix >= 20:
        sq, sq_reason = 'B', ('Red folder week' if risk_state.get('red_folder_week') else f'VIX {vix:.0f}')
    else:
        sq, sq_reason = 'A', 'Clean macro environment'

    # ORB reliability — degraded during any governance-active window
    pre_event    = active_phase in _GOVERNANCE_PHASES or (
        minutes_to_next is not None and 0 <= minutes_to_next <= 15
    )
    orb_reliable = sq == 'A' and not pre_event and vix < 20

    # Recommended action — single operational line
    if active_phase == 'POST_COOLDOWN':
        mins_ago = abs(minutes_to_next) if minutes_to_next is not None else 0
        action = f'Post-event cooldown — {next_event["title"]} released {mins_ago}min ago. Allow market to settle.'
    elif active_phase == 'LIVE' or (minutes_to_next is not None and minutes_to_next <= 0):
        action = f'Stand aside — {next_event["title"]} is live.'
    elif active_phase == 'IMMINENT':
        action = f'Stand aside — {next_event["title"]} in {minutes_to_next} min.'
    elif active_phase == 'APPROACHING':
        action = f'Prepare — {next_event["title"]} in {minutes_to_next} min.'
    elif vix >= 25:
        action = 'Grade A only. Size −50%. Observe first 15 min.'
    elif sq == 'C':
        action = 'Reduced conviction day. Higher bar for entry.'
    else:
        action = 'Standard discipline. Respect session structure.'

    return {
        'events_today':    today_events,
        'high_events':     high_events,
        'next_event':      next_event,
        'active_phase':    active_phase,
        'minutes_to_next': minutes_to_next,
        'vix':             vix,
        'vix_pct':         vix_pct,
        'nq_pct':          nq_pct,
        'es_pct':          es_pct,
        'us10y':           us10y,
        'regime':          regime,
        'session_quality': sq,
        'sq_reason':       sq_reason,
        'orb_reliable':    orb_reliable,
        'action':          action,
        'macro_risk':      risk_state.get('macro_risk', 'low'),
        'red_folder_week': risk_state.get('red_folder_week', False),
        'computed_at':     now.isoformat(),
    }


# ── Deterministic NOVA tactical lines ──────────────────────────────────────────

def _nova_lines_for_event(title: str, severity: str, phase: str,
                           mins: Optional[int]) -> list[str]:
    """
    Return 2-3 tactical NOVA lines for a macro event.
    Deterministic rule-based — no API call.
    Language is operational, not commentary.
    """
    t = title.lower()

    if any(k in t for k in ('cpi', 'consumer price index', 'core cpi')):
        lines = ['ORB unreliable at open.', 'Elevated sweep probability both sides.']
        lines.append('No entries pre-data.' if phase == 'IMMINENT'
                     else 'Stand aside until data settles (~09:45 ET).')

    elif any(k in t for k in ('pce', 'personal consumption expenditure')):
        lines = ['PCE drives rate repricing — expect directional expansion.',
                 'ORB unreliable pre-data.',
                 'Entry window opens ~09:45 ET if reaction is clean.']

    elif any(k in t for k in ('nonfarm', 'payroll', 'nfp')):
        lines = ['High-volatility binary print.',
                 'ORB formation likely erratic.',
                 'No entries until 09:50 ET minimum.']

    elif any(k in t for k in ('fomc', 'rate decision', 'interest rate decision')):
        lines = ['Maximum uncertainty event.',
                 'Stand aside until post-decision direction locks.',
                 'Session may not present a tradeable setup.']

    elif any(k in t for k in ('powell', 'waller', 'jefferson', 'barr', 'cook',
                               'fed speak', 'fed chair', 'fed governor',
                               'fed president', 'fed minutes', 'beige book')):
        lines = ['Fed speaker risk active during session.',
                 'Continuation quality may degrade mid-session.',
                 'Watch for headline-driven momentum reversal.']

    elif any(k in t for k in ('ppi', 'producer price')):
        lines = ['Inflation proxy — watch for yield move at print.',
                 'Moderate ORB impact expected.']

    elif any(k in t for k in ('retail sales',)):
        lines = ['Consumer data — moderate market-moving potential.',
                 'Continuation quality may be affected post-print.']

    elif any(k in t for k in ('gdp', 'gross domestic')):
        lines = ['Growth print — directional signal for risk appetite.',
                 'ORB reliability reduced at open.']

    elif any(k in t for k in ('jobless', 'initial claims', 'unemployment rate')):
        lines = ['Labor data — lower impact than NFP.',
                 'Continuation quality likely unaffected.']

    elif any(k in t for k in ('ism', 'pmi', 'manufacturing', 'services index')):
        lines = ['Sector data — moderate impact.',
                 'Watch for NQ/ES divergence off print.']

    elif any(k in t for k in ('michigan', 'consumer sentiment', 'consumer confidence')):
        lines = ['Sentiment proxy — moderate impact.',
                 'Standard session caution applies.']

    else:
        lines = ['Elevated macro risk at release time.', 'Standard session caution applies.']

    # Phase urgency: if IMMINENT and no stand-aside already, add one
    if phase == 'IMMINENT' and mins is not None and mins <= 5:
        has_action = any('stand aside' in l.lower() or 'no entries' in l.lower() for l in lines)
        if not has_action:
            lines = [lines[0], 'Stand aside. No entries pre-data.']

    return lines[:3]


# ── Embed primitives ───────────────────────────────────────────────────────────

def _field(name: str, value: str, inline: bool = True) -> dict:
    return {'name': name, 'value': value or '—', 'inline': inline}


def _spacer() -> dict:
    return {'name': '​', 'value': '​', 'inline': False}


def _fmt_pct(v) -> str:
    try:
        return f'{float(v):+.1f}%'
    except (TypeError, ValueError):
        return '—'


# ── Embed builders — thin view layer over operational state ────────────────────

def _build_calendar_embed(event: MacroEvent) -> dict:
    """
    Tight calendar event embed. Mobile-first. Max 4 fields.
    Title = event name. Description = timing line. NOVA = 2-3 tactical lines.
    """
    emoji = _EMOJI.get(event.severity, '📊')
    mins  = event.minutes_away

    phase_str = (
        f'IMMINENT — {mins} MIN' if event.phase == 'IMMINENT' else
        f'APPROACHING — {mins} MIN' if event.phase == 'APPROACHING' else
        event.phase
    )
    description = f'{event.time_et} ET  ·  {phase_str}  ·  {event.severity}'

    fields = []

    # Forecast / Prev — parse from "Forecast: X | Prev: Y"
    note = event.note or ''
    if 'Forecast:' in note:
        parts = [p.strip() for p in note.split('|')]
        fcst  = parts[0].replace('Forecast:', '').strip()
        prev  = parts[1].replace('Prev:', '').strip() if len(parts) > 1 else ''
        if fcst and fcst != '—':
            fields.append(_field('Forecast', fcst))
        if prev and prev != '—':
            fields.append(_field('Prev', prev))

    # NOVA tactical lines
    nova = _nova_lines_for_event(event.title, event.severity, event.phase, mins)
    if nova:
        fields.append(_spacer())
        fields.append(_field('NOVA', '\n'.join(nova), inline=False))

    return {
        'title':       f'{emoji}  {event.title.upper()}',
        'description': description,
        'fields':      fields,
        'color':       _COLORS[event.severity],
        'footer':      {'text': f'NOVA Macro  ·  {event.source or "Calendar"}  ·  {now_ny().strftime("%H:%M ET")}'},
        'timestamp':   datetime.now(timezone.utc).isoformat(),
    }


def _build_vix_embed(vix: float, vix_pct: float, regime: str, severity: str,
                     nq_pct: float = 0, es_pct: float = 0) -> dict:
    emoji = _EMOJI.get(severity, '⚠️')

    fields = [
        _field('VIX',    f'{vix:.1f}  ({_fmt_pct(vix_pct)})'),
        _field('Regime', regime or '—'),
        _field('NQ',     _fmt_pct(nq_pct)),
        _field('ES',     _fmt_pct(es_pct)),
        _spacer(),
        _field('NOVA',
               'ORB reliability degraded. Grade A only.\n'
               'Size −50%. Observe first 15 min.\n'
               'Widen stops 1.5× for elevated intraday swings.',
               inline=False),
    ]

    return {
        'title':       f'{emoji}  VIX {vix:.0f}  ·  VOLATILITY WARNING',
        'description': f'Elevated conditions active  ·  Regime: {regime}',
        'fields':      fields,
        'color':       _COLORS[severity],
        'footer':      {'text': f'NOVA Macro  ·  VIX Monitor  ·  {now_ny().strftime("%H:%M ET")}'},
        'timestamp':   datetime.now(timezone.utc).isoformat(),
    }


def _build_breaking_embed(headline: str, severity: str,
                           source: str = '', impact: str = '') -> dict:
    emoji = _EMOJI.get(severity, '⚠️')

    # Distill headline to a short title (first 8 words, caps)
    words      = headline.split()
    short      = ' '.join(words[:8]).rstrip('.,—').upper()
    if len(short) > 58:
        short = short[:55] + '…'

    fields = [
        _field('Severity', severity),
        _field('Source',   source or 'Live Feed'),
    ]
    if impact:
        fields.append(_field('Market', impact, inline=False))
    fields += [
        _spacer(),
        _field('NOVA',
               'Stand aside. Allow initial reaction to settle.\n'
               'Reassess session direction at 09:45 ET minimum.',
               inline=False),
    ]

    return {
        'title':       f'{emoji}  {short}',
        'description': headline[:250],
        'fields':      fields,
        'color':       _COLORS[severity],
        'footer':      {'text': f'NOVA Macro  ·  Breaking  ·  {now_ny().strftime("%H:%M ET")}'},
        'timestamp':   datetime.now(timezone.utc).isoformat(),
    }


def _build_morning_brief_embed(today_events: list[dict], risk_state: dict) -> dict:
    now  = now_ny()
    snap = risk_state.get('market_snapshot', {})

    def _last(k):
        v = (snap.get(k) or {}).get('last')
        return f'{float(v):.2f}' if v else '—'

    def _pct(k):
        v = (snap.get(k) or {}).get('pct')
        return _fmt_pct(v)

    # Events — one compact line each
    high_events = [e for e in today_events if e.get('importance') == 'high']
    event_lines = []
    for ev in today_events:
        icon = '🔴' if ev.get('importance') == 'high' else '🟡'
        name = ev.get('title', '')
        t    = ev.get('time_et', '')
        note = ev.get('note', '')
        data = ''
        if 'Forecast:' in note:
            parts = [p.strip() for p in note.split('|')]
            fcst  = parts[0].replace('Forecast:', '').strip()
            prev  = parts[1].replace('Prev:', '').strip() if len(parts) > 1 else ''
            if fcst and fcst != '—':
                data = f'  {fcst} f'
                if prev and prev != '—':
                    data += f' / {prev} p'
        event_lines.append(f'{icon} **{t}**  {name}{data}')

    events_text = '\n'.join(event_lines) if event_lines else 'No scheduled events today.'

    # Market — single line
    regime   = risk_state.get('market_regime', '—')
    us10y    = _last('US10Y')
    market_line = (
        f'VIX {_last("VIX")} ({_pct("VIX")})  ·  '
        f'NQ {_pct("NQ")}  ·  '
        f'ES {_pct("ES")}  ·  '
        f'10Y {us10y}%  ·  '
        f'Regime: {regime}'
    )

    # Session quality — tight
    if len(high_events) >= 2:
        sq_label = 'C'
        sq_note  = f'{len(high_events)} HIGH events. Size down. Higher bar for entry.'
    elif len(high_events) == 1:
        ev       = high_events[0]
        sq_label = 'B'
        sq_note  = f'{ev["title"]} at {ev["time_et"]} ET. No entries before event clears.'
    elif risk_state.get('red_folder_week'):
        sq_label = 'B'
        sq_note  = 'Red folder week. Background risk elevated. Standard discipline.'
    else:
        sq_label = 'A'
        sq_note  = 'Clean macro environment. Standard session discipline.'

    fields = [
        _field('Events', events_text, inline=False),
        _spacer(),
        _field('Market', market_line, inline=False),
        _spacer(),
        _field(f'Session Cap: {sq_label}', sq_note, inline=False),
    ]

    return {
        'title':       f'NOVA MACRO BRIEF  ·  {now.strftime("%A %b %d").upper()}',
        'description': 'Session prep  ·  NY open 09:30 ET',
        'fields':      fields,
        'color':       0x9B59B6,
        'footer':      {'text': f'NOVA Macro  ·  Daily Brief  ·  {now.strftime("%H:%M ET")}'},
        'timestamp':   datetime.now(timezone.utc).isoformat(),
    }


# ── Discord delivery ───────────────────────────────────────────────────────────

def _deliver_to_macro_channel(embed: dict) -> dict:
    """Deliver embed to #macro-risk. Returns result dict."""
    channel = DISCORD_CHANNEL_MACRO
    if not DISCORD_BOT_TOKEN:
        return {'ok': False, 'error': 'DISCORD_BOT_TOKEN not configured'}
    if not channel:
        return {'ok': False, 'error': 'DISCORD_CHANNEL_MACRO not set'}

    url = f'{_DISCORD_API}/channels/{channel}/messages'
    try:
        r = requests.post(
            url,
            headers={
                'Authorization': f'Bot {DISCORD_BOT_TOKEN}',
                'Content-Type':  'application/json',
            },
            json={'embeds': [embed]},
            timeout=20,
        )
        if r.status_code in (200, 201):
            return {'ok': True}
        return {'ok': False, 'status': r.status_code, 'error': r.text[:200]}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ── Anti-spam helpers ──────────────────────────────────────────────────────────

def _already_delivered(state: dict, event_key: str, phase: str) -> bool:
    phases_done = state.get('delivered', {}).get(event_key, {}).get('phases', [])
    return phase in phases_done


def _record_delivery(state: dict, event_key: str, phase: str) -> dict:
    if 'delivered' not in state:
        state['delivered'] = {}
    entry = state['delivered'].setdefault(event_key, {'phases': [], 'last_ts': ''})
    if phase not in entry['phases']:
        entry['phases'].append(phase)
    entry['last_ts'] = datetime.now(timezone.utc).isoformat()
    return state


def _breaking_key(headline: str) -> str:
    return headline[:50].lower().strip()


def _vix_cooldown_expired(state: dict, minutes: int = 60) -> bool:
    ts_str = state.get('vix_alert_ts', '')
    if not ts_str:
        return True
    try:
        last = datetime.fromisoformat(ts_str)
        elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 60
        return elapsed >= minutes
    except Exception:
        return True


# ── Public API ─────────────────────────────────────────────────────────────────

def run_macro_calendar_check() -> list[dict]:
    """
    Phase-based macro calendar alert delivery.
    Call every 5 minutes alongside check_todays_events().

    Delivers:
    - APPROACHING: first alert 15–45 min before event (HIGH+ only)
    - IMMINENT:    final warning 0–10 min before event (HIGH+ only)
    - MEDIUM events: APPROACHING only

    Returns list of result dicts for each attempted delivery.
    """
    macro_data = _read_json(_MACRO_EVENTS_FILE)
    all_events = macro_data.get('events', [])
    today      = now_ny().strftime('%Y-%m-%d')
    state      = _load_macro_state()
    results    = []

    today_events = [e for e in all_events if e.get('date') == today]

    for ev in today_events:
        phase, mins = _compute_phase_and_mins(ev.get('time_et', ''))
        if phase not in ('APPROACHING', 'IMMINENT'):
            continue  # Discord alerts only fire pre-event (not post-event or expired)

        severity, category = _classify_event(ev)

        # Only deliver MEDIUM and above
        if severity == LOW:
            continue

        # Delivery rules:
        # CRITICAL/HIGH → deliver at both APPROACHING and IMMINENT
        # MEDIUM        → deliver at APPROACHING only
        if severity == MEDIUM and phase == 'IMMINENT':
            continue

        event = MacroEvent(
            title         = ev.get('title', ''),
            time_et       = ev.get('time_et', ''),
            date          = ev.get('date', today),
            importance    = ev.get('importance', ''),
            category      = category,
            severity      = severity,
            note          = ev.get('note', ''),
            source        = ev.get('source', ''),
            minutes_away  = mins,
            phase         = phase,
        )

        if _already_delivered(state, event.event_key, phase):
            continue

        embed  = _build_calendar_embed(event)
        result = _deliver_to_macro_channel(embed)
        result['event'] = event.title
        result['phase'] = phase
        results.append(result)

        if result.get('ok'):
            state = _record_delivery(state, event.event_key, phase)
            _save_macro_state(state)
            print(f'[macro-discord] Delivered {severity} {phase} — {event.title}')
        else:
            print(f'[macro-discord] Delivery failed — {event.title}: {result.get("error")}')

    return results


def run_macro_morning_brief() -> dict:
    """
    Deliver the daily morning macro brief to #macro-risk.
    Call this once per day, targeting the 09:00–09:20 ET window.
    Checks if already delivered today before sending.
    """
    state = _load_macro_state()
    today = now_ny().strftime('%Y-%m-%d')

    if state.get('morning_brief_date') == today:
        return {'ok': True, 'skipped': True, 'reason': 'Already delivered today'}

    macro_data   = _read_json(_MACRO_EVENTS_FILE)
    risk_state   = _read_json(_RISK_STATE_FILE)
    all_events   = macro_data.get('events', [])
    today_events = [
        e for e in all_events
        if e.get('date') == today and e.get('importance') in ('high', 'medium')
    ]
    today_events.sort(key=lambda e: e.get('time_et', ''))

    embed  = _build_morning_brief_embed(today_events, risk_state)
    result = _deliver_to_macro_channel(embed)

    if result.get('ok'):
        state['morning_brief_date'] = today
        _save_macro_state(state)
        print(f'[macro-discord] Morning brief delivered — {len(today_events)} events today')

    return result


def run_vix_volatility_check(vix_threshold: float = 20.0) -> Optional[dict]:
    """
    Monitor VIX for elevated conditions and deliver a volatility warning.
    Call every 5 minutes alongside the finnhub cycle.
    60-minute cooldown between VIX alerts.

    vix_threshold: VIX level above which a warning fires (default 20.0).
    """
    risk_state = _read_json(_RISK_STATE_FILE)
    snap       = risk_state.get('market_snapshot', {})
    vix_data   = snap.get('VIX', {})
    vix_last   = vix_data.get('last')
    vix_pct    = vix_data.get('pct', 0)
    regime     = risk_state.get('market_regime', '')

    if not vix_last or float(vix_last) < vix_threshold:
        return None

    vix_f     = float(vix_last)
    vix_pct_f = float(vix_pct)
    severity  = _classify_vix(vix_f, vix_pct_f)

    nq_pct = float((snap.get('NQ') or {}).get('pct') or 0)
    es_pct = float((snap.get('ES') or {}).get('pct') or 0)

    state = _load_macro_state()
    if not _vix_cooldown_expired(state, minutes=60):
        return {'ok': True, 'skipped': True, 'reason': 'VIX cooldown active'}

    embed  = _build_vix_embed(vix_f, vix_pct_f, regime, severity, nq_pct, es_pct)
    result = _deliver_to_macro_channel(embed)

    if result.get('ok'):
        state['vix_alert_ts'] = datetime.now(timezone.utc).isoformat()
        _save_macro_state(state)
        print(f'[macro-discord] VIX warning delivered — VIX={vix_f:.1f} ({vix_pct_f:+.1f}%)')

    return result


def run_breaking_news_check() -> Optional[dict]:
    """
    Scan all top headlines from the last news cycle for breaking events.
    Fires a Discord alert for each HIGH/CRITICAL headline not yet delivered.
    Deduped per headline — each unique story fires at most once.
    """
    risk_state  = _read_json(_RISK_STATE_FILE)
    news_items  = risk_state.get('_news_items') or []
    last_hl     = risk_state.get('last_headline', '')

    # Build candidate list: all stored items + last_headline as fallback
    candidates: list[tuple[str, str]] = []  # (headline, source)
    seen_in_batch: set[str] = set()
    for item in news_items[:10]:
        hl = item.get('headline', '')
        if hl and hl not in seen_in_batch:
            candidates.append((hl, item.get('source', '')))
            seen_in_batch.add(hl)
    if last_hl and last_hl not in seen_in_batch:
        candidates.append((last_hl, ''))

    if not candidates:
        return None

    state  = _load_macro_state()
    known  = state.get('breaking_keys', [])
    fired  = 0
    result = None

    for headline, source in candidates:
        severity, _ = _classify_breaking(headline)
        if severity == MEDIUM:
            continue

        bk_key = _breaking_key(headline)
        if bk_key in known:
            continue

        embed  = _build_breaking_embed(headline, severity, source)
        result = _deliver_to_macro_channel(embed)

        if result.get('ok'):
            known.append(bk_key)
            fired += 1
            print(f'[macro-discord] Breaking news — {severity}: {headline[:80]}')

    if fired:
        state['breaking_keys'] = known[-30:]
        _save_macro_state(state)

    return result or {'ok': True, 'skipped': True, 'reason': 'No new breaking headlines'}


def get_macro_discord_status() -> dict:
    """Return current macro delivery state for health checks."""
    state      = _load_macro_state()
    today      = now_ny().strftime('%Y-%m-%d')
    risk_state = _read_json(_RISK_STATE_FILE)
    snap       = risk_state.get('market_snapshot', {})
    vix_last   = (snap.get('VIX') or {}).get('last')

    return {
        'channel_configured':    bool(DISCORD_BOT_TOKEN and DISCORD_CHANNEL_MACRO),
        'morning_brief_today':   state.get('morning_brief_date') == today,
        'events_delivered_today': len([
            k for k in state.get('delivered', {})
            if k.startswith(today)
        ]),
        'breaking_delivered':    len(state.get('breaking_keys', [])),
        'vix_alert_ts':          state.get('vix_alert_ts', '—'),
        'vix_current':           vix_last,
        'macro_risk':            risk_state.get('macro_risk', '—'),
        'headline_risk':         risk_state.get('headline_risk', '—'),
        'event_phase':           risk_state.get('event_phase', '—'),
        'next_event':            risk_state.get('next_event', '—'),
    }
