"""
verify_discord.py — NOVA Discord delivery verification script.

Run this after adding DISCORD_BOT_TOKEN and DISCORD_CHANNEL_LIVE to .env.
It checks configuration, sends a test embed, and confirms screenshot attachment.

Usage:
    python scripts/verify_discord.py
"""
import sys
import os
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

# ── Load env ───────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

# ── Check 1: imports ───────────────────────────────────────────
print('\n── NOVA Discord Verification ──────────────────────────\n')

try:
    from donna_alert_engine import (
        AlertData, deliver_alert, get_alert_status, build_embed,
        send_discord, capture_screenshot,
        HEADS_UP, EXECUTION_READY, INVALIDATION, NO_TRADE,
    )
    print('✅  Alert engine imported')
except Exception as e:
    print(f'❌  Alert engine import failed: {e}')
    sys.exit(1)

# ── Check 2: config ────────────────────────────────────────────
from donna_config import (
    DISCORD_BOT_TOKEN,
    DISCORD_CHANNEL_LIVE,
    ALERT_SCREENSHOT,
)

if DISCORD_BOT_TOKEN:
    token_preview = DISCORD_BOT_TOKEN[:12] + '...'
    print(f'✅  DISCORD_BOT_TOKEN    {token_preview}')
else:
    print('❌  DISCORD_BOT_TOKEN    not set — add to .env')

if DISCORD_CHANNEL_LIVE:
    print(f'✅  DISCORD_CHANNEL_LIVE {DISCORD_CHANNEL_LIVE}')
else:
    print('❌  DISCORD_CHANNEL_LIVE not set — add to .env')

if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_LIVE:
    print('\nCannot proceed — configure .env first (see .env.example).\n')
    sys.exit(1)

# ── Check 3: screenshot ────────────────────────────────────────
print(f'\n── Screenshot pipeline ─────────────────────────────────')
if ALERT_SCREENSHOT:
    print('Capturing TradingView screenshot...')
    photo = capture_screenshot()
    if photo:
        size_kb = photo.stat().st_size // 1024
        print(f'✅  Screenshot captured: {photo.name} ({size_kb} KB)')
    else:
        print('⚠️   Screenshot failed (TradingView may not be open) — alert will send without image')
        photo = None
else:
    print('ℹ️   ALERT_SCREENSHOT=false — skipping')
    photo = None

# ── Check 4: embed preview ─────────────────────────────────────
print(f'\n── Embed preview ───────────────────────────────────────')
test_data = AlertData(
    alert_type=HEADS_UP,
    symbol='ES',
    setup_type='PROS_LONG',
    direction='LONG',
    priority='standard',
    session='NY_OPEN',
    session_quality='A',
    ib_draw='IB HIGH',
    daily_bias='BULLISH',
    htf_4h_bias='BULLISH',
    grade='A',
    timeframe='30M PROS',
    time_to_close='3 min to close',
    watch_time='Watch for confirmation at 10:00 AM ET',
    notes='VERIFICATION TEST — delivery pipeline check',
)

embed = build_embed(test_data)
print(f'  Title:  {embed["title"]}')
print(f'  Color:  #{embed["color"]:06X}')
print(f'  Fields: {len(embed.get("fields", []))}')
print(f'  Footer: {embed.get("footer", {}).get("text", "")}')
print('✅  Embed built')

# ── Check 5: Discord delivery ──────────────────────────────────
print(f'\n── Discord delivery ────────────────────────────────────')
print(f'  Channel: {DISCORD_CHANNEL_LIVE}')
print('  Sending test embed...')

result = send_discord(test_data, photo)

if result.get('ok'):
    print('✅  Discord delivery SUCCESS')
    if photo:
        print('✅  Screenshot attached inside embed')
else:
    print(f'❌  Discord delivery FAILED: {result.get("error")}')
    if 'status' in result:
        print(f'    HTTP {result["status"]}')
        if result['status'] == 401:
            print('    → Token invalid or missing "Bot " prefix')
        elif result['status'] == 403:
            print('    → Bot lacks permission (Send Messages / Embed Links / Attach Files)')
        elif result['status'] == 404:
            print('    → Channel ID not found — check DISCORD_CHANNEL_LIVE')

# ── Summary ────────────────────────────────────────────────────
print(f'\n── Alert governance status ─────────────────────────────')
status = get_alert_status()
for k, v in status.items():
    print(f'  {k:<28} {v}')

print('\n────────────────────────────────────────────────────────\n')
