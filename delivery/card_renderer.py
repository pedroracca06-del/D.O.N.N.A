"""card_renderer.py — NOVA execution card: chart area renderer.

Fetches OHLC bars and renders candles + execution overlays onto a
matplotlib axes object. No browser dependency — pure Python.

Symbol map: MES/ES → ES=F (yfinance)  |  MNQ/NQ → NQ=F
"""
from __future__ import annotations

from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np

try:
    import yfinance as yf
    _YF_OK = True
except ImportError:
    _YF_OK = False

try:
    import pandas as pd
    _PD_OK = True
except ImportError:
    _PD_OK = False

# ── Symbol mapping ─────────────────────────────────────────────────────────────
_YF_MAP = {
    'MES': 'ES=F', 'ES': 'ES=F',
    'MNQ': 'NQ=F', 'NQ': 'NQ=F',
}

# ── Color palette ──────────────────────────────────────────────────────────────
C = {
    'bg':           '#0a0c10',
    'chart_bg':     '#0d0f16',
    'panel_bg':     '#0f1118',
    'border':       '#1e2230',
    'grid':         '#141620',
    'up':           '#00c851',
    'up_wick':      '#00e05a',
    'down':         '#ff3355',
    'down_wick':    '#ff5577',
    'entry':        '#00d4ff',
    'sl':           '#ff3355',
    'tp1':          '#00c851',
    'tp2':          '#00ff99',
    'zone_demand':  '#0b2e1a',
    'zone_supply':  '#2e0b12',
    'orb_high':     '#6655ee',
    'orb_low':      '#ee8800',
    'ib_fill':      '#1a1a3a',
    'text_primary': '#dde1ef',
    'text_dim':     '#4a5878',
    'text_accent':  '#00d4ff',
    'nova_blue':    '#0080ff',
    'separator':    '#1a1e2a',
}

GRADE_COLOR = {'A': '#00c851', 'B': '#f0a500', 'C': '#ff6030', 'D': '#ff3355'}


# ── OHLC data fetch ────────────────────────────────────────────────────────────

def fetch_ohlc(symbol: str, bars: int = 78, interval: str = '5m'):
    """
    Fetch recent OHLC bars for a futures symbol.
    Returns a DataFrame with columns Open/High/Low/Close/Volume, or None.
    Falls back to synthetic candles if network unavailable.
    """
    if not (_YF_OK and _PD_OK):
        return None

    ticker = _YF_MAP.get(symbol.upper(), symbol)
    try:
        df = yf.download(ticker, period='1d', interval=interval,
                         progress=False, auto_adjust=True, multi_level_index=False)
        if df is None or df.empty:
            df = yf.download(ticker, period='5d', interval=interval,
                             progress=False, auto_adjust=True, multi_level_index=False)
        if df is None or df.empty:
            return None
        df = df.tail(bars).copy()
        return df
    except Exception:
        return None


def synthetic_ohlc(current_price: float, high_30: float, low_30: float,
                   bars: int = 60):
    """
    Generate plausible candle data when live fetch fails.
    Anchored to current price + session high/low.
    """
    if not _PD_OK:
        return None

    # Guard: if prices are zero or invalid, we can't generate meaningful candles
    if not current_price or current_price <= 0:
        return None

    rng = np.random.default_rng(seed=int(current_price) % 10000)
    mid   = (high_30 + low_30) / 2 if (high_30 and low_30) else current_price
    span  = max(high_30 - low_30, current_price * 0.001) if (high_30 and low_30) else current_price * 0.002

    prices = [mid]
    for _ in range(bars - 1):
        drift  = rng.normal(0, span * 0.04)
        prices.append(np.clip(prices[-1] + drift, low_30 - span * 0.2, high_30 + span * 0.2))
    prices[-1] = current_price

    rows = []
    for p in prices:
        body = span * rng.uniform(0.01, 0.25)
        wick = span * rng.uniform(0.02, 0.35)
        o = p + rng.uniform(-body, body)
        c = p + rng.uniform(-body, body)
        h = max(o, c) + rng.uniform(0, wick)
        l = min(o, c) - rng.uniform(0, wick)
        rows.append({'Open': o, 'High': h, 'Low': l, 'Close': c, 'Volume': 0})

    import pandas as pd
    from datetime import datetime, timedelta
    idx = [datetime.now() - timedelta(minutes=(bars - i) * 5) for i in range(bars)]
    return pd.DataFrame(rows, index=idx)


