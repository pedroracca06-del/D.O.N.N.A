"""execution_reconcile.py — Execution Bot v2 Phase 3: broker state reader + reconciliation.

Read-only inspection of Alpaca broker state and NOVA journal for pre-trade
conflict detection and state reconciliation.

SAFETY CONTRACT — this module MUST NEVER:
  - Submit orders
  - Cancel orders
  - Modify positions
  - Call any Alpaca write endpoint

Public API:
    get_broker_positions_safe() -> list          — all open Alpaca positions
    get_broker_orders_safe()    -> list          — all open Alpaca orders
    get_open_journal_trades_safe() -> list       — OPEN journal entries
    normalize_position_record(pos) -> dict       — Alpaca Position → standard dict
    normalize_order_record(order) -> dict        — Alpaca Order → standard dict
    check_open_position_conflict(...) -> dict    — conflict gate for new signal
    detect_protective_orders(...) -> dict        — stop/target detection
    reconcile_execution_state(...) -> dict       — broker/journal comparison scaffold
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

_lock = threading.Lock()

# ── ETF routing (same as prop_risk.py) ───────────────────────────────────────

_ETF_ROUTE: dict[str, str] = {
    'MNQ': 'QQQ', 'NQ': 'QQQ',
    'MES': 'SPY', 'ES':  'SPY',
}


def _normalize_symbol(symbol: str) -> str:
    return (
        symbol.upper()
        .replace('CME_MINI:', '').replace('CME:', '')
        .replace('1!', '').replace('!', '').strip()
    )


def _symbol_to_etf(symbol: str) -> str:
    return _ETF_ROUTE.get(_normalize_symbol(symbol), _normalize_symbol(symbol))


# ── Alpaca client (read-only) ─────────────────────────────────────────────────

def _get_alpaca_client():
    """
    Return (client, error_str). Never raises.
    Returns (None, reason) when credentials are missing or library not installed.
    """
    api_key    = os.getenv('ALPACA_API_KEY', '').strip()
    secret_key = os.getenv('ALPACA_SECRET_KEY', '').strip()
    if not api_key or not secret_key:
        return None, 'ALPACA_API_KEY or ALPACA_SECRET_KEY not set'
    try:
        from alpaca.trading.client import TradingClient
        paper = 'paper' in os.getenv('ALPACA_BASE_URL', 'paper').lower()
        return TradingClient(api_key, secret_key, paper=paper), None
    except ImportError:
        return None, 'alpaca library not installed'
    except Exception as e:
        return None, f'client init error: {e}'


# ── Record normalizers ────────────────────────────────────────────────────────

def _to_dict(obj) -> dict:
    """Convert an Alpaca model object to a plain dict, safely."""
    if isinstance(obj, dict):
        return obj
    for method in ('model_dump', 'dict'):
        try:
            return getattr(obj, method)()
        except AttributeError:
            pass
    try:
        return vars(obj)
    except TypeError:
        return {}


def _str_val(v) -> str:
    """Enum or string → lowercase string."""
    if v is None:
        return ''
    return str(getattr(v, 'value', v)).lower()


def _flt(raw: dict, key: str, default=None):
    v = raw.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def normalize_position_record(pos) -> dict:
    """
    Alpaca Position object or dict → standard dict.
    All numeric fields are float; side is normalized to 'long'/'short'.
    """
    raw  = _to_dict(pos)
    side = _str_val(raw.get('side'))
    if side in ('buy',):
        side = 'long'
    elif side in ('sell',):
        side = 'short'
    return {
        'symbol':          str(raw.get('symbol', '')).upper(),
        'side':            side,
        'qty':             _flt(raw, 'qty', 0.0),
        'avg_entry_price': _flt(raw, 'avg_entry_price'),
        'market_value':    _flt(raw, 'market_value'),
        'unrealized_pl':   _flt(raw, 'unrealized_pl'),
        'raw':             raw,
    }


def normalize_order_record(order) -> dict:
    """
    Alpaca Order object or dict → standard dict.
    `legs` are recursively normalized.
    """
    raw = _to_dict(order)
    legs = []
    for leg in (raw.get('legs') or []):
        try:
            legs.append(normalize_order_record(leg))
        except Exception:
            pass
    return {
        'id':          str(raw.get('id', '')),
        'symbol':      str(raw.get('symbol', '')).upper(),
        'side':        _str_val(raw.get('side')),
        'type':        _str_val(raw.get('type')),
        'qty':         _flt(raw, 'qty', 0.0),
        'status':      _str_val(raw.get('status')),
        'limit_price': _flt(raw, 'limit_price'),
        'stop_price':  _flt(raw, 'stop_price'),
        'order_class': _str_val(raw.get('order_class')),
        'legs':        legs,
        'raw':         raw,
    }


# ── Broker readers (read-only, never crash) ───────────────────────────────────

def get_broker_positions_safe() -> list:
    """
    Return normalized list of all current Alpaca positions.
    Returns [] with logged warning on any failure. Never raises.
    """
    client, err = _get_alpaca_client()
    if client is None:
        return []
    try:
        positions = client.get_all_positions()
        return [normalize_position_record(p) for p in (positions or [])]
    except Exception:
        return []


def get_broker_orders_safe() -> list:
    """
    Return normalized list of all open Alpaca orders.
    Returns [] on any failure. Never raises.
    """
    client, err = _get_alpaca_client()
    if client is None:
        return []
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
        return [normalize_order_record(o) for o in (orders or [])]
    except Exception:
        return []


def get_open_journal_trades_safe() -> list:
    """
    Return all journal entries with outcome='OPEN'.
    Returns [] on any failure. Never raises.
    """
    try:
        from core.state import load_journal
        trades = load_journal()
        return [
            t for t in (trades or [])
            if str(t.get('outcome', '')).upper() == 'OPEN'
        ]
    except Exception:
        return []


# ── Open position conflict gate ───────────────────────────────────────────────

def check_open_position_conflict(
    symbol: str,
    direction: str,
    routed_etf: str,
    broker_positions: list,
) -> dict:
    """
    Check if there is already an open broker position for the routed ETF.

    Any existing position is a conflict — regardless of direction — since
    prop firms treat adding to or hedging an open position as a second trade
    against the same instrument exposure.

    Returns a gate result dict compatible with Phase 2 gate structure.
    """
    etf_upper = routed_etf.upper()
    matching  = [
        p for p in broker_positions
        if str(p.get('symbol', '')).upper() == etf_upper
    ]
    if matching:
        existing = matching[0]
        return {
            'checked':           True,
            'conflict':          True,
            'routed_etf':        routed_etf,
            'existing_side':     existing.get('side'),
            'existing_qty':      existing.get('qty'),
            'existing_position': existing,
            'rejection_code':    'REJECTED_OPEN_POSITION',
            'reason': (
                f'Existing {existing.get("side")} position of '
                f'{existing.get("qty")} {etf_upper} blocks new {direction} {symbol} signal'
            ),
        }
    return {
        'checked':           True,
        'conflict':          False,
        'routed_etf':        routed_etf,
        'existing_side':     None,
        'existing_qty':      None,
        'existing_position': None,
        'rejection_code':    None,
        'reason':            f'No existing position for {etf_upper} — clear to proceed',
    }


# ── Protective order detection ────────────────────────────────────────────────

def detect_protective_orders(
    routed_etf: str,
    broker_positions: list,
    broker_orders: list,
) -> dict:
    """
    Check whether an existing position for routed_etf has protective orders
    (stop-loss and/or take-profit).

    For a LONG position: protective orders are 'sell' side.
    For a SHORT position: protective orders are 'buy' side.

    Bracket / OCO orders are treated as fully protected (both stop + target).

    Returns a detection result dict. Does not modify any broker state.
    """
    etf_upper     = routed_etf.upper()
    etf_positions = [
        p for p in broker_positions
        if str(p.get('symbol', '')).upper() == etf_upper
    ]
    if not etf_positions:
        return {
            'position_found':    False,
            'position_side':     None,
            'position_qty':      None,
            'stop_found':        False,
            'target_found':      False,
            'bracket_detected':  False,
            'unprotected':       False,
            'reason':            f'No open position for {etf_upper}',
        }

    pos      = etf_positions[0]
    pos_side = (pos.get('side') or '').lower()
    # protective sell side for long, buy side for short
    prot_side = 'sell' if pos_side == 'long' else 'buy'

    etf_orders   = [
        o for o in broker_orders
        if str(o.get('symbol', '')).upper() == etf_upper
    ]

    stop_found       = False
    target_found     = False
    bracket_detected = False

    for order in etf_orders:
        order_side  = (order.get('side') or '').lower()
        order_type  = (order.get('type') or '').lower()
        order_class = (order.get('order_class') or '').lower()

        if order_class in ('bracket', 'oco'):
            bracket_detected = True
            stop_found       = True
            target_found     = True
            break

        if order_side != prot_side:
            continue

        if order_type in ('stop', 'stop_limit', 'trailing_stop'):
            stop_found = True
        if order_type == 'limit':
            target_found = True

        # Also check legs of any bracket/oco that appears as a main order
        for leg in (order.get('legs') or []):
            leg_side  = (leg.get('side') or '').lower()
            leg_type  = (leg.get('type') or '').lower()
            if leg_side == prot_side:
                if leg_type in ('stop', 'stop_limit', 'trailing_stop'):
                    stop_found = True
                if leg_type == 'limit':
                    target_found = True

    unprotected = not stop_found

    return {
        'position_found':   True,
        'position_side':    pos_side,
        'position_qty':     pos.get('qty'),
        'stop_found':       stop_found,
        'target_found':     target_found,
        'bracket_detected': bracket_detected,
        'unprotected':      unprotected,
        'reason': (
            'UNPROTECTED — no stop order detected'
            if unprotected else
            f'Protected: stop={stop_found} target={target_found} bracket={bracket_detected}'
        ),
    }


# ── Reconciliation scaffold ───────────────────────────────────────────────────

_RECON_SYNCED                 = 'SYNCED'
_RECON_BROKER_POSITION_MISSING = 'BROKER_POSITION_MISSING'
_RECON_JOURNAL_MISSING        = 'JOURNAL_MISSING'
_RECON_SIZE_MISMATCH          = 'SIZE_MISMATCH'
_RECON_DIRECTION_MISMATCH     = 'DIRECTION_MISMATCH'
_RECON_UNPROTECTED            = 'UNPROTECTED_POSITION'
_RECON_UNKNOWN                = 'UNKNOWN_BROKER_STATE'
_RECON_INSUFFICIENT           = 'INSUFFICIENT_DATA'


def reconcile_execution_state(
    execution_request: dict,
    broker_positions: list,
    broker_orders: list,
    journal_trades: list,
) -> dict:
    """
    Pre-trade reconciliation scaffold: compare broker state with journal records
    for the routed instrument and report any discrepancy.

    This is observation-only for Phase 3. Results are written to trace_v2
    and logged as warnings/errors — they do NOT affect final_status unless
    the caller explicitly uses reconciliation_status for routing.

    Statuses:
      INSUFFICIENT_DATA        — no broker positions AND no open journal trades
      SYNCED                   — broker + journal agree; position is protected
      BROKER_POSITION_MISSING  — journal shows open trade but broker has no position
      JOURNAL_MISSING          — broker has position but no journal entry found
      SIZE_MISMATCH            — qty disagrees between broker and journal
      DIRECTION_MISMATCH       — direction/side disagrees
      UNPROTECTED_POSITION     — position exists but no stop order detected
      UNKNOWN_BROKER_STATE     — error reading broker (passed-in positions may be stale/empty)
    """
    symbol     = str(execution_request.get('symbol', '')).upper()
    routed_etf = _symbol_to_etf(symbol)
    direction  = str(execution_request.get('direction', '')).upper()
    etf_upper  = routed_etf.upper()

    warnings: list[str] = []
    errors:   list[str] = []

    # Find broker position for the routed instrument
    broker_pos = next(
        (p for p in broker_positions if str(p.get('symbol', '')).upper() == etf_upper),
        None,
    )

    # Find open journal trade for the routed instrument
    journal_trade = next(
        (t for t in journal_trades
         if str(t.get('ticker', '')).upper() == etf_upper),
        None,
    )

    base: dict = {
        'routed_etf':             routed_etf,
        'broker_position_found':  broker_pos is not None,
        'journal_trade_found':    journal_trade is not None,
        'direction_match':        None,
        'size_match':             None,
        'protective_stop_found':  False,
        'protective_target_found': False,
        'warnings':               warnings,
        'errors':                 errors,
    }

    # ── Both empty: no data to reconcile ──────────────────────────────────────
    if broker_pos is None and journal_trade is None:
        return {
            **base,
            'reconciliation_status': _RECON_INSUFFICIENT,
            'reason': f'No broker position and no open journal trade for {etf_upper} — pre-trade clean state',
        }

    # ── Journal has open trade but broker has no position ─────────────────────
    if broker_pos is None and journal_trade is not None:
        errors.append(
            f'Journal shows open {journal_trade.get("direction")} '
            f'{etf_upper} trade but broker has no position — possible orphaned journal entry'
        )
        return {
            **base,
            'reconciliation_status': _RECON_BROKER_POSITION_MISSING,
            'reason': f'BROKER_POSITION_MISSING: journal has open {etf_upper} trade but Alpaca shows nothing',
        }

    # ── Broker has position but journal does not record it ────────────────────
    protective = detect_protective_orders(routed_etf, broker_positions, broker_orders)
    base['protective_stop_found']   = protective.get('stop_found', False)
    base['protective_target_found'] = protective.get('target_found', False)

    if broker_pos is not None and journal_trade is None:
        warnings.append(
            f'Broker has {broker_pos.get("side")} {broker_pos.get("qty")} '
            f'{etf_upper} position but no matching open journal entry'
        )
        if protective.get('unprotected'):
            return {
                **base,
                'reconciliation_status': _RECON_UNPROTECTED,
                'reason': f'UNPROTECTED_POSITION: {etf_upper} position has no stop + no journal record',
            }
        return {
            **base,
            'reconciliation_status': _RECON_JOURNAL_MISSING,
            'reason': f'JOURNAL_MISSING: broker shows {broker_pos.get("side")} {etf_upper} but journal has no open entry',
        }

    # ── Both broker and journal present — compare ──────────────────────────────
    # Direction comparison
    broker_side_normalized = 'LONG' if (broker_pos.get('side') or '').lower() == 'long' else 'SHORT'
    journal_direction      = str(journal_trade.get('direction', '')).upper()
    direction_match        = (broker_side_normalized == journal_direction)
    base['direction_match'] = direction_match

    # Size comparison (within 5% tolerance for partial fills)
    broker_qty  = float(broker_pos.get('qty') or 0)
    journal_qty = float(journal_trade.get('qty') or 0)
    if broker_qty > 0 and journal_qty > 0:
        diff_pct = abs(broker_qty - journal_qty) / max(broker_qty, journal_qty)
        size_match = diff_pct <= 0.05   # within 5%
    else:
        size_match = broker_qty == journal_qty
    base['size_match'] = size_match

    # Determine status (priority: direction > size > unprotected > synced)
    if not direction_match:
        errors.append(
            f'Direction mismatch: broker={broker_side_normalized} '
            f'journal={journal_direction} for {etf_upper}'
        )
        return {
            **base,
            'reconciliation_status': _RECON_DIRECTION_MISMATCH,
            'reason': f'DIRECTION_MISMATCH: broker={broker_side_normalized} vs journal={journal_direction}',
        }

    if not size_match:
        warnings.append(
            f'Size mismatch: broker={broker_qty} journal={journal_qty} for {etf_upper}'
        )
        return {
            **base,
            'reconciliation_status': _RECON_SIZE_MISMATCH,
            'reason': f'SIZE_MISMATCH: broker={broker_qty} vs journal={journal_qty} (>{5}% diff)',
        }

    if protective.get('unprotected'):
        warnings.append(f'Position {etf_upper} has no detected stop order — UNPROTECTED')
        return {
            **base,
            'reconciliation_status': _RECON_UNPROTECTED,
            'reason': f'UNPROTECTED_POSITION: {etf_upper} {broker_side_normalized} position has no stop order',
        }

    return {
        **base,
        'reconciliation_status': _RECON_SYNCED,
        'reason': (
            f'SYNCED: broker={broker_side_normalized} {broker_qty} {etf_upper} '
            f'matches journal; protected={not protective["unprotected"]}'
        ),
    }
