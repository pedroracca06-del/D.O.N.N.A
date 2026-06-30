from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import requests

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse

from core.config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_ASSISTANT_MODEL,
    TELEGRAM_BOT_TOKEN, TELEGRAM_ALERT_MODE, FOREX_FACTORY_NOTES_URL,
    FINNHUB_API_KEY, FMP_API_KEY, ALPHA_VANTAGE_API_KEY,
    RISK_STATE_FILE, ALERTS_FILE, ASSISTANT_FILE, SETTINGS_FILE, MACRO_EVENTS_FILE,
    MORNING_BRIEF_FILE, NY_TZ, GROK_INTEL_FILE,
    CACHE, now_ny, utc_now_iso, session_label, safe_float,
    send_telegram_message,
)
from core.state import (
    ensure_files,
    load_risk_state, save_risk_state,
    load_alert_history, save_alert_history,
    load_assistant_state, save_assistant_state,
    load_settings,
    load_macro_events,
    load_journal, save_journal, compute_journal_stats,
    read_json_file, write_json_file,
)
from engines.engines import (
    build_harvey_payload, build_dashboard_payload,
    build_scenario_engine, build_performance_memory,
    build_market_driver_engine, build_morning_edge, build_session_significance,
    get_live_major_indexes, get_live_market_data, get_live_movers,
    get_live_calendar, get_live_earnings, get_live_news, get_live_futures_macro_pulse,
    send_morning_brief, get_quote_with_fallback,
)
from engines.signals import process_signal

try:
    from delivery.alert_engine import (
        deliver_alert, AlertData, get_alert_status, start_setup_monitor,
        HEADS_UP, EXECUTION_READY, INVALIDATION, NO_TRADE,
    )
    _ALERT_ENGINE_AVAILABLE = True
except Exception:
    _ALERT_ENGINE_AVAILABLE = False
    def deliver_alert(data, **kw):  return {'delivered': False, 'error': 'alert engine unavailable'}
    def get_alert_status():         return {}
    def start_setup_monitor(**kw):  pass

try:
    from services.execution import (
        execute_signal,
        get_account, get_positions,
        close_position, close_all_positions, close_all_positions_eod,
        cancel_all_orders, has_open_journal_match,
        check_execution_governance, log_governance_rejection,
        get_today_trade_count,
        get_execution_status,
        check_position_outcomes,
        sync_positions_from_alpaca,
        reconcile_positions_from_alpaca,
        set_macro_lock, set_red_folder_lock,
        disable_trade_permission, enable_trade_permission,
        get_rejections,
    )
    _EXECUTION_AVAILABLE = True
except Exception:
    _EXECUTION_AVAILABLE = False
    def execute_signal(r):                  return {'status': 'unavailable'}
    def get_account():                      return {'available': False}
    def get_positions():                    return []
    def cancel_all_orders():                return {'status': 'unavailable', 'cancelled': 0}
    def has_open_journal_match(symbol):     return False
    def check_execution_governance(d, p, i): return {'allowed': False, 'code': 'EXECUTION_UNAVAILABLE', 'reason': 'execution not loaded'}
    def log_governance_rejection(c, r, d, p=None): pass
    def close_position(s):                  return {'status': 'unavailable'}
    def close_all_positions():              return {'status': 'unavailable'}
    def close_all_positions_eod():          return 0
    def get_today_trade_count():            return 0
    def get_execution_status():             return {'available': False}
    def check_position_outcomes():          return 0
    def sync_positions_from_alpaca():       pass
    def reconcile_positions_from_alpaca():  pass
    def get_rejections(limit=50):           return []
    def set_macro_lock(a, r=''):            pass
    def set_red_folder_lock(a, e=''):       pass
    def disable_trade_permission(r=''):     pass
    def enable_trade_permission():          pass

from engines.analytics import compute_analytics, validate_trade

from services.assistant import (
    ASSISTANT_SYSTEM_PROMPT, call_assistant_llm, apply_assistant_action,
)
from ui.html import DASHBOARD_HTML

try:
    from services.news import process_news_guard_cycle, get_grok_intelligence
except Exception:
    def process_news_guard_cycle():
        return None
    def get_grok_intelligence():
        return {}

try:
    from engines.risk_engine import (
        build_risk_engine_payload, reset_stop_trading,
        update_re_settings, load_re_state,
    )
    _RISK_ENGINE_AVAILABLE = True
except Exception:
    _RISK_ENGINE_AVAILABLE = False
    def build_risk_engine_payload(*a, **kw):
        return {'stop_trading': False, 'stop_reason': '', 'position_size': {}, 'rr': {}, 'drawdown': {}, 'session_losses': {}}
    def reset_stop_trading():
        return {'status': 'ok', 'stop_trading': False}
    def update_re_settings(**kw):
        return {}
    def load_re_state():
        return {'account_size': 25000.0, 'risk_pct': 1.0}

try:
    from services.headlines import process_headlines_cycle, check_todays_breaking_events
except Exception:
    def process_headlines_cycle():
        return None
    def check_todays_breaking_events():
        return {'events_found': 0, 'high_events': [], 'risk_escalated': False,
                'red_folder': False, 'error': 'donna_headlines not available'}

try:
    from services.finnhub import process_finnhub_cycle
except Exception:
    def process_finnhub_cycle():
        return None

try:
    from delivery.macro_discord import (
        run_macro_calendar_check,
        run_macro_morning_brief,
        run_breaking_news_check,
    )
    _MACRO_DISCORD_AVAILABLE = True
except Exception as _mde:
    print(f'[main] donna_macro_discord unavailable: {_mde}')
    _MACRO_DISCORD_AVAILABLE = False

try:
    from core.state_engine import state as _donna_state
    _STATE_ENGINE_AVAILABLE = True
except Exception as _se_err:
    print(f'[main] donna_state_engine unavailable: {_se_err}')
    _STATE_ENGINE_AVAILABLE = False
    class _FallbackState:
        def get_state(self):   return {}
        def get(self, k, d=None): return d
        def get_trade_count(self): return 0
    _donna_state = _FallbackState()  # type: ignore[assignment]

app = FastAPI(title='NOVA v5.0 Live Market Core', version='5.0')
_sse_clients: list[asyncio.Queue] = []

_GROK_API_KEY      = os.getenv('GROK_API_KEY', '').strip()
_GROK_INTEL_FILE   = GROK_INTEL_FILE  # /data/ persistent disk via DONNA_DATA_DIR
_GROK_INTEL_PROMPT = (
    'You are a financial markets AI with live access to X/Twitter and current news. '
    'Return ONLY valid JSON with these fields:\n'
    '{\n'
    '  "top_story": "<headline of the single most market-moving story right now>",\n'
    '  "top_story_summary": "<2-3 sentence summary of that story and its market impact>",\n'
    '  "market_sentiment": "<one of: BULLISH | BEARISH | NEUTRAL | MIXED>",\n'
    '  "sentiment_reason": "<1-2 sentences explaining the sentiment>",\n'
    '  "donna_trade_read": "<actionable trading implication for today — what to watch, avoid, or lean into>",\n'
    '  "key_names_to_watch": ["TICKER1", "TICKER2", "TICKER3"],\n'
    '  "x_market_chatter": "<dominant narrative traders and financial accounts are discussing on X/Twitter right now — 1 sentence>",\n'
    '  "x_stress_signal": "<any unusual fear, panic, risk-off, or market stress signals trending on X/Twitter — or the string none>",\n'
    '  "x_key_catalyst": "<main catalyst driving market discussion on X right now — Fed, macro, earnings, geopolitical — or none>"\n'
    '}\n'
    'No markdown fences, no extra keys, no commentary. Output raw JSON only.'
)


