from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse

from donna_config import (
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_ASSISTANT_MODEL,
    TELEGRAM_BOT_TOKEN, TELEGRAM_ALERT_MODE, FOREX_FACTORY_NOTES_URL,
    FINNHUB_API_KEY, FMP_API_KEY, ALPHA_VANTAGE_API_KEY,
    RISK_STATE_FILE, ALERTS_FILE, ASSISTANT_FILE, SETTINGS_FILE, MACRO_EVENTS_FILE,
    MORNING_BRIEF_FILE, NY_TZ,
    CACHE, now_ny, utc_now_iso, session_label, safe_float,
    send_telegram_message,
)
from donna_state import (
    ensure_files,
    load_risk_state, save_risk_state,
    load_alert_history, save_alert_history,
    load_assistant_state, save_assistant_state,
    load_settings,
    load_macro_events,
    load_journal, save_journal, compute_journal_stats,
    read_json_file, write_json_file,
)
from donna_engines import (
    build_harvey_payload, build_dashboard_payload,
    build_scenario_engine, build_performance_memory,
    build_market_driver_engine, build_morning_edge, build_session_significance,
    get_live_major_indexes, get_live_market_data, get_live_movers,
    get_live_calendar, get_live_earnings, get_live_news, get_live_futures_macro_pulse,
    send_morning_brief,
)
from donna_signals import process_signal

try:
    from donna_execution import (
        execute_signal,
        get_account, get_positions,
        close_position, close_all_positions,
        get_today_trade_count,
    )
    _EXECUTION_AVAILABLE = True
except Exception:
    _EXECUTION_AVAILABLE = False
    def execute_signal(r):           return {'status': 'unavailable'}
    def get_account():               return {'available': False}
    def get_positions():             return []
    def close_position(s):           return {'status': 'unavailable'}
    def close_all_positions():       return {'status': 'unavailable'}
    def get_today_trade_count():     return 0

from donna_assistant import (
    ASSISTANT_SYSTEM_PROMPT, call_assistant_llm, apply_assistant_action,
)
from donna_html import DASHBOARD_HTML

try:
    from donna_news import process_news_guard_cycle
except Exception:
    def process_news_guard_cycle():
        return None

try:
    from donna_risk_engine import (
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
    from donna_headlines import process_headlines_cycle, check_todays_breaking_events
except Exception:
    def process_headlines_cycle():
        return None
    def check_todays_breaking_events():
        return {'events_found': 0, 'high_events': [], 'risk_escalated': False,
                'red_folder': False, 'error': 'donna_headlines not available'}

try:
    from donna_finnhub import process_finnhub_cycle
except Exception:
    def process_finnhub_cycle():
        return None

app = FastAPI(title='DONNA v5.0 Live Market Core', version='5.0')
_sse_clients: list[asyncio.Queue] = []


# ── Background loops ───────────────────────────────────────────

async def morning_brief_loop():
    while True:
        try:
            ny        = now_ny()
            today_str = ny.strftime('%Y-%m-%d')
            if ny.weekday() < 5 and ny.hour == 9 and ny.minute == 0:
                state = read_json_file(MORNING_BRIEF_FILE, {})
                if state.get('last_sent_date') != today_str:
                    print(f'DONNA morning brief: sending for {today_str}')
                    result = await asyncio.to_thread(send_morning_brief)
                    print(f'DONNA morning brief: {result}')
        except Exception as e:
            print(f'Morning brief loop error: {e}')
        await asyncio.sleep(60)


async def news_loop():
    while True:
        try:
            await asyncio.to_thread(process_news_guard_cycle)
        except Exception as e:
            print('Donna News loop error:', str(e))
        await asyncio.sleep(300)


async def headline_loop():
    while True:
        try:
            await asyncio.to_thread(process_headlines_cycle)
        except Exception as e:
            print('Headline loop error:', str(e))
        await asyncio.sleep(900)


async def finnhub_loop():
    while True:
        try:
            await asyncio.to_thread(process_finnhub_cycle)
        except Exception as e:
            print('Finnhub loop error:', str(e))
        await asyncio.sleep(300)


# ── Startup ────────────────────────────────────────────────────

@app.on_event('startup')
async def startup():
    ensure_files()
    await asyncio.to_thread(check_todays_breaking_events)
    asyncio.create_task(news_loop())
    asyncio.create_task(headline_loop())
    asyncio.create_task(finnhub_loop())
    asyncio.create_task(morning_brief_loop())


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
        'telegram_alert_mode':         TELEGRAM_ALERT_MODE,
        'chat_model':                  ANTHROPIC_ASSISTANT_MODEL,
        'fast_model':                  ANTHROPIC_MODEL,
    }


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
    return build_harvey_payload()


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


