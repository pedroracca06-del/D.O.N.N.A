"""
engines/morning_brief.py -- Compact structured morning brief.

PURPOSE: A trader-readable pre-session intelligence summary.
Readable in under 30 seconds. 5 fields. No prose. No Claude call.

Content:
  THESIS       -- synthesis thesis_state + one-sentence thesis
  DRAW         -- primary liquidity draw (direction + distance + context)
  PARTICIPATION -- RVOL context + session type expectation
  MACRO        -- macro_risk + next event
  WATCH        -- thesis_condition (the key question for today)

Delivery:
  1. donna_intelligence_log.json (MORNING_BRIEF event -- appears in Feed)
  2. Discord SESSION_BRIEF channel (compact embed -- no prose)

Architecture rule:
  Deterministic only. Never calls Claude. Never calls an external API.
  Consumes only existing intelligence JSON files -- all already on disk.

Called from: main.py morning_brief_loop() after existing Telegram brief.
Tracks last_sent_date in donna_morning_brief_compact.json.
Fires once per trading day between 9:00 and 9:25 AM ET.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_NY_TZ = ZoneInfo('America/New_York')

from core.config import (
    DATA_DIR,
    SYNTHESIS_FILE     as _SYN_FILE,
    LIQUIDITY_FILE     as _LIQ_FILE,
    PARTICIPATION_FILE as _P_FILE,
    RISK_STATE_FILE    as _RISK_FILE,
    SESSION_MEMORY_FILE as _MEM_FILE,
)

_COMPACT_STATE_FILE = DATA_DIR / 'donna_morning_brief_compact.json'


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


def _ny_now() -> datetime:
    return datetime.now(_NY_TZ)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _already_sent_today() -> bool:
    try:
        state = _read_json(_COMPACT_STATE_FILE)
        return state.get('last_sent_date') == _ny_now().strftime('%Y-%m-%d')
    except Exception:
        return False


def _mark_sent() -> None:
    try:
        state = {
            'last_sent_date': _ny_now().strftime('%Y-%m-%d'),
            'last_sent_utc':  _utc_iso(),
        }
        _COMPACT_STATE_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')
    except Exception:
        pass


# ── Brief construction ────────────────────────────────────────────────────────

def _build_thesis_line(synth: dict) -> str:
    state  = synth.get('thesis_state', 'UNKNOWN')
    thesis = (synth.get('market_thesis') or '').strip()
    conf   = synth.get('confidence', '')
    if not thesis or thesis.startswith('Market intelligence data'):
        return f'{state} -- insufficient data'
    conf_str = f' [{conf}]' if conf else ''
    return f'{state}{conf_str} -- {thesis}'


def _build_draw_line(liq: dict) -> str:
    liq_nq = liq.get('nq', {})
    draw   = liq_nq.get('primary_draw') or {}
    u_above = liq_nq.get('untapped_above', 0)
    u_below = liq_nq.get('untapped_below', 0)

    if draw.get('label') and draw.get('side'):
        d_pts  = abs(_safe_float(draw.get('distance_pts', 0)))
        d_side = 'below' if draw.get('side') == 'BELOW' else 'above'
        d_lbl  = draw['label']
        draw_str = f'{d_lbl} ({d_pts:.0f}pts {d_side})'
    else:
        draw_str = 'no clear primary draw'

    levels_str = f'{u_above} above / {u_below} below untapped'
    return f'{draw_str} -- {levels_str}'


def _build_participation_line(part: dict) -> str:
    bias      = part.get('participation_bias', 'UNKNOWN')
    sess_type = part.get('session_type', 'UNCERTAIN')
    nq_data   = part.get('nq') or {}
    rvol      = _safe_float(nq_data.get('rvol', 0.0))

    rvol_str = f'RVOL {rvol:.2f}x' if rvol > 0 else 'RVOL unavailable'
    return f'{bias} ({rvol_str}) -- session type: {sess_type}'


def _build_macro_line(risk: dict) -> str:
    macro_risk  = (risk.get('macro_risk') or 'LOW').upper()
    next_event  = risk.get('next_event', '') or 'none scheduled'
    event_phase = risk.get('event_phase', '')

    phase_str = f' [{event_phase.upper()}]' if event_phase and event_phase.lower() not in ('none', '') else ''
    return f'{macro_risk} risk{phase_str} -- next event: {next_event}'


def _build_watch_line(synth: dict, mem: dict) -> str:
    condition = (synth.get('thesis_condition') or '').strip()
    narrative = mem.get('rolling_narrative', '')

    if condition and not condition.startswith('Insufficient'):
        return condition
    if narrative and narrative != 'Session memory unavailable.':
        return narrative
    return 'No prior session context available -- observe structure at open.'


def build_compact_brief() -> dict:
    """
    Build the compact morning brief from existing intelligence state.
    Returns a structured dict ready to emit as an INTELLIGENCE event.
    """
    synth = _read_json(_SYN_FILE)
    liq   = _read_json(_LIQ_FILE)
    part  = _read_json(_P_FILE)
    risk  = _read_json(_RISK_FILE)
    mem   = _read_json(_MEM_FILE)

    thesis_line      = _build_thesis_line(synth)
    draw_line        = _build_draw_line(liq)
    part_line        = _build_participation_line(part)
    macro_line       = _build_macro_line(risk)
    watch_line       = _build_watch_line(synth, mem)

    # Structured brief text (5 lines -- readable in under 30 seconds)
    brief_text = (
        f'THESIS       {thesis_line}\n'
        f'DRAW         {draw_line}\n'
        f'PARTICIPATION {part_line}\n'
        f'MACRO        {macro_line}\n'
        f'WATCH        {watch_line}'
    )

    date_str = _ny_now().strftime('%A, %b %d').replace(' 0', ' ')

    return {
        'date':               _ny_now().strftime('%Y-%m-%d'),
        'date_label':         date_str,
        'thesis_state':       synth.get('thesis_state', 'UNKNOWN'),
        'thesis':             synth.get('market_thesis', ''),
        'confidence':         synth.get('confidence', ''),
        'condition':          synth.get('thesis_condition', ''),
        'liquidity_draw':     draw_line,
        'participation':      part_line,
        'macro_risk':         (risk.get('macro_risk') or 'LOW').upper(),
        'session_narrative':  mem.get('rolling_narrative', ''),
        'key_question':       watch_line,
        'brief_text':         brief_text,
    }


# ── Delivery ──────────────────────────────────────────────────────────────────

def _emit_to_feed(brief: dict) -> None:
    """Write MORNING_BRIEF to the intelligence log so it appears in the Feed."""
    try:
        from engines.synthesis import _emit_intelligence_event
        _emit_intelligence_event('MORNING_BRIEF', {
            'symbol':        'MARKET',
            'session':       'PRE_MARKET',
            'thesis_state':  brief['thesis_state'],
            'thesis':        brief['thesis'],
            'confidence':    brief['confidence'],
            'condition':     brief['condition'],
            'liquidity_draw':    brief['liquidity_draw'],
            'participation':     brief['participation'],
            'macro_risk':        brief['macro_risk'],
            'session_narrative': brief['session_narrative'],
            'key_question':      brief['key_question'],
            'brief_text':        brief['brief_text'],
        })
        print(f'[morning_brief] Feed event emitted for {brief["date"]}')
    except Exception as exc:
        print(f'[morning_brief] feed emit error: {exc}')


def _send_to_discord(brief: dict) -> None:
    """
    Send compact brief to Discord SESSION_BRIEF channel.
    Uses a simple embed -- no elaborate formatting.
    """
    try:
        import os, requests as _req
        token   = os.getenv('DISCORD_BOT_TOKEN', '').strip()
        channel = os.getenv('DISCORD_CHANNEL_MORNING_BRIEF', '').strip() or \
                  os.getenv('DISCORD_CHANNEL_LIVE', '').strip()
        if not token or not channel:
            print('[morning_brief] Discord not configured -- skipping Discord send')
            return

        state_label = brief['thesis_state']
        date_label  = brief['date_label']

        embed = {
            'title':       f'NOVA MORNING BRIEF -- {date_label}',
            'description': f'```\n{brief["brief_text"]}\n```',
            'color':       0x1a1a2e,
            'footer':      {'text': 'NOVA Intelligence -- pre-session brief'},
        }

        resp = _req.post(
            f'https://discord.com/api/v10/channels/{channel}/messages',
            headers={
                'Authorization': f'Bot {token}',
                'Content-Type':  'application/json',
            },
            json={'embeds': [embed]},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            print(f'[morning_brief] Discord sent for {brief["date"]}')
        else:
            print(f'[morning_brief] Discord error {resp.status_code}: {resp.text[:200]}')
    except Exception as exc:
        print(f'[morning_brief] Discord send error: {exc}')


# ── Main entry point ──────────────────────────────────────────────────────────

def compute_and_deliver_morning_brief() -> dict:
    """
    Build the compact brief, emit to Feed, send to Discord.
    Called once per trading day from main.py morning_brief_loop().
    Returns the brief dict or empty dict if already sent today.
    """
    if _already_sent_today():
        return {}

    try:
        brief = build_compact_brief()
        _emit_to_feed(brief)
        _send_to_discord(brief)
        _mark_sent()
        print(f'[morning_brief] Compact brief delivered for {brief["date"]}')
        return brief
    except Exception as exc:
        print(f'[morning_brief] delivery error: {exc}')
        return {}
