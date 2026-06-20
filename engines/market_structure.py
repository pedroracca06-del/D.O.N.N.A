"""
engines/market_structure.py — Market Structure Memory.

Gives NOVA awareness of the market context that existed before the current session.
Every session opens inside a structural context that was set by prior sessions.
Without this, NOVA is blind to 15+ hours of market activity before each open.

Levels computed per instrument (NQ and ES):
  onh                  Overnight High — Globex session high before 9:30 AM ET
  onl                  Overnight Low  — Globex session low  before 9:30 AM ET
  overnight_range      ONH - ONL in points
  open_vs_overnight    ABOVE_OVERNIGHT_RANGE / INSIDE / BELOW (at session open)
  price_vs_overnight   ABOVE / INSIDE / BELOW (current price, updates every cycle)
  daily_open           Today's regular session open price (9:30 AM bar)
  prev_close           Prior day's settlement close
  gap_signal           GAP_UP / GAP_DOWN / NO_GAP (open vs prior close)
  gap_pct              % gap between today's open and prior close
  pwh                  Prior week high (Mon-Fri of previous calendar week)
  pwl                  Prior week low
  monthly_open         First bar open of the current calendar month
  price_vs_pwh         ABOVE / AT / BELOW prior week high
  price_vs_pwl         ABOVE / AT / BELOW prior week low
  price_vs_monthly     ABOVE / AT / BELOW monthly open

Architecture:
  Structural levels (ONH/ONL, PWH/PWL, monthly_open, gap) are fetched via yfinance
  and cached in-memory for 30 minutes — heavy yfinance calls avoided every cycle.

  Current price vs structure comparisons are recomputed every cycle from risk_state
  (cheap dict reads, no network).

Observation only. No execution gates modified.
Refresh: called from process_finnhub_cycle() after cross_market compute.
Output: donna_market_structure.json
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from core.config import (
    MARKET_STRUCTURE_FILE as _MS_FILE,
    RISK_STATE_FILE       as _RISK_FILE,
)

_NY_TZ = ZoneInfo('America/New_York')

# ── In-memory cache for yfinance structural fetch (30-min TTL) ────────────────
_nq_cache:  dict  = {}
_es_cache:  dict  = {}
_cache_ts:  float = 0.0
_CACHE_TTL = 1800   # 30 minutes

# Gap threshold: open must differ from prior close by >= this % to qualify
_GAP_THRESHOLD_PCT = 0.20

# "AT level" tolerance: within 0.10% of the level counts as AT
_AT_TOLERANCE_PCT = 0.10


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


def _vs_level(price: float, level: Optional[float]) -> str:
    """Return ABOVE / AT / BELOW given current price vs a structural level."""
    if not price or not level:
        return 'UNKNOWN'
    tol = price * _AT_TOLERANCE_PCT / 100
    if abs(price - level) <= tol:
        return 'AT'
    return 'ABOVE' if price > level else 'BELOW'


def _price_vs_overnight(price: float, onh: Optional[float], onl: Optional[float]) -> str:
    if not price or not onh or not onl:
        return 'UNKNOWN'
    if price > onh:
        return 'ABOVE_OVERNIGHT_RANGE'
    if price < onl:
        return 'BELOW_OVERNIGHT_RANGE'
    return 'INSIDE_OVERNIGHT_RANGE'


# ── Structural level fetch (cached 30 min) ───────────────────────────────────

def _fetch_structure(yf_symbol: str, label: str) -> dict:
    """
    Fetch all structural levels for one instrument via yfinance.
    Returns a dict with all level fields. Empty dict on any failure.
    Tolerates pre-market (no session bars yet), weekends, holidays.
    """
    try:
        import yfinance as yf

        ticker  = yf.Ticker(yf_symbol)
        result: dict = {}
        now_ny  = datetime.now(_NY_TZ)
        today   = now_ny.date()

        # ── Intraday 5m bars — overnight range + daily open ──────────────────
        # Use period='2d' to ensure the overnight session is captured
        intra = ticker.history(period='2d', interval='5m')

        if intra is not None and not intra.empty:
            if intra.index.tz is None:
                intra.index = intra.index.tz_localize('UTC')
            intra.index = intra.index.tz_convert(_NY_TZ)

            yesterday = today - timedelta(days=1)

            # Overnight mask: yesterday 17:00+ AND today pre-09:30
            # CME Globex re-opens at ~18:00 ET after the daily settlement break.
            # Using 17:00 as the cutoff captures the full Globex overnight block.
            overnight_mask = (
                (
                    (intra.index.date == yesterday) &
                    (intra.index.hour >= 17)
                ) | (
                    (intra.index.date == today) & (
                        (intra.index.hour < 9) |
                        ((intra.index.hour == 9) & (intra.index.minute < 30))
                    )
                )
            )
            overnight_bars = intra[overnight_mask]

            onh = onl = None
            if not overnight_bars.empty:
                onh = round(float(overnight_bars['High'].max()), 2)
                onl = round(float(overnight_bars['Low'].min()), 2)
            result['onh'] = onh
            result['onl'] = onl
            result['overnight_range'] = (
                round(onh - onl, 2) if onh and onl else None
            )

            # Regular session bars (9:30+ today)
            session_mask = (
                (intra.index.date == today) & (
                    (intra.index.hour > 9) |
                    ((intra.index.hour == 9) & (intra.index.minute >= 30))
                )
            )
            session_bars = intra[session_mask]

            daily_open = None
            if not session_bars.empty:
                daily_open = round(float(session_bars['Open'].iloc[0]), 2)
            result['daily_open'] = daily_open

            # Open vs overnight (computed once at open, stays fixed)
            if onh and onl and daily_open:
                if daily_open > onh:
                    result['open_vs_overnight'] = 'ABOVE_OVERNIGHT_RANGE'
                elif daily_open < onl:
                    result['open_vs_overnight'] = 'BELOW_OVERNIGHT_RANGE'
                else:
                    result['open_vs_overnight'] = 'INSIDE_OVERNIGHT_RANGE'
            else:
                result['open_vs_overnight'] = 'UNKNOWN'

        # ── Daily bars — PWH/PWL, monthly open, gap ──────────────────────────
        daily = ticker.history(period='45d', interval='1d')

        if daily is not None and not daily.empty:
            if daily.index.tz is None:
                daily.index = daily.index.tz_localize('UTC')
            daily.index = daily.index.tz_convert(_NY_TZ)

            weekday = now_ny.weekday()   # 0=Mon … 6=Sun

            # Prior week: Monday through Friday of the previous calendar week.
            # this_monday = start of current week (Mon).
            # last_friday = this_monday - 3 days = Fri of prior week.
            # last_monday = this_monday - 7 days = Mon of prior week.
            this_monday  = today - timedelta(days=weekday)
            last_friday  = this_monday - timedelta(days=3)
            last_monday  = this_monday - timedelta(days=7)

            prior_week = daily[
                (daily.index.date >= last_monday) &
                (daily.index.date <= last_friday)
            ]
            pwh = pwl = None
            if not prior_week.empty:
                pwh = round(float(prior_week['High'].max()), 2)
                pwl = round(float(prior_week['Low'].min()), 2)
            result['pwh'] = pwh
            result['pwl'] = pwl

            # Monthly open: first daily bar of the current calendar month
            month_bars = daily[
                (daily.index.month == now_ny.month) &
                (daily.index.year  == now_ny.year)
            ]
            monthly_open = None
            if not month_bars.empty:
                monthly_open = round(float(month_bars['Open'].iloc[0]), 2)
            result['monthly_open'] = monthly_open

            # Gap: today's open vs prior day's close
            prev_bars  = daily[daily.index.date < today]
            prev_close = None
            if not prev_bars.empty:
                prev_close = round(float(prev_bars['Close'].iloc[-1]), 2)
            result['prev_close'] = prev_close

            daily_open = result.get('daily_open')
            if daily_open and prev_close and prev_close > 0:
                gap_pct = round((daily_open - prev_close) / prev_close * 100, 3)
                result['gap_pct'] = gap_pct
                if gap_pct >= _GAP_THRESHOLD_PCT:
                    result['gap_signal'] = 'GAP_UP'
                elif gap_pct <= -_GAP_THRESHOLD_PCT:
                    result['gap_signal'] = 'GAP_DOWN'
                else:
                    result['gap_signal'] = 'NO_GAP'
            else:
                result['gap_pct']   = 0.0
                result['gap_signal'] = 'UNKNOWN'

        return result

    except Exception as exc:
        print(f'[market_structure] _fetch_structure failed for {yf_symbol}: {exc}')
        return {}


# ── Narrative builder ─────────────────────────────────────────────────────────

def _build_narrative(nq: dict, es: dict, session_ctx: str) -> str:
    parts: list[str] = []

    # Gap
    nq_gap    = nq.get('gap_signal', 'UNKNOWN')
    nq_gap_pc = nq.get('gap_pct', 0.0)
    if nq_gap == 'GAP_UP':
        parts.append(f'NQ gapped up {nq_gap_pc:+.2f}% at open')
    elif nq_gap == 'GAP_DOWN':
        parts.append(f'NQ gapped down {nq_gap_pc:+.2f}% at open')

    # Open vs overnight
    ovn = nq.get('open_vs_overnight', 'UNKNOWN')
    onh = nq.get('onh')
    onl = nq.get('onl')
    if ovn == 'ABOVE_OVERNIGHT_RANGE' and onh:
        parts.append(f'NQ opened above overnight range (ONH {onh:.2f})')
    elif ovn == 'BELOW_OVERNIGHT_RANGE' and onl:
        parts.append(f'NQ opened below overnight range (ONL {onl:.2f})')

    # Current price vs overnight
    pvo = nq.get('price_vs_overnight', 'UNKNOWN')
    if pvo == 'ABOVE_OVERNIGHT_RANGE' and onh:
        parts.append(f'NQ now above ONH {onh:.2f}')
    elif pvo == 'BELOW_OVERNIGHT_RANGE' and onl:
        parts.append(f'NQ now below ONL {onl:.2f}')

    # Price vs PWH/PWL
    pwh = nq.get('pwh')
    pwl = nq.get('pwl')
    vs_pwh = nq.get('price_vs_pwh', 'UNKNOWN')
    vs_pwl = nq.get('price_vs_pwl', 'UNKNOWN')
    if vs_pwh == 'ABOVE' and pwh:
        parts.append(f'NQ above prior week high ({pwh:.2f})')
    elif vs_pwh == 'AT' and pwh:
        parts.append(f'NQ testing prior week high ({pwh:.2f})')
    elif vs_pwl == 'BELOW' and pwl:
        parts.append(f'NQ below prior week low ({pwl:.2f})')
    elif vs_pwl == 'AT' and pwl:
        parts.append(f'NQ testing prior week low ({pwl:.2f})')

    # Price vs monthly open
    mo      = nq.get('monthly_open')
    vs_mo   = nq.get('price_vs_monthly', 'UNKNOWN')
    if vs_mo == 'ABOVE' and mo:
        parts.append(f'NQ above monthly open ({mo:.2f})')
    elif vs_mo == 'BELOW' and mo:
        parts.append(f'NQ below monthly open ({mo:.2f})')
    elif vs_mo == 'AT' and mo:
        parts.append(f'NQ at monthly open ({mo:.2f})')

    if session_ctx == 'PRE_MARKET':
        onh_str = f'{onh:.2f}' if onh else '?'
        onl_str = f'{onl:.2f}' if onl else '?'
        parts.append(
            f'Overnight range building: ONH={onh_str} ONL={onl_str} '
            f'(open not yet set)'
        )

    if not parts:
        return 'Market structure levels available — no notable structural context triggered.'

    return ' | '.join(parts)


# ── Main compute ──────────────────────────────────────────────────────────────

def compute_market_structure() -> dict:
    """
    Compute market structure memory. Called from process_finnhub_cycle().

    Structural levels (ONH/ONL, PWH/PWL, monthly_open, gap) use a 30-minute
    in-memory cache to avoid redundant yfinance network calls each cycle.

    Current price vs structure comparisons recompute every cycle from risk_state
    (cheap dict read, no network call).

    Never raises — returns a neutral/empty state on any failure.
    """
    global _nq_cache, _es_cache, _cache_ts

    try:
        now_ts     = time.time()
        cache_miss = (now_ts - _cache_ts) > _CACHE_TTL

        if cache_miss:
            nq_levels = _fetch_structure('NQ=F', 'NQ')
            es_levels = _fetch_structure('ES=F', 'ES')
            # Only advance cache timestamp when at least one fetch succeeded
            if nq_levels or es_levels:
                _nq_cache = nq_levels
                _es_cache = es_levels
                _cache_ts = now_ts
        else:
            nq_levels = _nq_cache
            es_levels = _es_cache

        # Current prices from risk_state (always fresh, no network)
        risk     = _read_json(_RISK_FILE)
        snapshot = risk.get('market_snapshot', {})
        nq_price = _safe((snapshot.get('NQ') or {}).get('last'))
        es_price = _safe((snapshot.get('ES') or {}).get('last'))

        # Build per-instrument state dicts with current price comparisons
        nq = dict(nq_levels) if nq_levels else {}
        es = dict(es_levels) if es_levels else {}

        for struct, price in ((nq, nq_price), (es, es_price)):
            struct['current_price'] = price if price else None
            if price:
                struct['price_vs_onh']     = _vs_level(price, struct.get('onh'))
                struct['price_vs_onl']     = _vs_level(price, struct.get('onl'))
                struct['price_vs_overnight'] = _price_vs_overnight(
                    price, struct.get('onh'), struct.get('onl')
                )
                struct['price_vs_pwh']     = _vs_level(price, struct.get('pwh'))
                struct['price_vs_pwl']     = _vs_level(price, struct.get('pwl'))
                struct['price_vs_monthly'] = _vs_level(price, struct.get('monthly_open'))

        # Session context
        now_ny = datetime.now(_NY_TZ)
        mins   = now_ny.hour * 60 + now_ny.minute
        if mins < 9 * 60 + 30:
            session_ctx = 'PRE_MARKET'
        elif mins < 16 * 60:
            session_ctx = 'REGULAR_SESSION'
        else:
            session_ctx = 'POST_MARKET'

        narrative = _build_narrative(nq, es, session_ctx)

        state = {
            'nq':            nq,
            'es':            es,
            'session_ctx':   session_ctx,
            'narrative':     narrative,
            'levels_cached': not cache_miss,
            'last_updated':  _utc_iso(),
        }

        _MS_FILE.write_text(json.dumps(state, indent=2, default=str), encoding='utf-8')

        nq_gap = nq.get('gap_signal', 'N/A')
        nq_ovn = nq.get('price_vs_overnight', 'N/A')
        print(
            f'[market_structure] {session_ctx} | '
            f'NQ gap={nq_gap} | vs_overnight={nq_ovn} | '
            f'PWH={nq.get("pwh")} PWL={nq.get("pwl")} | '
            f'monthly_open={nq.get("monthly_open")} | '
            f'cached={not cache_miss}'
        )
        return state

    except Exception as exc:
        print(f'[market_structure] compute error: {exc}')
        return _neutral_state()


def _neutral_state() -> dict:
    empty = {
        'onh': None, 'onl': None, 'overnight_range': None,
        'open_vs_overnight': 'UNKNOWN', 'price_vs_overnight': 'UNKNOWN',
        'daily_open': None, 'prev_close': None,
        'gap_signal': 'UNKNOWN', 'gap_pct': 0.0,
        'pwh': None, 'pwl': None,
        'monthly_open': None,
        'price_vs_onh': 'UNKNOWN', 'price_vs_onl': 'UNKNOWN',
        'price_vs_pwh': 'UNKNOWN', 'price_vs_pwl': 'UNKNOWN',
        'price_vs_monthly': 'UNKNOWN',
        'current_price': None,
    }
    return {
        'nq': empty.copy(), 'es': empty.copy(),
        'session_ctx': 'UNKNOWN',
        'narrative': 'Market structure data unavailable.',
        'levels_cached': False,
        'last_updated': _utc_iso(),
    }


# ── Load / format ─────────────────────────────────────────────────────────────

def load_market_structure() -> dict:
    """Load cached market structure state from file. No network calls."""
    data = _read_json(_MS_FILE)
    return data if data else _neutral_state()


def format_for_prompt(ms: dict) -> str:
    """
    Multi-line market structure block for Claude evaluation prompt.
    Placed after Cross-Market Intelligence so Claude has full structural
    context before evaluating any setup.
    """
    nq = ms.get('nq', {})
    es = ms.get('es', {})

    if not nq and not es:
        return ''

    def _fmt_level(v) -> str:
        if v is None:
            return '?'
        try:
            return f'{float(v):.2f}'
        except Exception:
            return str(v)

    session_ctx = ms.get('session_ctx', 'UNKNOWN')

    lines = [
        '=== MARKET STRUCTURE MEMORY (context from prior sessions) ===',
    ]

    for label, struct in (('NQ', nq), ('ES', es)):
        onh      = struct.get('onh')
        onl      = struct.get('onl')
        ovn_rng  = struct.get('overnight_range')
        open_ovn = struct.get('open_vs_overnight', 'UNKNOWN')
        pvt_ovn  = struct.get('price_vs_overnight', 'UNKNOWN')
        gap_sig  = struct.get('gap_signal', 'UNKNOWN')
        gap_pct  = struct.get('gap_pct', 0.0)
        pwh      = struct.get('pwh')
        pwl      = struct.get('pwl')
        mo       = struct.get('monthly_open')
        vs_pwh   = struct.get('price_vs_pwh', '?')
        vs_pwl   = struct.get('price_vs_pwl', '?')
        vs_mo    = struct.get('price_vs_monthly', '?')
        price    = struct.get('current_price')

        price_str = f'{price:.2f}' if price else '?'

        lines.append(f'{label} (price={price_str}):')

        if onh and onl:
            lines.append(
                f'  Overnight:    ONH={_fmt_level(onh)}  ONL={_fmt_level(onl)}'
                f'  range={_fmt_level(ovn_rng)}pts'
                f'  | open_vs_ovn={open_ovn}  now_vs_ovn={pvt_ovn}'
            )
        else:
            lines.append(f'  Overnight:    data unavailable ({session_ctx})')

        if gap_sig not in ('UNKNOWN', None):
            lines.append(f'  Gap:          {gap_sig} ({gap_pct:+.2f}%)')

        if pwh and pwl:
            lines.append(
                f'  Prior week:   PWH={_fmt_level(pwh)}  PWL={_fmt_level(pwl)}'
                f'  | price vs PWH={vs_pwh}  price vs PWL={vs_pwl}'
            )

        if mo:
            lines.append(
                f'  Monthly open: {_fmt_level(mo)}'
                f'  | price vs monthly={vs_mo}'
            )

    lines.append(f'Summary: {ms.get("narrative", "")}')
    lines.append('=== END MARKET STRUCTURE MEMORY ===')
    return '\n'.join(lines)


def format_for_assistant(ms: dict) -> str:
    """Compact single-line format for assistant session context."""
    nq = ms.get('nq', {})

    gap    = nq.get('gap_signal', '?')
    ovn    = nq.get('price_vs_overnight', '?')
    vs_pwh = nq.get('price_vs_pwh', '?')
    vs_pwl = nq.get('price_vs_pwl', '?')
    vs_mo  = nq.get('price_vs_monthly', '?')
    onh    = nq.get('onh')
    onl    = nq.get('onl')
    pwh    = nq.get('pwh')
    pwl    = nq.get('pwl')
    mo     = nq.get('monthly_open')

    onh_str = f'{onh:.0f}' if onh else '?'
    onl_str = f'{onl:.0f}' if onl else '?'
    pwh_str = f'{pwh:.0f}' if pwh else '?'
    pwl_str = f'{pwl:.0f}' if pwl else '?'
    mo_str  = f'{mo:.0f}'  if mo  else '?'

    return (
        f'STRUCTURE: gap={gap} | ovn={ovn}(ONH={onh_str}/ONL={onl_str}) | '
        f'vs_PWH={vs_pwh}({pwh_str}) vs_PWL={vs_pwl}({pwl_str}) | '
        f'vs_monthly={vs_mo}({mo_str})'
    )
