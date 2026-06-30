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
    from engines.momentum import compute_momentum as _compute_momentum, format_for_prompt as _momentum_fmt
except Exception:
    _compute_momentum = None
    _momentum_fmt     = None

try:
    from services.execution_trace import log_reasoning_snapshot as _log_snapshot
except Exception:
    _log_snapshot = None

try:
    from engines.market_reality_v2 import load_market_reality_v2 as _load_mr2, format_for_prompt as _mr2_prompt
except Exception:
    _load_mr2    = None
    _mr2_prompt  = None

try:
    from engines.cross_market import load_cross_market as _load_cm, format_for_prompt as _cm_prompt
except Exception:
    _load_cm    = None
    _cm_prompt  = None

try:
    from engines.market_structure import load_market_structure as _load_ms, format_for_prompt as _ms_prompt
except Exception:
    _load_ms   = None
    _ms_prompt = None

try:
    from engines.participation import load_participation as _load_p, format_for_prompt as _p_prompt
except Exception:
    _load_p   = None
    _p_prompt = None

try:
    from engines.liquidity import load_liquidity as _load_liq, format_for_prompt as _liq_prompt
except Exception:
    _load_liq  = None
    _liq_prompt = None

try:
    from engines.synthesis import load_synthesis as _load_syn, format_for_prompt as _syn_prompt
except Exception:
    _load_syn  = None
    _syn_prompt = None

try:
    from engines.session_memory import load_session_memory as _load_mem, format_for_prompt as _mem_prompt
except Exception:
    _load_mem  = None
    _mem_prompt = None

# ── Feed sync — fire-and-forget push to Render ────────────────────────────────

import threading as _threading

def _push_execution_entry(execution_entry: dict) -> None:
    """
    Push one execution_trace entry (DECISION_CHAIN or BRIDGE_REJECTED) to Render.
    Runs in a daemon thread — never blocks the monitor cycle.
    """
    if not execution_entry:
        return
    def _do():
        try:
            import requests as _req
            from core.config import NOVA_RENDER_URL, NOVA_INGEST_SECRET
            if not NOVA_RENDER_URL or not NOVA_INGEST_SECRET:
                return
            _req.post(
                NOVA_RENDER_URL + '/api/feed/ingest',
                json    = {'execution': execution_entry},
                headers = {'X-Nova-Ingest-Secret': NOVA_INGEST_SECRET},
                timeout = 4,
            )
        except Exception:
            pass
    _threading.Thread(target=_do, daemon=True).start()


def _push_feed_entry(signal_entry: dict, reasoning_entry: dict) -> None:
    """
    Push one signal + reasoning entry to Render's /api/feed/ingest.
    Runs in a daemon thread — never blocks the monitor cycle.
    Silent on all failures (Render may be down, env vars unset, etc.).
    """
    if not signal_entry and not reasoning_entry:
        return
    def _do():
        try:
            import requests as _req
            from core.config import NOVA_RENDER_URL, NOVA_INGEST_SECRET
            if not NOVA_RENDER_URL or not NOVA_INGEST_SECRET:
                return
            payload: dict = {}
            if signal_entry:
                payload['signal'] = signal_entry
            if reasoning_entry:
                payload['reasoning'] = reasoning_entry
            _req.post(
                NOVA_RENDER_URL + '/api/feed/ingest',
                json    = payload,
                headers = {'X-Nova-Ingest-Secret': NOVA_INGEST_SECRET},
                timeout = 4,
            )
        except Exception:
            pass
    _threading.Thread(target=_do, daemon=True).start()


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


# ── NOVA table field specs ────────────────────────────────────────────────────
# Single source of truth for both parse_nova_tables() and compute_mcp_health().
_MCP_REQUIRED_V2: frozenset = frozenset({
    'TICKER', 'TF', 'IB_STATUS', 'SESSION',
    'ORB_ACTIVE', 'PROS_ACTIVE', 'COOLDOWN', 'TRAP',
    'ICT_STEP', 'PEER_ALIGN',
})
_MCP_OPTIONAL_V2: frozenset = frozenset({'DRAW_TARGET', 'DRAW_DIR'})

# ── NOVA table parsing ─────────────────────────────────────────────────────────

def parse_nova_tables(raw_tables: list[list[str]]) -> dict:
    """
    Parse NOVA indicator table rows into structured dicts.

    Priority 1: NOVA BRIDGE (permanent automation interface, single table).
      Identified by 'NOVA BRIDGE' header row. Maps prefixed keys to the
      same main/pros/orb sub-dicts that downstream evaluators expect.
      BRIDGE_VER >= 2: also extracts rows 21-33 into bridge_v2 + bridge_meta.
      Observation only — bridge_meta does not affect execution.

    Priority 2: Legacy three-table layout (backward-compat fallback).
      NOVA ENGINE → main, PROS ENGINE → pros, ORB CONSOLE → orb.
      Kept until all charts are confirmed on the new Pine Script.

    Phase B additions (all observability-only, no execution impact):
      parser_mode  — which parsing path was taken (BRIDGE_V2/BRIDGE_V1/LEGACY_TABLES/NO_BRIDGE/UNREADABLE)
      parse_status — parse outcome (ok/required_fields_missing/version_mismatch/legacy_fallback/bridge_missing/unreadable/parser_exception)
      bridge_meta  — extended with field completeness, version gate, required/optional splits
    """
    try:
        return _parse_nova_tables_impl(raw_tables)
    except Exception as exc:
        print(f'[parse_nova_tables] parser_exception: {exc}')
        return {
            'parser_mode':  'UNREADABLE',
            'parse_status': 'parser_exception',
            'main': {}, 'pros': {}, 'orb': {},
        }


