"""
test_nova_review.py — Journal "NOVA Review" (AI trade analysis) regression tests.

Context: NOVA Review is the per-trade AI analysis feature in the Journal tab
(the "Generate NOVA Review" button on trade cards / trade-detail modal) — it
is NOT the NOVA REPLAY tab (covered separately by test_replay_dashboard.py).
It calls POST /journal/analyze (main.py), which hits the Claude API via
core.config.client.

Root-cause audit found the account's Anthropic credit balance was too low,
so every generation attempt failed with a 400 from Anthropic's API — and the
frontend's generateAnalysis() JS silently swallowed that failure with zero
visible error, indistinguishable from "does nothing" (a real, separate bug
from the billing issue itself, which is an account matter, not a code fix).
This file locks in: (a) the backend already returns/raises a usable error
message on every failure path, and (b) the frontend now surfaces it.

Covers:
  1.  /journal/analyze returns valid JSON {'status':'ok', ...} on success
  2.  /journal/analyze returns a usable message when Claude client unconfigured
  3.  /journal/analyze raises HTTPException(500) with a usable detail on Claude API error
  4.  /journal/analyze raises HTTPException(400) on invalid trade index
  5.  /journal/analyze does not crash on a trade record missing most fields
  6.  Frontend: _novaReviewError() toast helper is defined
  7.  Frontend: generateAnalysis() calls the error helper on failure branches
  8.  Frontend: generateAnalysis() checks res.ok (HTTP status), not just data.status
  9.  Frontend: no \\' escape sequence introduced in the new JS block

Run:  python tests/test_nova_review.py
      python -m pytest tests/test_nova_review.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('ALPACA_API_KEY', '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

import main
from ui.html import DASHBOARD_HTML

_JS_START = DASHBOARD_HTML.find('function _novaReviewError')
assert _JS_START > 0, '_novaReviewError helper not found in DASHBOARD_HTML'
_JS_END = DASHBOARD_HTML.find('function toggleReview')
assert _JS_END > _JS_START, 'toggleReview() not found after _novaReviewError()'
_JS_BLOCK = DASHBOARD_HTML[_JS_START:_JS_END]


class _FakeRequest:
    """Duck-types starlette.requests.Request for the one method journal_analyze() calls."""
    def __init__(self, body: dict):
        self._body = body

    async def json(self):
        return self._body


def _valid_trade(**overrides) -> dict:
    trade = {
        'ticker': 'MES1!', 'direction': 'LONG', 'setup_type': 'PROS_CONTINUATION',
        'entry_price': 6000.0, 'exit_price': 6010.0, 'stop': 5990.0, 'tp1': 6020.0,
        'size': 1, 'rr': 2.0, 'realized_pnl': 100.0, 'outcome': 'WIN',
        'session': 'NY_AM', 'macro_risk': 'low', 'notes': '', 'emotional_state': '',
        'behavioral_flags': [], 'reflection': '',
    }
    trade.update(overrides)
    return trade


def _mock_claude_response(text: str):
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


# ── Backend: /journal/analyze ──────────────────────────────────────────────

def test_analyze_returns_ok_json_on_success():
    trade = _valid_trade()
    with patch.object(main, 'load_journal', return_value=[trade]), \
         patch.object(main, 'save_journal') as mock_save, \
         patch('core.config.client') as mock_client:
        mock_client.messages.create.return_value = _mock_claude_response('QUALIFICATION\nGood setup.')
        result = asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))

    assert result['status'] == 'ok'
    assert result.get('analysis'), 'success response must carry the analysis text'
    assert result['index'] == 0
    assert mock_save.called, 'a successful review must be persisted to the journal'


def test_analyze_returns_usable_message_when_client_unconfigured():
    trade = _valid_trade()
    with patch.object(main, 'load_journal', return_value=[trade]), \
         patch('core.config.client', None):
        result = asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))

    assert result['status'] == 'error'
    assert result.get('detail'), 'error response must carry a human-readable detail message'


def test_analyze_raises_500_with_usable_detail_on_claude_error():
    from fastapi import HTTPException
    trade = _valid_trade()
    with patch.object(main, 'load_journal', return_value=[trade]), \
         patch('core.config.client') as mock_client:
        mock_client.messages.create.side_effect = RuntimeError('credit balance is too low')
        try:
            asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))
            raise AssertionError('expected HTTPException to be raised')
        except HTTPException as exc:
            assert exc.status_code == 500
            assert exc.detail, 'HTTPException must carry a non-empty detail message'
            assert 'credit balance' in exc.detail or 'Claude API error' in exc.detail


def test_analyze_raises_400_on_invalid_index():
    from fastapi import HTTPException
    with patch.object(main, 'load_journal', return_value=[]):
        try:
            asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))
            raise AssertionError('expected HTTPException to be raised')
        except HTTPException as exc:
            assert exc.status_code == 400


def test_analyze_does_not_crash_on_sparse_trade_record():
    # A trade missing nearly every optional field must not crash prompt building —
    # this is the "missing outcome data does not crash" guarantee for this endpoint.
    sparse_trade = {'ticker': 'MNQ1!'}
    with patch.object(main, 'load_journal', return_value=[sparse_trade]), \
         patch.object(main, 'save_journal'), \
         patch('core.config.client') as mock_client:
        mock_client.messages.create.return_value = _mock_claude_response('OK')
        result = asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))

    assert result['status'] == 'ok'


# ── Frontend: generateAnalysis() error surfacing ───────────────────────────

def test_error_helper_function_present():
    assert 'function _novaReviewError(msg)' in DASHBOARD_HTML


def test_generate_analysis_calls_error_helper_on_failure_branches():
    fn_start = DASHBOARD_HTML.find('async function generateAnalysis')
    fn_end   = DASHBOARD_HTML.find('function toggleReview')
    fn_body  = DASHBOARD_HTML[fn_start:fn_end]
    assert fn_body.count('_novaReviewError(') >= 2, (
        'generateAnalysis() must call _novaReviewError() on both the '
        'non-ok-response branch and the catch(e) branch — this is the '
        'regression guard for the "silent failure" bug'
    )


def test_generate_analysis_checks_res_ok():
    fn_start = DASHBOARD_HTML.find('async function generateAnalysis')
    fn_end   = DASHBOARD_HTML.find('function toggleReview')
    fn_body  = DASHBOARD_HTML[fn_start:fn_end]
    assert 'res.ok' in fn_body, (
        'generateAnalysis() must check the HTTP response status, not just '
        'data.status, or an HTTPException body shaped differently than '
        '{status:"ok"} could be misread'
    )


def test_no_backslash_quote_in_new_review_js():
    assert "\\'" not in _JS_BLOCK, "Found \\' escape sequence in NOVA Review JS block — use ' directly"


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [
        ('analyze: returns ok JSON on success',               test_analyze_returns_ok_json_on_success),
        ('analyze: usable message when client unconfigured',  test_analyze_returns_usable_message_when_client_unconfigured),
        ('analyze: 500 with usable detail on Claude error',   test_analyze_raises_500_with_usable_detail_on_claude_error),
        ('analyze: 400 on invalid index',                     test_analyze_raises_400_on_invalid_index),
        ('analyze: sparse trade record does not crash',       test_analyze_does_not_crash_on_sparse_trade_record),
        ('frontend: _novaReviewError() helper present',       test_error_helper_function_present),
        ('frontend: error helper called on failure branches', test_generate_analysis_calls_error_helper_on_failure_branches),
        ('frontend: checks res.ok (HTTP status)',              test_generate_analysis_checks_res_ok),
        ('frontend: no backslash-quote in review JS',          test_no_backslash_quote_in_new_review_js),
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
