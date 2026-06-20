"""
engines/cross_market.py — Cross-Market Intelligence Layer.

Computes relationships between instruments that are already in risk_state.market_snapshot.
No new network calls. No new data sources. Pure analysis of existing data.

Signals computed:
  nq_vs_es       NQ % change minus ES % change — tech leadership vs lagging
  dxy_signal     Dollar headwind / tailwind vs equity direction
  yield_signal   US10Y intraday change — yield pressure or relief
  gold_signal    Gold direction vs equities — risk-off confirmation or divergence
  btc_signal     BTC direction vs equities — global risk appetite read
  vix_move       VIX % change today — speed of fear, not just level

Output:
  cross_market_bias   BEARISH_PRESSURE / MILD_HEADWIND / MIXED / NEUTRAL /
                      MILD_TAILWIND / BULLISH_SUPPORT
  narrative           Plain-English 1-2 line summary for Claude and the assistant
  headwind_count      Number of active headwind signals (0-5)
  tailwind_count      Number of active tailwind signals (0-5)

Architecture rule: Observation only. These signals feed intelligence context.
They do NOT gate execution. Gate decisions come after evidence accumulates.

Refresh: called at end of process_finnhub_cycle() (~5 min).
Read path: load_cross_market() -> donna_cross_market.json, no network call.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from core.config import CROSS_MARKET_FILE as _CM_FILE, RISK_STATE_FILE as _RISK_FILE

_THRESHOLDS = {
    'nq_vs_es_lead':      0.5,   # % spread for TECH_LEADING / TECH_LAGGING
    'dxy_move':           0.3,   # % DXY move considered meaningful
    'yield_pressure_bps': 0.05,  # absolute yield change in pct-pts (= 5 bps)
    'gold_move':          0.5,   # % gold move considered meaningful
    'btc_move':           1.5,   # % BTC move to read as risk signal
    'equity_move':        0.3,   # % equity average move to pair with assets above
    'vix_spike':          10.0,  # % VIX daily change for FEAR_SPIKE
    'vix_rising':          5.0,  # % VIX daily change for FEAR_RISING
    'vix_falling':        -5.0,  # % VIX daily change for CALMING
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


def _safe(v, default: float = 0.0) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def _get(snapshot: dict, key: str, field: str) -> float:
    return _safe((snapshot.get(key) or {}).get(field))


# ── Signal classifiers ────────────────────────────────────────────────────────

def _classify_nq_vs_es(nq_pct: float, es_pct: float) -> tuple[str, float]:
    spread = round(nq_pct - es_pct, 3)
    t = _THRESHOLDS['nq_vs_es_lead']
    if spread >= t:
        return 'TECH_LEADING', spread
    if spread <= -t:
        return 'TECH_LAGGING', spread
    return 'ALIGNED', spread


def _classify_dxy(dxy_pct: float, nq_pct: float) -> str:
    t = _THRESHOLDS['dxy_move']
    if dxy_pct >= t:
        # Dollar rising — typically NQ headwind
        return 'DXY_HEADWIND' if nq_pct < 0 else 'DXY_RISING_NQ_HOLDING'
    if dxy_pct <= -t:
        # Dollar falling — typically NQ tailwind
        return 'DXY_TAILWIND' if nq_pct > 0 else 'DXY_FALLING_NQ_WEAK'
    return 'DXY_NEUTRAL'


def _classify_yield(us10y_chg: float) -> str:
    """us10y_chg is the absolute change in yield percentage points (e.g. +0.05 = +5bps)."""
    t = _THRESHOLDS['yield_pressure_bps']
    if us10y_chg >= t:
        return 'YIELD_PRESSURE'
    if us10y_chg <= -t:
        return 'YIELD_RELIEF'
    return 'YIELD_NEUTRAL'


def _classify_gold(gold_pct: float, equity_avg: float) -> str:
    gm = _THRESHOLDS['gold_move']
    em = _THRESHOLDS['equity_move']
    if gold_pct >= gm and equity_avg <= -em:
        return 'GOLD_RISK_OFF'         # classic safe-haven bid
    if gold_pct >= gm and equity_avg >= em:
        return 'GOLD_INFLATION'        # both rising = possible inflation trade
    if gold_pct <= -gm and equity_avg <= -em:
        return 'GOLD_LIQUIDATION'      # both falling = broad liquidation
    return 'GOLD_NEUTRAL'


def _classify_btc(btc_pct: float, equity_avg: float) -> str:
    bt = _THRESHOLDS['btc_move']
    em = _THRESHOLDS['equity_move']
    if btc_pct >= bt and equity_avg >= em:
        return 'BTC_RISK_ON'           # crypto + equities up = risk appetite
    if btc_pct <= -bt and equity_avg <= -em:
        return 'BTC_RISK_OFF'          # crypto + equities down = global risk-off
    if abs(btc_pct) >= bt * 1.3 and abs(equity_avg) < em:
        return 'BTC_DIVERGING'         # large BTC move, equities flat = divergence
    return 'BTC_NEUTRAL'


def _classify_vix_move(vix_pct: float) -> str:
    if vix_pct >= _THRESHOLDS['vix_spike']:
        return 'FEAR_SPIKE'
    if vix_pct >= _THRESHOLDS['vix_rising']:
        return 'FEAR_RISING'
    if vix_pct <= _THRESHOLDS['vix_falling']:
        return 'FEAR_CALMING'
    return 'VIX_STABLE'


# ── Bias aggregation ──────────────────────────────────────────────────────────

def _aggregate_bias(
    nq_vs_es_label: str,
    dxy_signal:     str,
    yield_signal:   str,
    gold_signal:    str,
    btc_signal:     str,
    vix_move:       str,
) -> tuple[str, int, int]:
    headwinds = sum([
        nq_vs_es_label == 'TECH_LAGGING',
        dxy_signal == 'DXY_HEADWIND',
        yield_signal == 'YIELD_PRESSURE',
        gold_signal in ('GOLD_RISK_OFF', 'GOLD_LIQUIDATION'),
        btc_signal == 'BTC_RISK_OFF',
        vix_move == 'FEAR_SPIKE',
    ])
    tailwinds = sum([
        nq_vs_es_label == 'TECH_LEADING',
        dxy_signal == 'DXY_TAILWIND',
        yield_signal == 'YIELD_RELIEF',
        btc_signal == 'BTC_RISK_ON',
        vix_move == 'FEAR_CALMING',
    ])

    if headwinds >= 4:
        bias = 'BEARISH_PRESSURE'
    elif headwinds >= 2 and tailwinds == 0:
        bias = 'MILD_HEADWIND'
    elif headwinds >= 2 and tailwinds >= 2:
        bias = 'MIXED'
    elif tailwinds >= 3:
        bias = 'BULLISH_SUPPORT'
    elif tailwinds >= 2 and headwinds == 0:
        bias = 'MILD_TAILWIND'
    elif headwinds == 1 and tailwinds == 0:
        bias = 'SLIGHT_HEADWIND'
    elif tailwinds == 1 and headwinds == 0:
        bias = 'SLIGHT_TAILWIND'
    else:
        bias = 'NEUTRAL'

    return bias, headwinds, tailwinds


# ── Narrative builder ─────────────────────────────────────────────────────────

def _build_narrative(
    nq_pct:         float,
    es_pct:         float,
    nq_vs_es_label: str,
    nq_vs_es_spread: float,
    dxy_pct:        float,
    dxy_signal:     str,
    us10y_chg:      float,
    us10y_last:     float,
    yield_signal:   str,
    gold_pct:       float,
    gold_signal:    str,
    btc_pct:        float,
    btc_signal:     str,
    vix_pct:        float,
    vix_last:       float,
    vix_move:       str,
    cross_market_bias: str,
) -> str:
    parts: list[str] = []

    if nq_vs_es_label == 'TECH_LAGGING':
        parts.append(
            f'Tech lagging: NQ {nq_pct:+.2f}% vs ES {es_pct:+.2f}% '
            f'(spread {nq_vs_es_spread:+.2f}%)'
        )
    elif nq_vs_es_label == 'TECH_LEADING':
        parts.append(
            f'Tech leading: NQ {nq_pct:+.2f}% vs ES {es_pct:+.2f}% '
            f'(spread {nq_vs_es_spread:+.2f}%)'
        )

    if dxy_signal == 'DXY_HEADWIND':
        parts.append(f'DXY headwind confirmed ({dxy_pct:+.2f}%)')
    elif dxy_signal == 'DXY_TAILWIND':
        parts.append(f'DXY tailwind confirmed ({dxy_pct:+.2f}%)')
    elif dxy_signal == 'DXY_RISING_NQ_HOLDING':
        parts.append(f'DXY rising ({dxy_pct:+.2f}%) but NQ holding — divergence watch')
    elif dxy_signal == 'DXY_FALLING_NQ_WEAK':
        parts.append(f'DXY falling ({dxy_pct:+.2f}%) but NQ also weak — unusual')

    if yield_signal == 'YIELD_PRESSURE':
        bps = round(us10y_chg * 100)
        parts.append(f'Yields +{bps}bps to {us10y_last:.2f}% — NQ headwind active')
    elif yield_signal == 'YIELD_RELIEF':
        bps = round(abs(us10y_chg) * 100)
        parts.append(f'Yields -{bps}bps to {us10y_last:.2f}% — rate relief supporting NQ')

    if gold_signal == 'GOLD_RISK_OFF':
        parts.append(f'Gold confirming risk-off ({gold_pct:+.2f}%)')
    elif gold_signal == 'GOLD_LIQUIDATION':
        parts.append(f'Gold liquidating alongside equities — broad selling')
    elif gold_signal == 'GOLD_INFLATION':
        parts.append(f'Gold rising with equities ({gold_pct:+.2f}%) — possible inflation bid')

    if btc_signal == 'BTC_RISK_ON':
        parts.append(f'BTC confirming risk appetite ({btc_pct:+.2f}%)')
    elif btc_signal == 'BTC_RISK_OFF':
        parts.append(f'BTC confirming risk-off ({btc_pct:+.2f}%)')
    elif btc_signal == 'BTC_DIVERGING':
        parts.append(f'BTC diverging from equities ({btc_pct:+.2f}%) — monitor for follow-through')

    if vix_move == 'FEAR_SPIKE':
        parts.append(f'VIX spiking ({vix_pct:+.1f}%, now {vix_last:.1f}) — acute fear event')
    elif vix_move == 'FEAR_RISING':
        parts.append(f'VIX rising ({vix_pct:+.1f}%, now {vix_last:.1f}) — caution building')
    elif vix_move == 'FEAR_CALMING':
        parts.append(f'VIX declining ({vix_pct:+.1f}%, now {vix_last:.1f}) — fear receding')

    if not parts:
        return 'Cross-market signals neutral — no dominant cross-asset theme active.'

    return ' | '.join(parts)


# ── Main compute ──────────────────────────────────────────────────────────────

def compute_cross_market() -> dict:
    """
    Compute cross-market intelligence from existing risk_state.market_snapshot.
    No network calls. Saves to donna_cross_market.json. Returns the state dict.
    Never raises — returns NEUTRAL state on any failure.
    """
    try:
        risk     = _read_json(_RISK_FILE)
        snapshot = risk.get('market_snapshot', {})

        nq_pct     = _get(snapshot, 'NQ',    'pct')
        es_pct     = _get(snapshot, 'ES',    'pct')
        dxy_pct    = _get(snapshot, 'DXY',   'pct')
        us10y_chg  = _get(snapshot, 'US10Y', 'chg')   # absolute bps change
        us10y_last = _get(snapshot, 'US10Y', 'last')
        gold_pct   = _get(snapshot, 'GOLD',  'pct')
        btc_pct    = _get(snapshot, 'BTC',   'pct')
        vix_pct    = _get(snapshot, 'VIX',   'pct')
        vix_last   = _get(snapshot, 'VIX',   'last')

        # Average equity move for pairing signals
        equity_avg = (nq_pct + es_pct) / 2 if (nq_pct or es_pct) else 0.0

        # Classify each signal
        nq_vs_es_label, nq_vs_es_spread = _classify_nq_vs_es(nq_pct, es_pct)
        dxy_signal   = _classify_dxy(dxy_pct, nq_pct)
        yield_signal = _classify_yield(us10y_chg)
        gold_signal  = _classify_gold(gold_pct, equity_avg)
        btc_signal   = _classify_btc(btc_pct, equity_avg)
        vix_move     = _classify_vix_move(vix_pct)

        cross_market_bias, headwinds, tailwinds = _aggregate_bias(
            nq_vs_es_label, dxy_signal, yield_signal,
            gold_signal, btc_signal, vix_move,
        )

        narrative = _build_narrative(
            nq_pct, es_pct, nq_vs_es_label, nq_vs_es_spread,
            dxy_pct, dxy_signal,
            us10y_chg, us10y_last, yield_signal,
            gold_pct, gold_signal,
            btc_pct, btc_signal,
            vix_pct, vix_last, vix_move,
            cross_market_bias,
        )

        state = {
            'nq_pct':            round(nq_pct, 3),
            'es_pct':            round(es_pct, 3),
            'nq_vs_es_spread':   nq_vs_es_spread,
            'nq_vs_es_label':    nq_vs_es_label,
            'dxy_pct':           round(dxy_pct, 3),
            'dxy_signal':        dxy_signal,
            'us10y_last':        round(us10y_last, 3),
            'us10y_chg':         round(us10y_chg, 4),
            'yield_signal':      yield_signal,
            'gold_pct':          round(gold_pct, 3),
            'gold_signal':       gold_signal,
            'btc_pct':           round(btc_pct, 3),
            'btc_signal':        btc_signal,
            'vix_pct':           round(vix_pct, 3),
            'vix_last':          round(vix_last, 2),
            'vix_move':          vix_move,
            'cross_market_bias': cross_market_bias,
            'headwind_count':    headwinds,
            'tailwind_count':    tailwinds,
            'narrative':         narrative,
            'last_updated':      _utc_iso(),
        }

        _CM_FILE.write_text(json.dumps(state, indent=2), encoding='utf-8')
        print(
            f'[cross_market] {cross_market_bias} | '
            f'NQ/ES={nq_vs_es_label}({nq_vs_es_spread:+.2f}%) | '
            f'{dxy_signal} | {yield_signal} | {gold_signal} | {btc_signal} | {vix_move}'
        )
        return state

    except Exception as exc:
        print(f'[cross_market] compute error: {exc}')
        return _neutral_state()


def _neutral_state() -> dict:
    return {
        'nq_pct': 0.0, 'es_pct': 0.0,
        'nq_vs_es_spread': 0.0, 'nq_vs_es_label': 'ALIGNED',
        'dxy_pct': 0.0, 'dxy_signal': 'DXY_NEUTRAL',
        'us10y_last': 0.0, 'us10y_chg': 0.0, 'yield_signal': 'YIELD_NEUTRAL',
        'gold_pct': 0.0, 'gold_signal': 'GOLD_NEUTRAL',
        'btc_pct': 0.0, 'btc_signal': 'BTC_NEUTRAL',
        'vix_pct': 0.0, 'vix_last': 0.0, 'vix_move': 'VIX_STABLE',
        'cross_market_bias': 'NEUTRAL',
        'headwind_count': 0, 'tailwind_count': 0,
        'narrative': 'Cross-market data unavailable.',
        'last_updated': _utc_iso(),
    }


# ── Load / format ─────────────────────────────────────────────────────────────

def load_cross_market() -> dict:
    """Load cached cross-market state from file. No network calls."""
    data = _read_json(_CM_FILE)
    return data if data else _neutral_state()


def format_for_prompt(cm: dict) -> str:
    """
    Multi-line cross-market block for Claude evaluation prompt.
    Placed after Market Reality so Claude reads cross-asset context
    before evaluating any setup.
    """
    if not cm or cm.get('cross_market_bias') == 'NEUTRAL' and not cm.get('narrative'):
        return ''

    bias     = cm.get('cross_market_bias', 'NEUTRAL')
    hw       = cm.get('headwind_count', 0)
    tw       = cm.get('tailwind_count', 0)
    nq_pct   = cm.get('nq_pct', 0.0)
    es_pct   = cm.get('es_pct', 0.0)
    spread   = cm.get('nq_vs_es_spread', 0.0)
    nq_label = cm.get('nq_vs_es_label', 'ALIGNED')
    dxy_pct  = cm.get('dxy_pct', 0.0)
    dxy_sig  = cm.get('dxy_signal', 'DXY_NEUTRAL')
    us10y    = cm.get('us10y_last', 0.0)
    us10y_ch = cm.get('us10y_chg', 0.0)
    y_sig    = cm.get('yield_signal', 'YIELD_NEUTRAL')
    gold_pct = cm.get('gold_pct', 0.0)
    gold_sig = cm.get('gold_signal', 'GOLD_NEUTRAL')
    btc_pct  = cm.get('btc_pct', 0.0)
    btc_sig  = cm.get('btc_signal', 'BTC_NEUTRAL')
    vix_pct  = cm.get('vix_pct', 0.0)
    vix_last = cm.get('vix_last', 0.0)
    vix_move = cm.get('vix_move', 'VIX_STABLE')

    lines = [
        f'=== CROSS-MARKET INTELLIGENCE (observation only) ===',
        f'Bias: {bias} | Headwinds: {hw} | Tailwinds: {tw}',
        f'NQ/ES:   NQ {nq_pct:+.2f}% vs ES {es_pct:+.2f}% -> {nq_label} (spread {spread:+.2f}%)',
        f'DXY:     {dxy_pct:+.2f}% -> {dxy_sig}',
        f'US10Y:   {us10y:.3f}% (chg {us10y_ch:+.4f}pts / {round(us10y_ch*100):+d}bps) -> {y_sig}',
        f'Gold:    {gold_pct:+.2f}% -> {gold_sig}',
        f'BTC:     {btc_pct:+.2f}% -> {btc_sig}',
        f'VIX:     {vix_pct:+.1f}% (now {vix_last:.1f}) -> {vix_move}',
        f'Summary: {cm.get("narrative", "")}',
        f'=== END CROSS-MARKET INTELLIGENCE ===',
    ]
    return '\n'.join(lines)


def format_for_assistant(cm: dict) -> str:
    """Compact single-line format for assistant context."""
    if not cm:
        return 'CROSS_MKT: unavailable'
    bias     = cm.get('cross_market_bias', 'NEUTRAL')
    nq_label = cm.get('nq_vs_es_label', 'ALIGNED')
    spread   = cm.get('nq_vs_es_spread', 0.0)
    dxy_sig  = cm.get('dxy_signal', 'DXY_NEUTRAL')
    y_sig    = cm.get('yield_signal', 'YIELD_NEUTRAL')
    gold_sig = cm.get('gold_signal', 'GOLD_NEUTRAL')
    btc_sig  = cm.get('btc_signal', 'BTC_NEUTRAL')
    hw       = cm.get('headwind_count', 0)
    tw       = cm.get('tailwind_count', 0)
    return (
        f'CROSS_MKT: {bias} ({hw}hw/{tw}tw) | '
        f'NQ/ES={nq_label}({spread:+.2f}%) | {dxy_sig} | {y_sig} | {gold_sig} | {btc_sig}'
    )