def _load_cached_grok() -> dict:
    """Return the last saved Grok intelligence file, or an empty dict."""
    if _GROK_INTEL_FILE.exists():
        try:
            return json.loads(_GROK_INTEL_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def fetch_grok_intelligence() -> dict:
    if not _GROK_API_KEY:
        print('[grok_intelligence] GROK_API_KEY not set — skipping fetch')
        return _load_cached_grok()
    try:
        resp = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {_GROK_API_KEY}',
                'Content-Type':  'application/json',
            },
            json={
                'model': 'grok-3-mini',
                'messages': [
                    {'role': 'system', 'content': 'You are a concise financial markets intelligence assistant.'},
                    {'role': 'user',   'content': _GROK_INTEL_PROMPT},
                ],
                'temperature':   0.3,
                'response_format': {'type': 'json_object'},
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content']
        result  = json.loads(content)
        result['fetched_at'] = utc_now_iso()
        _GROK_INTEL_FILE.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(f'[grok_intelligence] Updated — sentiment:{result.get("market_sentiment")}')
        return result
    except Exception as e:
        print(f'[grok_intelligence] Fetch error: {e} — keeping previous cached data')
        return _load_cached_grok()


# ── Background loops ───────────────────────────────────────────

async def position_outcomes_loop():
    """Every 60 s during NY session (+30 min buffer), check Alpaca for closed
    bracket legs and update journal entries with P&L / outcome."""
    while True:
        try:
            ny = now_ny()
            m  = ny.hour * 60 + ny.minute
            if ny.weekday() < 5 and 9 * 60 + 30 <= m <= 16 * 60 + 30:
                await asyncio.to_thread(reconcile_positions_from_alpaca)
                await asyncio.to_thread(sync_positions_from_alpaca)
                n = await asyncio.to_thread(check_position_outcomes)
                if n:
                    print(f'[position_outcomes] Updated {n} journal entry/entries')
        except Exception as e:
            print(f'Position outcomes loop error: {e}')
        await asyncio.sleep(60)


async def eod_close_loop():
    closed_today = False
    while True:
        try:
            now        = now_ny()
            is_weekday = now.weekday() < 5
            # Reset flag at start of new day
            if now.hour < 15:
                closed_today = False
            # No new trades after 3:30 PM — guard runs once (only while permission is still on)
            if is_weekday and now.hour == 15 and now.minute >= 30:
                if _EXECUTION_AVAILABLE:
                    from core.state_engine import state as _st
                    if not _st.get('eod_lock') and _st.get('trade_permission'):
                        disable_trade_permission('EOD_NO_NEW_ENTRIES_AFTER_1530')
                        print(f'[EOD] {now.strftime("%H:%M ET")} — no new entries after 3:30 PM')
            # Force close all at 3:45 PM — retry every 60s until flat (up to 4:30 PM)
            _eod_hour = now.hour * 60 + now.minute
            if is_weekday and 15 * 60 + 45 <= _eod_hour <= 16 * 60 + 30 and not closed_today:
                if _EXECUTION_AVAILABLE:
                    from core.state_engine import state as _st
                    try:
                        positions = get_positions()
                    except Exception as pos_err:
                        print(f'[EOD] get_positions failed — will retry: {pos_err}')
                        positions = None
                    if positions is None:
                        pass  # Alpaca unreachable — leave closed_today=False so we retry next tick
                    elif positions:
                        print(f'[EOD] {now.strftime("%H:%M ET")} — closing {len(positions)} positions')
                        closed = close_all_positions_eod()
                        print(f'[EOD] Closed {closed} positions — eod_lock=True')
                        if closed > 0:
                            closed_today = True
                    else:
                        print(f'[EOD] {now.strftime("%H:%M ET")} — already flat, setting eod_lock')
                        _st.set('eod_lock', True)
                        closed_today = True
        except Exception as e:
            print(f'[EOD loop error] {e}')
        await asyncio.sleep(60)


async def morning_brief_loop():
    while True:
        try:
            ny        = now_ny()
            today_str = ny.strftime('%Y-%m-%d')
            if ny.weekday() < 5 and ny.hour == 9 and ny.minute < 5:
                state = read_json_file(MORNING_BRIEF_FILE, {})
                if state.get('last_sent_date') != today_str:
                    print(f'DONNA morning brief: sending for {today_str}')
                    result = await asyncio.to_thread(send_morning_brief)
                    print(f'DONNA morning brief: {result}')
            # Compact intelligence brief -- fires 9:00-9:25 AM, once per day
            if ny.weekday() < 5 and ny.hour == 9 and ny.minute < 25:
                try:
                    from engines.morning_brief import compute_and_deliver_morning_brief
                    await asyncio.to_thread(compute_and_deliver_morning_brief)
                except Exception as _be:
                    print(f'[morning_brief] compact brief error: {_be}')
        except Exception as e:
            print(f'Morning brief loop error: {e}')
        await asyncio.sleep(60)


def _news_sleep_seconds() -> int:
    """60s during market hours (09:00–16:30 ET weekdays), 300s otherwise."""
    ny = now_ny()
    m  = ny.hour * 60 + ny.minute
    if ny.weekday() < 5 and 9 * 60 <= m <= 16 * 60 + 30:
        return 60
    return 300


async def news_loop():
    while True:
        try:
            await asyncio.to_thread(process_news_guard_cycle)
            if _MACRO_DISCORD_AVAILABLE:
                await asyncio.to_thread(run_breaking_news_check)
        except Exception as e:
            print('Donna News loop error:', str(e))
        await asyncio.sleep(_news_sleep_seconds())


async def headline_loop():
    while True:
        try:
            await asyncio.to_thread(process_headlines_cycle)
        except Exception as e:
            print('Headline loop error:', str(e))
        await asyncio.sleep(_news_sleep_seconds())


async def finnhub_loop():
    while True:
        try:
            await asyncio.to_thread(process_finnhub_cycle)
        except Exception as e:
            print('Finnhub loop error:', str(e))
        await asyncio.sleep(300)


async def grok_loop():
    while True:
        try:
            await asyncio.to_thread(fetch_grok_intelligence)
        except Exception as e:
            print('Grok intelligence loop error:', str(e))
        # Adaptive sleep: 5 min during market hours (9:00–16:30 ET Mon–Fri), 30 min outside
        ny = now_ny()
        m  = ny.hour * 60 + ny.minute
        in_market = ny.weekday() < 5 and 9 * 60 <= m <= 16 * 60 + 30
        await asyncio.sleep(300 if in_market else 1800)


async def macro_discord_loop():
    """
    Every 5 min: check macro calendar phases, VIX, and breaking news.
    Delivers high-signal events exclusively to #macro-risk.
    Morning brief fires once per day at 09:00–09:20 ET.
    """
    if not _MACRO_DISCORD_AVAILABLE:
        return
    while True:
        try:
            ny = now_ny()
            # Morning brief window: 09:00–09:20 ET, weekdays only
            if ny.weekday() < 5 and ny.hour == 9 and ny.minute < 20:
                await asyncio.to_thread(run_macro_morning_brief)
            # Core checks — all active during market hours
            if ny.weekday() < 5:
                await asyncio.to_thread(run_macro_calendar_check)
                await asyncio.to_thread(run_breaking_news_check)
        except Exception as e:
            print(f'[macro_discord_loop] error: {e}')
        await asyncio.sleep(_news_sleep_seconds())


# ── Startup ────────────────────────────────────────────────────

def _init_settings_from_bundle() -> None:
    """
    On Render, DONNA_DATA_DIR=/data so SETTINGS_FILE lives on the persistent disk.
    The disk may be an old version missing execution_mode / execution_profiles.
    Copy those fields from the bundled repo copy (data/donna_settings.json next to
    main.py) so a fresh disk or a disk that pre-dates these fields always arms correctly.
    """
    try:
        from core.config import BASE_DIR
        bundled = BASE_DIR / 'data' / 'donna_settings.json'
        if not bundled.exists() or bundled == SETTINGS_FILE:
            return
        b = json.loads(bundled.read_text(encoding='utf-8'))
        disk: dict = json.loads(SETTINGS_FILE.read_text(encoding='utf-8')) if SETTINGS_FILE.exists() else {}
        changed = False
        for key in ('execution_mode', 'execution_profiles'):
            if key not in disk or not disk[key]:
                disk[key] = b.get(key)
                changed = True
        if changed:
            SETTINGS_FILE.write_text(json.dumps(disk, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f'[startup] donna_settings.json patched from bundled copy: execution_mode={disk.get("execution_mode")}')
    except Exception as _e:
        print(f'[startup] _init_settings_from_bundle error: {_e}')


@app.on_event('startup')
async def startup():
    _init_settings_from_bundle()
    ensure_files()
    if _STATE_ENGINE_AVAILABLE:
        print(
            f'State engine loaded — '
            f'date: {_donna_state.get("state_date")}, '
            f'trades today: {_donna_state.get_trade_count()}'
        )
    # Execution audit -- detect and repair any ghost trade gaps from prior sessions
    try:
        from services.audit import reconcile_execution_audit
        await asyncio.to_thread(reconcile_execution_audit)
    except Exception as e:
        print(f'[startup] audit reconciliation error: {e}')
    await asyncio.to_thread(check_todays_breaking_events)
    try:
        await asyncio.to_thread(process_finnhub_cycle)
        print('[startup] Initial finnhub cycle complete')
    except Exception as e:
        print(f'[startup] Initial finnhub cycle failed: {e}')
    asyncio.create_task(news_loop())
    asyncio.create_task(headline_loop())
    asyncio.create_task(finnhub_loop())
    asyncio.create_task(grok_loop())
    asyncio.create_task(morning_brief_loop())
    asyncio.create_task(macro_discord_loop())
    if _EXECUTION_AVAILABLE:
        await asyncio.to_thread(sync_positions_from_alpaca)
        await asyncio.to_thread(reconcile_positions_from_alpaca)
        asyncio.create_task(position_outcomes_loop())
        asyncio.create_task(eod_close_loop())
    if _ALERT_ENGINE_AVAILABLE:
        await asyncio.to_thread(start_setup_monitor, 60)
        print('[startup] NOVA alert monitor started (60s polling interval)')


# ── Health / meta ──────────────────────────────────────────────

@app.get('/')
async def root():
    return {'status': 'NOVA is online', 'version': app.version}


@app.get('/debug-paths')
async def debug_paths():
    import os
    from core.config import DATA_DIR, JOURNAL_FILE
    data_dir_str = str(DATA_DIR)
    journal_str  = str(JOURNAL_FILE)
    env_nova      = os.getenv('NOVA_DATA_DIR', 'NOT_SET')
    env_donna     = os.getenv('DONNA_DATA_DIR', 'NOT_SET')
    data_dir_exists   = DATA_DIR.exists()
    journal_exists    = JOURNAL_FILE.exists()
    journal_bytes     = JOURNAL_FILE.stat().st_size if journal_exists else -1
    data_dir_contents = sorted([f.name for f in DATA_DIR.iterdir()]) if data_dir_exists else []
    return {
        'env_NOVA_DATA_DIR':  env_nova,
        'env_DONNA_DATA_DIR': env_donna,
        'DATA_DIR':           data_dir_str,
        'JOURNAL_FILE':       journal_str,
        'data_dir_exists':    data_dir_exists,
        'journal_exists':     journal_exists,
        'journal_bytes':      journal_bytes,
        'data_dir_contents':  data_dir_contents,
    }


@app.get('/debug-grok')
async def debug_grok():
    """Trace every stage of the Grok intelligence pipeline."""
    import requests as _req

    # Stage 1: API key
    key_set    = bool(_GROK_API_KEY)
    key_prefix = (_GROK_API_KEY[:8] + '...') if key_set else 'NOT_SET'

    # Stage 2: File
    file_path    = str(_GROK_INTEL_FILE)
    file_exists  = _GROK_INTEL_FILE.exists()
    file_bytes   = _GROK_INTEL_FILE.stat().st_size if file_exists else -1
    file_contents = None
    if file_exists:
        try:
            file_contents = json.loads(_GROK_INTEL_FILE.read_text(encoding='utf-8'))
        except Exception as _fe:
            file_contents = f'PARSE_ERROR: {_fe}'

    # Stage 3: Live API probe (only if key is set — single message, minimal cost)
    api_status  = 'SKIPPED — key not set'
    api_payload = None
    if key_set:
        try:
            _r = _req.post(
                'https://api.x.ai/v1/chat/completions',
                headers={'Authorization': f'Bearer {_GROK_API_KEY}', 'Content-Type': 'application/json'},
                json={
                    'model': 'grok-3-mini',
                    'messages': [
                        {'role': 'system', 'content': 'You are a test assistant.'},
                        {'role': 'user',   'content': 'Reply with exactly: {"status":"ok"}'},
                    ],
                    'temperature': 0,
                    'response_format': {'type': 'json_object'},
                },
                timeout=15,
            )
            api_status  = f'HTTP {_r.status_code}'
            api_payload = _r.json() if _r.ok else _r.text[:500]
        except Exception as _ae:
            api_status  = f'EXCEPTION: {_ae}'

    # Stage 4: Endpoint read
    endpoint_result = _load_cached_grok()

    return {
        'stage_1_api_key':      {'set': key_set, 'prefix': key_prefix},
        'stage_2_file':         {'path': file_path, 'exists': file_exists, 'bytes': file_bytes, 'contents': file_contents},
        'stage_3_api_probe':    {'status': api_status, 'payload': api_payload},
        'stage_4_endpoint':     endpoint_result or 'EMPTY — file missing or parse failed',
        'break_point':          (
            'STAGE 1 — GROK_API_KEY not set' if not key_set
            else 'STAGE 2 — file missing (loop not yet run or API failing)' if not file_exists
            else 'STAGE 4 — endpoint returns empty (file unreadable)' if not endpoint_result
            else 'NO BREAK DETECTED — pipeline appears healthy'
        ),
    }


@app.head('/')
async def root_head():
    return Response(status_code=200)


@app.get('/check-env')
async def check_env():
    return {
        'anthropic_key_found':         bool(ANTHROPIC_API_KEY),
        'telegram_found':              bool(TELEGRAM_BOT_TOKEN),
        'finnhub_found':               bool(FINNHUB_API_KEY),
        'fmp_found':                   bool(FMP_API_KEY),
        'alpha_vantage_found':         bool(ALPHA_VANTAGE_API_KEY),
        'forex_factory_notes_url_set': bool(FOREX_FACTORY_NOTES_URL),
        'risk_file_exists':            RISK_STATE_FILE.exists(),
        'alerts_file_exists':          ALERTS_FILE.exists(),
        'assistant_file_exists':       ASSISTANT_FILE.exists(),
        'settings_file_exists':        SETTINGS_FILE.exists(),
        'macro_events_file_exists':    MACRO_EVENTS_FILE.exists(),
        'discord_macro_channel_set':   bool(os.getenv('DISCORD_CHANNEL_MACRO', '')),
        'macro_discord_available':     _MACRO_DISCORD_AVAILABLE,
        'telegram_alert_mode':         TELEGRAM_ALERT_MODE,
        'chat_model':                  ANTHROPIC_ASSISTANT_MODEL,
        'fast_model':                  ANTHROPIC_MODEL,
    }


@app.get('/state-engine')
async def state_engine_endpoint():
    """Return the full DONNA state engine snapshot."""
    return _donna_state.get_state()


@app.get('/system-health')
async def system_health():
    return {
        'status': 'ok',
        'cache_keys': list(CACHE.keys()),
        'finnhub_configured': bool(FINNHUB_API_KEY),
        'fmp_configured': bool(FMP_API_KEY),
        'alpha_vantage_configured': bool(ALPHA_VANTAGE_API_KEY),
        'forex_factory_macro_layer': load_macro_events().get('source', 'unknown'),
        'last_time_ny': now_ny().isoformat(),
    }


@app.get('/test-telegram')
async def test_telegram():
    return send_telegram_message('NOVA TEST MESSAGE')


@app.get('/breaking-check')
async def breaking_check():
    result = await asyncio.to_thread(check_todays_breaking_events)
    return result


# ── Dashboard ──────────────────────────────────────────────────

@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get('/dashboard-data')
async def dashboard_data():
    return build_dashboard_payload()


# ── Market data ────────────────────────────────────────────────

@app.get('/market-data')
async def market_data():
    return get_live_market_data()


@app.get('/major-indexes')
async def major_indexes():
    return {'rows': get_live_major_indexes()}


@app.get('/movers')
async def movers():
    return get_live_movers()


@app.get('/trending-movers')
async def trending_movers():
    symbols = [
        ('NVDA', 'NVIDIA'), ('MSFT', 'Microsoft'), ('AAPL', 'Apple'),
        ('AMZN', 'Amazon'), ('META', 'Meta'), ('TSLA', 'Tesla'),
        ('GOOG', 'Alphabet'), ('AVGO', 'Broadcom'), ('CSCO', 'Cisco'),
        ('AMD', 'AMD'), ('JPM', 'JPMorgan'), ('BAC', 'Bank of America'),
        ('GS', 'Goldman Sachs'), ('XOM', 'ExxonMobil'), ('CVX', 'Chevron'),
    ]
    rows = []
    for sym, name in symbols:
        q = await asyncio.to_thread(get_quote_with_fallback, sym)
        if not q:
            continue
        pct = q.get('pct', 0)
        try:
            pct_num = float(str(pct).replace('%', ''))
        except Exception:
            pct_num = 0.0
        rows.append({'symbol': sym, 'name': name, 'last': q.get('last', '-'),
                     'chg': q.get('chg', '-'), 'pct': pct_num})
    rows.sort(key=lambda r: r['pct'], reverse=True)
    gainers = [dict(r, pct=f"{r['pct']:+.2f}%") for r in rows[:5]]
    losers  = [dict(r, pct=f"{r['pct']:+.2f}%") for r in rows[-5:][::-1]]
    return {'gainers': gainers, 'losers': losers}


@app.get('/sector-heat')
async def sector_heat():
    sectors = [
        ('XLK',  'Technology',        31.0),
        ('XLV',  'Healthcare',        12.5),
        ('XLF',  'Financials',        13.0),
        ('XLY',  'Consumer Disc.',    11.0),
        ('XLC',  'Comm. Services',     9.0),
        ('XLI',  'Industrials',        9.0),
        ('XLP',  'Consumer Staples',   6.0),
        ('XLE',  'Energy',             4.0),
        ('XLU',  'Utilities',          2.5),
        ('XLB',  'Materials',          2.5),
        ('XLRE', 'Real Estate',        2.0),
    ]
    results = []
    for sym, name, weight in sectors:
        q = await asyncio.to_thread(get_quote_with_fallback, sym)
        pct_num = 0.0
        if q:
            try:
                pct_num = float(str(q.get('pct', 0)).replace('%', ''))
            except Exception:
                pass
        results.append({'symbol': sym, 'name': name, 'weight': weight,
                        'last': (q or {}).get('last', '-'),
                        'pct': round(pct_num, 2)})
    return {'sectors': results}


@app.get('/nq-components')
async def nq_components():
    components = [
        ('AAPL',  'Apple',     9.0),
        ('MSFT',  'Microsoft', 9.0),
        ('NVDA',  'NVIDIA',    8.5),
        ('AMZN',  'Amazon',    5.5),
        ('META',  'Meta',      5.0),
        ('GOOG',  'Alphabet',  5.0),
        ('AVGO',  'Broadcom',  4.0),
        ('TSLA',  'Tesla',     3.5),
        ('COST',  'Costco',    2.5),
        ('ADBE',  'Adobe',     1.5),
    ]
    results = []
    for sym, name, weight in components:
        q = await asyncio.to_thread(get_quote_with_fallback, sym)
        pct_num = 0.0
        if q:
            try:
                pct_num = float(str(q.get('pct', 0)).replace('%', ''))
            except Exception:
                pass
        results.append({'symbol': sym, 'name': name, 'weight': weight,
                        'last': (q or {}).get('last', '-'),
                        'pct': round(pct_num, 2)})
    return {'components': results}


# ── Stock Heatmaps ─────────────────────────────────────────────

from core.config import SP500_HEATMAP_FILE as _SP500_HEATMAP_FILE, NQ_HEATMAP_FILE as _NQ_HEATMAP_FILE

_SP500_SYMBOLS: dict[str, tuple[str, float]] = {
    'XLK':  ('Technology',               31.0),
    'XLF':  ('Financials',               13.0),
    'XLV':  ('Healthcare',               12.5),
    'XLY':  ('Consumer Discretionary',   11.0),
    'XLI':  ('Industrials',               9.0),
    'XLC':  ('Communication Services',    9.0),
    'XLP':  ('Consumer Staples',          6.0),
    'XLE':  ('Energy',                    4.0),
    'XLRE': ('Real Estate',               2.0),
    'XLU':  ('Utilities',                 2.5),
    'XLB':  ('Materials',                 2.5),
}

_NQ_SYMBOLS: dict[str, tuple[str, float]] = {
    'AAPL':  ('Apple',       9.0), 'MSFT':  ('Microsoft',   8.5),
    'NVDA':  ('NVIDIA',      7.8), 'AMZN':  ('Amazon',      5.2),
    'META':  ('Meta',        4.8), 'TSLA':  ('Tesla',       3.5),
    'GOOGL': ('Alphabet',    3.2), 'AVGO':  ('Broadcom',    2.9),
    'COST':  ('Costco',      2.4), 'ADBE':  ('Adobe',       1.8),
    'AMD':   ('AMD',         1.6), 'NFLX':  ('Netflix',     1.5),
    'CSCO':  ('Cisco',       1.2), 'INTC':  ('Intel',       0.9),
    'QCOM':  ('Qualcomm',    0.8), 'TXN':   ('Texas Instr', 0.8),
    'ORCL':  ('Oracle',      0.7), 'INTU':  ('Intuit',      0.7),
    'MU':    ('Micron',      0.6), 'KLAC':  ('KLA Corp',    0.5),
}


def _heatmap_is_market_hours() -> bool:
    ny = now_ny()
    m  = ny.hour * 60 + ny.minute
    return ny.weekday() < 5 and 9 * 60 + 30 <= m <= 16 * 60


def _fetch_heatmap(symbols_dict: dict, cache_file: Path, include_symbol: bool = True) -> dict:
    from datetime import timezone as _tz
    ttl = 300 if _heatmap_is_market_hours() else 1800
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding='utf-8'))
            age = (datetime.now(_tz.utc) - datetime.fromisoformat(
                cached.get('fetched_at', '1970-01-01T00:00:00+00:00').replace('Z', '+00:00')
            )).total_seconds()
            # also re-fetch if the cached entry count no longer matches the dict
            if age < ttl and len(cached.get('stocks', [])) == len(symbols_dict):
                return cached
        except Exception:
            pass

    stocks = []
    for sym, (name, weight) in symbols_dict.items():
        try:
            r   = requests.get(
                f'https://finnhub.io/api/v1/quote?symbol={sym}&token={FINNHUB_API_KEY}',
                timeout=8,
            )
            r.raise_for_status()
            q     = r.json()
            pct   = round(float(q.get('dp', 0) or 0), 2)
            price = round(float(q.get('c',  0) or 0), 2)
        except Exception:
            pct, price = 0.0, 0.0
        item: dict = {
            'name':           name,
            'percent_change': pct,
            'price':          price,
            'market_weight':  weight,
        }
        if include_symbol:
            item['symbol'] = sym
        stocks.append(item)

    result = {'stocks': stocks, 'fetched_at': utc_now_iso()}
    try:
        cache_file.write_text(json.dumps(result, indent=2), encoding='utf-8')
    except Exception:
        pass
    return result


