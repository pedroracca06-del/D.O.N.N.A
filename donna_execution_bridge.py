"""donna_execution_bridge.py — NOVA monitor → execution bot translator.

Translates AlertData objects into the signal_result payload expected by
execute_signal() in donna_execution.py.

Safety contract (enforced in order):
  1. NOVA_AUTO_EXECUTE env var must be 'true'           — disabled by default
  2. Alpaca must be in paper mode (_PAPER=True)          — live blocks hard
  3. alert_type must be EXECUTION_READY                  — HEADS_UP never executes
  4. grade must be A or B                                — C/D never executes
  5. direction must be LONG / SHORT / BUY / SELL         — N/A never executes
  6. symbol must be in the routing table                 — unknown symbols never execute
  7. execute_signal() runs all governance rules (0-5)    — bridge never bypasses

Claude grades setups. The bridge translates. The executor governs.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from donna_alert_engine import AlertData

# ── Config ───────────────────────────────────────────────────────────────────────

def _auto_execute_enabled() -> bool:
    """Read flag at call time so env changes take effect without restart."""
    return os.getenv('NOVA_AUTO_EXECUTE', 'false').strip().lower() == 'true'

# Symbol routing table: NOVA symbol → instrument + ticker
_SYMBOL_MAP: dict[str, dict] = {
    'MES':  {'instrument': 'MES', 'ticker': 'MES1!'},
    'ES':   {'instrument': 'ES',  'ticker': 'ES1!'},
    'MNQ':  {'instrument': 'MNQ', 'ticker': 'MNQ1!'},
    'NQ':   {'instrument': 'NQ',  'ticker': 'NQ1!'},
}

# Grade → confidence for execute_signal (Asia gate requires ≥90%)
_GRADE_CONFIDENCE: dict[str, str] = {
    'A': '90%',
    'B': '75%',
}

_SKIP   = 'skipped'
_TRIED  = 'attempted'
_OFF    = 'disabled'


# ── Internal helpers ─────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
    print(f'[bridge] {ts}  {msg}')


def _is_paper() -> bool:
    """True only when Alpaca is pointed at paper-api.alpaca.markets."""
    try:
        from donna_execution import _PAPER
        return bool(_PAPER)
    except Exception:
        return False


def _sym_key(symbol: str) -> str:
    """Normalise 'CME_MINI:MES1!' or 'MES' → 'MES'."""
    return (
        symbol.upper()
        .replace('CME_MINI:', '')
        .replace('CME:', '')
        .replace('1!', '')
        .replace('!', '')
        .strip()
    )


# ── Discord execution result notification ────────────────────────────────────────

def _notify_discord(alert: 'AlertData', result: dict, paper: bool) -> None:
    """Post a compact execution result embed to #execution channel."""
    try:
        import requests
        from donna_config import DISCORD_BOT_TOKEN
        from donna_alert_engine import _DISCORD_API, _resolve_channel, DISCORD_CHANNEL_LIVE

        # Route to #execution if configured, else fall back to #live-alerts
        channel = _resolve_channel('EXECUTION_READY') or DISCORD_CHANNEL_LIVE
        if not DISCORD_BOT_TOKEN or not channel:
            return

        status = result.get('status', 'unknown')
        code   = result.get('code') or result.get('reason') or ''
        mode   = 'PAPER' if paper else 'LIVE'

        if status == 'executed':
            color = 0x00C851   # green
            title = f'ORDER SUBMITTED  ·  {mode}'
            body  = (
                f"**{alert.symbol}** {getattr(alert, 'direction', '')}  "
                f"·  ETF: {result.get('etf', '?')}  "
                f"·  Shares: {result.get('shares', '?')}\n"
                f"Grade: {alert.grade}  ·  Session: {getattr(alert, 'session', '?')}\n"
                f"Order ID: `{result.get('order_id', '—')}`"
            )
        elif status == _SKIP:
            color = 0xFFBB33   # amber
            title = f'EXECUTION SKIPPED  ·  {mode}'
            body  = (
                f"**{alert.symbol}** {getattr(alert, 'direction', '')}\n"
                f"Reason: `{code}`\n"
                f"Grade: {alert.grade}  ·  Session: {getattr(alert, 'session', '?')}"
            )
        else:
            color = 0xFF4444   # red
            title = f'EXECUTION ERROR  ·  {mode}'
            body  = (
                f"**{alert.symbol}** {getattr(alert, 'direction', '')}\n"
                f"`{result.get('reason', result.get('error', 'unknown'))}`"
            )

        embed = {
            'title':       title,
            'description': body,
            'color':       color,
            'footer':      {'text': f'NOVA Bridge  ·  {datetime.now(timezone.utc).strftime("%H:%M UTC")}'},
            'timestamp':   datetime.now(timezone.utc).isoformat(),
        }
        requests.post(
            f'{_DISCORD_API}/channels/{channel}/messages',
            headers={
                'Authorization':  f'Bot {DISCORD_BOT_TOKEN}',
                'Content-Type':   'application/json',
            },
            json={'embeds': [embed]},
            timeout=10,
        )
    except Exception as exc:
        _log(f'discord notify error: {exc}')


