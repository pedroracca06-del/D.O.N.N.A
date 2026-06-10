"""donna_local_monitor.py — Local NOVA reasoning monitor.

Run this on your trading machine before the session opens.
Monitors across Asia, London, and full New York sessions.
Delivers HEADS_UP / EXECUTION_READY / INVALIDATION alerts to Discord with chart screenshots.

Active sessions (60s polling):
  ASIA       20:00–00:00 ET  — PROS only, grade A required
  LONDON     03:00–08:30 ET  — PROS only, grade A/B
  NY_OPEN    09:30–11:00 ET  — PROS + ORB, grade A/B (highest quality)
  NY_AM      11:00–12:30 ET  — PROS continuation, grade A/B
  NY_PM      13:30–16:00 ET  — PROS only, grade A required

Dead zones (300s sleep, no API calls):
  DEAD_ZONE  00:00–03:00 ET
  LUNCH      12:30–13:30 ET
  POST_CLOSE 16:00–18:00 ET
  PRE_MARKET 08:30–09:30 ET
  WEEKEND    Saturday / Sunday before 18:00

Usage:
    python donna_local_monitor.py

Keep this terminal open while trading. Ctrl+C to stop.
"""
from __future__ import annotations

import io
import json
import logging
import os
import sys
import time

# Force UTF-8 output on Windows to handle arrow/symbol chars from NOVA tables
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from datetime import datetime
from zoneinfo import ZoneInfo

import requests

NY_TZ = ZoneInfo('America/New_York')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('nova')

_QUALITY_LABEL = {'A': 'A', 'B': 'B', 'C': 'C', 'dead': '-'}
_MCP_FAIL_THRESHOLD = 3  # consecutive failures before Discord alert


def _get_session() -> dict:
    """Return current session info from the reasoning engine's classifier."""
    from engines.reasoning import _session_info
    now  = datetime.now(NY_TZ)
    mins = now.hour * 60 + now.minute
    return _session_info(mins, now.weekday())


def _time_et() -> str:
    return datetime.now(NY_TZ).strftime('%H:%M ET')


def _is_extreme_market() -> bool:
    """True when market reality reports PANIC_SELLING or BEARISH_DOMINANT (V2), or EXTREME/CRITICAL severity (V1 fallback)."""
    try:
        import json as _j
        from pathlib import Path as _P
        mr2_path = _P(__file__).parent / 'data' / 'donna_market_reality_v2.json'
        if mr2_path.exists():
            mr2 = _j.loads(mr2_path.read_text())
            if mr2.get('state'):
                return mr2.get('state') in ('PANIC_SELLING', 'BEARISH_DOMINANT')
    except Exception:
        pass
    # V1 fallback when V2 file is absent or unreadable
    try:
        import json as _j
        from pathlib import Path as _P
        mr = _j.loads((_P(__file__).parent / 'data' / 'donna_market_reality.json').read_text())
        return mr.get('severity') in ('EXTREME', 'CRITICAL')
    except Exception:
        return False


def _market_summary() -> str:
    """Short market context string for Discord notifications."""
    try:
        import json as _j
        from pathlib import Path as _P
        rs = _j.loads((_P(__file__).parent / 'data' / 'donna_risk_state.json').read_text())
        snap = rs.get('market_snapshot', {})
        nq   = snap.get('NQ', {})
        vix  = snap.get('VIX', {})
        return f"NQ {nq.get('last', '?')} ({nq.get('pct', '?')}%)  |  VIX {vix.get('last', '?')}"
    except Exception:
        return ''


def _send_health_alert(title: str, description: str, color: int) -> None:
    """Send a system health embed to the live Discord channel."""
    try:
        token      = os.getenv('DISCORD_BOT_TOKEN', '')
        channel_id = os.getenv('DISCORD_CHANNEL_LIVE', '')
        if not token or not channel_id:
            return
        embed = {
            'title':       title,
            'description': description,
            'color':       color,
            'timestamp':   datetime.utcnow().isoformat(),
        }
        requests.post(
            f'https://discord.com/api/v10/channels/{channel_id}/messages',
            headers={'Authorization': f'Bot {token}', 'Content-Type': 'application/json'},
            json={'embeds': [embed]},
            timeout=10,
        )
    except Exception as e:
        log.warning(f'Health alert send failed: {e}')


