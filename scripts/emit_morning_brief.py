"""
emit_morning_brief.py — Manually emit a test MORNING_BRIEF intelligence event.

Writes to the local intelligence log AND pushes to the Render feed via ingest API.
Usage:
    python scripts/emit_morning_brief.py
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Setup ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault('DONNA_DATA_DIR', str(ROOT / 'data'))

NY_TZ = ZoneInfo('America/New_York')

# ── Build the test event ───────────────────────────────────────────────────────
now_ny = datetime.now(NY_TZ)
eid    = f'INTEL_{int(time.time() * 1000)}_{random.randint(100, 999)}'
ts     = now_ny.strftime('%Y-%m-%d %H:%M:%S ET')

event = {
    'id':            eid,
    'timestamp_et':  ts,
    'event_type':    'INTELLIGENCE',
    'subtype':       'MORNING_BRIEF',
    'session':       'NY_OPEN',

    # Morning Brief fields
    'thesis':        'Market structure favours longs above 21,200 NQ. PDH at 21,340 is the primary draw. ES accepted above monthly open — bullish lean until structure fails.',
    'brief_text':    'NQ held overnight range and is opening above PDH. ES structure is constructive with price above the monthly open at 5,820. Primary draw is the ONH at 21,340 for NQ. Participation context shows RVOL tracking 1.2x — above average but not extreme. No red-folder events until 14:00 ET (FOMC minutes). Bias is long above 21,200 with invalidation at 21,080 (ONL).',
    'liquidity_draw': 'ONH 21,340 (NQ) / PDH 5,883 (ES)',
    'participation':  'RVOL 1.2x — ABOVE_AVERAGE',
    'macro_risk':     'LOW',
    'session_narrative': 'Clean overnight range. Price opened inside yesterday\'s range on ES, above on NQ. No gap fill needed. Directional bias is long with confluence from MR2 score +7 (BULLISH_LEANING) and overnight acceptance above prior day range.',
    'key_question':  'Does NQ sustain above 21,200 on first pullback? That is the long trigger.',

    # Evidence fields
    'thesis_state':         'BULLISH_LEANING',
    'thesis_state_prev':    '',
    'confidence':           'CONDITIONAL',
    'primary_driver':       'MARKET_STRUCTURE',
    'confirming_evidence':  ['Price above monthly open (ES)', 'ONH untapped (NQ)', 'RVOL > 1.0x'],
    'conflicting_evidence': ['FOMC minutes 14:00 ET — uncertainty cap'],
    'bull_score':           7,
    'bear_score':           3,
    'major_conflict':       False,
}

print('=' * 60)
print('MORNING_BRIEF test event')
print('=' * 60)
print(json.dumps(event, indent=2))
print()

# ── Step 1: Write to local intelligence log ────────────────────────────────────
try:
    from core.config import INTELLIGENCE_LOG_FILE
    data: list = []
    if INTELLIGENCE_LOG_FILE.exists():
        raw = json.loads(INTELLIGENCE_LOG_FILE.read_text(encoding='utf-8'))
        data = raw if isinstance(raw, list) else []
    data.insert(0, event)
    INTELLIGENCE_LOG_FILE.write_text(json.dumps(data[:500], indent=2), encoding='utf-8')
    print(f'[1] Written to {INTELLIGENCE_LOG_FILE}  ({len(data)} total entries)')
except Exception as e:
    print(f'[1] LOCAL WRITE FAILED: {e}')
    sys.exit(1)

# ── Step 2: Verify local feed ──────────────────────────────────────────────────
try:
    from services.feed import build_feed
    result = build_feed(limit=5, event_type='INTELLIGENCE')
    cards  = result.get('feed', [])
    first  = cards[0] if cards else {}
    print(f'[2] /api/feed?event_type=INTELLIGENCE → {result["total"]} cards')
    print(f'    First card: event_type={first.get("event_type")} subtype={first.get("subtype")} ts={first.get("timestamp_et")}')
    print(f'    Summary: {first.get("claude_rationale", "")[:100]}')
except Exception as e:
    print(f'[2] LOCAL FEED VERIFY FAILED: {e}')

print()

# ── Step 3: POST to Render ─────────────────────────────────────────────────────
render_url = os.getenv('NOVA_RENDER_URL', '').rstrip('/')
ingest_secret = os.getenv('NOVA_INGEST_SECRET', '')

if not render_url or not ingest_secret:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
        render_url    = os.getenv('NOVA_RENDER_URL', '').rstrip('/')
        ingest_secret = os.getenv('NOVA_INGEST_SECRET', '')
    except Exception:
        pass

if not render_url:
    print('[3] NOVA_RENDER_URL not set — skipping Render push')
    sys.exit(0)

import urllib.request

body = json.dumps({'intelligence': event}).encode()
req  = urllib.request.Request(
    f'{render_url}/api/feed/ingest',
    data=body,
    headers={
        'Content-Type':       'application/json',
        'X-Nova-Ingest-Secret': ingest_secret,
    },
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        resp_data = json.loads(resp.read())
    print(f'[3] Render ingest response: {resp_data}')
    intel_id = resp_data.get('intelligence_id', '')
    if intel_id:
        print(f'    intelligence_id: {intel_id}  ✓')
    else:
        print('    WARNING: intelligence_id empty — check endpoint is deployed')
except Exception as e:
    print(f'[3] Render POST failed: {e}')
    sys.exit(1)

# ── Step 4: Verify on Render ───────────────────────────────────────────────────
time.sleep(1)
try:
    verify_req = urllib.request.Request(
        f'{render_url}/api/feed?event_type=INTELLIGENCE&limit=3',
        headers={'Accept': 'application/json'},
    )
    with urllib.request.urlopen(verify_req, timeout=20) as resp:
        verify = json.loads(resp.read())
    cards   = verify.get('feed', [])
    total   = verify.get('total', 0)
    first   = cards[0] if cards else {}
    print()
    print(f'[4] Render /api/feed?event_type=INTELLIGENCE → {total} cards')
    print(f'    First card: event_type={first.get("event_type")} subtype={first.get("subtype")}')
    print(f'    ID match: {first.get("source_id") == eid}  (expected {eid})')
    print(f'    Summary: {first.get("claude_rationale","")[:120]}')
except Exception as e:
    print(f'[4] Render verify failed: {e}')

print()
print('Done. Open Alerts → Intelligence in the dashboard to see the card.')
