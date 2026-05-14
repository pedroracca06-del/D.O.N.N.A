"""donna_execution.py — DONNA autonomous trading, two-mode broker architecture."""
from __future__ import annotations

import math
import os
from datetime import timedelta

from donna_config import (
    now_ny, utc_now_iso, safe_float, send_telegram_message, session_label,
)
from donna_state import (
    load_risk_state, save_risk_state,
    load_alert_history, save_alert_history,
    load_macro_events,
    load_journal, save_journal,
)

# ── Broker mode ────────────────────────────────────────────────
# Change this one variable to switch execution backends.
# Options: ALPACA_ETF | TRADOVATE | RITHMIC
BROKER_MODE = "ALPACA_ETF"

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

# ── ALPACA_ETF mode: instrument → ETF ticker ───────────────────
# ES / MES signals trade SPY shares (S&P 500 proxy)
# NQ / MNQ signals trade QQQ shares (NASDAQ-100 proxy)
_ETF_MAP = {
    'ES': 'SPY', 'MES': 'SPY',
    'NQ': 'QQQ', 'MNQ': 'QQQ',
}

# Session-aware sizing table — DONNA official risk rules
# NY/London: 1% = $1 000/trade   Asia: 0.5% = $500/trade
# stop/target are $/share distances; cap is hard max shares
_ETF_SIZING: dict[str, dict] = {
    'NY_LON': {
        'SPY': {'risk': 1000.0, 'stop': 5.00, 'target': 10.00, 'cap': 50},
        'QQQ': {'risk': 1000.0, 'stop': 7.50, 'target': 15.00, 'cap': 40},
    },
    'ASIA': {
        'SPY': {'risk':  500.0, 'stop': 5.00, 'target': 10.00, 'cap': 10},
        'QQQ': {'risk':  500.0, 'stop': 7.50, 'target': 15.00, 'cap':  8},
    },
}

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


def _get_etf_price(symbol: str) -> float:
    """
    Fetch live mid-price for an ETF via Alpaca market data REST API.
    Uses direct HTTP rather than the SDK data client for reliability.
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return 0.0
    try:
        import requests as _req
        r = _req.get(
            f'https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest',
            headers={
                'APCA-API-KEY-ID':     ALPACA_API_KEY,
                'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY,
            },
            timeout=5,
        )
        q   = r.json().get('quote', {})
        ask = float(q.get('ap') or 0)
        bid = float(q.get('bp') or 0)
        if ask > 0 and bid > 0:
            return round((ask + bid) / 2, 2)
        return float(ask or bid or 0)
    except Exception:
        return 0.0


# ── ETF signal helpers ─────────────────────────────────────────

def _map_etf(data: dict) -> str | None:
    """Resolve instrument/ticker to 'SPY' or 'QQQ'."""
    combined = (
        str(data.get('instrument', '')).upper() + ' ' +
        str(data.get('ticker', '')).upper()
    )
    if any(k in combined for k in ('NQ', 'MNQ')):
        return 'QQQ'
    if any(k in combined for k in ('ES', 'MES')):
        return 'SPY'
    return None


def _get_etf_sizing(etf: str, session: str) -> dict:
    """Return qty, stop_dist, tgt_dist for DONNA's official sizing rules."""
    key    = 'ASIA' if session == 'ASIA' else 'NY_LON'
    p      = _ETF_SIZING[key].get(etf, _ETF_SIZING['NY_LON']['SPY'])
    qty    = max(1, min(math.floor(p['risk'] / p['stop']), p['cap']))
    return {'qty': qty, 'stop': p['stop'], 'target': p['target']}


def _log_skip(data: dict, parsed: dict, reason: str, code: str = '') -> dict:
    """Persist skip record to donna_risk_state.json."""
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
    upcoming: list[tuple[int, str]] = []

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
    """Return (blocked, reason_code). Sets daily_loss_limit_hit if limit breached."""
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
    """Return start-day anchor for current Asia session (19:00–03:00 ET), or None."""
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


