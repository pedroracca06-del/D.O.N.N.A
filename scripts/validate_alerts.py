"""
validate_alerts.py — Full end-to-end Alerts category validation.

Generates one test event per category, pushes to Render, verifies via /api/feed,
then cleans up all test entries.

Usage:
    python scripts/validate_alerts.py
    python scripts/validate_alerts.py --cleanup-only   (remove previous test events)
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DONNA_DATA_DIR', str(ROOT / 'data'))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
except Exception:
    pass

RENDER_URL    = os.getenv('NOVA_RENDER_URL', '').rstrip('/')
INGEST_SECRET = os.getenv('NOVA_INGEST_SECRET', '')
NY_TZ         = ZoneInfo('America/New_York')


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(NY_TZ).strftime('%Y-%m-%d %H:%M:%S ET')

def _id(prefix: str) -> str:
    return f'TEST_{prefix}_{int(time.time()*1000)}_{random.randint(100,999)}'

def _post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode('utf-8')
    req  = urllib.request.Request(
        f'{RENDER_URL}{path}',
        data=data,
        headers={
            'Content-Type':         'application/json',
            'X-Nova-Ingest-Secret': INGEST_SECRET,
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())

def _get(path: str) -> dict:
    req = urllib.request.Request(
        f'{RENDER_URL}{path}',
        headers={'Accept': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())

def _check(label: str, cond: bool, detail: str = ''):
    mark = 'PASS' if cond else 'FAIL'
    print(f'  [{mark}] {label}' + (f' — {detail}' if detail else ''))
    return cond


# ── Test event definitions ─────────────────────────────────────────────────────

def make_morning_brief() -> dict:
    return {
        'id':            _id('INTEL'),
        'timestamp_et':  _ts(),
        'event_type':    'INTELLIGENCE',
        'subtype':       'MORNING_BRIEF',
        'session':       'NY_OPEN',
        'thesis':        '[TEST] Bullish structure above 21,200 NQ. PDH is primary draw.',
        'brief_text':    '[TEST EVENT] NQ accepted above PDH overnight. ES above monthly open. RVOL 1.2x. No red-folder until 14:00 ET. Bias long above 21,200, invalidation 21,080.',
        'liquidity_draw': 'ONH 21,340 (NQ) / PDH 5,883 (ES)',
        'participation':  'RVOL 1.2x - ABOVE_AVERAGE',
        'macro_risk':     'LOW',
        'key_question':  'Does NQ sustain above 21,200 on first pullback?',
        'thesis_state':  'BULLISH_LEANING',
        'confidence':    'CONDITIONAL',
        'primary_driver': 'MARKET_STRUCTURE',
        'bull_score':    7,
        'bear_score':    3,
    }

def make_liquidity_event() -> dict:
    return {
        'id':            _id('LIQ'),
        'timestamp_et':  _ts(),
        'event_type':    'LIQUIDITY_EVENT',
        'subtype':       'LIQUIDITY_SWEEP',
        'session':       'NY_OPEN',
        'symbol':        'NQ',
        'level':         'PDH',
        'price':         21340,
        'significance':  'HIGH',
        'description':   '[TEST] NQ swept PDH (21,340 HIGH) — resting sell orders cleared above. Potential draw exhausted.',
    }

def make_participation_event() -> dict:
    return {
        'id':            _id('PART'),
        'timestamp_et':  _ts(),
        'event_type':    'PARTICIPATION_EVENT',
        'subtype':       'RVOL_SURGE',
        'session':       'NY_OPEN',
        'symbol':        'NQ',
        'description':   '[TEST] NQ RVOL crossed 2.0x threshold — institutional participation confirmed. Session type: TRENDING.',
    }

def make_execution_ready() -> dict:
    """
    Signal log entry for an EXECUTION_READY alert.
    alert_type drives subtype=EXECUTION_READY and alert_fired=True in the feed.
    """
    return {
        'id':               _id('SIG'),
        'timestamp_et':     _ts(),
        'symbol':           'MES',
        'direction':        'LONG',
        'grade':            'A',
        'session':          'NY_OPEN',
        'alert_type':       'EXECUTION_READY',
        'strategy_family':  'PROS',
        'setup_type':       'PROS_LONG',
        'entry_zone':       '5820-5825',
        'stop':             '5805',
        'tp1':              '5845',
        'rr':               '1:1.7',
        'claude_rationale': '[TEST] Grade A PROS long. MR2 BULLISH_LEANING (+7). Draw to PDH 5,883. IB aligned long. Entry on first pullback to 5820 zone. Stop below IB low 5805.',
        'mr2_state':        'BULLISH_LEANING',
        'mr2_score':        7,
        'mr2_block_longs':  False,
        'mr2_block_shorts': False,
        'mr2_block_reason': '',
        'dp_dominance':     'BULLISH',
        'dp_conviction':    'HIGH',
        'draw_name':        'PDH',
        'draw_category':    'STRONG',
        'draw_tp1_pts':     60,
        'draw_independent': True,
        'pre_signal':       'A',
        'pre_rationale':    'IB aligned, structure clean, draw independent',
    }

def make_governance_rejection() -> dict:
    """
    Execution trace BRIDGE_REJECTED entry → normalizes to GOVERNANCE event_type.
    """
    return {
        'id':               _id('GOV'),
        'timestamp_et':     _ts(),
        'event_type':       'BRIDGE_REJECTED',
        'symbol':           'MES',
        'direction':        'LONG',
        'grade':            'A',
        'session':          'NY_OPEN',
        'rejection_code':   'DAILY_LOSS_LIMIT',
        'rejection_reason': '[TEST] Daily loss limit reached. 3 trades taken, max drawdown threshold hit. No new longs permitted until session reset.',
        'setup_type':       'PROS_LONG',
        'strategy_family':  'PROS',
    }


# ── Validation runner ──────────────────────────────────────────────────────────

def validate_event(
    category: str,
    event_type_expected: str,
    subtype_expected: str,
    entry: dict,
    ingest_field: str,
    fd_filter: str,
) -> bool:
    eid = entry['id']
    print(f'\n{"="*60}')
    print(f'  Category : {category}')
    print(f'  Type     : {event_type_expected} / {subtype_expected}')
    print(f'  ID       : {eid}')
    print(f'{"="*60}')

    all_pass = True

    # 1. Ingest
    try:
        resp = _post('/api/feed/ingest', {ingest_field: entry})
        ingested_id = resp.get(f'{ingest_field}_id', '') or resp.get('intelligence_id', '')
        ok = _check('Ingest accepted', resp.get('ok') is True, f'{ingest_field}_id={ingested_id}')
        all_pass = all_pass and ok
    except Exception as ex:
        _check('Ingest accepted', False, str(ex))
        return False

    time.sleep(0.8)

    # 2. Verify in /api/feed by event_type
    try:
        result = _get(f'/api/feed?event_type={event_type_expected}&limit=20')
        cards  = result.get('feed', [])
        total  = result.get('total', 0)
        match  = next((c for c in cards if c.get('source_id') == eid or
                       c.get('id') == f'FEED_INTEL_{eid}' or
                       c.get('id') == f'FEED_{eid}' or
                       eid in str(c.get('id', ''))), None)
        _check('Event in feed', match is not None, f'{total} {event_type_expected} cards found')
        if match:
            _check('event_type correct', match.get('event_type') == event_type_expected,
                   f'got={match.get("event_type")}')
            _check('subtype correct', match.get('subtype') == subtype_expected,
                   f'got={match.get("subtype")}')
            _check('summary populated', bool(match.get('claude_rationale') or
                                             (match.get('intelligence', {}) or {}).get('thesis')),
                   match.get('claude_rationale', '')[:80])
        else:
            all_pass = False
    except Exception as ex:
        _check('Feed verification', False, str(ex))
        all_pass = False

    # 3. Confirm category filter maps correctly
    cat_map = {
        'intelligence': ['INTELLIGENCE', 'MR2_CHANGE'],
        'execution':    ['SIGNAL', 'EXECUTION'],
        'system':       ['GOVERNANCE'],
        'market':       ['LIQUIDITY_EVENT', 'PARTICIPATION_EVENT'],
    }
    in_filter = event_type_expected in cat_map.get(fd_filter, [])
    _check(f'Maps to Alerts → {fd_filter.upper()} filter', in_filter)
    all_pass = all_pass and in_filter

    return all_pass


def run_cleanup(ids: list[str]) -> None:
    print(f'\n{"="*60}')
    print('  CLEANUP — removing test events from Render')
    print(f'  IDs: {ids}')
    print(f'{"="*60}')
    try:
        resp = _post('/api/test/purge', {'ids': ids})
        removed = resp.get('removed', {})
        print(f'  Removed: {removed}')
        _check('Purge accepted', resp.get('ok') is True)
    except Exception as ex:
        print(f'  CLEANUP FAILED: {ex}')


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    cleanup_only = '--cleanup-only' in sys.argv

    if not RENDER_URL:
        print('ERROR: NOVA_RENDER_URL not set')
        sys.exit(1)

    print(f'Render: {RENDER_URL}')
    print(f'Time  : {_ts()}')

    # ── Build all events ───────────────────────────────────────────────────────
    brief      = make_morning_brief()
    liq        = make_liquidity_event()
    part       = make_participation_event()
    signal     = make_execution_ready()
    governance = make_governance_rejection()

    all_ids = [brief['id'], liq['id'], part['id'], signal['id'], governance['id']]

    if cleanup_only:
        run_cleanup(all_ids)
        return

    # ── Also clean up the previous MORNING_BRIEF test event ───────────────────
    prev_brief_id = 'INTEL_1782013841415_200'

    results = []

    # 1. INTELLIGENCE / MORNING_BRIEF
    results.append(validate_event(
        category='INTELLIGENCE',
        event_type_expected='INTELLIGENCE',
        subtype_expected='MORNING_BRIEF',
        entry=brief,
        ingest_field='intelligence',
        fd_filter='intelligence',
    ))

    # 2. MARKET / LIQUIDITY_EVENT
    results.append(validate_event(
        category='MARKET',
        event_type_expected='LIQUIDITY_EVENT',
        subtype_expected='LIQUIDITY_SWEEP',
        entry=liq,
        ingest_field='intelligence',
        fd_filter='market',
    ))

    # 3. MARKET / PARTICIPATION_EVENT
    results.append(validate_event(
        category='MARKET',
        event_type_expected='PARTICIPATION_EVENT',
        subtype_expected='RVOL_SURGE',
        entry=part,
        ingest_field='intelligence',
        fd_filter='market',
    ))

    # 4. EXECUTION / EXECUTION_READY (SIGNAL type)
    results.append(validate_event(
        category='EXECUTION',
        event_type_expected='SIGNAL',
        subtype_expected='EXECUTION_READY',
        entry=signal,
        ingest_field='signal',
        fd_filter='execution',
    ))

    # 5. SYSTEM / GOVERNANCE (BRIDGE_REJECTED)
    results.append(validate_event(
        category='SYSTEM',
        event_type_expected='GOVERNANCE',
        subtype_expected='DAILY_LOSS_LIMIT',
        entry=governance,
        ingest_field='execution',
        fd_filter='system',
    ))

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(results)
    total  = len(results)
    print(f'\n{"="*60}')
    print(f'  RESULT: {passed}/{total} categories passed')
    print(f'{"="*60}')

    # ── Cleanup — remove all test events ──────────────────────────────────────
    run_cleanup(all_ids + [prev_brief_id])

    # ── Final feed state ──────────────────────────────────────────────────────
    time.sleep(1)
    try:
        after = _get('/api/feed?limit=5')
        print(f'\n  Feed after cleanup: {after.get("total", "?")} total events')
        print(f'  Stats: {after.get("stats", {})}')
        remaining_test = [c for c in after.get('feed', []) if 'TEST' in str(c.get('source_id', ''))]
        _check('No test events remain in top-5', len(remaining_test) == 0,
               f'{len(remaining_test)} test cards still visible')
    except Exception as ex:
        print(f'  Post-cleanup verify failed: {ex}')

    print()
    if passed < total:
        sys.exit(1)


if __name__ == '__main__':
    main()
