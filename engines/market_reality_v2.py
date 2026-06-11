"""
engines/market_reality_v2.py — Market Reality 2.0

NOVA's objective ground-truth referee.

No AI. No Claude. No Pine. No PROS. No setup logic. No cached narrative.
Pure deterministic scoring of hard market facts.

Purpose: prevent stale narrative and local setup optimism from overriding
obvious market truth. If NQ/ES are making weekly lows, this layer says
BEARISH_DOMINANT regardless of any prior context, setup phase, or cached read.

Facts assessed per instrument (NQ and ES scored independently, combined):
  pct_change     NQ/ES % change vs prior close              weight +-2
  vs_vwap        price above/below intraday VWAP             weight +-1
  vs_open        price above/below daily open                weight +-1
  vs_ib_mid      price above/below IB midpoint (9:30-10:30)  weight +-1
  ib_position    price above IB high / below IB low          weight +-2
  session_pos    in top or bottom 20% of session range       weight +-1
  weekly_struct  weekly high/low break (shared, not doubled) weight +-3

Max combined score: +-19 (8 per instrument minus 1 for shared weekly fact)

Output states:
  PANIC_SELLING     extreme down move (score <=-12 OR big pct + weekly low)
  BEARISH_DOMINANT  score <= -8
  BEARISH_LEANING   score <= -4
  RANGE_BOUND       -3 to +3
  BULLISH_LEANING   score >= +4
  BULLISH_DOMINANT  score >= +8
  NEUTRAL           insufficient data (levels unavailable)

Execution hard gates (overrides all setup logic and Pine state):
  BEARISH_DOMINANT / PANIC_SELLING  block LONG auto-execution
  BULLISH_DOMINANT                  block SHORT auto-execution
  Counter-trend setups may still surface as HEADS_UP.

Computed every Finnhub cycle (~5 min). Saved to donna_market_reality_v2.json.
Consumed by: reasoning prompt, conviction gate, directional pressure, assistant.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from engines.market_reality_shared import fetch_weekly_structure

_BASE_DIR  = Path(__file__).parent.parent
_V2_FILE   = _BASE_DIR / 'data' / 'donna_market_reality_v2.json'
_RISK_FILE = _BASE_DIR / 'data' / 'donna_risk_state.json'
_NY_TZ     = ZoneInfo('America/New_York')

# ── Score thresholds ──────────────────────────────────────────────────────────
_PANIC_SCORE    = -12
_DOMINANT_SCORE =   8   # abs value
_LEANING_SCORE  =   4   # abs value


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Intraday data fetch ───────────────────────────────────────────────────────

def _fetch_intraday(yf_symbol: str) -> dict:
    """
    Fetch today's 5-minute bars via yfinance and extract:
      daily_open, session_high, session_low, ib_high, ib_low, ib_mid, vwap

    Returns empty dict on any failure. All consumers must handle gracefully.
    Tolerates missing volume (VWAP will be None), partial IB (before 10:30 ET),
    and empty DataFrames (pre-market, weekend, market closed).
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(yf_symbol)
        hist   = ticker.history(period='1d', interval='5m')

        if hist is None or hist.empty:
            return {}

        # Ensure timezone-aware index in NY time
        if hist.index.tz is None:
            hist.index = hist.index.tz_localize('UTC')
        hist.index = hist.index.tz_convert(_NY_TZ)

        # Only use regular session bars (9:30 onwards)
        session_mask = (hist.index.hour > 9) | (
            (hist.index.hour == 9) & (hist.index.minute >= 30)
        )
        session_bars = hist[session_mask]

        if session_bars.empty:
            return {}

        daily_open   = _safe(session_bars['Open'].iloc[0])
        session_high = _safe(session_bars['High'].max())
        session_low  = _safe(session_bars['Low'].min())

        # IB: 9:30 to 10:29 ET inclusive
        ib_mask = (
            ((session_bars.index.hour == 9)  & (session_bars.index.minute >= 30)) |
            ((session_bars.index.hour == 10) & (session_bars.index.minute < 30))
        )
        ib_bars  = session_bars[ib_mask]
        ib_high  = _safe(ib_bars['High'].max()) if not ib_bars.empty else None
        ib_low   = _safe(ib_bars['Low'].min())  if not ib_bars.empty else None
        ib_mid   = round((ib_high + ib_low) / 2, 2) if ib_high and ib_low else None

        # VWAP = sum(typical * volume) / sum(volume)
        vwap = None
        vol_sum = _safe(session_bars['Volume'].sum())
        if vol_sum > 0:
            typical  = (session_bars['High'] + session_bars['Low'] + session_bars['Close']) / 3
            vwap_raw = _safe((typical * session_bars['Volume']).sum() / vol_sum)
            if vwap_raw > 0:
                vwap = round(vwap_raw, 2)

        return {
            'daily_open':   round(daily_open, 2)   if daily_open   else None,
            'session_high': round(session_high, 2) if session_high else None,
            'session_low':  round(session_low, 2)  if session_low  else None,
            'ib_high':      round(ib_high, 2)       if ib_high      else None,
            'ib_low':       round(ib_low, 2)        if ib_low       else None,
            'ib_mid':       ib_mid,
            'vwap':         vwap,
        }

    except Exception as exc:
        print(f'[market_reality_v2] intraday fetch failed {yf_symbol}: {exc}')
        return {}


