"""card_compositor.py — NOVA execution card: full card assembly.

Assembles the complete execution card PNG from:
  - OHLC candle chart (card_renderer)
  - Right panel  (setup summary / trade plan / AI reasoning)
  - Top bar      (instrument | TF | setup | grade | session | time)
  - Bottom bar   (risk tier | daily P&L | trades | cooldown | governance)

Output: 1200 × 675px PNG — Discord-native, Render-compatible, no browser.

Entry point: generate_card(alert, signal_raw) → Path | None
"""
from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch

from delivery.card_renderer import (
    C, GRADE_COLOR,
    fetch_ohlc, synthetic_ohlc, render_chart_axes,
)

# ── Output directory ───────────────────────────────────────────────────────────
_BASE   = Path(__file__).parent.parent
_SS_DIR = _BASE / 'mcp' / 'tradingview' / 'screenshots'
_SS_DIR.mkdir(parents=True, exist_ok=True)

# Card dimensions
_W, _H, _DPI = 12.0, 6.75, 100   # → 1200 × 675 px

# ── Fonts ──────────────────────────────────────────────────────────────────────
_FONT_TITLE  = {'family': 'monospace', 'size': 7.5, 'weight': 'bold', 'color': C['text_primary']}
_FONT_LABEL  = {'family': 'monospace', 'size': 6.2, 'color': C['text_dim']}
_FONT_VALUE  = {'family': 'monospace', 'size': 7.0, 'weight': 'bold', 'color': C['text_primary']}
_FONT_ACCENT = {'family': 'monospace', 'size': 7.0, 'weight': 'bold', 'color': C['text_accent']}


# ── Card data model ────────────────────────────────────────────────────────────

@dataclass
class CardData:
    # Identity
    symbol:         str = 'MES'
    timeframe:      str = '5M'
    setup_type:     str = 'PROS_LONG'
    direction:      str = 'LONG'
    grade:          str = '?'
    session:        str = 'NY_OPEN'
    session_quality:str = '?'
    timestamp:      str = ''
    execution_mode: str = 'PAPER'

    # Market context
    daily_bias:     str = '?'
    htf_4h_bias:    str = '?'
    ib_draw:        str = '?'
    nova_state:     str = ''
    nova_conf:      str = ''
    regime:         str = ''
    vix:            float = 0.0

    # Price levels (floats; 0.0 = not available)
    entry:  float = 0.0
    stop:   float = 0.0
    tp1:    float = 0.0
    tp2:    float = 0.0
    rr:     str   = ''

    # ORB / IB structure
    orb_high: float = 0.0
    orb_low:  float = 0.0
    ib_high:  float = 0.0
    ib_low:   float = 0.0
    levels:   list  = field(default_factory=list)

    # OHLC anchor (for synthetic fallback)
    current_price: float = 0.0
    high_30:       float = 0.0
    low_30:        float = 0.0

    # Text
    action:         str = ''
    notes:          str = ''
    reasoning_bullets: list = field(default_factory=list)

    # Governance / session state
    trades_today:       int   = 0
    max_trades:         int   = 5
    daily_pnl_pct:      float = 0.0
    daily_loss_limit:   float = 2.0
    cooldown_min:       int   = 15
    macro_lock:         bool  = False
    red_folder:         bool  = False
    account_equity:     str   = ''

    @property
    def grade_color(self) -> str:
        return GRADE_COLOR.get(self.grade.upper(), '#aaaaaa')

    @property
    def direction_color(self) -> str:
        return C['up'] if 'LONG' in self.direction.upper() else C['down']

    @property
    def risk_pts(self) -> str:
        if self.entry and self.stop:
            return f'{abs(self.entry - self.stop):,.1f} pts'
        return '—'

    @property
    def reward_pts(self) -> str:
        if self.entry and self.tp1:
            return f'{abs(self.tp1 - self.entry):,.1f} pts'
        return '—'

    def signal_dict(self) -> dict:
        return {
            'entry':     self.entry or None,
            'stop':      self.stop  or None,
            'tp1':       self.tp1   or None,
            'tp2':       self.tp2   or None,
            'direction': self.direction,
            'orb_high':  self.orb_high or None,
            'orb_low':   self.orb_low  or None,
            'ib_high':   self.ib_high  or None,
            'ib_low':    self.ib_low   or None,
            'levels':    self.levels,
        }


