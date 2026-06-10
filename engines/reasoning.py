"""donna_nova_reasoning.py — NOVA Phase 2C/2E: Live Market Reasoning Pipeline.

Architecture:
  TradingView (MCP/CDP) → chart context reader
  → session evaluator (fast, deterministic)
  → PROS / ORB / IB / invalidation evaluators (deterministic, no API call)
  → signal classifier  →  Claude (quality grader + alert generation)
  → AlertData → donna_alert_engine → Discord

Claude is called ONLY when a deterministic signal is detected.
On Render: MCP not available → gracefully returns empty (webhook path remains live).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────────

_BASE_DIR   = Path(__file__).parent.parent
_MCP_DIR    = _BASE_DIR / 'mcp' / 'tradingview'
_RULES_FILE = _BASE_DIR / 'nova_knowledge_core' / 'RULES' / 'nova_strategy_core.json'
_RULES_ROOT = _BASE_DIR / 'nova_strategy_core.json'

# ── Config imports ─────────────────────────────────────────────────────────────

try:
    from core.config import client as _anthropic_client, ANTHROPIC_MODEL, now_ny
    from core.state_engine import DonnaStateEngine as _DSE
    _state_engine = _DSE()
except Exception:
    _anthropic_client = None
    ANTHROPIC_MODEL   = 'claude-haiku-4-5-20251001'
    _state_engine     = None
    def now_ny():
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('America/New_York'))

try:
    from delivery.alert_engine import AlertData, HEADS_UP, EXECUTION_READY, INVALIDATION, NO_TRADE
except Exception:
    AlertData       = None
    HEADS_UP        = 'HEADS_UP'
    EXECUTION_READY = 'EXECUTION_READY'
    INVALIDATION    = 'INVALIDATION'
    NO_TRADE        = 'NO_TRADE'

try:
    from engines import market_memory as _market_memory
except Exception:
    _market_memory = None

try:
    from engines import directional_pressure as _dp_engine
except Exception:
    _dp_engine = None

try:
    from services.execution_trace import log_reasoning_snapshot as _log_snapshot
except Exception:
    _log_snapshot = None

# ── MCP data collection ────────────────────────────────────────────────────────

def _run_mcp(*args: str, timeout: int = 10) -> Optional[dict]:
    """Run a TradingView MCP CLI command. Returns parsed JSON or None."""
    try:
        result = subprocess.run(
            ['node', 'src/cli/index.js', *args],
            cwd=str(_MCP_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if data.get('success') is not False:
                return data
    except Exception:
        pass
    return None


def read_chart_context() -> dict:
    """
    Collect all chart data from the currently active TradingView tab.
    Only reads NOVA indicator data — ignores third-party studies.
    Returns {'connected': False} if TradingView is not reachable.
    """
    ctx: dict = {'connected': False}

    state = _run_mcp('state')
    if not state:
        return ctx
    ctx['connected'] = True
    ctx['symbol']    = state.get('symbol', 'UNKNOWN')
    ctx['timeframe'] = state.get('resolution', '1')

    quote = _run_mcp('quote')
    if quote:
        ctx['price']  = quote.get('last') or quote.get('close')
        ctx['volume'] = quote.get('volume')
        ctx['high']   = quote.get('high')
        ctx['low']    = quote.get('low')

    ohlcv = _run_mcp('ohlcv', '--count', '30', '--summary')
    if ohlcv:
        ctx['ohlcv'] = {
            'range_30':   ohlcv.get('range'),
            'change_pct': ohlcv.get('change_pct'),
            'avg_volume': ohlcv.get('avg_volume'),
            'high_30':    ohlcv.get('high'),
            'low_30':     ohlcv.get('low'),
            'last_5':     ohlcv.get('last_5_bars', []),
        }

    labels = _run_mcp('data', 'labels', '--study-filter', 'NOVA')
    if labels:
        nova_studies = [s for s in labels.get('studies', []) if 'NOVA' in s.get('name', '')]
        if nova_studies:
            ctx['nova_labels'] = nova_studies[0].get('labels', [])

    lines = _run_mcp('data', 'lines', '--study-filter', 'NOVA')
    if lines:
        nova_studies = [s for s in lines.get('studies', []) if 'NOVA' in s.get('name', '')]
        if nova_studies:
            ctx['nova_levels'] = nova_studies[0].get('horizontal_levels', [])

    tables = _run_mcp('data', 'tables', '--study-filter', 'NOVA')
    if tables:
        nova_studies = [s for s in tables.get('studies', []) if 'NOVA' in s.get('name', '')]
        if nova_studies:
            raw_tables = nova_studies[0].get('tables', [])
            ctx['nova_tables'] = [t.get('rows', []) for t in raw_tables]

    return ctx


# Instruments the scanner evaluates every cycle.
# Scanner is instrument-native — execution routing (ETF proxy vs direct futures)
# is handled downstream by the bridge and broker layer, not here.
_SCAN_SYMBOLS = [
    'CME_MINI:MES1!',   # Micro E-mini S&P 500
    'CME_MINI:MNQ1!',   # Micro E-mini Nasdaq-100
]

_HOME_SYMBOL      = 'CME_MINI:MNQ1!'  # chart always returns here after scan
_SYMBOL_DWELL_SEC = 90                # seconds to display each symbol before reading


def _collect_all_contexts() -> list[dict]:
    """
    Read chart context for every instrument in _SCAN_SYMBOLS.

    Flow per symbol:
      1. Switch chart to target symbol
      2. Dwell for _SYMBOL_DWELL_SEC so the trader can watch the chart
      3. Read full NOVA context (tables, levels, labels, OHLCV)

    After all symbols are read, restores to _HOME_SYMBOL (MNQ).
    Total cycle time: _SYMBOL_DWELL_SEC × len(_SCAN_SYMBOLS) ≈ 3 min.
    The monitor should NOT sleep after this call — dwell time is the cadence.

    Returns list of chart contexts (one per symbol). Empty if TradingView
    is unreachable.
    """
    import time

    current = _run_mcp('symbol')
    if not current or not current.get('success'):
        ctx = read_chart_context()
        return [ctx] if ctx.get('connected') else []

    contexts: list[dict] = []

    for symbol in _SCAN_SYMBOLS:
        switched = _run_mcp('symbol', symbol, timeout=20)
        if not switched or not switched.get('success'):
            print(f'[nova-scan] symbol switch failed: {symbol}')
            continue

        sym_short = symbol.replace('CME_MINI:', '').replace('1!', '')
        print(f'[nova-scan] watching {sym_short} for {_SYMBOL_DWELL_SEC}s...')
        time.sleep(_SYMBOL_DWELL_SEC)

        ctx = read_chart_context()
        if ctx.get('connected'):
            ctx['scanned_symbol'] = symbol
            ctx['is_primary']     = (symbol == _SCAN_SYMBOLS[0])
            contexts.append(ctx)
            print(f'[nova-scan] {sym_short}  price={ctx.get("price")}  '
                  f'tables={len(ctx.get("nova_tables", []))}')
        else:
            print(f'[nova-scan] no context for {symbol}')

    # Always return to home symbol
    _run_mcp('symbol', _HOME_SYMBOL, timeout=20)

    return contexts


# ── NOVA table parsing ─────────────────────────────────────────────────────────

def parse_nova_tables(raw_tables: list[list[str]]) -> dict:
    """
    Parse NOVA indicator table rows into structured dicts.

    ES/MES has 3 tables: NOVA ENGINE, ORB CONSOLE, PROS ENGINE.
    NQ/other has 2 tables: NOVA ENGINE, PROS ENGINE.
    Tables are identified by header key, not index — index-based fails on ES/MES
    because raw_tables[1] is ORB CONSOLE, not PROS ENGINE.
    """
    parsed = {}

    def _parse_rows(rows: list[str]) -> dict:
        result = {}
        for row in rows:
            if ' | ' in row:
                key, _, val = row.partition(' | ')
                result[key.strip()] = val.strip()
        return result

    for table_rows in raw_tables:
        if not table_rows:
            continue
        d = _parse_rows(table_rows)
        if 'NOVA ENGINE' in d:
            parsed['main'] = d
        elif 'PROS ENGINE' in d:
            parsed['pros'] = d
        elif 'ORB CONSOLE' in d:
            parsed['orb'] = d

    # Fallback to index order if header detection found nothing
    if 'main' not in parsed and len(raw_tables) >= 1:
        parsed['main'] = _parse_rows(raw_tables[0])
    if 'pros' not in parsed and len(raw_tables) >= 2:
        parsed['pros'] = _parse_rows(raw_tables[1])

    return parsed


# ── Session context evaluator (fast, deterministic) ────────────────────────────

def _session_info(mins: int, weekday: int) -> dict:
    """
    Classify the current time into a trading session.

    Sessions (ET):
      ASIA       20:00-00:00  quality C  — PROS only, no ORB
      DEAD_ZONE  00:00-03:00  quality dead
      LONDON     03:00-08:30  quality B  — PROS only, no ORB
      PRE_MARKET 08:30-09:30  quality dead
      NY_OPEN    09:30-11:00  quality A  — PROS + ORB (highest priority)
      NY_AM      11:00-12:30  quality B  — PROS continuation
      LUNCH      12:30-13:30  quality dead
      NY_PM      13:30-16:00  quality C  — PROS only
      POST_CLOSE 16:00-18:00  quality dead
      WEEKEND    Saturday / Sunday before 18:00  — dead

    Sunday 18:00+ is treated as ASIA (CME Globex reopens 18:00 ET Sunday).
    """
    # Saturday: fully dead
    if weekday == 5:
        return {'name': 'WEEKEND', 'quality': 'dead', 'active': False, 'poll_interval': 300}
    # Sunday before CME reopen
    if weekday == 6 and mins < 18 * 60:
        return {'name': 'WEEKEND', 'quality': 'dead', 'active': False, 'poll_interval': 300}

    if 9 * 60 + 30 <= mins <= 11 * 60:
        return {'name': 'NY_OPEN',    'quality': 'A',    'active': True,  'poll_interval': 60}
    if 11 * 60 < mins <= 12 * 60 + 30:
        return {'name': 'NY_AM',      'quality': 'B',    'active': True,  'poll_interval': 60}
    if 12 * 60 + 30 < mins < 13 * 60 + 30:
        return {'name': 'LUNCH',      'quality': 'dead', 'active': False, 'poll_interval': 300}
    if 13 * 60 + 30 <= mins <= 16 * 60:
        return {'name': 'NY_PM',      'quality': 'C',    'active': True,  'poll_interval': 60}
    if 16 * 60 < mins < 18 * 60:
        return {'name': 'POST_CLOSE', 'quality': 'dead', 'active': False, 'poll_interval': 300}
    if mins >= 18 * 60:
        return {'name': 'ASIA',       'quality': 'C',    'active': True,  'poll_interval': 60}
    if mins < 3 * 60:
        return {'name': 'DEAD_ZONE',  'quality': 'dead', 'active': False, 'poll_interval': 300}
    if 3 * 60 <= mins < 8 * 60 + 30:
        return {'name': 'LONDON',     'quality': 'B',    'active': True,  'poll_interval': 60}
    if 8 * 60 + 30 <= mins < 9 * 60 + 30:
        return {'name': 'PRE_MARKET', 'quality': 'dead', 'active': False, 'poll_interval': 120}
    return     {'name': 'UNKNOWN',    'quality': 'dead', 'active': False, 'poll_interval': 300}


def evaluate_session_context() -> dict:
    """
    Evaluate current session state without calling Claude.
    Returns facts used as hard constraints throughout the pipeline.
    """
    now  = now_ny()
    mins = now.hour * 60 + now.minute
    sess = _session_info(mins, now.weekday())

    ctx = {
        'time_et':          now.strftime('%H:%M ET'),
        'day':              now.strftime('%A'),
        'session':          sess['name'],
        'session_quality':  sess['quality'],
        'is_active':        sess['active'],
        'is_dead_zone':     not sess['active'],
        'poll_interval':    sess['poll_interval'],
        'ib_window_closed': mins >= 10 * 60 + 30,
        # Legacy — True only for NY_OPEN; kept for Claude prompt compatibility
        'in_window':        sess['name'] == 'NY_OPEN',
        'daily_trades':     0,
        'daily_loss_hit':   False,
        'first_trade_won':  None,
    }

    if _state_engine:
        try:
            ctx['daily_trades']   = _state_engine.get('daily_trade_count') or 0
            ctx['daily_loss_hit'] = _state_engine.get('daily_loss_trade_hit') or False
            first_outcome         = _state_engine.get('first_trade_outcome')
            ctx['first_trade_won'] = (first_outcome == 'WIN') if first_outcome else None
        except Exception:
            pass

    # session_blocked = account limits only — quality filtering is handled in _classify_signal
    ctx['session_blocked'] = (
        ctx['daily_loss_hit'] or
        ctx['daily_trades'] >= 2 or
        (ctx['daily_trades'] == 1 and ctx['first_trade_won'] is False)
    )

    return ctx


# ── Level extraction helpers ───────────────────────────────────────────────────

def _extract_level(labels: list, levels: list, keyword: str) -> Optional[float]:
    """Extract a named price level from NOVA labels or horizontal lines."""
    kw = keyword.upper()

    for item in labels:
        if isinstance(item, dict):
            text = str(item.get('text', '') or item.get('label', '') or item.get('name', '')).upper()
            if kw in text:
                val = item.get('price') or item.get('value') or item.get('y')
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass

    for item in levels:
        if isinstance(item, dict):
            name = str(item.get('name', '') or item.get('title', '') or item.get('text', '')).upper()
            if kw in name:
                val = item.get('price') or item.get('value') or item.get('y')
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass

    return None


# ── Deterministic evaluators ──────────────────────────────────────────────────

def _evaluate_price_structure(
    chart_ctx:  dict,
    ib_eval:    dict,
    pros_eval:  dict,
    main_state: dict,
) -> dict:
    """
    State-based OTE detection from raw price and fib math.

    Architecture principle: Pine events CONTRIBUTE to execution intelligence —
    they do not DEFINE it. A valid PROS environment persists even after Pine's
    one-bar prosContinuation reference is consumed. This evaluator detects OTE
    from market state directly so the system stays alert through the full window.

    Returns has_ote=True when price is in the 0.618–0.786 retracement zone
    relative to the 30-bar swing, regardless of indicator trigger state.
    """
    price = chart_ctx.get('price')
    ohlcv = chart_ctx.get('ohlcv', {})

    try:
        price   = float(price)
        high_30 = float(ohlcv.get('high_30') or 0)
        low_30  = float(ohlcv.get('low_30')  or 0)
    except (TypeError, ValueError):
        return {'has_ote': False, 'reason': 'invalid price data'}

    if not high_30 or not low_30 or high_30 <= low_30:
        return {'has_ote': False, 'reason': 'no 30-bar range data'}

    swing_range = high_30 - low_30
    if swing_range < 8:
        return {'has_ote': False, 'reason': f'range {swing_range:.1f}pts too narrow'}

    ib_draw = ib_eval.get('draw', 'UNCLEAR')
    ib_high = ib_eval.get('ib_high')
    ib_low  = ib_eval.get('ib_low')
    cmd_up  = main_state.get('CMD', '').upper()
    displ   = (main_state.get('PROS', '') or '').upper()

    # Fib levels from the 30-bar swing
    # LONG: displacement was DOWN → retracing UP into these levels
    long_ote_lo  = low_30  + swing_range * 0.618
    long_ote_hi  = low_30  + swing_range * 0.705
    long_ext_hi  = low_30  + swing_range * 0.786   # outer boundary

    # SHORT: displacement was UP → retracing DOWN into these levels
    short_ote_hi = high_30 - swing_range * 0.618
    short_ote_lo = high_30 - swing_range * 0.705
    short_ext_lo = high_30 - swing_range * 0.786   # outer boundary

    in_long_ote  = long_ote_lo  <= price <= long_ext_hi
    in_short_ote = short_ext_lo <= price <= short_ote_hi

    if not in_long_ote and not in_short_ote:
        return {
            'has_ote':   False,
            'reason':    f'price {price} outside OTE zones',
            'long_ote':  f'{long_ote_lo:.2f}–{long_ext_hi:.2f}',
            'short_ote': f'{short_ext_lo:.2f}–{short_ote_hi:.2f}',
        }

    # Direction: IB draw is primary, CMD/DISPL secondary, then price-zone logic
    bias_long  = (ib_draw == 'IB HIGH'
                  or 'LONG' in cmd_up or 'BUY' in cmd_up or 'BULL' in cmd_up
                  or 'BULL' in displ)
    bias_short = (ib_draw == 'IB LOW'
                  or 'SHORT' in cmd_up or 'SELL' in cmd_up or 'BEAR' in cmd_up
                  or 'BEAR' in displ)

    direction = 'N/A'
    if in_long_ote and not bias_short:
        direction = 'LONG'
    elif in_short_ote and not bias_long:
        direction = 'SHORT'
    elif in_long_ote and in_short_ote:
        # Overlapping zone — use bias
        if bias_long:
            direction = 'LONG'
        elif bias_short:
            direction = 'SHORT'

    if direction == 'N/A':
        return {'has_ote': False, 'reason': 'direction bias conflicts with OTE zone'}

    if direction == 'LONG':
        fib_pct  = (price - low_30)  / swing_range
        clean    = long_ote_lo <= price <= long_ote_hi
        ote_lo, ote_hi = long_ote_lo, long_ext_hi
    else:
        fib_pct  = (high_30 - price) / swing_range
        clean    = short_ote_lo <= price <= short_ote_hi
        ote_lo, ote_hi = short_ext_lo, short_ote_hi

    ib_aligned = (
        (direction == 'LONG'  and ib_high and price < ib_high) or
        (direction == 'SHORT' and ib_low  and price > ib_low)
    )

    return {
        'has_ote':      True,
        'direction':    direction,
        'fib_pct':      round(fib_pct, 3),
        'clean_ote':    clean,
        'swing_high':   high_30,
        'swing_low':    low_30,
        'swing_range':  round(swing_range, 2),
        'ote_lo':       round(ote_lo,  2),
        'ote_hi':       round(ote_hi,  2),
        'ib_aligned':   ib_aligned,
        'source':       'price_structure',
    }


def _evaluate_pros_phase(main_state: dict, pros_state: dict, chart_ctx: dict) -> dict:
    """
    Detect PROS setup phase from NOVA indicator table values.
    Does not call Claude — maps known table values to signal states.

    Field mapping from nova_execution_v1.pine:
      main_state['PROS']        = prosEngineState  (summary: CONTINUATION, BUILDING, ACTIVE, WAIT)
      pros_state['PROS ENGINE'] = prosEngineState  (same value, PROS table header)
      pros_state['OTE']         = prosOteText      (TAGGED / MID ONLY / SHALLOW / —)
      pros_state['RETRACE']     = prosRetraceText  (OTE / DEEP / MID / ABOVE / —)
      pros_state['CONT']        = prosContText     (CONFIRMED / BUILDING / WAIT / —)
      pros_state['DISPL']       = prosDisplText    (BULL / BEAR + arrow)
      main_state['CMD']         = donnaCommand     (BUY / SELL / WAIT)
      main_state['STATE']       = donnaScenario    (overall system state — NOT PROS phase)
    """
    # PROS engine phase — ASCII keywords, encoding-safe across CDP
    pros_engine  = (pros_state.get('PROS ENGINE', '') or main_state.get('PROS', '')).upper()
    cmd_up       = main_state.get('CMD', '').upper()
    displ_up     = pros_state.get('DISPL', '').upper()
    pros_ote_up  = pros_state.get('OTE', '').upper()
    pros_retrace = pros_state.get('RETRACE', '').upper()
    pros_cont_up = pros_state.get('CONT', '').upper()

    # Direction: CMD is unconditionally authoritative.
    # DISPL describes structural context (the leg price displaced from), not trade direction.
    # DISPL is only used when CMD is neutral (WAIT/empty) — never overrides an explicit CMD.
    # Bug case: CMD=SELL + DISPL=BULL must route SHORT, not LONG.
    direction = 'N/A'
    if cmd_up in ('BUY', 'LONG'):
        direction = 'LONG'
    elif cmd_up in ('SELL', 'SHORT'):
        direction = 'SHORT'
    elif 'BULL' in displ_up:
        direction = 'LONG'
    elif 'BEAR' in displ_up:
        direction = 'SHORT'

    # Phase from prosEngineState keywords (all ASCII — arrow chars are skipped intentionally)
    if 'CONTINUATION' in pros_engine:
        # prosContinuationBull/Bear fired — sequence complete, setup confirmed
        phase           = 'SETUP_READY'
        signal_strength = 'high'
    elif 'BUILDING' in pros_engine:
        # prosConFreshBull/Bear — reference anchored, continuation forming
        if 'TAGGED' in pros_ote_up:
            phase           = 'OTE_TAGGED'
            signal_strength = 'high'
        elif 'DEEP' in pros_ote_up or pros_retrace in ('OTE', 'DEEP'):
            # DEEP in OTE field = over-retrace (price traversed OTE zone going deeper)
            # Riskier than a clean tag but OTE was still reached — treat as approaching
            phase           = 'OTE_APPROACHING'
            signal_strength = 'medium'
        else:
            phase           = 'BUILDING'
            signal_strength = 'medium'
    elif 'ACTIVE' in pros_engine:
        # Leg valid — displacement exists, rejection/continuation not yet fired
        if 'TAGGED' in pros_ote_up:
            phase           = 'OTE_TAGGED'
            signal_strength = 'high'
        elif 'DEEP' in pros_ote_up or pros_retrace in ('OTE', 'DEEP'):
            # DEEP in OTE field = over-retrace — still worth monitoring, lower conviction
            phase           = 'OTE_APPROACHING'
            signal_strength = 'medium'
        else:
            phase           = 'BUILDING'
            signal_strength = 'low'
    else:
        # WAIT or empty — no active PROS leg
        phase           = 'NONE'
        signal_strength = 'none'

    # CONT quality: CONFIRMED = fully confirmed continuation (STRONG)
    if 'CONFIRMED' in pros_cont_up or 'STRONG' in pros_cont_up:
        cont_quality = 'STRONG'
    elif 'BUILDING' in pros_cont_up:
        cont_quality = 'BUILDING'
    elif 'WEAK' in pros_cont_up:
        cont_quality = 'WEAK'
    elif pros_cont_up and pros_cont_up not in ('WAIT', '—', '-'):
        cont_quality = 'MODERATE'
    else:
        cont_quality = 'UNKNOWN'

    # ACCEPTED_CONTINUATION: Pine's CONT=CONFIRMED signals that buyers have accepted
    # the continuation regime — stair-step defense, persistent bid at OTE.
    # The single-fire prosContinuationBull may have already consumed its reference,
    # leaving the engine in BUILDING/ACTIVE. That reference consumption is not a
    # failure; it means the sequence completed and price is now in accepted regime.
    # Promote to ACCEPTED_CONTINUATION so Claude can grade it — all risk gates intact.
    if cont_quality == 'STRONG' and phase in ('BUILDING', 'OTE_APPROACHING', 'OTE_TAGGED'):
        phase           = 'ACCEPTED_CONTINUATION'
        signal_strength = 'high'

    has_signal = phase in (
        'SETUP_READY', 'OTE_TAGGED', 'OTE_APPROACHING',
        'BUILDING', 'ACCEPTED_CONTINUATION',
    )

    return {
        'phase':           phase,
        'direction':       direction,
        'setup_type':      f'PROS_{direction}' if direction != 'N/A' else 'N/A',
        'ote_status':      pros_ote_up or 'UNKNOWN',
        'cont_quality':    cont_quality,
        'has_signal':      has_signal,
        'signal_strength': signal_strength,
    }


def _evaluate_orb_phase(main_state: dict, chart_ctx: dict, session_ctx: dict) -> dict:
    """
    Detect ORB setup phase from chart context and NOVA levels.
    ORB is defined at 09:30–09:32 ET; context is valid through 11:00 ET.
    """
    labels = chart_ctx.get('nova_labels', [])
    levels = chart_ctx.get('nova_levels', [])
    price  = chart_ctx.get('price')

    orb_high = _extract_level(labels, levels, 'ORB HIGH') or _extract_level(labels, levels, 'ORB_HIGH')
    orb_low  = _extract_level(labels, levels, 'ORB LOW')  or _extract_level(labels, levels, 'ORB_LOW')
    orb_mid  = _extract_level(labels, levels, 'ORB MID')  or _extract_level(labels, levels, 'ORB_MID')

    if not orb_high or not orb_low:
        return {
            'phase':      'UNDEFINED',
            'has_signal': False,
            'orb_high':   None,
            'orb_low':    None,
            'orb_mid':    None,
            'orb_range':  None,
            'in_context': session_ctx['in_window'],
        }

    orb_range = orb_high - orb_low
    if not orb_mid:
        orb_mid = (orb_high + orb_low) / 2

    phase     = 'INSIDE_ORB'
    direction = 'N/A'
    has_signal = False

    if price is not None:
        try:
            p = float(price)
            orb_tolerance = orb_range * 0.15  # 15% of range = "near boundary"

            if p > orb_high:
                direction = 'LONG'
                if p <= orb_high + orb_tolerance:
                    # Just broke out — E1 setup may be forming as price extends
                    phase      = 'BREAKOUT_LONG'
                    has_signal = True
                else:
                    phase = 'ABOVE_ORB'
            elif p < orb_low:
                direction = 'SHORT'
                if p >= orb_low - orb_tolerance:
                    phase      = 'BREAKOUT_SHORT'
                    has_signal = True
                else:
                    phase = 'BELOW_ORB'
            elif abs(p - orb_mid) <= orb_range * 0.10:
                # Price at midpoint — E1 rejection setup area
                phase      = 'AT_MIDPOINT'
                has_signal = True
        except (TypeError, ValueError):
            pass

    # Determine E1 vs E2 setup type
    setup_type = 'N/A'
    if has_signal and direction != 'N/A':
        if phase in ('BREAKOUT_LONG', 'BREAKOUT_SHORT'):
            setup_type = f'ORB_E2_{direction}'   # Breakout → external liquidity rejection
        elif phase == 'AT_MIDPOINT':
            setup_type = 'ORB_E1_UNKNOWN'         # Direction depends on which side broke

    return {
        'phase':      phase,
        'direction':  direction,
        'setup_type': setup_type,
        'has_signal': has_signal,
        'orb_high':   orb_high,
        'orb_low':    orb_low,
        'orb_mid':    orb_mid,
        'orb_range':  orb_range,
        'orb_wide':   orb_range > 15,    # MES: >15pts reduces reliability
        'in_context': session_ctx['in_window'],
    }


def _evaluate_ib_alignment(main_state: dict, chart_ctx: dict, pros_state: dict | None = None) -> dict:
    """
    Assess IB draw alignment.
    IB levels come from PROS table rows IB H / IB L (preferred — added in Pine v1.x+) or
    fall back to NOVA labels/lines. CMD gives the directional bias.
    """
    labels = chart_ctx.get('nova_labels', [])
    levels = chart_ctx.get('nova_levels', [])
    price  = chart_ctx.get('price')

    # Prefer table-exported values — reliable bridge, no label parsing risk
    ib_high: float | None = None
    ib_low:  float | None = None
    if pros_state:
        try:
            ib_high = float(pros_state.get('IB H', '') or '')
        except (ValueError, TypeError):
            pass
        try:
            ib_low = float(pros_state.get('IB L', '') or '')
        except (ValueError, TypeError):
            pass

    # Fall back to label extraction for older Pine builds
    if not ib_high:
        ib_high = _extract_level(labels, levels, 'IB HIGH') or _extract_level(labels, levels, 'IB_HIGH')
    if not ib_low:
        ib_low  = _extract_level(labels, levels, 'IB LOW')  or _extract_level(labels, levels, 'IB_LOW')

    cmd_up = main_state.get('CMD', '').upper()

    if not ib_high or not ib_low:
        return {'draw': 'UNCLEAR', 'ib_high': None, 'ib_low': None, 'aligned': None,
                'ib_range': None}

    ib_range = ib_high - ib_low

    # Infer draw from CMD — substring match handles "WATCH LONG", "WATCH SHORT" etc.
    draw = 'UNCLEAR'
    if 'BUY' in cmd_up or 'LONG' in cmd_up or 'BULL' in cmd_up:
        draw = 'IB HIGH'
    elif 'SELL' in cmd_up or 'SHORT' in cmd_up or 'BEAR' in cmd_up:
        draw = 'IB LOW'

    # Verify price is positioned to reach the draw
    aligned = None
    if price and draw != 'UNCLEAR':
        try:
            p = float(price)
            if draw == 'IB HIGH':
                aligned = p < ib_high          # Price can still travel to IB HIGH
            elif draw == 'IB LOW':
                aligned = p > ib_low           # Price can still travel to IB LOW
        except (TypeError, ValueError):
            pass

    return {
        'draw':     draw,
        'ib_high':  ib_high,
        'ib_low':   ib_low,
        'ib_range': ib_range,
        'aligned':  aligned,
        'ib_tight': ib_range is not None and ib_range < 5,  # Very small range = less reliable
    }


def _check_invalidation_signals(main_state: dict, pros_state: dict, chart_ctx: dict) -> dict:
    """
    Detect explicit invalidation signals from NOVA indicator state.
    Returns whether an active setup has been broken.
    """
    state_up = main_state.get('STATE', '').upper()
    cmd_up   = main_state.get('CMD', '').upper()

    invalidated = False
    reason      = ''

    # NOVA indicator may emit explicit invalidation labels
    for keyword in ('INVALID', 'BROKEN', 'FAILED', 'VIOLATED'):
        if keyword in state_up:
            invalidated = True
            reason = f'Setup {keyword.lower()} per NOVA indicator'
            break

    return {
        'invalidated': invalidated,
        'reason':      reason,
        'setup_type':  'N/A',
    }


def _classify_signal(
    pros_eval:       dict,
    orb_eval:        dict,
    ib_eval:         dict,
    inv_eval:        dict,
    session_ctx:     dict,
    price_ote_eval:  dict | None = None,
) -> tuple[Optional[str], str, str]:
    """
    Classify signal type from deterministic evaluations.
    Returns (alert_type, setup_type, rationale).
    Claude will confirm, grade, and enrich — this is the pre-filter only.
    """
    session_name    = session_ctx.get('session', 'UNKNOWN')
    session_quality = session_ctx.get('session_quality', 'dead')

    # Invalidation takes priority over everything
    if inv_eval['invalidated']:
        return INVALIDATION, inv_eval.get('setup_type', 'N/A'), inv_eval['reason']

    # Dead zones — no analysis regardless of chart conditions
    if session_ctx.get('is_dead_zone'):
        return None, 'N/A', f'Dead zone ({session_name}) — no analysis'

    # Account-level blocks
    if session_ctx['session_blocked']:
        if session_ctx['daily_loss_hit']:
            return NO_TRADE, 'N/A', 'Daily loss limit hit'
        return None, 'N/A', 'Session blocked (trades/loss threshold)'

    # PROS signals — valid in all active sessions (ASIA, LONDON, NY_OPEN, NY_AM, NY_PM)
    if pros_eval['has_signal']:
        direction = pros_eval['direction']
        phase     = pros_eval['phase']
        setup     = pros_eval['setup_type']
        ib_draw   = ib_eval.get('draw', 'UNCLEAR')
        ib_tight  = ib_eval.get('ib_tight', False)

        ib_note = ''
        if ib_draw != 'UNCLEAR' and ib_eval.get('aligned') is False:
            ib_note = f'countertrend vs {ib_draw}'
        elif ib_tight:
            ib_note = 'IB range tight — draw less reliable'

        base_rationale = (
            f'PROS {direction} | phase={phase} | OTE={pros_eval["ote_status"]}'
            f' | session={session_name}({session_quality})'
        )
        if ib_note:
            base_rationale += f' | IB: {ib_note}'

        if phase == 'SETUP_READY':
            return EXECUTION_READY, setup, base_rationale
        elif phase == 'OTE_TAGGED':
            return EXECUTION_READY, setup, base_rationale + ' | OTE tagged'
        elif phase == 'ACCEPTED_CONTINUATION':
            return EXECUTION_READY, setup, base_rationale + ' | accepted continuation regime — CONT confirmed'
        elif phase == 'OTE_APPROACHING':
            return HEADS_UP, setup, base_rationale + ' | OTE approaching'
        elif phase == 'BUILDING':
            return HEADS_UP, setup, base_rationale + ' | displacement building'

    # Price structure OTE — fires when indicator hasn't triggered but market state is valid.
    # This is the state-based layer: Pine events contribute context but do not define reality.
    if price_ote_eval and price_ote_eval.get('has_ote') and not session_ctx.get('is_dead_zone'):
        direction = price_ote_eval['direction']
        fib_pct   = price_ote_eval.get('fib_pct', 0)
        clean     = price_ote_eval.get('clean_ote', False)
        ib_note   = 'IB aligned' if price_ote_eval.get('ib_aligned') else 'IB unclear'
        zone_desc = f'OTE {fib_pct:.1%} ({"clean 0.618-0.705" if clean else "outer 0.786"})'
        return (
            HEADS_UP,
            f'PROS_{direction}',
            f'{zone_desc} | {ib_note} | swing {price_ote_eval.get("swing_range","?")}pts'
            f' | session={session_name}({session_quality}) | source=price_structure',
        )

    # ORB signals — NY_OPEN only, before IB window closes (09:30-10:30 ET)
    orb_session_valid = session_name == 'NY_OPEN' and not session_ctx['ib_window_closed']
    if orb_eval.get('has_signal') and orb_eval.get('in_context') and orb_session_valid:
        phase     = orb_eval['phase']
        setup     = orb_eval['setup_type']
        orb_wide  = orb_eval.get('orb_wide', False)

        wide_note = ' | WIDE ORB — reliability reduced' if orb_wide else ''
        rationale = f'ORB {phase} | range={orb_eval.get("orb_range", "?"):.1f}pts{wide_note}'
        return HEADS_UP, setup, rationale

    return None, 'N/A', 'No qualifying signal detected'


# ── Strategy rules loader ──────────────────────────────────────────────────────

def _load_strategy_rules() -> str:
    """Load compact strategy rules for prompt injection."""
    for path in (_RULES_FILE, _RULES_ROOT):
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return json.dumps({
                    'pros_rules':          data.get('pros_rules', {}),
                    'orb_rules':           data.get('orb_rules', {}),
                    'no_trade_conditions': data.get('no_trade_conditions', []),
                    'tp_management':       data.get('tp_management', {}),
                    'risk_management':     data.get('risk_management', {}),
                    'session_context':     data.get('session_context', {}),
                }, indent=None, separators=(',', ':'))
            except Exception:
                pass
    return '{}'


# ── System prompt — full strategy knowledge ────────────────────────────────────

_SYSTEM_PROMPT = """You are NOVA, an AI trading intelligence system for MES/ES and MNQ/NQ futures.