def _parse_nova_tables_impl(raw_tables: list[list[str]]) -> dict:
    parsed: dict = {}

    def _parse_rows(rows: list[str]) -> dict:
        result = {}
        for row in rows:
            if ' | ' in row:
                key, _, val = row.partition(' | ')
                result[key.strip()] = val.strip()
        return result

    # ── Priority 1: NOVA BRIDGE ───────────────────────────────────────────────
    # Header row is a single cell with no ' | ', so it's never in the parsed
    # dict — check the raw rows list directly instead.
    for table_rows in raw_tables:
        if not table_rows:
            continue
        if table_rows[0].strip() != 'NOVA BRIDGE':
            continue
        d = _parse_rows(table_rows)

        parsed['main'] = {
            'CMD':   d.get('CMD',       ''),
            'STATE': d.get('SYS_STATE', ''),
            'SCORE': d.get('SCORE',     ''),
            'CONF':  d.get('CONF',      ''),
            'PROS':  d.get('PROS_ENG',  ''),
        }
        parsed['pros'] = {
            'PROS ENGINE': d.get('PROS_ENG',  ''),
            'DISPL':       d.get('P_DISPL',   ''),
            'RETRACE':     d.get('P_RETRACE', ''),
            'OTE':         d.get('P_OTE',     ''),
            'CONT':        d.get('P_CONT',    ''),
            'QUALITY':     d.get('P_QUALITY', ''),
            'STDV':        d.get('P_STDV',    ''),
            'IB H':        d.get('IB H',      ''),
            'IB L':        d.get('IB L',      ''),
        }
        parsed['orb'] = {
            'STATE': d.get('O_STATE',  ''),
            'BIAS':  d.get('O_BIAS',   ''),
            'TYPE':  d.get('O_TYPE',   ''),
            'REJ Q': d.get('O_REJ_Q',  ''),
            'HIGH':  d.get('O_HIGH',   ''),
            'MID':   d.get('O_MID',    ''),
            'LOW':   d.get('O_LOW',    ''),
        }

        # ── BRIDGE v2 extension fields (rows 21-33) ───────────────────────────
        # Observation/health only — nothing here gates execution.
        # If BRIDGE_VER is absent the chart is running v1; skip v2 extraction.
        _V2_KEYS = [
            'BRIDGE_VER', 'TICKER', 'TF', 'IB_STATUS', 'SESSION',
            'ORB_ACTIVE', 'PROS_ACTIVE', 'COOLDOWN', 'TRAP',
            'ICT_STEP', 'PEER_ALIGN', 'DRAW_TARGET', 'DRAW_DIR',
        ]

        def _vbool(val: str):
            v = val.strip()
            return True if v == '1' else (False if v == '0' else None)

        def _vint(val: str):
            v = val.strip()
            return int(v) if v.lstrip('-').isdigit() else None

        def _vfloat(val: str):
            v = val.strip()
            if v in ('', '—', 'na', 'NA'):
                return None
            try:
                return float(v)
            except ValueError:
                return None

        bridge_ver_raw = d.get('BRIDGE_VER', '').strip()
        bridge_ver     = int(bridge_ver_raw) if bridge_ver_raw.isdigit() else 1
        v2_detected    = bridge_ver >= 2

        present = [k for k in _V2_KEYS if d.get(k, '').strip() not in ('', '—')]
        missing = [k for k in _V2_KEYS if d.get(k, '').strip()     in ('', '—')]

        # Phase B: split by required vs optional for diagnostic granularity
        req_present = [k for k in _MCP_REQUIRED_V2 if d.get(k, '').strip() not in ('', '—')]
        req_missing  = [k for k in _MCP_REQUIRED_V2 if d.get(k, '').strip()     in ('', '—')]
        opt_present  = [k for k in _MCP_OPTIONAL_V2 if d.get(k, '').strip() not in ('', '—')]
        opt_missing  = [k for k in _MCP_OPTIONAL_V2 if d.get(k, '').strip()     in ('', '—')]

        bridge_v2 = {
            'bridge_ver':  bridge_ver,
            'ticker':      d.get('TICKER',     '').strip() or None,
            'timeframe':   d.get('TF',         '').strip() or None,
            'ib_status':   d.get('IB_STATUS',  '').strip() or None,
            'session':     d.get('SESSION',    '').strip() or None,
            'orb_active':  _vbool(d.get('ORB_ACTIVE',  '')),
            'pros_active': _vbool(d.get('PROS_ACTIVE', '')),
            'cooldown':    _vbool(d.get('COOLDOWN',    '')),
            'trap':        _vbool(d.get('TRAP',        '')),
            'ict_step':    _vint( d.get('ICT_STEP',    '')),
            'peer_align':  d.get('PEER_ALIGN', '').strip() or None,
            'draw_target': _vfloat(d.get('DRAW_TARGET', '')),
            'draw_dir':    d.get('DRAW_DIR',   '').strip() or None,
        }

        # Phase B: parser_mode / parse_status
        if v2_detected:
            parser_mode  = 'BRIDGE_V2'
            parse_status = 'ok' if not req_missing else 'required_fields_missing'
        else:
            parser_mode  = 'BRIDGE_V1'
            parse_status = 'version_mismatch'

        bridge_meta = {
            # ── existing keys (backward compat) ──────────────────────────────
            'bridge_version':        bridge_ver,
            'bridge_v2_detected':    v2_detected,
            'parsed_ticker':         bridge_v2['ticker'],
            'parsed_timeframe':      bridge_v2['timeframe'],
            'parsed_session':        bridge_v2['session'],
            'bridge_fields_present': len(present),
            'bridge_fields_missing': missing,
            # ── Phase B additions ─────────────────────────────────────────────
            'parser_mode':                  parser_mode,
            'parse_status':                 parse_status,
            'expected_bridge_version':      2,
            'required_fields_present':      req_present,
            'required_fields_missing':      req_missing,
            'optional_fields_present':      opt_present,
            'optional_fields_missing':      opt_missing,
            'total_bridge_fields_present':  len(present),
            'total_bridge_fields_expected': len(_V2_KEYS),
        }

        parsed['bridge_v2']    = bridge_v2
        parsed['bridge_meta']  = bridge_meta
        parsed['parser_mode']  = parser_mode
        parsed['parse_status'] = parse_status

        if v2_detected:
            _miss_str = ','.join(missing) if missing else 'none'
            print(
                f'[nova-bridge-v2]'
                f' ver={bridge_ver}'
                f' ticker={bridge_v2["ticker"]}'
                f' tf={bridge_v2["timeframe"]}'
                f' session={bridge_v2["session"]}'
                f' ib={bridge_v2["ib_status"]}'
                f' orb={bridge_v2["orb_active"]}'
                f' pros={bridge_v2["pros_active"]}'
                f' trap={bridge_v2["trap"]}'
                f' ict={bridge_v2["ict_step"]}'
                f' peer={bridge_v2["peer_align"]}'
                f' fields={len(present)}/{len(_V2_KEYS)}'
                f' missing={_miss_str}'
                f' status={parse_status}'
            )

        return parsed  # NOVA BRIDGE found — skip legacy detection

    # ── Priority 2: Legacy three-table fallback ───────────────────────────────
    legacy_found = False
    for table_rows in raw_tables:
        if not table_rows:
            continue
        header = table_rows[0].strip()
        d = _parse_rows(table_rows)
        if header == 'NOVA ENGINE':
            parsed['main'] = d
            legacy_found = True
        elif header == 'PROS ENGINE':
            parsed['pros'] = d
            legacy_found = True
        elif header == 'ORB CONSOLE':
            parsed['orb'] = d
            legacy_found = True

    # Index-based fallback if header detection found nothing
    if 'main' not in parsed and len(raw_tables) >= 1:
        parsed['main'] = _parse_rows(raw_tables[0])
    if 'pros' not in parsed and len(raw_tables) >= 2:
        parsed['pros'] = _parse_rows(raw_tables[1])

    # Phase B: parser_mode / parse_status for non-BRIDGE paths
    if legacy_found:
        parsed['parser_mode']  = 'LEGACY_TABLES'
        parsed['parse_status'] = 'legacy_fallback'
    elif not raw_tables:
        parsed['parser_mode']  = 'NO_BRIDGE'
        parsed['parse_status'] = 'bridge_missing'
    else:
        parsed['parser_mode']  = 'NO_BRIDGE'
        parsed['parse_status'] = 'unreadable'

    return parsed


# ── MCP health scoring ─────────────────────────────────────────────────────────

def compute_mcp_health(chart_ctx: dict, nova_state: dict) -> dict:
    """
    Compute a structured health/confidence score for the current MCP read.

    Observation only — the returned score does NOT gate execution.
    Score sources: bridge_meta (from parse_nova_tables) + chart_ctx connectivity.

    Score bands:
      100 = v2 BRIDGE, all required + optional fields present
       85 = v2 BRIDGE, all required present, optional missing
       70 = v2 BRIDGE, one required field missing
      60+ = v2 BRIDGE, 2 required missing (degrades toward 30)
       50 = legacy v1 BRIDGE or no BRIDGE_VER
       30 = connected but NOVA BRIDGE not found (indicator may be missing)
        0 = TradingView not reachable

    Status:
      HEALTHY  80–100
      DEGRADED 50–79
      BROKEN   0–49
    """
    warnings: list = []
    errors:   list = []

    _pm = nova_state.get('parser_mode',  'UNKNOWN')
    _ps = nova_state.get('parse_status', 'unknown')

    def _result(confidence: int, *, ticker=None, timeframe=None, session=None,
                fields_present: int = 0, fields_missing: list = None,
                bridge_ver: int = 1, v2: bool = False,
                ticker_match=None, timeframe_match=None,
                chart_symbol: str = '', chart_timeframe: str = '') -> dict:
        confidence = max(0, min(100, confidence))
        status = ('HEALTHY'  if confidence >= 80 else
                  'DEGRADED' if confidence >= 50 else 'BROKEN')
        return {
            'status':             status,
            'confidence':         confidence,
            'bridge_version':     bridge_ver,
            'bridge_v2_detected': v2,
            'ticker':             ticker,
            'timeframe':          timeframe,
            'session':            session,
            'fields_present':     fields_present,
            'fields_missing':     fields_missing or [],
            'warnings':           list(warnings),
            'errors':             list(errors),
            # Phase B additions
            'parser_mode':        _pm,
            'parse_status':       _ps,
            'ticker_match':       ticker_match,
            'timeframe_match':    timeframe_match,
            'chart_symbol':       chart_symbol,
            'chart_timeframe':    chart_timeframe,
        }

    _chart_sym = chart_ctx.get('symbol',    '')
    _chart_tf  = chart_ctx.get('timeframe', '')

    # Case 0: TradingView not reachable ───────────────────────────────────────
    if not chart_ctx.get('connected'):
        errors.append('TradingView not reachable')
        return _result(0, chart_symbol=_chart_sym, chart_timeframe=_chart_tf)

    bridge_meta  = nova_state.get('bridge_meta', {})
    nova_tables  = chart_ctx.get('nova_tables',  [])
    bridge_found = 'bridge_meta' in nova_state

    # Case 1: connected, NOVA BRIDGE absent ───────────────────────────────────
    if not bridge_found:
        if not nova_tables:
            errors.append('NOVA tables absent — indicator may be missing from chart')
        else:
            errors.append('NOVA BRIDGE header not found in any table')
        return _result(30, chart_symbol=_chart_sym, chart_timeframe=_chart_tf)

    bridge_ver  = bridge_meta.get('bridge_version',     1)
    v2_detected = bridge_meta.get('bridge_v2_detected', False)

    # Case 2: BRIDGE found but v1 (no BRIDGE_VER or < 2) ─────────────────────
    if not v2_detected:
        warnings.append(
            f'Legacy BRIDGE v{bridge_ver} detected — '
            're-save NOVA EXECUTION V1 to activate v2 fields'
        )
        return _result(50, bridge_ver=bridge_ver,
                       chart_symbol=_chart_sym, chart_timeframe=_chart_tf)

    # Case 3: v2 BRIDGE — evaluate field completeness ─────────────────────────
    all_missing = bridge_meta.get('bridge_fields_missing', [])
    missing_req = [f for f in all_missing if f in _MCP_REQUIRED_V2]
    missing_opt = [f for f in all_missing if f in _MCP_OPTIONAL_V2]

    for f in missing_req:
        warnings.append(f'Required v2 field absent: {f}')
    for f in missing_opt:
        warnings.append(f'Optional v2 field absent: {f}')

    n_req = len(missing_req)
    if n_req == 0:
        confidence = 85 if missing_opt else 100
    elif n_req == 1:
        confidence = 70
    else:
        # 2+ missing required: degrade from 65 toward 30
        confidence = max(30, 65 - (n_req - 1) * 10)

    # Identity check: TICKER from BRIDGE must match chart symbol ──────────────
    ticker    = bridge_meta.get('parsed_ticker')
    timeframe = bridge_meta.get('parsed_timeframe')
    session   = bridge_meta.get('parsed_session')

    def _norm(s: str) -> str:
        return s.replace('CME_MINI:', '').replace('CME:', '').replace('1!', '').strip().upper()

    ticker_match: bool | None    = None
    timeframe_match: bool | None = None

    if ticker and _chart_sym:
        ticker_match = (_norm(ticker) == _norm(_chart_sym))
        if not ticker_match:
            errors.append(
                f'Symbol mismatch: BRIDGE TICKER={ticker}, chart symbol={_chart_sym}'
            )
            confidence = min(confidence, 30)

    if timeframe and _chart_tf:
        timeframe_match = (timeframe.strip() == _chart_tf.strip())

    return _result(
        confidence,
        ticker=ticker, timeframe=timeframe, session=session,
        fields_present=bridge_meta.get('bridge_fields_present', 0),
        fields_missing=all_missing,
        bridge_ver=bridge_ver, v2=True,
        ticker_match=ticker_match, timeframe_match=timeframe_match,
        chart_symbol=_chart_sym, chart_timeframe=_chart_tf,
    )