# ── Factory ───────────────────────────────────────────────────────────────────

def _safe_float(val) -> float:
    if not val:
        return 0.0
    try:
        cleaned = re.sub(r'[^\d\.\-]', '', str(val))
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0


def _extract_bullets(notes: str, action: str, n: int = 4) -> list[str]:
    """Turn notes + action into ≤n short bullet strings."""
    bullets: list[str] = []

    # Action first (usually most concise)
    if action:
        first = action.split('.')[0].strip()
        if len(first) > 10:
            bullets.append(first[:80])

    # Split notes into sentences
    if notes:
        sentences = re.split(r'(?<=[.!?])\s+', notes.strip())
        for s in sentences:
            s = s.strip().rstrip('.')
            if len(s) > 15 and not s.startswith('Grade') and len(bullets) < n:
                bullets.append(s[:80])

    return bullets[:n] if bullets else ['Monitor for confirmation signal']


def from_signal(signal_raw: dict, alert_type: str = 'HEADS_UP') -> CardData:
    """Build CardData directly from a signal log entry dict."""
    try:
        from core.state_engine import DonnaStateEngine
        _dse   = DonnaStateEngine()
        _state = _dse.get_state()
    except Exception:
        _state = {}

    try:
        from core.config import now_ny
        ts = now_ny().strftime('%b %d, %Y  %I:%M %p ET')
    except Exception:
        ts = datetime.now().strftime('%b %d, %Y  %I:%M %p ET')

    notes  = signal_raw.get('notes',  '')
    action = signal_raw.get('action', '')
    symbol = signal_raw.get('symbol', 'MES')

    entry = _safe_float(signal_raw.get('entry_zone') or signal_raw.get('entry'))
    stop  = _safe_float(signal_raw.get('stop'))
    tp1   = _safe_float(signal_raw.get('tp1'))

    # TP2 only if explicitly provided — no auto-generation
    tp2 = _safe_float(signal_raw.get('tp2', 0))

    current = _safe_float(signal_raw.get('price', 0))
    h30     = _safe_float(signal_raw.get('high_30', current * 1.001))
    l30     = _safe_float(signal_raw.get('low_30',  current * 0.999))

    orb_high = _safe_float(signal_raw.get('orb_high'))
    orb_low  = _safe_float(signal_raw.get('orb_low'))
    ib_high  = _safe_float(signal_raw.get('ib_high'))
    ib_low   = _safe_float(signal_raw.get('ib_low'))
    levels   = [_safe_float(v) for v in signal_raw.get('levels', []) if v]

    # If no ORB from signal, try to use IB range as visual guide
    if not orb_high and ib_high:
        orb_high = ib_high
    if not orb_low and ib_low:
        orb_low = ib_low

    # Regime → market state label
    regime_raw = signal_raw.get('regime', '')
    regime_map = {
        'TRENDING_UP': 'TRENDING ↑', 'TRENDING_DOWN': 'TRENDING ↓',
        'RANGING': 'RANGING', 'MIXED': 'MIXED', 'VOLATILE': 'VOLATILE',
    }
    market_state = regime_map.get(regime_raw.upper(), regime_raw or '—')

    rr  = signal_raw.get('rr', '')
    if not rr and entry and stop and tp1:
        risk   = abs(entry - stop)
        reward = abs(tp1 - entry)
        if risk > 0:
            rr = f'1 : {reward/risk:.1f}'

    exec_mode = 'LIVE' if _state.get('trade_permission', False) else 'PAPER'

    return CardData(
        symbol          = symbol,
        timeframe       = signal_raw.get('timeframe', '5M') or '5M',
        setup_type      = signal_raw.get('setup_type', signal_raw.get('pre_setup', '?')),
        direction       = signal_raw.get('direction', 'N/A'),
        grade           = signal_raw.get('grade', '?'),
        session         = signal_raw.get('session', 'NY_OPEN'),
        session_quality = signal_raw.get('session_quality', '?'),
        timestamp       = ts,
        execution_mode  = exec_mode,
        daily_bias      = signal_raw.get('daily_bias', '?'),
        htf_4h_bias     = signal_raw.get('htf_4h_bias', '?'),
        ib_draw         = signal_raw.get('ib_draw', '?'),
        nova_state      = signal_raw.get('nova_state', ''),
        nova_conf       = signal_raw.get('nova_conf', ''),
        regime          = market_state,
        vix             = _safe_float(signal_raw.get('vix', 0)),
        entry           = entry,
        stop            = stop,
        tp1             = tp1,
        tp2             = tp2,
        rr              = rr,
        orb_high        = orb_high,
        orb_low         = orb_low,
        ib_high         = ib_high,
        ib_low          = ib_low,
        levels          = levels,
        current_price   = current,
        high_30         = h30,
        low_30          = l30,
        action          = action,
        notes           = notes,
        reasoning_bullets = _extract_bullets(notes, action),
        trades_today    = _state.get('trades_taken', 0),
        max_trades      = 2,
        daily_pnl_pct   = _state.get('cumulative_risk_today', 0.0),
        daily_loss_limit= 2.0,
        cooldown_min    = 15,
        macro_lock      = bool(_state.get('macro_lock')),
        red_folder      = bool(_state.get('red_folder_active') or signal_raw.get('red_folder_week')),
        account_equity  = '',
    )