@app.get('/sp500-heatmap')
async def sp500_heatmap():
    return await asyncio.to_thread(_fetch_heatmap, _SP500_SYMBOLS, _SP500_HEATMAP_FILE, False)


@app.get('/nq-heatmap')
async def nq_heatmap():
    return await asyncio.to_thread(_fetch_heatmap, _NQ_SYMBOLS, _NQ_HEATMAP_FILE)


# ── BTC + VIX live quotes ──────────────────────────────────────

from core.config import BTC_VIX_CACHE_FILE as _BTC_VIX_CACHE_FILE


def _finnhub_quote_raw(symbol: str) -> dict | None:
    """Single Finnhub /quote call; returns {last, pct, chg} or None on failure."""
    try:
        r = requests.get(
            f'https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}',
            timeout=5,
        )
        r.raise_for_status()
        q = r.json()
        last = float(q.get('c', 0) or 0)
        if last == 0:
            return None
        return {
            'last': round(last, 2),
            'pct':  round(float(q.get('dp', 0) or 0), 2),
            'chg':  round(float(q.get('d',  0) or 0), 2),
        }
    except Exception:
        return None


def _fetch_btc_vix() -> dict:
    from datetime import timezone as _tz
    if _BTC_VIX_CACHE_FILE.exists():
        try:
            cached = json.loads(_BTC_VIX_CACHE_FILE.read_text(encoding='utf-8'))
            age = (datetime.now(_tz.utc) - datetime.fromisoformat(
                cached.get('fetched_at', '1970-01-01T00:00:00+00:00').replace('Z', '+00:00')
            )).total_seconds()
            if age < 60:
                return cached
        except Exception:
            pass

    btc = _finnhub_quote_raw('BINANCE:BTCUSDT') or _finnhub_quote_raw('COINBASE:BTC-USD')
    vix = _finnhub_quote_raw('VIXY')   # VIXY tracks VIX; ^VIX not available on Finnhub free tier

    result: dict = {
        'BTC':        btc or {},
        'VIX':        vix or {},
        'fetched_at': utc_now_iso(),
    }
    try:
        _BTC_VIX_CACHE_FILE.write_text(json.dumps(result, indent=2), encoding='utf-8')
    except Exception:
        pass
    return result


@app.get('/btc-vix')
async def btc_vix():
    return await asyncio.to_thread(_fetch_btc_vix)


@app.get('/futures-macro-pulse')
async def futures_macro_pulse():
    return {'rows': get_live_futures_macro_pulse()}


@app.get('/calendar')
async def calendar():
    return get_live_calendar()


@app.get('/earnings')
async def earnings():
    return get_live_earnings()


# ── Scenario engine ────────────────────────────────────────────

@app.get('/scenario-data')
async def scenario_data():
    return build_scenario_engine()


@app.post('/scenario-data/refresh')
async def scenario_data_refresh():
    return build_scenario_engine(force=True)


# ── HARVEY ─────────────────────────────────────────────────────

@app.get('/harvey-data')
async def harvey_data():
    payload  = build_harvey_payload()
    risk     = load_risk_state()
    snapshot = risk.get('market_snapshot', {})
    nq_last  = snapshot.get('NQ', {}).get('last', 0)
    es_last  = snapshot.get('ES', {}).get('last', 0)
    nq_pct   = snapshot.get('NQ', {}).get('pct', 0)
    es_pct   = snapshot.get('ES', {}).get('pct', 0)
    if nq_last and nq_last > 1000:
        payload['nq_last'] = nq_last
        payload['nq_pct']  = nq_pct
    if es_last and es_last > 1000:
        payload['es_last'] = es_last
        payload['es_pct']  = es_pct
    from engines.synthesis import load_synthesis
    from engines.market_reality_v2 import load_market_reality_v2
    from engines.liquidity import load_liquidity
    from engines.participation import load_participation
    from engines.session_memory import load_session_memory

    def _safe_load(fn, name):
        try:
            return fn()
        except Exception as _e:
            print(f'[harvey-data] {name} load error: {_e}')
            return {}

    payload['intelligence'] = {
        'synthesis':      _safe_load(load_synthesis,         'synthesis'),
        'mr2':            _safe_load(load_market_reality_v2, 'mr2'),
        'liquidity':      _safe_load(load_liquidity,         'liquidity'),
        'participation':  _safe_load(load_participation,     'participation'),
        'session_memory': _safe_load(load_session_memory,    'session_memory'),
    }
    return payload


# ── Risk engine ────────────────────────────────────────────────

@app.get('/risk-engine-data')
async def risk_engine_data(
    entry:     float | None = None,
    stop:      float | None = None,
    target:    float | None = None,
    direction: str          = 'LONG',
):
    trades   = load_journal()
    re_state = load_re_state()
    payload  = build_risk_engine_payload(
        trades       = trades,
        account_size = float(re_state.get('account_size', 25000)),
        risk_pct     = float(re_state.get('risk_pct', 1.0)),
        entry        = entry,
        stop         = stop,
        target       = target,
        direction    = direction,
    )
    return {'status': 'ok', **payload}


@app.post('/risk-engine/reset-stop')
async def risk_engine_reset_stop():
    return reset_stop_trading()


@app.post('/risk-engine/settings')
async def risk_engine_settings(request: Request):
    body         = await request.json()
    account_size = body.get('account_size')
    risk_pct     = body.get('risk_pct')
    try:
        if account_size is not None: account_size = float(account_size)
        if risk_pct     is not None: risk_pct     = float(risk_pct)
    except Exception:
        raise HTTPException(status_code=400, detail='account_size and risk_pct must be numbers')
    state = update_re_settings(account_size=account_size, risk_pct=risk_pct)
    return {'status': 'ok', 'settings': state}


# ── Alerts ─────────────────────────────────────────────────────

@app.get('/alerts-data')
async def alerts_data():
    return {'alerts': load_alert_history()}


@app.get('/grok-intelligence')
async def grok_intelligence():
    cached = _load_cached_grok()
    if cached:
        return cached
    # No file yet — return a safe skeleton so the frontend never breaks
    return {
        'top_story':          '',
        'top_story_summary':  '',
        'market_sentiment':   'NEUTRAL',
        'sentiment_reason':   'Intelligence is being fetched — check back shortly.',
        'donna_trade_read':   '',
        'key_names_to_watch': [],
        'x_market_chatter':   '',
        'x_stress_signal':    '',
        'x_key_catalyst':     '',
        'fetched_at':         None,
    }


@app.get('/api/governance')
async def governance_status():
    """Aggregated gate status for the Governance UI page."""
    try:
        from core.state_engine import state as _st
        from services.execution_bridge import _load_execution_config, _is_paper
        st = _st.get_state()
        active_mode, cfg = _load_execution_config()
        positions = _st.get_open_positions()
        return {
            'execution_mode':          active_mode,
            'paper_mode':              _is_paper(),
            'nova_auto_execute':       os.getenv('NOVA_AUTO_EXECUTE', 'false').lower() == 'true',
            'trade_permission':        st.get('trade_permission', False),
            'daily_trade_count':       st.get('daily_trade_count', 0),
            'max_trades':              int(cfg.get('max_trades_per_day', 5)) if cfg else 5,
            'open_positions':          positions,
            'open_positions_count':    len(positions),
            'max_concurrent_positions': int(cfg.get('max_concurrent_positions', 2)) if cfg else 2,
            'eod_lock':                st.get('eod_lock', False),
            'macro_lock':              st.get('macro_lock', False),
            'red_folder_lock':         st.get('red_folder_lock', False),
            'execution_lock':          st.get('execution_lock', False),
            'size_reduction_active':   st.get('size_reduction_active', False),
            'spy_cooldown_until':      st.get('spy_cooldown_until'),
            'qqq_cooldown_until':      st.get('qqq_cooldown_until'),
            'blocked_signals_today':   st.get('blocked_signals_today', []),
            'risk_lockouts':           st.get('risk_lockouts', []),
            'min_grade':               cfg.get('min_grade', 'B') if cfg else 'N/A',
            'cooldown_minutes':        int(cfg.get('trade_cooldown_minutes', 20)) if cfg else 20,
            'risk_tier':               cfg.get('risk_tier', 'N/A') if cfg else 'N/A',
            'daily_pnl':               st.get('daily_pnl', 0.0),
            'session_state':           st.get('session_state', ''),
            'last_updated':            st.get('last_updated', ''),
        }
    except Exception as exc:
        return {'error': str(exc)}


