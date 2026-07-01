"""prop_risk.py — Execution Bot v2 Phase 2: prop-firm risk config and gate evaluation.

Config file: nova_prop_risk_config.json in DATA_DIR.
Default config: all zeros / empty lists → all gates skip (safe for initial deployment).

Gates are pure evaluation functions — they never read from external state.
Callers (execution_request.py) read runtime context and pass it in as arguments.

Public API:
    load_prop_config() -> dict                  — load file, fall back to defaults
    save_prop_config(config) -> None            — write to file
    get_default_config() -> dict                — safe zero-config
    run_prop_gates(symbol, session, ...) -> list — evaluate all configured gates
    get_runtime_context() -> dict               — read trade count / P&L / positions
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_lock = threading.Lock()

# ── ETF routing (mirrors execution.py logic) ──────────────────────────────────

_ETF_ROUTE: dict[str, str] = {
    'MNQ': 'QQQ', 'NQ': 'QQQ',
    'MES': 'SPY', 'ES': 'SPY',
}


def _normalize_symbol(symbol: str) -> str:
    return (
        symbol.upper()
        .replace('CME_MINI:', '').replace('CME:', '')
        .replace('1!', '').replace('!', '').strip()
    )


def _symbol_to_etf(symbol: str) -> str:
    return _ETF_ROUTE.get(_normalize_symbol(symbol), _normalize_symbol(symbol))


# ── Config file path ──────────────────────────────────────────────────────────

def _prop_config_file() -> Path:
    try:
        from core.config import DATA_DIR
        return DATA_DIR / 'nova_prop_risk_config.json'
    except Exception:
        return Path('data') / 'nova_prop_risk_config.json'


# ── Default config ────────────────────────────────────────────────────────────

def get_default_config() -> dict:
    """
    Safe zero-config: every gate value is 0 / empty list / False.
    Gates with zero values are SKIPPED — they do not block.
    This is the correct default for initial prop deployment.
    """
    return {
        'prop_firm_name':           'NONE',
        'account_size':             0.0,
        'starting_balance':         0.0,
        'current_balance':          0.0,
        'max_daily_loss':           0.0,    # 0 = gate disabled
        'max_total_loss':           0.0,    # 0 = gate disabled
        'trailing_drawdown_enabled': False,
        'trailing_drawdown_amount': 0.0,
        'trailing_drawdown_type':   'FIXED_FROM_START',
        'trailing_hwm':             0.0,
        'max_contracts_total':      0,      # 0 = gate disabled
        'max_contracts_per_symbol': 0,      # 0 = gate disabled
        'max_trades_per_day':       0,      # 0 = gate disabled
        'allowed_symbols':          [],     # [] = all symbols allowed
        'allowed_sessions':         [],     # [] = all sessions allowed
        'flatten_before_close':     True,
        'news_trading_allowed':     False,
        'consistency_rule_enabled': False,
        'daily_profit_cap_if_any':  None,
    }


# ── Config I/O ────────────────────────────────────────────────────────────────

def load_prop_config() -> dict:
    """
    Load prop risk config from file.

    Falls back to get_default_config() if file is missing or unreadable.
    Sets '_config_missing': True when file was absent so callers can log a warning.
    Never raises.
    """
    p = _prop_config_file()
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                defaults = get_default_config()
                merged = {**defaults, **data}   # config file overrides defaults for known keys
                merged['_config_missing'] = False
                return merged
    except Exception as e:
        defaults = get_default_config()
        defaults['_config_missing'] = True
        defaults['_config_error'] = str(e)
        return defaults

    # File doesn't exist — write defaults so the user can edit it
    defaults = get_default_config()
    defaults['_config_missing'] = True
    try:
        with _lock:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(get_default_config(), indent=2), encoding='utf-8')
    except Exception:
        pass
    return defaults


def save_prop_config(config: dict) -> None:
    """Write prop risk config to file. Strips internal _ fields before saving."""
    clean = {k: v for k, v in config.items() if not k.startswith('_')}
    with _lock:
        _prop_config_file().write_text(json.dumps(clean, indent=2), encoding='utf-8')


# ── Runtime context ───────────────────────────────────────────────────────────

def get_runtime_context() -> dict:
    """
    Read current execution runtime state for prop gate evaluation.
    Returns safe defaults on any error — gates skip rather than block on unavailable data.
    """
    ctx: dict = {
        'trade_count':    0,
        'daily_pnl':      0.0,
        'open_positions': [],
        'context_error':  None,
    }
    try:
        from core.state_engine import state as _st
        ctx['trade_count']    = int(_st.get('daily_trade_count', 0))
        ctx['daily_pnl']      = float(_st.get('daily_pnl', 0.0) or 0.0)
        ctx['open_positions'] = _st.get_open_positions() or []
    except Exception as e:
        ctx['context_error'] = str(e)
    return ctx


# ── Gate evaluation ───────────────────────────────────────────────────────────

_GATE_PASS = 'PASS'
_GATE_FAIL = 'FAIL'
_GATE_SKIP = 'SKIP'


def _gate(name: str, result: str, reason: str, rejection_code: str = '') -> dict:
    return {
        'gate':           name,
        'result':         result,
        'reason':         reason,
        'rejection_code': rejection_code if result == _GATE_FAIL else None,
    }


def run_prop_gates(
    symbol: str,
    session: str,
    trade_count: int = 0,
    daily_pnl: float = 0.0,
    open_positions: Optional[list] = None,
    config: Optional[dict] = None,
) -> list[dict]:
    """
    Evaluate all configured prop risk gates. Returns list of gate result dicts.

    Never raises. Never reads from external state — all context passed as arguments.
    Gates with zero/empty config values are SKIPPED (not FAIL).

    Gate result: {'gate', 'result' (PASS|FAIL|SKIP), 'reason', 'rejection_code'}
    """
    if config is None:
        config = get_default_config()
    if open_positions is None:
        open_positions = []

    results: list[dict] = []
    sym_norm = _normalize_symbol(symbol)
    routed_etf = _symbol_to_etf(symbol)

    # ── Gate 1: Allowed symbols ──────────────────────────────────────────────
    allowed_syms = [_normalize_symbol(s) for s in (config.get('allowed_symbols') or [])]
    if not allowed_syms:
        results.append(_gate('ALLOWED_SYMBOLS', _GATE_SKIP,
                             'allowed_symbols is empty — all symbols permitted'))
    elif sym_norm in allowed_syms:
        results.append(_gate('ALLOWED_SYMBOLS', _GATE_PASS,
                             f'{sym_norm} in allowed_symbols {allowed_syms}'))
    else:
        results.append(_gate('ALLOWED_SYMBOLS', _GATE_FAIL,
                             f'{sym_norm} not in allowed_symbols {allowed_syms}',
                             'REJECTED_SYMBOL_NOT_ALLOWED'))

    # ── Gate 2: Allowed sessions ─────────────────────────────────────────────
    allowed_sess = [s.upper().strip() for s in (config.get('allowed_sessions') or [])]
    sess_upper   = (session or '').upper().strip()
    if not allowed_sess:
        results.append(_gate('ALLOWED_SESSIONS', _GATE_SKIP,
                             'allowed_sessions is empty — all sessions permitted'))
    elif sess_upper in allowed_sess:
        results.append(_gate('ALLOWED_SESSIONS', _GATE_PASS,
                             f'{sess_upper} in allowed_sessions {allowed_sess}'))
    else:
        results.append(_gate('ALLOWED_SESSIONS', _GATE_FAIL,
                             f'{sess_upper} not in allowed_sessions {allowed_sess}',
                             'REJECTED_SESSION'))

    # ── Gate 3: Max trades per day ───────────────────────────────────────────
    max_trades = int(config.get('max_trades_per_day') or 0)
    if max_trades <= 0:
        results.append(_gate('MAX_TRADES_PER_DAY', _GATE_SKIP,
                             'max_trades_per_day=0 — unlimited'))
    elif trade_count >= max_trades:
        results.append(_gate('MAX_TRADES_PER_DAY', _GATE_FAIL,
                             f'trade_count={trade_count} >= max_trades_per_day={max_trades}',
                             'REJECTED_MAX_TRADES'))
    else:
        results.append(_gate('MAX_TRADES_PER_DAY', _GATE_PASS,
                             f'{trade_count}/{max_trades} trades today'))

    # ── Gate 4: Max contracts total (concurrent open positions) ─────────────
    max_total = int(config.get('max_contracts_total') or 0)
    if max_total <= 0:
        results.append(_gate('MAX_CONTRACTS_TOTAL', _GATE_SKIP,
                             'max_contracts_total=0 — unlimited'))
    elif len(open_positions) >= max_total:
        results.append(_gate('MAX_CONTRACTS_TOTAL', _GATE_FAIL,
                             f'open_positions={len(open_positions)} >= max_contracts_total={max_total}',
                             'REJECTED_MAX_CONTRACTS'))
    else:
        results.append(_gate('MAX_CONTRACTS_TOTAL', _GATE_PASS,
                             f'{len(open_positions)}/{max_total} total positions'))

    # ── Gate 5: Max contracts per symbol ─────────────────────────────────────
    max_per_sym = int(config.get('max_contracts_per_symbol') or 0)
    if max_per_sym <= 0:
        results.append(_gate('MAX_CONTRACTS_PER_SYMBOL', _GATE_SKIP,
                             'max_contracts_per_symbol=0 — unlimited'))
    else:
        sym_positions = [
            p for p in open_positions
            if str(p.get('symbol', '')).upper() == routed_etf
        ]
        if len(sym_positions) >= max_per_sym:
            results.append(_gate('MAX_CONTRACTS_PER_SYMBOL', _GATE_FAIL,
                                 f'{routed_etf} has {len(sym_positions)} positions >= max_contracts_per_symbol={max_per_sym}',
                                 'REJECTED_MAX_CONTRACTS'))
        else:
            results.append(_gate('MAX_CONTRACTS_PER_SYMBOL', _GATE_PASS,
                                 f'{routed_etf}: {len(sym_positions)}/{max_per_sym} positions'))

    # ── Gate 6: Daily loss limit ──────────────────────────────────────────────
    max_daily_loss = float(config.get('max_daily_loss') or 0.0)
    if max_daily_loss <= 0.0:
        results.append(_gate('DAILY_LOSS_LIMIT', _GATE_SKIP,
                             'max_daily_loss=0 — not configured'))
    elif daily_pnl < -max_daily_loss:
        results.append(_gate('DAILY_LOSS_LIMIT', _GATE_FAIL,
                             f'daily_pnl={daily_pnl:.2f} < -{max_daily_loss:.2f} (prop limit)',
                             'REJECTED_PROP_DAILY_LOSS'))
    else:
        remaining = max_daily_loss + daily_pnl
        results.append(_gate('DAILY_LOSS_LIMIT', _GATE_PASS,
                             f'daily_pnl={daily_pnl:.2f}, remaining loss budget={remaining:.2f}'))

    # ── Gate 7: Max total loss (from starting balance) ────────────────────────
    max_total_loss    = float(config.get('max_total_loss')    or 0.0)
    starting_balance  = float(config.get('starting_balance')  or 0.0)
    current_balance   = float(config.get('current_balance')   or 0.0)
    if max_total_loss <= 0.0 or starting_balance <= 0.0 or current_balance <= 0.0:
        results.append(_gate('MAX_TOTAL_LOSS', _GATE_SKIP,
                             'max_total_loss or starting_balance or current_balance is 0 — not configured'))
    else:
        total_loss = starting_balance - current_balance
        if total_loss >= max_total_loss:
            results.append(_gate('MAX_TOTAL_LOSS', _GATE_FAIL,
                                 f'total_loss={total_loss:.2f} >= max_total_loss={max_total_loss:.2f}',
                                 'REJECTED_PROP_MAX_LOSS'))
        else:
            remaining = max_total_loss - total_loss
            results.append(_gate('MAX_TOTAL_LOSS', _GATE_PASS,
                                 f'total_loss={total_loss:.2f}/{max_total_loss:.2f}, '
                                 f'remaining budget={remaining:.2f}'))

    return results
