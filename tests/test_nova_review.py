"""
test_nova_review.py — Journal "NOVA Review" (AI trade analysis) regression tests.

Context: NOVA Review is the per-trade AI analysis feature in the Journal tab
(the "Generate NOVA Review" button on trade cards / trade-detail modal) — it
is NOT the NOVA REPLAY tab (covered separately by test_replay_dashboard.py).
It calls POST /journal/analyze (main.py), which as of NOVA Intelligence V1
commit #6 calls intelligence.gateway.request_intelligence("journal_review",
...) instead of core.config.client directly.

Root-cause audit found the account's Anthropic credit balance was too low,
so every generation attempt failed with a 400 from Anthropic's API — and the
frontend's generateAnalysis() JS silently swallowed that failure with zero
visible error, indistinguishable from "does nothing" (a real, separate bug
from the billing issue itself, which is an account matter, not a code fix).
This file locks in: (a) the backend already returns/raises a usable error
message on every failure path, and (b) the frontend now surfaces it.

Covers:
  1.  /journal/analyze returns valid JSON {'status':'ok', ...} on success
  2.  /journal/analyze returns a usable message when the provider is unconfigured
  3.  /journal/analyze raises HTTPException(500) with a usable, non-leaking
      detail on a provider failure (e.g. credit exhaustion)
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
from intelligence.envelope import IntelligenceResponse, UsageInfo
from intelligence.errors import IntelligenceErrorCode

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


def _success_envelope(text: str) -> IntelligenceResponse:
    return IntelligenceResponse(
        success=True, feature='journal_review', provider='anthropic', model='claude-haiku-4-5-20251001',
        request_id='req-test', cached=False, latency_ms=1, content=text, structured_data={'analysis': text},
        usage=UsageInfo(input_tokens=50, output_tokens=20, estimated_cost_usd=0.0002),
    )


def _failure_envelope(error_code: IntelligenceErrorCode, user_message: str) -> IntelligenceResponse:
    return IntelligenceResponse(
        success=False, feature='journal_review', provider='anthropic', model='claude-haiku-4-5-20251001',
        request_id='req-test', cached=False, latency_ms=1, error_code=error_code.value, user_message=user_message,
        usage=UsageInfo(),
    )


# ── Backend: /journal/analyze ──────────────────────────────────────────────

def test_analyze_returns_ok_json_on_success():
    trade = _valid_trade()
    with patch.object(main, 'load_journal', return_value=[trade]), \
         patch.object(main, 'save_journal') as mock_save, \
         patch.object(main, 'request_intelligence', return_value=_success_envelope('QUALIFICATION\nGood setup.')) as mock_gw:
        result = asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))

    assert result['status'] == 'ok'
    assert result.get('analysis'), 'success response must carry the analysis text'
    assert result['index'] == 0
    assert mock_save.called, 'a successful review must be persisted to the journal'
    mock_gw.assert_called_once()
    assert mock_gw.call_args.args[0] == 'journal_review'


def test_analyze_returns_usable_message_when_provider_unconfigured():
    trade = _valid_trade()
    envelope = _failure_envelope(
        IntelligenceErrorCode.PROVIDER_NOT_CONFIGURED,
        'AI features are not configured right now.',
    )
    with patch.object(main, 'load_journal', return_value=[trade]), \
         patch.object(main, 'request_intelligence', return_value=envelope):
        result = asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))

    assert result['status'] == 'error'
    assert result.get('detail'), 'error response must carry a human-readable detail message'
    assert result['detail'] == 'AI features are not configured right now.'


def test_analyze_raises_500_with_usable_detail_on_provider_error():
    from fastapi import HTTPException
    trade = _valid_trade()
    envelope = _failure_envelope(
        IntelligenceErrorCode.INSUFFICIENT_CREDITS,
        'AI credits are unavailable right now — try again later.',
    )
    with patch.object(main, 'load_journal', return_value=[trade]), \
         patch.object(main, 'request_intelligence', return_value=envelope):
        try:
            asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))
            raise AssertionError('expected HTTPException to be raised')
        except HTTPException as exc:
            assert exc.status_code == 500
            assert exc.detail, 'HTTPException must carry a non-empty detail message'
            assert exc.detail == 'AI credits are unavailable right now — try again later.'
            # The regression this file exists for: no raw exception/provider
            # detail ever leaks into the HTTP response.
            assert 'RuntimeError' not in exc.detail
            assert 'Traceback' not in exc.detail


def test_analyze_sanitizes_unexpected_exception():
    """A genuinely unexpected failure (e.g. a prompt-build bug) must never
    leak str(e) into the HTTP response -- distinct from an ordinary gateway
    failure envelope, which is covered by the previous test."""
    from fastapi import HTTPException
    trade = _valid_trade()
    with patch.object(main, 'load_journal', return_value=[trade]), \
         patch.object(main, 'request_intelligence', side_effect=RuntimeError('a secret internal detail that must never leak')):
        try:
            asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))
            raise AssertionError('expected HTTPException to be raised')
        except HTTPException as exc:
            assert exc.status_code == 500
            assert exc.detail == 'Journal review failed.'
            assert 'secret internal detail' not in exc.detail


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
         patch.object(main, 'request_intelligence', return_value=_success_envelope('OK')):
        result = asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))

    assert result['status'] == 'ok'


def test_analyze_passes_curated_trade_and_nearby_signals_only():
    """input_data must carry exactly {'trade': {...curated fields...},
    'nearby_signals': str} -- never the raw trade dict, and never
    nova_review/nova_review_ts (this endpoint's own prior output)."""
    trade = _valid_trade(nova_review='a prior review', nova_review_ts='2026-01-01T00:00:00Z')
    with patch.object(main, 'load_journal', return_value=[trade]), \
         patch.object(main, 'save_journal'), \
         patch.object(main, 'request_intelligence', return_value=_success_envelope('OK')) as mock_gw:
        asyncio.run(main.journal_analyze(_FakeRequest({'index': 0})))

    input_data = mock_gw.call_args.args[1]
    assert set(input_data.keys()) == {'trade', 'nearby_signals'}
    assert 'nova_review' not in input_data['trade']
    assert 'nova_review_ts' not in input_data['trade']
    assert input_data['trade']['ticker'] == 'MES1!'
    assert mock_gw.call_args.kwargs.get('user_id') == 'pedro'


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
        ('analyze: returns ok JSON on success',                 test_analyze_returns_ok_json_on_success),
        ('analyze: usable message when provider unconfigured',  test_analyze_returns_usable_message_when_provider_unconfigured),
        ('analyze: 500 with usable detail on provider error',   test_analyze_raises_500_with_usable_detail_on_provider_error),
        ('analyze: sanitizes unexpected exception',             test_analyze_sanitizes_unexpected_exception),
        ('analyze: 400 on invalid index',                       test_analyze_raises_400_on_invalid_index),
        ('analyze: sparse trade record does not crash',         test_analyze_does_not_crash_on_sparse_trade_record),
        ('analyze: curated trade + nearby signals only',        test_analyze_passes_curated_trade_and_nearby_signals_only),
        ('frontend: _novaReviewError() helper present',         test_error_helper_function_present),
        ('frontend: error helper called on failure branches',   test_generate_analysis_calls_error_helper_on_failure_branches),
        ('frontend: checks res.ok (HTTP status)',                test_generate_analysis_checks_res_ok),
        ('frontend: no backslash-quote in review JS',            test_no_backslash_quote_in_new_review_js),
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
