"""donna_execution.py — DONNA autonomous paper trading via Alpaca futures API."""
from __future__ import annotations

import calendar
import os
from datetime import date, timedelta

from donna_config import now_ny, utc_now_iso, safe_float, send_telegram_message
from donna_state import load_risk_state, load_alert_history, save_alert_history

# ── Alpaca setup ───────────────────────────────────────────────

ALPACA_API_KEY    = os.getenv('ALPACA_API_KEY', '').strip()
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY', '').strip()
_PAPER = 'paper' in os.getenv('ALPACA_BASE_URL', 'paper-api.alpaca.markets').lower()

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest, TakeProfitRequest, StopLossRequest, GetOrdersRequest,
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, QueryOrderStatus
    _ALPACA_LIB = True
except ImportError:
    TradingClient = None  # type: ignore
    _ALPACA_LIB = False

# ── Contract specs ─────────────────────────────────────────────
# MES: $5/point, 4-pt stop → $20 risk/contract
# MNQ: $2/point, 10-pt stop → $20 risk/contract

_POINT_VALUE   = {'MES': 5.0,  'MNQ': 2.0}
_DEFAULT_STOP  = {'MES': 4.0,  'MNQ': 10.0}
_ACCOUNT_SIZE  = 100_000.0
_RISK_FRACTION = 0.01       # 1% = $1 000 max risk
_MAX_CONTRACTS = 3

# CME quarterly expiry months (Globex codes)
_QUARTERLY = [(3, 'H'), (6, 'M'), (9, 'U'), (12, 'Z')]


# ── Front-month contract resolution ───────────────────────────

def _third_friday(year: int, month: int) -> date:
    weeks   = calendar.monthcalendar(year, month)
    fridays = [w[4] for w in weeks if w[4] != 0]
    return date(year, month, fridays[2])


def _front_month_symbol(base: str) -> str:
    """Return active quarterly symbol, e.g. 'MESM26'.

    Rolls 7 days before the third Friday of the expiry month.
    """
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


# ── Internal helpers ───────────────────────────────────────────

def _client() -> 'TradingClient | None':
    if not _ALPACA_LIB or not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None
    try:
        return TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=_PAPER)
    except Exception:
        return None


def _in_ny_cash() -> bool:
    ny = now_ny()
    if ny.weekday() >= 5:
        return False
    m = ny.hour * 60 + ny.minute
    return 9 * 60 + 30 <= m < 16 * 60


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
    stop_pts = _DEFAULT_STOP.get(base, 4.0)
    pv       = _POINT_VALUE.get(base, 5.0)
    qty      = int((_ACCOUNT_SIZE * _RISK_FRACTION) / (stop_pts * pv))
    return max(1, min(qty, _MAX_CONTRACTS))


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
    api = _client()
    if not api:
        return 0
    try:
        req    = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            after=f'{date.today().isoformat()}T00:00:00Z',
            limit=500,
        )
        orders = api.get_orders(filter=req)
        # Count only bracket parents (entry orders), not the stop/target legs
        return sum(
            1 for o in orders
            if str(getattr(o, 'order_class', '')) in ('bracket', '')
            and getattr(o, 'legs', None) is not None  # bracket parents always have legs
        )
    except Exception:
        return 0


# ── Core execution ─────────────────────────────────────────────

def execute_signal(signal_result: dict) -> dict:
    """Gate-check and execute a TAKE signal as a bracket order on Alpaca paper."""
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
    base = _map_base(data)
    if not base:
        return {'status': 'skipped', 'reason': 'cannot resolve instrument to MNQ or MES'}

    symbol = _front_month_symbol(base)   # e.g. 'MESM26'

    # ── Alpaca client ─────────────────────────────────────────
    api = _client()
    if not api:
        return {'status': 'error', 'reason': 'Alpaca client unavailable — check ALPACA_API_KEY/ALPACA_SECRET_KEY'}

    # ── no-double-up gate ─────────────────────────────────────
    positions = get_positions()
    if any(p['symbol'].startswith(base) for p in positions):
        return {'status': 'skipped', 'reason': f'already holding open {base} position'}

    # ── sizing ────────────────────────────────────────────────
    signal   = str(data.get('signal', '')).upper()
    is_long  = signal in ('LONG', 'BUY')
    side     = OrderSide.BUY if is_long else OrderSide.SELL
    qty      = _calc_qty(base)

    stop_pts   = _DEFAULT_STOP[base]
    target_pts = stop_pts * 2            # 2:1 R:R
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
            MarketOrderRequest(
                symbol        = symbol,
                qty           = qty,
                side          = side,
                time_in_force = TimeInForce.DAY,
                order_class   = OrderClass.BRACKET,
                take_profit   = TakeProfitRequest(limit_price=target_px),
                stop_loss     = StopLossRequest(stop_price=stop_px),
            )
        )
        order_id = str(order.id)
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}

    # ── log to alert history ──────────────────────────────────
    direction = 'BUY' if is_long else 'SELL'
    record = {
        'type':          'execution',
        'ticker':        symbol,
        'signal':        direction,
        'session':       data.get('session', ''),
        'timeframe':     data.get('timeframe', ''),
        'price':         str(entry_ref),
        'verdict':       'TAKE',
        'confidence':    parsed.get('confidence', ''),
        'summary':       (f'EXECUTED {direction} {qty}x {symbol} @ {entry_ref}. '
                          f'Stop: {stop_px}, Target: {target_px}'),
        'instrument':    symbol,
        'tier':          data.get('tier', ''),
        'setup_type':    data.get('setup_type', ''),
        'signal_reason': data.get('signal_reason', ''),
        'entry_price':   entry_ref,
        'contracts':     qty,
        'stop_price':    stop_px,
        'target_price':  target_px,
        'order_id':      order_id,
        'timestamp':     utc_now_iso(),
    }
    alerts = load_alert_history()
    alerts.insert(0, record)
    save_alert_history(alerts)

    send_telegram_message(
        f'DONNA EXECUTED\n'
        f'{direction} {qty}x {symbol} @ {entry_ref}\n'
        f'Stop: {stop_px} | Target: {target_px}\n'
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
        'target_price': target_px,
        'order_id':     order_id,
    }
