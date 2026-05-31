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

_BASE_DIR   = Path(__file__).parent
_MCP_DIR    = _BASE_DIR / 'mcp' / 'tradingview'
_RULES_FILE = _BASE_DIR / 'NOVA_KNOWLEDGE_CORE' / 'RULES' / 'nova_strategy_core.json'
_RULES_ROOT = _BASE_DIR / 'nova_strategy_core.json'

# ── Config imports ─────────────────────────────────────────────────────────────

try:
    from donna_config import client as _anthropic_client, ANTHROPIC_MODEL, now_ny
    from donna_state_engine import DonnaStateEngine as _DSE
    _state_engine = _DSE()
except Exception:
    _anthropic_client = None
    ANTHROPIC_MODEL   = 'claude-haiku-4-5-20251001'
    _state_engine     = None
    def now_ny():
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('America/New_York'))

try:
    from donna_alert_engine import AlertData, HEADS_UP, EXECUTION_READY, INVALIDATION, NO_TRADE
except Exception:
    AlertData       = None
    HEADS_UP        = 'HEADS_UP'
    EXECUTION_READY = 'EXECUTION_READY'
    INVALIDATION    = 'INVALIDATION'
    NO_TRADE        = 'NO_TRADE'

# ── MCP data collection ────────────────────────────────────────────────────────

