"""donna_execution.py — DONNA autonomous paper trading, official 5-rule risk framework."""
from __future__ import annotations

import calendar
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from donna_config import (
    now_ny, utc_now_iso, safe_float, send_telegram_message, session_label,
)
from donna_state import (
    load_risk_state, save_risk_state,
    load_alert_history, save_alert_history,
    load_macro_events,
    load_journal, save_journal,
)

# ── Alpaca setup ───────────────────────────────────────────────

ALPACA_API_KEY    = os.getenv('ALPACA_API_KEY', '').strip()
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY', '').strip()
_PAPER = 'paper' in os.getenv('ALPACA_BASE_URL', 'paper-api.alpaca.markets').lower()

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest, TakeProfitRequest, StopLossRequest,
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
    _ALPACA_LIB = True
except ImportError:
    TradingClient = None  # type: ignore
    _ALPACA_LIB = False

# ── Contract specs (Rule 5) ────────────────────────────────────
# Risk $500/trade = 0.5% of $100 000.
# MES: 4-pt stop × $5/pt = $20 risk → floor(500/20) = 25 → cap 3
# MNQ: 10-pt stop × $2/pt = $20 risk → floor(500/20) = 25 → cap 3

_POINT_VALUE    = {'MES': 5.0,  'MNQ': 2.0}
_DEFAULT_STOP   = {'MES': 4.0,  'MNQ': 10.0}   # points per trade
_MAX_CONTRACTS  = 3
_RISK_PER_TRADE = 500.0   # $500 = 0.5 % of $100 000

# CME quarterly expiry (Globex codes)
_QUARTERLY = [(3, 'H'), (6, 'M'), (9, 'U'), (12, 'Z')]

# ── Risk rule constants ────────────────────────────────────────

_RED_FOLDER_MINS     = 30       # Rule 1: blackout on each side of a HIGH event
_DAILY_TRADE_LIMIT   = 2        # Rule 2: max trades per calendar day ET
_LOSS_LIMIT_NY_LON   = -1000.0  # Rule 3: NY + London P&L floor
_LOSS_LIMIT_ASIA     = -500.0   # Rule 3: Asia P&L floor
_ASIA_MIN_CONFIDENCE = 90.0     # Rule 4: min confidence for Asia execution
_ASIA_MAX_TRADES     = 1        # Rule 4: max trades per Asia session


# ── Alpaca client ──────────────────────────────────────────────

def _client() -> 'TradingClient | None':
    if not _ALPACA_LIB or not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None
    try:
        return TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=_PAPER)
    except Exception:
        return None


# ── Front-month contract resolution ───────────────────────────

def _third_friday(year: int, month: int) -> date:
    weeks   = calendar.monthcalendar(year, month)
    fridays = [w[4] for w in weeks if w[4] != 0]
    return date(year, month, fridays[2])


def _front_month_symbol(base: str) -> str:
    """Return active quarterly symbol, e.g. 'MESM26'. Rolls 7 days before third Friday."""
    today = date.today()
    for yr_offset in range(2):
        year = today.year + yr_offset
        for month, code in _QUARTERLY:
            if yr_offset == 0 and month < today.month:
                continue
            roll_date = _third_friday(year, month) - timedelta(days=7)
            if today <= roll_date:
                return f'{base}{code}{str(year)[2:]}'
    return f'{base}M{str(today.year + 1)[2:]}'


# ── Signal helpers ─────────────────────────────────────────────

def _map_base(data: dict) -> str | None:
    """Resolve signal instrument/ticker to 'MNQ' or 'MES'."""
    instrument = str(data.get('instrument', '')).upper()
    ticker     = str(data.get('ticker', '')).upper()
    if 'NQ' in instrument or 'NQ' in ticker or 'MNQ' in ticker:
        return 'MNQ'
    if 'ES' in instrument or 'ES' in ticker or 'MES' in ticker:
        return 'MES'
    return None


def _calc_qty(base: str) -> int:
    """floor(500 / (stop_pts × point_val)), capped at _MAX_CONTRACTS, minimum 1."""
    stop_pts = _DEFAULT_STOP.get(base, 4.0)
    pv       = _POINT_VALUE.get(base, 5.0)
    qty      = math.floor(_RISK_PER_TRADE / (stop_pts * pv))
    return max(1, min(qty, _MAX_CONTRACTS))