# ── MCP snapshot logging ───────────────────────────────────────────────────────

_MCP_SNAPSHOT_CAP = 500

def _build_mcp_snapshot(
    chart_ctx:   dict,
    nova_state:  dict,
    mcp_health:  dict,
    session_ctx: dict,
) -> dict:
    """Build a structured snapshot dict from one reasoning cycle.  Pure — no I/O."""
    import time as _time
    bm   = nova_state.get('bridge_meta', {})
    bv2  = nova_state.get('bridge_v2',   {})
    pros = nova_state.get('pros', {})
    orb  = nova_state.get('orb',  {})

    # Compact mcp_health copy — only the fields useful for replay/audit
    _h = {
        'status':             mcp_health.get('status'),
        'confidence':         mcp_health.get('confidence'),
        'bridge_version':     mcp_health.get('bridge_version'),
        'bridge_v2_detected': mcp_health.get('bridge_v2_detected'),
        'ticker_match':       mcp_health.get('ticker_match'),
        'timeframe_match':    mcp_health.get('timeframe_match'),
        'warnings':           mcp_health.get('warnings', []),
        'errors':             mcp_health.get('errors',   []),
    }

    return {
        # ── snapshot classification ───────────────────────────────────────────
        'snapshot_type': 'market_read',
        # ── identity ──────────────────────────────────────────────────────────
        'timestamp':       _time.strftime('%Y-%m-%dT%H:%M:%SZ', _time.gmtime()),
        'symbol':          chart_ctx.get('symbol'),
        'timeframe':       chart_ctx.get('timeframe'),
        'session':         session_ctx.get('session') or mcp_health.get('session'),
        # ── parser diagnostics ────────────────────────────────────────────────
        'parser_mode':     nova_state.get('parser_mode'),
        'parse_status':    nova_state.get('parse_status'),
        # ── health summary ────────────────────────────────────────────────────
        'mcp_health':      _h,
        # ── chart identity cross-check ────────────────────────────────────────
        'chart_symbol':    chart_ctx.get('symbol'),
        'chart_timeframe': chart_ctx.get('timeframe'),
        'parsed_ticker':   bm.get('parsed_ticker'),
        'parsed_timeframe': bm.get('parsed_timeframe'),
        'ticker_match':    mcp_health.get('ticker_match'),
        'timeframe_match': mcp_health.get('timeframe_match'),
        # ── bridge data ───────────────────────────────────────────────────────
        'bridge_v2':       dict(bv2),
        'bridge_meta':     dict(bm),
        # ── raw NOVA state (rows 0-20 canonical keys) ─────────────────────────
        'nova_main': dict(nova_state.get('main', {})),
        'nova_pros': dict(pros),
        'nova_orb':  dict(orb),
        # ── market structure (promoted for easy querying) ─────────────────────
        'ib_high':        pros.get('IB H'),
        'ib_low':         pros.get('IB L'),
        'ib_status':      bv2.get('ib_status'),
        'orb_high':       orb.get('HIGH'),
        'orb_mid':        orb.get('MID'),
        'orb_low':        orb.get('LOW'),
        'orb_active':     bv2.get('orb_active'),
        'pros_active':    bv2.get('pros_active'),
        'peer_alignment': bv2.get('peer_align'),
        'draw_target':    bv2.get('draw_target'),
        'draw_direction': bv2.get('draw_dir'),
        # ── signal metadata (None until evaluation completes — Phase C logs
        #    market state at read time; signal overlay is a future refinement)
        'setup_type':  None,
        'signal_type': None,
        'direction':   None,
        'confidence':  None,
        'rationale':   None,
        # ── aggregated diagnostics ────────────────────────────────────────────
        'warnings': mcp_health.get('warnings', []),
        'errors':   mcp_health.get('errors',   []),
    }


def _append_mcp_snapshot(snapshot: dict) -> None:
    """Append snapshot to the rolling JSON file.  Non-blocking — caller runs in daemon thread."""
    import json as _json
    from core.config import MCP_SNAPSHOTS_FILE
    try:
        existing: list = []
        if MCP_SNAPSHOTS_FILE.exists():
            try:
                raw = _json.loads(MCP_SNAPSHOTS_FILE.read_text(encoding='utf-8'))
                existing = raw if isinstance(raw, list) else []
            except Exception:
                existing = []
        existing.append(snapshot)
        if len(existing) > _MCP_SNAPSHOT_CAP:
            existing = existing[-_MCP_SNAPSHOT_CAP:]
        MCP_SNAPSHOTS_FILE.write_text(_json.dumps(existing, indent=2), encoding='utf-8')
    except Exception as _exc:
        print(f'[mcp-snapshot] write error (non-fatal): {_exc}')


def _build_decision_snapshot(
    base_snap:     dict,
    *,
    pros_eval:     dict = None,
    orb_eval:      dict = None,
    ib_eval:       dict = None,
    pre_signal:    str  = '',
    pre_setup:     str  = '',
    pre_rationale: str  = '',
    decision:      dict = None,
    claude_called: bool = False,
    alert_generated: bool = False,
) -> dict:
    """Build a decision-enriched snapshot from a market_read base.  Pure — no I/O."""
    pe = pros_eval or {}
    oe = orb_eval  or {}
    ie = ib_eval   or {}
    de = decision  or {}

    alert_type     = de.get('alert_type', '') or ''
    alert_required = bool(de.get('alert_required', False))
    is_exec_ready  = alert_type == 'EXECUTION_READY'
    is_heads_up    = alert_type == 'HEADS_UP'
    is_no_trade    = (alert_type == 'NO_TRADE') or (pre_signal == 'NO_TRADE')
    is_rejected    = claude_called and not alert_required
    rejection_reason = (de.get('no_alert_reason', '') or '') if not alert_required else ''

    snap = dict(base_snap)
    snap.update({
        'snapshot_type': 'decision',
        # ── pre-evaluator signal (deterministic output) ───────────────────────
        'pre_signal':    pre_signal,
        'pre_setup':     pre_setup,
        'pre_rationale': pre_rationale,
        # ── evaluator summaries ───────────────────────────────────────────────
        'pros_eval_summary': {
            'phase':          pe.get('phase'),
            'direction':      pe.get('direction'),
            'setup_type':     pe.get('setup_type'),
            'has_signal':     pe.get('has_signal'),
            'signal_strength': pe.get('signal_strength'),
            'ote_status':     pe.get('ote_status'),
            'cont_quality':   pe.get('cont_quality'),
        },
        'orb_eval_summary': {
            'phase':         oe.get('phase'),
            'direction':     oe.get('direction'),
            'setup_type':    oe.get('setup_type'),
            'has_signal':    oe.get('has_signal'),
            'entry_type':    oe.get('entry_type'),
            'entry_quality': oe.get('entry_quality'),
            'in_context':    oe.get('in_context'),
            'orb_range':     oe.get('orb_range'),
        },
        'ib_eval_summary': {
            'draw':        ie.get('draw'),
            'draw_source': ie.get('draw_source'),
            'aligned':     ie.get('aligned'),
            'ib_range':    ie.get('ib_range'),
            'ib_tight':    ie.get('ib_tight'),
            'ib_source':   ie.get('ib_source'),
        },
        # ── Claude decision fields ────────────────────────────────────────────
        'claude_called':  claude_called,
        'signal_type':    alert_type or pre_signal,
        'setup_type':     de.get('setup_type') or pre_setup,
        'direction':      de.get('direction'),
        'confidence':     None,
        'grade':          de.get('grade'),
        'rationale':      de.get('reasoning') or de.get('notes'),
        'entry_zone':     de.get('entry_zone'),
        'stop':           de.get('stop'),
        'tp1':            de.get('tp1'),
        'rr':             de.get('rr'),
        # ── final decision state ──────────────────────────────────────────────
        'alert_required':     alert_required,
        'alert_generated':    alert_generated,
        'is_execution_ready': is_exec_ready,
        'is_heads_up':        is_heads_up,
        'is_no_trade':        is_no_trade,
        'is_rejected':        is_rejected,
        'rejection_reason':   rejection_reason,
    })
    return snap