# ── Per-instrument fact scoring ───────────────────────────────────────────────

def _score_instrument(price: float, pct: float, levels: dict) -> tuple[int, dict]:
    """
    Score one instrument (NQ or ES) against its intraday levels.
    Returns (score, facts_dict). Weekly structure is scored separately (shared).
    """
    score = 0
    facts: dict = {}

    def _fact(key: str, value, pts: int, note: str) -> None:
        score_ref  = [score]  # closure workaround
        signal = 'BULL' if pts > 0 else 'BEAR' if pts < 0 else 'NEUTRAL'
        facts[key] = {'value': value, 'signal': signal, 'pts': pts, 'note': note}

    # -- Fact 1: percent change vs prior close (weight +-2) --------------------
    if pct >= 0.4:
        pts = 2
    elif pct >= 0.1:
        pts = 1
    elif pct <= -0.4:
        pts = -2
    elif pct <= -0.1:
        pts = -1
    else:
        pts = 0
    score += pts
    facts['pct_change'] = {
        'value':  round(pct, 3),
        'signal': 'BULL' if pts > 0 else 'BEAR' if pts < 0 else 'NEUTRAL',
        'pts':    pts,
        'note':   f'{pct:+.2f}% vs prior close',
    }

    # -- Fact 2: price vs VWAP (weight +-1) ------------------------------------
    vwap = levels.get('vwap')
    if vwap and price:
        pts = 1 if price > vwap else -1
        score += pts
        facts['vs_vwap'] = {
            'value':  'ABOVE' if pts > 0 else 'BELOW',
            'signal': 'BULL'  if pts > 0 else 'BEAR',
            'pts':    pts,
            'note':   f'{price:.2f} vs VWAP {vwap:.2f}',
        }

    # -- Fact 3: price vs daily open (weight +-1) ------------------------------
    daily_open = levels.get('daily_open')
    if daily_open and price:
        pts = 1 if price > daily_open else -1
        score += pts
        facts['vs_open'] = {
            'value':  'ABOVE' if pts > 0 else 'BELOW',
            'signal': 'BULL'  if pts > 0 else 'BEAR',
            'pts':    pts,
            'note':   f'{price:.2f} vs open {daily_open:.2f}',
        }

    # -- Fact 4: price vs IB midpoint (weight +-1) -----------------------------
    ib_mid = levels.get('ib_mid')
    if ib_mid and price:
        pts = 1 if price > ib_mid else -1
        score += pts
        facts['vs_ib_mid'] = {
            'value':  'ABOVE' if pts > 0 else 'BELOW',
            'signal': 'BULL'  if pts > 0 else 'BEAR',
            'pts':    pts,
            'note':   f'{price:.2f} vs IB_mid {ib_mid:.2f}',
        }

    # -- Fact 5: IB position — above IB high or below IB low (weight +-2) -----
    ib_high = levels.get('ib_high')
    ib_low  = levels.get('ib_low')
    if ib_high and ib_low and price:
        if price > ib_high:
            pts = 2; pos = 'ABOVE_IB_HIGH'
        elif price < ib_low:
            pts = -2; pos = 'BELOW_IB_LOW'
        else:
            pts = 0; pos = 'INSIDE_IB'
        score += pts
        facts['ib_position'] = {
            'value':  pos,
            'signal': 'BULL' if pts > 0 else 'BEAR' if pts < 0 else 'NEUTRAL',
            'pts':    pts,
            'note':   f'IB {ib_low:.2f}–{ib_high:.2f}',
        }

    # -- Fact 6: session range position (weight +-1) ---------------------------
    sh = levels.get('session_high')
    sl = levels.get('session_low')
    if sh and sl and price and sh > sl:
        pos_pct = (price - sl) / (sh - sl)
        if pos_pct >= 0.80:
            pts = 1; pos_label = 'NEAR_SESSION_HIGH'
        elif pos_pct <= 0.20:
            pts = -1; pos_label = 'NEAR_SESSION_LOW'
        else:
            pts = 0; pos_label = 'MID_SESSION_RANGE'
        score += pts
        facts['session_position'] = {
            'value':  pos_label,
            'signal': 'BULL' if pts > 0 else 'BEAR' if pts < 0 else 'NEUTRAL',
            'pts':    pts,
            'note':   f'{pos_pct:.0%} of session range ({sl:.2f}–{sh:.2f})',
        }

    return score, facts


