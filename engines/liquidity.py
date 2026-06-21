"""
engines/liquidity.py — Liquidity Intelligence.

Teaches NOVA to independently understand where price is likely seeking liquidity.

Liquidity is the engine of price movement. Key structural levels accumulate
resting orders — stops from trapped traders, limit orders from institutions,
breakout entries from retail. Price is drawn toward these levels to fill those
orders. Understanding this is the difference between watching price move and
understanding why it moves.

This engine answers one question: "Where is price seeking liquidity?"
It does NOT answer: "How should I trade the liquidity?"

Concepts taught:
  Liquidity level     A price level where resting orders are clustered
  Untapped            Level price has NOT yet reached this session (orders still resting)
  Swept               Level price HAS already exceeded this session (orders filled)
  Nearest target      Closest untapped level in each direction from current price
  Primary draw        Most significant untapped liquidity target given current position
  Liquidity distance  Points and % between current price and each level

Levels tracked (per instrument — NQ and ES):
  PDH / PDL       Prior day high / low — most referenced by professional traders
  ONH / ONL       Overnight high / low — session-specific cluster
  PWH / PWL       Prior week high / low — highest timeframe cluster tracked
  monthly_open    Monthly reference level (lighter cluster than session levels)

Swept determination:
  A level ABOVE current price is SWEPT if today's session_high has reached or
  exceeded it (resting orders above have been triggered or absorbed).
  A level BELOW current price is SWEPT if today's session_low has reached or
  gone below it.

Data sources (no new yfinance calls, no new APIs):
  donna_market_structure.json   — all key levels (PDH/PDL, ONH/ONL, PWH/PWL, monthly_open)
  donna_market_reality_v2.json  — today's session_high / session_low per instrument
  donna_risk_state.json         — current prices

Observation only. No execution gates. No entry rules. No grading changes.
This is Level 1 Core Intelligence — independent of any strategy.

Called from process_finnhub_cycle() after compute_market_structure().
Output: donna_liquidity.json
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from core.config import (
    LIQUIDITY_FILE         as _LIQ_FILE,
    MARKET_STRUCTURE_FILE  as _MS_FILE,
    MARKET_REALITY_V2_FILE as _MR2_FILE,
    RISK_STATE_FILE        as _RISK_FILE,
)

_NY_TZ = ZoneInfo('America/New_York')

# Significance scores — how strong a liquidity cluster is at each level type.
# Higher = more resting orders, stronger magnetic pull on price.
# PDH/PWH share top weight: PDH because every intraday professional marks it,
# PWH because weekly participants cluster stops/entries there.
_SIG = {
    'PWH': 3, 'PWL': 3,    # prior week — highest timeframe tracked
    'PDH': 3, 'PDL': 3,    # prior day  — universal intraday reference
    'ONH': 2, 'ONL': 2,    # overnight  — session-specific cluster
    'monthly_open': 1,      # monthly reference — lighter, directional bias
}
_SIG_LABEL = {3: 'HIGH', 2: 'MEDIUM', 1: 'LOW'}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(v, default: float = 0.0) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


# ── Core level analysis ───────────────────────────────────────────────────────

def _build_levels(
    ms: dict,
    session_high: Optional[float],
    session_low:  Optional[float],
    price:        float,
) -> list[dict]:
    """
    Build the full list of liquidity levels for one instrument.

    Each level gets:
      label, price, side (ABOVE/BELOW), status (UNTAPPED/SWEPT),
      distance_pts, distance_pct, significance, sig_score

    Sorted by absolute distance from current price (nearest first).
    Deduplicates on price — if two labels share the same price, the
    higher-significance one is kept.
    """
    candidates = [
        ('PDH',          ms.get('pdh')),
        ('PDL',          ms.get('pdl')),
        ('ONH',          ms.get('onh')),
        ('ONL',          ms.get('onl')),
        ('PWH',          ms.get('pwh')),
        ('PWL',          ms.get('pwl')),
        ('monthly_open', ms.get('monthly_open')),
    ]

    seen_prices: dict[float, dict] = {}

    for label, lvl_price in candidates:
        if not lvl_price or lvl_price <= 0:
            continue

        lvl_price = round(float(lvl_price), 2)
        side = 'ABOVE' if lvl_price >= price else 'BELOW'

        # Swept determination: has this session already reached the level?
        status = 'UNTAPPED'
        if side == 'ABOVE' and session_high and session_high >= lvl_price:
            status = 'SWEPT'
        elif side == 'BELOW' and session_low and session_low <= lvl_price:
            status = 'SWEPT'

        sig_score = _SIG.get(label, 1)
        entry = {
            'label':        label,
            'price':        lvl_price,
            'side':         side,
            'status':       status,
            'distance_pts': round(lvl_price - price, 2),
            'distance_pct': round((lvl_price - price) / price * 100, 3),
            'significance': _SIG_LABEL[sig_score],
            'sig_score':    sig_score,
        }

        # Deduplicate by price — keep highest significance
        if lvl_price in seen_prices:
            if sig_score > seen_prices[lvl_price]['sig_score']:
                seen_prices[lvl_price] = entry
        else:
            seen_prices[lvl_price] = entry

    levels = sorted(seen_prices.values(), key=lambda x: abs(x['distance_pts']))
    return levels


def _primary_draw(levels: list[dict]) -> Optional[dict]:
    """
    Select the primary draw — the most compelling untapped liquidity target.

    Score = sig_score / (1 + abs_distance_pts / 100)

    A nearby high-significance level scores highest.
    A distant low-significance level scores lowest.
    This naturally selects the immediate target without hardcoding rules.
    """
    untapped = [l for l in levels if l['status'] == 'UNTAPPED']
    if not untapped:
        return None
    return max(untapped, key=lambda l: l['sig_score'] / (1 + abs(l['distance_pts']) / 100))


def _nearest(levels: list[dict], side: str) -> Optional[dict]:
    """Nearest untapped level on the specified side."""
    candidates = [l for l in levels if l['side'] == side and l['status'] == 'UNTAPPED']
    return min(candidates, key=lambda l: abs(l['distance_pts'])) if candidates else None


def _compute_instrument(
    ms: dict,
    session_high: Optional[float],
    session_low:  Optional[float],
    price:        float,
    label:        str,
) -> dict:
    """
    Compute full liquidity picture for one instrument.
    Returns a dict ready to embed in the output state.
    """
    levels = _build_levels(ms, session_high, session_low, price)

    above_levels   = [l for l in levels if l['side'] == 'ABOVE']
    below_levels   = [l for l in levels if l['side'] == 'BELOW']

    untapped_above = [l for l in above_levels if l['status'] == 'UNTAPPED']
    untapped_below = [l for l in below_levels if l['status'] == 'UNTAPPED']
    swept_above    = [l for l in above_levels if l['status'] == 'SWEPT']
    swept_below    = [l for l in below_levels if l['status'] == 'SWEPT']

    draw   = _primary_draw(levels)
    near_a = _nearest(levels, 'ABOVE')
    near_b = _nearest(levels, 'BELOW')

    return {
        'price':              price,
        'levels':             levels,
        'untapped_above':     len(untapped_above),
        'untapped_below':     len(untapped_below),
        'swept_above':        len(swept_above),
        'swept_below':        len(swept_below),
        'nearest_above':      near_a,
        'nearest_below':      near_b,
        'primary_draw':       draw,
        'session_high':       session_high,
        'session_low':        session_low,
    }


# ── Narrative builder ─────────────────────────────────────────────────────────

def _build_narrative(nq: dict, es: dict) -> str:
    parts: list[str] = []

    draw = nq.get('primary_draw')
    if draw:
        dist = draw['distance_pts']
        pct  = draw['distance_pct']
        side = 'above' if draw['side'] == 'ABOVE' else 'below'
        parts.append(
            f'NQ primary draw: {draw["label"]} {draw["price"]:.2f} '
            f'({dist:+.0f}pts, {pct:+.2f}%) [{draw["significance"]}]'
        )

    near_a = nq.get('nearest_above')
    near_b = nq.get('nearest_below')
    if near_a and near_a != draw:
        parts.append(
            f'Nearest above: {near_a["label"]} {near_a["price"]:.2f} ({near_a["distance_pts"]:+.0f}pts) UNTAPPED'
        )
    if near_b and near_b != draw:
        parts.append(
            f'Nearest below: {near_b["label"]} {near_b["price"]:.2f} ({near_b["distance_pts"]:+.0f}pts) UNTAPPED'
        )

    u_a = nq.get('untapped_above', 0)
    u_b = nq.get('untapped_below', 0)
    s_a = nq.get('swept_above', 0)
    s_b = nq.get('swept_below', 0)
    if u_a + u_b + s_a + s_b > 0:
        parts.append(
            f'Untapped: {u_a} above / {u_b} below | '
            f'Swept today: {s_a} above / {s_b} below'
        )

    if not parts:
        return 'Liquidity data unavailable -- market closed or structure not yet computed.'

    return ' | '.join(parts)


# ── Market event emission ─────────────────────────────────────────────────────

def _emit_sweep_events(prev: dict, curr: dict) -> None:
    """Emit LIQUIDITY_EVENT to the feed when a level transitions UNTAPPED → SWEPT."""
    try:
        now_ny = datetime.now(_NY_TZ)
        m = now_ny.hour * 60 + now_ny.minute
        if not (9 * 60 + 30 <= m <= 16 * 60):
            return  # Regular session only
        from engines.synthesis import _emit_intelligence_event
        for inst in ('nq', 'es'):
            prev_lvls = {lv['label']: lv for lv in (prev.get(inst, {}).get('levels') or [])}
            curr_lvls = {lv['label']: lv for lv in (curr.get(inst, {}).get('levels') or [])}
            for label, clv in curr_lvls.items():
                plv = prev_lvls.get(label, {})
                if plv.get('status') == 'UNTAPPED' and clv.get('status') == 'SWEPT':
                    price = clv.get('price', '?')
                    side  = 'above' if clv.get('side') == 'ABOVE' else 'below'
                    sig   = clv.get('significance', '')
                    _emit_intelligence_event(
                        'LIQUIDITY_SWEEP',
                        {
                            'symbol':      inst.upper(),
                            'session':     'NY',
                            'level':       label,
                            'price':       price,
                            'significance': sig,
                            'description': f'{inst.upper()} swept {label} ({sig}) at {price} — resting orders cleared {side}',
                        },
                        event_type='LIQUIDITY_EVENT',
                    )
    except Exception as exc:
        print(f'[liquidity] sweep event error: {exc}')


# ── Main compute ──────────────────────────────────────────────────────────────

def compute_liquidity() -> dict:
    """
    Compute liquidity intelligence. Called from process_finnhub_cycle() after
    compute_market_structure().

    Reads from three existing files — no new network calls.
    Never raises — returns neutral state on any failure.
    """
    try:
        prev_state = _read_json(_LIQ_FILE)   # snapshot before overwrite
        ms_state  = _read_json(_MS_FILE)
        mr2_state = _read_json(_MR2_FILE)
        risk      = _read_json(_RISK_FILE)

        snapshot  = risk.get('market_snapshot', {})
        nq_price  = _safe((snapshot.get('NQ') or {}).get('last'))
        es_price  = _safe((snapshot.get('ES') or {}).get('last'))

        nq_ms = ms_state.get('nq', {})
        es_ms = ms_state.get('es', {})

        nq_mr2 = mr2_state.get('nq_levels', {})
        es_mr2 = mr2_state.get('es_levels', {})

        nq_sh = _safe(nq_mr2.get('session_high')) or None
        nq_sl = _safe(nq_mr2.get('session_low'))  or None
        es_sh = _safe(es_mr2.get('session_high')) or None
        es_sl = _safe(es_mr2.get('session_low'))  or None

        nq_data: dict = {}
        es_data: dict = {}

        if nq_price and nq_ms:
            nq_data = _compute_instrument(nq_ms, nq_sh, nq_sl, nq_price, 'NQ')
        if es_price and es_ms:
            es_data = _compute_instrument(es_ms, es_sh, es_sl, es_price, 'ES')

        narrative = _build_narrative(nq_data, es_data)

        state = {
            'nq':          nq_data,
            'es':          es_data,
            'narrative':   narrative,
            'last_updated': _utc_iso(),
        }

        _LIQ_FILE.write_text(json.dumps(state, indent=2, default=str), encoding='utf-8')

        if prev_state:
            _emit_sweep_events(prev_state, state)

        nq_draw = nq_data.get('primary_draw') or {}
        d_pts   = nq_draw.get('distance_pts')
        d_str   = f'{d_pts:+.0f}pts' if d_pts is not None else '?'
        print(
            f'[liquidity] NQ {nq_price:.2f} | '
            f'draw={nq_draw.get("label","?")}@{nq_draw.get("price","?")} ({d_str}) | '
            f'untapped: {nq_data.get("untapped_above","?")}up/{nq_data.get("untapped_below","?")}dn | '
            f'swept: {nq_data.get("swept_above","?")}up/{nq_data.get("swept_below","?")}dn'
        ) if nq_price else print('[liquidity] NQ price unavailable')

        return state

    except Exception as exc:
        print(f'[liquidity] compute error: {exc}')
        return _neutral_state()


def _neutral_state() -> dict:
    empty = {
        'price': None, 'levels': [],
        'untapped_above': 0, 'untapped_below': 0,
        'swept_above': 0, 'swept_below': 0,
        'nearest_above': None, 'nearest_below': None,
        'primary_draw': None,
        'session_high': None, 'session_low': None,
    }
    return {
        'nq': empty.copy(), 'es': empty.copy(),
        'narrative': 'Liquidity data unavailable.',
        'last_updated': _utc_iso(),
    }


# ── Load / format ─────────────────────────────────────────────────────────────

def load_liquidity() -> dict:
    """Load cached liquidity state from file. No network calls."""
    data = _read_json(_LIQ_FILE)
    return data if data else _neutral_state()


def format_for_prompt(liq: dict) -> str:
    """
    Multi-line liquidity block for the Claude evaluation prompt.
    Answers: where is price seeking liquidity? What has already been swept?

    Placed after Market Structure so Claude reads levels before interpreting
    the liquidity context built on top of them.
    """
    nq = liq.get('nq', {})
    es = liq.get('es', {})

    if not nq and not es:
        return ''

    def _fmt_level(l: Optional[dict]) -> str:
        if not l:
            return 'none'
        d = l['distance_pts']
        return f'{l["label"]} {l["price"]:.2f} ({d:+.0f}pts) [{l["significance"]}]'

    lines = ['=== LIQUIDITY INTELLIGENCE (observation only) ===']

    for inst_label, inst in (('NQ', nq), ('ES', es)):
        price = inst.get('price')
        if not price:
            lines.append(f'{inst_label}: price unavailable')
            continue

        draw   = inst.get('primary_draw')
        near_a = inst.get('nearest_above')
        near_b = inst.get('nearest_below')
        u_a    = inst.get('untapped_above', 0)
        u_b    = inst.get('untapped_below', 0)
        s_a    = inst.get('swept_above', 0)
        s_b    = inst.get('swept_below', 0)
        sh     = inst.get('session_high')
        sl     = inst.get('session_low')

        sh_str = f'{sh:.2f}' if sh else '?'
        sl_str = f'{sl:.2f}' if sl else '?'

        lines.append(f'{inst_label} ({price:.2f}) | session_range={sl_str}-{sh_str}:')
        lines.append(f'  Primary draw:   {_fmt_level(draw)}')
        lines.append(f'  Nearest above:  {_fmt_level(near_a)}  (UNTAPPED)')
        lines.append(f'  Nearest below:  {_fmt_level(near_b)}  (UNTAPPED)')
        lines.append(
            f'  Untapped: {u_a} above / {u_b} below  |  '
            f'Swept today: {s_a} above / {s_b} below'
        )

        # List all levels for full context
        levels = inst.get('levels', [])
        if levels:
            level_lines = []
            for l in levels:
                d = l['distance_pts']
                status_tag = 'SWEPT' if l['status'] == 'SWEPT' else 'UNTAPPED'
                level_lines.append(
                    f'    {l["label"]:14s} {l["price"]:.2f}  ({d:+.0f}pts)  '
                    f'{status_tag}  [{l["significance"]}]'
                )
            lines.append('  All levels:')
            lines.extend(level_lines)

    lines.append(f'Summary: {liq.get("narrative", "")}')
    lines.append('=== END LIQUIDITY INTELLIGENCE ===')
    return '\n'.join(lines)


def format_for_assistant(liq: dict) -> str:
    """Compact single-line format for assistant session context."""
    nq   = liq.get('nq', {})
    draw = nq.get('primary_draw')
    na   = nq.get('nearest_above')
    nb   = nq.get('nearest_below')
    u_a  = nq.get('untapped_above', 0)
    u_b  = nq.get('untapped_below', 0)
    s_a  = nq.get('swept_above', 0)
    s_b  = nq.get('swept_below', 0)

    draw_str = (
        f'{draw["label"]}@{draw["price"]:.0f}({draw["distance_pts"]:+.0f}pts)'
        if draw else '?'
    )
    na_str = f'{na["label"]}@{na["price"]:.0f}' if na else '?'
    nb_str = f'{nb["label"]}@{nb["price"]:.0f}' if nb else '?'

    return (
        f'LIQUIDITY: draw={draw_str} | '
        f'above={na_str}({u_a}untapped/{s_a}swept) '
        f'below={nb_str}({u_b}untapped/{s_b}swept)'
    )