# ── Execution engine ───────────────────────────────────────────

@app.get('/execution-status')
async def execution_status():
    if not _EXECUTION_AVAILABLE:
        return {'available': False, 'error': 'donna_execution not loaded'}

    account, positions, trades_today = await asyncio.gather(
        asyncio.to_thread(get_account),
        asyncio.to_thread(get_positions),
        asyncio.to_thread(get_today_trade_count),
    )

    stop_trading = False
    try:
        from donna_risk_engine import load_re_state
        stop_trading = bool(load_re_state().get('stop_trading', False))
    except Exception:
        pass

    return {
        'available':     True,
        'account':       account,
        'positions':     positions,
        'pnl_today':     account.get('pnl_today', 0),
        'trades_today':  trades_today,
        'stop_trading':  stop_trading,
    }


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


# ── Morning brief ──────────────────────────────────────────────

@app.get('/send-morning-brief')
async def manual_morning_brief():
    return await asyncio.to_thread(send_morning_brief)


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
    result = process_signal(payload)
    if result.get('status') != 'ok':
        raise HTTPException(status_code=500, detail=result.get('error', 'Signal processing failed'))

    execution: dict = {}
    if _EXECUTION_AVAILABLE:
        try:
            execution = await asyncio.to_thread(execute_signal, result)
        except Exception as e:
            execution = {'status': 'error', 'reason': str(e)}

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

    from donna_config import client
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
    trades = load_journal()
    stats  = compute_journal_stats(trades)
    return {'status': 'ok', 'trades': trades, 'stats': stats}


@app.post('/journal/add')
async def journal_add(request: Request):
    body     = await request.json()
    for f in ['ticker', 'direction', 'outcome']:
        if f not in body:
            raise HTTPException(status_code=400, detail=f'Missing field: {f}')

    direction = str(body.get('direction', 'LONG')).upper()
    outcome   = str(body.get('outcome', 'WIN')).upper()
    if direction not in ('LONG', 'SHORT'):
        raise HTTPException(status_code=400, detail='direction must be LONG or SHORT')
    if outcome not in ('WIN', 'LOSS', 'BREAKEVEN'):
        raise HTTPException(status_code=400, detail='outcome must be WIN, LOSS, or BREAKEVEN')

    # realized_pnl takes priority; entry/exit/size are optional when it's provided
    realized_pnl = None
    rp_raw = body.get('realized_pnl')
    if rp_raw is not None and rp_raw != '':
        try:
            realized_pnl = float(rp_raw)
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

    if realized_pnl is None and (entry is None or exit_ is None):
        raise HTTPException(status_code=400, detail='Provide realized_pnl or both entry_price and exit_price')

    if realized_pnl is not None:
        pnl = round(realized_pnl, 2)
    else:
        pnl = round((exit_ - entry) * size if direction == 'LONG' else (entry - exit_) * size, 2)  # type: ignore[operator]

    state  = load_risk_state()
    harvey = build_harvey_payload()
    nq_pts = safe_float(state.get('market_snapshot', {}).get('NQ_SESSION_POINTS', 0))

    trade_date_raw = str(body.get('trade_date', '')).strip()
    trade_date     = trade_date_raw if (trade_date_raw and len(trade_date_raw) == 10) else datetime.now(NY_TZ).strftime('%Y-%m-%d')

    trade = {
        'ticker':         str(body.get('ticker', '')).upper(),
        'direction':      direction,
        'entry_price':    entry,
        'exit_price':     exit_,
        'size':           size,
        'realized_pnl':   realized_pnl,
        'setup_type':     str(body.get('setup_type', '')),
        'notes':          str(body.get('notes', '')),
        'outcome':        outcome,
        'pnl':            pnl,
        'trade_date':     trade_date,
        'timestamp':      utc_now_iso(),
        'active_regime':  harvey.get('regime', {}).get('regime', state.get('market_regime', 'UNKNOWN')),
        'session':        session_label(),
        'macro_risk':     state.get('macro_risk', 'medium'),
        'bias_score':     harvey.get('bias_score', 50),
        'harvey_verdict': harvey.get('verdict', 'WAIT'),
        'nq_points':      nq_pts,
    }

    trades = load_journal()
    trades.append(trade)
    save_journal(trades)
    stats = compute_journal_stats(trades)
    return {'status': 'ok', 'trade': trade, 'stats': stats}


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