## ROLE
You are the intelligence layer of an autonomous trading system. The indicator and deterministic engine have already identified the setup. Your job is to grade it and confirm execution — not to second-guess the signal.

The risk is already managed externally: 1% equity per trade, stop loss defined at OTE zone boundary, daily loss limit enforced, trade count capped at 5. You do not need to protect against losses by skipping trades. That is what stops are for.

## OPERATING PRINCIPLES
- Never alert when session_blocked=true (daily loss hit or trade limit reached).
- When the indicator shows a valid displacement leg + price at OTE: that is a trade. Grade it and execute.
- Your job is to assess QUALITY (how clean is the structure) — not to find reasons to skip.
- Silence is only correct when: no valid displacement leg exists, OR IB draw directly contradicts the direction with no structural justification, OR price has already closed beyond the displacement base.
- CONT=WAIT and QUALITY=WEAK mean the setup hasn't confirmed rejection yet — that is normal. Do not use these as reasons to skip a HEADS_UP.
- HEADS_UP = price is AT or approaching OTE. Alert so execution can be ready.
- EXECUTION_READY = OTE tagged with rejection confirmed. Execute immediately.

## SESSION QUALITY THRESHOLDS
HEADS_UP — alert whenever a valid leg is forming toward OTE:
- NY_OPEN (A): grade B or C → alert.
- NY_AM (B) / LONDON (B): grade B or C → alert.
- NY_PM (C) / ASIA (C): grade B → alert.