# ── Drawing primitives ─────────────────────────────────────────────────────────

def _draw_candles(ax, df, width: float = 0.55) -> None:
    for i, (_, row) in enumerate(df.iterrows()):
        try:
            o, h, l, c = float(row['Open']), float(row['High']), float(row['Low']), float(row['Close'])
        except Exception:
            continue
        bull       = c >= o
        body_color = C['up']        if bull else C['down']
        wick_color = C['up_wick']   if bull else C['down_wick']

        ax.plot([i, i], [l, h], color=wick_color, linewidth=0.7, zorder=2, solid_capstyle='round')

        body_h = max(abs(c - o), (h - l) * 0.005)
        rect = mpatches.Rectangle(
            (i - width / 2, min(o, c)),
            width, body_h,
            linewidth=0.2,
            edgecolor=wick_color,
            facecolor=body_color,
            zorder=3,
        )
        ax.add_patch(rect)


def _hline(ax, y: float, color: str, label: str, x0: int, x1: int,
           ls: str = '--', lw: float = 1.1) -> None:
    ylo, yhi = ax.get_ylim()
    if not (ylo <= y <= yhi):
        return  # level outside visible range — skip line and label
    ax.hlines(y, x0, x1, colors=color, linewidths=lw, linestyles=ls, zorder=5, alpha=0.9)
    ax.text(x1 + 0.4, y, label, color=color, fontsize=6.2, fontweight='bold',
            va='center', ha='left', zorder=6, clip_on=False,
            bbox=dict(boxstyle='round,pad=0.15', facecolor='#08090e',
                      edgecolor=color, linewidth=0.5, alpha=0.92))


def _zone(ax, y_lo: float, y_hi: float, fc: str, label: str,
          x0: int, x1: int, alpha: float = 0.30) -> None:
    span = y_hi - y_lo
    if span <= 0:
        return
    ax.fill_between([x0, x1], y_lo, y_hi, color=fc, alpha=alpha, zorder=1)
    ax.text(x1 - 0.8, (y_lo + y_hi) / 2, label,
            color=fc, fontsize=5.8, fontweight='bold',
            va='center', ha='right', alpha=0.85, zorder=4)


# ── Main render function ───────────────────────────────────────────────────────

