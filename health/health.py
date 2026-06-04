"""
donna_health.py — NOVA Operational Health Check

Pre-flight and runtime readiness audit for the full NOVA trading system.

Usage:
  python donna_health.py            # full check, formatted report
  python donna_health.py --json     # machine-readable JSON output

API:
  from health.health import run_health_check
  result = run_health_check()
  result['safe_to_trade']  # True / False
  result['sections']       # per-section PASS/WARNING/FAIL breakdown

Future endpoints:
  GET /health     → full report
  GET /preflight  → safe_to_trade + top-line only
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')

# Force UTF-8 stdout so box/arrow chars render on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── Paths ──────────────────────────────────────────────────────────────────────

BASE_DIR  = Path(__file__).parent.parent
MCP_DIR   = BASE_DIR / 'mcp' / 'tradingview'
SS_DIR    = MCP_DIR / 'screenshots'

STATE_FILES = {
    'risk_state':    BASE_DIR / 'data' / 'donna_risk_state.json',
    'state_engine':  BASE_DIR / 'data' / 'donna_state_engine.json',
    'risk_engine':   BASE_DIR / 'data' / 'donna_risk_engine_state.json',
    'alert_state':   BASE_DIR / 'data' / 'donna_alert_state.json',
    'macro_events':  BASE_DIR / 'data' / 'donna_macro_events.json',
    'macro_discord': BASE_DIR / 'data' / 'donna_macro_discord_state.json',
}

# ── Result primitives ──────────────────────────────────────────────────────────

PASS    = 'PASS'
WARNING = 'WARNING'
FAIL    = 'FAIL'
SKIP    = 'SKIP'


def _r(status: str, detail: str, value=None) -> dict:
    return {'status': status, 'detail': detail, 'value': value}


def _read(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return None


def _age_minutes(ts_str: str) -> Optional[float]:
    if not ts_str:
        return None
    try:
        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return (datetime.now(timezone.utc) - ts).total_seconds() / 60
    except Exception:
        return None


def _mcp(cmd: list[str], timeout: int = 10) -> tuple[Optional[dict], Optional[str]]:
    try:
        r = subprocess.run(
            ['node', 'src/cli/index.js'] + cmd,
            cwd=str(MCP_DIR), capture_output=True, text=True, timeout=timeout,
        )
        out = r.stdout.strip()
        if out:
            return json.loads(out), None
        return None, (r.stderr or 'no output')[:120]
    except subprocess.TimeoutExpired:
        return None, 'timeout'
    except Exception as e:
        return None, str(e)[:80]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — INFRASTRUCTURE
# ══════════════════════════════════════════════════════════════════════════════

def _check_credentials() -> list[dict]:
    results = []

    # Discord
    token = os.getenv('DISCORD_BOT_TOKEN', '')
    if token:
        try:
            import requests
            r = requests.get('https://discord.com/api/v10/users/@me',
                headers={'Authorization': f'Bot {token}'}, timeout=8)
            if r.status_code == 200:
                name = r.json().get('username', '?')
                results.append(_r(PASS, f'Discord bot authenticated  ({name})'))
            else:
                results.append(_r(FAIL, f'Discord bot token rejected  (HTTP {r.status_code})'))
        except Exception as e:
            results.append(_r(FAIL, f'Discord API unreachable  ({e})'))
    else:
        results.append(_r(FAIL, 'Discord bot token not set in .env'))

    # Anthropic
    ak = os.getenv('ANTHROPIC_API_KEY', '')
    if ak:
        try:
            from anthropic import Anthropic
            c = Anthropic(api_key=ak)
            model = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
            c.messages.create(model=model, max_tokens=1,
                messages=[{'role': 'user', 'content': 'ping'}])
            results.append(_r(PASS, f'Anthropic API responsive  ({model})'))
        except Exception as e:
            results.append(_r(FAIL, f'Anthropic API failed  ({str(e)[:60]})'))
    else:
        results.append(_r(FAIL, 'Anthropic API key not set in .env'))

    return results


def _check_discord_channels() -> list[dict]:
    results = []
    channels = {
        'DISCORD_CHANNEL_LIVE':          '#live-alerts',
        'DISCORD_CHANNEL_HEADS_UP':      '#heads-up',
        'DISCORD_CHANNEL_EXECUTION':     '#execution',
        'DISCORD_CHANNEL_INVALIDATION':  '#invalidation',
        'DISCORD_CHANNEL_NO_TRADE':      '#no-trade',
        'DISCORD_CHANNEL_MORNING_BRIEF': '#morning-brief',
        'DISCORD_CHANNEL_MACRO':         '#macro-risk',
    }
    for env_key, label in channels.items():
        val = os.getenv(env_key, '')
        if val:
            results.append(_r(PASS, f'{label}  ({val})'))
        else:
            sev = WARNING if env_key != 'DISCORD_CHANNEL_LIVE' else FAIL
            results.append(_r(sev, f'{label}  not configured'))
    return results


def _check_mcp() -> list[dict]:
    results = []

    if not MCP_DIR.exists():
        results.append(_r(FAIL, 'MCP directory not found'))
        return results

    data, err = _mcp(['status'])
    if data and data.get('success') is not False:
        results.append(_r(PASS, f'CDP connected  ({data.get("url", "port 9222")})'))

        # Chart state
        state, serr = _mcp(['state'])
        if state:
            symbol = state.get('symbol', '?')
            tf     = state.get('resolution', '?')
            studies = state.get('studies', [])
            nova   = [s for s in studies if 'NOVA' in s.get('name', '').upper()]
            results.append(_r(PASS, f'Chart: {symbol} / {tf}  —  {len(nova)} NOVA indicator(s)'))
            if not nova:
                results.append(_r(WARNING, 'No NOVA indicator found on chart — reasoning engine blind'))
        else:
            results.append(_r(WARNING, f'Chart state unavailable  ({serr})'))

        # Quote
        quote, qerr = _mcp(['quote'])
        if quote:
            price = quote.get('last') or quote.get('close')
            vol   = quote.get('volume')
            results.append(_r(PASS, f'Live quote: {price}  vol: {vol}'))
        else:
            results.append(_r(WARNING, f'Quote unavailable  ({qerr})'))

    else:
        msg = err or (data or {}).get('error', 'CDP not connected')
        results.append(_r(FAIL, f'TradingView not reachable  —  {msg}'))
        results.append(_r(SKIP, 'Chart / quote checks skipped  (MCP offline)'))

    return results


def _check_screenshot() -> list[dict]:
    # Try to find an existing screenshot (don't trigger a new capture in health check)
    if not SS_DIR.exists():
        return [_r(WARNING, 'Screenshots directory missing  —  first capture will create it')]

    shots = sorted(SS_DIR.glob('*.png'), key=lambda f: f.stat().st_mtime, reverse=True)
    if not shots:
        return [_r(WARNING, 'No screenshots captured yet  —  pipeline untested')]

    latest = shots[0]
    age = (time.time() - latest.stat().st_mtime) / 60
    size_kb = latest.stat().st_size // 1024
    return [_r(PASS, f'Last screenshot: {age:.0f} min ago  ({size_kb}KB  —  {latest.name})')]


def _check_state_files() -> list[dict]:
    results = []
    for key, path in STATE_FILES.items():
        if path.exists():
            d = _read(path)
            if d is not None:
                results.append(_r(PASS, f'{path.name}  ({path.stat().st_size}B)'))
            else:
                results.append(_r(FAIL, f'{path.name}  exists but unreadable'))
        else:
            sev = WARNING if key in ('alert_state', 'macro_discord') else FAIL
            results.append(_r(sev, f'{path.name}  not found  (created on first use)'))

    # Write test
    test_path = BASE_DIR / '_health_write_test.tmp'
    try:
        test_path.write_text('ok')
        test_path.unlink()
        results.append(_r(PASS, 'Filesystem write test passed'))
    except Exception as e:
        results.append(_r(FAIL, f'Filesystem write test failed  ({e})'))

    return results


def _check_render_backend() -> list[dict]:
    url = (os.getenv('RENDER_EXTERNAL_URL') or
           os.getenv('RENDER_URL') or
           os.getenv('DONNA_BACKEND_URL') or '').strip().rstrip('/')
    if not url:
        return [_r(WARNING, 'RENDER_EXTERNAL_URL not set  —  backend reachability not verified')]
    try:
        import requests
        r = requests.get(f'{url}/', timeout=10)
        if r.status_code in (200, 204):
            return [_r(PASS, f'Render backend responding  ({url})')]
        return [_r(WARNING, f'Render backend HTTP {r.status_code}  ({url})')]
    except Exception as e:
        return [_r(FAIL, f'Render backend unreachable  ({e})')]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — MARKET DATA
# ══════════════════════════════════════════════════════════════════════════════

def _check_market_data() -> list[dict]:
    results = []
    risk = _read(STATE_FILES['risk_state']) or {}
    snap = risk.get('market_snapshot', {})

    # Snapshot freshness
    ts  = snap.get('_updated_at') or risk.get('last_updated') or ''
    age = _age_minutes(ts)
    if age is None:
        results.append(_r(FAIL, 'Market snapshot never populated  —  finnhub cycle has not run'))
    elif age < 15:
        results.append(_r(PASS, f'Market snapshot fresh  ({age:.0f} min ago)'))
    elif age < 30:
        results.append(_r(WARNING, f'Market snapshot aging  ({age:.0f} min  —  expected <15)'))
    else:
        results.append(_r(FAIL, f'Market snapshot stale  ({age:.0f} min  —  feed may be down)'))

    # Key instruments
    for sym, label in [('NQ','NQ'), ('ES','ES'), ('VIX','VIX'), ('US10Y','10Y'), ('DXY','DXY')]:
        d = snap.get(sym, {})
        last = d.get('last')
        pct  = d.get('pct')
        if last:
            results.append(_r(PASS, f'{label}: {last}  ({pct:+.1f}%)' if pct is not None else f'{label}: {last}'))
        else:
            results.append(_r(WARNING, f'{label}: no data'))

    # Macro events freshness
    macro = _read(STATE_FILES['macro_events']) or {}
    macro_ts = macro.get('fetched_at') or macro.get('_last_updated') or ''
    macro_age = _age_minutes(macro_ts)
    event_count = len(macro.get('events', []))
    if macro_age is None or event_count == 0:
        results.append(_r(WARNING, 'Economic calendar empty  —  headlines cycle may not have run'))
    elif macro_age < 1440:
        results.append(_r(PASS, f'Economic calendar: {event_count} events  ({macro_age:.0f} min ago)'))
    else:
        results.append(_r(WARNING, f'Economic calendar stale  ({macro_age/60:.0f} hours old)'))

    # API key presence (live test only if keys configured)
    for env_k, label in [('FMP_API_KEY','FMP'), ('FINNHUB_API_KEY','Finnhub')]:
        if os.getenv(env_k):
            results.append(_r(PASS, f'{label} API key configured'))
        else:
            results.append(_r(WARNING, f'{label} API key not in .env  —  feed degraded'))

    # Market regime
    regime = risk.get('market_regime')
    if regime:
        results.append(_r(PASS, f'Market regime: {regime}'))
    else:
        results.append(_r(WARNING, 'Market regime not computed'))

    return results


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — INTELLIGENCE LAYER
# ══════════════════════════════════════════════════════════════════════════════

def _check_intelligence() -> list[dict]:
    results = []

    # compute_macro_state()
    try:
        from delivery.macro_discord import compute_macro_state
        state = compute_macro_state()
        sq    = state.get('session_quality', '?')
        phase = state.get('active_phase', '?')
        vix   = state.get('vix', 0)
        action = state.get('action', '?')
        results.append(_r(PASS,
            f'compute_macro_state()  →  sq={sq}  phase={phase}  vix={vix:.1f}'))
        results.append(_r(PASS, f'Action: {action}'))
    except Exception as e:
        results.append(_r(FAIL, f'compute_macro_state() crashed  ({e})'))

    # Session context evaluator
    try:
        from engines.reasoning import evaluate_session_context
        sc = evaluate_session_context()
        blocked = sc.get('session_blocked', '?')
        trades  = sc.get('daily_trades', '?')
        results.append(_r(PASS,
            f'Session context  →  {sc.get("session")}  blocked={blocked}  trades={trades}'))
    except Exception as e:
        results.append(_r(FAIL, f'evaluate_session_context() crashed  ({e})'))

    # Reasoning engine imports
    try:
        from engines.reasoning import (
            _evaluate_pros_phase, _evaluate_orb_phase,
            _evaluate_ib_alignment, _classify_signal,
        )
        # Smoke test with empty state
        pe = _evaluate_pros_phase({}, {}, {})
        oe = _evaluate_orb_phase({}, {}, {'in_window': False})
        ib = _evaluate_ib_alignment({}, {})
        sc = evaluate_session_context()
        inv = {'invalidated': False, 'reason': '', 'setup_type': 'N/A'}
        sig, setup, rat = _classify_signal(pe, oe, ib, inv, sc)
        results.append(_r(PASS,
            f'Deterministic evaluators operational  pre-signal={sig or "NONE"}'))
    except Exception as e:
        results.append(_r(FAIL, f'Reasoning evaluators crashed  ({e})'))

    # Anti-spam governance
    try:
        from delivery.alert_engine import get_alert_status
        gs = get_alert_status()
        total = gs.get('daily_total', 0)
        cap   = gs.get('daily_max', 20)
        supp  = gs.get('suppressed_today', 0)
        results.append(_r(PASS,
            f'Alert governance  →  {total}/{cap} delivered  {supp} suppressed today'))
    except Exception as e:
        results.append(_r(WARNING, f'Alert governance unreadable  ({e})'))

    return results


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — ALERT SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

def _check_alert_system() -> list[dict]:
    results = []

    token = os.getenv('DISCORD_BOT_TOKEN', '')
    live  = os.getenv('DISCORD_CHANNEL_LIVE', '')
    macro = os.getenv('DISCORD_CHANNEL_MACRO', '')

    # Delivery capability
    if token and (live or macro):
        results.append(_r(PASS, 'Discord delivery: bot token + at least one channel configured'))
    elif token:
        results.append(_r(WARNING, 'Discord bot token set but no channel IDs configured'))
    else:
        results.append(_r(FAIL, 'Discord delivery not configured  —  no alerts will send'))

    # Channel routing audit
    channel_map = {
        'HEADS_UP':        ('DISCORD_CHANNEL_HEADS_UP',      'DISCORD_CHANNEL_LIVE'),
        'EXECUTION_READY': ('DISCORD_CHANNEL_EXECUTION',     'DISCORD_CHANNEL_LIVE'),
        'INVALIDATION':    ('DISCORD_CHANNEL_INVALIDATION',  'DISCORD_CHANNEL_LIVE'),
        'NO_TRADE':        ('DISCORD_CHANNEL_NO_TRADE',      'DISCORD_CHANNEL_LIVE'),
        'SESSION_BRIEF':   ('DISCORD_CHANNEL_MORNING_BRIEF', 'DISCORD_CHANNEL_LIVE'),
        'MACRO':           ('DISCORD_CHANNEL_MACRO',         'DISCORD_CHANNEL_LIVE'),
    }
    fallback_count = 0
    for alert_type, (primary, fallback) in channel_map.items():
        if os.getenv(primary):
            pass  # dedicated channel — ideal
        elif os.getenv(fallback):
            fallback_count += 1

    if fallback_count == 0:
        results.append(_r(PASS, 'All alert types have dedicated channels'))
    else:
        results.append(_r(WARNING, f'{fallback_count} alert type(s) falling back to #live-alerts'))

    # Screenshot pipeline status
    if SS_DIR.exists() and list(SS_DIR.glob('*.png')):
        results.append(_r(PASS, 'Screenshot pipeline: captures exist in directory'))
    else:
        results.append(_r(WARNING, 'Screenshot pipeline: no captures yet  —  untested until MCP active'))

    return results


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — EXECUTION SAFETY
# ══════════════════════════════════════════════════════════════════════════════

def _check_execution_safety() -> tuple[list[dict], bool, str]:
    results   = []
    safe      = True
    fail_reason = ''

    def _fail(detail: str):
        nonlocal safe, fail_reason
        safe = False
        if not fail_reason:
            fail_reason = detail

    now   = datetime.now(timezone.utc)
    today = datetime.now().strftime('%Y-%m-%d')

    # ── State engine ──
    se = _read(STATE_FILES['state_engine']) or {}

    trade_count   = se.get('daily_trade_count', 0)
    loss_hit      = se.get('daily_loss_trade_hit', False)
    trade_perm    = se.get('trade_permission', True)
    state_date    = se.get('state_date', '')
    stop_trading  = se.get('stop_trading', False)

    # Date drift check
    if state_date and state_date != today:
        results.append(_r(WARNING, f'State engine date mismatch: {state_date} vs today {today}  —  may need reset'))
    else:
        results.append(_r(PASS, f'State engine date: {state_date or today}'))

    results.append(_r(PASS if trade_count < 2 else WARNING,
        f'Daily trade count: {trade_count} / 2'))

    if loss_hit:
        _fail('Daily loss limit already hit  —  session closed')
        results.append(_r(FAIL, 'Daily loss limit: HIT  —  no entries permitted'))
    else:
        results.append(_r(PASS, 'Daily loss limit: clear'))

    if not trade_perm:
        _fail('Trade permission disabled')
        results.append(_r(FAIL, 'Trade permission: DISABLED'))
    else:
        results.append(_r(PASS, 'Trade permission: ENABLED'))

    if stop_trading:
        _fail('stop_trading flag is set in state engine')
        results.append(_r(FAIL, 'Stop trading flag: SET'))
    else:
        results.append(_r(PASS, 'Stop trading flag: clear'))

    # ── Risk engine ──
    re = _read(STATE_FILES['risk_engine']) or {}
    if re.get('stop_trading'):
        _fail('stop_trading set in risk engine')
        results.append(_r(FAIL, 'Risk engine stop_trading: SET'))
    else:
        results.append(_r(PASS, 'Risk engine stop_trading: clear'))

    # ── Risk state locks ──
    risk = _read(STATE_FILES['risk_state']) or {}
    macro_lock      = risk.get('macro_lock', False)
    red_folder_lock = risk.get('red_folder_lock', False)
    red_folder_week = risk.get('red_folder_week', False)

    if macro_lock:
        _fail('Macro lock is active in risk state')
        results.append(_r(FAIL, 'Macro lock: ACTIVE'))
    else:
        results.append(_r(PASS, 'Macro lock: clear'))

    if red_folder_lock:
        results.append(_r(WARNING, 'Red folder lock: ACTIVE  —  execution paused near macro event'))
    else:
        results.append(_r(PASS, 'Red folder lock: clear'))

    if red_folder_week:
        results.append(_r(WARNING, 'Red folder week flag: active  —  elevated caution'))
    else:
        results.append(_r(PASS, 'Red folder week: no key events'))

    # ── Alert state — orphaned signals ──
    alert_st = _read(STATE_FILES['alert_state']) or {}
    signals  = alert_st.get('signals', {})
    orphaned = []
    for key, sig in signals.items():
        ts_str = sig.get('last_delivery_time', '')
        age    = _age_minutes(ts_str)
        if age is not None and age > 24 * 60:
            orphaned.append(key)

    if orphaned:
        results.append(_r(WARNING, f'Orphaned signals ({len(orphaned)}): {", ".join(orphaned[:3])}'))
    else:
        results.append(_r(PASS, f'Active signals: {len(signals)}  —  no orphans'))

    if not fail_reason:
        fail_reason = ''

    return results, safe, fail_reason


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SESSION READINESS
# ══════════════════════════════════════════════════════════════════════════════

def _build_session_readiness() -> dict:
    from zoneinfo import ZoneInfo
    now_ny = datetime.now(ZoneInfo('America/New_York'))
    mins   = now_ny.hour * 60 + now_ny.minute

    try:
        from delivery.macro_discord import compute_macro_state
        ms = compute_macro_state()
    except Exception:
        ms = {}

    try:
        from engines.reasoning import evaluate_session_context
        sc = evaluate_session_context()
    except Exception:
        sc = {}

    risk   = _read(STATE_FILES['risk_state']) or {}
    snap   = risk.get('market_snapshot', {})
    vix    = float((snap.get('VIX') or {}).get('last') or 0)
    regime = risk.get('market_regime', '—')

    in_window   = 9 * 60 + 30 <= mins <= 11 * 60
    orb_defined = mins >= 9 * 60 + 32
    ib_locked   = mins >= 10 * 60 + 30

    # ORB readiness
    if not in_window:
        orb_status = 'NOT YET  (09:30 ET)'
    elif not orb_defined:
        orb_status = 'DEFINING  (09:30–09:32 ET)'
    else:
        orb_status = 'DEFINED'

    # Aggressiveness
    sq    = ms.get('session_quality', sc.get('session', '?'))
    phase = ms.get('active_phase', 'CLEAR')
    if vix >= 25 or phase in ('IMMINENT', 'LIVE'):
        aggr = 'REDUCED  (elevated risk)'
    elif sq == 'C':
        aggr = 'REDUCED  (session cap C)'
    elif sq == 'B':
        aggr = 'NORMAL  (session cap B)'
    else:
        aggr = 'NORMAL'

    # VIX label
    if vix == 0:
        vix_label = 'no data'
    elif vix >= 30:
        vix_label = f'{vix:.1f}  CRITICAL  (>30)'
    elif vix >= 25:
        vix_label = f'{vix:.1f}  ELEVATED  (>25)'
    elif vix >= 20:
        vix_label = f'{vix:.1f}  CAUTION  (>20)'
    else:
        vix_label = f'{vix:.1f}  normal'

    next_event = risk.get('next_event') or ms.get('next_event', {})
    if isinstance(next_event, dict):
        next_event = next_event.get('title', 'none')

    return {
        'time_et':             now_ny.strftime('%H:%M ET'),
        'session':             sc.get('session', 'UNKNOWN'),
        'in_trading_window':   in_window,
        'session_quality':     ms.get('session_quality', '?'),
        'sq_reason':           ms.get('sq_reason', ''),
        'macro_risk':          risk.get('macro_risk', '—'),
        'active_phase':        phase,
        'next_event':          next_event,
        'vix':                 vix_label,
        'regime':              regime,
        'orb_status':          orb_status,
        'ib_locked':           ib_locked,
        'execution_aggressive': aggr,
        'action':              ms.get('action', '—'),
        'trades_today':        sc.get('daily_trades', 0),
        'loss_hit':            sc.get('daily_loss_hit', False),
        'session_blocked':     sc.get('session_blocked', False),
    }


# ══════════════════════════════════════════════════════════════════════════════
# AGGREGATOR
# ══════════════════════════════════════════════════════════════════════════════

def run_health_check() -> dict:
    started = time.time()

    # Run all sections
    creds     = _check_credentials()
    channels  = _check_discord_channels()
    mcp       = _check_mcp()
    screenshot= _check_screenshot()
    files     = _check_state_files()
    backend   = _check_render_backend()
    market    = _check_market_data()
    intel     = _check_intelligence()
    alerts    = _check_alert_system()
    exec_res, safe_to_trade, fail_reason = _check_execution_safety()
    readiness = _build_session_readiness()

    def _worst(checks: list[dict]) -> str:
        order = {FAIL: 3, WARNING: 2, PASS: 1, SKIP: 0}
        return max((c.get('status', SKIP) for c in checks), key=lambda s: order.get(s, 0), default=SKIP)

    sections = {
        'credentials':       {'label': 'API Credentials',       'checks': creds},
        'discord_channels':  {'label': 'Discord Channels',      'checks': channels},
        'mcp':               {'label': 'TradingView MCP',        'checks': mcp},
        'screenshot':        {'label': 'Screenshot Pipeline',    'checks': screenshot},
        'state_files':       {'label': 'State Files',            'checks': files},
        'backend':           {'label': 'Render Backend',         'checks': backend},
        'market_data':       {'label': 'Market Data',            'checks': market},
        'intelligence':      {'label': 'Intelligence Layer',     'checks': intel},
        'alert_system':      {'label': 'Alert System',           'checks': alerts},
        'execution_safety':  {'label': 'Execution Safety',       'checks': exec_res},
    }
    for k, s in sections.items():
        s['status'] = _worst(s['checks'])

    elapsed = round(time.time() - started, 1)

    return {
        'safe_to_trade':    safe_to_trade,
        'fail_reason':      fail_reason,
        'sections':         sections,
        'session_readiness': readiness,
        'elapsed_seconds':  elapsed,
        'checked_at':       datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# FORMATTED OUTPUT
# ══════════════════════════════════════════════════════════════════════════════

_ICONS = {PASS: 'PASS   ', WARNING: 'WARN   ', FAIL: 'FAIL   ', SKIP: 'SKIP   '}
_SEP   = '-' * 56


def _print_section(label: str, checks: list[dict], status: str) -> None:
    print(f'\n  [{status:7}]  {label}')
    print(f'  {_SEP}')
    for c in checks:
        icon = _ICONS.get(c['status'], '?      ')
        print(f'    {icon}  {c["detail"]}')


def print_report(result: dict) -> None:
    r    = result['session_readiness']
    safe = result['safe_to_trade']

    print()
    print('  ======================================================')
    print(f'  NOVA OPERATIONAL HEALTH CHECK  --  {r["time_et"]}')
    print('  ======================================================')

    sections = result['sections']
    for key in ['credentials', 'discord_channels', 'mcp', 'screenshot',
                'state_files', 'backend', 'market_data', 'intelligence',
                'alert_system', 'execution_safety']:
        s = sections[key]
        _print_section(s['label'], s['checks'], s['status'])

    # Session readiness
    print(f'\n  [READINESS]  Trading Session State')
    print(f'  {_SEP}')
    fields = [
        ('Session',             r['session']),
        ('Time',                r['time_et']),
        ('In trading window',   str(r['in_trading_window'])),
        ('Session quality',     f'{r["session_quality"]}  —  {r["sq_reason"]}'),
        ('Macro risk',          r['macro_risk'].upper()),
        ('Active phase',        r['active_phase']),
        ('Next event',          str(r['next_event'])),
        ('VIX',                 r['vix']),
        ('Regime',              r['regime']),
        ('ORB status',          r['orb_status']),
        ('IB window locked',    str(r['ib_locked'])),
        ('Aggressiveness',      r['execution_aggressive']),
        ('Trades today',        str(r['trades_today'])),
        ('Loss limit hit',      str(r['loss_hit'])),
        ('Session blocked',     str(r['session_blocked'])),
        ('NOVA action',         r['action']),
    ]
    for label, val in fields:
        print(f'    {label:<24}  {val}')

    # Final verdict
    print(f'\n  {_SEP}')
    if safe:
        print('  SAFE_TO_TRADE: TRUE')
    else:
        print('  SAFE_TO_TRADE: FALSE')
        print(f'  Reason: {result["fail_reason"]}')

    # Section summary
    print()
    for key in ['credentials', 'mcp', 'market_data', 'intelligence',
                'alert_system', 'execution_safety']:
        s = sections[key]
        print(f'    {s["status"]:7}  {s["label"]}')

    print(f'\n  Completed in {result["elapsed_seconds"]}s')
    print()


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    as_json = '--json' in sys.argv
    result  = run_health_check()
    if as_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_report(result)