EXECUTION_READY — alert when rejection at OTE is confirmed:
- NY_OPEN (A) / NY_AM (B) / LONDON (B): grade A or B → alert.
- NY_PM (C) / ASIA (C): grade A only → alert.

- ORB is only valid during NY_OPEN session (09:30–10:30 ET). Never alert ORB outside that window.
- In ASIA / LONDON sessions: require clean displacement size before alerting.

## ALERT TYPES
HEADS_UP:        Setup forming — displacement in progress, OTE approaching, ORB reclaim developing,
                 continuation quality building, IB draw alignment strengthening.
EXECUTION_READY: Setup confirmed — OTE tagged with rejection, or ORB entry sequence complete.
INVALIDATION:    Active setup broken. Only when a setup was previously forming and is now invalid.
NO_TRADE:        Active block condition. Only fire once per session per condition (governance handles dedup).

## PROS RULES
Sequence: expansion → displacement → fib retracement (OTE) → rejection → continuation

OTE zone: 0.618–0.705 fib (primary). 0.786 valid as outer boundary. 0.5 = suboptimal, skip.
- LONG setup: expansion up → pullback to 0.618–0.705 → rejection → target IB HIGH / PDH / equal highs
- SHORT setup: expansion down → pullback to 0.618–0.705 → rejection → target IB LOW / PDL / equal lows
- Entry: rejection signal at OTE required (momentum shift, pin, engulf). Limit orders valid with clear bias.
- Stop: below/above OTE zone or displacement base. Normal: 30pts MES. High vol: 40pts.
- Target: IB high/low = TP1 (checkpoint, not mandatory exit). Hold to 3:1–4:1 if volume/momentum intact.