def close_all_positions_eod() -> int:
    """
    Force-close all open positions at 3:45 PM ET.
    Updates existing DONNA_AUTO journal entries (outcome → EOD_CLOSE) or creates
    a new entry for manually placed positions.  Sends a Telegram message per close.
    Returns number of positions closed.
    """
    positions = get_positions()
    if not positions:
        return 0

    api = _client()
    if not api:
        return 0

    ny      = now_ny()
    closed  = 0

    for pos in positions:
        symbol    = pos['symbol']
        qty       = abs(int(pos['qty']))
        is_long   = int(pos['qty']) > 0 or 'long' in str(pos.get('side', '')).lower()
        avg_entry = float(pos['avg_entry'])
        unreal    = float(pos['unrealized_pnl'])
        mkt_val   = float(pos['market_value'])

        # Approximate exit price from market value
        exit_price = round(mkt_val / qty, 2) if qty > 0 else avg_entry

        try:
            api.close_position(symbol)
        except Exception as e:
            print(f'EOD close failed for {symbol}: {e}')
            continue

        realized_pnl = round(unreal, 2)
        outcome_str  = 'WIN' if realized_pnl > 0 else ('LOSS' if realized_pnl < 0 else 'BREAKEVEN')
        exit_time    = ny.strftime('%H:%M:%S ET')

        # Update existing OPEN DONNA_AUTO journal entry if one matches
        trades  = load_journal()
        matched = False
        for i, t in enumerate(trades):
            if (t.get('ticker') == symbol
                    and str(t.get('outcome', '')).upper() == 'OPEN'
                    and t.get('source') == 'DONNA_AUTO'):
                trades[i] = {
                    **t,
                    'exit_price':   exit_price,
                    'exit_time':    exit_time,
                    'realized_pnl': realized_pnl,
                    'pnl':          realized_pnl,
                    'outcome':      'EOD_CLOSE',
                    'notes':        (
                        (t.get('notes') or '').rstrip(' |')
                        + f' | EOD forced close @ {exit_price}'
                    ),
                }
                matched = True
                break

        if not matched:
            trades.append({
                'source':       'DONNA_EOD',
                'ticker':       symbol,
                'direction':    'LONG' if is_long else 'SHORT',
                'trade_date':   ny.strftime('%Y-%m-%d'),
                'time':         exit_time,
                'entry_price':  avg_entry,
                'exit_price':   exit_price,
                'exit_time':    exit_time,
                'size':         qty,
                'realized_pnl': realized_pnl,
                'pnl':          realized_pnl,
                'outcome':      'EOD_CLOSE',
                'session':      'NEW_YORK_CLOSE',
                'broker_mode':  BROKER_MODE,
                'notes':        f'EOD forced close @ {exit_price}',
                'timestamp':    utc_now_iso(),
            })

        save_journal(trades)

        pnl_str = f'+${realized_pnl:.2f}' if realized_pnl >= 0 else f'-${abs(realized_pnl):.2f}'
        send_telegram_message(
            f'DONNA EOD CLOSE\n'
            f'{symbol} {qty} shares ({"LONG" if is_long else "SHORT"}) closed @ {exit_price}\n'
            f'P&L: {pnl_str}'
        )
        closed += 1

    return closed


def get_today_trade_count() -> int:
    return _get_daily_trades_taken()


def get_execution_status() -> dict:
    """Full risk-rule snapshot for the /execution-status endpoint."""
    rf   = _red_folder_status()
    risk = _get_daily_state()
    acct = get_account()
    return {
        'broker_mode':              BROKER_MODE,
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


# ── Journal helpers ────────────────────────────────────────────

def _journal_log_trade(
    data: dict, parsed: dict, symbol: str,
    is_long: bool, qty: int, entry_ref: float,
    stop_px: float, tgt_px: float, order_id: str, session: str,
) -> None:
    """Write a DONNA_AUTO journal entry immediately after a confirmed order."""
    risk   = load_risk_state()
    regime = str(data.get('regime', '') or risk.get('market_regime', '')).upper() or 'UNKNOWN'
    conf   = str(parsed.get('confidence', ''))
    setup  = str(data.get('setup_type', ''))
    tier   = str(data.get('tier', ''))
    ny     = now_ny()

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
        'session':        session,
        'harvey_verdict': 'TAKE',
        'broker_mode':    BROKER_MODE,
        'realized_pnl':   None,
        'pnl':            None,
        'outcome':        'OPEN',
        'notes': (
            f'DONNA autonomous trade. {setup} on {symbol}. '
            f'Regime: {regime}. Confidence: {conf}. Broker: {BROKER_MODE}.'
        ),
        'timestamp': utc_now_iso(),
    }
    trades = load_journal()
    trades.append(entry)
    save_journal(trades)