# ── Section renderers ──────────────────────────────────────────────────────────

def _clear_axes(ax, bg: str = C['bg']) -> None:
    ax.set_facecolor(bg)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def _render_top_bar(ax, d: CardData) -> None:
    _clear_axes(ax, C['bg'])

    # Left: NOVA logo + symbol
    ax.text(0.012, 0.55, '▶ NOVA', fontsize=8.5, fontweight='bold',
            color=C['nova_blue'] if False else '#0080ff',
            transform=ax.transAxes, va='center', family='monospace')

    ax.text(0.072, 0.55, 'EXECUTION PLAN',
            fontsize=6.8, fontweight='bold', color=C['text_dim'],
            transform=ax.transAxes, va='center', family='monospace',
            alpha=0.7)

    # Separator
    ax.axvline(0.155, color=C['separator'], linewidth=0.6, alpha=0.7)

    # Instrument chips
    chips = [
        (d.symbol,      C['text_primary'], True),
        (f'| {d.timeframe}', C['text_dim'],   False),
        (f'| {d.setup_type.replace("_", " ")}', C['text_accent'], True),
    ]
    x = 0.165
    for txt, col, bold in chips:
        ax.text(x, 0.55, txt, fontsize=7.2, fontweight='bold' if bold else 'normal',
                color=col, transform=ax.transAxes, va='center', family='monospace')
        x += len(txt) * 0.0062 + 0.008

    # Right side: GRADE + session + timestamp
    ax.text(0.995, 0.55,
            f'{d.timestamp}   ·   {d.session}',
            fontsize=6.2, color=C['text_dim'], fontweight='normal',
            transform=ax.transAxes, va='center', ha='right', family='monospace')

    # Grade badge
    ax.text(0.870, 0.55, f'GRADE  {d.grade}',
            fontsize=7.5, fontweight='bold', color=d.grade_color,
            transform=ax.transAxes, va='center', ha='right', family='monospace',
            bbox=dict(boxstyle='round,pad=0.25', facecolor='#0a0c10',
                      edgecolor=d.grade_color, linewidth=0.8, alpha=0.95))

    # Bottom border line
    ax.axhline(0.02, color=C['border'], linewidth=0.5)