Grade criteria:
  A = clean displacement + OTE tap 0.618–0.705 + rejection confirmed + IB draw aligned + session timing correct. Execute.
  B = valid displacement + price at/near OTE + IB draw aligned or neutral. One element imprecise. Execute.
  C = setup present but two elements imprecise or IB draw unclear. Alert only — do not auto-execute.
  D = no valid displacement, price already past OTE, direct IB contradiction, or structure broken. Skip.

Grading rules:
- CONT=WAIT is NOT a downgrade. It means price hasn't rejected yet — normal for HEADS_UP.
- QUALITY=WEAK is NOT a downgrade on its own. It means no rejection yet — grade the displacement structure instead.
- IB draw UNCLEAR means direction cannot be confirmed from IB — treat as neutral, not negative. Do not downgrade to D for UNCLEAR.
- A clean displacement leg + price pulling to 0.618–0.705 = Grade B minimum, regardless of confirmation status.
- Grade D only when structure is genuinely broken — not when it's simply unconfirmed.

PROS invalidation (set alert_required=false or INVALIDATION if setup was active):
- Price closes beyond displacement base (expansion origin violated)
- Retracement exceeds 0.786 fib without clear structural justification
- Only 0.5 fib tapped, no OTE reached — suboptimal, likely break even or loss
- Multiple failed rejections at OTE
- Opposing expansion forms during retracement
- Structure shifts: price dumps from fib zone aggressively → bias flip, prior setup void