def _log_skip(data: dict, parsed: dict, reason: str, code: str = '') -> dict:
    """Persist skip record (with reason_code) to donna_risk_state.json."""
    risk    = load_risk_state()
    skipped = risk.get('skipped_executions', [])
    skipped.insert(0, {
        'ticker':      data.get('ticker', ''),
        'signal':      data.get('signal', ''),
        'instrument':  data.get('instrument', ''),
        'tier':        data.get('tier', ''),
        'setup_type':  data.get('setup_type', ''),
        'confidence':  parsed.get('confidence', ''),
        'reason':      reason,
        'reason_code': code,
        'timestamp':   utc_now_iso(),
    })
    risk['skipped_executions'] = skipped[:50]
    save_risk_state(risk)
    return {'status': 'skipped', 'reason': reason, 'reason_code': code}


# ── Daily state helpers ────────────────────────────────────────

def _get_daily_state() -> dict:
    """Load risk state, resetting daily counters if ET calendar date has changed."""
    risk      = load_risk_state()
    today_str = now_ny().strftime('%Y-%m-%d')
    if risk.get('daily_trades_date') != today_str:
        risk['daily_trades_date']    = today_str
        risk['daily_trades_taken']   = 0
        risk['daily_loss_limit_hit'] = False
        save_risk_state(risk)
    return risk


# ── RULE 1: RED FOLDER ─────────────────────────────────────────

def _red_folder_status() -> dict:
    """
    Read donna_macro_events.json, find HIGH-importance events, check ±30-min
    blackout window around each.  Also locate the next upcoming HIGH event.

    Returns:
        active            bool  — True if now is inside a blackout window
        reason            str   — human-readable block reason
        next_event_name   str   — name/title of next HIGH event today
        next_event_time_et str  — HH:MM ET of that event
        minutes_to_next   int|None
    """
    result: dict = {
        'active':             False,
        'reason':             '',
        'next_event_name':    '',
        'next_event_time_et': '',
        'minutes_to_next':    None,
    }

    try:
        events = load_macro_events().get('events', [])
    except Exception:
        return result  # fail open — don't block on unreadable calendar

    now_et      = now_ny()
    now_et_mins = now_et.hour * 60 + now_et.minute
    upcoming: list[tuple[int, str]] = []   # (event_mins, title)

    for event in events:
        if str(event.get('importance', '')).lower() != 'high':
            continue
        time_str = str(event.get('time_et', '')).strip()
        if not time_str:
            continue
        try:
            h, m    = map(int, time_str.split(':'))
            ev_mins = h * 60 + m
        except Exception:
            continue

        window_start = ev_mins - _RED_FOLDER_MINS
        window_end   = ev_mins + _RED_FOLDER_MINS
        title        = event.get('title', f'HIGH event at {time_str} ET')

        if window_start <= now_et_mins <= window_end:
            result['active'] = True
            result['reason'] = (
                f'RED_FOLDER_WINDOW — {title} at {time_str} ET, '
                f'within ±{_RED_FOLDER_MINS}min blackout'
            )

        if ev_mins > now_et_mins:
            upcoming.append((ev_mins, title))

    if upcoming:
        upcoming.sort()
        next_mins, next_title = upcoming[0]
        result['next_event_name']    = next_title
        result['next_event_time_et'] = f'{next_mins // 60:02d}:{next_mins % 60:02d} ET'
        result['minutes_to_next']    = next_mins - now_et_mins

    return result


# ── RULE 2: Daily trade limit ──────────────────────────────────

def _get_daily_trades_taken() -> int:
    return int(_get_daily_state().get('daily_trades_taken', 0))


def _increment_daily_trades() -> None:
    risk      = load_risk_state()
    today_str = now_ny().strftime('%Y-%m-%d')
    if risk.get('daily_trades_date') != today_str:
        risk['daily_trades_date']    = today_str
        risk['daily_trades_taken']   = 0
        risk['daily_loss_limit_hit'] = False
    risk['daily_trades_taken'] = int(risk.get('daily_trades_taken', 0)) + 1
    save_risk_state(risk)