@app.get('/api/execution-state')
async def execution_state():
    """
    Full execution arming status — answers 'why won't the next trade fire?'
    Returns armed flag, active blockers, position attribution, and exact conditions
    required for the next trade to execute.
    """
    try:
        import os as _os
        from core.state_engine import state as _st
        from services.execution_bridge import _load_execution_config, _auto_execute_enabled, _is_paper

        st           = _st.get_state()
        auto_execute = _auto_execute_enabled()
        paper        = _is_paper()
        active_mode, cfg = _load_execution_config()

        # Collect every blocker that would prevent a hypothetical A-grade PROS signal
        blockers: list[str] = []
        conditions_met: list[str] = []

        # System gates
        if not auto_execute:
            blockers.append('NOVA_AUTO_EXECUTE is false — set to true to arm execution')
        else:
            conditions_met.append('NOVA_AUTO_EXECUTE=true')

        if not paper:
            blockers.append('Alpaca is in LIVE mode — bridge is paper-only')
        else:
            conditions_met.append('Alpaca paper mode confirmed')

        # Profile gates
        if active_mode == 'disabled' or not cfg:
            blockers.append(f'Execution profile is disabled (mode={active_mode})')
        else:
            conditions_met.append(f'Execution profile active: {active_mode}')
            if cfg.get('kill_switch', False):
                blockers.append('Kill switch is engaged')
            else:
                conditions_met.append('Kill switch off')

        # State engine locks
        if st.get('eod_lock'):
            blockers.append('EOD lock active — trading day closed')
        if st.get('macro_lock'):
            blockers.append('Macro lock active')
        if st.get('red_folder_lock'):
            blockers.append('Red-folder lock active')
        if st.get('execution_lock'):
            blockers.append('Execution lock active')

        # Position state
        positions = _st.get_open_positions()
        max_concurrent = int(cfg.get('max_concurrent_positions', 2)) if cfg else 2
        if len(positions) >= max_concurrent:
            blockers.append(f'Concurrent position cap reached: {len(positions)}/{max_concurrent}')
        else:
            conditions_met.append(f'Position slots available: {len(positions)}/{max_concurrent} used')

        # Annotate positions with source + blocking analysis
        position_detail = []
        for p in positions:
            src = p.get('source', 'UNKNOWN')
            sym = p.get('symbol', '?')
            side = p.get('side', '?')
            blocks = []
            if sym == 'SPY':
                blocks.append('blocks new MES/ES signals in same direction')
            elif sym == 'QQQ':
                blocks.append('blocks new MNQ/NQ signals in same direction')
            position_detail.append({
                'symbol':    sym,
                'side':      side,
                'qty':       p.get('qty', '?'),
                'source':    src,
                'entry_ref': p.get('entry_ref', '?'),
                'opened':    p.get('timestamp', '?')[:16] if p.get('timestamp') else '?',
                'blocks':    blocks,
            })

        # Trades today
        trades_today = int(st.get('daily_trade_count', 0))
        max_trades   = int(cfg.get('max_trades_per_day', 5)) if cfg else 5
        if trades_today >= max_trades:
            blockers.append(f'Daily trade limit reached: {trades_today}/{max_trades}')
        else:
            conditions_met.append(f'Daily trade budget: {trades_today}/{max_trades} used')

        armed = auto_execute and paper and active_mode != 'disabled' and cfg is not None and not blockers

        # Conditions for the next trade to fire
        conditions_for_next = []
        for b in blockers:
            conditions_for_next.append(f'RESOLVE: {b}')
        if not blockers:
            conditions_for_next = [
                'Receive EXECUTION_READY alert with grade A or B',
                'MR2 must not be blocking the signal direction',
                'No same-ETF position already open in that direction',
                'Cooldown window must be clear',
            ]

        return {
            'armed':                   armed,
            'nova_auto_execute':       auto_execute,
            'paper_mode':              paper,
            'execution_mode':          active_mode,
            'risk_tier':               cfg.get('risk_tier', 'N/A') if cfg else 'N/A',
            'min_grade':               cfg.get('min_grade', 'B') if cfg else 'N/A',
            'positions':               position_detail,
            'open_count':              len(positions),
            'max_concurrent':          max_concurrent,
            'trades_today':            trades_today,
            'max_trades':              max_trades,
            'eod_lock':                st.get('eod_lock', False),
            'macro_lock':              st.get('macro_lock', False),
            'red_folder_lock':         st.get('red_folder_lock', False),
            'execution_lock':          st.get('execution_lock', False),
            'blockers_active':         blockers,
            'conditions_met':          conditions_met,
            'conditions_for_next_trade': conditions_for_next,
        }
    except Exception as exc:
        return {'error': str(exc)}


@app.get('/api/decision-chain')
async def decision_chain(
    symbol: str = '',
    grade: str = '',
    direction: str = '',
    limit: int = 20,
):
    """Recent DECISION_CHAIN entries from the execution trace. Filterable by symbol/grade/direction."""
    try:
        from services.execution_trace import get_decision_chains
        chains = get_decision_chains(limit=limit, symbol=symbol, direction=direction, grade=grade)
        return {'chains': chains, 'count': len(chains)}
    except Exception as exc:
        return {'error': str(exc)}


@app.get('/market-reality')
async def market_reality_endpoint():
    """Live market reality state. Returns V2 (fact-based) with V1 fields merged as fallback."""
    try:
        from engines.market_reality_v2 import load_market_reality_v2
        mr2 = load_market_reality_v2()
        if mr2 and mr2.get('state'):
            # Supplement with V1 fields any caller may still expect (weekly_structure, grok)
            try:
                from engines.market_reality import load_market_reality
                mr1 = load_market_reality()
                mr2.setdefault('weekly_structure', mr1.get('weekly_structure', ''))
                mr2.setdefault('grok_sentiment',   mr1.get('grok_sentiment', ''))
                mr2.setdefault('direction',         mr1.get('direction', ''))
                mr2.setdefault('severity',          mr1.get('severity', ''))
            except Exception:
                pass
            mr2['session'] = session_label()
            return mr2
    except Exception:
        pass
    try:
        from engines.market_reality import load_market_reality
        return load_market_reality()
    except Exception as exc:
        return {'error': str(exc), 'direction': 'UNKNOWN', 'severity': 'LOW'}


@app.get('/cross-market')
async def cross_market_endpoint():
    """Cross-market intelligence state — NQ/ES spread, DXY, yields, gold, BTC signals."""
    try:
        from engines.cross_market import load_cross_market
        return load_cross_market()
    except Exception as exc:
        return {'error': str(exc), 'cross_market_bias': 'UNKNOWN'}


@app.get('/market-structure')
async def market_structure_endpoint():
    """Market structure memory — overnight range, prior week levels, gap, monthly open."""
    try:
        from engines.market_structure import load_market_structure
        return load_market_structure()
    except Exception as exc:
        return {'error': str(exc), 'nq': {}, 'es': {}}


@app.get('/participation')
async def participation_endpoint():
    """Liquidity & participation intelligence — RVOL, session type, breadth, volume confirmation."""
    try:
        from engines.participation import load_participation
        return load_participation()
    except Exception as exc:
        return {'error': str(exc), 'session_type': 'UNKNOWN', 'participation_bias': 'UNKNOWN'}


@app.get('/liquidity')
async def liquidity_endpoint():
    """Liquidity intelligence — swept/untapped levels, nearest targets, primary draw."""
    try:
        from engines.liquidity import load_liquidity
        return load_liquidity()
    except Exception as exc:
        return {'error': str(exc), 'nq': {}, 'es': {}}


@app.get('/synthesis')
async def synthesis_endpoint():
    """Market synthesis — unified interpretation across all Level 1 intelligence engines."""
    try:
        from engines.synthesis import load_synthesis
        return load_synthesis()
    except Exception as exc:
        return {'error': str(exc), 'market_thesis': 'UNKNOWN', 'confidence': 'LOW'}


@app.get('/session-memory')
async def session_memory_endpoint():
    """Multi-session memory -- rolling narrative of what the market has been trying to accomplish."""
    try:
        from engines.session_memory import load_session_memory
        return load_session_memory()
    except Exception as exc:
        return {'error': str(exc), 'rolling_narrative': 'Session memory unavailable.', 'session_count': 0}


# ── MCP Snapshot query helpers ────────────────────────────────────────────────

def _read_mcp_snapshots_raw() -> list:
    """Load nova_mcp_snapshots.json, return [] on any failure."""
    try:
        from core.config import MCP_SNAPSHOTS_FILE
        import json as _j
        if not MCP_SNAPSHOTS_FILE.exists():
            return []
        raw = _j.loads(MCP_SNAPSHOTS_FILE.read_text(encoding='utf-8'))
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _filter_snapshots(
    snaps: list,
    *,
    snapshot_type:      str  | None = None,
    symbol:             str  | None = None,
    parser_mode:        str  | None = None,
    parse_status:       str  | None = None,
    signal_type:        str  | None = None,
    setup_type:         str  | None = None,
    direction:          str  | None = None,
    is_execution_ready: bool | None = None,
    is_rejected:        bool | None = None,
    ticker_match:       bool | None = None,
    timeframe_match:    bool | None = None,
) -> list:
    """Apply optional AND-combined filters to a snapshot list."""
    r = snaps
    if snapshot_type      is not None: r = [s for s in r if s.get('snapshot_type')      == snapshot_type]
    if symbol             is not None: r = [s for s in r if s.get('symbol')             == symbol]
    if parser_mode        is not None: r = [s for s in r if s.get('parser_mode')        == parser_mode]
    if parse_status       is not None: r = [s for s in r if s.get('parse_status')       == parse_status]
    if signal_type        is not None: r = [s for s in r if s.get('signal_type')        == signal_type]
    if setup_type         is not None: r = [s for s in r if s.get('setup_type')         == setup_type]
    if direction          is not None: r = [s for s in r if s.get('direction')          == direction]
    if is_execution_ready is not None: r = [s for s in r if bool(s.get('is_execution_ready')) == is_execution_ready]
    if is_rejected        is not None: r = [s for s in r if bool(s.get('is_rejected'))        == is_rejected]
    if ticker_match       is not None: r = [s for s in r if s.get('ticker_match')       == ticker_match]
    if timeframe_match    is not None: r = [s for s in r if s.get('timeframe_match')    == timeframe_match]
    return r


def _decision_replay_summary(snap: dict) -> dict:
    """Compact replay format for a single decision snapshot."""
    h = snap.get('mcp_health') or {}
    return {
        'timestamp':          snap.get('timestamp'),
        'symbol':             snap.get('symbol'),
        'timeframe':          snap.get('timeframe'),
        'session':            snap.get('session'),
        'parser_mode':        snap.get('parser_mode'),
        'parse_status':       snap.get('parse_status'),
        'mcp_status':         h.get('status'),
        'mcp_confidence':     h.get('confidence'),
        'pre_signal':         snap.get('pre_signal'),
        'pre_setup':          snap.get('pre_setup'),
        'signal_type':        snap.get('signal_type'),
        'setup_type':         snap.get('setup_type'),
        'direction':          snap.get('direction'),
        'grade':              snap.get('grade'),
        'rationale':          snap.get('rationale'),
        'is_execution_ready': snap.get('is_execution_ready'),
        'is_heads_up':        snap.get('is_heads_up'),
        'is_no_trade':        snap.get('is_no_trade'),
        'is_rejected':        snap.get('is_rejected'),
        'rejection_reason':   snap.get('rejection_reason'),
        'ib_status':          snap.get('ib_status'),
        'orb_active':         snap.get('orb_active'),
        'pros_active':        snap.get('pros_active'),
        'peer_alignment':     snap.get('peer_alignment'),
        'draw_direction':     snap.get('draw_direction'),
    }


@app.get('/api/mcp-snapshots/latest')
async def mcp_snapshots_latest():
    """Most recent MCP snapshot (any type)."""
    snaps = _read_mcp_snapshots_raw()
    return snaps[-1] if snaps else {}


@app.get('/api/mcp-snapshots/decisions')
async def mcp_snapshots_decisions(limit: int = 50):
    """Last N decision snapshots (snapshot_type=decision)."""
    limit = max(1, min(limit, 500))
    snaps = _read_mcp_snapshots_raw()
    return _filter_snapshots(snaps, snapshot_type='decision')[-limit:]


@app.get('/api/mcp-snapshots')
async def mcp_snapshots_endpoint(
    limit:               int        = 50,
    snapshot_type:       str | None = None,
    symbol:              str | None = None,
    parser_mode:         str | None = None,
    parse_status:        str | None = None,
    signal_type:         str | None = None,
    setup_type:          str | None = None,
    direction:           str | None = None,
    is_execution_ready:  bool | None = None,
    is_rejected:         bool | None = None,
    ticker_match:        bool | None = None,
    timeframe_match:     bool | None = None,
):
    """Rolling MCP snapshots with optional AND-combined filters (last N, max 500)."""
    try:
        limit = max(1, min(limit, 500))
        snaps = _read_mcp_snapshots_raw()
        snaps = _filter_snapshots(
            snaps,
            snapshot_type=snapshot_type, symbol=symbol,
            parser_mode=parser_mode,     parse_status=parse_status,
            signal_type=signal_type,     setup_type=setup_type,
            direction=direction,         is_execution_ready=is_execution_ready,
            is_rejected=is_rejected,     ticker_match=ticker_match,
            timeframe_match=timeframe_match,
        )
        return snaps[-limit:]
    except Exception as exc:
        return {'error': str(exc), 'snapshots': []}


@app.get('/api/mcp-replay/decisions')
async def mcp_replay_decisions(limit: int = 50):
    """Compact replay summaries for the last N decision snapshots."""
    try:
        limit = max(1, min(limit, 500))
        snaps = _read_mcp_snapshots_raw()
        decisions = _filter_snapshots(snaps, snapshot_type='decision')
        return [_decision_replay_summary(s) for s in decisions[-limit:]]
    except Exception as exc:
        return {'error': str(exc), 'summaries': []}


@app.get('/api/mcp-replay/fingerprints')
async def mcp_replay_fingerprints(limit: int = 50):
    """Compact fingerprint records for the last N decision snapshots."""
    try:
        from engines.reasoning import _build_setup_fingerprint
        limit = max(1, min(limit, 500))
        snaps = _read_mcp_snapshots_raw()
        decisions = _filter_snapshots(snaps, snapshot_type='decision')
        out = []
        for s in decisions[-limit:]:
            fp = s.get('setup_fingerprint') or _build_setup_fingerprint(s)
            out.append({
                'timestamp':          s.get('timestamp'),
                'symbol':             s.get('symbol'),
                'setup_type':         s.get('setup_type'),
                'direction':          s.get('direction'),
                'signal_type':        s.get('signal_type'),
                'session':            s.get('session'),
                'fingerprint':        fp,
                'mcp_confidence':     (s.get('mcp_health') or {}).get('confidence'),
                'is_execution_ready': s.get('is_execution_ready'),
                'is_rejected':        s.get('is_rejected'),
            })
        return out
    except Exception as exc:
        return {'error': str(exc), 'fingerprints': []}