def _fire_decision_snapshot(base: dict, **kwargs) -> None:
    """Build a decision snapshot and append it in a daemon thread (non-blocking)."""
    snap = _build_decision_snapshot(base, **kwargs)
    _threading.Thread(target=_append_mcp_snapshot, args=(snap,), daemon=True).start()


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
    # leaving the engine in ACTIVE. That reference consumption is not a
    # failure; it means the sequence completed and price is now in accepted regime.
    # Promote to ACCEPTED_CONTINUATION so Claude can grade it — all risk gates intact.
    # BUILDING excluded: price has not yet reached OTE — CONT=CONFIRMED before OTE is a
    # sequence violation (manipulation → OTE → rejection → continuation requires the
    # OTE to be reached before continuation can be confirmed).
    if cont_quality == 'STRONG' and phase in ('OTE_APPROACHING', 'OTE_TAGGED'):
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


def _evaluate_orb_phase(main_state: dict, chart_ctx: dict, session_ctx: dict, orb_table: dict | None = None) -> dict:
    """
    Detect ORB setup from the NOVA indicator's ORB CONSOLE table.

    Primary source: TYPE and BIAS fields populated by the orbPassXxx gate layer
    (orbPassMidRejectBull/Bear, orbPassLiqRejectBull/Bear, orbPassEdgeRejectBull/Bear).
    These implement RP's three setup types directly:
      MID_REJECT  → ORB_BREAK_RETEST (break → mandatory midpoint retest → confirmation)
      LIQ_REJECT  → ORB_BOUNCE / ORB_REJECTION (external key level sweep + reclaim)
      EDGE_REJECT → ORB_BOUNCE / ORB_REJECTION (ORB boundary tap + rejection)

    No longer re-derives signal from price proximity (old E1/E2 logic removed).
    """
    labels = chart_ctx.get('nova_labels', [])
    levels = chart_ctx.get('nova_levels', [])

    orb_high = _extract_level(labels, levels, 'ORB HIGH') or _extract_level(labels, levels, 'ORB_HIGH')
    orb_low  = _extract_level(labels, levels, 'ORB LOW')  or _extract_level(labels, levels, 'ORB_LOW')
    orb_mid  = _extract_level(labels, levels, 'ORB MID')  or _extract_level(labels, levels, 'ORB_MID')

    if not orb_high or not orb_low:
        return {
            'phase':         'UNDEFINED',
            'has_signal':    False,
            'setup_type':    'N/A',
            'direction':     'N/A',
            'entry_type':    '',
            'entry_quality': '',
            'orb_high':      None,
            'orb_low':       None,
            'orb_mid':       None,
            'orb_range':     None,
            'orb_wide':      False,
            'in_context':    session_ctx['in_window'],
        }

    orb_range = orb_high - orb_low
    if not orb_mid:
        orb_mid = (orb_high + orb_low) / 2

    # Read indicator's RP-framework classification from ORB CONSOLE table
    _tbl          = orb_table or {}
    entry_type    = _tbl.get('TYPE', '').strip()
    entry_quality = _tbl.get('REJ Q', '').strip()
    bias_raw      = _tbl.get('BIAS', '').strip().upper()

    # BIAS values from Pine Script: "BULL", "BEAR", "BULL DEAD", "BEAR DEAD", "NEUTRAL"
    if 'BULL' in bias_raw and 'DEAD' not in bias_raw:
        direction = 'LONG'
    elif 'BEAR' in bias_raw and 'DEAD' not in bias_raw:
        direction = 'SHORT'
    else:
        direction = 'N/A'

    # TYPE values that indicate an active orbPassXxx gate has fired:
    #   MID_REJECT  — orbPassMidRejectBull/Bear: break confirmed + midpoint retest + closure
    #   LIQ_REJECT  — orbPassLiqRejectBull/Bear: external key level swept + 2-bar reclaim
    #   EDGE_REJECT — orbPassEdgeRejectBull/Bear: ORB boundary tap + rejection quality sequence
    # All other TYPE values (MID DEFEND ▲, LIQ DETECT, EXPANDING, etc.) are context display only.
    _SETUP_MAP = {
        'MID_REJECT': {
            'LONG':  'ORB_BREAK_RETEST_LONG',
            'SHORT': 'ORB_BREAK_RETEST_SHORT',
            'N/A':   'ORB_BREAK_RETEST',
        },
        'LIQ_REJECT': {
            'LONG':  'ORB_BOUNCE_LONG',
            'SHORT': 'ORB_REJECTION_SHORT',
            'N/A':   'ORB_LIQ_REJECT',
        },
        'EDGE_REJECT': {
            'LONG':  'ORB_BOUNCE_LONG',
            'SHORT': 'ORB_REJECTION_SHORT',
            'N/A':   'ORB_EDGE_REJECT',
        },
    }

    if entry_type in _SETUP_MAP:
        phase      = entry_type
        setup_type = _SETUP_MAP[entry_type].get(direction, _SETUP_MAP[entry_type]['N/A'])
        has_signal = True
    else:
        phase      = 'NO_SETUP'
        setup_type = 'N/A'
        has_signal = False

    return {
        'phase':         phase,
        'direction':     direction,
        'setup_type':    setup_type,
        'has_signal':    has_signal,
        'entry_type':    entry_type,
        'entry_quality': entry_quality,
        'orb_high':      orb_high,
        'orb_low':       orb_low,
        'orb_mid':       orb_mid,
        'orb_range':     orb_range,
        'orb_wide':      orb_range > 15,
        'in_context':    session_ctx['in_window'],
    }


# ── IB cross-validator ────────────────────────────────────────────────────────
# Keyed by ISO date string; populated after 10:30 AM so the window is complete.
_ib_yf_cache: dict = {}

def _compute_ib_from_yfinance() -> dict:
    """
    Derive IB High/Low from yfinance 1-minute NQ=F data for today's RTH session.
    Only uses bars timestamped 9:30–10:29 AM ET — never pre-market or overnight.
    Returns {'ib_high': float, 'ib_low': float, 'forming': bool} or {} on failure.
    Caches once the IB window closes (10:30 AM ET).
    """
    global _ib_yf_cache
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        import yfinance as _yf

        tz  = ZoneInfo('America/New_York')
        now = datetime.now(tz)
        mins = now.hour * 60 + now.minute
        if mins < 9 * 60 + 30:
            return {}

        cache_key = now.date().isoformat()
        if cache_key in _ib_yf_cache:
            return _ib_yf_cache[cache_key]

        hist = _yf.Ticker('NQ=F').history(period='1d', interval='1m', prepost=True)
        if hist.empty:
            return {}
        hist.index = hist.index.tz_convert(tz)
        today_bars = hist[hist.index.date == now.date()]
        ib_bars    = today_bars.between_time('09:30', '10:29')
        if ib_bars.empty:
            return {}

        result = {
            'ib_high': float(ib_bars['High'].max()),
            'ib_low':  float(ib_bars['Low'].min()),
            'forming': mins < 10 * 60 + 30,
        }
        if mins >= 10 * 60 + 30:
            _ib_yf_cache[cache_key] = result
        return result
    except Exception:
        return {}

# Max allowed deviation (NQ points) between PROS table IB and yfinance IB
# before the PROS table value is considered stale and overridden.
_IB_STALE_THRESHOLD = 75.0