# ── RULE 3: Daily loss limit ───────────────────────────────────

def _check_daily_loss_limit(session: str, pnl_today: float) -> tuple[bool, str]:
    """
    Return (blocked, reason_code).
    If limit breached, sets daily_loss_limit_hit=True in risk state.
    If already hit (from earlier in the day), blocks immediately.
    """
    risk = _get_daily_state()

    if risk.get('daily_loss_limit_hit'):
        code = 'DAILY_LOSS_LIMIT_ASIA' if session == 'ASIA' else 'DAILY_LOSS_LIMIT_NY'
        return True, code

    if session == 'ASIA' and pnl_today < _LOSS_LIMIT_ASIA:
        risk['daily_loss_limit_hit'] = True
        save_risk_state(risk)
        return True, 'DAILY_LOSS_LIMIT_ASIA'

    if session in ('LONDON', 'NEW_YORK_CASH') and pnl_today < _LOSS_LIMIT_NY_LON:
        risk['daily_loss_limit_hit'] = True
        save_risk_state(risk)
        return True, 'DAILY_LOSS_LIMIT_NY'

    return False, ''


# ── RULE 4: Asia session ───────────────────────────────────────

def _asia_session_anchor() -> str | None:
    """
    Return 'YYYY-MM-DD' of the calendar day when the current Asia session started,
    or None if we are not currently in the Asia session.
    Asia = 19:00–03:00 ET.  The session is anchored to its start day.
    """
    ny = now_ny()
    h  = ny.hour
    if h >= 19:
        return ny.strftime('%Y-%m-%d')
    if h < 3:
        return (ny - timedelta(days=1)).strftime('%Y-%m-%d')
    return None


def _get_asia_trade_taken() -> bool:
    anchor = _asia_session_anchor()
    if anchor is None:
        return False
    risk = load_risk_state()
    if risk.get('asia_session_anchor') != anchor:
        risk['asia_session_anchor'] = anchor
        risk['asia_trade_taken']    = False
        save_risk_state(risk)
        return False
    return bool(risk.get('asia_trade_taken', False))


def _set_asia_trade_taken() -> None:
    anchor = _asia_session_anchor()
    if anchor is None:
        return
    risk = load_risk_state()
    risk['asia_session_anchor'] = anchor
    risk['asia_trade_taken']    = True
    save_risk_state(risk)


# ── Public helpers ─────────────────────────────────────────────

def get_account() -> dict:
    api = _client()
    if not api:
        return {'available': False, 'error': 'Alpaca not configured'}
    try:
        a = api.get_account()
        return {
            'available':    True,
            'equity':       float(a.equity),
            'cash':         float(a.cash),
            'buying_power': float(a.buying_power),
            'pnl_today':    round(float(a.equity) - float(a.last_equity), 2),
            'status':       str(a.status),
        }
    except Exception as e:
        return {'available': False, 'error': str(e)}


def get_positions() -> list:
    api = _client()
    if not api:
        return []
    try:
        return [
            {
                'symbol':         p.symbol,
                'qty':            int(p.qty),
                'side':           str(p.side),
                'avg_entry':      float(p.avg_entry_price),
                'market_value':   float(p.market_value),
                'unrealized_pnl': float(p.unrealized_pl),
            }
            for p in api.get_all_positions()
        ]
    except Exception:
        return []