# ── State classification ──────────────────────────────────────────────────────

def _classify_state(
    total_score:      int,
    weekly_structure: str,
    nq_pct:           float,
    es_pct:           float,
    fact_count:       int,
) -> str:
    """Map combined score + context to an output state."""
    if fact_count < 3:
        return 'NEUTRAL'

    min_pct = min(nq_pct, es_pct)

    # PANIC_SELLING: extreme score OR severe drop + weekly low break
    if total_score <= _PANIC_SCORE:
        return 'PANIC_SELLING'
    if min_pct <= -1.5 and weekly_structure == 'WEEKLY_LOW_BREAK':
        return 'PANIC_SELLING'
    if total_score <= -8 and min_pct <= -1.0:
        return 'PANIC_SELLING'

    if total_score <= -_DOMINANT_SCORE:
        return 'BEARISH_DOMINANT'
    if total_score <= -_LEANING_SCORE:
        return 'BEARISH_LEANING'
    if total_score >= _DOMINANT_SCORE:
        return 'BULLISH_DOMINANT'
    if total_score >= _LEANING_SCORE:
        return 'BULLISH_LEANING'

    # Borderline: is a key level being crossed right now?
    if abs(total_score) in (3,):
        return 'TRANSITION'

    return 'RANGE_BOUND'


# ── Main compute ──────────────────────────────────────────────────────────────