@app.get('/api/mcp-replay/similar')
async def mcp_replay_similar(
    limit:       int        = 10,
    symbol:      str | None = None,
    setup_type:  str | None = None,
    direction:   str | None = None,
    session:     str | None = None,
):
    """Find historical decision snapshots most similar to the latest one.

    Uses setup_fingerprint similarity scoring (0.0–1.0).
    Observability only — does not affect any execution or signal logic.
    """
    try:
        from engines.reasoning import _find_similar_setups, _similar_match_summary
        limit = max(1, min(limit, 100))
        all_snaps = _read_mcp_snapshots_raw()
        decisions = _filter_snapshots(
            all_snaps, snapshot_type='decision',
            symbol=symbol, setup_type=setup_type,
            direction=direction, session=session,
        )
        if not decisions:
            return {'current': None, 'matches': []}
        current = decisions[-1]
        matches = _find_similar_setups(current, decisions, limit=limit)
        return {
            'current': {
                'timestamp':   current.get('timestamp'),
                'symbol':      current.get('symbol'),
                'setup_type':  current.get('setup_type'),
                'signal_type': current.get('signal_type'),
                'direction':   current.get('direction'),
                'session':     current.get('session'),
            },
            'matches': [_similar_match_summary(m) for m in matches],
        }
    except Exception as exc:
        return {'error': str(exc), 'current': None, 'matches': []}


@app.get('/api/mcp-replay/outcomes')
async def mcp_replay_outcomes(limit: int = 50):
    """Compact outcome records for the last N decision snapshots.

    Links each snapshot to signal log / journal / execution trace entries.
    Read-only — no execution impact.
    """
    try:
        from engines.outcome_linker import (
            link_snapshot_to_outcome, outcome_summary,
            load_signal_log, load_journal, load_execution_trace,
        )
        limit       = max(1, min(limit, 500))
        all_snaps   = _read_mcp_snapshots_raw()
        decisions   = _filter_snapshots(all_snaps, snapshot_type='decision')
        signal_log  = await asyncio.to_thread(load_signal_log)
        journal     = await asyncio.to_thread(load_journal)
        trace       = await asyncio.to_thread(load_execution_trace)
        results     = []
        for snap in decisions[-limit:]:
            link = link_snapshot_to_outcome(snap, signal_log, journal, trace)
            results.append(outcome_summary(snap, link))
        return results
    except Exception as exc:
        return {'error': str(exc), 'outcomes': []}


@app.get('/api/mcp-replay/similar-with-outcomes')
async def mcp_replay_similar_with_outcomes(limit: int = 10):
    """Similar setups enriched with outcome links.

    Finds setups similar to the latest decision snapshot, then attempts to
    link each historical match to a known trade outcome.  Does NOT compute
    aggregate stats (win rate, avg R) — outcome data must be linked first.
    Read-only — no execution impact.
    """
    try:
        from engines.reasoning import _find_similar_setups, _similar_match_summary
        from engines.outcome_linker import (
            link_snapshot_to_outcome, load_signal_log, load_journal, load_execution_trace,
        )
        limit       = max(1, min(limit, 100))
        all_snaps   = _read_mcp_snapshots_raw()
        decisions   = _filter_snapshots(all_snaps, snapshot_type='decision')
        if not decisions:
            return {'current': None, 'matches': [], 'outcome_note': 'No decision snapshots available'}

        current    = decisions[-1]
        signal_log = await asyncio.to_thread(load_signal_log)
        journal    = await asyncio.to_thread(load_journal)
        trace      = await asyncio.to_thread(load_execution_trace)

        matches    = _find_similar_setups(current, decisions, limit=limit)
        enriched   = []
        for m in matches:
            base_summary = _similar_match_summary(m)
            snap = m.get('snapshot', {})
            link = link_snapshot_to_outcome(snap, signal_log, journal, trace)
            base_summary['trade_status']     = link.get('trade_status', 'UNKNOWN')
            base_summary['outcome']          = link.get('outcome', 'UNKNOWN')
            base_summary['match_confidence'] = link.get('match_confidence', 'NONE')
            base_summary['linked_signal_id'] = link.get('linked_signal_id', '')
            base_summary['outcome_note'] = (
                f"Outcome linked via {link['match_method']}"
                if link.get('match_method') != 'NONE'
                else 'No outcome linked — snapshot not yet matched to a trade'
            )
            enriched.append(base_summary)

        return {
            'current': {
                'timestamp':    current.get('timestamp'),
                'symbol':       current.get('symbol'),
                'setup_type':   current.get('setup_type'),
                'signal_type':  current.get('signal_type'),
                'direction':    current.get('direction'),
                'session':      current.get('session'),
                'decision_id':  current.get('decision_id'),
            },
            'matches': enriched,
            # No aggregate stats — outcome linking is in early stage.
            # Win rate / avg R will be computed once HIGH-confidence links accumulate.
        }
    except Exception as exc:
        return {'error': str(exc), 'current': None, 'matches': []}


@app.get('/api/mcp-health')
async def mcp_health_endpoint():
    """MCP health snapshot -- written locally by reasoning cycle, graceful fallback when no local monitor."""
    try:
        from core.config import MCP_HEALTH_FILE
        if MCP_HEALTH_FILE.exists():
            import json as _json
            return _json.loads(MCP_HEALTH_FILE.read_text())
        return {'status': 'UNKNOWN', 'confidence': 0, 'bridge_version': 0, 'bridge_v2_detected': False,
                'ticker': None, 'timeframe': None, 'session': None,
                'fields_present': 0, 'fields_missing': [], 'warnings': [], 'errors': [],
                '_written_at': None, 'error': 'no_local_monitor_data'}
    except Exception as exc:
        return {'status': 'UNKNOWN', 'confidence': 0, 'error': str(exc)}


@app.get('/morning-brief')
async def morning_brief_endpoint():
    """Compact structured morning brief -- thesis, draw, participation, macro, watch."""
    try:
        from engines.morning_brief import build_compact_brief
        return build_compact_brief()
    except Exception as exc:
        return {'error': str(exc), 'brief_text': 'Morning brief unavailable.'}


@app.get('/audit/execution')
async def execution_audit_endpoint():
    """Execution audit -- detect ghost trades and missing journal entries."""
    try:
        from services.audit import reconcile_execution_audit
        return await asyncio.to_thread(reconcile_execution_audit)
    except Exception as exc:
        return {'error': str(exc), 'clean': 0, 'reconstructed': 0, 'unresolved': 0}


# ── Execution engine ───────────────────────────────────────────

@app.get('/execution-status')
async def execution_status():
    if not _EXECUTION_AVAILABLE:
        return {'available': False, 'error': 'donna_execution not loaded'}
    status = await asyncio.to_thread(get_execution_status)
    return {'available': True, **status}


@app.get('/execution-gate')
async def execution_gate():
    return {
        'can_execute':       _donna_state.can_execute(),
        'trade_permission':  _donna_state.get('trade_permission'),
        'eod_lock':          _donna_state.get('eod_lock'),
        'macro_lock':        _donna_state.get('macro_lock'),
        'red_folder_lock':   _donna_state.get('red_folder_lock'),
        'risk_lockouts':     _donna_state.get('risk_lockouts'),
        'daily_trade_count': _donna_state.get('daily_trade_count'),
    }


@app.get('/execution/rejections')
async def execution_rejections(limit: int = 50):
    """Return recent signal rejections with full gate context for observability."""
    records = await asyncio.to_thread(get_rejections, min(limit, 200))
    by_code: dict = {}
    for r in records:
        code = r.get('rejection_code', 'UNKNOWN')
        by_code[code] = by_code.get(code, 0) + 1
    return {
        'total':    len(records),
        'by_code':  by_code,
        'records':  records,
    }


@app.get('/execution/trace')
async def execution_trace(limit: int = 100):
    """
    Full execution pipeline trace — every signal from webhook entry through
    verdict, gate checks, and broker response.

    Each entry has event_type:
      SIGNAL_RECEIVED — webhook received a payload
      VERDICT         — process_signal() completed (verdict + confidence)
      REJECTED        — signal blocked at a gate (includes full gate snapshot)
      EXECUTED        — broker order confirmed

    Query: ?limit=N (max 500)
    """
    try:
        from services.execution_trace import get_trace
        entries = await asyncio.to_thread(get_trace, min(limit, 500))
        by_type: dict = {}
        for e in entries:
            t = e.get('event_type', 'UNKNOWN')
            by_type[t] = by_type.get(t, 0) + 1
        return {
            'total':    len(entries),
            'by_type':  by_type,
            'entries':  entries,
        }
    except Exception as e:
        return {'total': 0, 'entries': [], 'error': str(e)}


@app.get('/reasoning/trace')
async def reasoning_trace(limit: int = 50):
    """
    Full reasoning intelligence snapshots — every Claude evaluation cycle.
    Each entry is self-contained: Pine state, price OTE, directional pressure,
    market memory, and Claude's decision captured together at decision time.

    Answers: "Why did NOVA think this?" / "Why was this blocked?" /
             "What differentiated good from bad trades?"

    Query: ?limit=N (max 300)
    """
    try:
        from services.execution_trace import get_reasoning_trace
        entries = await asyncio.to_thread(get_reasoning_trace, min(limit, 300))
        grades: dict = {}
        for e in entries:
            g = (e.get('claude') or {}).get('grade', 'N/A')
            grades[g] = grades.get(g, 0) + 1
        return {
            'total':   len(entries),
            'grades':  grades,
            'entries': entries,
        }
    except Exception as e:
        return {'total': 0, 'entries': [], 'error': str(e)}


@app.get('/api/feed')
async def nova_feed(
    limit:      int  = 50,
    offset:     int  = 0,
    event_type: str  = None,
    symbol:     str  = None,
    date:       str  = None,
    grade:      str  = None,
    subtype:    str  = None,
    alert_only: bool = False,
):
    """
    NOVA Intelligence Feed — merged chronological timeline.

    Merges signal evaluations, governance rejections, confirmed executions,
    and Market Reality state transitions into a single time-ordered feed.
    Each card is self-contained: strategy, MR2 state, DP state, draw context,
    and rationale are embedded directly — no external lookups needed.

    Filters (all optional, combinable):
      ?event_type=SIGNAL|EXECUTION|GOVERNANCE|MR2_CHANGE
      ?symbol=MES|MNQ
      ?date=YYYY-MM-DD
      ?grade=A|B|C|D
      ?subtype=HEADS_UP|EXECUTION_READY|BRIDGE_REJECTED|LONGS_BLOCKED|...
      ?alert_only=true   — only signal cards where an alert actually fired
      ?limit=N &offset=N — pagination
    """
    try:
        from services.feed import build_feed
        result = await asyncio.to_thread(
            build_feed,
            limit=min(limit, 500),
            offset=offset,
            event_type=event_type,
            symbol=symbol,
            date=date,
            grade=grade,
            subtype=subtype,
            alert_only=alert_only,
        )
        return result
    except Exception as e:
        return {'error': str(e), 'feed': [], 'total': 0}


@app.get('/api/feed/card/{source_id}')
async def nova_feed_card(source_id: str):
    """
    Single feed card detail by source_id.

    For SIGNAL cards with a reasoning_trace_id, returns the full reasoning
    snapshot under _reasoning_detail for complete intelligence audit.
    """
    try:
        from services.feed import get_feed_card
        card = await asyncio.to_thread(get_feed_card, source_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f'Card not found: {source_id}')
        return card
    except HTTPException:
        raise
    except Exception as e:
        return {'error': str(e)}


@app.get('/api/feed/stats')
async def nova_feed_stats():
    """Aggregate statistics across the full feed."""
    try:
        from services.feed import get_feed_stats
        return await asyncio.to_thread(get_feed_stats)
    except Exception as e:
        return {'error': str(e)}


@app.get('/api/feed/health')
async def nova_feed_health():
    """
    Sync health: signal/reasoning/execution counts, newest timestamps, last ingest.
    Use this to diagnose whether an empty feed means no events or sync failure.
    """
    try:
        from services.feed import get_feed_health
        return await asyncio.to_thread(get_feed_health)
    except Exception as e:
        return {'error': str(e)}


@app.post('/api/feed/ingest')
async def nova_feed_ingest(request: Request):
    """
    Receive signal and/or reasoning entries pushed by the local intelligence monitor.
    Authenticated via X-Nova-Ingest-Secret header (shared secret).
    Body: { "signal": {...}, "reasoning": {...} }  — both fields are optional.
    """
    from core.config import NOVA_INGEST_SECRET
    if not NOVA_INGEST_SECRET:
        raise HTTPException(status_code=503, detail='Ingest not configured on this instance.')

    secret = request.headers.get('X-Nova-Ingest-Secret', '')
    if secret != NOVA_INGEST_SECRET:
        raise HTTPException(status_code=401, detail='Invalid ingest secret.')

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid JSON body.')

    signal_entry       = body.get('signal')
    reasoning_entry    = body.get('reasoning')
    execution_entry    = body.get('execution')
    intelligence_entry = body.get('intelligence')
    mcp_health_entry   = body.get('mcp_health')

    if not any([signal_entry, reasoning_entry, execution_entry, intelligence_entry, mcp_health_entry]):
        raise HTTPException(status_code=400, detail='Body must contain signal, reasoning, execution, intelligence, and/or mcp_health.')

    from services.feed import ingest_signal, ingest_reasoning, ingest_execution, ingest_intelligence

    signal_id        = ''
    reasoning_id     = ''
    execution_id     = ''
    intelligence_id  = ''

    if signal_entry and isinstance(signal_entry, dict):
        signal_id = await asyncio.to_thread(ingest_signal, signal_entry)

    if reasoning_entry and isinstance(reasoning_entry, dict):
        reasoning_id = await asyncio.to_thread(ingest_reasoning, reasoning_entry)

    if execution_entry and isinstance(execution_entry, dict):
        execution_id = await asyncio.to_thread(ingest_execution, execution_entry)

    if intelligence_entry and isinstance(intelligence_entry, dict):
        intelligence_id = await asyncio.to_thread(ingest_intelligence, intelligence_entry)

    if mcp_health_entry and isinstance(mcp_health_entry, dict):
        from core.config import MCP_HEALTH_FILE
        import json as _json
        await asyncio.to_thread(
            lambda: MCP_HEALTH_FILE.write_text(_json.dumps(mcp_health_entry, indent=2))
        )

    return {
        'ok':               True,
        'signal_id':        signal_id,
        'reasoning_id':     reasoning_id,
        'execution_id':     execution_id,
        'intelligence_id':  intelligence_id,
    }