def _evaluate_ib_alignment(main_state: dict, chart_ctx: dict, pros_state: dict | None = None) -> dict:
    """
    Assess IB draw alignment.
    IB levels come from PROS table rows IB H / IB L (preferred — added in Pine v1.x+) or
    fall back to NOVA labels/lines. CMD gives the directional bias.

    Cross-validates all PROS table values against a live yfinance 1m computation.
    If the deviation exceeds _IB_STALE_THRESHOLD the PROS table value is treated as
    stale (chart crash / state corruption) and the yfinance value is used instead.
    """
    labels = chart_ctx.get('nova_labels', [])
    levels = chart_ctx.get('nova_levels', [])
    price  = chart_ctx.get('price')

    # Primary: PROS table (reliable bridge, no label-parsing risk)
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

    # Secondary: label extraction for older Pine builds
    if not ib_high:
        ib_high = _extract_level(labels, levels, 'IB HIGH') or _extract_level(labels, levels, 'IB_HIGH')
    if not ib_low:
        ib_low  = _extract_level(labels, levels, 'IB LOW')  or _extract_level(labels, levels, 'IB_LOW')

    # Cross-validate against independently computed yfinance IB.
    # Stale chart state (crash, holiday gap, contract roll) can produce wildly wrong
    # PROS table values — yfinance gives us ground truth from actual 1m RTH bars.
    _ib_source = 'pros_table'
    yf_ib = _compute_ib_from_yfinance()
    if yf_ib:
        yf_h, yf_l = yf_ib.get('ib_high'), yf_ib.get('ib_low')
        if ib_high and yf_h and abs(ib_high - yf_h) > _IB_STALE_THRESHOLD:
            print(f'[IB-GUARD] PROS IB_H {ib_high} deviates {abs(ib_high-yf_h):.1f}pts from yfinance {yf_h:.2f} — using yfinance')
            ib_high = yf_h
            _ib_source = 'yfinance_override'
        if ib_low and yf_l and abs(ib_low - yf_l) > _IB_STALE_THRESHOLD:
            print(f'[IB-GUARD] PROS IB_L {ib_low} deviates {abs(ib_low-yf_l):.1f}pts from yfinance {yf_l:.2f} — using yfinance')
            ib_low = yf_l
            _ib_source = 'yfinance_override'
        # Use yfinance as sole source when PROS table returned nothing
        if not ib_high and yf_h:
            ib_high    = yf_h
            _ib_source = 'yfinance_primary'
        if not ib_low and yf_l:
            ib_low     = yf_l
            _ib_source = 'yfinance_primary'

    cmd_up = main_state.get('CMD', '').upper()

    if not ib_high or not ib_low:
        return {'draw': 'UNCLEAR', 'ib_high': None, 'ib_low': None, 'aligned': None,
                'ib_range': None}

    ib_range = ib_high - ib_low

    # Infer draw from CMD — substring match handles "WATCH LONG", "WATCH SHORT" etc.
    draw           = 'UNCLEAR'
    draw_source    = 'CMD'
    if 'BUY' in cmd_up or 'LONG' in cmd_up or 'BULL' in cmd_up:
        draw = 'IB HIGH'
    elif 'SELL' in cmd_up or 'SHORT' in cmd_up or 'BEAR' in cmd_up:
        draw = 'IB LOW'

    # DISPL fallback: when CMD is WAIT/neutral, PROS table DISPL field carries direction.
    # Marked as fallback so callers can surface it in rationale — direction is less certain.
    if draw == 'UNCLEAR' and pros_state:
        displ_up = (pros_state.get('DISPL', '') or '').upper()
        if 'BULL' in displ_up:
            draw        = 'IB HIGH'
            draw_source = 'DISPL_FALLBACK'
        elif 'BEAR' in displ_up:
            draw        = 'IB LOW'
            draw_source = 'DISPL_FALLBACK'

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
        'draw':        draw,
        'draw_source': draw_source,
        'ib_high':     ib_high,
        'ib_low':      ib_low,
        'ib_range':    ib_range,
        'aligned':     aligned,
        'ib_tight':    ib_range is not None and ib_range < 5,
        'ib_source':   _ib_source,
    }


def _check_invalidation_signals(
    main_state: dict,
    pros_state: dict,
    chart_ctx:  dict,
    pros_eval:  dict | None = None,
) -> dict:
    """
    Detect explicit invalidation signals from NOVA indicator state.
    Returns whether an active setup has been broken.

    pros_eval is optional; when present, enables H2 (price beyond displacement base).
    """
    state_up = main_state.get('STATE', '').upper()

    invalidated = False
    reason      = ''

    # NOVA indicator may emit explicit invalidation labels
    for keyword in ('INVALID', 'BROKEN', 'FAILED', 'VIOLATED'):
        if keyword in state_up:
            invalidated = True
            reason = f'Setup {keyword.lower()} per NOVA indicator'
            break

    # H2: price closed beyond displacement base — directional thesis structurally broken.
    # Uses 30-bar swing as the displacement origin proxy (same data as price_ote_eval).
    # Only runs when an active PROS signal with a known direction exists.
    if not invalidated and pros_eval and pros_eval.get('has_signal'):
        direction = pros_eval.get('direction', 'N/A')
        ohlcv     = chart_ctx.get('ohlcv', {})
        try:
            price = float(chart_ctx.get('price') or 0)
            if direction == 'SHORT':
                sw_hi = float(ohlcv.get('high_30') or 0)
                if sw_hi and price > sw_hi:
                    invalidated = True
                    reason = f'H2: price {price:.2f} above displacement base {sw_hi:.2f} — bearish thesis broken'
            elif direction == 'LONG':
                sw_lo = float(ohlcv.get('low_30') or 0)
                if sw_lo and price < sw_lo:
                    invalidated = True
                    reason = f'H2: price {price:.2f} below displacement base {sw_lo:.2f} — bullish thesis broken'
        except (TypeError, ValueError):
            pass

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
        if ib_eval.get('draw_source') == 'DISPL_FALLBACK':
            base_rationale += ' | IB_DIR:DISPL_FALLBACK(CMD=WAIT)'

        # Fix 4: surface PROS/ORB conflict for Claude — do not block, just flag.
        if orb_eval.get('has_signal') and orb_eval.get('in_context'):
            base_rationale = (
                f'[ORB_CONFLICT: ORB also signaling {orb_eval.get("phase","?")} {orb_eval.get("direction","?")}] '
                + base_rationale
            )

        # Fix 1: direction must be known before autonomous execution is permitted.
        # N/A means both CMD and DISPL were absent/neutral — no routing target exists.
        _can_execute = direction != 'N/A'
        _no_dir_note = '' if _can_execute else ' | [NO_DIR] direction indeterminate — capped at HEADS_UP'

        if phase == 'SETUP_READY':
            if _can_execute:
                return EXECUTION_READY, setup, base_rationale
            return HEADS_UP, setup, base_rationale + _no_dir_note
        elif phase == 'OTE_TAGGED':
            if _can_execute:
                return EXECUTION_READY, setup, base_rationale + ' | OTE tagged'
            return HEADS_UP, setup, base_rationale + ' | OTE tagged' + _no_dir_note
        elif phase == 'ACCEPTED_CONTINUATION':
            if _can_execute:
                return EXECUTION_READY, setup, base_rationale + ' | accepted continuation regime — CONT confirmed'
            return HEADS_UP, setup, base_rationale + ' | accepted continuation regime' + _no_dir_note
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
        quality   = orb_eval.get('entry_quality', '') or '?'
        orb_range_val = orb_eval.get('orb_range')
        range_str = f'{orb_range_val:.1f}' if orb_range_val is not None else '?'
        rationale = f'ORB {phase} | {setup} | quality={quality} | range={range_str}pts{wide_note}'
        return HEADS_UP, setup, rationale

    return None, 'N/A', 'No qualifying signal detected'


def _apply_market_reality_gate(
    signal_type: str,
    setup_type:  str,
    rationale:   str,
) -> tuple[str, str, str]:
    """
    Hard gate based on Market Reality 2.0 objective state.
    Runs BEFORE the conviction gate — highest priority override.

    BEARISH_DOMINANT / PANIC_SELLING → LONG signals capped at HEADS_UP.
    BULLISH_DOMINANT                 → SHORT signals capped at HEADS_UP.

    This gate cannot be overridden by Pine state, PROS phase, or IB draw.
    If the market is objectively BEARISH_DOMINANT, the system will not
    autonomously execute longs regardless of any setup signal.
    """
    if not _load_mr2:
        return signal_type, setup_type, rationale

    try:
        mr2   = _load_mr2()
        state = mr2.get('state', 'NEUTRAL')

        is_long  = 'LONG' in setup_type or 'BULL' in setup_type
        is_short = 'SHORT' in setup_type or 'BEAR' in setup_type

        if signal_type == EXECUTION_READY:
            if is_long and mr2.get('block_longs'):
                return (
                    HEADS_UP,
                    setup_type,
                    f'[MR2_GATE {state}] LONG auto-execution blocked — '
                    f'{mr2.get("block_longs_reason", state)} | {rationale}',
                )
            if is_short and mr2.get('block_shorts'):
                return (
                    HEADS_UP,
                    setup_type,
                    f'[MR2_GATE {state}] SHORT auto-execution blocked — '
                    f'{mr2.get("block_shorts_reason", state)} | {rationale}',
                )
    except Exception:
        pass

    return signal_type, setup_type, rationale