def close_position(symbol: str) -> dict:
    api = _client()
    if not api:
        return {'status': 'error', 'error': 'Alpaca not configured'}
    try:
        api.close_position(symbol)
        return {'status': 'ok', 'symbol': symbol}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def close_all_positions() -> dict:
    api = _client()
    if not api:
        return {'status': 'error', 'error': 'Alpaca not configured'}
    try:
        api.close_all_positions(cancel_orders=True)
        return {'status': 'ok'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def get_today_trade_count() -> int:
    """Trades executed today ET, from donna_risk_state daily counter."""
    return _get_daily_trades_taken()


def get_execution_status() -> dict:
    """Full risk-rule snapshot for the /execution-status endpoint."""
    rf        = _red_folder_status()
    risk      = _get_daily_state()
    acct      = get_account()
    return {
        'daily_trades_taken':       int(risk.get('daily_trades_taken', 0)),
        'daily_loss_limit_hit':     bool(risk.get('daily_loss_limit_hit', False)),
        'asia_trade_taken':         _get_asia_trade_taken(),
        'red_folder_window_active': rf['active'],
        'next_red_folder_event':    rf['next_event_name'],
        'next_event_time_et':       rf['next_event_time_et'],
        'minutes_to_next_event':    rf['minutes_to_next'],
        'current_pnl_today':        acct.get('pnl_today'),
        'session':                  session_label(),
        'account':                  acct,
        'positions':                get_positions(),
    }


# ── Journal helpers ───────────────────────────────────────────

def _journal_log_trade(
    data: dict, parsed: dict, symbol: str, base: str,
    is_long: bool, qty: int, entry_ref: float,
    stop_px: float, tgt_px: float, order_id: str, session: str,
) -> None:
    """Write a DONNA_AUTO journal entry immediately after a confirmed bracket order."""
    risk    = load_risk_state()
    regime  = str(data.get('regime', '') or risk.get('market_regime', '')).upper() or 'UNKNOWN'
    macro   = risk.get('macro_risk', 'medium')
    conf    = str(parsed.get('confidence', ''))
    setup   = str(data.get('setup_type', ''))
    tier    = str(data.get('tier', ''))
    instr   = str(data.get('instrument', symbol))
    ny      = now_ny()

    entry = {
        'source':         'DONNA_AUTO',
        'order_id':       order_id,
        'ticker':         symbol,
        'direction':      'LONG' if is_long else 'SHORT',
        'trade_date':     ny.strftime('%Y-%m-%d'),
        'time':           ny.strftime('%H:%M:%S ET'),
        'entry_price':    entry_ref,
        'stop_price':     stop_px,
        'target_price':   tgt_px,
        'exit_price':     None,
        'exit_time':      None,
        'size':           qty,
        'setup_type':     setup,
        'tier':           tier,
        'confidence':     conf,
        'regime':         regime,
        'active_regime':  regime,
        'macro_risk':     macro,
        'session':        session,
        'harvey_verdict': 'TAKE',
        'realized_pnl':   None,
        'pnl':            None,
        'outcome':        'OPEN',
        'notes': (
            f'DONNA autonomous trade. {setup} on {instr}. '
            f'Regime: {regime}. Confidence: {conf}.'
        ),
        'timestamp': utc_now_iso(),
    }
    trades = load_journal()
    trades.append(entry)
    save_journal(trades)


def check_position_outcomes() -> int:
    """
    Scan journal entries with outcome=OPEN/source=DONNA_AUTO, query Alpaca for
    each bracket order's leg fills, and update the journal with realized P&L,
    exit price/time, and WIN/LOSS/BREAKEVEN outcome.  Returns number updated.
    """
    trades    = load_journal()
    open_auto = [
        (i, t) for i, t in enumerate(trades)
        if t.get('source') == 'DONNA_AUTO'
        and str(t.get('outcome', '')).upper() == 'OPEN'
        and t.get('order_id')
    ]
    if not open_auto:
        return 0

    api = _client()
    if not api:
        return 0

    updated = 0
    for idx, trade in open_auto:
        try:
            order = api.get_order_by_id(trade['order_id'])
        except Exception:
            continue

        updates: dict = {}

        # Capture actual entry fill price if Alpaca has it
        actual_entry = getattr(order, 'filled_avg_price', None)
        if actual_entry is not None:
            try:
                updates['entry_price'] = float(actual_entry)
            except Exception:
                pass

        # Find the leg that filled (TP or SL)
        legs       = getattr(order, 'legs', None) or []
        filled_leg = next(
            (lg for lg in legs if str(getattr(lg, 'status', '')).lower() == 'filled'),
            None,
        )

        if filled_leg is None:
            # Position still open — only write entry price update if changed
            if updates:
                trades[idx] = {**trade, **updates}
                updated += 1
            continue

        # Exit price & time
        raw_exit   = getattr(filled_leg, 'filled_avg_price', None)
        exit_price = float(raw_exit) if raw_exit is not None else 0.0
        exit_time  = now_ny().strftime('%H:%M:%S ET')
        try:
            filled_at = getattr(filled_leg, 'filled_at', None)
            if filled_at:
                exit_time = filled_at.astimezone(now_ny().tzinfo).strftime('%H:%M:%S ET')
        except Exception:
            pass

        # P&L (futures dollar value)
        entry_px  = float(updates.get('entry_price', trade.get('entry_price') or 0))
        qty       = int(trade.get('size') or 1)
        direction = str(trade.get('direction', 'LONG')).upper()
        ticker    = str(trade.get('ticker', ''))
        base      = 'MNQ' if ('MNQ' in ticker or 'NQ' in ticker) else 'MES'
        pv        = _POINT_VALUE.get(base, 5.0)

        raw_pnl = (
            (exit_price - entry_px) * qty * pv if direction == 'LONG'
            else (entry_px - exit_price) * qty * pv
        )
        realized_pnl = round(raw_pnl, 2)
        outcome      = 'WIN' if realized_pnl > 0 else ('LOSS' if realized_pnl < 0 else 'BREAKEVEN')

        trades[idx] = {
            **trade,
            **updates,
            'exit_price':   exit_price,
            'exit_time':    exit_time,
            'realized_pnl': realized_pnl,
            'pnl':          realized_pnl,
            'outcome':      outcome,
        }
        updated += 1

    if updated:
        save_journal(trades)
    return updated


# ── Core execution ─────────────────────────────────────────────

def execute_signal(signal_result: dict) -> dict:
    """
    Apply DONNA's 5 official risk rules then, if all pass, submit a bracket
    market order via Alpaca paper.  Every blocked TAKE signal is logged with
    an exact reason_code to donna_risk_state.json.

    Rule 1 — RED FOLDER       ±30 min around any HIGH macro event → block.
    Rule 2 — DAILY TRADE LIMIT  max 2 trades per calendar day ET.
    Rule 3 — DAILY LOSS LIMIT   NY/London < -$1 000 | Asia < -$500 → block.
    Rule 4 — ASIA SESSION       confidence ≥ 90%, max 1 trade per Asia session.
    Rule 5 — POSITION SIZING    floor(500 / (stop_pts × point_val)), cap 3.
    """
    parsed = signal_result.get('parsed', {})
    data   = signal_result.get('data', {})

    # ── VERDICT — non-TAKE signals not logged as skips
    if str(parsed.get('verdict', '')).upper() != 'TAKE':
        return {'status': 'skipped', 'reason': 'verdict not TAKE'}

    # ── RULE 1: RED FOLDER
    rf = _red_folder_status()
    if rf['active']:
        return _log_skip(data, parsed, rf['reason'], 'RED_FOLDER_WINDOW')

    # ── Session + account P&L (shared by Rules 2–4)
    session   = session_label()
    acct      = get_account()
    pnl_today = acct.get('pnl_today', 0.0) if acct.get('available') else 0.0

    # ── RULE 2: DAILY TRADE LIMIT
    trades_today = _get_daily_trades_taken()
    if trades_today >= _DAILY_TRADE_LIMIT:
        return _log_skip(data, parsed,
            f'daily trade limit reached — {trades_today}/{_DAILY_TRADE_LIMIT} trades taken today',
            'DAILY_TRADE_LIMIT')

    # ── RULE 3: DAILY LOSS LIMIT
    loss_hit, loss_code = _check_daily_loss_limit(session, pnl_today)
    if loss_hit:
        limit = _LOSS_LIMIT_ASIA if session == 'ASIA' else _LOSS_LIMIT_NY_LON
        return _log_skip(data, parsed,
            f'daily loss limit hit — P&L ${pnl_today:,.2f} (limit ${limit:,.0f}) [{session}]',
            loss_code)

    # ── RULE 4: ASIA SESSION RULES
    if session == 'ASIA':
        try:
            confidence_val = float(
                str(parsed.get('confidence', '0')).replace('%', '').strip()
            )
        except Exception:
            confidence_val = 0.0

        if confidence_val < _ASIA_MIN_CONFIDENCE:
            return _log_skip(data, parsed,
                f'Asia session requires confidence ≥ {_ASIA_MIN_CONFIDENCE:.0f}% '
                f'— signal is {confidence_val:.1f}%',
                'ASIA_CONFIDENCE_TOO_LOW')

        if _get_asia_trade_taken():
            return _log_skip(data, parsed,
                'Asia session trade already taken — max 1 trade per Asia session',
                'ASIA_TRADE_ALREADY_TAKEN')

    # ── SYMBOL RESOLUTION
    base = _map_base(data)
    if not base:
        return _log_skip(data, parsed, 'cannot resolve instrument to MNQ or MES')
    symbol = _front_month_symbol(base)

    # ── ALPACA CLIENT
    api = _client()
    if not api:
        return {
            'status': 'error',
            'reason': 'Alpaca client unavailable — check ALPACA_API_KEY/ALPACA_SECRET_KEY',
        }

    # ── RULE 5: POSITION SIZING — floor(500 / (stop_pts × point_val)), cap 3
    signal    = str(data.get('signal', '')).upper()
    is_long   = signal in ('LONG', 'BUY')
    side      = OrderSide.BUY if is_long else OrderSide.SELL
    qty       = _calc_qty(base)
    stop_pts  = _DEFAULT_STOP[base]
    tgt_pts   = stop_pts * 2   # 2:1 R:R
    entry_ref = safe_float(data.get('price', 0))

    if is_long:
        stop_px = round(entry_ref - stop_pts, 2)
        tgt_px  = round(entry_ref + tgt_pts,  2)
    else:
        stop_px = round(entry_ref + stop_pts, 2)
        tgt_px  = round(entry_ref - tgt_pts,  2)

    # ── BRACKET ORDER
    try:
        order = api.submit_order(
            MarketOrderRequest(
                symbol        = symbol,
                qty           = qty,
                side          = side,
                time_in_force = TimeInForce.DAY,
                order_class   = OrderClass.BRACKET,
                take_profit   = TakeProfitRequest(limit_price=tgt_px),
                stop_loss     = StopLossRequest(stop_price=stop_px),
            )
        )
        order_id = str(order.id)
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}

    # ── RECORD COUNTERS — only after confirmed order submission
    _increment_daily_trades()
    if session == 'ASIA':
        _set_asia_trade_taken()

    # ── AUTO-JOURNAL — create OPEN entry immediately
    _journal_log_trade(
        data=data, parsed=parsed, symbol=symbol, base=base,
        is_long=is_long, qty=qty, entry_ref=entry_ref,
        stop_px=stop_px, tgt_px=tgt_px, order_id=order_id, session=session,
    )

    # ── LOG EXECUTION
    direction = 'BUY' if is_long else 'SELL'
    record = {
        'type':          'execution',
        'ticker':        symbol,
        'signal':        direction,
        'session':       session,
        'timeframe':     data.get('timeframe', ''),
        'price':         str(entry_ref),
        'verdict':       'TAKE',
        'confidence':    parsed.get('confidence', ''),
        'summary':       (f'EXECUTED {direction} {qty}x {symbol} @ {entry_ref}. '
                          f'Stop: {stop_px}, Target: {tgt_px}'),
        'instrument':    symbol,
        'tier':          data.get('tier', ''),
        'setup_type':    data.get('setup_type', ''),
        'signal_reason': data.get('signal_reason', ''),
        'entry_price':   entry_ref,
        'contracts':     qty,
        'stop_price':    stop_px,
        'target_price':  tgt_px,
        'order_id':      order_id,
        'timestamp':     utc_now_iso(),
    }
    alerts = load_alert_history()
    alerts.insert(0, record)
    save_alert_history(alerts)

    send_telegram_message(
        f'DONNA EXECUTED\n'
        f'{direction} {qty}x {symbol} @ {entry_ref}\n'
        f'Stop: {stop_px} | Target: {tgt_px}\n'
        f'Setup: {data.get("setup_type", "")} | Tier: {data.get("tier", "")}\n'
        f'Order ID: {order_id}'
    )

    return {
        'status':       'executed',
        'symbol':       symbol,
        'side':         'buy' if is_long else 'sell',
        'contracts':    qty,
        'entry_ref':    entry_ref,
        'stop_price':   stop_px,
        'target_price': tgt_px,
        'order_id':     order_id,
    }