def _run_mcp(*args: str) -> Optional[dict]:
    """Run a TradingView MCP CLI command. Returns parsed JSON or None."""
    try:
        result = subprocess.run(
            ['node', 'src/cli/index.js', *args],
            cwd=str(_MCP_DIR),
            capture_output=True,
            text=True,
            timeout=10,
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
    Collect all chart data from TradingView MCP.
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


# ── NOVA table parsing ─────────────────────────────────────────────────────────

def parse_nova_tables(raw_tables: list[list[str]]) -> dict:
    """
    Parse NOVA indicator table rows into structured dicts.

    Table 1 (main engine):  CMD, SCORE, STATE, PROS, OTE, CONT, QUALITY, STDV, SESS
    Table 2 (PROS engine):  DISPL, RETRACE, OTE, CONT, QUALITY, STDV, SESS
    """
    parsed = {}

    def _parse_rows(rows: list[str]) -> dict:
        result = {}
        for row in rows:
            if ' | ' in row:
                key, _, val = row.partition(' | ')
                result[key.strip()] = val.strip()
        return result

    if len(raw_tables) >= 1:
        parsed['main'] = _parse_rows(raw_tables[0])
    if len(raw_tables) >= 2:
        parsed['pros'] = _parse_rows(raw_tables[1])

    return parsed


# ── Session context evaluator (fast, deterministic) ────────────────────────────

def evaluate_session_context() -> dict:
    """
    Evaluate current session state without calling Claude.
    Returns facts used as hard constraints throughout the pipeline.
    """
    now  = now_ny()
    mins = now.hour * 60 + now.minute

    ctx = {
        'time_et':          now.strftime('%H:%M ET'),
        'day':              now.strftime('%A'),
        'in_window':        9 * 60 + 30 <= mins <= 11 * 60,
        'window_open':      mins < 9 * 60 + 30,
        'window_closed':    mins > 11 * 60,
        'ib_window_closed': mins >= 10 * 60 + 30,
        'session':          'NY_OPEN' if 9 * 60 + 30 <= mins <= 11 * 60 else
                            'PRE_MARKET' if mins < 9 * 60 + 30 else 'OFF_HOURS',
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

    ctx['session_blocked'] = (
        not ctx['in_window'] or
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

    # Direction: CMD is authoritative; DISPL is the secondary signal
    direction = 'N/A'
    if cmd_up in ('BUY', 'LONG') or 'BULL' in displ_up:
        direction = 'LONG'
    elif cmd_up in ('SELL', 'SHORT') or 'BEAR' in displ_up:
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
        elif pros_retrace in ('OTE', 'DEEP'):
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
        elif pros_retrace in ('OTE', 'DEEP'):
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

    has_signal = phase in ('SETUP_READY', 'OTE_TAGGED', 'OTE_APPROACHING', 'BUILDING')

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


def _evaluate_ib_alignment(main_state: dict, chart_ctx: dict) -> dict:
    """
    Assess IB draw alignment.
    IB levels come from NOVA labels/lines. CMD gives the directional bias.
    """
    labels = chart_ctx.get('nova_labels', [])
    levels = chart_ctx.get('nova_levels', [])
    price  = chart_ctx.get('price')

    ib_high = _extract_level(labels, levels, 'IB HIGH') or _extract_level(labels, levels, 'IB_HIGH')
    ib_low  = _extract_level(labels, levels, 'IB LOW')  or _extract_level(labels, levels, 'IB_LOW')

    cmd_up = main_state.get('CMD', '').upper()

    if not ib_high or not ib_low:
        return {'draw': 'UNCLEAR', 'ib_high': None, 'ib_low': None, 'aligned': None,
                'ib_range': None}

    ib_range = ib_high - ib_low

    # Infer draw from CMD
    draw = 'UNCLEAR'
    if cmd_up in ('BUY', 'LONG') or 'BULL' in cmd_up:
        draw = 'IB HIGH'
    elif cmd_up in ('SELL', 'SHORT') or 'BEAR' in cmd_up:
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
    pros_eval:   dict,
    orb_eval:    dict,
    ib_eval:     dict,
    inv_eval:    dict,
    session_ctx: dict,
) -> tuple[Optional[str], str, str]:
    """
    Classify signal type from deterministic evaluations.
    Returns (alert_type, setup_type, rationale).
    Claude will confirm, grade, and enrich — this is the pre-filter only.
    """
    # Invalidation takes priority over everything
    if inv_eval['invalidated']:
        return INVALIDATION, inv_eval.get('setup_type', 'N/A'), inv_eval['reason']

    # Session hard blocks
    if not session_ctx['in_window']:
        return None, 'N/A', 'Outside trading window'

    if session_ctx['session_blocked']:
        if session_ctx['daily_loss_hit']:
            return NO_TRADE, 'N/A', 'Daily loss limit hit'
        return None, 'N/A', 'Session blocked (trades/loss threshold)'

    # PROS signals — priority over ORB
    if pros_eval['has_signal']:
        direction = pros_eval['direction']
        phase     = pros_eval['phase']
        setup     = pros_eval['setup_type']
        ib_draw   = ib_eval.get('draw', 'UNCLEAR')
        ib_tight  = ib_eval.get('ib_tight', False)

        # IB context note (Claude will judge alignment more precisely)
        ib_note = ''
        if ib_draw != 'UNCLEAR' and ib_eval.get('aligned') is False:
            ib_note = f'countertrend vs {ib_draw}'
        elif ib_tight:
            ib_note = 'IB range tight — draw less reliable'

        base_rationale = f'PROS {direction} | phase={phase} | OTE={pros_eval["ote_status"]}'
        if ib_note:
            base_rationale += f' | IB: {ib_note}'

        if phase == 'SETUP_READY':
            return EXECUTION_READY, setup, base_rationale
        elif phase == 'OTE_TAGGED':
            return EXECUTION_READY, setup, base_rationale + ' | OTE tagged'
        elif phase == 'OTE_APPROACHING':
            return HEADS_UP, setup, base_rationale + ' | OTE approaching'
        elif phase == 'BUILDING':
            return HEADS_UP, setup, base_rationale + ' | displacement building'

    # ORB signals
    if orb_eval.get('has_signal') and orb_eval.get('in_context'):
        phase     = orb_eval['phase']
        setup     = orb_eval['setup_type']
        direction = orb_eval['direction']
        orb_wide  = orb_eval.get('orb_wide', False)

        wide_note = ' | WIDE ORB — reliability reduced' if orb_wide else ''
        rationale = f'ORB {phase} | range={orb_eval.get("orb_range", "?"):.1f}pts{wide_note}'

        # ORB E1 (midpoint rejection) or E2 (external liquidity rejection) both start as HEADS_UP
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
Evaluate live market conditions from TradingView NOVA indicator data and generate Discord alerts.
A deterministic pre-assessment has already been run. Your job is to confirm or override it, grade the setup, and produce alert fields.

## OPERATING PRINCIPLES
- Quality over quantity. Silence is correct when there is no genuine edge.
- Never alert outside 09:30–11:00 ET. Never alert when session_blocked=true.
- A missed alert is better than a false positive. Be conservative.
- HEADS_UP = setup forming BEFORE confirmation. This is the system's key differentiator.
- EXECUTION_READY = setup confirmed and actionable RIGHT NOW.
- Grade C or D setups → no alert. Downgrade rather than silence if context is partly bullish.

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
  A = clean expansion + clear displacement + OTE tap 0.618–0.705 + strong rejection + IB alignment confirmed + session timing correct
  B = most criteria met; one element weak or unclear
  C = two or more elements weak, ambiguous, or countertrend IB draw
  D = do not trade (multiple failures, no clear structure)

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

    main_state = nova_state.get('main', {})
    pros_state = nova_state.get('pros', {})

    pre = pre_assess or {}
    pros_eval = pre.get('pros_eval', {})
    orb_eval  = pre.get('orb_eval', {})
    ib_eval   = pre.get('ib_eval', {})
    inv_eval  = pre.get('inv_eval', {})

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

    return f"""LIVE MARKET CONTEXT
Symbol:        {symbol}
Price:         {price}
Time:          {session_ctx['time_et']}  ({session_ctx['day']})
Session:       {session_ctx['session']}
In window:     {session_ctx['in_window']} (09:30–11:00 ET)
IB locked:     {session_ctx['ib_window_closed']} (locks at 10:30)
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

DETERMINISTIC PRE-ASSESSMENT
PROS: phase={pros_eval.get('phase', 'N/A')} | direction={pros_eval.get('direction', 'N/A')} | OTE={pros_eval.get('ote_status', 'N/A')} | cont={pros_eval.get('cont_quality', '?')}
ORB:  phase={orb_eval.get('phase', 'N/A')} | {orb_range_str or 'levels not extracted'}
IB:   {ib_str or 'levels not extracted'}
INVALIDATION: {inv_eval.get('invalidated', False)} | {inv_eval.get('reason', '')}
Pre-signal: {pre.get('pre_signal', 'NONE')} | setup={pre.get('pre_setup', 'N/A')}
Rationale:  {pre.get('rationale', '')}

EVALUATION TASK
The deterministic layer classified a potential {pre.get('pre_signal', 'NONE')} signal.
1. Confirm or override the signal type (alert_required=false if conditions don't warrant it)
2. Grade the setup A/B/C/D using full PROS + ORB + IB criteria from the system prompt
3. Generate all alert fields for Discord delivery
4. For EXECUTION_READY: include entry_zone, stop, tp1, rr
5. For HEADS_UP: include watch_time and timeframe context
6. Infer daily_bias and htf_4h_bias from available price action context
7. If grade is C or D → set alert_required=false with no_alert_reason

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


# ── Top-level reasoning cycle ──────────────────────────────────────────────────

def run_reasoning_cycle() -> list:
    """
    Full reasoning cycle. Called by the setup monitor every 60 seconds.

    1. Read live chart context from TradingView MCP
    2. Evaluate session state (fast, deterministic)
    3. Parse NOVA indicator tables
    4. Run deterministic evaluators — PROS, ORB, IB, invalidation
    5. Classify signal type (pre-filter, no API call)
    6. Skip Claude entirely if no signal or obvious block
    7. Call Claude with full context + pre-assessment
    8. Return list of AlertData to deliver
    """
    # Step 1: Chart
    chart_ctx = read_chart_context()
    if not chart_ctx.get('connected'):
        return []

    # Step 2: Session
    session_ctx = evaluate_session_context()

    # Step 3: Parse NOVA tables
    raw_tables = chart_ctx.get('nova_tables', [])
    nova_state = parse_nova_tables(raw_tables)
    main_state = nova_state.get('main', {})
    pros_state_data = nova_state.get('pros', {})

    # Step 4: Deterministic evaluators
    pros_eval = _evaluate_pros_phase(main_state, pros_state_data, chart_ctx)
    orb_eval  = _evaluate_orb_phase(main_state, chart_ctx, session_ctx)
    ib_eval   = _evaluate_ib_alignment(main_state, chart_ctx)
    inv_eval  = _check_invalidation_signals(main_state, pros_state_data, chart_ctx)

    # Step 5: Signal classification
    signal_type, setup_type, rationale = _classify_signal(
        pros_eval, orb_eval, ib_eval, inv_eval, session_ctx
    )

    # Step 6: Pre-filter
    if signal_type is None:
        print(f'[nova-reasoning] {session_ctx["time_et"]} | no signal | {rationale}')
        return []

    # Hard NO_TRADE — emit directly, no Claude needed
    if signal_type == NO_TRADE and session_ctx.get('daily_loss_hit') and AlertData:
        return [AlertData(
            alert_type  = NO_TRADE,
            symbol      = chart_ctx.get('symbol', 'ES').replace('CME_MINI:', '').replace('1!', ''),
            setup_type  = 'N/A',
            direction   = 'N/A',
            priority    = 'high',
            session     = session_ctx['session'],
            reason      = 'Daily loss limit reached (2%)',
            action      = 'Session closed. No further entries.',
        )]

    # Step 7: Claude evaluation
    pre_assess = {
        'pros_eval':  pros_eval,
        'orb_eval':   orb_eval,
        'ib_eval':    ib_eval,
        'inv_eval':   inv_eval,
        'pre_signal': signal_type,
        'pre_setup':  setup_type,
        'rationale':  rationale,
    }
    decision = evaluate_with_claude(nova_state, session_ctx, chart_ctx, pre_assess)
    if not decision:
        return []

    alert_required = decision.get('alert_required', False)
    log_reason = decision.get('no_alert_reason', '') if not alert_required else decision.get('alert_type', '')
    print(
        f'[nova-reasoning] {session_ctx["time_et"]} | '
        f'pre={signal_type} | alert={alert_required} | grade={decision.get("grade", "?")} | {log_reason}'
    )

    # Step 8: Build AlertData
    symbol = chart_ctx.get('symbol', 'ES').replace('CME_MINI:', '').replace('1!', '')
    alert  = decision_to_alert(decision, symbol)
    return [alert] if alert else []


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
    pros_eval = _evaluate_pros_phase(main_state, pros_state_data, chart_ctx)
    orb_eval  = _evaluate_orb_phase(main_state, chart_ctx, session_ctx)
    ib_eval   = _evaluate_ib_alignment(main_state, chart_ctx)
    inv_eval  = _check_invalidation_signals(main_state, pros_state_data, chart_ctx)

    signal_type, setup_type, rationale = _classify_signal(
        pros_eval, orb_eval, ib_eval, inv_eval, session_ctx
    )

    pre_assess = {
        'pros_eval':  pros_eval,
        'orb_eval':   orb_eval,
        'ib_eval':    ib_eval,
        'inv_eval':   inv_eval,
        'pre_signal': signal_type,
        'pre_setup':  setup_type,
        'rationale':  rationale,
    }

    decision = evaluate_with_claude(nova_state, session_ctx, chart_ctx, pre_assess) or {}

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
