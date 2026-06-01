"""
test_macro_discord.py — NOVA Macro Intelligence feed visual inspection.

Sends 4 test alerts to #macro-risk using the refined embed layer.
Run:  python test_macro_discord.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

BOT_TOKEN  = os.getenv('DISCORD_BOT_TOKEN', '').strip()
CHANNEL_ID = (
    os.getenv('DISCORD_CHANNEL_MACRO', '').strip() or
    os.getenv('DISCORD_CHANNEL_LIVE', '').strip()
)

NY_TZ       = ZoneInfo('America/New_York')
DISCORD_API = 'https://discord.com/api/v10'

COLORS = {
    'CRITICAL': 0xFF0000,
    'HIGH':     0xFF4444,
    'MEDIUM':   0xFFBB33,
    'BRIEF':    0x9B59B6,
}


def now_et() -> str:
    return datetime.now(NY_TZ).strftime('%H:%M ET')


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def field(name: str, value: str, inline: bool = True) -> dict:
    return {'name': name, 'value': value, 'inline': inline}


def spacer() -> dict:
    return {'name': '​', 'value': '​', 'inline': False}


def footer(tag: str) -> dict:
    return {'text': f'NOVA Macro  ·  {tag}  ·  {now_et()}'}


def send(embed: dict) -> dict:
    r = requests.post(
        f'{DISCORD_API}/channels/{CHANNEL_ID}/messages',
        headers={'Authorization': f'Bot {BOT_TOKEN}', 'Content-Type': 'application/json'},
        json={'embeds': [embed]},
        timeout=20,
    )
    return {'status': r.status_code, 'ok': r.status_code in (200, 201),
            'err': r.text[:120] if r.status_code not in (200, 201) else ''}


# ── 1. Morning Macro Brief ─────────────────────────────────────────────────────

def morning_brief() -> dict:
    events = (
        '\U0001F534 **08:30**  Core PCE Price Index YoY  —  2.6% f / 2.8% p\n'
        '\U0001F534 **08:30**  Personal Income MoM  —  +0.4% f / +0.5% p\n'
        '\U0001F7E1 **10:00**  UMich Consumer Sentiment  —  68.8 f / 67.4 p\n'
        '\U0001F534 **11:30**  Fed Governor Waller Speech  —  lean unknown'
    )
    market = (
        'VIX 18.4 (−0.8%)  ·  NQ +0.3%  ·  ES +0.2%  ·  10Y 4.31%  ·  Regime: TRENDING UP'
    )

    return {
        'title':       'NOVA MACRO BRIEF  ·  FRIDAY MAY 30',
        'description': 'Session prep  ·  NY open 09:30 ET',
        'color':       COLORS['BRIEF'],
        'fields': [
            field('Events', events, inline=False),
            spacer(),
            field('Market', market, inline=False),
            spacer(),
            field(
                'Session Cap: B',
                'PCE at open + Fed speaker during session.\n'
                'No entries before 09:40 ET. ORB context valid post-08:45 only.',
                inline=False,
            ),
        ],
        'footer':    footer('Daily Brief'),
        'timestamp': ts(),
    }


# ── 2. HIGH — Core PCE Approaching ────────────────────────────────────────────

def high_event() -> dict:
    return {
        'title':       '⚠️  CORE PCE PRICE INDEX',
        'description': '08:30 ET  ·  APPROACHING — 28 MIN  ·  HIGH',
        'color':       COLORS['HIGH'],
        'fields': [
            field('Forecast', '2.6% YoY'),
            field('Prev',     '2.8% YoY'),
            spacer(),
            field(
                'NOVA',
                'PCE drives rate repricing — expect directional expansion.\n'
                'ORB unreliable pre-data.\n'
                'Entry window opens ~09:45 ET if reaction is clean.',
                inline=False,
            ),
        ],
        'footer':    footer('BEA  ·  Scheduled Macro'),
        'timestamp': ts(),
    }


# ── 3. CRITICAL — Breaking Fed Headline ───────────────────────────────────────

def critical_breaking() -> dict:
    return {
        'title':       '\U0001F6A8  FED SIGNALS RATE PAUSE REVERSAL',
        'description': (
            'Waller signals rate cuts delayed to Q4 2026 — '
            'services inflation cited as persistent. Markets repricing aggressively.'
        ),
        'color':       COLORS['CRITICAL'],
        'fields': [
            field('Severity', 'CRITICAL'),
            field('Source',   'Bloomberg / WSJ'),
            field(
                'Repricing',
                'June cut probability: 42% → 18%\n'
                'Bond yields +8bps  ·  NQ futures −0.9%',
                inline=False,
            ),
            spacer(),
            field(
                'NOVA',
                'Stand aside. Allow initial spike to settle.\n'
                'Reassess session direction at 09:45 ET minimum.',
                inline=False,
            ),
        ],
        'footer':    footer('Breaking'),
        'timestamp': ts(),
    }


# ── 4. Volatility Warning ──────────────────────────────────────────────────────

def vix_warning() -> dict:
    return {
        'title':       '⚠️  VIX 26  ·  VOLATILITY WARNING',
        'description': 'Elevated conditions active  ·  Regime: VOLATILE',
        'color':       COLORS['HIGH'],
        'fields': [
            field('VIX',    '26.4  (+8.2%)'),
            field('Regime', 'VOLATILE'),
            field('NQ',     '−1.8%'),
            field('ES',     '−1.1%'),
            spacer(),
            field(
                'NOVA',
                'ORB reliability degraded. Grade A only.\n'
                'Size −50%. Observe first 15 min.\n'
                'Widen stops 1.5× for elevated intraday swings.',
                inline=False,
            ),
        ],
        'footer':    footer('VIX Monitor'),
        'timestamp': ts(),
    }


# ── Runner ─────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        print('ERROR: DISCORD_BOT_TOKEN not set.')
        print('  Run:  $env:DISCORD_BOT_TOKEN = "your-token"')
        sys.exit(1)

    if not CHANNEL_ID:
        print('ERROR: DISCORD_CHANNEL_MACRO (or DISCORD_CHANNEL_LIVE) not set.')
        sys.exit(1)

    print(f'Channel: {CHANNEL_ID}')
    print()

    suite = [
        ('Morning Brief      ', morning_brief),
        ('HIGH  — Core PCE   ', high_event),
        ('CRITICAL — Breaking', critical_breaking),
        ('Volatility Warning ', vix_warning),
    ]

    for label, builder in suite:
        embed  = builder()
        result = send(embed)
        status = f'OK  (HTTP {result["status"]})' if result['ok'] else f'FAIL (HTTP {result["status"]}) {result["err"]}'
        print(f'  {label}  {status}')
        time.sleep(1.2)

    print()
    print('Done. Inspect #macro-risk.')


if __name__ == '__main__':
    main()
