"""donna_execution.py — DONNA's autonomous paper trading engine via Alpaca."""
from __future__ import annotations

import os
from datetime import date

from donna_config import now_ny, utc_now_iso, safe_float, send_telegram_message
from donna_state import load_risk_state, load_alert_history, save_alert_history

# ── Alpaca setup ───────────────────────────────────────────────

ALPACA_API_KEY    = os.getenv('ALPACA_API_KEY', '').strip()
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY', '').strip()
ALPACA_BASE_URL   = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets').strip()

try:
    import alpaca_trade_api as tradeapi
    _ALPACA_LIB = True
except ImportError:
    tradeapi = None  # type: ignore
    _ALPACA_LIB = False

# ── Contract specs ─────────────────────────────────────────────
# MNQ: $2/point  |  MES: $5/point
# Default stop keeps risk-per-contract at $20 in both cases.

_POINT_VALUE   = {'MNQ': 2.0,  'MES': 5.0}
_DEFAULT_STOP  = {'MNQ': 10.0, 'MES': 4.0}   # points
_ACCOUNT_SIZE  = 100_000.0
_RISK_FRACTION = 0.01      # 1% = $1 000 max risk
_MAX_CONTRACTS = 3


# ── Internal helpers ───────────────────────────────────────────

def _client():
    if not _ALPACA_LIB or not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None
    try:
        return tradeapi.REST(
            ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version='v2'
        )
    except Exception:
        return None


def _in_ny_cash() -> bool:
    ny = now_ny()
    if ny.weekday() >= 5:
        return False
    m = ny.hour * 60 + ny.minute
    return 9 * 60 + 30 <= m < 16 * 60


def _map_symbol(data: dict) -> str | None:
    """Resolve signal instrument/ticker to MNQ or MES."""
    instrument = str(data.get('instrument', '')).upper()
    ticker     = str(data.get('ticker', '')).upper()
    if 'NQ' in instrument or 'NQ' in ticker or 'MNQ' in ticker:
        return 'MNQ'
    if 'ES' in instrument or 'ES' in ticker or 'MES' in ticker:
        return 'MES'
    return None


def _calc_qty(symbol: str) -> int:
    """Max contracts within 1% account risk, capped at _MAX_CONTRACTS."""
    stop_pts = _DEFAULT_STOP.get(symbol, 10.0)
    pv       = _POINT_VALUE.get(symbol, 2.0)
    risk     = _ACCOUNT_SIZE * _RISK_FRACTION         # $1 000
    qty      = int(risk / (stop_pts * pv))            # $1000 / $20 = 50 → capped
    return max(1, min(qty, _MAX_CONTRACTS))