def _run_premarket_check() -> None:
    """
    9:25 AM ET pre-market health check — alerts, TradingView MCP, execution.
    Posts a focused status embed to the morning-brief Discord channel.
    """
    from engines.reasoning import _run_mcp

    now_str = datetime.now(NY_TZ).strftime('%H:%M ET')
    lines   = []
    issues  = []

    # ── TradingView MCP ───────────────────────────────────────────────────────
    status_data, _ = None, None
    try:
        import subprocess, json as _json
        from pathlib import Path
        mcp_dir = Path(__file__).parent / 'mcp' / 'tradingview'

        result = subprocess.run(
            ['node', 'src/cli/index.js', 'status'],
            cwd=str(mcp_dir), capture_output=True, text=True, timeout=10,
        )
        status_data = _json.loads(result.stdout.strip()) if result.stdout.strip() else None
    except Exception:
        pass

    if status_data and status_data.get('success') is not False:
        # Quick quote for live price confirmation
        try:
            qr = subprocess.run(
                ['node', 'src/cli/index.js', 'quote'],
                cwd=str(mcp_dir), capture_output=True, text=True, timeout=10,
            )
            quote = _json.loads(qr.stdout.strip()) if qr.stdout.strip() else {}
            price = quote.get('last') or quote.get('close') or '?'
            sym   = status_data.get('symbol', '?')
            lines.append(f'**TradingView MCP**   ✅  CDP live  ·  {sym} @ {price}')
        except Exception:
            lines.append('**TradingView MCP**   ✅  CDP live')
    else:
        lines.append('**TradingView MCP**   ❌  CDP offline — TradingView not running')
        issues.append('MCP offline')

    # ── Alert system ──────────────────────────────────────────────────────────
    token      = os.getenv('DISCORD_BOT_TOKEN', '')
    ch_live    = os.getenv('DISCORD_CHANNEL_LIVE', '')
    ch_exec    = os.getenv('DISCORD_CHANNEL_EXECUTION', '')
    ch_brief   = os.getenv('DISCORD_CHANNEL_MORNING_BRIEF', '')

    configured = sum(1 for c in [ch_live, ch_exec, ch_brief,
                                  os.getenv('DISCORD_CHANNEL_HEADS_UP',''),
                                  os.getenv('DISCORD_CHANNEL_INVALIDATION',''),
                                  os.getenv('DISCORD_CHANNEL_NO_TRADE',''),
                                  os.getenv('DISCORD_CHANNEL_MACRO','')] if c)
    if token and configured >= 5:
        lines.append(f'**Alert System**      ✅  {configured}/7 channels configured')
    elif token:
        lines.append(f'**Alert System**      ⚠️  {configured}/7 channels — some missing')
        issues.append('alert channels incomplete')
    else:
        lines.append('**Alert System**      ❌  Discord bot token not set')
        issues.append('Discord not configured')

    # ── Execution ─────────────────────────────────────────────────────────────
    try:
        import json as _json2
        from pathlib import Path as _Path
        se_path = _Path(__file__).parent / 'data' / 'donna_state_engine.json'
        se = _json2.loads(se_path.read_text(encoding='utf-8')) if se_path.exists() else {}
    except Exception:
        se = {}

    trade_perm  = se.get('trade_permission', True)
    exec_lock   = se.get('execution_lock', False)
    macro_lock  = se.get('macro_lock', False)
    trades_done = se.get('daily_trade_count', 0)
    auto_exec   = os.getenv('NOVA_AUTO_EXECUTE', '').strip().lower() == 'true'
    alpaca_key  = bool(os.getenv('ALPACA_API_KEY', ''))
    alpaca_url  = os.getenv('ALPACA_BASE_URL', 'paper')
    mode        = 'PAPER' if 'paper' in alpaca_url.lower() else 'LIVE'

    # Auto-restore trade_permission if it's False with no valid blocking reason.
    # This is the last line of defence before the session opens.
    if not trade_perm and not exec_lock and not se.get('daily_loss_trade_hit', False):
        try:
            from services.execution import enable_trade_permission
            enable_trade_permission()
            trade_perm = True
            log.info('Pre-market check: trade_permission auto-restored before open')
        except Exception as _ep:
            log.warning(f'Pre-market check: could not restore trade_permission: {_ep}')

    exec_parts = []
    exec_ok    = True

    if not auto_exec:
        exec_parts.append('NOVA_AUTO_EXECUTE not set')
        exec_ok = False
        issues.append('NOVA_AUTO_EXECUTE disabled')
    else:
        exec_parts.append(f'{mode} mode')

    if not trade_perm:
        exec_parts.append('trade permission **DISABLED**')
        exec_ok = False
        issues.append('trade_permission=False')
    else:
        exec_parts.append('permission ON')

    if exec_lock or macro_lock:
        exec_parts.append('LOCKED')
        exec_ok = False
        issues.append('execution locked')

    if not alpaca_key:
        exec_parts.append('Alpaca keys missing')
        exec_ok = False
        issues.append('Alpaca not configured')

    exec_parts.append(f'trades today: {trades_done}/5')

    exec_icon = '✅' if exec_ok else '❌'
    lines.append(f'**Execution**         {exec_icon}  {" · ".join(exec_parts)}')

    # ── Build and send embed ──────────────────────────────────────────────────
    safe       = len(issues) == 0
    color      = 0x00C851 if safe else (0xFF4444 if len(issues) >= 2 else 0xFFBB33)
    verdict    = '✅  **READY — open in 5 min**' if safe else f'⚠️  **{len(issues)} issue(s) — fix before open**'

    description = '\n'.join(lines) + f'\n\n{verdict}'
    if issues:
        description += '\n> ' + ' · '.join(issues)

    try:
        _token = os.getenv('DISCORD_BOT_TOKEN', '')
        _ch    = os.getenv('DISCORD_CHANNEL_MORNING_BRIEF') or os.getenv('DISCORD_CHANNEL_LIVE', '')
        if _token and _ch:
            _r = requests.post(
                f'https://discord.com/api/v10/channels/{_ch}/messages',
                headers={'Authorization': f'Bot {_token}', 'Content-Type': 'application/json'},
                json={'embeds': [{
                    'title':       f'NOVA PRE-MARKET CHECK  ·  {now_str}',
                    'description': description,
                    'color':       color,
                    'timestamp':   datetime.utcnow().isoformat(),
                    'footer':      {'text': 'NY_OPEN in 5 min  ·  09:30 ET'},
                }]},
                timeout=10,
            )
            if _r.status_code in (200, 201):
                log.info(f'Pre-market check delivered — {"READY" if safe else "ISSUES: " + str(issues)}')
            else:
                log.error(f'Pre-market check Discord error {_r.status_code}: {_r.text[:200]}')
        else:
            log.warning('Pre-market check: Discord not configured — logging only')
            for ln in lines:
                log.info(ln.replace('**', ''))
    except Exception as e:
        log.warning(f'Pre-market check Discord send failed: {e}')


