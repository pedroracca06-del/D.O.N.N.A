"""
scripts/test_feed_sync.py — End-to-end feed sync verification

Pushes one synthetic signal to Render's /api/feed/ingest, then polls
/api/feed/health to confirm the entry arrived.

Usage (from repo root):
    python scripts/test_feed_sync.py

Requirements:
    NOVA_RENDER_URL and NOVA_INGEST_SECRET must be set in local .env
    Render must have NOVA_INGEST_SECRET set to the same value.
    Render service must be running (not sleeping).

Exit codes:
    0 — entry confirmed on Render
    1 — push failed or entry not found after timeout
"""
import sys
import time
import json
from pathlib import Path

# Load .env before importing config
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from core.config import NOVA_RENDER_URL, NOVA_INGEST_SECRET

# ── Pre-flight ────────────────────────────────────────────────────────────────

def fail(msg: str) -> None:
    print(f'FAIL  {msg}')
    sys.exit(1)


if not NOVA_RENDER_URL:
    fail('NOVA_RENDER_URL is not set in .env')

if not NOVA_INGEST_SECRET:
    fail('NOVA_INGEST_SECRET is not set in .env')

print(f'Target : {NOVA_RENDER_URL}')
print(f'Secret : {"*" * 8}{NOVA_INGEST_SECRET[-4:]}')
print()

# ── Build test entry ──────────────────────────────────────────────────────────

import random
_ts_ms  = int(time.time() * 1000)
_tag    = random.randint(100, 999)
TEST_ID = f'SIG_SYNCTEST_{_ts_ms}-{_tag}'

from datetime import datetime
from zoneinfo import ZoneInfo
_now_et = datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M:%S ET')
_today  = datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')

test_signal = {
    'id':              TEST_ID,
    'timestamp':       datetime.utcnow().isoformat() + 'Z',
    'timestamp_et':    _now_et,
    'date':            _today,
    'symbol':          'MES',
    'price':           5800.0,
    'session':         'NY_AM',
    'session_quality': 'A',
    'alert_type':      'HEADS_UP',
    'alert_required':  True,
    'grade':           'B',
    'direction':       'LONG',
    'setup_type':      'PROS_OTE',
    'strategy_family': 'PROS',
    'claude_rationale': f'Feed sync test — id={TEST_ID}',
    'pre_rationale':   'Synthetic entry for end-to-end sync verification',
    'mr2_state':       'BULLISH',
    'mr2_score':       3,
    'dp_dominance':    'BULLISH',
    'dp_conviction':   'HIGH',
    'reasoning_trace_id': '',
    'screenshot':      '',
}

# ── Step 1: Push ──────────────────────────────────────────────────────────────

try:
    import requests
except ImportError:
    fail('requests package not installed: pip install requests')

print(f'PUSH  {TEST_ID}')

try:
    r = requests.post(
        NOVA_RENDER_URL + '/api/feed/ingest',
        json    = {'signal': test_signal},
        headers = {'X-Nova-Ingest-Secret': NOVA_INGEST_SECRET},
        timeout = 15,
    )
except requests.exceptions.ConnectionError:
    fail(f'Could not connect to {NOVA_RENDER_URL} — is the service running?')
except requests.exceptions.Timeout:
    fail('Request timed out after 15s — Render may be cold-starting, retry in 30s.')

if r.status_code == 401:
    fail('401 Unauthorized — NOVA_INGEST_SECRET does not match Render env var.')
if r.status_code == 503:
    fail('503 — Ingest not configured on Render (NOVA_INGEST_SECRET not set in Render env vars).')
if r.status_code != 200:
    fail(f'HTTP {r.status_code}: {r.text}')

resp = r.json()
print(f'OK    ingest response: {json.dumps(resp)}')

if resp.get('signal_id') != TEST_ID:
    fail(f'signal_id mismatch: expected {TEST_ID}, got {resp.get("signal_id")}')

# ── Step 2: Verify via health ─────────────────────────────────────────────────

print()
print('POLL  /api/feed/health ...')

deadline = time.time() + 10
confirmed = False
while time.time() < deadline:
    try:
        h = requests.get(NOVA_RENDER_URL + '/api/feed/health', timeout=8).json()
        if h.get('last_signal_id') == TEST_ID:
            confirmed = True
            break
    except Exception:
        pass
    time.sleep(1)

if not confirmed:
    fail(f'Health endpoint did not reflect {TEST_ID} within 10s.')

print(f'OK    health.last_signal_id = {h["last_signal_id"]}')
print(f'OK    health.last_ingest_ts = {h["last_ingest_ts"]}')
print(f'OK    health.signal_count   = {h["signal_count"]}')

# ── Step 3: Verify via feed ───────────────────────────────────────────────────

print()
print('POLL  /api/feed?limit=1 ...')

try:
    feed_resp = requests.get(NOVA_RENDER_URL + '/api/feed', params={'limit': 1}, timeout=8).json()
    top = (feed_resp.get('feed') or [None])[0]
    if top and top.get('source_id') == TEST_ID:
        print(f'OK    top feed card source_id = {top["source_id"]}')
        print(f'OK    top feed card subtype    = {top.get("subtype")}')
        print(f'OK    top feed card rationale  = {top.get("claude_rationale","")[:60]}')
    else:
        src = top.get('source_id') if top else None
        print(f'WARN  top feed card is {src}, not the test entry')
        print('      (normal if Render has newer real signals)')
except Exception as e:
    print(f'WARN  feed check error: {e}')

# ── Done ──────────────────────────────────────────────────────────────────────

print()
print('PASS  End-to-end sync verified.')
print(f'      Local signal → Render feed in < 1 push cycle.')
print()
print('Next: set NOVA_RENDER_URL and NOVA_INGEST_SECRET in .env,')
print('      then restart the monitor — every new signal will push automatically.')