def _render_panel(ax, d: CardData) -> None:
    _clear_axes(ax, C['panel_bg'])
    ax.axvline(0.0, color=C['border'], linewidth=0.5)

    x0   = 0.07   # left margin
    lh   = 0.048  # row line height (tighter than before)
    xval = 0.50   # value column x offset

    def sep(y: float) -> None:
        ax.axhline(y, xmin=0.04, color=C['separator'], linewidth=0.35)

    def header(y: float, title: str) -> None:
        ax.text(x0, y, title, fontsize=5.8, fontweight='bold',
                color=C['text_dim'], transform=ax.transAxes, va='top',
                family='monospace', alpha=0.70)

    def row(y: float, label: str, value: str, val_color: str = None) -> None:
        if y < 0.03:
            return
        ax.text(x0, y, f'{label:<13}', fontsize=5.8, color=C['text_dim'],
                transform=ax.transAxes, va='top', family='monospace')
        ax.text(x0 + xval, y, value, fontsize=6.3, fontweight='bold',
                color=val_color or C['text_primary'],
                transform=ax.transAxes, va='top', family='monospace')

    dir_color = d.direction_color

    # ── SETUP SUMMARY ────────────────────────────────────────────── y ≈ 0.97
    y = 0.97
    header(y, 'SETUP SUMMARY')
    y -= 0.052

    row(y, 'Setup',     d.setup_type.replace('_', ' '));           y -= lh
    row(y, 'Direction', d.direction, dir_color);                    y -= lh
    row(y, 'Session',   d.session.replace('_', ' '));              y -= lh
    row(y, 'Mkt State', d.regime or '—');                          y -= lh
    row(y, 'Bias',      d.daily_bias or '—',
        dir_color if d.daily_bias and d.daily_bias != '?' else C['text_dim']); y -= lh
    row(y, 'NOVA',      d.nova_state or '—',
        C['text_accent'] if d.nova_state else C['text_dim']);      y -= lh

    # ── TRADE PLAN ──────────────────────────────────────────────── y ≈ 0.67
    y -= 0.018
    sep(y + 0.020)
    header(y, 'TRADE PLAN')
    y -= 0.052

    row(y, 'Entry',
        f'{d.entry:,.1f}' if d.entry else '—',
        C['entry'] if d.entry else C['text_dim']);                  y -= lh
    row(y, 'Stop',
        f'{d.stop:,.1f}' if d.stop else '—',
        C['sl'] if d.stop else C['text_dim']);                      y -= lh
    row(y, 'TP1',
        f'{d.tp1:,.1f}' if d.tp1 else '—',
        C['tp1'] if d.tp1 else C['text_dim']);                      y -= lh
    row(y, 'Risk',    d.risk_pts);                                  y -= lh
    row(y, 'Reward',  d.reward_pts);                                y -= lh
    row(y, 'R : R',   d.rr or '—',
        C['up'] if d.rr else C['text_dim']);                        y -= lh

    # ── AI REASONING ─────────────────────────────────────────────── y ≈ 0.34
    y -= 0.018
    sep(y + 0.020)
    header(y, 'AI REASONING')
    y -= 0.050

    bullet_lh = 0.042
    for bullet in d.reasoning_bullets[:4]:
        if y < 0.05:
            break
        wrapped = textwrap.wrap(bullet, width=38)
        for i, line in enumerate(wrapped[:2]):
            if y < 0.03:
                break
            prefix = '▸  ' if i == 0 else '    '
            ax.text(x0, y, prefix + line, fontsize=5.5, color=C['text_primary'],
                    transform=ax.transAxes, va='top', family='monospace', alpha=0.90)
            y -= bullet_lh
        y -= 0.008

    # ── GOVERNANCE — subtle operational marker at panel bottom ───────
    if y > 0.08:
        sep(y + 0.010)
        macro_ok   = not d.macro_lock
        folder_ok  = not d.red_folder
        trades_ok  = d.trades_today < d.max_trades
        gov_all_ok = macro_ok and folder_ok and trades_ok
        gov_dot    = '●' if gov_all_ok else '○'
        gov_txt    = 'GOVERNANCE  CLEAR' if gov_all_ok else 'GOVERNANCE  CAUTION'
        gov_color  = C['up'] if gov_all_ok else C['text_dim']
        ax.text(x0, y - 0.01, gov_dot, fontsize=5.5, color=gov_color,
                transform=ax.transAxes, va='top', family='monospace', alpha=0.55)
        ax.text(x0 + 0.12, y - 0.01, gov_txt, fontsize=5.2, color=C['text_dim'],
                transform=ax.transAxes, va='top', family='monospace', alpha=0.50)