## ORB RULES
ORB defined: first 2 min of NY open (09:30–09:32) or first full 5m candle.
ORB HIGH / ORB LOW define the balance zone. ORB MID is the critical pivot.

Entry 1 (Midpoint Rejection):
  1. Price breaks out of ORB (above HIGH or below LOW)
  2. Price re-enters the ORB box
  3. Price taps ORB midpoint → rejection confirmed
  4. Entry: continuation in original breakout direction
  Stop: beyond midpoint rejection candle. Target: opposite ORB extreme then extension.

Entry 2 (External Liquidity Rejection):
  1. Price breaks out of ORB
  2. Price taps external liquidity (stops above/below prior session high/low)
  3. Rejection at external liquidity
  4. Entry: back toward ORB midpoint as TP1, then opposite extreme
  Stop: beyond external liquidity sweep candle.

ORB wide (>15pts MES) = reduced reliability → downgrade one tier.
ORB invalidation: full body close through midpoint from wrong side, or multiple violations in both directions.
ORB context expires after 11:00 ET.

## INITIAL BALANCE — REQUIRED CONTEXT LAYER
IB = high/low of first hour of session (09:30–10:30 NY AM).
IB is NOT an entry model. It is a REQUIRED context layer for every PROS setup.

Rules:
- Determine IB draw (IB HIGH = bullish draw, IB LOW = bearish draw) BEFORE grading any setup.
- PROS direction must align with IB draw → Grade A candidate.
- PROS direction opposes IB draw → countertrend → Grade C or avoid.
- IB level is TP1 (first target, not a hard exit).
- At TP1: if volume/momentum still strong → hold to 3:1–4:1 RR.
- IB range tight/choppy → draw less reliable → degrade session quality.