def check_position_outcomes() -> int:
    """
    Scan OPEN DONNA_AUTO journal entries, query Alpaca for bracket order fills,
    and update journal with realized P&L, exit price/time, and WIN/LOSS/BREAKEVEN.
    Returns number of entries updated.
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

        actual_entry = getattr(order, 'filled_avg_price', None)
        if actual_entry is not None:
            try:
                updates['entry_price'] = float(actual_entry)
            except Exception:
                pass

        legs       = getattr(order, 'legs', None) or []
        filled_leg = next(
            (lg for lg in legs if str(getattr(lg, 'status', '')).lower() == 'filled'),
            None,
        )

        if filled_leg is None:
            if updates:
                trades[idx] = {**trade, **updates}
                updated += 1
            continue

        raw_exit   = getattr(filled_leg, 'filled_avg_price', None)
        exit_price = float(raw_exit) if raw_exit is not None else 0.0
        exit_time  = now_ny().strftime('%H:%M:%S ET')
        try:
            filled_at = getattr(filled_leg, 'filled_at', None)
            if filled_at:
                exit_time = filled_at.astimezone(now_ny().tzinfo).strftime('%H:%M:%S ET')
        except Exception:
            pass

        entry_px  = float(updates.get('entry_price', trade.get('entry_price') or 0))
        qty       = int(trade.get('size') or 1)
        direction = str(trade.get('direction', 'LONG')).upper()

        # ETF shares: P&L = price_diff × shares (no futures point multiplier)
        raw_pnl = (
            (exit_price - entry_px) * qty if direction == 'LONG'
            else (entry_px - exit_price) * qty
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


# ── Placeholder broker functions ───────────────────────────────

def execute_tradovate(signal_data: dict) -> dict:
    """Stub — plug in Tradovate API when ready, then set BROKER_MODE = 'TRADOVATE'."""
    return {'status': 'skipped', 'reason': 'Tradovate not connected yet'}


def execute_rithmic(signal_data: dict) -> dict:
    """Stub — plug in Rithmic API when ready, then set BROKER_MODE = 'RITHMIC'."""
    return {'status': 'skipped', 'reason': 'Rithmic not connected yet'}


# ── ALPACA_ETF execution ───────────────────────────────────────

def _execute_alpaca_etf(data: dict, parsed: dict, session: str, is_long: bool) -> dict:
    """
    Rule 5 + order submission for ALPACA_ETF mode.
    ES/MES → SPY shares, NQ/MNQ → QQQ shares.
    Sizing follows DONNA official rules (session-aware, hard caps applied).
    """
    etf = _map_etf(data)
    if not etf:
        return _log_skip(data, parsed,
            'cannot resolve instrument to SPY or QQQ — check ticker/instrument field')

    api = _client()
    if not api:
        return {
            'status': 'error',
            'reason': 'Alpaca client unavailable — check ALPACA_API_KEY/ALPACA_SECRET_KEY',
        }

    sizing    = _get_etf_sizing(etf, session)
    qty       = sizing['qty']
    stop_dist = sizing['stop']
    tgt_dist  = sizing['target']
    side      = OrderSide.BUY if is_long else OrderSide.SELL

    # Use live ETF price for stop/target — signal price is a futures price and
    # cannot be used as a reference for SPY/QQQ bracket order validation.
    entry_ref = _get_etf_price(etf)
    if entry_ref <= 0:
        return {'status': 'error', 'reason': f'Could not fetch live price for {etf}'}

    if is_long:
        stop_px = round(entry_ref - stop_dist, 2)
        tgt_px  = round(entry_ref + tgt_dist,  2)
    else:
        stop_px = round(entry_ref + stop_dist, 2)
        tgt_px  = round(entry_ref - tgt_dist,  2)

    try:
        order = api.submit_order(
            MarketOrderRequest(
                symbol        = etf,
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

    # Record counters only after confirmed order submission
    _increment_daily_trades()
    if session == 'ASIA':
        _set_asia_trade_taken()

    _journal_log_trade(
        data=data, parsed=parsed, symbol=etf,
        is_long=is_long, qty=qty, entry_ref=entry_ref,
        stop_px=stop_px, tgt_px=tgt_px, order_id=order_id, session=session,
    )

    direction = 'BUY' if is_long else 'SELL'
    record = {
        'type':         'execution',
        'ticker':       etf,
        'signal':       direction,
        'session':      session,
        'timeframe':    data.get('timeframe', ''),
        'price':        str(entry_ref),
        'verdict':      'TAKE',
        'confidence':   parsed.get('confidence', ''),
        'summary':      (f'EXECUTED {direction} {qty} shares {etf} @ {entry_ref}. '
                         f'Stop: {stop_px}, Target: {tgt_px}'),
        'instrument':   etf,
        'tier':         data.get('tier', ''),
        'setup_type':   data.get('setup_type', ''),
        'entry_price':  entry_ref,
        'shares':       qty,
        'stop_price':   stop_px,
        'target_price': tgt_px,
        'order_id':     order_id,
        'timestamp':    utc_now_iso(),
    }
    alerts = load_alert_history()
    alerts.insert(0, record)
    save_alert_history(alerts)

    risk_usd = qty * stop_dist
    send_telegram_message(
        f'DONNA EXECUTED\n'
        f'{direction} {qty} shares {etf} @ {entry_ref}\n'
        f'Stop: {stop_px} ({stop_dist:.2f}/share) | Target: {tgt_px}\n'
        f'Risk: ${risk_usd:.0f} | Session: {session}\n'
        f'Setup: {data.get("setup_type", "")} | Tier: {data.get("tier", "")}\n'
        f'Order ID: {order_id}'
    )

    return {
        'status':       'executed',
        'symbol':       etf,
        'side':         'buy' if is_long else 'sell',
        'shares':       qty,
        'entry_ref':    entry_ref,
        'stop_price':   stop_px,
        'target_price': tgt_px,
        'order_id':     order_id,
    }


# ── Core execution — routes by BROKER_MODE ─────────────────────

def execute_signal(signal_result: dict) -> dict:
    """
    Apply DONNA's 5 official risk rules, then route to the active broker.
    To switch brokers: change BROKER_MODE at the top of this file.

    Rule 1 — RED FOLDER        ±30 min around any HIGH macro event → block.
    Rule 2 — DAILY TRADE LIMIT  max 2 trades per calendar day ET.
    Rule 3 — DAILY LOSS LIMIT   NY/London < -$1 000 | Asia < -$500 → block.
    Rule 4 — ASIA SESSION       confidence ≥ 90%, max 1 trade per Asia session.
    Rule 5 — POSITION SIZING    broker-specific (ALPACA_ETF: floor($500/stop)).
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

    # ── RULE 5 + ORDER — routed by BROKER_MODE
    signal  = str(data.get('signal', '')).upper()
    is_long = signal in ('LONG', 'BUY')

    if BROKER_MODE == 'ALPACA_ETF':
        return _execute_alpaca_etf(data, parsed, session, is_long)
    if BROKER_MODE == 'TRADOVATE':
        return execute_tradovate(signal_result)
    if BROKER_MODE == 'RITHMIC':
        return execute_rithmic(signal_result)
    return {'status': 'error', 'reason': f'Unknown BROKER_MODE: {BROKER_MODE}'}
