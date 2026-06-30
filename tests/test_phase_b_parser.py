"""
test_phase_b_parser.py — Phase B Parser Hardening smoke tests.

Covers:
  1. BRIDGE_V2 healthy parse          — parser_mode=BRIDGE_V2, parse_status=ok
  2. BRIDGE_V1 fallback               — parser_mode=BRIDGE_V1, parse_status=version_mismatch
  3. Legacy three-table parse          — parser_mode=LEGACY_TABLES, parse_status=legacy_fallback
  4. Missing required fields           — parse_status=required_fields_missing
  5. Wrong bridge version (explicit 1) — parser_mode=BRIDGE_V1
  6. No tables at all                  — parser_mode=NO_BRIDGE, parse_status=bridge_missing
  7. Tables with no recognized header  — parser_mode=NO_BRIDGE, parse_status=unreadable
  8. Parser exception safety           — parser_mode=UNREADABLE, parse_status=parser_exception
  9. parser_mode propagates to mcp_health
 10. ticker_match field populated correctly
 11. timeframe_match field populated correctly
 12. Field completeness lists in bridge_meta

Run:  python tests/test_phase_b_parser.py
      python -m pytest tests/test_phase_b_parser.py -v
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from engines.reasoning import parse_nova_tables, compute_mcp_health, _MCP_REQUIRED_V2, _MCP_OPTIONAL_V2

# ── helpers ───────────────────────────────────────────────────────────────────

def _v2_rows(ticker='MES1!', bridge_ver='2', **overrides) -> list[str]:
    base = {
        'CMD': 'WAIT', 'SYS_STATE': 'READING MARKET', 'SCORE': 'B 0 / S 48',
        'CONF': 'LOW 44%', 'PROS_ENG': 'BUILDING', 'P_DISPL': 'BULL',
        'P_RETRACE': 'TOO DEEP', 'P_OTE': 'DEEP', 'P_CONT': 'BUILDING',
        'P_QUALITY': 'GOOD', 'P_STDV': 'NORMAL',
        'IB H': '7489.75', 'IB L': '7409',
        'O_STATE': 'ORB_EXPIRED', 'O_BIAS': 'BULL DEAD', 'O_TYPE': 'EDGE DFND',
        'O_REJ_Q': '3 EDGE', 'O_HIGH': '7467.75', 'O_MID': '7464.5', 'O_LOW': '7461.25',
        'BRIDGE_VER': bridge_ver, 'TICKER': ticker, 'TF': '1', 'IB_STATUS': 'COMPLETE',
        'SESSION': 'NY_CASH', 'ORB_ACTIVE': '0', 'PROS_ACTIVE': '1',
        'COOLDOWN': '0', 'TRAP': '0', 'ICT_STEP': '1',
        'PEER_ALIGN': 'CONFIRM', 'DRAW_TARGET': '7560.00', 'DRAW_DIR': 'UP',
    }
    base.update(overrides)
    rows = ['NOVA BRIDGE']
    for k, v in base.items():
        rows.append(f'{k} | {v}')
    return rows

def _ctx(symbol='CME_MINI:MES1!', timeframe='1', tables=None) -> dict:
    ctx = {'connected': True, 'symbol': symbol, 'timeframe': timeframe}
    if tables is not None:
        ctx['nova_tables'] = tables
    return ctx


# ── Test 1: full v2 healthy parse ─────────────────────────────────────────────

def test_bridge_v2_healthy_parse():
    s = parse_nova_tables([_v2_rows()])
    assert s['parser_mode']  == 'BRIDGE_V2',  f"got {s['parser_mode']}"
    assert s['parse_status'] == 'ok',         f"got {s['parse_status']}"
    bm = s['bridge_meta']
    assert bm['parser_mode']             == 'BRIDGE_V2'
    assert bm['parse_status']            == 'ok'
    assert bm['bridge_v2_detected']      is True
    assert bm['expected_bridge_version'] == 2
    assert bm['required_fields_missing'] == []
    assert bm['optional_fields_missing'] == []
    assert bm['total_bridge_fields_expected'] == 13
    assert bm['total_bridge_fields_present']  == 13
    # main/pros/orb populated
    assert s['main']['CMD'] == 'WAIT'
    assert s['pros']['DISPL'] == 'BULL'
    assert s['orb']['STATE'] == 'ORB_EXPIRED'


# ── Test 2: BRIDGE_V1 (no BRIDGE_VER row) ────────────────────────────────────

def test_bridge_v1_fallback():
    v1_rows = [
        'NOVA BRIDGE', 'CMD | BUY', 'SYS_STATE | ELITE ICT LONG',
        'SCORE | B 72 / S 10', 'CONF | HIGH 81%', 'PROS_ENG | CONTINUATION',
        'P_DISPL | BULL', 'P_RETRACE | OTE', 'P_OTE | TAGGED',
        'P_CONT | CONFIRMED', 'P_QUALITY | ELITE', 'P_STDV | NORMAL',
        'IB H | 21487.25', 'IB L | 21340.50',
        'O_STATE | ORB_READY', 'O_BIAS | BULL', 'O_TYPE | MID_REJECT',
        'O_REJ_Q | ELITE', 'O_HIGH | 21510.00', 'O_MID | 21425.50', 'O_LOW | 21341.00',
    ]
    s = parse_nova_tables([v1_rows])
    assert s['parser_mode']  == 'BRIDGE_V1',         f"got {s['parser_mode']}"
    assert s['parse_status'] == 'version_mismatch',  f"got {s['parse_status']}"
    bm = s['bridge_meta']
    assert bm['bridge_v2_detected']   is False
    assert bm['bridge_version']       == 1
    assert bm['expected_bridge_version'] == 2


# ── Test 3: legacy three-table ────────────────────────────────────────────────

def test_legacy_three_table_parse():
    tables = [
        ['NOVA ENGINE', 'CMD | SELL', 'STATE | BEAR TREND'],
        ['PROS ENGINE', 'DISPL | BEAR', 'RETRACE | MID'],
        ['ORB CONSOLE', 'STATE | ORB_FAILED', 'BIAS | BEAR'],
    ]
    s = parse_nova_tables(tables)
    assert s['parser_mode']  == 'LEGACY_TABLES',  f"got {s['parser_mode']}"
    assert s['parse_status'] == 'legacy_fallback', f"got {s['parse_status']}"
    assert 'bridge_meta' not in s
    assert s['main'].get('CMD') == 'SELL'
    assert s['pros'].get('DISPL') == 'BEAR'
    assert s['orb'].get('STATE') == 'ORB_FAILED'


# ── Test 4: v2 with required fields missing ───────────────────────────────────

def test_missing_required_fields():
    rows = _v2_rows()
    rows = [r for r in rows if not r.startswith('ICT_STEP') and not r.startswith('TRAP')]
    s = parse_nova_tables([rows])
    assert s['parser_mode']  == 'BRIDGE_V2',               f"got {s['parser_mode']}"
    assert s['parse_status'] == 'required_fields_missing', f"got {s['parse_status']}"
    bm = s['bridge_meta']
    assert 'ICT_STEP' in bm['required_fields_missing']
    assert 'TRAP'     in bm['required_fields_missing']
    assert bm['total_bridge_fields_present'] == 11


# ── Test 5: explicit BRIDGE_VER=1 ────────────────────────────────────────────

def test_explicit_bridge_ver_1():
    rows = _v2_rows(bridge_ver='1')
    s = parse_nova_tables([rows])
    assert s['parser_mode']  == 'BRIDGE_V1',        f"got {s['parser_mode']}"
    assert s['parse_status'] == 'version_mismatch', f"got {s['parse_status']}"
    assert s['bridge_meta']['bridge_version'] == 1


# ── Test 6: no tables at all ─────────────────────────────────────────────────

def test_no_tables_bridge_missing():
    s = parse_nova_tables([])
    assert s['parser_mode']  == 'NO_BRIDGE',      f"got {s['parser_mode']}"
    assert s['parse_status'] == 'bridge_missing', f"got {s['parse_status']}"
    assert 'bridge_meta' not in s


# ── Test 7: tables with no recognized header ──────────────────────────────────

def test_unrecognized_headers_unreadable():
    s = parse_nova_tables([['RANDOM TABLE', 'FOO | BAR'], ['ANOTHER | VALUE']])
    assert s['parser_mode']  == 'NO_BRIDGE', f"got {s['parser_mode']}"
    assert s['parse_status'] == 'unreadable', f"got {s['parse_status']}"


# ── Test 8: parser exception safety ──────────────────────────────────────────

def test_parser_exception_safety():
    # Pass something that is not a list[list[str]] — should be caught
    s = parse_nova_tables(None)  # type: ignore
    assert s['parser_mode']  == 'UNREADABLE',       f"got {s['parser_mode']}"
    assert s['parse_status'] == 'parser_exception', f"got {s['parse_status']}"
    assert s['main'] == {}


# ── Test 9: parser_mode propagates to mcp_health ─────────────────────────────

def test_parser_mode_propagates_to_mcp_health():
    rows = _v2_rows()
    ctx  = _ctx(tables=[rows])
    nova = parse_nova_tables(ctx['nova_tables'])
    h    = compute_mcp_health(ctx, nova)
    assert h['parser_mode']  == 'BRIDGE_V2', f"got {h['parser_mode']}"
    assert h['parse_status'] == 'ok',        f"got {h['parse_status']}"
    assert h['status'] == 'HEALTHY'

    # Legacy path: parser_mode=LEGACY_TABLES
    legacy_ctx = _ctx(tables=[
        ['NOVA ENGINE', 'CMD | SELL'],
        ['PROS ENGINE', 'DISPL | BEAR'],
    ])
    nova_leg = parse_nova_tables(legacy_ctx['nova_tables'])
    h_leg    = compute_mcp_health(legacy_ctx, nova_leg)
    assert h_leg['parser_mode']  == 'LEGACY_TABLES'
    assert h_leg['parse_status'] == 'legacy_fallback'
    assert h_leg['status']       == 'BROKEN'   # bridge_meta absent → confidence=30


# ── Test 10: ticker_match field ───────────────────────────────────────────────

def test_ticker_match_field():
    # Matching ticker
    ctx   = _ctx(symbol='CME_MINI:MES1!', tables=[_v2_rows(ticker='MES1!')])
    nova  = parse_nova_tables(ctx['nova_tables'])
    h     = compute_mcp_health(ctx, nova)
    assert h['ticker_match'] is True, f"expected True, got {h['ticker_match']}"
    assert h['chart_symbol'] == 'CME_MINI:MES1!'

    # Mismatched ticker
    ctx2  = _ctx(symbol='CME_MINI:MES1!', tables=[_v2_rows(ticker='MNQ1!')])
    nova2 = parse_nova_tables(ctx2['nova_tables'])
    h2    = compute_mcp_health(ctx2, nova2)
    assert h2['ticker_match'] is False
    assert h2['confidence']   <= 30
    assert h2['status']       == 'BROKEN'


# ── Test 11: timeframe_match field ───────────────────────────────────────────

def test_timeframe_match_field():
    ctx  = _ctx(timeframe='1', tables=[_v2_rows()])
    nova = parse_nova_tables(ctx['nova_tables'])
    h    = compute_mcp_health(ctx, nova)
    assert h['timeframe_match']  is True,  f"got {h['timeframe_match']}"
    assert h['chart_timeframe']  == '1'

    # TF mismatch: chart says 5-minute, bridge says 1-minute
    ctx2  = _ctx(timeframe='5', tables=[_v2_rows()])
    nova2 = parse_nova_tables(ctx2['nova_tables'])
    h2    = compute_mcp_health(ctx2, nova2)
    assert h2['timeframe_match'] is False


# ── Test 12: field completeness lists ────────────────────────────────────────

def test_field_completeness_lists():
    rows = _v2_rows()
    rows = [r for r in rows if not r.startswith('ICT_STEP')]
    s    = parse_nova_tables([rows])
    bm   = s['bridge_meta']
    assert 'ICT_STEP' in bm['required_fields_missing']
    assert 'ICT_STEP' not in bm['required_fields_present']
    assert set(bm['optional_fields_missing']) <= _MCP_OPTIONAL_V2
    assert set(bm['optional_fields_present']) <= _MCP_OPTIONAL_V2
    # Every required key appears in exactly one list
    all_req = set(bm['required_fields_present']) | set(bm['required_fields_missing'])
    assert all_req == _MCP_REQUIRED_V2


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [(k, v) for k, v in globals().items() if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f'PASS  {name}')
            passed += 1
        except AssertionError as e:
            print(f'FAIL  {name}: {e}')
            failed += 1
        except Exception as e:
            print(f'ERROR {name}: {e}')
            failed += 1
    print(f'\n{passed}/{passed + failed} passed')
    import sys as _sys
    _sys.exit(1 if failed else 0)