## SESSION QUALITY
Grade A: clean environment — all conditions favorable, IB draw defined, no macro risk
Grade B: one degradation condition (e.g., ORB wide, 1 prior trade, draw slightly unclear)
Grade C: two+ degradations — higher bar for entry, size down
Standby: 3+ degradations or hostile environment — observe only

Degradation factors: ORB >15pts, IB too tight/choppy, pre-market choppy, low volume at open,
spread >2pts, macro event same day, VIX elevated >20, NQ/ES diverging, PROS/ORB signals in conflict.

## NOVA INDICATOR TABLES
Main table: CMD / STATE / PROS / OTE / CONT / QUALITY / STDV / SESS
PROS table: DISPL / RETRACE / OTE / CONT / QUALITY / STDV

STATE interpretation:
  "BUILDING ▲/▼"  → displacement in progress → HEADS_UP candidate
  "SETUP READY"   → setup confirmed → EXECUTION_READY candidate
  "CHOP"          → no direction → no alert (or NO_TRADE if a block condition is active)
  "WAIT"          → unclear → silence

OTE interpretation:
  "TAGGED"     → price in OTE zone (0.618–0.705)
  "APPROACHING" → price nearing OTE → HEADS_UP
  "ABOVE/BELOW" → price outside OTE zone

CMD: BUY / SELL / WAIT

## OUTPUT — JSON ONLY
No markdown. No explanation outside the JSON object.
{
  "alert_required": true or false,
  "alert_type": "HEADS_UP" | "EXECUTION_READY" | "INVALIDATION" | "NO_TRADE" | null,
  "setup_type": "PROS_LONG" | "PROS_SHORT" | "ORB_E1_LONG" | "ORB_E1_SHORT" | "ORB_E2_LONG" | "ORB_E2_SHORT" | "N/A",
  "direction": "LONG" | "SHORT" | "N/A",
  "session_quality": "A" | "B" | "C" | "?",
  "ib_draw": "IB HIGH" | "IB LOW" | "UNCLEAR",
  "daily_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
  "htf_4h_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
  "grade": "A" | "B" | "C" | "D",
  "timeframe": "e.g. '30M PROS' or '1M ORB'",
  "time_to_close": "e.g. '3 min to close' or ''",
  "watch_time": "e.g. 'Watch for OTE confirmation at 10:00 AM ET' or ''",
  "entry_zone": "price range or ''",
  "stop": "price level or ''",
  "tp1": "price level or ''",
  "rr": "ratio or ''",
  "reason": "invalidation/no-trade reason or ''",
  "action": "action instruction or ''",
  "notes": "key context for the trader — specific, actionable",
  "no_alert_reason": "why no alert (when alert_required is false)"
}"""


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _build_evaluation_prompt(
    nova_state:  dict,
    session_ctx: dict,
    chart_ctx:   dict,
    pre_assess:  Optional[dict] = None,
) -> str:
    """Build the Claude user-turn prompt with live context and pre-assessment."""
    price  = chart_ctx.get('price', 'unknown')
    symbol = chart_ctx.get('symbol', 'UNKNOWN')
    ohlcv  = chart_ctx.get('ohlcv', {})
    levels = chart_ctx.get('nova_levels', [])[:10]
    labels = chart_ctx.get('nova_labels', [])

    # Load market reality for directional grounding
    try:
        from engines.market_reality import load_market_reality, format_reality_for_prompt
        _mr = load_market_reality()
        _mr_block = format_reality_for_prompt(_mr)
    except Exception:
        _mr_block = ''
        _mr = {}

    main_state = nova_state.get('main', {})
    pros_state = nova_state.get('pros', {})

    pre = pre_assess or {}
    pros_eval       = pre.get('pros_eval', {})
    orb_eval        = pre.get('orb_eval', {})
    ib_eval         = pre.get('ib_eval', {})
    inv_eval        = pre.get('inv_eval', {})
    price_ote_eval  = pre.get('price_ote_eval', {})

    orb_range_str = ''
    if orb_eval.get('orb_high') and orb_eval.get('orb_low'):
        orb_range_str = (
            f"HIGH={orb_eval['orb_high']:.2f} MID={orb_eval.get('orb_mid', '?'):.2f} "
            f"LOW={orb_eval['orb_low']:.2f} range={orb_eval.get('orb_range', '?'):.1f}pts"
        )

    ib_str = ''
    if ib_eval.get('ib_high') and ib_eval.get('ib_low'):
        ib_str = (
            f"HIGH={ib_eval['ib_high']:.2f} LOW={ib_eval['ib_low']:.2f} "
            f"range={ib_eval.get('ib_range', '?'):.1f}pts draw={ib_eval.get('draw', 'UNCLEAR')} "
            f"aligned={ib_eval.get('aligned', '?')}"
        )

    return f"""{_mr_block}

LIVE MARKET CONTEXT
Symbol:        {symbol}
Price:         {price}
Time:          {session_ctx['time_et']}  ({session_ctx['day']})
Session:       {session_ctx['session']} (quality={session_ctx.get('session_quality','?')})
IB locked:     {session_ctx['ib_window_closed']} (locks at 10:30 ET)
Blocked:       {session_ctx['session_blocked']}
Trades today:  {session_ctx['daily_trades']} / 2
Daily loss:    {session_ctx['daily_loss_hit']}

NOVA INDICATOR — MAIN ENGINE
{json.dumps(main_state, indent=None)}

NOVA INDICATOR — PROS ENGINE
{json.dumps(pros_state, indent=None)}

KEY PRICE LEVELS (NOVA)
{json.dumps(levels)}

SESSION LABELS
{json.dumps(labels)}

30-BAR OHLCV SUMMARY
Range: {ohlcv.get('range_30', '?')} pts | Change: {ohlcv.get('change_pct', '?')} | Avg vol: {ohlcv.get('avg_volume', '?')}
30-bar high: {ohlcv.get('high_30', '?')} | 30-bar low: {ohlcv.get('low_30', '?')}

DETERMINISTIC PRE-ASSESSMENT (indicator-driven)
PROS: phase={pros_eval.get('phase', 'N/A')} | direction={pros_eval.get('direction', 'N/A')} | OTE={pros_eval.get('ote_status', 'N/A')} | cont={pros_eval.get('cont_quality', '?')}
ORB:  phase={orb_eval.get('phase', 'N/A')} | {orb_range_str or 'levels not extracted'}
IB:   {ib_str or 'levels not extracted'}
INVALIDATION: {inv_eval.get('invalidated', False)} | {inv_eval.get('reason', '')}
Pre-signal: {pre.get('pre_signal', 'NONE')} | setup={pre.get('pre_setup', 'N/A')}
Rationale:  {pre.get('rationale', '')}

PRICE STRUCTURE (state-based — independent of Pine event triggers)
{f"Direction={price_ote_eval.get('direction')} | Fib={price_ote_eval.get('fib_pct',0):.1%} | Clean OTE={price_ote_eval.get('clean_ote')} | IB aligned={price_ote_eval.get('ib_aligned')} | Zone={price_ote_eval.get('ote_lo')}–{price_ote_eval.get('ote_hi')} | Swing={price_ote_eval.get('swing_low')}→{price_ote_eval.get('swing_high')} ({price_ote_eval.get('swing_range')}pts)" if price_ote_eval.get('has_ote') else f"Not in OTE zone — {price_ote_eval.get('reason', 'no data')}"}

{_market_memory.format_for_prompt(symbol) if _market_memory else ''}