def render_chart_axes(ax, df, signal: dict) -> None:
    """
    Render candles + execution overlays onto an existing matplotlib axes.

    signal keys (all optional):
        entry, stop, tp1, tp2      — float price levels
        direction                  — 'LONG' | 'SHORT'
        orb_high, orb_low          — ORB range levels
        ib_high, ib_low            — initial balance levels
        levels                     — list of float key price levels
    """
    ax.set_facecolor(C['chart_bg'])
    for spine in ax.spines.values():
        spine.set_color(C['border'])
        spine.set_linewidth(0.5)

    if df is None or len(df) == 0:
        ax.text(0.5, 0.5, 'CHART DATA UNAVAILABLE', transform=ax.transAxes,
                color=C['text_dim'], ha='center', va='center', fontsize=10)
        return

    n = len(df)
    _draw_candles(ax, df)

    # ── Y-range: center on the active execution zone ──────────────────────────
    # Priority: "show where the trade is happening" not "show every level."
    # Far TP targets live in the right panel; the chart stays tight and readable.
    all_p: list[float] = []
    for col in ('High', 'Low', 'Open', 'Close'):
        all_p.extend(df[col].dropna().tolist())

    candle_min, candle_max = min(all_p), max(all_p)
    candle_span = max(candle_max - candle_min, candle_min * 0.001)

    entry = signal.get('entry')
    stop  = signal.get('stop')

    if entry and stop and entry > 0 and stop > 0:
        # Center on execution zone midpoint; height = 3× the risk distance
        zone_mid    = (float(entry) + float(stop)) / 2
        risk_dist   = abs(float(entry) - float(stop))
        half_h      = max(risk_dist * 3.0, candle_span * 0.55)
        p_min       = min(zone_mid - half_h, candle_min)
        p_max       = max(zone_mid + half_h, candle_max)
    else:
        # No execution levels — show full candle range
        p_min, p_max = candle_min, candle_max

    margin = max((p_max - p_min) * 0.06, p_min * 0.001)

    x_label_pad = 7  # space right of last candle for level labels
    ax.set_xlim(-1, n + x_label_pad)
    ax.set_ylim(p_min - margin, p_max + margin)

    direction = signal.get('direction', 'LONG')
    entry = signal.get('entry')
    stop  = signal.get('stop')
    tp1   = signal.get('tp1')
    tp2   = signal.get('tp2')

    # Execution zone fill (demand/supply block)
    if entry and stop:
        lo, hi = sorted([entry, stop])
        inner_lo = lo + (hi - lo) * 0.15
        inner_hi = hi - (hi - lo) * 0.10
        zone_c = C['zone_demand'] if direction == 'LONG' else C['zone_supply']
        zone_l = 'DEMAND / OB' if direction == 'LONG' else 'SUPPLY / OB'
        _zone(ax, inner_lo, inner_hi, zone_c, zone_l, max(0, n - 22), n, alpha=0.45)

    # IB zone (subtle fill behind candles)
    ib_hi = signal.get('ib_high')
    ib_lo = signal.get('ib_low')
    if ib_hi and ib_lo and ib_hi != ib_lo:
        _zone(ax, ib_lo, ib_hi, C['ib_fill'], 'IB', 0, n, alpha=0.12)

    # ORB levels
    orb_h = signal.get('orb_high')
    orb_l = signal.get('orb_low')
    if orb_h:
        _hline(ax, orb_h, C['orb_high'], f'ORB H  {orb_h:,.1f}', 0, n, ls=':', lw=0.9)
    if orb_l:
        _hline(ax, orb_l, C['orb_low'],  f'ORB L  {orb_l:,.1f}', 0, n, ls=':', lw=0.9)

    # Execution lines  (drawn last so they're on top)
    if tp2:
        _hline(ax, tp2, C['tp2'],   f'TP2  {tp2:,.1f}',   0, n, ls='--', lw=0.9)
    if tp1:
        _hline(ax, tp1, C['tp1'],   f'TP1  {tp1:,.1f}',   0, n, ls='--', lw=1.2)
    if entry:
        _hline(ax, entry, C['entry'], f'ENTRY  {entry:,.1f}', 0, n, ls='-', lw=1.4)
    if stop:
        _hline(ax, stop,  C['sl'],    f'SL  {stop:,.1f}',     0, n, ls='-', lw=1.2)

    # Key price levels (from indicator)
    for lvl in signal.get('levels', []):
        try:
            lvl = float(lvl)
            if p_min - margin < lvl < p_max + margin:
                ax.hlines(lvl, 0, n, colors=C['text_dim'], linewidths=0.5,
                          linestyles=':', alpha=0.45, zorder=1)
        except Exception:
            pass

    # Grid
    ax.grid(True, color=C['grid'], linewidth=0.35, alpha=0.7, zorder=0)
    ax.minorticks_on()
    ax.tick_params(which='minor', length=0)

    # Ticks
    ax.tick_params(axis='both', colors=C['text_dim'], labelsize=6.0, length=3, width=0.4)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position('right')
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))

    # x-axis: sparse time labels
    n_ticks = min(10, n)
    step    = max(1, n // n_ticks)
    tpos, tlabels = [], []
    for pos in range(0, n, step):
        tpos.append(pos)
        try:
            idx = df.index[pos]
            tlabels.append(idx.strftime('%H:%M') if hasattr(idx, 'strftime') else '')
        except Exception:
            tlabels.append('')
    ax.set_xticks(tpos)
    ax.set_xticklabels(tlabels, fontsize=6.0, color=C['text_dim'])