@app.post('/api/test/purge')
async def purge_test_events(request: Request):
    """
    Remove specific event IDs from all feed log files. Test cleanup only.
    Authenticated via X-Nova-Ingest-Secret.
    Body: { "ids": ["id1", "id2", ...] }
    """
    from core.config import NOVA_INGEST_SECRET, INTELLIGENCE_LOG_FILE, SIGNAL_LOG_FILE, TRACE_FILE
    secret = request.headers.get('X-Nova-Ingest-Secret', '')
    if secret != NOVA_INGEST_SECRET:
        raise HTTPException(status_code=401, detail='Invalid ingest secret.')
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid JSON body.')
    ids_to_remove = set(body.get('ids', []))
    if not ids_to_remove:
        return {'ok': True, 'removed': {}}
    removed: dict = {}
    for name, path in [
        ('intelligence', INTELLIGENCE_LOG_FILE),
        ('signal',       SIGNAL_LOG_FILE),
        ('execution',    TRACE_FILE),
    ]:
        try:
            if not path.exists():
                continue
            import json as _json
            data = _json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, list):
                continue
            before = len(data)
            data = [e for e in data if e.get('id') not in ids_to_remove]
            if len(data) != before:
                path.write_text(_json.dumps(data, indent=2, default=str), encoding='utf-8')
            removed[name] = before - len(data)
        except Exception as exc:
            removed[name] = f'error: {exc}'
    return {'ok': True, 'removed': removed}


@app.get('/orchestration-status')
async def orchestration_status():
    from datetime import datetime, timezone
    s   = _donna_state.get_state()
    now = datetime.now(timezone.utc)

    def mins_remaining(iso_str):
        if not iso_str:
            return None
        try:
            dt = datetime.strptime(iso_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
            r  = (dt - now).total_seconds() / 60
            return round(max(r, 0), 1)
        except Exception:
            return None

    def thesis_age(iso_str):
        if not iso_str:
            return None
        try:
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            return round((now - dt).total_seconds() / 60, 1)
        except Exception:
            return None

    spy_until  = s.get('spy_cooldown_until')
    qqq_until  = s.get('qqq_cooldown_until')
    thesis_set = s.get('thesis_set_at')

    live_exposure = []
    try:
        live_exposure = await asyncio.to_thread(get_positions)
    except Exception:
        pass

    blocked_today = s.get('blocked_signals_today', [])
    return {
        'active_thesis':                  s.get('active_thesis', 'NEUTRAL'),
        'thesis_direction':               s.get('thesis_direction'),
        'thesis_set_at':                  thesis_set,
        'thesis_age_minutes':             thesis_age(thesis_set),
        'spy_cooldown_until':             spy_until,
        'qqq_cooldown_until':             qqq_until,
        'spy_cooldown_remaining_minutes': mins_remaining(spy_until),
        'qqq_cooldown_remaining_minutes': mins_remaining(qqq_until),
        'blocked_signals_today':          blocked_today,
        'last_block_reason':              blocked_today[-1].get('block_reason') if blocked_today else None,
        'open_positions':                 s.get('open_positions', []),
        'live_alpaca_exposure':           live_exposure,
        'can_execute':                    _donna_state.can_execute(),
        'trade_permission':               s.get('trade_permission', True),
        'macro_lock':                     s.get('macro_lock', False),
        'red_folder_lock':                s.get('red_folder_lock', False),
    }


@app.get('/analytics-summary')
async def analytics_summary():
    return await asyncio.to_thread(compute_analytics)

@app.get('/analytics/validate')
async def analytics_validate():
    """Re-derive outcome and pnl for every closed trade. Returns integrity report."""
    from core.state import load_journal
    def _run():
        closed  = [t for t in load_journal() if t.get('outcome') in ('WIN', 'LOSS', 'BREAKEVEN')]
        results = []
        for t in closed:
            v = validate_trade(t)
            results.append({
                'signal_id':        t.get('signal_id', ''),
                'ticker':           t.get('ticker', ''),
                'trade_date':       t.get('trade_date', ''),
                'direction':        t.get('direction', ''),
                'entry_price':      t.get('entry_price'),
                'exit_price':       t.get('exit_price'),
                'size':             t.get('size'),
                **v,
            })
        valid   = [r for r in results if r.get('valid')]
        invalid = [r for r in results if not r.get('valid')]
        return {
            'total_closed': len(closed),
            'valid':        len(valid),
            'invalid':      len(invalid),
            'trades':       results,
        }
    return await asyncio.to_thread(_run)


@app.post('/execution/macro-lock')
async def execution_macro_lock(request: Request):
    """Set or clear the macro lock. Body: {"active": bool, "reason": str}"""
    if not _EXECUTION_AVAILABLE:
        raise HTTPException(status_code=503, detail='execution not loaded')
    body   = await request.json()
    active = bool(body.get('active', False))
    reason = str(body.get('reason', '')).strip()
    await asyncio.to_thread(set_macro_lock, active, reason)
    return {'status': 'ok', 'macro_lock': active, 'reason': reason}

@app.post('/execution/red-folder-lock')
async def execution_red_folder_lock(request: Request):
    """Set or clear the red folder lock. Body: {"active": bool, "reason": str}"""
    if not _EXECUTION_AVAILABLE:
        raise HTTPException(status_code=503, detail='execution not loaded')
    body   = await request.json()
    active = bool(body.get('active', False))
    reason = str(body.get('reason', '')).strip()
    await asyncio.to_thread(set_red_folder_lock, active, reason)
    return {'status': 'ok', 'red_folder_lock': active, 'reason': reason}


@app.post('/execution/trade-permission')
async def execution_trade_permission(request: Request):
    """Enable or disable trade permission. Body: {"active": bool, "reason": str}"""
    if not _EXECUTION_AVAILABLE:
        raise HTTPException(status_code=503, detail='execution not loaded')
    body   = await request.json()
    active = bool(body.get('active', True))
    reason = str(body.get('reason', 'manual')).strip()
    if active:
        await asyncio.to_thread(enable_trade_permission)
    else:
        await asyncio.to_thread(disable_trade_permission, reason)
    return {'status': 'ok', 'trade_permission': active}


@app.post('/execution/close')
async def execution_close(request: Request):
    body   = await request.json()
    symbol = str(body.get('symbol', '')).strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail='symbol is required')
    return await asyncio.to_thread(close_position, symbol)


@app.post('/execution/close-all')
async def execution_close_all():
    return await asyncio.to_thread(close_all_positions)


@app.get('/execution/positions')
async def execution_positions_endpoint():
    """
    Live Alpaca positions cleaned for UI display, plus account summary.

    Broker reality first: every position Alpaca reports is included
    regardless of whether NOVA's journal knows about it. journal_matched
    is false for a broker position with no matching OPEN autonomous journal
    entry -- the same gap the QQQ orphan position exposed -- so the UI can
    surface it instead of leaving it invisible.
    """
    positions_raw = await asyncio.to_thread(get_positions) if _EXECUTION_AVAILABLE else []
    account_raw   = await asyncio.to_thread(get_account)   if _EXECUTION_AVAILABLE else {}
    positions = []
    for p in (positions_raw or []):
        qty      = float(p.get('qty') or 0)
        mval     = float(p.get('market_value') or 0)
        side_raw = str(p.get('side', '')).upper()
        side     = 'SHORT' if 'SHORT' in side_raw else 'LONG'
        cur_price = round(abs(mval) / abs(qty), 4) if qty != 0 else None
        symbol    = p.get('symbol', '')
        matched   = await asyncio.to_thread(has_open_journal_match, symbol) if _EXECUTION_AVAILABLE else False
        positions.append({
            'symbol':         symbol,
            'side':           side,
            'qty':            int(abs(qty)),
            'entry_price':    round(float(p.get('avg_entry') or 0), 4),
            'current_price':  cur_price,
            'unrealized_pnl': round(float(p.get('unrealized_pnl') or 0), 2),
            'status':         'OPEN',
            'journal_matched': matched,
            'warning': (
                None if matched else
                'Broker position detected with no matching NOVA journal entry.'
            ),
        })
    acct = {}
    if account_raw:
        acct = {
            'equity':       round(float(account_raw.get('equity')       or 0), 2),
            'pnl_today':    round(float(account_raw.get('pnl_today')    or 0), 2),
            'buying_power': round(float(account_raw.get('buying_power') or 0), 2),
            'available':    account_raw.get('available', False),
        }
    return {'positions': positions, 'account': acct}


@app.post('/execution/cancel-orders')
async def execution_cancel_orders():
    """Cancel all open orders on Alpaca without closing positions."""
    if not _EXECUTION_AVAILABLE:
        raise HTTPException(status_code=503, detail='execution not loaded')
    return await asyncio.to_thread(cancel_all_orders)


@app.post('/execution/settings')
async def execution_settings_update(request: Request):
    """Update execution mode and active profile parameters (min_grade, max_trades, cooldown)."""
    body = await request.json()
    settings = load_settings()

    new_mode = str(body.get('execution_mode', '')).strip()
    valid_modes = ('paper', 'paper_validation', 'autonomous_test', 'prop_firm', 'live_personal')
    if new_mode and new_mode in valid_modes:
        settings['execution_mode'] = new_mode

    active_mode = settings.get('execution_mode', 'paper_validation')
    profiles = settings.get('execution_profiles', {})
    profile = dict(profiles.get(active_mode, {}))

    if 'min_grade' in body:
        g = str(body['min_grade']).strip().upper()
        if g in ('A+', 'A', 'B', 'C'):
            profile['min_grade'] = g
    if 'max_trades_per_day' in body:
        try:
            profile['max_trades_per_day'] = max(1, int(body['max_trades_per_day']))
        except (TypeError, ValueError):
            pass
    if 'cooldown_minutes' in body:
        try:
            profile['trade_cooldown_minutes'] = max(0, int(body['cooldown_minutes']))
        except (TypeError, ValueError):
            pass

    profiles[active_mode] = profile
    settings['execution_profiles'] = profiles
    write_json_file(SETTINGS_FILE, settings)
    return {'status': 'ok', 'execution_mode': settings['execution_mode'], 'profile': profile}


@app.get('/close-all')
async def close_all_eod_manual():
    """Manually trigger EOD close of all open positions immediately."""
    if not _EXECUTION_AVAILABLE:
        return {'status': 'unavailable', 'error': 'execution not loaded'}
    n = await asyncio.to_thread(close_all_positions_eod)
    return {'status': 'ok', 'positions_closed': n}


@app.get('/system-check')
async def system_check():
    """Return connection and daily-state status for all DONNA subsystems."""
    from core.config import TELEGRAM_BOT_TOKEN, FINNHUB_API_KEY
    from core.state import load_macro_events

    # Alpaca
    alpaca_connected = False
    if _EXECUTION_AVAILABLE:
        try:
            acct = await asyncio.to_thread(get_account)
            alpaca_connected = bool(acct.get('available'))
        except Exception:
            pass

    # Open positions count
    open_pos = 0
    if _EXECUTION_AVAILABLE:
        try:
            open_pos = len(await asyncio.to_thread(get_positions))
        except Exception:
            pass

    # Execution state
    exec_state: dict = {}
    if _EXECUTION_AVAILABLE:
        try:
            exec_state = await asyncio.to_thread(get_execution_status)
        except Exception:
            pass

    # Grok: last fetch time from cached file
    grok_connected = bool(os.getenv('GROK_API_KEY', '').strip())
    last_grok_fetch: str | None = None
    try:
        if _GROK_INTEL_FILE.exists():
            cached = json.loads(_GROK_INTEL_FILE.read_text(encoding='utf-8'))
            last_grok_fetch = cached.get('fetched_at')
    except Exception:
        pass

    # Calendar: last fetch time from macro events file
    last_calendar_fetch: str | None = None
    try:
        macro = load_macro_events()
        last_calendar_fetch = macro.get('fetched_at') or macro.get('last_updated')
    except Exception:
        pass

    ny = now_ny()
    m  = ny.hour * 60 + ny.minute
    eod_close_window = ny.weekday() < 5 and m >= 15 * 60 + 45 and m < 16 * 60 + 30

    from services.execution import BROKER_MODE as _BROKER_MODE
    return {
        'alpaca_connected':      alpaca_connected,
        'grok_connected':        grok_connected,
        'finnhub_connected':     bool(FINNHUB_API_KEY),
        'telegram_connected':    bool(TELEGRAM_BOT_TOKEN),
        'daily_trades_taken':    exec_state.get('daily_trades_taken', 0),
        'first_trade_outcome':   exec_state.get('first_trade_outcome', ''),
        'cumulative_risk_today': exec_state.get('cumulative_risk_today', 0.0),
        'open_positions':        open_pos,
        'eod_close_scheduled':   _EXECUTION_AVAILABLE,
        'eod_close_window_now':  eod_close_window,
        'last_grok_fetch':       last_grok_fetch,
        'last_calendar_fetch':   last_calendar_fetch,
        'broker_mode':           _BROKER_MODE if _EXECUTION_AVAILABLE else 'unavailable',
    }


# ── Morning brief ──────────────────────────────────────────────

@app.get('/send-morning-brief')
async def manual_morning_brief():
    return await asyncio.to_thread(send_morning_brief)