# ── Public API ───────────────────────────────────────────────────────────────────

def route_to_execution(alert: 'AlertData') -> dict:
    """
    Translate an AlertData object and route it through execute_signal().

    Returns dict with keys:
      status  : 'disabled' | 'skipped' | 'attempted'
      reason  : why skipped (when status != attempted)
      code    : rejection code (when status == skipped)
      signal_id: unique ID (when status == attempted)
      result  : execute_signal() return dict (when status == attempted)
    """
    symbol     = getattr(alert, 'symbol',     '')
    alert_type = getattr(alert, 'alert_type', '')
    grade      = getattr(alert, 'grade',      '')
    direction  = getattr(alert, 'direction',  '')
    setup_type = getattr(alert, 'setup_type', '')
    session    = getattr(alert, 'session',    '')

    # ── Gate 1: Feature flag (checked dynamically — env change takes effect immediately)
    if not _auto_execute_enabled():
        _log(f'DISABLED  {symbol} {direction} {alert_type}  (set NOVA_AUTO_EXECUTE=true to enable)')
        return {'status': _OFF, 'reason': 'NOVA_AUTO_EXECUTE is false'}

    # ── Gate 2: Paper mode only — hard block on live
    paper = _is_paper()
    if not paper:
        _log(f'BLOCKED  {symbol} — live mode detected, bridge requires paper mode')
        return {'status': _SKIP, 'reason': 'live mode — bridge is paper-only', 'code': 'NOT_PAPER_MODE'}

    # ── Gate 3: EXECUTION_READY only
    if alert_type != 'EXECUTION_READY':
        _log(f'SKIP  {symbol}  alert_type={alert_type}  (not EXECUTION_READY)')
        return {'status': _SKIP, 'reason': f'alert_type={alert_type}', 'code': 'NOT_EXECUTION_READY'}

    # ── Gate 4: Grade A or B only
    if grade not in ('A', 'B'):
        _log(f'SKIP  {symbol} {direction}  grade={grade}  (not actionable)')
        return {'status': _SKIP, 'reason': f'grade={grade}', 'code': 'GRADE_NOT_ACTIONABLE'}

    # ── Gate 5: Valid direction
    direction_up = direction.upper()
    if direction_up not in ('LONG', 'SHORT', 'BUY', 'SELL'):
        _log(f'SKIP  {symbol}  direction={direction}  (not tradeable)')
        return {'status': _SKIP, 'reason': f'direction={direction}', 'code': 'INVALID_DIRECTION'}
    signal = 'LONG' if direction_up in ('LONG', 'BUY') else 'SHORT'

    # ── Gate 6: Symbol routing
    key     = _sym_key(symbol)
    routing = _SYMBOL_MAP.get(key)
    if not routing:
        _log(f'SKIP  {symbol}  unmapped symbol (key={key})')
        return {'status': _SKIP, 'reason': f'unmapped symbol: {symbol}', 'code': 'UNMAPPED_SYMBOL'}

    instrument = routing['instrument']
    ticker     = routing['ticker']

    # ── Build execute_signal payload
    strategy_family = setup_type.split('_')[0] if '_' in setup_type else 'NOVA'
    confidence      = _GRADE_CONFIDENCE.get(grade, '75%')
    signal_id       = f'NOVA_{key}_{signal}_{uuid.uuid4().hex[:8].upper()}'

    signal_result = {
        'status': 'ok',
        'data': {
            'ticker':          ticker,
            'instrument':      instrument,
            'signal':          signal,
            'signal_id':       signal_id,
            'strategy_family': strategy_family,
            'setup_type':      setup_type,
            'session':         session,
            'score':           grade,
            'timeframe':       getattr(alert, 'timeframe', ''),
            'trap_risk':       'false',
            'signal_reason':   f'NOVA grade {grade} | {setup_type} | {session}',
        },
        'parsed': {
            'verdict':    'TAKE',
            'confidence': confidence,
        },
    }

    _log(
        f'ROUTING  {instrument} {signal}  grade={grade}  conf={confidence}  '
        f'session={session}  id={signal_id}'
    )

    # ── Route — all governance enforced inside execute_signal(), not here
    try:
        from donna_execution import execute_signal
        result = execute_signal(signal_result)
    except Exception as exc:
        _log(f'execute_signal() raised: {exc}')
        result = {'status': 'error', 'reason': str(exc)}

    exec_status = result.get('status', 'unknown')
    exec_code   = result.get('code') or result.get('reason', '')
    _log(f'RESULT  status={exec_status}  code={exec_code}  id={signal_id}')

    _notify_discord(alert, result, paper)

    return {'status': _TRIED, 'signal_id': signal_id, 'result': result}