def compute_market_reality_v2() -> dict:
    """
    Compute Market Reality 2.0 state. Called from process_finnhub_cycle().
    Fetches intraday 5m bars for NQ=F and ES=F, scores all hard facts,
    and saves result to donna_market_reality_v2.json.
    Fully independent of V1 — weekly structure fetched via shared module.

    Returns the full state dict. Never raises — returns a NEUTRAL state on
    any failure so the rest of the system is never blocked.
    """
    try:
        # Load price data from risk state (set by Finnhub cycle)
        risk     = _read_json(_RISK_FILE)
        snapshot = risk.get('market_snapshot', {})

        nq_price = _safe((snapshot.get('NQ') or {}).get('last'))
        es_price = _safe((snapshot.get('ES') or {}).get('last'))
        nq_pct   = _safe((snapshot.get('NQ') or {}).get('pct'))
        es_pct   = _safe((snapshot.get('ES') or {}).get('pct'))
        vix      = _safe((snapshot.get('VIX') or {}).get('last'))

        # Fetch weekly structure from shared module — independent of V1
        weekly_data      = fetch_weekly_structure()
        weekly_structure = weekly_data.get('structure', 'RANGE')

        # Fetch intraday levels (network calls — both tolerate failure)
        nq_levels = _fetch_intraday('NQ=F')
        es_levels = _fetch_intraday('ES=F')

        # Score per instrument
        nq_score, nq_facts = _score_instrument(nq_price, nq_pct, nq_levels)
        es_score, es_facts = _score_instrument(es_price, es_pct, es_levels)

        # Weekly structure: scored once (shared context, not per-instrument)
        weekly_pts = 0
        if weekly_structure == 'WEEKLY_HIGH_BREAK':
            weekly_pts =  3
        elif weekly_structure == 'WEEKLY_LOW_BREAK':
            weekly_pts = -3

        total_score = nq_score + es_score + weekly_pts
        fact_count  = len(nq_facts) + len(es_facts) + (1 if weekly_pts != 0 else 0)

        # Count bull/bear facts across both instruments
        all_facts = {**{f'nq_{k}': v for k, v in nq_facts.items()},
                     **{f'es_{k}': v for k, v in es_facts.items()}}
        if weekly_pts != 0:
            all_facts['weekly_structure'] = {
                'value':  weekly_structure,
                'signal': 'BULL' if weekly_pts > 0 else 'BEAR',
                'pts':    weekly_pts,
                'note':   weekly_structure,
            }

        bull_facts = [f for f in all_facts.values() if f.get('signal') == 'BULL']
        bear_facts = [f for f in all_facts.values() if f.get('signal') == 'BEAR']

        state = _classify_state(total_score, weekly_structure, nq_pct, es_pct, fact_count)

        # Hard execution gates
        block_longs  = state in ('BEARISH_DOMINANT', 'PANIC_SELLING')
        block_shorts = state in ('BULLISH_DOMINANT',)

        block_longs_reason = ''
        if block_longs:
            top_bear = sorted(bear_facts, key=lambda x: x.get('pts', 0))[:3]
            block_longs_reason = (
                f'{state}: {len(bear_facts)} bear facts | '
                + ' | '.join(f.get('note', '') for f in top_bear)
            )

        block_shorts_reason = ''
        if block_shorts:
            top_bull = sorted(bull_facts, key=lambda x: -x.get('pts', 0))[:3]
            block_shorts_reason = (
                f'{state}: {len(bull_facts)} bull facts | '
                + ' | '.join(f.get('note', '') for f in top_bull)
            )

        result = {
            'state':                state,
            'score':                total_score,
            'nq_score':             nq_score,
            'es_score':             es_score,
            'weekly_pts':           weekly_pts,
            'bull_fact_count':      len(bull_facts),
            'bear_fact_count':      len(bear_facts),
            'nq_price':             nq_price,
            'es_price':             es_price,
            'nq_pct':               round(nq_pct, 3),
            'es_pct':               round(es_pct, 3),
            'vix':                  vix,
            'weekly_structure':     weekly_structure,
            'nq_levels':            nq_levels,
            'es_levels':            es_levels,
            'nq_facts':             nq_facts,
            'es_facts':             es_facts,
            'all_facts':            all_facts,
            'block_longs':          block_longs,
            'block_shorts':         block_shorts,
            'block_longs_reason':   block_longs_reason,
            'block_shorts_reason':  block_shorts_reason,
            'last_updated':         _utc_iso(),
        }

        _V2_FILE.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')

        bear_str = f'{len(bear_facts)} bear' if bear_facts else 'no bear'
        bull_str = f'{len(bull_facts)} bull' if bull_facts else 'no bull'
        print(
            f'[market_reality_v2] {state} | score={total_score:+d} | '
            f'{bull_str} | {bear_str} | NQ {nq_pct:+.2f}% ES {es_pct:+.2f}%'
        )
        return result

    except Exception as exc:
        print(f'[market_reality_v2] compute error: {exc}')
        return _neutral_state()


def _neutral_state() -> dict:
    return {
        'state': 'NEUTRAL', 'score': 0, 'nq_score': 0, 'es_score': 0,
        'weekly_pts': 0, 'bull_fact_count': 0, 'bear_fact_count': 0,
        'nq_price': 0.0, 'es_price': 0.0, 'nq_pct': 0.0, 'es_pct': 0.0,
        'vix': 0.0, 'weekly_structure': 'RANGE',
        'nq_levels': {}, 'es_levels': {}, 'nq_facts': {}, 'es_facts': {}, 'all_facts': {},
        'block_longs': False, 'block_shorts': False,
        'block_longs_reason': '', 'block_shorts_reason': '',
        'last_updated': _utc_iso(),
    }