def main() -> None:
    from engines.reasoning import run_reasoning_cycle, _run_mcp
    from delivery.alert_engine import deliver_alert
    from services.execution_bridge import route_to_execution

    _auto_execute = os.getenv('NOVA_AUTO_EXECUTE', 'false').strip().lower() == 'true'
    _exec_label   = 'ENABLED (paper only)' if _auto_execute else 'DISABLED — set NOVA_AUTO_EXECUTE=true to enable'

    log.info('NOVA monitor started')
    log.info('Active: ASIA 20:00-00:00 | LONDON 03:00-08:30 | NY_OPEN 09:30-11:00 | NY_AM 11:00-12:30 | NY_PM 13:30-16:00')
    log.info(f'Auto-execute: {_exec_label}')
    log.info('Ctrl+C to stop\n')

    _mcp_fail_count       = 0
    _mcp_down_alerted     = False
    _premarket_check_date = ''   # YYYY-MM-DD of last pre-market check
    _lunch_alerted        = False
    _lunch_override_alerted = False

    # ── Startup: restore trade_permission if no valid block exists ────────────
    # EOD disables it at 3:30 PM daily. The daily reset in state_engine should
    # restore it each morning, but can be pre-empted if the state date is already
    # updated before the reset fires. This guard catches that race condition.
    try:
        import json as _json
        from pathlib import Path as _Path
        _se_path = _Path(__file__).parent / 'data' / 'donna_state_engine.json'
        _se = _json.loads(_se_path.read_text(encoding='utf-8')) if _se_path.exists() else {}
        if (
            not _se.get('trade_permission', True)
            and not _se.get('daily_loss_trade_hit', False)
            and not _se.get('execution_lock', False)
        ):
            from services.execution import enable_trade_permission
            enable_trade_permission()
            log.info('Startup: trade_permission restored — no blocking condition active')
    except Exception as _spe:
        log.warning(f'Startup trade_permission check failed: {_spe}')

    while True:
        try:
            now_ny = datetime.now(NY_TZ)
            _today = now_ny.strftime('%Y-%m-%d')
            _h, _m = now_ny.hour, now_ny.minute

            # ── 9:25 AM pre-market check — fires once per trading day ─────────
            if (
                _h == 9 and 25 <= _m <= 29
                and now_ny.weekday() < 5          # weekday only
                and _premarket_check_date != _today
            ):
                _premarket_check_date = _today
                log.info(f'{_time_et()} — running pre-market health check')
                try:
                    _run_premarket_check()
                except Exception as _pce:
                    log.error(f'Pre-market check failed: {_pce}')

            sess = _get_session()

            # Shorten dead-zone sleep to 60s between 9:00–9:29 so the 9:25
            # check is never missed due to a long 300s sleep cycle.
            if not sess['active'] and _h == 9 and _m < 30:
                sess['poll_interval'] = 60

            # EXTREME market override — never go dark during LUNCH in a crisis
            if sess['name'] == 'LUNCH':
                if _is_extreme_market():
                    sess = {'name': 'NY_AM', 'quality': 'B', 'active': True, 'poll_interval': 60}
                    if not _lunch_override_alerted:
                        _send_health_alert(
                            'NOVA LUNCH OVERRIDE — EXTREME MARKET',
                            f'Market severity EXTREME. Scanner continuing through lunch break.\n{_market_summary()}',
                            0xFF8800,
                        )
                        _lunch_override_alerted = True
                        log.warning('LUNCH override active — extreme market conditions')
                else:
                    _lunch_override_alerted = False
                    if not _lunch_alerted:
                        mkt = _market_summary()
                        _send_health_alert(
                            'NOVA PAUSED — LUNCH 12:30-13:30 ET',
                            f'Scanner entering lunch break. Resumes at 13:30 ET.\n{mkt}',
                            0x888888,
                        )
                        _lunch_alerted = True
                        log.info('Lunch break — Discord notification sent')
            else:
                _lunch_alerted        = False
                _lunch_override_alerted = False

            if sess['active']:
                quality = sess['quality']
                name    = sess['name']

                # ── MCP health check ──────────────────────────────────────
                mcp_ok = bool(_run_mcp('symbol'))

                if not mcp_ok:
                    _mcp_fail_count += 1
                    log.warning(f'{_time_et()} [{name}] MCP unreachable ({_mcp_fail_count}/{_MCP_FAIL_THRESHOLD}) — TradingView CDP down?')
                    if _mcp_fail_count >= _MCP_FAIL_THRESHOLD and not _mcp_down_alerted:
                        _send_health_alert(
                            '🔴 NOVA SCANNER DOWN',
                            f'TradingView CDP connection lost for {_mcp_fail_count} cycles.\n'
                            f'Chart scanning paused — **you are running blind.**\n\n'
                            f'Fix: relaunch TradingView with CDP flag via `launch_tradingview_cdp.ps1`',
                            0xFF0000,
                        )
                        _mcp_down_alerted = True
                        log.warning('Discord health alert sent — MCP down')
                else:
                    if _mcp_down_alerted:
                        _mcp_fail_count   = 0
                        _mcp_down_alerted = False
                        _send_health_alert(
                            '🟢 NOVA SCANNER RECOVERED',
                            'TradingView CDP connection restored. Chart scanning resumed.',
                            0x00C851,
                        )
                        log.info('Discord health alert sent — MCP recovered')
                    _mcp_fail_count = 0

                    # ── Normal reasoning cycle ────────────────────────────
                    # _collect_all_contexts() dwells on each symbol — no extra sleep needed
                    alerts = run_reasoning_cycle()
                    if alerts:
                        for alert in alerts:
                            grade = getattr(alert, 'grade', '?')
                            log.info(
                                f'ALERT  [{name}]  {alert.alert_type} | {alert.setup_type} '
                                f'| {alert.direction} | grade={grade}'
                            )
                            deliver_alert(alert)

                            if getattr(alert, 'alert_type', '') == 'EXECUTION_READY':
                                try:
                                    bridge_result = route_to_execution(alert)
                                    b_status = bridge_result.get('status', '?')
                                    b_detail = (
                                        bridge_result.get('result', {}).get('status', '')
                                        or bridge_result.get('reason', '')
                                        or bridge_result.get('code', '')
                                    )
                                    log.info(
                                        f'BRIDGE [{name}] {alert.symbol} {alert.direction} '
                                        f'grade={grade} → {b_status} {b_detail}'
                                    )
                                except Exception as be:
                                    log.error(f'Bridge error: {be}')
                    else:
                        log.info(f'{_time_et()} [{name} Q:{quality}] — no signal')
                    sess['poll_interval'] = 0  # dwell time in scan is the cadence

            else:
                name = sess['name']
                log.info(f'{_time_et()} [{name}] — dead zone, sleeping {sess["poll_interval"]}s')

        except KeyboardInterrupt:
            log.info('Monitor stopped.')
            return
        except Exception as e:
            log.error(f'Cycle error: {e}')

        time.sleep(sess.get('poll_interval', 60))


if __name__ == '__main__':
    main()