def _apply_conviction_gate(
    signal_type:  str,
    setup_type:   str,
    rationale:    str,
    dir_pressure: dict,
) -> tuple[str, str, str]:
    """
    Post-classification conviction filter. Runs after _classify_signal(),
    before evaluate_with_claude(). Makes directional intelligence load-bearing
    in the execution path — not just informational to Claude.

    Rules:
      CONFLICTED / LOW conviction  → cap EXECUTION_READY at HEADS_UP.
        When primary intelligence sources disagree, the system must not
        autonomously execute regardless of Claude's grade. Claude still
        evaluates, but the output is capped at HEADS_UP.

      Counter-dominant signal      → flag in rationale.
        LONG vs BEAR_DOMINANT (or vice versa) doesn't block the signal —
        exceptional counter-trend setups exist. But Claude must see the
        pressure conflict explicitly and justify the grade.

      Aligned signal               → affirm in rationale.
        LONG + BULL_DOMINANT + HIGH conviction is the ideal environment.
        Claude sees alignment and can grade with confidence.
    """
    if not dir_pressure or dir_pressure.get('dominance') == 'NEUTRAL':
        return signal_type, setup_type, rationale

    conviction = dir_pressure.get('conviction', 'HIGH')
    dominance  = dir_pressure.get('dominance',  'CONTESTED')
    bull_pts   = dir_pressure.get('bullish', 0)
    bear_pts   = dir_pressure.get('bearish', 0)
    net        = dir_pressure.get('net', 0)

    is_long  = 'LONG' in setup_type or 'BULL' in setup_type
    is_short = 'SHORT' in setup_type or 'BEAR' in setup_type

    # Gate 1: low conviction blocks autonomous execution
    if signal_type == EXECUTION_READY and conviction in ('CONFLICTED', 'LOW'):
        return (
            HEADS_UP,
            setup_type,
            f'[CONVICTION_GATE conviction={conviction}] '
            f'EXECUTION_READY capped at HEADS_UP | '
            f'bull={bull_pts} bear={bear_pts} net={net:+d} | {rationale}',
        )

    # Gate 2: counter-dominant trade — require explicit Claude justification
    if is_long and 'BEAR' in dominance:
        rationale = (
            f'[COUNTER_DOMINANT {dominance} bear={bear_pts} vs bull={bull_pts}] '
            f'Grade A requires clear structural reason to trade against dominance. '
            f'{rationale}'
        )
    elif is_short and 'BULL' in dominance:
        rationale = (
            f'[COUNTER_DOMINANT {dominance} bull={bull_pts} vs bear={bear_pts}] '
            f'Grade A requires clear structural reason to trade against dominance. '
            f'{rationale}'
        )

    # Gate 3: fully aligned environment — affirm for Claude
    elif conviction == 'HIGH' and (
        (is_long  and 'BULL' in dominance) or
        (is_short and 'BEAR' in dominance)
    ):
        rationale = (
            f'[ALIGNED {dominance} conviction=HIGH net={net:+d}] '
            f'All intelligence sources agree. '
            f'{rationale}'
        )

    return signal_type, setup_type, rationale


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

## MOMENTUM CONFIRMATION (MACD quality factor — never a trigger)
Evidence of buyer/seller control returning during OTE retracement. 5m MACD slope, acceleration, and curl.
This is a quality modifier — it adjusts grade, not the decision to trade.

STRONG_BULLISH: MACD slope turned positive + curl up + histogram growing → buyers stepping in at OTE
BULLISH:        Positive slope or histogram growing — partial confirmation
NEUTRAL:        No clear momentum signal — grade from structure alone
BEARISH:        Selling momentum persists at OTE — caution
STRONG_BEARISH: Sellers accelerating — structural concern

Grade adjustment rules (apply after all other factors):

STEP 1 — Check for full conviction cluster BEFORE applying any MACD adjustment.
If ALL five of the following are true simultaneously, skip the MACD downgrade rules entirely
and assign the grade the structure deserves (A if structure is clean). Log MACD as cautionary only.
  (1) Pre-signal = EXECUTION_READY
  (2) Indicator confidence contains ELITE (85%+)
  (3) PROS QUALITY = STRONG
  (4) PROS CONT = CONFIRMED
  (5) IB aligned = True (draw resolved, direction confirmed)
When this cluster is present: grade from structure + IB alignment alone. Do not reduce the grade
for MACD direction. Add to notes: "MACD not yet curled — entry may be 1-2 bars early.
Full conviction cluster present; structure takes precedence over momentum lag."
This cluster check does NOT apply to ORB setups (PROS fields will be absent).
It does NOT apply when quality=WEAK, phase=BUILDING, confidence is not ELITE, or IB is UNCLEAR.

STEP 2 — If conviction cluster is NOT fully present, apply standard MACD adjustments:
- LONG setup + STRONG_BULLISH → upgrade one tier if borderline (B→A possible if all else aligns)
- LONG setup + BEARISH        → downgrade one tier (A→B, B→C)
- LONG setup + STRONG_BEARISH → downgrade one tier + note active selling at OTE
- SHORT setup + STRONG_BEARISH → upgrade one tier if borderline
- SHORT setup + BULLISH       → downgrade one tier
- SHORT setup + STRONG_BULLISH → downgrade one tier + note active buying at OTE
- NEUTRAL → no change; use structure and IB to determine grade