# ── Smoke test — run directly to verify pipeline without live signals ─────────────

def _run_smoke_test() -> None:
    """
    Build a synthetic EXECUTION_READY alert and run it through the full bridge.
    Verifies translation, gate logic, and execute_signal() governance without
    waiting for a live chart signal.

    Usage:  python donna_execution_bridge.py
    """
    import sys

    # Import AlertData
    try:
        from donna_alert_engine import AlertData
    except ImportError:
        print('[smoke] FAIL — cannot import AlertData')
        sys.exit(1)

    print('\n=== NOVA EXECUTION BRIDGE SMOKE TEST ===\n')

    # (label, env_auto_execute, overrides)
    cases = [
        ('Gate 1 — AUTO_EXECUTE disabled (expected: disabled)',
         False,
         {'alert_type': 'EXECUTION_READY', 'grade': 'A', 'direction': 'LONG'}),
        ('Gate 3 — HEADS_UP not routed (expected: skipped NOT_EXECUTION_READY)',
         True,
         {'alert_type': 'HEADS_UP', 'grade': 'A', 'direction': 'LONG'}),
        ('Gate 4 — Grade C blocked (expected: skipped GRADE_NOT_ACTIONABLE)',
         True,
         {'alert_type': 'EXECUTION_READY', 'grade': 'C', 'direction': 'LONG'}),
        ('Gate 5 — N/A direction blocked (expected: skipped INVALID_DIRECTION)',
         True,
         {'alert_type': 'EXECUTION_READY', 'grade': 'A', 'direction': 'N/A'}),
        ('Gate 6 — Unknown symbol (expected: skipped UNMAPPED_SYMBOL)',
         True,
         {'alert_type': 'EXECUTION_READY', 'grade': 'A', 'direction': 'LONG', 'symbol': 'AAPL'}),
        ('Full path — Grade A LONG MES (expected: attempted, governance decides)',
         True,
         {'alert_type': 'EXECUTION_READY', 'grade': 'A', 'direction': 'LONG', 'symbol': 'MES'}),
        ('Full path — Grade B SHORT NQ (expected: attempted, governance decides)',
         True,
         {'alert_type': 'EXECUTION_READY', 'grade': 'B', 'direction': 'SHORT', 'symbol': 'NQ'}),
    ]

    for label, auto_on, overrides in cases:
        os.environ['NOVA_AUTO_EXECUTE'] = 'true' if auto_on else 'false'
        print(f'--- {label}')
        base = {
            'symbol':          'MES',
            'setup_type':      'PROS_LONG',
            'direction':       'LONG',
            'alert_type':      'EXECUTION_READY',
            'grade':           'A',
            'session':         'NY_OPEN',
            'session_quality': 'A',
        }
        base.update(overrides)
        alert = AlertData(**{k: v for k, v in base.items() if k in AlertData.__dataclass_fields__})
        result = route_to_execution(alert)
        print(f'    -> status={result["status"]}  '
              f'code={result.get("code", result.get("reason", result.get("result", {}).get("code", "")))}')
        print()

    print('=== SMOKE TEST COMPLETE ===')
    print('Review output above. "attempted" cases were sent to execute_signal().')
    print('Check donna_rejections.json and donna_execution_trace.json for governance records.\n')


if __name__ == '__main__':
    _run_smoke_test()