# ── Alert engine ────────────────────────────────────────────────

@app.post('/nova-alert')
async def nova_alert(request: Request):
    """Deliver a NOVA intelligence alert to Discord and Telegram.

    Body (JSON):
      alert_type   : HEADS_UP | EXECUTION_READY | INVALIDATION | NO_TRADE
      symbol       : "ES" | "MES"
      setup_type   : "PROS_LONG" | "ORB_E1_SHORT" | etc.
      direction    : "LONG" | "SHORT" | "N/A"
      priority     : "critical" | "high" | "standard"  (optional)
      session_quality, ib_draw, daily_bias, htf_4h_bias, grade (optional)
      entry_zone, stop, tp1, rr  (optional — execution alerts)
      timeframe, time_to_close, watch_time  (optional — heads-up)
      reason, action, notes  (optional)
      screenshot   : true | false  (optional, default true)
    """
    if not _ALERT_ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail='Alert engine not available')
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid JSON body')

    with_screenshot = body.pop('screenshot', True)
    try:
        data = AlertData(**{k: v for k, v in body.items() if k in AlertData.__dataclass_fields__})
    except Exception as e:
        raise HTTPException(status_code=422, detail=f'Invalid alert data: {e}')

    result = await asyncio.to_thread(deliver_alert, data, with_screenshot)
    return result


@app.get('/alert-status')
async def alert_status():
    """Return current alert governance state."""
    if not _ALERT_ENGINE_AVAILABLE:
        return {'available': False}
    return get_alert_status()


@app.get('/macro-status')
async def macro_status():
    """Return macro Discord feed state — delivered events, VIX, phase, channel health."""
    if not _MACRO_DISCORD_AVAILABLE:
        return {'available': False}
    from delivery.macro_discord import get_macro_discord_status
    return get_macro_discord_status()


@app.post('/nova-alert/test')
async def nova_alert_test():
    """Send a test heads-up alert to verify delivery pipeline."""
    if not _ALERT_ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail='Alert engine not available')
    data = AlertData(
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
        notes='TEST ALERT — delivery pipeline verification',
    )
    result = await asyncio.to_thread(deliver_alert, data, False)
    return result


# ── Webhook / SSE ──────────────────────────────────────────────

@app.post('/webhook')
async def webhook(request: Request):
    body = await request.body()
    text = body.decode('utf-8', errors='ignore').strip()
    if not text:
        raise HTTPException(status_code=400, detail='Empty body')
    try:
        payload = json.loads(text)
    except Exception:
        raise HTTPException(status_code=400, detail=f'Webhook body is not valid JSON. Received: {text[:200]}')

    # ── execution trace: SIGNAL_RECEIVED ──────────────────────
    try:
        from services.execution_trace import log_execution_event as _log_ev
        _log_ev('SIGNAL_RECEIVED', {
            'strategy_family': str(payload.get('strategy_family', '')).upper(),
            'setup_type':      str(payload.get('setup_type', '')).upper(),
            'ticker':          str(payload.get('ticker', '')).upper(),
            'instrument':      str(payload.get('instrument', '')).upper(),
            'signal':          str(payload.get('signal', '')).upper(),
            'session':         str(payload.get('session', '')),
            'score':           str(payload.get('score', '')),
        }, {
            'price':       payload.get('price', ''),
            'timeframe':   payload.get('timeframe', ''),
            'tier':        payload.get('tier', ''),
            'trap_risk':   payload.get('trap_risk', 'false'),
            'signal_reason': payload.get('signal_reason', ''),
        })
    except Exception:
        pass

    result = process_signal(payload)
    if result.get('status') != 'ok':
        raise HTTPException(status_code=500, detail=result.get('error', 'Signal processing failed'))

    # ── Governance gate: enforce strategy, instrument, grade, and daily trade
    # limit BEFORE calling execute_signal() at all. This is the public,
    # internet-facing entry point -- it must never rely solely on what's
    # inside execute_signal() to keep a disallowed signal off the broker.
    # execute_signal() enforces the exact same check internally too (the
    # backstop for every other caller), so this can never be the only gate.
    _sig_data = result['data']
    _gate = await asyncio.to_thread(
        check_execution_governance,
        _sig_data, result.get('parsed', {}), _sig_data.get('instrument', ''),
    )

    execution: dict = {}
    if not _gate['allowed']:
        await asyncio.to_thread(
            log_governance_rejection, _gate['code'], _gate['reason'], _sig_data, result.get('parsed', {}),
        )
        execution = {'status': 'skipped', 'reason': _gate['reason'], 'code': _gate['code']}
    elif _EXECUTION_AVAILABLE:
        try:
            execution = await asyncio.to_thread(execute_signal, result)
        except Exception as e:
            execution = {'status': 'error', 'reason': str(e)}

    if execution.get('status') == 'executed':
        try:
            _sig        = result['data']
            _parsed     = result['parsed']
            _snap       = load_risk_state()
            _harvey     = build_harvey_payload()
            _signal_dir = str(_sig.get('signal', '')).upper()
            _direction  = 'LONG' if _signal_dir in ('LONG', 'BUY') else 'SHORT'
            _auto_trade = {
                'signal_id':       _sig.get('signal_id', ''),
                'strategy_family': _sig.get('strategy_family', 'UNKNOWN'),
                'setup_type':      _sig.get('setup_type', ''),
                'ticker':          _sig.get('ticker', ''),
                'direction':       _direction,
                'entry_price':     execution.get('entry_ref'),
                'exit_price':      None,
                'size':            execution.get('shares', 1),
                'realized_pnl':    None,
                'pnl':             None,
                'outcome':         'OPEN',
                'session':         session_label(),
                'trade_date':      datetime.now(NY_TZ).strftime('%Y-%m-%d'),
                'timestamp':       utc_now_iso(),
                'active_regime':   _harvey.get('regime', {}).get('regime', _snap.get('market_regime', 'UNKNOWN')),
                'score':           _sig.get('score', ''),
                'confidence':      _parsed.get('confidence', ''),
                'trap_risk':       _sig.get('trap_risk', 'false'),
                'macro_risk':      _snap.get('macro_risk', 'medium'),
                'bias_score':      _harvey.get('bias_score', 50),
                'harvey_verdict':  _harvey.get('verdict', 'WAIT'),
                'timeframe':       _sig.get('timeframe', ''),
                'tier':            _sig.get('tier', ''),
                'ict_step':        _sig.get('ict_step', ''),
                'kill_zone':       _sig.get('kill_zone', ''),
                'notes':           'auto-logged on execution',
                'source':          'NOVA_AUTO',
                'order_id':        execution.get('order_id', ''),
            }
            _trades = load_journal()
            _trades.append(_auto_trade)
            save_journal(_trades)
        except Exception as _je:
            print(f'[webhook] auto-journal error: {_je}')

    if _sse_clients:
        evt = json.dumps({
            'type':            'signal',
            'ticker':          result['data'].get('ticker', ''),
            'signal':          result['data'].get('signal', ''),
            'grade':           result['parsed'].get('grade', ''),
            'direction':       result['data'].get('direction', ''),
            'strategy_family': result['data'].get('strategy_family', ''),
            'setup_type':      result['data'].get('setup_type', ''),
            'verdict':         result['parsed'].get('verdict', ''),
            'confidence':      result['parsed'].get('confidence', ''),
            'summary':         result['parsed'].get('summary', ''),
        })
        for q in list(_sse_clients):
            try:
                q.put_nowait(evt)
            except Exception:
                pass
    return {**result, 'execution': execution}


@app.get('/stream')
async def stream():
    queue: asyncio.Queue = asyncio.Queue()
    _sse_clients.append(queue)

    async def event_generator():
        try:
            yield 'data: {"type":"connected"}\n\n'
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f'data: {data}\n\n'
                except asyncio.TimeoutError:
                    yield ': ping\n\n'
        finally:
            try:
                _sse_clients.remove(queue)
            except ValueError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ── Assistant ──────────────────────────────────────────────────

@app.get('/assistant-data')
async def assistant_data():
    return load_assistant_state()


@app.post('/assistant/set-focus')
async def assistant_set_focus(request: Request):
    body  = await request.json()
    value = str(body.get('daily_focus', '')).strip()
    if not value:
        raise HTTPException(status_code=400, detail='daily_focus is required')
    state = load_assistant_state()
    state['daily_focus'] = value
    save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/add-task')
async def assistant_add_task(request: Request):
    body  = await request.json()
    value = str(body.get('task', '')).strip()
    if not value:
        raise HTTPException(status_code=400, detail='task is required')
    state = load_assistant_state()
    state['tasks'].append(value)
    state['tasks'] = state['tasks'][:20]
    save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/delete-task')
async def assistant_delete_task(request: Request):
    body = await request.json()
    try:
        index = int(body.get('index'))
    except Exception:
        raise HTTPException(status_code=400, detail='index must be integer')
    state = load_assistant_state()
    if index < 0 or index >= len(state['tasks']):
        raise HTTPException(status_code=400, detail='invalid task index')
    state['tasks'].pop(index)
    save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/add-reminder')
async def assistant_add_reminder(request: Request):
    body  = await request.json()
    value = str(body.get('reminder', '')).strip()
    if not value:
        raise HTTPException(status_code=400, detail='reminder is required')
    state = load_assistant_state()
    state['reminders'].append(value)
    state['reminders'] = state['reminders'][:20]
    save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/delete-reminder')
async def assistant_delete_reminder(request: Request):
    body = await request.json()
    try:
        index = int(body.get('index'))
    except Exception:
        raise HTTPException(status_code=400, detail='index must be integer')
    state = load_assistant_state()
    if index < 0 or index >= len(state['reminders']):
        raise HTTPException(status_code=400, detail='invalid reminder index')
    state['reminders'].pop(index)
    save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/clear-tasks')
async def assistant_clear_tasks():
    state = load_assistant_state()
    state['tasks'] = []
    save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/clear-reminders')
async def assistant_clear_reminders():
    state = load_assistant_state()
    state['reminders'] = []
    save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/chat')
async def assistant_chat(request: Request):
    body    = await request.json()
    message = str(body.get('message', '')).strip()
    if not message:
        raise HTTPException(status_code=400, detail='message is required')

    from core.config import client
    if not client:
        risk    = load_risk_state()
        driver  = build_market_driver_engine(risk)
        morning = build_morning_edge(risk)
        sig     = build_session_significance(risk)
        msg_lower = message.lower()
        if 'what matters' in msg_lower or 'summary' in msg_lower:
            reply = f"{driver['dominant_driver']} is in control. {sig['summary']}"
        elif 'danger' in msg_lower or 'safe' in msg_lower:
            reply = f"Main threat: {morning['main_threat']}. Open quality: {morning['open_quality']}."
        elif 'mover' in msg_lower or 'company' in msg_lower:
            reply = 'Watch NVDA, MSFT, AMZN, AMD, and TSLA first. They have the most index influence right now.'
        elif 'significant' in msg_lower or 'real' in msg_lower:
            reply = sig['summary']
        else:
            reply = f"NOVA fallback: Bias is {morning['today_bias']}. Focus is {morning['focus']}."
        return {'status': 'ok', 'action': 'none', 'value': '', 'reply': reply, 'assistant': load_assistant_state(), 'risk': load_risk_state(), 'alerts': load_alert_history()[:10]}

    try:
        result        = call_assistant_llm(message)
        updated_state = apply_assistant_action(result['action'], result['value'])
        return {'status': 'ok', **result, 'assistant': updated_state, 'risk': load_risk_state(), 'alerts': load_alert_history()[:10]}
    except Exception as e:
        return {'status': 'error', 'action': 'none', 'value': '', 'reply': f'Assistant error: {str(e)}', 'assistant': load_assistant_state(), 'risk': load_risk_state(), 'alerts': load_alert_history()[:10]}


# ── Journal ────────────────────────────────────────────────────

@app.get('/journal/data')
async def journal_data():
    trades    = load_journal()
    stats     = compute_journal_stats(trades)
    today_str = now_ny().strftime('%Y-%m-%d')

    _closed_outcomes = ('WIN', 'LOSS', 'EOD_CLOSE', 'BREAKEVEN')
    today_pnl = sum(
        float(t.get('realized_pnl', 0) or 0)
        for t in trades
        if t.get('trade_date') == today_str
        and t.get('outcome') in _closed_outcomes
        and t.get('realized_pnl') is not None
        and t.get('outcome') != 'REJECTED'
    )

    # win_rate is already computed correctly by compute_journal_stats (EOD_CLOSE
    # is now classified as WIN/LOSS by pnl sign inside compute_journal_stats).
    # Drop the endpoint-level override — rely on the backend stat.

    stats['today_pnl'] = round(today_pnl, 2)

    return {'status': 'ok', 'trades': trades, 'stats': stats}


@app.get('/journal/signals')
async def journal_signals():
    """Return recent signal log entries for the Journal intelligence feed."""
    import json as _json
    from core.config import SIGNAL_LOG_FILE as _sig_file
    try:
        entries = _json.loads(_sig_file.read_text(encoding='utf-8')) if _sig_file.exists() else []
    except Exception:
        entries = []
    # Return last 150 entries (newest first — file is already newest-first)
    return {'status': 'ok', 'signals': entries[:150], 'total': len(entries)}


