"""
test_replay_dashboard.py — NOVA Replay dashboard UI smoke tests.

Covers:
  1.  NOVA REPLAY tab button present in HTML
  2.  page-replay div present
  3.  All required DOM element IDs present
  4.  All required JS functions present
  5.  Replay tab handler wired in tab switch code
  6.  Filter selects present (symbol, conclusion, confidence)
  7.  No forbidden keys (win_rate, avg_r, expected_value, hit_rate) in replay JS
  8.  No execution/mutation buttons in replay page HTML
  9.  Empty state text present (no crash on empty data)
 10.  Replay endpoints are referenced in JS fetch calls
 11.  Conclusion label function covers all Phase I labels
 12.  CSS classes referenced in JS are defined in the style block
 13.  No \\' escape sequences introduced in new replay JS block

Run:  python tests/test_replay_dashboard.py
      python -m pytest tests/test_replay_dashboard.py -v
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from ui.html import DASHBOARD_HTML

HTML = DASHBOARD_HTML

# Isolate the replay JS block (from the NOVA REPLAY comment to end of script)
_REPLAY_JS_START = HTML.find('// ════════ NOVA REPLAY ════════')
assert _REPLAY_JS_START > 0, 'Replay JS block not found in HTML'
_REPLAY_JS = HTML[_REPLAY_JS_START:]

_REPLAY_PAGE_START = HTML.find('id="page-replay"')
assert _REPLAY_PAGE_START > 0, 'page-replay div not found'
_REPLAY_PAGE_END   = HTML.find('</div><!-- /page-replay -->')
_REPLAY_PAGE_HTML  = HTML[_REPLAY_PAGE_START:_REPLAY_PAGE_END]

_FORBIDDEN = frozenset({'win_rate', 'avg_r', 'expected_value', 'hit_rate'})


def test_tab_button_present():
    assert 'data-page="replay"' in HTML
    assert 'NOVA REPLAY' in HTML


def test_page_div_present():
    assert 'id="page-replay"' in HTML
    assert '</div><!-- /page-replay -->' in HTML


def test_required_dom_ids_present():
    required_ids = [
        'rpLatestCard',
        'rpSimilarPanel',
        'rpTblHead',
        'rpTblBody',
        'rpTableEmpty',
        'rpfSymbol',
        'rpfConclusion',
        'rpfConfidence',
    ]
    missing = [eid for eid in required_ids if f'id="{eid}"' not in HTML]
    assert not missing, f'Missing DOM IDs: {missing}'


def test_required_js_functions_present():
    required_fns = [
        'async function refreshReplay()',
        'function rpApplyFilters()',
        'function _rpConclLabel(',
        'function _rpConclClass(',
        'function _rpFmt(',
        'function _rpTs(',
        'function _rpRenderLatestCard(',
        'function _rpRenderTable(',
        'function _rpRenderSimilar(',
    ]
    missing = [fn for fn in required_fns if fn not in _REPLAY_JS]
    assert not missing, f'Missing JS functions: {missing}'


def test_tab_switch_handler_wired():
    assert "btn.dataset.page === 'replay'" in HTML
    assert 'refreshReplay()' in HTML


def test_filter_selects_present():
    assert 'id="rpfSymbol"' in _REPLAY_PAGE_HTML
    assert 'id="rpfConclusion"' in _REPLAY_PAGE_HTML
    assert 'id="rpfConfidence"' in _REPLAY_PAGE_HTML
    assert 'onchange="rpApplyFilters()"' in _REPLAY_PAGE_HTML


def test_no_forbidden_keys_in_replay_js():
    for k in _FORBIDDEN:
        assert k not in _REPLAY_JS, f'Forbidden key "{k}" found in replay JS'


def test_no_execution_buttons_in_replay_page():
    # Ensure no trading action buttons are in the replay page HTML
    forbidden_patterns = [
        'EXECUTE',
        'PLACE ORDER',
        'BUY',
        'SELL',
        '/api/execution',
        '/api/broker',
    ]
    for pat in forbidden_patterns:
        assert pat not in _REPLAY_PAGE_HTML, f'Execution pattern "{pat}" found in replay page'


def test_empty_state_text_present():
    # Empty / no-data messages must exist in JS (rendered when arrays are empty)
    assert 'No replay data yet' in _REPLAY_JS or 'No replay data yet' in _REPLAY_PAGE_HTML
    assert 'No similar historical' in _REPLAY_JS


def test_endpoints_referenced_in_js():
    required_endpoints = [
        '/api/mcp-replay/post-trade-reviews',
        '/api/mcp-replay/similar-with-outcomes',
    ]
    for ep in required_endpoints:
        assert ep in _REPLAY_JS, f'Endpoint "{ep}" not found in replay JS'


def test_conclusion_labels_cover_all_phase_i_labels():
    required_labels = [
        'GOOD_READ_GOOD_DECISION',
        'GOOD_READ_BAD_DECISION',
        'NO_TRADE_REVIEW_ONLY',
        'NO_TRADE_CONFIRMED_CORRECT',
        'MISSED_OPPORTUNITY',
        'INSUFFICIENT_DATA',
    ]
    missing = [lbl for lbl in required_labels if lbl not in _REPLAY_JS]
    assert not missing, f'Missing conclusion labels in replay JS: {missing}'


def test_css_classes_defined():
    required_css = [
        '.rp-card{',
        '.rp-tbl{',
        '.rp-concl{',
        '.rp-lesson{',
        '.rp-badge{',
        '.rp-concl-good{',
        '.rp-concl-bad{',
        '.rp-concl-skip{',
        '.rp-concl-missed{',
        '.rp-concl-insuf{',
    ]
    missing = [cls for cls in required_css if cls not in HTML]
    assert not missing, f'Missing CSS classes: {missing}'


def test_no_backslash_quote_in_replay_js():
    # Confirm no \\' sequences were introduced in the new replay JS block
    # (these can corrupt JS inside Python triple-quoted strings)
    assert "\\'" not in _REPLAY_JS, "Found \\' escape sequence in replay JS block — use ' directly"


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [
        ('Tab button present',                      test_tab_button_present),
        ('page-replay div present',                 test_page_div_present),
        ('Required DOM IDs present',                test_required_dom_ids_present),
        ('Required JS functions present',           test_required_js_functions_present),
        ('Tab switch handler wired',                test_tab_switch_handler_wired),
        ('Filter selects present',                  test_filter_selects_present),
        ('No forbidden keys in replay JS',          test_no_forbidden_keys_in_replay_js),
        ('No execution buttons in replay page',     test_no_execution_buttons_in_replay_page),
        ('Empty state text present',                test_empty_state_text_present),
        ('Endpoints referenced in JS',              test_endpoints_referenced_in_js),
        ('Conclusion labels cover all Phase I',     test_conclusion_labels_cover_all_phase_i_labels),
        ('CSS classes defined',                     test_css_classes_defined),
        ('No backslash-quote in replay JS',         test_no_backslash_quote_in_replay_js),
    ]

    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f'  PASS  {name}')
            passed += 1
        except Exception as exc:
            print(f'  FAIL  {name}: {exc}')
            failed += 1

    status = 'OK' if not failed else 'FAIL'
    print(f'\n{passed}/{passed + failed} tests passed [{status}]')
    if failed:
        raise SystemExit(1)
