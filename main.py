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
    MORNING_BRIEF_FILE, NY_TZ,
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

app = FastAPI(title='DONNA v5.0 Live Market Core', version='5.0')
_sse_clients: list[asyncio.Queue] = []

_GROK_API_KEY      = os.getenv('GROK_API_KEY', '').strip()
_GROK_INTEL_FILE   = Path(__file__).parent / 'data' / 'donna_grok_intelligence.json'
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
            # Force close all at 3:45 PM — retry every 60s until flat
            if is_weekday and now.hour == 15 and now.minute >= 45 and not closed_today:
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

@app.on_event('startup')
async def startup():
    ensure_files()
    if _STATE_ENGINE_AVAILABLE:
        print(
            f'State engine loaded — '
            f'date: {_donna_state.get("state_date")}, '
            f'trades today: {_donna_state.get_trade_count()}'
        )
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
    return {'status': 'Donna is online', 'version': app.version}


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
    return send_telegram_message('DONNA TEST MESSAGE')


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

_SP500_HEATMAP_FILE = Path(__file__).parent / 'data' / 'donna_sp500_heatmap.json'
_NQ_HEATMAP_FILE    = Path(__file__).parent / 'data' / 'donna_nq_heatmap.json'

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

_BTC_VIX_CACHE_FILE = Path(__file__).parent / 'data' / 'donna_btc_vix_cache.json'


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


@app.get('/market-reality')
async def market_reality_endpoint():
    """Live market reality state — direction, severity, structure, X/Twitter chatter."""
    try:
        from engines.market_reality import load_market_reality
        return load_market_reality()
    except Exception as exc:
        return {'error': str(exc), 'direction': 'UNKNOWN', 'severity': 'LOW'}


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

    execution: dict = {}
    if _EXECUTION_AVAILABLE:
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
                'source':          'DONNA_AUTO',
                'order_id':        execution.get('order_id', ''),
            }
            _trades = load_journal()
            _trades.append(_auto_trade)
            save_journal(_trades)
        except Exception as _je:
            print(f'[webhook] auto-journal error: {_je}')

    if _sse_clients:
        evt = json.dumps({
            'type':       'signal',
            'ticker':     result['data'].get('ticker', ''),
            'signal':     result['data'].get('signal', ''),
            'verdict':    result['parsed'].get('verdict', ''),
            'confidence': result['parsed'].get('confidence', ''),
            'summary':    result['parsed'].get('summary', ''),
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
            reply = f"Donna fallback: Bias is {morning['today_bias']}. Focus is {morning['focus']}."
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

    today_pnl = sum(
        float(t.get('realized_pnl', 0) or 0)
        for t in trades
        if t.get('trade_date') == today_str
        and t.get('outcome') in ('WIN', 'LOSS')
        and t.get('realized_pnl') is not None
    )

    closed_trades = [t for t in trades if t.get('outcome') in ('WIN', 'LOSS')]
    wins          = len([t for t in closed_trades if t.get('outcome') == 'WIN'])
    win_rate      = (wins / len(closed_trades) * 100) if closed_trades else 0

    stats['today_pnl'] = round(today_pnl, 2)
    stats['win_rate']  = round(win_rate, 1)

    return {'status': 'ok', 'trades': trades, 'stats': stats}


@app.get('/journal/signals')
async def journal_signals():
    """Return recent signal log entries for the Journal intelligence feed."""
    import json as _json
    from pathlib import Path
    sig_file = Path(__file__).parent / 'data' / 'donna_signal_log.json'
    try:
        entries = _json.loads(sig_file.read_text(encoding='utf-8')) if sig_file.exists() else []
    except Exception:
        entries = []
    # Return last 150 entries (newest first — file is already newest-first)
    return {'status': 'ok', 'signals': entries[:150], 'total': len(entries)}


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

    # Compute signed P&L — LONG profits when exit > entry, SHORT when exit < entry
    if realized_pnl_raw is not None:
        pnl = round(realized_pnl_raw, 2)
    else:
        pnl = round((exit_ - entry) * size if direction == 'LONG' else (entry - exit_) * size, 2)  # type: ignore[operator]

    # Outcome is always derived from the signed P&L — never trust the form value
    outcome = 'WIN' if pnl > 0 else ('LOSS' if pnl < 0 else 'BREAKEVEN')

    state  = load_risk_state()
    harvey = build_harvey_payload()
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

    sig_file = Path(__file__).parent / 'data' / 'donna_signal_log.json'
    try:
        all_sigs = _json.loads(sig_file.read_text(encoding='utf-8')) if sig_file.exists() else []
    except Exception:
        all_sigs = []
    nearby = [s for s in all_sigs if ticker in (s.get('symbol') or '').upper()][:10]

    trace_file = Path(__file__).parent / 'data' / 'donna_execution_trace.json'
    try:
        all_trace = _json.loads(trace_file.read_text(encoding='utf-8')) if trace_file.exists() else []
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
    sig_file = Path(__file__).parent / 'data' / 'donna_signal_log.json'
    try:
        all_sigs = _json.loads(sig_file.read_text(encoding='utf-8')) if sig_file.exists() else []
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
