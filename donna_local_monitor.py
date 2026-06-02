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
import logging
import sys
import time

# Force UTF-8 output on Windows to handle arrow/symbol chars from NOVA tables
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from datetime import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo('America/New_York')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('nova')

_QUALITY_LABEL = {'A': 'A', 'B': 'B', 'C': 'C', 'dead': '-'}


def _get_session() -> dict:
    """Return current session info from the reasoning engine's classifier."""
    from donna_nova_reasoning import _session_info
    now  = datetime.now(NY_TZ)
    mins = now.hour * 60 + now.minute
    return _session_info(mins, now.weekday())


def _time_et() -> str:
    return datetime.now(NY_TZ).strftime('%H:%M ET')


def main() -> None:
    from donna_nova_reasoning import run_reasoning_cycle
    from donna_alert_engine import deliver_alert

    log.info('NOVA monitor started')
    log.info('Active: ASIA 20:00-00:00 | LONDON 03:00-08:30 | NY_OPEN 09:30-11:00 | NY_AM 11:00-12:30 | NY_PM 13:30-16:00')
    log.info('Ctrl+C to stop\n')

    while True:
        try:
            sess = _get_session()

            if sess['active']:
                quality = sess['quality']
                name    = sess['name']

                alerts = run_reasoning_cycle()
                if alerts:
                    for alert in alerts:
                        grade = getattr(alert, 'grade', '?')
                        log.info(
                            f'ALERT  [{name}]  {alert.alert_type} | {alert.setup_type} '
                            f'| {alert.direction} | grade={grade}'
                        )
                        deliver_alert(alert)
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