def _render_bottom_bar(ax, d: CardData) -> None:
    _clear_axes(ax, C['bg'])
    ax.axhline(0.95, color=C['border'], linewidth=0.5)

    # Build chips: [(label, value, value_color), ...]
    pnl_color = C['up'] if d.daily_pnl_pct >= 0 else C['down']
    chips = [
        ('RISK TIER',    'STANDARD (2%)',        C['text_primary']),
        ('DAILY P&L',    f'{d.daily_pnl_pct:+.2f}%  /  {d.daily_loss_limit:.0f}%', pnl_color),
        ('TRADES',       f'{d.trades_today} / {d.max_trades}',  C['text_primary']),
        ('COOLDOWN',     f'{d.cooldown_min} MIN', C['text_dim']),
        ('MODE',         d.execution_mode,
                         C['tp1'] if d.execution_mode == 'LIVE' else C['text_dim']),
        ('SESSION Q',    d.session_quality,
                         GRADE_COLOR.get(d.session_quality, C['text_dim'])),
    ]
    if d.account_equity:
        chips.append(('EQUITY', d.account_equity, C['text_primary']))

    n_chips = len(chips)
    spacing = 1.0 / n_chips
    for i, (label, value, val_col) in enumerate(chips):
        x = spacing * i + spacing * 0.5
        ax.text(x, 0.70, label, fontsize=5.2, color=C['text_dim'],
                transform=ax.transAxes, va='center', ha='center', family='monospace')
        ax.text(x, 0.28, value, fontsize=6.2, fontweight='bold', color=val_col,
                transform=ax.transAxes, va='center', ha='center', family='monospace')

        if i > 0:
            ax.axvline(spacing * i, color=C['separator'], linewidth=0.4, alpha=0.6)


# ── Main assembly ──────────────────────────────────────────────────────────────

def render_card(d: CardData, output_path: Optional[Path] = None) -> Optional[Path]:
    """
    Assemble the full execution card PNG.
    Returns the Path to the saved PNG, or None on failure.
    """
    if output_path is None:
        ts  = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
        output_path = _SS_DIR / f'nova_card_{d.symbol}_{ts}.png'

    try:
        fig = plt.figure(figsize=(_W, _H), dpi=_DPI, facecolor=C['bg'])

        gs = gridspec.GridSpec(
            3, 2,
            figure=fig,
            height_ratios=[0.075, 0.845, 0.080],
            width_ratios=[0.635, 0.365],
            hspace=0.0,
            wspace=0.0,
        )

        ax_top    = fig.add_subplot(gs[0, :])
        ax_chart  = fig.add_subplot(gs[1, 0])
        ax_panel  = fig.add_subplot(gs[1, 1])
        ax_bottom = fig.add_subplot(gs[2, :])

        # Top bar
        _render_top_bar(ax_top, d)

        # Chart — fetch OHLC then render; both may return None if price is unavailable
        df = fetch_ohlc(d.symbol)
        if df is None or (hasattr(df, 'empty') and df.empty):
            df = synthetic_ohlc(d.current_price, d.high_30, d.low_30)
        # df may still be None — render_chart_axes handles that gracefully

        render_chart_axes(ax_chart, df, d.signal_dict())

        # Right panel
        _render_panel(ax_panel, d)

        # Bottom bar
        _render_bottom_bar(ax_bottom, d)

        plt.savefig(output_path, dpi=_DPI,
                    facecolor=C['bg'], edgecolor='none')
        plt.close(fig)
        return output_path

    except Exception as exc:
        try:
            plt.close('all')
        except Exception:
            pass
        print(f'[card_compositor] render failed: {exc}')
        return None


def generate_card(signal_raw: dict, alert_type: str = 'HEADS_UP') -> Optional[Path]:
    """
    Convenience entry point: takes a raw signal dict, builds CardData,
    renders the card, returns the PNG path.

    Usage in alert_engine.py:
        from delivery.card_compositor import generate_card
        photo = generate_card(signal_raw, data.alert_type)
    """
    card = from_signal(signal_raw, alert_type)
    return render_card(card)