Critical: MACD curl near OTE (slope direction reversal) is the highest-value momentum signal.
It marks the exact bar where control is transferring. A clean curl + IB aligned = high-confidence setup.
NEVER downgrade to D solely for BEARISH/STRONG_BEARISH momentum — it is one input among many.

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

    # Market Reality 2.0 — objective ground truth (leads the prompt)
    _mr2_block = ''
    try:
        if _load_mr2 and _mr2_prompt:
            _mr2      = _load_mr2()
            _mr2_block = _mr2_prompt(_mr2)
    except Exception:
        pass

    # Market Reality v1 — only included when V2 is unavailable (avoids dual-source drift)
    _mr_block = ''
    if not _mr2_block:
        try:
            from engines.market_reality import load_market_reality, format_reality_for_prompt
            _mr = load_market_reality()
            _mr_block = format_reality_for_prompt(_mr)
        except Exception:
            _mr = {}

    # Cross-market intelligence — observation context only, not an execution gate
    _cm_block = ''
    try:
        if _load_cm and _cm_prompt:
            _cm_block = _cm_prompt(_load_cm())
    except Exception:
        pass

    # Market structure memory — overnight range, prior week levels, gap, monthly open
    _ms_block = ''
    try:
        if _load_ms and _ms_prompt:
            _ms_block = _ms_prompt(_load_ms())
    except Exception:
        pass

    # Liquidity & participation — RVOL, session type, breadth, volume confirmation
    _p_block = ''
    try:
        if _load_p and _p_prompt:
            _p_block = _p_prompt(_load_p())
    except Exception:
        pass

    # Liquidity intelligence — swept/untapped levels, primary draw
    _liq_block = ''
    try:
        if _load_liq and _liq_prompt:
            _liq_block = _liq_prompt(_load_liq())
    except Exception:
        pass

    # Session Memory — rolling multi-session narrative context (historical before current)
    _mem_block = ''
    try:
        if _load_mem and _mem_prompt:
            _mem_block = _mem_prompt(_load_mem())
    except Exception:
        pass

    # Synthesis — unified market interpretation across all Level 1 intelligence engines
    _syn_block = ''
    try:
        if _load_syn and _syn_prompt:
            _syn_block = _syn_prompt(_load_syn())
    except Exception:
        pass

    main_state = nova_state.get('main', {})
    pros_state = nova_state.get('pros', {})

    pre = pre_assess or {}
    pros_eval       = pre.get('pros_eval', {})
    orb_eval        = pre.get('orb_eval', {})
    ib_eval         = pre.get('ib_eval', {})
    inv_eval        = pre.get('inv_eval', {})
    price_ote_eval  = pre.get('price_ote_eval', {})
    momentum_eval   = pre.get('momentum_eval', {})

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

    return f"""{_mr2_block}

{_mr_block}

{_cm_block}

{_ms_block}

{_p_block}

{_liq_block}

{_mem_block}

{_syn_block}

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

{_momentum_fmt(momentum_eval) if _momentum_fmt and momentum_eval else ''}

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
    orb_table       = nova_state.get('orb', {})

    # MCP health — observation only, does not affect execution path below
    _mcp_health = compute_mcp_health(chart_ctx, nova_state)
    _h = _mcp_health
    print(
        f'[mcp-health]'
        f' status={_h["status"]}'
        f' confidence={_h["confidence"]}'
        f' bridge={_h["bridge_version"]}'
        f' ticker={_h["ticker"]}'
        f' tf={_h["timeframe"]}'
        f' session={_h["session"]}'
        f' warnings={len(_h["warnings"])}'
        f' errors={len(_h["errors"])}'
        f' parser_mode={_h.get("parser_mode","?")}'
        f' parse_status={_h.get("parse_status","?")}'
        f' ticker_match={_h.get("ticker_match")}'
        f' tf_match={_h.get("timeframe_match")}'
    )

    def _write_and_push_mcp_health(h: dict) -> None:
        import time
        from core.config import MCP_HEALTH_FILE, NOVA_RENDER_URL, NOVA_INGEST_SECRET
        h['_written_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        try:
            MCP_HEALTH_FILE.write_text(json.dumps(h, indent=2))
        except Exception:
            pass
        try:
            if NOVA_RENDER_URL and NOVA_INGEST_SECRET:
                import requests as _req
                _req.post(
                    NOVA_RENDER_URL + '/api/feed/ingest',
                    json={'mcp_health': h},
                    headers={'X-Nova-Ingest-Secret': NOVA_INGEST_SECRET},
                    timeout=4,
                )
        except Exception:
            pass
    _threading.Thread(target=_write_and_push_mcp_health, args=(_mcp_health.copy(),), daemon=True).start()

    _mcp_snap = _build_mcp_snapshot(chart_ctx, nova_state, _mcp_health, session_ctx)
    _threading.Thread(target=_append_mcp_snapshot, args=(_mcp_snap,), daemon=True).start()

    pros_eval       = _evaluate_pros_phase(main_state, pros_state_data, chart_ctx)
    orb_eval        = _evaluate_orb_phase(main_state, chart_ctx, session_ctx, orb_table)
    ib_eval         = _evaluate_ib_alignment(main_state, chart_ctx, pros_state_data)
    inv_eval        = _check_invalidation_signals(main_state, pros_state_data, chart_ctx, pros_eval)
    price_ote_eval  = _evaluate_price_structure(chart_ctx, ib_eval, pros_eval, main_state)

    mem_summary = {}
    if _market_memory:
        try:
            _market_memory.update(symbol, session_ctx, price_ote_eval, pros_eval, chart_ctx)
            mem_summary = _market_memory.get_summary(symbol)
        except Exception:
            pass

    momentum_eval = {}
    if _compute_momentum:
        try:
            momentum_eval = _compute_momentum(symbol, ote_eval=price_ote_eval)
        except Exception:
            pass

    # Classify first — family must be known before DP can be computed
    signal_type, setup_type, rationale = _classify_signal(
        pros_eval, orb_eval, ib_eval, inv_eval, session_ctx, price_ote_eval
    )

    if signal_type is None:
        print(f'[nova-reasoning] {session_ctx["time_et"]} | {symbol} | no signal | {rationale}')
        _fire_decision_snapshot(
            _mcp_snap,
            pros_eval=pros_eval, orb_eval=orb_eval, ib_eval=ib_eval,
            pre_signal='', pre_setup='', pre_rationale=rationale or '',
            decision=None, claude_called=False, alert_generated=False,
        )
        return []

    # Derive active family from classification — gates which DP scorers run
    _active_family = setup_type.split('_')[0].upper() if '_' in setup_type else ''

    dir_pressure = {}
    if _dp_engine:
        try:
            dir_pressure = _dp_engine.compute(
                pros_eval, ib_eval, session_ctx, mem_summary,
                momentum_eval=momentum_eval or None,
                orb_eval=orb_eval or None,
                active_family=_active_family,
            )
        except Exception:
            pass

    signal_type, setup_type, rationale = _apply_market_reality_gate(
        signal_type, setup_type, rationale
    )
    signal_type, setup_type, rationale = _apply_conviction_gate(
        signal_type, setup_type, rationale, dir_pressure
    )

    if signal_type == NO_TRADE and session_ctx.get('daily_loss_hit') and AlertData:
        _fire_decision_snapshot(
            _mcp_snap,
            pros_eval=pros_eval, orb_eval=orb_eval, ib_eval=ib_eval,
            pre_signal=signal_type, pre_setup=setup_type, pre_rationale=rationale or '',
            decision=None, claude_called=False, alert_generated=True,
        )
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

    # Tier 1 family isolation: Claude sees only the responsible strategy family.
    # _active_family was derived from setup_type before any gate modification.
    if _active_family == 'ORB':
        _pros_for_claude, _orb_for_claude = {}, orb_eval
    elif _active_family == 'PROS':
        _pros_for_claude, _orb_for_claude = pros_eval, {}
    else:
        _pros_for_claude, _orb_for_claude = pros_eval, orb_eval

    pre_assess = {
        'pros_eval':      _pros_for_claude,
        'orb_eval':       _orb_for_claude,
        'ib_eval':        ib_eval,
        'inv_eval':       inv_eval,
        'price_ote_eval': price_ote_eval,
        'dir_pressure':   dir_pressure,
        'momentum_eval':  momentum_eval,
        'pre_signal':     signal_type,
        'pre_setup':      setup_type,
        'rationale':      rationale,
    }
    decision = evaluate_with_claude(nova_state, session_ctx, chart_ctx, pre_assess)
    if not decision:
        _fire_decision_snapshot(
            _mcp_snap,
            pros_eval=pros_eval, orb_eval=orb_eval, ib_eval=ib_eval,
            pre_signal=signal_type, pre_setup=setup_type, pre_rationale=rationale or '',
            decision=None, claude_called=True, alert_generated=False,
        )
        return []

    # Load MR2 once — shared between reasoning snapshot and signal log entry.
    _mr2_snap: dict = {}
    if _load_mr2:
        try:
            _mr2_snap = _load_mr2()
        except Exception:
            pass

    _snapshot_entry: dict = {}
    _snapshot_id = ''
    if _log_snapshot:
        try:
            _snap_result = _log_snapshot(
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
                mr2_state       = _mr2_snap,
                momentum_eval   = momentum_eval,
            )
            if isinstance(_snap_result, dict):
                _snapshot_entry = _snap_result
                _snapshot_id    = _snap_result.get('id', '')
        except Exception:
            pass

    # Derive fields for self-contained signal log entry (readable months later without reconstruction).
    _final_setup      = decision.get('setup_type', '') or setup_type or ''
    _strategy_family  = _final_setup.split('_')[0].upper() if '_' in _final_setup else _active_family or ''
    _claude_rationale = decision.get('reasoning', '') or decision.get('notes', '') or ''
    _mr2_block_reason = _mr2_snap.get('block_longs_reason', '') or _mr2_snap.get('block_shorts_reason', '')

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

        # Session development telemetry — minutes since 9:30 ET
        _ny_session = session_ctx.get('session', '')
        if _ny_session in ('NY_OPEN', 'NY_AM', 'NY_PM', 'NEW_YORK_CASH', 'LUNCH'):
            _now_log = now_ny()
            _ny_open_minutes = (_now_log.hour * 60 + _now_log.minute) - (9 * 60 + 30)
        else:
            _ny_open_minutes = None

        _draw_tel = _classify_draw(
            price          = chart_ctx.get('price'),
            tp1_str        = decision.get('tp1', '') or '',
            ib_draw        = ib_eval.get('draw', ''),
            ib_draw_claude = decision.get('ib_draw', '') or '',
            session        = session_ctx.get('session', ''),
        )

        _signal_entry = log_cycle(
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
            orb_state        = orb_parsed.get('STATE', ''),
            orb_bias         = orb_parsed.get('BIAS', ''),
            orb_high         = _safe_float(orb_parsed.get('HIGH')),
            orb_mid          = _safe_float(orb_parsed.get('MID')),
            orb_low          = _safe_float(orb_parsed.get('LOW')),
            orb_signal       = bool(orb_eval.get('has_signal')),
            orb_phase        = orb_eval.get('phase', ''),
            orb_range        = orb_eval.get('orb_range'),
            orb_entry_type   = orb_eval.get('entry_type', ''),
            orb_entry_quality= orb_eval.get('entry_quality', ''),

            # IB
            ib_high    = ib_eval.get('ib_high'),
            ib_low     = ib_eval.get('ib_low'),
            ib_draw    = ib_eval.get('draw', ''),
            ib_aligned = ib_eval.get('aligned'),
            ib_tight   = bool(ib_eval.get('ib_tight')),
            ib_source  = ib_eval.get('ib_source', 'pros_table'),

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

            # Draw Validation telemetry
            draw_name        = _draw_tel.get('draw_name', ''),
            draw_category    = _draw_tel.get('draw_category', ''),
            draw_tp1_pts     = _draw_tel.get('draw_tp1_pts'),
            draw_independent = _draw_tel.get('draw_independent'),

            # Strategy metadata
            strategy_family  = _strategy_family,

            # Claude rationale text
            claude_rationale = _claude_rationale,

            # Market Reality snapshot at signal time
            mr2_state        = _mr2_snap.get('state', ''),
            mr2_score        = _mr2_snap.get('score'),
            mr2_block_longs  = bool(_mr2_snap.get('block_longs', False)),
            mr2_block_shorts = bool(_mr2_snap.get('block_shorts', False)),
            mr2_block_reason = _mr2_block_reason,

            # Directional Pressure snapshot at signal time
            dp_dominance     = dir_pressure.get('dominance', ''),
            dp_conviction    = dir_pressure.get('conviction', ''),
            dp_bullish       = dir_pressure.get('bullish'),
            dp_bearish       = dir_pressure.get('bearish'),
            dp_net           = dir_pressure.get('net'),

            # Cross-reference to full reasoning snapshot
            reasoning_trace_id = _snapshot_id,

            # Screenshot
            screenshot = _screenshot,

            # Session development telemetry
            ny_open_minutes  = _ny_open_minutes,
            ib_window_closed = bool(session_ctx.get('ib_window_closed', False)),
        )
        # Push to Render — fire-and-forget, never blocks the monitor cycle
        _push_feed_entry(_signal_entry, _snapshot_entry)
    except Exception as _sle:
        print(f'[signal_log] log error: {_sle}')

    alert = decision_to_alert(decision, symbol)
    _fire_decision_snapshot(
        _mcp_snap,
        pros_eval=pros_eval, orb_eval=orb_eval, ib_eval=ib_eval,
        pre_signal=signal_type, pre_setup=setup_type, pre_rationale=rationale or '',
        decision=decision, claude_called=True, alert_generated=(alert is not None),
    )
    return [alert] if alert else []


def _safe_float(val) -> Optional[float]:
    """Parse a float from a string or number, return None on failure."""
    try:
        return float(val) if val not in (None, '', '—') else None
    except (TypeError, ValueError):
        return None


# ── Draw Validation Telemetry ──────────────────────────────────────────────────

def _parse_tp1_price(tp1_str: str) -> Optional[float]:
    """Extract the first numeric price value from Claude's TP1 string."""
    import re
    if not tp1_str:
        return None
    matches = re.findall(r'\d{3,}(?:\.\d+)?', tp1_str)  # 3+ digits = price, not fib level
    if matches:
        return _safe_float(matches[0])
    return None