@app.get('/api/signal-log/session-development')
async def session_development():
    """
    PROS session development audit data.
    Returns all NY_OPEN PROS signals with ib_maturity, ny_open_minutes, ib_window_closed.
    Use to compare: pre-9:45 vs post-9:45, UNCLEAR vs confirmed IB, grade distribution.
    """
    from delivery.signal_log import get_ny_open_pros, get_stats
    signals = await asyncio.to_thread(get_ny_open_pros, 500)

    # Bucket signals for direct comparison
    pre_945     = [s for s in signals if s.get('ny_open_minutes') is not None and s['ny_open_minutes'] < 15]
    post_945    = [s for s in signals if s.get('ny_open_minutes') is not None and s['ny_open_minutes'] >= 15]
    ib_unclear  = [s for s in signals if s.get('ib_maturity') == 'UNCLEAR']
    ib_forming  = [s for s in signals if s.get('ib_maturity') == 'FORMING']
    ib_mature   = [s for s in signals if s.get('ib_maturity') == 'MATURE']

    def _grade_dist(bucket):
        d = {}
        for s in bucket:
            g = s.get('grade', '')
            if g:
                d[g] = d.get(g, 0) + 1
        return d

    def _exec_rate(bucket):
        if not bucket:
            return None
        return round(sum(1 for s in bucket if s.get('alert_type') == 'EXECUTION_READY') / len(bucket), 3)

    return {
        'total_ny_open_pros': len(signals),
        'buckets': {
            'pre_945':    {'count': len(pre_945),   'exec_rate': _exec_rate(pre_945),   'grade_dist': _grade_dist(pre_945)},
            'post_945':   {'count': len(post_945),  'exec_rate': _exec_rate(post_945),  'grade_dist': _grade_dist(post_945)},
            'ib_unclear': {'count': len(ib_unclear),'exec_rate': _exec_rate(ib_unclear),'grade_dist': _grade_dist(ib_unclear)},
            'ib_forming': {'count': len(ib_forming),'exec_rate': _exec_rate(ib_forming),'grade_dist': _grade_dist(ib_forming)},
            'ib_mature':  {'count': len(ib_mature), 'exec_rate': _exec_rate(ib_mature), 'grade_dist': _grade_dist(ib_mature)},
        },
        'signals': signals,
    }


@app.get('/api/signal-log/direction-churn')
async def direction_churn():
    """
    Direction churn analysis — answers: real market structure change or indicator instability?

    Key fields per flip:
      ib_draw_also_flipped: True  → IB draw changed with direction (potentially real structure change)
      ib_draw_also_flipped: False → direction flipped while IB draw unchanged (interpretation instability candidate)
      held_until_next_flip_mins: how long the new direction was held before flipping again
      rapid_flip_backs_lt2min: flips reversed within 2 minutes (strong instability signal)
      instability_ratio: fraction of flips where IB draw did NOT change (0.0=all real, 1.0=all unstable)
    """
    from delivery.signal_log import get_direction_churn as _get_churn
    return await asyncio.to_thread(_get_churn, 500)


@app.post('/journal/add')
async def journal_add(request: Request):
    body      = await request.json()
    for f in ['ticker', 'direction']:
        if f not in body:
            raise HTTPException(status_code=400, detail=f'Missing field: {f}')

    direction = str(body.get('direction', 'LONG')).upper()
    if direction not in ('LONG', 'SHORT'):
        raise HTTPException(status_code=400, detail='direction must be LONG or SHORT')

    # realized_pnl takes priority; entry/exit/size are optional when it's provided
    realized_pnl_raw = None
    rp_raw = body.get('realized_pnl')
    if rp_raw is not None and rp_raw != '':
        try:
            realized_pnl_raw = float(rp_raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail='realized_pnl must be a number')

    entry, exit_, size = None, None, 1.0
    e_raw, x_raw, s_raw = body.get('entry_price'), body.get('exit_price'), body.get('size')
    if e_raw not in (None, '') or x_raw not in (None, ''):
        try:
            entry = float(e_raw) if e_raw not in (None, '') else None
            exit_ = float(x_raw) if x_raw not in (None, '') else None
            size  = float(s_raw) if s_raw not in (None, '') else 1.0
        except Exception:
            raise HTTPException(status_code=400, detail='entry_price, exit_price, size must be numbers')

    if realized_pnl_raw is None and (entry is None or exit_ is None):
        raise HTTPException(status_code=400, detail='Provide realized_pnl or both entry_price and exit_price')

    # Outcome from the form is the source of truth for sign normalization.
    # Users select WIN/LOSS/BE; the system enforces the correct sign on the stored value.
    outcome_raw = str(body.get('outcome', '')).upper().strip()

    # Compute raw P&L amount before normalization
    if realized_pnl_raw is not None:
        raw_pnl = realized_pnl_raw
    else:
        raw_pnl = (exit_ - entry) * size if direction == 'LONG' else (entry - exit_) * size  # type: ignore[operator]

    # Normalize sign: outcome wins over whatever sign the user typed
    if outcome_raw == 'WIN':
        pnl = round(abs(raw_pnl), 2)
    elif outcome_raw == 'LOSS':
        pnl = round(-abs(raw_pnl), 2)
    elif outcome_raw == 'BREAKEVEN':
        pnl = 0.0
    else:
        pnl = round(raw_pnl, 2)

    # Derive stored outcome from normalized pnl — guaranteed consistent
    outcome = 'WIN' if pnl > 0 else ('LOSS' if pnl < 0 else 'BREAKEVEN')

    state  = load_risk_state()
    try:
        harvey = build_harvey_payload()
    except Exception:
        harvey = {}
    nq_pts = safe_float(state.get('market_snapshot', {}).get('NQ_SESSION_POINTS', 0))

    trade_date_raw = str(body.get('trade_date', '')).strip()
    trade_date     = trade_date_raw if (trade_date_raw and len(trade_date_raw) == 10) else datetime.now(NY_TZ).strftime('%Y-%m-%d')

    # Optional numeric fields
    stop_raw = body.get('stop')
    tp1_raw  = body.get('tp1')
    stop_val = float(stop_raw) if stop_raw not in (None, '', 0) else None
    tp1_val  = float(tp1_raw)  if tp1_raw  not in (None, '', 0) else None

    # Behavioral fields
    emotional_state   = str(body.get('emotional_state', '')).strip()
    behavioral_flags  = body.get('behavioral_flags', [])
    if not isinstance(behavioral_flags, list):
        behavioral_flags = []
    reflection        = str(body.get('reflection', '')).strip()

    # Session: use provided value if given, else auto-detect
    session_val = str(body.get('session', '')).strip() or session_label()

    trade = {
        'ticker':           str(body.get('ticker', '')).upper(),
        'direction':        direction,
        'entry_price':      entry,
        'exit_price':       exit_,
        'size':             size,
        'stop':             stop_val,
        'tp1':              tp1_val,
        'realized_pnl':     pnl,
        'setup_type':       str(body.get('setup_type', '')),
        'notes':            str(body.get('notes', '')),
        'outcome':          outcome,
        'pnl':              pnl,
        'trade_date':       trade_date,
        'timestamp':        utc_now_iso(),
        'active_regime':    harvey.get('regime', {}).get('regime', state.get('market_regime', 'UNKNOWN')),
        'session':          session_val,
        'macro_risk':       state.get('macro_risk', 'medium'),
        'bias_score':       harvey.get('bias_score', 50),
        'harvey_verdict':   harvey.get('verdict', 'WAIT'),
        'nq_points':        nq_pts,
        'emotional_state':  emotional_state,
        'behavioral_flags': behavioral_flags,
        'reflection':       reflection,
    }

    trades = load_journal()
    trades.append(trade)
    save_journal(trades)
    stats = compute_journal_stats(trades)
    return {'status': 'ok', 'trade': trade, 'stats': stats}


@app.get('/journal/screenshot')
async def journal_screenshot(file: str):
    """Serve a chart screenshot by filename. Only files inside the screenshots directory."""
    from fastapi.responses import FileResponse
    from pathlib import Path
    screenshots_dir = Path(__file__).parent / 'mcp' / 'tradingview' / 'screenshots'
    if '/' in file or '\\' in file or '..' in file:
        raise HTTPException(status_code=400, detail='Invalid filename')
    target = screenshots_dir / file
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail='Screenshot not found')
    return FileResponse(str(target), media_type='image/png')


@app.post('/journal/trade-detail')
async def journal_trade_detail(request: Request):
    """Return enriched trade data: record + reasoning timeline + execution trace."""
    import json as _json
    from pathlib import Path
    body      = await request.json()
    trade_idx = int(body.get('index', -1))
    trades    = load_journal()
    if trade_idx < 0 or trade_idx >= len(trades):
        raise HTTPException(status_code=400, detail='Invalid trade index')
    trade = trades[trade_idx]
    ticker = (trade.get('ticker') or '').upper().replace('1!', '')

    from core.config import SIGNAL_LOG_FILE as _sig_file2, TRACE_FILE as _trace_file
    try:
        all_sigs = _json.loads(_sig_file2.read_text(encoding='utf-8')) if _sig_file2.exists() else []
    except Exception:
        all_sigs = []
    nearby = [s for s in all_sigs if ticker in (s.get('symbol') or '').upper()][:10]

    try:
        all_trace = _json.loads(_trace_file.read_text(encoding='utf-8')) if _trace_file.exists() else []
    except Exception:
        all_trace = []
    trace_record = next(
        (tr for tr in all_trace if ticker.upper() in (tr.get('instrument') or tr.get('ticker') or '').upper()),
        None,
    )

    return {
        'status': 'ok',
        'trade': trade,
        'index': trade_idx,
        'reasoning_timeline': nearby,
        'execution_trace': trace_record,
    }


@app.post('/journal/analyze')
async def journal_analyze(request: Request):
    """Generate a NOVA AI review for a journal trade entry. Stores result back to the trade."""
    import json as _json
    from pathlib import Path
    from core.config import client as _claude, ANTHROPIC_ASSISTANT_MODEL

    body      = await request.json()
    trade_idx = int(body.get('index', -1))
    trades    = load_journal()

    if trade_idx < 0 or trade_idx >= len(trades):
        raise HTTPException(status_code=400, detail='Invalid trade index')

    trade = trades[trade_idx]

    # Load nearby signal log entries for context
    from core.config import SIGNAL_LOG_FILE as _sig_file3
    try:
        all_sigs = _json.loads(_sig_file3.read_text(encoding='utf-8')) if _sig_file3.exists() else []
    except Exception:
        all_sigs = []

    # Filter signals: same symbol (MNQ or MES), most recent 8 entries
    ticker = (trade.get('ticker') or '').upper().replace('1!', '')
    nearby = [s for s in all_sigs if ticker in (s.get('symbol') or '').upper()][:8]

    # Build signal context block
    sig_lines = []
    for s in nearby:
        sig_lines.append(
            f"  {s.get('timestamp_et','?')} | {s.get('nova_cmd','?')} | "
            f"Grade {s.get('grade','?')} | Conf {s.get('nova_conf','?')} | "
            f"PROS {s.get('pros_phase','?')} {s.get('pros_direction','?')} | "
            f"OTE {s.get('pros_ote','?')} | IB {s.get('ib_draw','?')} | "
            f"Session Q{s.get('session_quality','?')}"
        )
    sig_context = '\n'.join(sig_lines) if sig_lines else '  No signal log entries found for this instrument.'

    prompt = f"""TRADE RECORD:
Instrument: {trade.get('ticker')} {trade.get('direction')}
Setup: {trade.get('setup_type') or 'unspecified'}
Entry: {trade.get('entry_price') or '—'} | Exit: {trade.get('exit_price') or '—'} | Stop: {trade.get('stop') or '—'} | TP1: {trade.get('tp1') or '—'}
Size: {trade.get('size',1)} | R:R: {trade.get('rr') or '—'}
P&L: {trade.get('realized_pnl')} | Outcome: {trade.get('outcome')}
Session: {trade.get('session') or '—'} | Macro risk: {trade.get('macro_risk') or '—'}
Trader notes: {trade.get('notes') or 'none'}
Emotional state: {trade.get('emotional_state') or 'not reported'}
Behavioral flags: {', '.join(trade.get('behavioral_flags') or []) or 'none'}
Reflection: {trade.get('reflection') or 'none'}

NOVA EVALUATION LOG (closest entries for {ticker}):
{sig_context}

Provide a structured post-trade analysis with these exact sections. Keep each section to 2-4 sentences max. Tactical, operational language only.

QUALIFICATION
Why this setup did or did not meet execution standards. Reference PROS phase, OTE, IB draw, session quality, confidence score.

EXECUTION
Entry timing, stop placement, exit management. Execution score: X/100.

OUTCOME ASSESSMENT
Was the outcome correct given the setup quality? Explain the result.

WHAT SHOULD HAVE HAPPENED
Validate correct trades. Identify the error on incorrect ones. State the right path.

BEHAVIORAL NOTE
One sentence on any behavioral pattern if trader notes or flags suggest it. If none, state "No behavioral flags."
"""

    system = "You are NOVA, an AI trading intelligence system for MES and MNQ micro futures. You give precise, institutional-grade trade reviews. No hedging, no generic advice. Speak directly about this specific trade."

    if not _claude:
        return {'status': 'error', 'detail': 'Claude API not configured'}

    try:
        resp = _claude.messages.create(
            model=ANTHROPIC_ASSISTANT_MODEL,
            system=system,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=800,
        )
        analysis = resp.content[0].text.strip() if resp.content else ''
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Claude API error: {str(e)[:100]}')

    trades[trade_idx]['nova_review']    = analysis
    trades[trade_idx]['nova_review_ts'] = utc_now_iso()
    save_journal(trades)

    return {'status': 'ok', 'analysis': analysis, 'index': trade_idx}


@app.post('/journal/delete')
async def journal_delete(request: Request):
    body = await request.json()
    idx  = body.get('index')
    if idx is None:
        raise HTTPException(status_code=400, detail='index is required')
    trades = load_journal()
    try:
        idx = int(idx)
        if idx < 0 or idx >= len(trades):
            raise HTTPException(status_code=400, detail='index out of range')
        trades.pop(idx)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='index must be an integer')
    save_journal(trades)
    stats = compute_journal_stats(trades)
    return {'status': 'ok', 'stats': stats}
