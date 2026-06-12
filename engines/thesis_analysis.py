"""engines/thesis_analysis.py — Correct Thesis / Bad Execution analysis framework.

For every closed DONNA_AUTO trade, answers:
  Was the market proving the thesis WRONG?
  or
  Was the market proving the thesis RIGHT after removing the position first?

Classification labels (one per closed trade):
  WRONG_IDEA                   both MR2 and directional pressure opposed direction
  RIGHT_IDEA_BAD_ENTRY         thesis correct, entry timing was the problem
  RIGHT_IDEA_STOP_TOO_TIGHT    thesis correct, stop was inside normal volatility
  RIGHT_IDEA_LIQUIDITY_SWEEP   thesis correct, swept through stop before expansion
  RIGHT_IDEA_EARLY_ENTRY       thesis correct, entered before confirmation window
  RIGHT_IDEA_POOR_CONFIRMATION thesis correct, confirmation signals were weak/conflicted
  RIGHT_IDEA_GOOD_EXECUTION    won cleanly; thesis and execution both correct
  INCONCLUSIVE                 insufficient data to classify

Public interface:
  analyze_closed_trade(trade: dict) -> dict   full pipeline, returns thesis_analysis block
  compute_excursions(trade: dict) -> dict      MAE/MFE/sweep/target-after-stop
  classify_trade(trade, excursions) -> (str, str)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ── Alpaca data credentials (same env vars used by execution layer) ─────────
_ALPACA_KEY    = os.getenv('ALPACA_API_KEY', '').strip()
_ALPACA_SECRET = os.getenv('ALPACA_SECRET_KEY', '').strip()
_DATA_BASE     = 'https://data.alpaca.markets'

# How far past exit to scan for target — ~100 minutes of 1m bars
_POST_EXIT_SCAN_BARS = 100

# Data dir (relative to this file: engines/ → project root → data/)
_DATA_DIR = Path(__file__).parent.parent / 'data'


# ── Alpaca bar fetch ─────────────────────────────────────────────────────────

def _get_bars(symbol: str, start_iso: str, end_iso: str) -> list[dict]:
    """Return Alpaca 1-minute bars. Returns [] on any error."""
    if not _ALPACA_KEY or not _ALPACA_SECRET:
        return []
    try:
        import requests
        r = requests.get(
            f'{_DATA_BASE}/v2/stocks/{symbol}/bars',
            headers={
                'APCA-API-KEY-ID':     _ALPACA_KEY,
                'APCA-API-SECRET-KEY': _ALPACA_SECRET,
            },
            params={
                'start':     start_iso,
                'end':       end_iso,
                'timeframe': '1Min',
                'limit':     500,
                'feed':      'iex',
            },
            timeout=10,
        )
        if r.ok:
            return r.json().get('bars', []) or []
    except Exception as e:
        print(f'[thesis_analysis] bars fetch error {symbol}: {e}')
    return []


# ── Timestamp helpers ─────────────────────────────────────────────────────────

def _parse_trade_times(trade: dict) -> tuple[str | None, str | None]:
    """
    Extract (entry_iso_utc, exit_iso_utc) from a journal trade record.
    entry comes from trade['timestamp'] (UTC ISO written at order submission).
    exit comes from trade['exit_time'] ("HH:MM:SS ET") + trade['trade_date'].
    """
    entry_iso: str | None = None
    exit_iso:  str | None = None

    raw_ts = trade.get('timestamp', '')
    if raw_ts:
        try:
            dt = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
            entry_iso = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except Exception:
            pass

    exit_t     = str(trade.get('exit_time', '') or '').replace(' ET', '').strip()
    trade_date = str(trade.get('trade_date', '') or '').strip()
    if exit_t and trade_date:
        try:
            from zoneinfo import ZoneInfo
            dt_naive = datetime.strptime(f'{trade_date} {exit_t}', '%Y-%m-%d %H:%M:%S')
            dt_ny    = dt_naive.replace(tzinfo=ZoneInfo('America/New_York'))
            exit_iso = dt_ny.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        except Exception:
            pass

    return entry_iso, exit_iso


def _eod_utc(trade_date: str) -> str | None:
    """Return 16:00:00 ET (NY session close) for the given trade_date as UTC ISO."""
    try:
        from zoneinfo import ZoneInfo
        dt_ny  = datetime.strptime(f'{trade_date} 16:00:00', '%Y-%m-%d %H:%M:%S')
        dt_ny  = dt_ny.replace(tzinfo=ZoneInfo('America/New_York'))
        return dt_ny.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return None


# ── Excursion computation ─────────────────────────────────────────────────────

def compute_excursions(trade: dict) -> dict:
    """
    Query Alpaca 1m bars for:
      1. Hold-period MAE (max adverse excursion) and MFE (max favorable excursion)
      2. Liquidity sweep detection (stop crossed then price recovered toward target)
      3. Whether target was reached after stop-out (rest of session)

    All $/share values in ETF terms (what was actually traded).
    Returns a dict; contains 'error' key if data unavailable.
    """
    symbol    = str(trade.get('ticker', '')).upper()
    direction = str(trade.get('direction', 'LONG')).upper()
    outcome   = str(trade.get('outcome', '')).upper()
    is_long   = direction == 'LONG'

    entry_px  = float(trade.get('entry_price') or 0)
    stop_px   = float(trade.get('stop_price')  or 0)
    target_px = float(trade.get('target_price') or 0)

    if not symbol or not entry_px or not stop_px or not target_px:
        return {'error': 'insufficient_trade_fields'}

    stop_dist   = abs(entry_px - stop_px)
    target_dist = abs(target_px - entry_px)

    if stop_dist == 0:
        return {'error': 'zero_stop_distance'}

    entry_iso, exit_iso = _parse_trade_times(trade)
    if not entry_iso or not exit_iso:
        return {'error': 'unparseable_timestamps'}

    # Guard: skip if exit is before or equal to entry (data anomaly)
    if exit_iso <= entry_iso:
        return {'error': 'exit_before_entry'}

    # ── Hold-period bars ──────────────────────────────────────────────────
    hold_bars = _get_bars(symbol, entry_iso, exit_iso)

    mae_pts = 0.0
    mfe_pts = 0.0

    for bar in hold_bars:
        hi = float(bar.get('h') or 0)
        lo = float(bar.get('l') or 0)
        if hi == 0 or lo == 0:
            continue
        if is_long:
            adverse   = entry_px - lo
            favorable = hi - entry_px
        else:
            adverse   = hi - entry_px
            favorable = entry_px - lo
        mae_pts = max(mae_pts, adverse)
        mfe_pts = max(mfe_pts, favorable)

    mae_pct_of_stop   = round(mae_pts / stop_dist,   3) if stop_dist   else 0.0
    mfe_pct_of_target = round(mfe_pts / target_dist, 3) if target_dist else 0.0

    # ── Liquidity sweep detection ──────────────────────────────────────────
    # A sweep: a hold-period bar's wick crosses the stop level (stop touched/exceeded),
    # then a later bar closes back through entry toward the target direction.
    # This is the signature of a "stop raid before expansion."
    sweep_detected = False
    sweep_bar_idx  = -1

    for i, bar in enumerate(hold_bars):
        lo = float(bar.get('l') or 0)
        hi = float(bar.get('h') or 0)
        if lo == 0 or hi == 0:
            continue

        stop_crossed = (is_long and lo < stop_px) or (not is_long and hi > stop_px)
        if not stop_crossed:
            continue

        # Check if any subsequent bar closes back through entry
        for rb in hold_bars[i + 1:]:
            rb_c = float(rb.get('c') or 0)
            if rb_c == 0:
                continue
            if is_long and rb_c > entry_px:
                sweep_detected = True
                sweep_bar_idx  = i
                break
            if not is_long and rb_c < entry_px:
                sweep_detected = True
                sweep_bar_idx  = i
                break
        if sweep_detected:
            break

    # ── Post-exit: did price reach the original target after stop-out? ────
    # Only meaningful for LOSS outcomes (stop-outs).
    reached_target_after = False
    bars_to_target_after: int | None = None

    if outcome == 'LOSS' and exit_iso:
        trade_date = str(trade.get('trade_date', '') or '')
        session_end_utc = _eod_utc(trade_date) if trade_date else None

        if session_end_utc and exit_iso < session_end_utc:
            post_bars = _get_bars(symbol, exit_iso, session_end_utc)
            for j, bar in enumerate(post_bars):
                hi = float(bar.get('h') or 0)
                lo = float(bar.get('l') or 0)
                if hi == 0 or lo == 0:
                    continue
                if is_long and hi >= target_px:
                    reached_target_after = True
                    bars_to_target_after = j
                    break
                if not is_long and lo <= target_px:
                    reached_target_after = True
                    bars_to_target_after = j
                    break

    return {
        'mae_pts':                  round(mae_pts, 4),
        'mfe_pts':                  round(mfe_pts, 4),
        'mae_pct_of_stop':          mae_pct_of_stop,
        'mfe_pct_of_target':        mfe_pct_of_target,
        'stop_distance':            round(stop_dist, 4),
        'target_distance':          round(target_dist, 4),
        'hold_bars_count':          len(hold_bars),
        'liquidity_sweep_detected': sweep_detected,
        'sweep_bar_index':          sweep_bar_idx if sweep_detected else None,
        'reached_target_after_stop': reached_target_after,
        'bars_to_target_after_stop': bars_to_target_after,
    }


# ── Thesis opposition check ───────────────────────────────────────────────────
#
# Directional pressure uses BULL_/BEAR_ prefix.
# Market Reality V2 uses BULLISH_/BEARISH_ prefix.
# Normalize both before comparison.

_DP_BEARISH  = {'BEAR_DOMINANT', 'BEAR_LEANING'}
_DP_BULLISH  = {'BULL_DOMINANT', 'BULL_LEANING'}
_MR2_BEARISH = {'BEARISH_DOMINANT', 'BEARISH_LEANING'}
_MR2_BULLISH = {'BULLISH_DOMINANT', 'BULLISH_LEANING'}


def _thesis_opposed(direction: str, mr2_state: str, dominance: str) -> bool:
    """
    Returns True when the market structure at entry objectively opposed the direction.

    Requires BOTH sources (MR2 + directional pressure) to agree before labeling
    a trade WRONG_IDEA. One source neutral → not WRONG_IDEA.
    """
    is_long   = direction == 'LONG'
    mr2_bear  = mr2_state.upper() in _MR2_BEARISH
    mr2_bull  = mr2_state.upper() in _MR2_BULLISH
    dp_bear   = dominance.upper() in _DP_BEARISH
    dp_bull   = dominance.upper() in _DP_BULLISH

    if is_long:
        return mr2_bear and dp_bear
    return mr2_bull and dp_bull


# ── Classifier ────────────────────────────────────────────────────────────────

def classify_trade(trade: dict, excursions: dict) -> tuple[str, str]:
    """
    Deterministic thesis classification. Returns (label, reason).

    Decision hierarchy:
      1. Insufficient data → INCONCLUSIVE
      2. Both MR2 and DP opposed direction → WRONG_IDEA
      3. WIN → assess execution quality → GOOD_EXECUTION or BAD_ENTRY
      4. LOSS + target reached after → identify WHY it was a bad execution
      5. LOSS + target not reached + thesis aligned → INCONCLUSIVE
    """
    outcome   = str(trade.get('outcome', '')).upper()
    direction = str(trade.get('direction', 'LONG')).upper()

    ctx             = trade.get('context_snapshot', {}) or {}
    mr2_state       = str(ctx.get('mr2_state',       'NEUTRAL')).upper()
    dominance       = str(ctx.get('dominance',        'NEUTRAL')).upper()
    conviction      = str(ctx.get('conviction',       'UNKNOWN')).upper()
    ib_aligned      = bool(ctx.get('ib_aligned',      False))
    session_quality = str(ctx.get('session_quality',  'C')).upper()
    momentum        = str(ctx.get('momentum',         'NEUTRAL')).upper()

    mae_pct       = float(excursions.get('mae_pct_of_stop',   0))
    mfe_pct       = float(excursions.get('mfe_pct_of_target', 0))
    sweep         = bool(excursions.get('liquidity_sweep_detected', False))
    reached_after = bool(excursions.get('reached_target_after_stop', False))
    bars_after    = excursions.get('bars_to_target_after_stop')

    # ── 1. Insufficient data ──────────────────────────────────────────────
    if excursions.get('error') or not ctx:
        reason = 'No context snapshot' if not ctx else excursions['error']
        return 'INCONCLUSIVE', f'Insufficient data: {reason}'

    # ── 2. WRONG_IDEA: both sources opposed direction at entry ────────────
    if _thesis_opposed(direction, mr2_state, dominance):
        return (
            'WRONG_IDEA',
            f'Market structure opposed direction at entry — '
            f'MR2={mr2_state} dominance={dominance}. '
            f'Market was proving the thesis wrong.'
        )

    # ── 3. WIN path ───────────────────────────────────────────────────────
    if outcome in ('WIN', 'BREAKEVEN'):
        if mae_pct < 0.40 and mfe_pct >= 0.70:
            return (
                'RIGHT_IDEA_GOOD_EXECUTION',
                f'Clean entry (MAE={mae_pct:.0%} of stop, MFE={mfe_pct:.0%} of target). '
                f'Thesis and execution both correct.'
            )
        if mae_pct >= 0.70:
            return (
                'RIGHT_IDEA_BAD_ENTRY',
                f'Won despite poor entry — stop threatened (MAE={mae_pct:.0%}). '
                f'Thesis correct but entry was marginal.'
            )
        return (
            'RIGHT_IDEA_GOOD_EXECUTION',
            f'Thesis correct, trade won (MAE={mae_pct:.0%} stop, MFE={mfe_pct:.0%} target).'
        )

    # ── 4. LOSS path — thesis aligned, trade stopped out ─────────────────

    bars_str = f' ({bars_after}m after stop-out)' if bars_after is not None else ''

    if reached_after:
        # Market proved thesis right AFTER removing us — classify the execution error

        # 4a. Liquidity sweep: stop crossed then price recovered
        if sweep:
            return (
                'RIGHT_IDEA_LIQUIDITY_SWEEP',
                f'Thesis correct — liquidity sweep through stop before target expansion{bars_str}. '
                f'Market raided stops then moved as expected.'
            )

        # 4b. Stop too tight: MAE is at or just past the stop (~1.0 = stop exactly hit)
        if 0.85 <= mae_pct <= 1.15:
            return (
                'RIGHT_IDEA_STOP_TOO_TIGHT',
                f'Thesis correct — MAE={mae_pct:.0%} of stop (stop was inside normal range). '
                f'Target reached{bars_str} — wider stop would have survived the excursion.'
            )

        # 4c. Early entry: IB incomplete or session quality too low
        if not ib_aligned or session_quality in ('C', 'D'):
            qual = (
                f'session_quality={session_quality}'
                if session_quality in ('C', 'D')
                else 'IB not aligned at entry'
            )
            return (
                'RIGHT_IDEA_EARLY_ENTRY',
                f'Thesis correct — entry before confirmation ({qual}). '
                f'Target reached{bars_str} in a later window.'
            )

        # 4d. Poor confirmation: conflicted signals or momentum opposing
        momentum_opposed = (
            (direction == 'LONG'  and momentum in ('BEARISH',)) or
            (direction == 'SHORT' and momentum in ('BULLISH',))
        )
        if conviction in ('CONFLICTED', 'LOW') or momentum_opposed:
            conf_detail = conviction if conviction in ('CONFLICTED', 'LOW') else f'momentum={momentum}'
            return (
                'RIGHT_IDEA_POOR_CONFIRMATION',
                f'Thesis correct — confirmation weak at entry ({conf_detail}). '
                f'Target reached{bars_str} after conditions improved.'
            )

        # 4e. Default: thesis aligned, target reached — entry was the differentiator
        return (
            'RIGHT_IDEA_BAD_ENTRY',
            f'Thesis correct — target reached{bars_str} after stop-out. '
            f'Entry was the differentiating factor (MAE={mae_pct:.0%} stop, '
            f'MFE={mfe_pct:.0%} target before exit).'
        )

    # ── 5. Thesis aligned, target NOT reached — cannot determine ─────────
    if outcome == 'EOD_CLOSE':
        return (
            'INCONCLUSIVE',
            'EOD forced close — insufficient post-exit window to confirm thesis direction.'
        )

    return (
        'INCONCLUSIVE',
        f'Thesis aligned at entry (MR2={mr2_state} dominance={dominance}) '
        f'but target not reached after stop-out. '
        f'Cannot distinguish WRONG_IDEA from CORRECT_IDEA_BAD_TIMING without further confirmation.'
    )


# ── Public interface ──────────────────────────────────────────────────────────

def analyze_closed_trade(trade: dict) -> dict:
    """
    Full thesis analysis pipeline for one closed journal trade.

    Returns the thesis_analysis dict to be written to the journal entry.
    Returns {} for OPEN trades or if trade has already been analyzed.
    Does not persist to journal — caller handles that.
    """
    from core.config import utc_now_iso

    outcome = str(trade.get('outcome', '')).upper()
    if outcome == 'OPEN':
        return {}

    # Skip re-analysis
    if trade.get('thesis_analysis'):
        return {}

    excursions               = compute_excursions(trade)
    classification, reason   = classify_trade(trade, excursions)

    return {
        'mae_pts':                  excursions.get('mae_pts'),
        'mfe_pts':                  excursions.get('mfe_pts'),
        'mae_pct_of_stop':          excursions.get('mae_pct_of_stop'),
        'mfe_pct_of_target':        excursions.get('mfe_pct_of_target'),
        'stop_distance':            excursions.get('stop_distance'),
        'target_distance':          excursions.get('target_distance'),
        'hold_bars_count':          excursions.get('hold_bars_count'),
        'liquidity_sweep_detected': excursions.get('liquidity_sweep_detected', False),
        'reached_target_after_stop': excursions.get('reached_target_after_stop', False),
        'bars_to_target_after_stop': excursions.get('bars_to_target_after_stop'),
        'classification':           classification,
        'classification_reason':    reason,
        'data_error':               excursions.get('error'),
        'analyzed_at':              utc_now_iso(),
    }