# ── Load / format ─────────────────────────────────────────────────────────────

def load_market_reality_v2() -> dict:
    """Load cached MR2 state from file. No network calls. Safe defaults if missing."""
    data = _read_json(_V2_FILE)
    return data if data else _neutral_state()


def format_for_prompt(mr2: dict) -> str:
    """
    Full MR2 block for Claude evaluation prompt.
    Placed before setup logic so it acts as ground truth override.
    """
    state  = mr2.get('state', 'NEUTRAL')
    score  = mr2.get('score', 0)
    nq_pct = mr2.get('nq_pct', 0.0)
    es_pct = mr2.get('es_pct', 0.0)
    vix    = mr2.get('vix', 0.0)
    weekly = mr2.get('weekly_structure', 'RANGE')
    bulls  = mr2.get('bull_fact_count', 0)
    bears  = mr2.get('bear_fact_count', 0)
    bl     = mr2.get('block_longs',  False)
    bs     = mr2.get('block_shorts', False)

    lines = [
        '=== MARKET REALITY 2.0 (objective ground truth — overrides all prior narrative) ===',
        f'State: {state}  |  Score: {score:+d}  |  Bull facts: {bulls}  |  Bear facts: {bears}',
        f'NQ: {nq_pct:+.2f}%   ES: {es_pct:+.2f}%   VIX: {vix:.1f}',
        f'Weekly structure: {weekly}',
    ]

    # NQ key levels
    nq_l = mr2.get('nq_levels', {})
    if nq_l:
        level_parts = []
        if nq_l.get('vwap'):     level_parts.append(f'VWAP={nq_l["vwap"]:.2f}')
        if nq_l.get('ib_high'):  level_parts.append(f'IB={nq_l["ib_low"]:.2f}-{nq_l["ib_high"]:.2f}')
        if nq_l.get('daily_open'): level_parts.append(f'open={nq_l["daily_open"]:.2f}')
        if level_parts:
            lines.append(f'NQ levels: {" | ".join(level_parts)}')

    # Significant bear facts
    bear_notes = [
        f.get('note', '')
        for f in mr2.get('all_facts', {}).values()
        if f.get('signal') == 'BEAR' and f.get('pts', 0) <= -2
    ]
    if bear_notes:
        lines.append(f'Key bear facts: {" | ".join(bear_notes[:4])}')

    bull_notes = [
        f.get('note', '')
        for f in mr2.get('all_facts', {}).values()
        if f.get('signal') == 'BULL' and f.get('pts', 0) >= 2
    ]
    if bull_notes:
        lines.append(f'Key bull facts: {" | ".join(bull_notes[:4])}')

    if bl:
        lines.append(f'EXECUTION RULE: LONG signals BLOCKED — {mr2.get("block_longs_reason", state)}')
    if bs:
        lines.append(f'EXECUTION RULE: SHORT signals BLOCKED — {mr2.get("block_shorts_reason", state)}')

    lines.append('=== END MARKET REALITY 2.0 ===')
    return '\n'.join(lines)


def format_for_assistant(mr2: dict) -> str:
    """Compact single-line format for assistant context."""
    state  = mr2.get('state', 'NEUTRAL')
    score  = mr2.get('score', 0)
    nq_pct = mr2.get('nq_pct', 0.0)
    es_pct = mr2.get('es_pct', 0.0)
    bl     = mr2.get('block_longs',  False)
    bs     = mr2.get('block_shorts', False)
    gate   = ' | LONGS_BLOCKED' if bl else ' | SHORTS_BLOCKED' if bs else ''
    return (
        f'MR2: {state} score={score:+d} | NQ {nq_pct:+.2f}% ES {es_pct:+.2f}%'
        f' | facts={mr2.get("bull_fact_count",0)}bull/{mr2.get("bear_fact_count",0)}bear{gate}'
    )
