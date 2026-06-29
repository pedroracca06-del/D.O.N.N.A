"""
test_mcp_health.py — smoke tests for compute_mcp_health()

Covers all six scoring branches:
  0   Not connected
  30  Connected but bridge missing
  50  Legacy v1 bridge
  70  v2 bridge with one required field absent
  85  v2 bridge with optional fields absent
  100 Full v2 bridge, all fields present

Run: python -m pytest tests/test_mcp_health.py -v
     python tests/test_mcp_health.py
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from engines.reasoning import compute_mcp_health, parse_nova_tables

# ── helpers ──────────────────────────────────────────────────────────────────

def _connected_ctx(symbol: str = 'CME_MINI:MES1!', tables=None) -> dict:
    ctx: dict = {'connected': True, 'symbol': symbol}
    if tables is not None:
        ctx['nova_tables'] = tables
    return ctx

def _v2_rows(ticker='MES1!', **overrides) -> list[str]:
    """Build a full 34-row NOVA BRIDGE v2 table as string rows."""
    base = {
        'CMD': 'WAIT', 'SYS_STATE': 'READING MARKET', 'SCORE': 'B 0 / S 48',
        'CONF': 'LOW 44%', 'PROS_ENG': 'BUILDING', 'P_DISPL': 'BULL',
        'P_RETRACE': 'TOO DEEP', 'P_OTE': 'DEEP', 'P_CONT': 'BUILDING',
        'P_QUALITY': 'GOOD', 'P_STDV': 'NORMAL',
        'IB H': '7489.75', 'IB L': '7409',
        'O_STATE': 'ORB_EXPIRED', 'O_BIAS': 'BULL DEAD', 'O_TYPE': 'EDGE DFND',
        'O_REJ_Q': '3 EDGE', 'O_HIGH': '7467.75', 'O_MID': '7464.5', 'O_LOW': '7461.25',
        'BRIDGE_VER': '2', 'TICKER': ticker, 'TF': '1', 'IB_STATUS': 'COMPLETE',
        'SESSION': 'NY_CASH', 'ORB_ACTIVE': '0', 'PROS_ACTIVE': '1',
        'COOLDOWN': '0', 'TRAP': '0', 'ICT_STEP': '1',
        'PEER_ALIGN': 'CONFIRM', 'DRAW_TARGET': '—', 'DRAW_DIR': 'NONE',
    }
    base.update(overrides)
    rows = ['NOVA BRIDGE']
    for k, v in base.items():
        rows.append(f'{k} | {v}')
    return rows


# ── Case 0: not connected ─────────────────────────────────────────────────────

def test_not_connected_returns_0():
    h = compute_mcp_health({'connected': False}, {})
    assert h['status']     == 'BROKEN'
    assert h['confidence'] == 0
    assert any('not reachable' in e for e in h['errors'])


# ── Case 1: bridge missing ────────────────────────────────────────────────────

def test_no_tables_returns_30():
    ctx = _connected_ctx(tables=[])
    h = compute_mcp_health(ctx, {})
    assert h['status']     == 'BROKEN'
    assert h['confidence'] == 30
    assert h['bridge_v2_detected'] is False

def test_tables_but_no_bridge_header_returns_30():
    ctx = _connected_ctx(tables=[['CMD | BUY', 'STATE | SOME STATE']])
    nova_state = parse_nova_tables(ctx['nova_tables'])
    h = compute_mcp_health(ctx, nova_state)
    assert h['confidence'] == 30
    assert h['status'] == 'BROKEN'


# ── Case 2: legacy v1 bridge ─────────────────────────────────────────────────

def test_v1_bridge_returns_50_degraded():
    v1_rows = [
        'NOVA BRIDGE', 'CMD | BUY', 'SYS_STATE | ELITE ICT LONG',
        'SCORE | B 72 / S 10', 'CONF | HIGH 81%', 'PROS_ENG | CONTINUATION',
        'P_DISPL | BULL', 'P_RETRACE | OTE', 'P_OTE | TAGGED',
        'P_CONT | CONFIRMED', 'P_QUALITY | ELITE', 'P_STDV | NORMAL',
        'IB H | 21487.25', 'IB L | 21340.50',
        'O_STATE | ORB_READY', 'O_BIAS | BULL', 'O_TYPE | MID_REJECT',
        'O_REJ_Q | ELITE', 'O_HIGH | 21510.00', 'O_MID | 21425.50', 'O_LOW | 21341.00',
        # No BRIDGE_VER row
    ]
    ctx = _connected_ctx(tables=[v1_rows])
    nova_state = parse_nova_tables(ctx['nova_tables'])
    h = compute_mcp_health(ctx, nova_state)
    assert h['confidence']         == 50
    assert h['status']             == 'DEGRADED'
    assert h['bridge_v2_detected'] is False
    assert h['bridge_version']     == 1
    assert any('Legacy' in w for w in h['warnings'])


# ── Case 3: v2 bridge with one required field missing ────────────────────────

def test_v2_one_required_missing_returns_70():
    rows = _v2_rows()
    # Remove ICT_STEP (required)
    rows = [r for r in rows if not r.startswith('ICT_STEP')]
    ctx = _connected_ctx(tables=[rows])
    nova_state = parse_nova_tables(ctx['nova_tables'])
    h = compute_mcp_health(ctx, nova_state)
    assert h['confidence'] == 70
    assert h['status']     == 'DEGRADED'
    assert 'ICT_STEP' in h['fields_missing']
    assert any('ICT_STEP' in w for w in h['warnings'])


# ── Case 4: v2 bridge with only optional fields missing ──────────────────────

def test_v2_optional_missing_returns_85():
    # DRAW_TARGET and DRAW_DIR already '—' in base, so missing_opt > 0
    rows = _v2_rows(DRAW_TARGET='—', DRAW_DIR='—')
    ctx = _connected_ctx(tables=[rows])
    nova_state = parse_nova_tables(ctx['nova_tables'])
    h = compute_mcp_health(ctx, nova_state)
    assert h['confidence']         == 85
    assert h['status']             == 'HEALTHY'
    assert h['bridge_v2_detected'] is True

def test_v2_no_optional_present_draw_dir_present():
    # DRAW_TARGET still '—', DRAW_DIR present → still 85 (one optional missing)
    rows = _v2_rows(DRAW_TARGET='—', DRAW_DIR='UP')
    ctx = _connected_ctx(tables=[rows])
    nova_state = parse_nova_tables(ctx['nova_tables'])
    h = compute_mcp_health(ctx, nova_state)
    assert h['confidence'] == 85
    assert h['status'] == 'HEALTHY'


# ── Case 5: full v2 bridge, all fields present ───────────────────────────────

def test_full_v2_returns_100():
    rows = _v2_rows(DRAW_TARGET='21560.00', DRAW_DIR='UP')
    ctx = _connected_ctx(tables=[rows])
    nova_state = parse_nova_tables(ctx['nova_tables'])
    h = compute_mcp_health(ctx, nova_state)
    assert h['confidence']         == 100
    assert h['status']             == 'HEALTHY'
    assert h['bridge_v2_detected'] is True
    assert h['ticker']             == 'MES1!'
    assert h['timeframe']          == '1'
    assert h['session']            == 'NY_CASH'
    assert h['fields_present']     == 13
    assert h['fields_missing']     == []
    assert h['warnings']           == []
    assert h['errors']             == []


# ── Case 6: symbol mismatch ───────────────────────────────────────────────────

def test_symbol_mismatch_caps_confidence_at_30():
    rows = _v2_rows(ticker='MNQ1!', DRAW_TARGET='21560.00', DRAW_DIR='UP')
    ctx = _connected_ctx(symbol='CME_MINI:MES1!', tables=[rows])
    nova_state = parse_nova_tables(ctx['nova_tables'])
    h = compute_mcp_health(ctx, nova_state)
    assert h['confidence'] <= 30
    assert h['status']     == 'BROKEN'
    assert any('mismatch' in e for e in h['errors'])


# ── Case 7: v2 with two required fields missing ───────────────────────────────

def test_v2_two_required_missing_degrades_below_70():
    rows = _v2_rows()
    rows = [r for r in rows if not r.startswith('ICT_STEP') and not r.startswith('TRAP')]
    ctx = _connected_ctx(tables=[rows])
    nova_state = parse_nova_tables(ctx['nova_tables'])
    h = compute_mcp_health(ctx, nova_state)
    assert h['confidence'] < 70
    assert h['status'] in ('DEGRADED', 'BROKEN')


# ── Legacy three-table format ─────────────────────────────────────────────────

def test_legacy_three_table_returns_30():
    legacy = [
        ['NOVA ENGINE', 'CMD | SELL', 'STATE | BEAR TREND'],
        ['PROS ENGINE', 'DISPL | BEAR', 'RETRACE | MID'],
        ['ORB CONSOLE', 'STATE | ORB_FAILED', 'BIAS | BEAR'],
    ]
    ctx = _connected_ctx(tables=legacy)
    nova_state = parse_nova_tables(ctx['nova_tables'])
    # Legacy three-table has no 'bridge_meta' → bridge_found=False → 30
    h = compute_mcp_health(ctx, nova_state)
    assert h['confidence'] == 30
    assert h['status'] == 'BROKEN'


# ── Runner for plain python execution ────────────────────────────────────────

if __name__ == '__main__':
    import inspect
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
    sys.exit(1 if failed else 0)
