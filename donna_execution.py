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
from donna_state_engine import state as _state

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
        'SPY': {'risk': 1000.0, 'stop': 10.00, 'target': 20.00, 'cap': 100},
        'QQQ': {'risk': 1000.0, 'stop': 15.00, 'target': 30.00, 'cap':  66},
    },
    'ASIA': {
        'SPY': {'risk':  500.0, 'stop': 10.00, 'target': 20.00, 'cap': 10},
        'QQQ': {'risk':  500.0, 'stop': 15.00, 'target': 30.00, 'cap':  8},
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
        risk['daily_trades_date']      = today_str
        risk['daily_trades_taken']     = 0
        risk['daily_loss_limit_hit']   = False
        risk['cumulative_risk_today']  = 0.0
        risk['first_trade_outcome']    = ''
        risk['size_reduction_active']  = False
        risk['daily_loss_trade_hit']   = False
        save_risk_state(risk)
        try:
            _state.reset_daily()
        except Exception as _e:
            print(f'[state_engine] _get_daily_state reset failed: {_e}')
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
    return _state.get('daily_trade_count', 0)


def _increment_daily_trades() -> None:
    _state.increment_trade_count()
    # Backup write to donna_risk_state.json
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
        try:
            _state.set_many({'daily_loss_trade_hit': True, 'trade_permission': False})
            _state.add_lockout('DAILY_LOSS_LIMIT_HIT')
        except Exception as _e:
            print(f'[state_engine] _check_daily_loss_limit write failed: {_e}')
        return True, 'DAILY_LOSS_LIMIT_ASIA'

    if session in ('LONDON', 'NEW_YORK_CASH') and pnl_today < _LOSS_LIMIT_NY_LON:
        risk['daily_loss_limit_hit'] = True
        save_risk_state(risk)
        try:
            _state.set_many({'daily_loss_trade_hit': True, 'trade_permission': False})
            _state.add_lockout('DAILY_LOSS_LIMIT_HIT')
        except Exception as _e:
            print(f'[state_engine] _check_daily_loss_limit write failed: {_e}')
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
    try:
        _state.set('asia_trade_taken', True)
    except Exception as _e:
        print(f'[state_engine] _set_asia_trade_taken write failed: {_e}')


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
        _state.remove_position(symbol)
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
            _state.remove_position(symbol)
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

    _state.set('eod_lock', True)
    _state.add_lockout('EOD_LOCK_ACTIVE')
    print('[EOD] eod_lock=True — no new executions until midnight reset')
    return closed


def get_today_trade_count() -> int:
    return _get_daily_trades_taken()


# ── Lock-control functions ─────────────────────────────────────

def set_macro_lock(active: bool, reason: str = '') -> None:
    _state.set('macro_lock', active)
    if active:
        _state.add_lockout(f'MACRO_LOCK: {reason}' if reason else 'MACRO_LOCK_ACTIVE')
        print(f'[macro_lock] SET — {reason}')
    else:
        lockouts = [
            l for l in (_state.get('risk_lockouts') or [])
            if not (l.get('reason', '') if isinstance(l, dict) else l).startswith('MACRO_LOCK')
        ]
        _state.set_many({'macro_lock': False, 'risk_lockouts': lockouts})
        print('[macro_lock] CLEARED')


def set_red_folder_lock(active: bool, event_name: str = '') -> None:
    _state.set('red_folder_lock', active)
    if active:
        _state.add_lockout(f'RED_FOLDER: {event_name}' if event_name else 'RED_FOLDER_WINDOW')
        print(f'[red_folder_lock] SET — {event_name}')
    else:
        lockouts = [
            l for l in (_state.get('risk_lockouts') or [])
            if not (l.get('reason', '') if isinstance(l, dict) else l).startswith('RED_FOLDER')
        ]
        _state.set_many({'red_folder_lock': False, 'risk_lockouts': lockouts})
        print('[red_folder_lock] CLEARED')


def disable_trade_permission(reason: str = 'manual_disable') -> None:
    _state.set_many({'trade_permission': False})
    _state.add_lockout(f'TRADE_PERMISSION_DISABLED: {reason}')
    print(f'[trade_permission] DISABLED — {reason}')


def enable_trade_permission() -> None:
    _state.set_many({'trade_permission': True})
    lockouts = [
        l for l in (_state.get('risk_lockouts') or [])
        if not (l.get('reason', '') if isinstance(l, dict) else l).startswith('TRADE_PERMISSION')
    ]
    _state.set('risk_lockouts', lockouts)
    print('[trade_permission] ENABLED')


def get_execution_status() -> dict:
    """Full risk-rule snapshot for the /execution-status endpoint."""
    rf   = _red_folder_status()
    risk = _get_daily_state()
    acct = get_account()
    return {
        'broker_mode':              BROKER_MODE,
        'daily_trades_taken':       _state.get('daily_trade_count', 0),
        'daily_loss_limit_hit':     bool(risk.get('daily_loss_limit_hit', False)),
        'daily_loss_trade_hit':     bool(risk.get('daily_loss_trade_hit', False)),
        'first_trade_outcome':      risk.get('first_trade_outcome', ''),
        'size_reduction_active':    bool(risk.get('size_reduction_active', False)),
        'cumulative_risk_today':    float(risk.get('cumulative_risk_today', 0.0)),
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
    Query Alpaca for all closed orders today, match to OPEN DONNA_AUTO journal
    entries by order_id (bracket legs) or symbol+direction fallback.
    Updates exit_price, realized_pnl, outcome, exit_time.  Returns count updated.
    """
    trades    = load_journal()
    open_auto = [
        (i, t) for i, t in enumerate(trades)
        if t.get('source') == 'DONNA_AUTO'
        and str(t.get('outcome', '')).upper() == 'OPEN'
    ]
    if not open_auto:
        return 0

    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return 0

    # Fetch all of today's orders from Alpaca REST (nested=true returns bracket legs)
    import requests as _req
    from datetime import timezone as _tz
    _base     = 'https://paper-api.alpaca.markets' if _PAPER else 'https://api.alpaca.markets'
    today_ny  = now_ny().replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = today_ny.astimezone(_tz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        r = _req.get(
            f'{_base}/v2/orders',
            headers={
                'APCA-API-KEY-ID':     ALPACA_API_KEY,
                'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY,
            },
            params={'status': 'all', 'after': today_utc, 'limit': 100, 'nested': 'true'},
            timeout=10,
        )
        today_orders = r.json() if (r.ok and isinstance(r.json(), list)) else []
    except Exception:
        today_orders = []

    # Lookups: by parent order id; by symbol+side for filled exits
    orders_by_id: dict = {str(o.get('id', '')): o for o in today_orders}
    exit_fills:   dict = {}
    for o in today_orders:
        if str(o.get('status', '')).lower() != 'filled':
            continue
        key = f"{str(o.get('symbol', '')).upper()}:{str(o.get('side', '')).lower()}"
        exit_fills.setdefault(key, []).append(o)

    def _parse_time(iso: str) -> str:
        try:
            from datetime import datetime as _dt
            ft = _dt.fromisoformat(iso.replace('Z', '+00:00'))
            return ft.astimezone(now_ny().tzinfo).strftime('%H:%M:%S ET')
        except Exception:
            return now_ny().strftime('%H:%M:%S ET')

    updated = 0
    for idx, trade in open_auto:
        order_id  = str(trade.get('order_id', ''))
        symbol    = str(trade.get('ticker', '')).upper()
        direction = str(trade.get('direction', 'LONG')).upper()
        exit_side = 'sell' if direction == 'LONG' else 'buy'
        entry_px  = float(trade.get('entry_price') or 0)

        exit_price: float | None = None
        exit_time_str = now_ny().strftime('%H:%M:%S ET')

        # Try 1: match bracket parent by order_id → find filled exit leg
        parent = orders_by_id.get(order_id)
        if parent:
            # Prefer actual fill price over estimate
            fp = parent.get('filled_avg_price')
            if fp:
                try:
                    entry_px = float(fp)
                except Exception:
                    pass
            for leg in (parent.get('legs') or []):
                if (str(leg.get('status', '')).lower() == 'filled'
                        and str(leg.get('side', '')).lower() == exit_side):
                    raw = leg.get('filled_avg_price')
                    if raw:
                        exit_price = float(raw)
                    fa = leg.get('filled_at', '')
                    if fa:
                        exit_time_str = _parse_time(fa)
                    break

        # Try 2: match by symbol + exit_side from today's filled orders
        if exit_price is None:
            key = f'{symbol}:{exit_side}'
            for o in exit_fills.get(key, []):
                if str(o.get('id', '')) == order_id:
                    continue  # skip the entry order itself
                raw = o.get('filled_avg_price')
                if raw:
                    exit_price = float(raw)
                fa = o.get('filled_at', '')
                if fa:
                    exit_time_str = _parse_time(fa)
                break

        if exit_price is None:
            continue

        qty     = int(trade.get('size') or 1)
        raw_pnl = (
            (exit_price - entry_px) * qty if direction == 'LONG'
            else (entry_px - exit_price) * qty
        )
        realized_pnl = round(raw_pnl, 2)
        outcome      = 'WIN' if realized_pnl > 0 else ('LOSS' if realized_pnl < 0 else 'BREAKEVEN')

        trades[idx] = {
            **trade,
            'entry_price':  entry_px,
            'exit_price':   exit_price,
            'exit_time':    exit_time_str,
            'realized_pnl': realized_pnl,
            'pnl':          realized_pnl,
            'outcome':      outcome,
        }
        updated += 1

    if updated:
        save_journal(trades)
        today_str = now_ny().strftime('%Y-%m-%d')
        # Update daily P&L in state engine
        new_today_pnl = sum(
            float(t.get('realized_pnl') or 0)
            for t in trades
            if t.get('trade_date') == today_str
            and t.get('outcome') in ('WIN', 'LOSS')
            and t.get('realized_pnl') is not None
        )
        _state.set('daily_pnl', round(new_today_pnl, 2))
        # Propagate first-trade outcome into daily risk state for trade-2 logic
        risk = load_risk_state()
        if risk.get('daily_trades_date') == today_str and not risk.get('first_trade_outcome'):
            closed_today = sorted(
                [t for t in trades
                 if t.get('source') == 'DONNA_AUTO'
                 and t.get('trade_date') == today_str
                 and str(t.get('outcome', '')).upper() in ('WIN', 'LOSS', 'BREAKEVEN')],
                key=lambda t_: t_.get('time', ''),
            )
            if closed_today:
                first_oc = closed_today[0].get('outcome', '')
                risk['first_trade_outcome'] = first_oc
                if first_oc == 'LOSS':
                    risk['daily_loss_trade_hit'] = True
                elif first_oc == 'WIN':
                    risk['size_reduction_active'] = True
                save_risk_state(risk)
                try:
                    _state.set_many({
                        'first_trade_outcome':  first_oc,
                        'daily_loss_trade_hit': risk.get('daily_loss_trade_hit', False),
                        'size_reduction_active': risk.get('size_reduction_active', False),
                    })
                except Exception as _e:
                    print(f'[state_engine] check_position_outcomes write failed: {_e}')

    return updated


# ── Placeholder broker functions ───────────────────────────────

def execute_tradovate(signal_data: dict) -> dict:
    """Stub — plug in Tradovate API when ready, then set BROKER_MODE = 'TRADOVATE'."""
    return {'status': 'skipped', 'reason': 'Tradovate not connected yet'}


def execute_rithmic(signal_data: dict) -> dict:
    """Stub — plug in Rithmic API when ready, then set BROKER_MODE = 'RITHMIC'."""
    return {'status': 'skipped', 'reason': 'Rithmic not connected yet'}


# ── ALPACA_ETF execution ───────────────────────────────────────

def _execute_alpaca_etf(data: dict, parsed: dict, session: str, is_long: bool, routed_etf: str, apply_size_reduction: bool = False) -> dict:
    """
    Rule 5 + order submission for ALPACA_ETF mode.
    Trades routed_etf (SPY or QQQ) as determined by execute_signal().
    Sizing follows DONNA official rules (session-aware, hard caps applied).
    """
    etf = routed_etf

    api = _client()
    if not api:
        return {
            'status': 'error',
            'reason': 'Alpaca client unavailable — check ALPACA_API_KEY/ALPACA_SECRET_KEY',
        }

    # Load daily risk state for cumulative checks
    risk_state       = _get_daily_state()
    cumulative_risk  = float(risk_state.get('cumulative_risk_today', 0.0))

    sizing    = _get_etf_sizing(etf, session)
    qty       = sizing['qty']
    stop_dist = sizing['stop']
    tgt_dist  = sizing['target']

    # Trade 2 uses 50% size — decision made upstream in execute_signal()
    if apply_size_reduction:
        qty = max(1, qty // 2)

    # Block if cumulative risk would exceed $1,000 daily cap
    new_trade_risk = qty * stop_dist
    if cumulative_risk + new_trade_risk > 1000.0:
        return _log_skip(data, parsed,
            f'daily risk cap: ${cumulative_risk:.0f} used + ${new_trade_risk:.0f} new >= $1,000 limit',
            'DAILY_RISK_LIMIT')

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
        clock = api.get_clock()
        if not clock.is_open:
            return {'status': 'skipped', 'reason': 'market_closed', 'code': 'MARKET_CLOSED'}
    except Exception as _ce:
        print(f'[execution] clock check failed: {_ce}')

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

    # State engine — primary authority for these fields
    _state.increment_trade_count()
    _state.set('last_execution_time', utc_now_iso())
    _state.add_position({
        'symbol':    etf,
        'side':      'buy' if is_long else 'sell',
        'qty':       qty,
        'entry_ref': entry_ref,
        'order_id':  order_id,
        'session':   session,
        'timestamp': utc_now_iso(),
    })
    # Set thesis and cooldown after execution
    _state.set_cooldown(etf, minutes=30)
    _direction_str = 'LONG' if is_long else 'SHORT'
    _new_thesis = 'RISK_ON_BULL' if is_long else 'RISK_OFF_BEAR'
    _state.set_thesis(_new_thesis, _direction_str)
    # Backup write to donna_risk_state.json
    risk_after = load_risk_state()
    today_str  = now_ny().strftime('%Y-%m-%d')
    if risk_after.get('daily_trades_date') != today_str:
        risk_after['daily_trades_date']     = today_str
        risk_after['daily_trades_taken']    = 0
        risk_after['cumulative_risk_today'] = 0.0
    risk_after['daily_trades_taken']    = int(risk_after.get('daily_trades_taken', 0)) + 1
    risk_after['cumulative_risk_today'] = float(risk_after.get('cumulative_risk_today', 0.0)) + (qty * stop_dist)
    save_risk_state(risk_after)
    try:
        _state.set('cumulative_risk_today', float(risk_after.get('cumulative_risk_today', 0.0)))
    except Exception as _e:
        print(f'[state_engine] _execute_alpaca_etf cumulative_risk write failed: {_e}')
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

def close_qqq_positions() -> dict:
    """Close all open QQQ positions on Alpaca immediately."""
    api = _client()
    if not api:
        return {'status': 'error', 'reason': 'Alpaca not configured'}
    try:
        positions = api.get_all_positions()
        qqq_pos   = [p for p in positions if str(p.symbol).upper() == 'QQQ']
        if not qqq_pos:
            print('[close_qqq] No open QQQ positions found')
            return {'status': 'ok', 'closed': 0}
        api.close_position('QQQ')
        count   = len(qqq_pos)
        ts_et   = now_ny().strftime('%Y-%m-%d %H:%M:%S ET')
        print(f'[close_qqq] {ts_et} — closed QQQ ({count} lot(s))')
        send_telegram_message(
            f'DONNA EMERGENCY CLOSE\n'
            f'Closed {count} QQQ position(s) — Asia-session rule violation cleanup\n'
            f'Time: {ts_et}'
        )
        return {'status': 'ok', 'closed': count}
    except Exception as e:
        print(f'[close_qqq] Error: {e}')
        return {'status': 'error', 'reason': str(e)}


def execute_signal(signal_result: dict) -> dict:
    """
    Apply DONNA's 5 official risk rules, then route to the active broker.
    To switch brokers: change BROKER_MODE at the top of this file.

    Rule 0 — STATE GATE         can_execute() must be True (eod/macro/red_folder/permission locks).
    Rule 1 — RED FOLDER        ±30 min around any HIGH macro event → block.
    Rule 2 — DAILY TRADE LIMIT  max 2 trades per calendar day ET.
    Rule 3 — DAILY LOSS LIMIT   NY/London < -$1 000 | Asia < -$500 → block.
    Rule 4 — ASIA SESSION       confidence ≥ 90%, max 1 trade per Asia session.
    Rule 5 — POSITION SIZING    broker-specific (ALPACA_ETF: floor($500/stop)).
    """
    # ── Rule 0: State engine gate — must pass before any other logic
    if not _state.can_execute():
        lockouts = _state.get('risk_lockouts') or []
        reason = (
            ', '.join(l['reason'] if isinstance(l, dict) else l for l in lockouts)
            if lockouts else 'execution_lock or trade_permission disabled'
        )
        print(f'[execute_signal] BLOCKED — {reason}')
        return {'status': 'skipped', 'reason': f'Execution blocked: {reason}', 'code': 'STATE_GATE_BLOCKED'}

    # ── Determine routed instrument from signal
    _sig_data  = signal_result.get('data', {})
    instrument = _sig_data.get('instrument', '').upper()
    ticker     = _sig_data.get('ticker', '').upper()

    # Route: ES/MES → SPY, NQ/MNQ → QQQ
    if instrument in ('ES', 'MES') or ticker in ('ES', 'MES', 'ES1!', 'MES1!'):
        routed_etf = 'SPY'
    elif instrument in ('NQ', 'MNQ') or ticker in ('NQ', 'MNQ', 'NQ1!', 'MNQ1!'):
        routed_etf = 'QQQ'
    else:
        print(f'[execute_signal] BLOCKED — unknown instrument: {instrument}')
        return {'status': 'skipped', 'reason': f'Unknown instrument: {instrument}', 'code': 'UNKNOWN_INSTRUMENT'}

    print(f'[execute_signal] Signal routed: {instrument} → {routed_etf}')

    # Generate or use provided signal_id; check and store for dedup
    signal_id      = _sig_data.get('signal_id') or f"{ticker}_{now_ny().strftime('%Y%m%d_%H%M%S')}"
    last_signal_id = _state.get('last_signal_id')
    if last_signal_id and last_signal_id == signal_id:
        print(f'[execute_signal] BLOCKED — duplicate signal_id: {signal_id}')
        return {'status': 'skipped', 'reason': 'Duplicate signal', 'code': 'DUPLICATE_SIGNAL'}
    _state.set('last_signal_id', signal_id)

    # ── Snapshot time + session at moment of execution — ALWAYS server-time, never from webhook
    ts_et        = now_ny().strftime('%Y-%m-%d %H:%M:%S ET')
    session      = session_label()   # derived from server clock, ignores webhook payload

    # ── Read + (if needed) reset daily counter — persisted in donna_risk_state.json
    risk_snap     = _get_daily_state()
    trades_today  = _state.get('daily_trade_count', 0)
    first_outcome = _state.get('first_trade_outcome')
    loss_hit      = _state.get('daily_loss_trade_hit')

    print(f'[execute_signal] {ts_et} | session={session} | daily_trades_taken={trades_today}')

    parsed = signal_result.get('parsed', {})
    data   = signal_result.get('data', {})

    # ── VERDICT — non-TAKE signals not logged as skips
    if str(parsed.get('verdict', '')).upper() != 'TAKE':
        print(f'[execute_signal] {ts_et} | BLOCKED: verdict not TAKE')
        return {'status': 'skipped', 'reason': 'verdict not TAKE'}

    # ── State engine — sole authority for daily trade state
    if loss_hit:
        print('[execute_signal] BLOCKED — daily loss trade hit, trading stopped for day')
        return {'status': 'skipped', 'reason': 'First trade loss — no more trades today', 'code': 'DAILY_LOSS_TRADE_HIT'}

    if trades_today >= 2:
        print('[execute_signal] BLOCKED — daily limit reached (2 trades)')
        return {'status': 'skipped', 'reason': 'Daily trade limit reached', 'code': 'DAILY_LIMIT_REACHED'}

    if trades_today == 1 and first_outcome != 'WIN':
        print('[execute_signal] BLOCKED — trade 2 requires trade 1 WIN')
        return {'status': 'skipped', 'reason': 'Trade 2 blocked — first trade not WIN', 'code': 'TRADE2_REQUIRES_WIN'}

    # ── One instrument family at a time — no simultaneous SPY+QQQ
    open_syms = {p.get('symbol', '') for p in _state.get_open_positions()}
    if routed_etf == 'SPY' and 'QQQ' in open_syms:
        print('[execute_signal] BLOCKED — NQ/QQQ position already open')
        return {'status': 'skipped', 'reason': 'NQ_position_open', 'code': 'INSTRUMENT_CONFLICT'}
    if routed_etf == 'QQQ' and 'SPY' in open_syms:
        print('[execute_signal] BLOCKED — ES/SPY position already open')
        return {'status': 'skipped', 'reason': 'ES_position_open', 'code': 'INSTRUMENT_CONFLICT'}

    # ── ORCHESTRATION LAYER ──────────────────────────────────────
    from donna_state_engine import state as _state
    signal_type = str(data.get('signal', '')).upper()

    # 1. Cooldown check
    if _state.is_on_cooldown(routed_etf):
        return {'status': 'skipped', 'reason': f'{routed_etf}_on_cooldown', 'code': 'COOLDOWN_ACTIVE'}

    # 2. Thesis conflict check
    _thesis = _state.get_thesis()
    _active_thesis = _thesis.get('active_thesis', 'NEUTRAL')
    _thesis_dir = _thesis.get('thesis_direction')
    _signal_dir = 'LONG' if signal_type in ('BUY', 'LONG') else 'SHORT'

    if _active_thesis != 'NEUTRAL' and _thesis_dir and _thesis_dir != _signal_dir:
        # Opposite direction requires thesis to be older than 60 minutes
        _thesis_set_at = _thesis.get('thesis_set_at')
        if _thesis_set_at:
            try:
                from datetime import datetime, timezone
                _set_dt = datetime.fromisoformat(_thesis_set_at.replace('Z', '+00:00'))
                _mins_since = (datetime.now(timezone.utc) - _set_dt).total_seconds() / 60
                if _mins_since < 60:
                    return {'status': 'skipped', 'reason': 'thesis_conflict', 'code': 'THESIS_CONFLICT'}
            except Exception:
                pass

    # ── Size reduction for trade 2
    if trades_today == 1 and first_outcome == 'WIN':
        apply_size_reduction = True
        print('[execute_signal] Reduced size active after first win')
    else:
        apply_size_reduction = False

    # ── RULE 1: RED FOLDER
    rf = _red_folder_status()
    if rf['active']:
        print(f'[execute_signal] {ts_et} | BLOCKED RULE1: {rf["reason"]}')
        return _log_skip(data, parsed, rf['reason'], 'RED_FOLDER_WINDOW')

    # ── Account P&L (fetched after cheap guards pass)
    acct      = get_account()
    pnl_today = acct.get('pnl_today', 0.0) if acct.get('available') else 0.0

    # ── RULE 3: DAILY LOSS LIMIT
    loss_hit, loss_code = _check_daily_loss_limit(session, pnl_today)
    if loss_hit:
        limit = _LOSS_LIMIT_ASIA if session == 'ASIA' else _LOSS_LIMIT_NY_LON
        print(f'[execute_signal] {ts_et} | BLOCKED RULE3: '
              f'P&L=${pnl_today:,.2f} limit=${limit:,.0f} session={session}')
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
            print(f'[execute_signal] {ts_et} | BLOCKED RULE4a: '
                  f'confidence={confidence_val:.1f}% < {_ASIA_MIN_CONFIDENCE:.0f}% (Asia minimum)')
            return _log_skip(data, parsed,
                f'Asia session requires confidence ≥ {_ASIA_MIN_CONFIDENCE:.0f}% '
                f'— signal is {confidence_val:.1f}%',
                'ASIA_CONFIDENCE_TOO_LOW')

        if _get_asia_trade_taken():
            print(f'[execute_signal] {ts_et} | BLOCKED RULE4b: Asia trade already taken this session')
            return _log_skip(data, parsed,
                'Asia session trade already taken — max 1 trade per Asia session',
                'ASIA_TRADE_ALREADY_TAKEN')

    # ── RULE 5 + ORDER — all rules passed, route to active broker
    signal  = str(data.get('signal', '')).upper()
    is_long = signal in ('LONG', 'BUY')
    print(f'[execute_signal] {ts_et} | ALL RULES PASSED — '
          f'broker={BROKER_MODE} signal={signal} session={session} trades_today={trades_today}')

    if BROKER_MODE == 'ALPACA_ETF':
        return _execute_alpaca_etf(data, parsed, session, is_long, routed_etf, apply_size_reduction)
    if BROKER_MODE == 'TRADOVATE':
        return execute_tradovate(signal_result)
    if BROKER_MODE == 'RITHMIC':
        return execute_rithmic(signal_result)
    return {'status': 'error', 'reason': f'Unknown BROKER_MODE: {BROKER_MODE}'}


# ── One-time QQQ cleanup — closes Asia-session violation positions on module load ──
try:
    _qqq_result = close_qqq_positions()
    print(f'[donna_execution] QQQ cleanup on load: {_qqq_result}')
except Exception as _e:
    print(f'[donna_execution] QQQ cleanup error: {_e}')