# Sessions where the NY IB window is confirmed closed (10:30 ET has passed)
_IB_CONFIRMED_SESSIONS = {'NY_AM', 'NY_PM', 'NEW_YORK_CASH'}

# Keywords in Claude's named draw that indicate a strong, pre-existing draw
_STRONG_DRAW_KEYWORDS = ('PDL', 'PDH', 'PRIOR DAY', 'PREV DAY', 'WEEK', 'MONTH',
                         'EQUAL HIGH', 'EQUAL LOW', 'EQL', 'SWING HIGH', 'SWING LOW')

# TP1 distance below which the draw is classified as collapsed / circular
_TP1_COLLAPSE_PTS = 3.0


def _classify_draw(
    price:          Optional[float],
    tp1_str:        str,
    ib_draw:        str,
    ib_draw_claude: str,
    session:        str,
) -> dict:
    """
    Classify the draw independence for Draw Validation telemetry.

    Returns draw_name, draw_category (STRONG / CONDITIONAL / CIRCULAR),
    draw_tp1_pts, and draw_independent. Logged only — never used as an
    execution gate. See nova_knowledge_core/PROS_EVAN_INVESTING/draw_validation.md.
    """
    draw_name = ib_draw_claude or ib_draw or 'UNKNOWN'
    tp1_price = _parse_tp1_price(tp1_str)

    draw_tp1_pts: Optional[float] = None
    if tp1_price is not None and price:
        try:
            draw_tp1_pts = round(abs(float(tp1_price) - float(price)), 2)
        except (TypeError, ValueError):
            pass

    # Rule 1: TP1 collapse → CIRCULAR regardless of draw label
    if draw_tp1_pts is not None and draw_tp1_pts < _TP1_COLLAPSE_PTS:
        return {
            'draw_name':       draw_name,
            'draw_category':   'CIRCULAR',
            'draw_tp1_pts':    draw_tp1_pts,
            'draw_independent': False,
        }

    # Rule 2: Named draw contains prior-session / structural keywords → STRONG
    named_upper = (ib_draw_claude or '').upper()
    if any(kw in named_upper for kw in _STRONG_DRAW_KEYWORDS):
        return {
            'draw_name':       draw_name,
            'draw_category':   'STRONG',
            'draw_tp1_pts':    draw_tp1_pts,
            'draw_independent': True,
        }

    # Rule 3: IB draw after IB window has closed → STRONG
    if ib_draw in ('IB HIGH', 'IB LOW') and session in _IB_CONFIRMED_SESSIONS:
        return {
            'draw_name':       draw_name,
            'draw_category':   'STRONG',
            'draw_tp1_pts':    draw_tp1_pts,
            'draw_independent': True,
        }

    # Rule 4: IB draw while IB is still forming (NY_OPEN) → CONDITIONAL
    if ib_draw in ('IB HIGH', 'IB LOW') and session == 'NY_OPEN':
        return {
            'draw_name':       draw_name,
            'draw_category':   'CONDITIONAL',
            'draw_tp1_pts':    draw_tp1_pts,
            'draw_independent': True,
        }

    # Default: CONDITIONAL — something is named but cannot be confirmed strong
    return {
        'draw_name':       draw_name,
        'draw_category':   'CONDITIONAL',
        'draw_tp1_pts':    draw_tp1_pts,
        'draw_independent': draw_tp1_pts is None or draw_tp1_pts >= _TP1_COLLAPSE_PTS,
    }


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
    orb_table       = nova_state.get('orb', {})

    mcp_health = compute_mcp_health(chart_ctx, nova_state)

    # Run all deterministic evaluators
    pros_eval      = _evaluate_pros_phase(main_state, pros_state_data, chart_ctx)
    orb_eval       = _evaluate_orb_phase(main_state, chart_ctx, session_ctx, orb_table)
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

    momentum_eval = {}
    if _compute_momentum:
        try:
            momentum_eval = _compute_momentum(symbol, ote_eval=price_ote_eval)
        except Exception:
            pass

    # Classify first — family must be known before DP can be computed
    signal_type, setup_type, rationale = _classify_signal(
        pros_eval, orb_eval, ib_eval, inv_eval, session_ctx, price_ote_eval
    )

    # Derive active family from classification — gates which DP scorers run
    _active_family = setup_type.split('_')[0].upper() if '_' in setup_type else ''

    dir_pressure = {}
    if _dp_engine:
        try:
            dir_pressure = _dp_engine.compute(
                pros_eval, ib_eval, session_ctx, mem_summary,
                momentum_eval=momentum_eval or None,
                orb_eval=orb_eval or None,
                active_family=_active_family,
            )
        except Exception:
            pass

    signal_type, setup_type, rationale = _apply_market_reality_gate(
        signal_type, setup_type, rationale
    )
    signal_type, setup_type, rationale = _apply_conviction_gate(
        signal_type, setup_type, rationale, dir_pressure
    )

    # Tier 1 family isolation: Claude sees only the responsible strategy family.
    # _active_family was derived from setup_type before any gate modification.
    if _active_family == 'ORB':
        _pros_for_claude, _orb_for_claude = {}, orb_eval
    elif _active_family == 'PROS':
        _pros_for_claude, _orb_for_claude = pros_eval, {}
    else:
        _pros_for_claude, _orb_for_claude = pros_eval, orb_eval

    pre_assess = {
        'pros_eval':      _pros_for_claude,
        'orb_eval':       _orb_for_claude,
        'ib_eval':        ib_eval,
        'inv_eval':       inv_eval,
        'price_ote_eval': price_ote_eval,
        'dir_pressure':   dir_pressure,
        'momentum_eval':  momentum_eval,
        'pre_signal':     signal_type,
        'pre_setup':      setup_type,
        'rationale':      rationale,
    }

    decision = evaluate_with_claude(nova_state, session_ctx, chart_ctx, pre_assess) or {}

    _mr2_snap_debug: dict = {}
    if _load_mr2:
        try:
            _mr2_snap_debug = _load_mr2()
        except Exception:
            pass

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
                mr2_state       = _mr2_snap_debug,
                momentum_eval   = momentum_eval,
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
        'bridge_v2':      nova_state.get('bridge_v2',   {}),
        'bridge_meta':    nova_state.get('bridge_meta', {}),
        'mcp_health':     mcp_health,
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