{_dp_engine.format_for_prompt(pre.get('dir_pressure', {})) if _dp_engine else ''}

EVALUATION TASK
Architecture note: Pine indicator events CONTRIBUTE to intelligence — they do not define it.
If the indicator is WAIT/READING but PRICE STRUCTURE shows OTE, evaluate from market state directly.
A valid displacement + price at OTE is a trade regardless of whether Pine re-fired its trigger.

1. Use BOTH indicator state AND price structure to assess the setup
2. Grade A/B/C/D — if price structure shows clean OTE with IB aligned = Grade B minimum
3. Generate all alert fields for Discord delivery
4. For EXECUTION_READY: include entry_zone, stop, tp1, rr
5. For HEADS_UP: include watch_time and entry zone to watch
6. Infer daily_bias and htf_4h_bias from price action and market reality
7. Grade D = skip (structure broken). Grade C = HEADS_UP only. Grade A/B = execute.

Respond with JSON only — no markdown."""


# ── Claude evaluation ──────────────────────────────────────────────────────────

def evaluate_with_claude(
    nova_state:  dict,
    session_ctx: dict,
    chart_ctx:   dict,
    pre_assess:  Optional[dict] = None,
) -> Optional[dict]:
    """
    Call Claude to evaluate setup conditions and generate alert fields.
    Returns parsed decision dict or None on failure.
    """
    if not _anthropic_client:
        return None

    user_prompt = _build_evaluation_prompt(nova_state, session_ctx, chart_ctx, pre_assess)

    try:
        response = _anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=768,
            system=_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f'[nova-reasoning] Claude evaluation failed: {e}')
        return None


# ── Alert decision → AlertData ─────────────────────────────────────────────────

def decision_to_alert(decision: dict, symbol: str) -> Optional[AlertData]:
    """Convert Claude's decision dict to an AlertData object."""
    if not decision or not decision.get('alert_required'):
        return None
    if not AlertData:
        return None

    alert_type = decision.get('alert_type')
    if alert_type not in (HEADS_UP, EXECUTION_READY, INVALIDATION, NO_TRADE):
        return None

    return AlertData(
        alert_type      = alert_type,
        symbol          = symbol,
        setup_type      = decision.get('setup_type', 'UNKNOWN'),
        direction       = decision.get('direction', 'N/A'),
        priority        = 'high' if alert_type == EXECUTION_READY else 'standard',
        session         = decision.get('session', 'NY_OPEN') if 'session' in decision else 'NY_OPEN',
        session_quality = decision.get('session_quality', '?'),
        ib_draw         = decision.get('ib_draw', '?'),
        daily_bias      = decision.get('daily_bias', '?'),
        htf_4h_bias     = decision.get('htf_4h_bias', '?'),
        grade           = decision.get('grade', '?'),
        entry_zone      = decision.get('entry_zone', ''),
        stop            = decision.get('stop', ''),
        tp1             = decision.get('tp1', ''),
        rr              = decision.get('rr', ''),
        timeframe       = decision.get('timeframe', ''),
        time_to_close   = decision.get('time_to_close', ''),
        watch_time      = decision.get('watch_time', ''),
        reason          = decision.get('reason', ''),
        action          = decision.get('action', ''),
        notes           = decision.get('notes', ''),
    )


# ── Per-chart evaluation ───────────────────────────────────────────────────────

def _evaluate_single_chart(chart_ctx: dict, session_ctx: dict) -> list:
    """
    Run the full evaluation pipeline for one chart context.
    Returns list of AlertData (0 or 1 items).
    """
    symbol = chart_ctx.get('symbol', 'ES').replace('CME_MINI:', '').replace('1!', '')

    raw_tables = chart_ctx.get('nova_tables', [])
    nova_state = parse_nova_tables(raw_tables)
    main_state = nova_state.get('main', {})
    pros_state_data = nova_state.get('pros', {})

    pros_eval       = _evaluate_pros_phase(main_state, pros_state_data, chart_ctx)
    orb_eval        = _evaluate_orb_phase(main_state, chart_ctx, session_ctx)
    ib_eval         = _evaluate_ib_alignment(main_state, chart_ctx, pros_state_data)
    inv_eval        = _check_invalidation_signals(main_state, pros_state_data, chart_ctx)
    price_ote_eval  = _evaluate_price_structure(chart_ctx, ib_eval, pros_eval, main_state)

    mem_summary = {}
    if _market_memory:
        try:
            _market_memory.update(symbol, session_ctx, price_ote_eval, pros_eval, chart_ctx)
            mem_summary = _market_memory.get_summary(symbol)
        except Exception:
            pass

    dir_pressure = {}
    if _dp_engine:
        try:
            dir_pressure = _dp_engine.compute(pros_eval, ib_eval, session_ctx, mem_summary)
        except Exception:
            pass

    signal_type, setup_type, rationale = _classify_signal(
        pros_eval, orb_eval, ib_eval, inv_eval, session_ctx, price_ote_eval
    )

    if signal_type is None:
        print(f'[nova-reasoning] {session_ctx["time_et"]} | {symbol} | no signal | {rationale}')
        return []

    if signal_type == NO_TRADE and session_ctx.get('daily_loss_hit') and AlertData:
        return [AlertData(
            alert_type  = NO_TRADE,
            symbol      = symbol,
            setup_type  = 'N/A',
            direction   = 'N/A',
            priority    = 'high',
            session     = session_ctx['session'],
            reason      = 'Daily loss limit reached (2%)',
            action      = 'Session closed. No further entries.',
        )]

    pre_assess = {
        'pros_eval':      pros_eval,
        'orb_eval':       orb_eval,
        'ib_eval':        ib_eval,
        'inv_eval':       inv_eval,
        'price_ote_eval': price_ote_eval,
        'dir_pressure':   dir_pressure,
        'pre_signal':     signal_type,
        'pre_setup':      setup_type,
        'rationale':      rationale,
    }
    decision = evaluate_with_claude(nova_state, session_ctx, chart_ctx, pre_assess)
    if not decision:
        return []

    if _log_snapshot:
        try:
            _log_snapshot(
                symbol          = symbol,
                session_ctx     = session_ctx,
                chart_ctx       = chart_ctx,
                pine_state      = {'main': main_state, 'pros': pros_state_data},
                pros_eval       = pros_eval,
                ib_eval         = ib_eval,
                price_ote_eval  = price_ote_eval,
                dir_pressure    = dir_pressure,
                mem_summary     = mem_summary,
                pre_signal      = signal_type,
                claude_decision = decision,
            )
        except Exception:
            pass

    alert_required = decision.get('alert_required', False)
    log_reason = decision.get('no_alert_reason', '') if not alert_required else decision.get('alert_type', '')
    print(
        f'[nova-reasoning] {session_ctx["time_et"]} | {symbol} | '
        f'pre={signal_type} | alert={alert_required} | grade={decision.get("grade", "?")} | {log_reason}'
    )

    # ── Operational intelligence log — capture every evaluated signal ──────────
    try:
        from delivery.signal_log import log_cycle
        from core.state import load_risk_state

        # Screenshot only when Claude graded a real signal
        _screenshot = ''
        if alert_required or signal_type in ('EXECUTION_READY', 'HEADS_UP'):
            try:
                from delivery.alert_engine import capture_screenshot
                _ss = capture_screenshot()
                _screenshot = str(_ss) if _ss else ''
            except Exception:
                pass

        # Macro context from risk state
        try:
            _risk = load_risk_state()
            _snap = _risk.get('market_snapshot', {})
            _vix  = float((_snap.get('VIX') or {}).get('last') or 0) or None
            _nq_p = float((_snap.get('NQ')  or {}).get('pct')  or 0) or None
            _es_p = float((_snap.get('ES')  or {}).get('pct')  or 0) or None
            _macro_risk = _risk.get('macro_risk', '')
            _regime     = _risk.get('market_regime', '')
        except Exception:
            _vix = _nq_p = _es_p = None
            _macro_risk = _regime = ''

        ohlcv      = chart_ctx.get('ohlcv', {})
        orb_parsed = nova_state.get('orb', {})

        log_cycle(
            # Instrument
            symbol       = symbol,
            price        = chart_ctx.get('price'),
            high_30      = ohlcv.get('high_30'),
            low_30       = ohlcv.get('low_30'),
            range_30     = ohlcv.get('range_30'),
            change_pct   = str(ohlcv.get('change_pct', '')),
            levels       = chart_ctx.get('nova_levels', []),

            # Session
            session         = session_ctx.get('session', ''),
            session_quality = session_ctx.get('session_quality', ''),

            # NOVA indicator
            nova_cmd      = main_state.get('CMD', ''),
            nova_state_val= main_state.get('STATE', ''),
            nova_score    = main_state.get('SCORE', ''),
            nova_conf     = main_state.get('CONF', ''),

            # PROS
            pros_phase    = pros_eval.get('phase', ''),
            pros_direction= pros_eval.get('direction', ''),
            pros_signal   = bool(pros_eval.get('has_signal')),
            pros_strength = pros_eval.get('signal_strength', ''),
            pros_ote      = pros_eval.get('ote_status', ''),
            pros_displ    = pros_state_data.get('DISPL', ''),
            pros_retrace  = pros_state_data.get('RETRACE', ''),
            pros_cont     = pros_state_data.get('CONT', ''),
            pros_quality  = pros_state_data.get('QUALITY', ''),
            pros_stdv     = pros_state_data.get('STDV', ''),

            # ORB
            orb_state  = orb_parsed.get('STATE', ''),
            orb_bias   = orb_parsed.get('BIAS', ''),
            orb_high   = _safe_float(orb_parsed.get('HIGH')),
            orb_mid    = _safe_float(orb_parsed.get('MID')),
            orb_low    = _safe_float(orb_parsed.get('LOW')),
            orb_signal = bool(orb_eval.get('has_signal')),
            orb_phase  = orb_eval.get('phase', ''),
            orb_range  = orb_eval.get('orb_range'),

            # IB
            ib_high    = ib_eval.get('ib_high'),
            ib_low     = ib_eval.get('ib_low'),
            ib_draw    = ib_eval.get('draw', ''),
            ib_aligned = ib_eval.get('aligned'),
            ib_tight   = bool(ib_eval.get('ib_tight')),

            # Invalidation
            invalidated = bool(inv_eval.get('invalidated')),
            inv_reason  = inv_eval.get('reason', ''),

            # Pre-classification
            pre_signal   = signal_type or '',
            pre_setup    = setup_type or '',
            pre_rationale= rationale or '',

            # Claude decision
            claude_called  = True,
            alert_required = bool(alert_required),
            alert_type     = decision.get('alert_type', '') or '',
            grade          = decision.get('grade', '') or '',
            setup_type     = decision.get('setup_type', '') or '',
            direction      = decision.get('direction', '') or '',
            entry_zone     = decision.get('entry_zone', '') or '',
            stop           = decision.get('stop', '') or '',
            tp1            = decision.get('tp1', '') or '',
            rr             = decision.get('rr', '') or '',
            ib_draw_claude = decision.get('ib_draw', '') or '',
            daily_bias     = decision.get('daily_bias', '') or '',
            htf_4h_bias    = decision.get('htf_4h_bias', '') or '',
            action         = decision.get('action', '') or '',
            notes          = decision.get('notes', '') or '',
            no_alert_reason= decision.get('no_alert_reason', '') or '',

            # Macro
            macro_risk = _macro_risk,
            vix        = _vix,
            regime     = _regime,
            nq_pct     = _nq_p,
            es_pct     = _es_p,

            # Screenshot
            screenshot = _screenshot,
        )
    except Exception as _sle:
        print(f'[signal_log] log error: {_sle}')

    alert = decision_to_alert(decision, symbol)
    return [alert] if alert else []


