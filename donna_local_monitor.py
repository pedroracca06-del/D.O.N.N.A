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
    from donna_nova_reasoning import _session_info
    now  = datetime.now(NY_TZ)
    mins = now.hour * 60 + now.minute
    return _session_info(mins, now.weekday())


def _time_et() -> str:
    return datetime.now(NY_TZ).strftime('%H:%M ET')


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


def main() -> None:
    from donna_nova_reasoning import run_reasoning_cycle, _run_mcp
    from donna_alert_engine import deliver_alert
    from donna_execution_bridge import route_to_execution

    _auto_execute = os.getenv('NOVA_AUTO_EXECUTE', 'false').strip().lower() == 'true'
    _exec_label   = 'ENABLED (paper only)' if _auto_execute else 'DISABLED — set NOVA_AUTO_EXECUTE=true to enable'

    log.info('NOVA monitor started')
    log.info('Active: ASIA 20:00-00:00 | LONDON 03:00-08:30 | NY_OPEN 09:30-11:00 | NY_AM 11:00-12:30 | NY_PM 13:30-16:00')
    log.info(f'Auto-execute: {_exec_label}')
    log.info('Ctrl+C to stop\n')

    _mcp_fail_count   = 0
    _mcp_down_alerted = False

    while True:
        try:
            sess = _get_session()

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
