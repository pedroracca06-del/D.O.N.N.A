"""donna_local_monitor.py — Local NOVA reasoning monitor.

Run this on your trading machine before the session opens.
Polls the live chart every 60 seconds during 09:30–11:00 ET and
delivers HEADS_UP / EXECUTION_READY / INVALIDATION alerts to Discord.

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


def _in_window() -> bool:
    now = datetime.now(NY_TZ)
    if now.weekday() >= 5:
        return False
    m = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= m <= 11 * 60


def _time_et() -> str:
    return datetime.now(NY_TZ).strftime('%H:%M ET')


def main() -> None:
    from donna_nova_reasoning import run_reasoning_cycle
    from donna_alert_engine import deliver_alert

    log.info('NOVA monitor started — armed for 09:30–11:00 ET')
    log.info('Ctrl+C to stop\n')

    while True:
        try:
            if _in_window():
                alerts = run_reasoning_cycle()
                if alerts:
                    for alert in alerts:
                        grade = getattr(alert, 'grade', '?')
                        log.info(
                            f'ALERT  {alert.alert_type} | {alert.setup_type} '
                            f'| {alert.direction} | grade={grade}'
                        )
                        deliver_alert(alert)
                else:
                    log.info(f'{_time_et()} — no signal')
            else:
                now = datetime.now(NY_TZ)
                m   = now.hour * 60 + now.minute
                if m < 9 * 60 + 30:
                    mins_to_open = (9 * 60 + 30) - m
                    log.info(f'{_time_et()} — pre-market, {mins_to_open} min to open')
                elif m > 11 * 60:
                    log.info(f'{_time_et()} — session closed, monitor sleeping')

        except KeyboardInterrupt:
            log.info('Monitor stopped.')
            return
        except Exception as e:
            log.error(f'Cycle error: {e}')

        time.sleep(60)


if __name__ == '__main__':
    main()