def _safe_float(val) -> Optional[float]:
    """Parse a float from a string or number, return None on failure."""
    try:
        return float(val) if val not in (None, '', '—') else None
    except (TypeError, ValueError):
        return None


# ── Top-level reasoning cycle ──────────────────────────────────────────────────

def run_reasoning_cycle() -> list:
    """
    Full reasoning cycle. Called by the setup monitor every 60 seconds.

    Reads every open TradingView tab (primary first, secondaries via tab switch).
    Runs the full PROS/ORB/IB/Claude pipeline for each chart independently.
    Returns all alerts across all symbols — MES, NQ, MNQ, whatever is open.
    """
    session_ctx = evaluate_session_context()

    all_contexts = _collect_all_contexts()
    if not all_contexts:
        return []

    all_alerts: list = []
    for chart_ctx in all_contexts:
        alerts = _evaluate_single_chart(chart_ctx, session_ctx)
        all_alerts.extend(alerts)

    return all_alerts


# ── Manual trigger (on-demand analysis + debugging) ───────────────────────────

def analyze_now(verbose: bool = False) -> dict:
    """
    Run a single full reasoning cycle and return the complete result.
    Use for on-demand chart analysis, debugging, and pre-session checks.
    """
    chart_ctx   = read_chart_context()
    session_ctx = evaluate_session_context()

    if not chart_ctx.get('connected'):
        return {'error': 'TradingView not connected', 'connected': False}

    raw_tables     = chart_ctx.get('nova_tables', [])
    nova_state     = parse_nova_tables(raw_tables)
    main_state     = nova_state.get('main', {})
    pros_state_data = nova_state.get('pros', {})

    # Run all deterministic evaluators
    pros_eval      = _evaluate_pros_phase(main_state, pros_state_data, chart_ctx)
    orb_eval       = _evaluate_orb_phase(main_state, chart_ctx, session_ctx)
    ib_eval        = _evaluate_ib_alignment(main_state, chart_ctx, pros_state_data)
    inv_eval       = _check_invalidation_signals(main_state, pros_state_data, chart_ctx)
    price_ote_eval = _evaluate_price_structure(chart_ctx, ib_eval, pros_eval, main_state)

    mem_summary = {}
    if _market_memory:
        try:
            _market_memory.update(symbol, session_ctx, price_ote_eval, pros_eval, chart_ctx)
            mem_summary = _market_memory.get_summary(symbol)
        except Exception:
            pass

    dir_pressure = {}
    if _dp_engine:
        try:
            dir_pressure = _dp_engine.compute(pros_eval, ib_eval, session_ctx, mem_summary)
        except Exception:
            pass

    signal_type, setup_type, rationale = _classify_signal(
        pros_eval, orb_eval, ib_eval, inv_eval, session_ctx, price_ote_eval
    )

    pre_assess = {
        'pros_eval':      pros_eval,
        'orb_eval':       orb_eval,
        'ib_eval':        ib_eval,
        'inv_eval':       inv_eval,
        'price_ote_eval': price_ote_eval,
        'dir_pressure':   dir_pressure,
        'pre_signal':     signal_type,
        'pre_setup':      setup_type,
        'rationale':      rationale,
    }

    decision = evaluate_with_claude(nova_state, session_ctx, chart_ctx, pre_assess) or {}

    if _log_snapshot:
        try:
            _log_snapshot(
                symbol          = symbol,
                session_ctx     = session_ctx,
                chart_ctx       = chart_ctx,
                pine_state      = {'main': main_state, 'pros': pros_state_data},
                pros_eval       = pros_eval,
                ib_eval         = ib_eval,
                price_ote_eval  = price_ote_eval,
                dir_pressure    = dir_pressure,
                mem_summary     = mem_summary,
                pre_signal      = signal_type,
                claude_decision = decision,
            )
        except Exception:
            pass

    result = {
        'connected':      True,
        'symbol':         chart_ctx.get('symbol'),
        'price':          chart_ctx.get('price'),
        'time_et':        session_ctx['time_et'],
        'in_window':      session_ctx['in_window'],
        'session':        session_ctx['session'],
        'nova_main':      nova_state.get('main', {}),
        'nova_pros':      nova_state.get('pros', {}),
        'pre_signal':     signal_type,
        'pre_setup':      setup_type,
        'pre_rationale':  rationale,
        'pros_eval':      pros_eval,
        'orb_eval':       orb_eval,
        'ib_eval':        ib_eval,
        'decision':       decision,
        'alert_required': decision.get('alert_required', False),
    }

    if verbose:
        result['chart_ctx']   = chart_ctx
        result['session_ctx'] = session_ctx

    return result