# ── Public account / position helpers ─────────────────────────

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
            'status':       a.status,
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
                'side':           p.side,
                'avg_entry':      float(p.avg_entry_price),
                'market_value':   float(p.market_value),
                'unrealized_pnl': float(p.unrealized_pl),
            }
            for p in api.list_positions()
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
        api.close_all_positions()
        return {'status': 'ok'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def get_today_trade_count() -> int:
    """Count entry orders submitted today (excludes bracket legs)."""
    api = _client()
    if not api:
        return 0
    try:
        today  = date.today().isoformat()
        orders = api.list_orders(
            status='all',
            after=f'{today}T00:00:00Z',
            limit=500,
        )
        return sum(
            1 for o in orders
            if getattr(o, 'order_class', '') in ('', 'simple', 'bracket')
            and getattr(o, 'legs', None) is None  # only the parent
        )
    except Exception:
        return 0


# ── Core execution ─────────────────────────────────────────────

def execute_signal(signal_result: dict) -> dict:
    """
    Gate-check a process_signal() result and, if all conditions pass,
    submit a bracket market order on the Alpaca paper account.
    """
    parsed = signal_result.get('parsed', {})
    data   = signal_result.get('data', {})

    # ── verdict gate ──────────────────────────────────────────
    if str(parsed.get('verdict', '')).upper() != 'TAKE':
        return {'status': 'skipped', 'reason': 'verdict not TAKE'}

    # ── session gate ──────────────────────────────────────────
    if not _in_ny_cash():
        return {'status': 'skipped', 'reason': 'outside NY cash session (09:30–16:00 ET)'}

    # ── macro / event gate ────────────────────────────────────
    risk        = load_risk_state()
    macro       = str(risk.get('macro_risk', 'medium')).lower()
    event_phase = str(risk.get('event_phase', '')).upper()
    if macro == 'high' and event_phase in ('LIVE', 'IMMINENT'):
        return {'status': 'skipped', 'reason': 'macro_risk HIGH with event LIVE/IMMINENT'}

    # ── stop-trading flag gate ────────────────────────────────
    try:
        from donna_risk_engine import load_re_state
        if load_re_state().get('stop_trading'):
            return {'status': 'skipped', 'reason': 'STOP_TRADING flag is active'}
    except Exception:
        pass

    # ── symbol resolution ─────────────────────────────────────
    symbol = _map_symbol(data)
    if not symbol:
        return {'status': 'skipped', 'reason': 'cannot resolve instrument to MNQ or MES'}

    # ── Alpaca client ─────────────────────────────────────────
    api = _client()
    if not api:
        return {'status': 'error', 'reason': 'Alpaca client unavailable — check ALPACA_API_KEY/ALPACA_SECRET_KEY'}

    # ── no-double-up gate ─────────────────────────────────────
    if any(p['symbol'] == symbol for p in get_positions()):
        return {'status': 'skipped', 'reason': f'already holding an open {symbol} position'}

    # ── sizing ────────────────────────────────────────────────
    signal    = str(data.get('signal', '')).upper()
    is_long   = signal in ('LONG', 'BUY')
    side      = 'buy' if is_long else 'sell'
    qty       = _calc_qty(symbol)

    stop_pts   = _DEFAULT_STOP[symbol]
    target_pts = stop_pts * 2                          # 2:1 R:R
    entry_ref  = safe_float(data.get('price', 0))

    if is_long:
        stop_px   = round(entry_ref - stop_pts,   2)
        target_px = round(entry_ref + target_pts, 2)
    else:
        stop_px   = round(entry_ref + stop_pts,   2)
        target_px = round(entry_ref - target_pts, 2)

    # ── bracket order ─────────────────────────────────────────
    try:
        order = api.submit_order(
            symbol        = symbol,
            qty           = qty,
            side          = side,
            type          = 'market',
            time_in_force = 'day',
            order_class   = 'bracket',
            stop_loss     = {'stop_price': stop_px},
            take_profit   = {'limit_price': target_px},
        )
        order_id = order.id
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}

    # ── log to alert history ──────────────────────────────────
    record = {
        'type':         'execution',
        'ticker':       symbol,
        'signal':       side.upper(),
        'session':      data.get('session', ''),
        'timeframe':    data.get('timeframe', ''),
        'price':        str(entry_ref),
        'verdict':      'TAKE',
        'confidence':   parsed.get('confidence', ''),
        'summary':      (f'EXECUTED {side.upper()} {qty}x {symbol} @ {entry_ref}. '
                         f'Stop: {stop_px}, Target: {target_px}'),
        'instrument':   symbol,
        'tier':         data.get('tier', ''),
        'setup_type':   data.get('setup_type', ''),
        'signal_reason': data.get('signal_reason', ''),
        'entry_price':  entry_ref,
        'contracts':    qty,
        'stop_price':   stop_px,
        'target_price': target_px,
        'order_id':     order_id,
        'timestamp':    utc_now_iso(),
    }
    alerts = load_alert_history()
    alerts.insert(0, record)
    save_alert_history(alerts)

    send_telegram_message(
        f'DONNA EXECUTED\n'
        f'{side.upper()} {qty}x {symbol} @ {entry_ref}\n'
        f'Stop: {stop_px} | Target: {target_px}\n'
        f'Setup: {data.get("setup_type", "")} | Tier: {data.get("tier", "")}\n'
        f'Order ID: {order_id}'
    )

    return {
        'status':       'executed',
        'symbol':       symbol,
        'side':         side,
        'contracts':    qty,
        'entry_ref':    entry_ref,
        'stop_price':   stop_px,
        'target_price': target_px,
        'order_id':     order_id,
    }
