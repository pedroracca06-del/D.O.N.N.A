"""market_reality.py — Market Reality Engine.

Aggregates live price data (yfinance), weekly structure, Grok/X sentiment, and
internal risk state into a single authoritative market_reality_state object.

Refresh schedule: called at the end of every process_finnhub_cycle() (~5 min).
Read path: load_market_reality() → reads donna_market_reality.json, no network call.

All AI prompts and the execution bridge consume this state.
Live price reality outranks cached narratives, prior session bias, and old AI reads.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

_BASE_DIR     = Path(__file__).parent.parent
_REALITY_FILE = _BASE_DIR / 'data' / 'donna_market_reality.json'
_RISK_FILE    = _BASE_DIR / 'data' / 'donna_risk_state.json'
_GROK_FILE    = _BASE_DIR / 'data' / 'donna_grok_intelligence.json'

_NY_TZ = ZoneInfo('America/New_York')


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


# ── Direction / Severity / Displacement ────────────────────────────────────────

def _compute_direction(nq_pct: float, es_pct: float) -> str:
    have_both = nq_pct != 0.0 and es_pct != 0.0
    if have_both and abs(nq_pct - es_pct) > 1.0 and nq_pct * es_pct < 0:
        return 'MIXED'
    avg = (nq_pct + es_pct) / 2 if have_both else (nq_pct or es_pct)
    if avg >= 0.4:
        return 'BULLISH'
    if avg <= -0.4:
        return 'BEARISH'
    if abs(avg) < 0.15:
        return 'NEUTRAL'
    return 'MIXED'


def _compute_severity(nq_pct: float, es_pct: float) -> str:
    magnitude = max(abs(nq_pct), abs(es_pct))
    if magnitude >= 2.5:
        return 'EXTREME'
    if magnitude >= 1.5:
        return 'HIGH'
    if magnitude >= 0.5:
        return 'MEDIUM'
    return 'LOW'


def _compute_displacement(direction: str, severity: str) -> str:
    if direction == 'BEARISH':
        return 'STRONG_BEARISH' if severity in ('HIGH', 'EXTREME') else 'WEAK_BEARISH'
    if direction == 'BULLISH':
        return 'STRONG_BULLISH' if severity in ('HIGH', 'EXTREME') else 'WEAK_BULLISH'
    return 'NEUTRAL'


def _compute_session_drive(direction: str, severity: str, regime: str, session: str) -> str:
    if direction == 'BEARISH' and severity in ('HIGH', 'EXTREME'):
        return 'BEAR_OPEN_DRIVE' if session in ('NY_OPEN', 'NEW_YORK_CASH') else 'BEAR_TREND'
    if direction == 'BULLISH' and severity in ('HIGH', 'EXTREME'):
        return 'BULL_OPEN_DRIVE' if session in ('NY_OPEN', 'NEW_YORK_CASH') else 'BULL_TREND'
    if direction == 'MIXED':
        return 'DIVERGENCE'
    if 'VOLATILE' in regime.upper():
        return 'VOLATILE_CHOP'
    return 'RANGE_BOUND'


def _compute_assistant_tone(direction: str, severity: str, prior_valid: bool) -> str:
    if direction == 'BEARISH':
        if severity == 'EXTREME':
            return 'BEARISH_ALERT'
        if severity == 'HIGH' and not prior_valid:
            return 'DEFENSIVE_REASSESSMENT'
        if severity in ('MEDIUM', 'HIGH'):
            return 'CAUTIOUS'
    if direction == 'BULLISH':
        if severity == 'EXTREME':
            return 'BULLISH_ALERT'
        if severity == 'HIGH':
            return 'CAUTIOUS'
    return 'NORMAL'


# ── Weekly structure detection (yfinance 5d history) ──────────────────────────

def _fetch_weekly_structure() -> dict:
    """
    Detect weekly high/low breaks by comparing today's range against the
    prior 4 days of NQ=F and ES=F data.  Tolerates yfinance outages gracefully.
    """
    result: dict = {
        'structure': 'RANGE',
        'nq_week_high': None, 'nq_week_low': None,
        'es_week_high': None, 'es_week_low': None,
    }
    try:
        structures: list[str] = []
        for yf_sym, label in (('NQ=F', 'nq'), ('ES=F', 'es')):
            hist = yf.Ticker(yf_sym).history(period='5d', interval='1d')
            if hist is None or hist.empty or len(hist) < 2:
                continue
            prior      = hist.iloc[:-1]
            today      = hist.iloc[-1]
            prior_high = float(prior['High'].max())
            prior_low  = float(prior['Low'].min())
            today_low  = float(today['Low'])
            today_high = float(today['High'])
            result[f'{label}_week_high'] = round(prior_high, 2)
            result[f'{label}_week_low']  = round(prior_low, 2)
            tol = prior_high * 0.0005  # 0.05% tolerance
            if today_low < prior_low - tol:
                structures.append('WEEKLY_LOW_BREAK')
            elif today_high > prior_high + tol:
                structures.append('WEEKLY_HIGH_BREAK')
        if 'WEEKLY_LOW_BREAK' in structures:
            result['structure'] = 'WEEKLY_LOW_BREAK'
        elif 'WEEKLY_HIGH_BREAK' in structures:
            result['structure'] = 'WEEKLY_HIGH_BREAK'
    except Exception as exc:
        print(f'[market_reality] weekly structure fetch failed: {exc}')
    return result


# ── Prior context validity check ───────────────────────────────────────────────

def _check_prior_context(direction: str, severity: str, grok: dict) -> tuple[bool, str]:
    """
    Returns (is_valid, reason_if_invalid).
    Invalidated when live price reality strongly contradicts cached sentiment,
    or when the Grok read is too old to trust.
    """
    grok_sentiment = (grok.get('market_sentiment') or '').upper()
    fetched_at_str = grok.get('fetched_at', '')

    if fetched_at_str:
        try:
            fetched_at   = datetime.fromisoformat(fetched_at_str.replace('Z', '+00:00'))
            age_min      = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 60
            if age_min > 45:
                return False, f'Grok intelligence is {age_min:.0f}min old — context stale'
        except Exception:
            pass

    if severity in ('HIGH', 'EXTREME'):
        if direction == 'BEARISH' and grok_sentiment == 'BULLISH':
            return False, f'Grok shows {grok_sentiment} but live price is {direction} at {severity} severity'
        if direction == 'BULLISH' and grok_sentiment == 'BEARISH':
            return False, f'Grok shows {grok_sentiment} but live price is {direction} at {severity} severity'

    return True, ''


# ── Main compute ───────────────────────────────────────────────────────────────

def compute_market_reality() -> dict:
    """
    Compute authoritative market_reality_state.
    Called at end of process_finnhub_cycle() — never call inline from request handlers.
    Saves result to donna_market_reality.json and returns the dict.
    """
    risk     = _read_json(_RISK_FILE)
    grok     = _read_json(_GROK_FILE)
    snapshot = risk.get('market_snapshot', {})

    nq_pct   = _safe_float((snapshot.get('NQ') or {}).get('pct'))
    es_pct   = _safe_float((snapshot.get('ES') or {}).get('pct'))
    nq_price = _safe_float((snapshot.get('NQ') or {}).get('last'))
    es_price = _safe_float((snapshot.get('ES') or {}).get('last'))
    vix      = _safe_float((snapshot.get('VIX') or {}).get('last'))
    regime   = risk.get('market_regime', 'UNKNOWN')
    session  = risk.get('donna_session', 'UNKNOWN')

    direction    = _compute_direction(nq_pct, es_pct)
    severity     = _compute_severity(nq_pct, es_pct)
    displacement = _compute_displacement(direction, severity)

    prior_valid, prior_reason = _check_prior_context(direction, severity, grok)
    assistant_tone = _compute_assistant_tone(direction, severity, prior_valid)
    session_drive  = _compute_session_drive(direction, severity, regime, session)

    weekly    = _fetch_weekly_structure()
    structure = weekly.get('structure', 'RANGE')
    # Weekly break with no corresponding pct move → upgrade severity floor to MEDIUM
    if structure in ('WEEKLY_LOW_BREAK', 'WEEKLY_HIGH_BREAK') and severity == 'LOW':
        severity = 'MEDIUM'

    bullish_exec_allowed   = not (direction == 'BEARISH' and severity in ('HIGH', 'EXTREME'))
    bearish_exec_preferred = direction == 'BEARISH' and severity in ('HIGH', 'EXTREME')
    short_exec_allowed     = not (direction == 'BULLISH' and severity in ('HIGH', 'EXTREME'))
    long_exec_preferred    = direction == 'BULLISH' and severity in ('HIGH', 'EXTREME')

    state = {
        'nq_change_pct':             round(nq_pct, 3),
        'es_change_pct':             round(es_pct, 3),
        'nq_price':                  nq_price,
        'es_price':                  es_price,
        'vix':                       vix,
        'direction':                 direction,
        'severity':                  severity,
        'session_drive':             session_drive,
        'structure':                 structure,
        'nq_week_high':              weekly.get('nq_week_high'),
        'nq_week_low':               weekly.get('nq_week_low'),
        'es_week_high':              weekly.get('es_week_high'),
        'es_week_low':               weekly.get('es_week_low'),
        'displacement':              displacement,
        'prior_context_valid':       prior_valid,
        'prior_context_reason':      prior_reason,
        'grok_sentiment':            grok.get('market_sentiment', 'UNKNOWN'),
        'grok_trade_read':           grok.get('donna_trade_read', ''),
        'x_market_chatter':          grok.get('x_market_chatter', ''),
        'x_stress_signal':           grok.get('x_stress_signal', ''),
        'x_key_catalyst':            grok.get('x_key_catalyst', ''),
        'top_story':                 grok.get('top_story', ''),
        'market_regime':             regime,
        'session':                   session,
        'assistant_tone':            assistant_tone,
        'bullish_execution_allowed': bullish_exec_allowed,
        'bearish_execution_preferred': bearish_exec_preferred,
        'short_execution_allowed':   short_exec_allowed,
        'long_execution_preferred':  long_exec_preferred,
        'last_updated':              _utc_iso(),
    }

    try:
        _REALITY_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')
        print(
            f'[market_reality] {direction} | severity={severity} | '
            f'NQ={nq_pct:+.2f}% ES={es_pct:+.2f}% | structure={structure} | '
            f'tone={assistant_tone}'
        )
    except Exception as exc:
        print(f'[market_reality] save error: {exc}')

    return state


def load_market_reality() -> dict:
    """Load cached market_reality_state from file. No network calls. Safe defaults if missing."""
    data = _read_json(_REALITY_FILE)
    if data:
        return data
    return {
        'direction': 'UNKNOWN',
        'severity': 'LOW',
        'nq_change_pct': 0.0,
        'es_change_pct': 0.0,
        'nq_price': 0.0,
        'es_price': 0.0,
        'vix': 0.0,
        'structure': 'RANGE',
        'displacement': 'NEUTRAL',
        'session_drive': 'UNKNOWN',
        'prior_context_valid': True,
        'prior_context_reason': '',
        'assistant_tone': 'NORMAL',
        'bullish_execution_allowed': True,
        'bearish_execution_preferred': False,
        'short_execution_allowed': True,
        'long_execution_preferred': False,
        'grok_sentiment': 'UNKNOWN',
        'grok_trade_read': '',
        'x_market_chatter': '',
        'x_stress_signal': '',
        'x_key_catalyst': '',
        'top_story': '',
        'last_updated': '',
    }


def format_reality_for_assistant(mr: dict) -> str:
    """
    Compact single-line market reality summary for the assistant context.
    Designed to be minimal so it doesn't inflate Claude's output or destabilise JSON.
    Full format_reality_for_prompt() is for reasoning/grading prompts only.
    """
    direction = mr.get('direction', 'UNKNOWN')
    severity  = mr.get('severity', 'LOW')
    nq_pct    = mr.get('nq_change_pct', 0.0)
    es_pct    = mr.get('es_change_pct', 0.0)
    structure = mr.get('structure', 'RANGE')
    tone      = mr.get('assistant_tone', 'NORMAL')
    longs_ok  = mr.get('bullish_execution_allowed', True)
    shorts_ok = mr.get('short_execution_allowed', True)

    exec_note = ''
    if not longs_ok:
        exec_note = ' | LONGS_BLOCKED'
    elif not shorts_ok:
        exec_note = ' | SHORTS_BLOCKED'

    return (
        f'LIVE_MARKET: NQ {nq_pct:+.2f}% ES {es_pct:+.2f}% | '
        f'{direction} {severity} | {structure} | tone={tone}{exec_note}'
    )


def format_reality_for_prompt(mr: dict) -> str:
    """
    Format market_reality_state into a compact block for AI prompt injection.
    Designed to be prepended before any cached context so Claude reads it first.
    """
    direction = mr.get('direction', 'UNKNOWN')
    severity  = mr.get('severity', 'UNKNOWN')
    nq_pct    = mr.get('nq_change_pct', 0.0)
    es_pct    = mr.get('es_change_pct', 0.0)
    structure = mr.get('structure', 'RANGE')
    disp      = mr.get('displacement', 'NEUTRAL')
    tone      = mr.get('assistant_tone', 'NORMAL')
    prior     = mr.get('prior_context_valid', True)
    vix       = mr.get('vix', 0.0)

    lines = [
        '=== MARKET REALITY (live — overrides all cached context) ===',
        f'Direction: {direction}  |  Severity: {severity}',
        f'NQ: {nq_pct:+.2f}%   ES: {es_pct:+.2f}%   VIX: {vix:.1f}',
        f'Structure: {structure}  |  Displacement: {disp}',
        f'Session drive: {mr.get("session_drive", "UNKNOWN")}',
        f'Grok/X Sentiment: {mr.get("grok_sentiment", "UNKNOWN")}',
    ]

    x_chatter   = mr.get('x_market_chatter', '')
    x_stress    = mr.get('x_stress_signal', '')
    x_catalyst  = mr.get('x_key_catalyst', '')
    top_story   = mr.get('top_story', '')
    trade_read  = mr.get('grok_trade_read', '')

    if x_chatter:
        lines.append(f'X/Twitter chatter: {x_chatter}')
    if x_catalyst:
        lines.append(f'X catalyst: {x_catalyst}')
    if x_stress and x_stress.lower() not in ('none', ''):
        lines.append(f'X stress signal: {x_stress}')
    if top_story:
        lines.append(f'Top story: {top_story}')
    if trade_read:
        lines.append(f'Grok trade read: {trade_read}')

    lines.append(f'Prior context valid: {prior}')
    if not prior and mr.get('prior_context_reason'):
        lines.append(f'  → {mr["prior_context_reason"]}')

    lines.append(f'Required tone: {tone}')

    if not mr.get('bullish_execution_allowed', True):
        lines.append('EXECUTION RULE: LONG signals blocked — bearish severity prohibits counter-trend longs')
    if not mr.get('short_execution_allowed', True):
        lines.append('EXECUTION RULE: SHORT signals blocked — bullish severity prohibits counter-trend shorts')

    lines.append('=== END MARKET REALITY ===')
    return '\n'.join(lines)
