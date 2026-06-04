# ============================================================
# donna_news.py — DONNA v5.0 Live News & Risk State Engine
# Replaces the stub process_news_guard_cycle() in main.py
#
# DROP THIS FILE into your project root alongside main.py
# It is imported automatically by the existing news_loop()
# ============================================================

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import os
import re
import requests

# ── paths & config ──────────────────────────────────────────
BASE_DIR = Path(__file__).parent
RISK_STATE_FILE = BASE_DIR / 'data' / 'donna_risk_state.json'
NY_TZ = ZoneInfo('America/New_York')

FINNHUB_API_KEY   = os.getenv('FINNHUB_API_KEY', '').strip()
FMP_API_KEY       = os.getenv('FMP_API_KEY', '').strip()
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '').strip()
GROK_API_KEY      = os.getenv('GROK_API_KEY', '').strip()

# ── helpers ──────────────────────────────────────────────────
def _now_ny():
    return datetime.now(NY_TZ)

def _utc_iso():
    return datetime.now(timezone.utc).isoformat()

def _safe_get(url, params=None, timeout=18):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'[donna_news] GET {url} failed: {e}')
        return None

def _read_risk():
    try:
        if RISK_STATE_FILE.exists():
            with open(RISK_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _write_risk(state: dict):
    state['last_updated'] = _utc_iso()
    with open(RISK_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

# ── keyword scoring ──────────────────────────────────────────
HIGH_MACRO = [
    'fed ', 'federal reserve', 'fomc', 'rate decision', 'rate hike', 'rate cut',
    'cpi ', 'pce ', 'inflation data', 'jobs report', 'nonfarm', 'payroll',
    'gdp ', 'recession', 'powell', 'treasury yield', 'debt ceiling',
    'banking crisis', 'systemic', 'liquidity crisis',
]
HIGH_HEADLINE = [
    'war', 'attack', 'explosion', 'sanction', 'iran', 'russia', 'china tariff',
    'emergency', 'crash', 'circuit breaker', 'halt', 'collapse', 'default',
    'mass layoff', 'earnings miss', 'guidance cut', 'fda reject',
]
HIGH_MARKET = [
    'nvda', 'nvidia', 'microsoft', 'msft', 'apple', 'aapl', 'amazon', 'amzn',
    'meta ', 'alphabet', 'tesla', 'tsla', 'amd ', 'advanced micro',
    'earnings beat', 'earnings miss', 'buyback', 'acquisition', 'merger',
    'ipo ', 'downgrade', 'upgrade', 'price target',
]
MEDIUM_MACRO = [
    'inflation', 'interest rate', 'bond yield', 'dollar', 'dxy', 'crude oil',
    'oil price', 'gold price', 'consumer sentiment', 'retail sales',
    'housing', 'jobless claims', 'manufacturing',
]

def _score_text(text: str) -> tuple[str, str, str]:
    """
    Returns (macro_risk, headline_risk, market_risk) each as 'low'|'medium'|'high'
    based on keyword scoring across headlines.
    """
    t = text.lower()

    macro_hits = sum(1 for k in HIGH_MACRO if k in t)
    if macro_hits >= 3:
        macro = 'high'
    elif macro_hits >= 1:
        macro = 'medium'
    elif any(k in t for k in MEDIUM_MACRO):
        macro = 'medium'
    else:
        macro = 'low'

    headline = 'low'
    if any(k in t for k in HIGH_HEADLINE):
        headline = 'high'
    elif any(k in t for k in ['geopolit', 'tariff', 'shutdown', 'protest', 'political']):
        headline = 'medium'

    market = 'low'
    if any(k in t for k in HIGH_MARKET):
        market = 'high'
    elif any(k in t for k in ['sector', 'rally', 'selloff', 'sell-off', 'rotation']):
        market = 'medium'

    return macro, headline, market

def _severity_label(macro: str, headline: str, market: str) -> str:
    levels = {'high': 3, 'medium': 2, 'low': 1}
    top = max(levels[macro], levels[headline], levels[market])
    return {3: 'HIGH', 2: 'MEDIUM', 1: 'LOW'}[top]

def _build_warnings(macro: str, headline: str, market: str,
                    next_event: str, event_phase: str) -> list[str]:
    warnings = []
    if macro == 'high':
        warnings.append(f'Macro event risk is elevated — {next_event}')
    elif macro == 'medium':
        warnings.append('Macro timing matters — respect event windows')

    if headline == 'high':
        warnings.append('Breaking headline risk is active — price action may be reactive')
    if market == 'high':
        warnings.append('Company catalyst pressure is elevated — leadership names in play')

    phase = str(event_phase).upper()
    if phase in ('LIVE', 'IMMINENT'):
        warnings.append(f'Event is LIVE or IMMINENT — reduce conviction, respect reaction')
    elif phase == 'APPROACHING':
        warnings.append('Event approaching — do not confuse pre-event noise for conviction')

    if not warnings:
        warnings.append('No elevated risk signals — standard session caution applies')

    return warnings[:4]

def _build_guidance(macro: str, headline: str, market: str,
                    top_headline: str, next_event: str) -> str:
    if macro == 'high':
        return (f'Macro risk is high. {next_event} is the main threat. '
                'Treat price action near event windows as potentially reactive, not conviction-driven.')
    if headline == 'high':
        return ('Breaking headline risk is active. '
                'Wait for the initial reaction to settle before reading direction as real.')
    if market == 'high':
        return ('Company catalysts are driving the tape. '
                'Focus on leadership names and watch whether moves broaden or stay contained.')
    return ('Balanced conditions. No single dominant threat. '
            'Respect session structure and leadership confirmation before adding size.')

# ── data sources ─────────────────────────────────────────────
def _fetch_finnhub_news() -> list[dict]:
    if not FINNHUB_API_KEY:
        return []
    data = _safe_get(
        'https://finnhub.io/api/v1/news',
        {'category': 'general', 'token': FINNHUB_API_KEY}
    )
    if not isinstance(data, list):
        return []
    results = []
    for item in data[:20]:
        hl = str(item.get('headline', '')).strip()
        if hl:
            results.append({
                'headline': hl,
                'summary': str(item.get('summary', '')).strip(),
                'source': str(item.get('source', '')).strip(),
                'url': str(item.get('url', '')).strip(),
                'ts': item.get('datetime', 0),
            })
    return results

def _fetch_fmp_news() -> list[dict]:
    if not FMP_API_KEY:
        return []
    data = _safe_get(
        'https://financialmodelingprep.com/api/v3/stock_news',
        {'limit': 20, 'apikey': FMP_API_KEY}
    )
    if not isinstance(data, list):
        return []
    results = []
    for item in data[:20]:
        hl = str(item.get('title', '')).strip()
        if hl:
            results.append({
                'headline': hl,
                'summary': str(item.get('text', '')).strip()[:300],
                'source': str(item.get('site', '')).strip(),
                'url': str(item.get('url', '')).strip(),
                'ts': 0,
            })
    return results

def _dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for item in items:
        key = item['headline'][:60].lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out

# ── macro calendar helpers ────────────────────────────────────
def _compute_event_phase(minutes_to_event) -> str:
    if minutes_to_event is None:
        return 'NONE'
    m = int(minutes_to_event)
    if m < 0:
        return 'PASSED'
    if m <= 5:
        return 'LIVE'
    if m <= 15:
        return 'IMMINENT'
    if m <= 45:
        return 'APPROACHING'
    return 'SCHEDULED'

def _get_next_event_from_file() -> tuple[str, int | None]:
    macro_file = BASE_DIR / 'data' / 'donna_macro_events.json'
    try:
        if not macro_file.exists():
            return 'No scheduled event', None
        with open(macro_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        events = data.get('events', [])
        now = _now_ny()
        best_title, best_mins = None, None
        for ev in events:
            time_str = str(ev.get('time_et', ''))
            try:
                h, m = [int(x) for x in time_str.split(':')]
                target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                mins = int((target - now).total_seconds() // 60)
                if mins >= -5 and (best_mins is None or mins < best_mins):
                    best_mins = mins
                    best_title = ev.get('title', 'Macro Event')
            except Exception:
                continue
        return (best_title or 'No scheduled event', best_mins)
    except Exception:
        return 'No scheduled event', None

# ── LLM headline classifier via Grok ─────────────────────────
_GROK_SYSTEM = (
    "You are DONNA's market news classifier. You have real-time awareness of current "
    "market events. Today CPI printed 3.8% annually - highest since May 2023. Markets "
    "are selling off. Factor this into your risk classification. Return only valid JSON."
)

def _llm_classify(headlines: list[str]) -> dict | None:
    """
    Uses Grok-3-mini (OpenAI-compatible) to extract a smarter headline read.
    Returns dict with keys: macro_headline, market_headline, macro_guidance,
    market_guidance, macro_severity, headline_severity, market_severity.
    Falls back to None on any error.
    """
    if not GROK_API_KEY:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(base_url='https://api.x.ai/v1', api_key=GROK_API_KEY)

        headlines_text = '\n'.join(f'- {h}' for h in headlines[:12])
        user_prompt = f"""Given these market headlines, extract the risk classification:

Headlines:
{headlines_text}

Return JSON only (no other text):
{{
  "macro_headline": "single most important macro headline or story (max 18 words)",
  "market_headline": "single most important company/sector headline (max 18 words)",
  "macro_guidance": "1-2 sentence trader-grade guidance on macro risk (max 30 words)",
  "market_guidance": "1-2 sentence guidance on market/company catalyst risk (max 30 words)",
  "macro_severity": "LOW | MEDIUM | HIGH",
  "headline_severity": "LOW | MEDIUM | HIGH",
  "market_severity": "LOW | MEDIUM | HIGH"
}}"""

        response = client.chat.completions.create(
            model='grok-3-mini',
            max_tokens=400,
            messages=[
                {'role': 'system', 'content': _GROK_SYSTEM},
                {'role': 'user',   'content': user_prompt},
            ],
        )
        raw = response.choices[0].message.content or ''
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            raw = match.group(0)
        data = json.loads(raw)
        return data
    except Exception as e:
        print(f'[donna_news] Grok classify error: {e}')
        return None

# ── main cycle ───────────────────────────────────────────────
def process_news_guard_cycle():
    """
    Main entry point — called by news_loop() in main.py every 5 minutes.
    Fetches live news, scores risk levels, updates donna_risk_state.json.
    """
    print(f'[donna_news] Running cycle at {_now_ny().strftime("%H:%M:%S")} ET')

    # 1. Fetch news from available sources
    items = _fetch_finnhub_news()
    if not items:
        items = _fetch_fmp_news()
    items = _dedupe(items)

    if not items:
        print('[donna_news] No news items fetched — skipping state update')
        return

    # 2. Score risk from all headlines combined
    all_text = ' '.join(i['headline'] + ' ' + i['summary'] for i in items)
    macro_risk, headline_risk, market_risk = _score_text(all_text)

    # 3. Get next event + phase
    next_event, mins_to_event = _get_next_event_from_file()
    event_phase = _compute_event_phase(mins_to_event)

    # 4. Pick best headlines
    # Sort: prefer items that score high
    def _item_score(item):
        t = (item['headline'] + ' ' + item['summary']).lower()
        s = 0
        if any(k in t for k in HIGH_MACRO): s += 3
        if any(k in t for k in HIGH_HEADLINE): s += 2
        if any(k in t for k in HIGH_MARKET): s += 2
        if any(k in t for k in MEDIUM_MACRO): s += 1
        return s

    ranked = sorted(items, key=_item_score, reverse=True)
    top_macro = ranked[0]['headline'] if ranked else 'No headline available'

    # Find best market/company headline
    market_items = [i for i in ranked if any(
        k in (i['headline'] + ' ' + i['summary']).lower() for k in HIGH_MARKET
    )]
    top_market = market_items[0]['headline'] if market_items else ranked[1]['headline'] if len(ranked) > 1 else top_macro

    # 5. Try LLM upgrade
    state = _read_risk()
    all_headlines = [i['headline'] for i in items[:12]]
    llm_data = _llm_classify(all_headlines)

    if llm_data:
        last_headline     = llm_data.get('macro_headline', top_macro)
        last_market_hl    = llm_data.get('market_headline', top_market)
        headline_guidance = llm_data.get('macro_guidance', '')
        market_guidance   = llm_data.get('market_guidance', '')
        # Allow LLM to upgrade severity but not downgrade below keyword score
        def _merge_severity(llm_val, keyword_val):
            order = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
            lv = order.get(str(llm_val).upper(), 1)
            kv = order.get(str(keyword_val).upper(), 1)
            return {1: 'low', 2: 'medium', 3: 'high'}[max(lv, kv)]
        macro_risk    = _merge_severity(llm_data.get('macro_severity', 'LOW'), macro_risk)
        headline_risk = _merge_severity(llm_data.get('headline_severity', 'LOW'), headline_risk)
        market_risk   = _merge_severity(llm_data.get('market_severity', 'LOW'), market_risk)
    else:
        last_headline     = top_macro
        last_market_hl    = top_market
        headline_guidance = _build_guidance(macro_risk, headline_risk, market_risk, top_macro, next_event)
        market_guidance   = (f'Company catalysts active: {top_market}'
                             if market_risk == 'high'
                             else 'No dominant company catalyst right now.')

    # 5b. Calendar coupling — event phase drives macro_risk floor
    if event_phase in ('LIVE', 'IMMINENT'):
        macro_risk = 'high'
        state['last_event_live_at'] = _utc_iso()
    elif event_phase == 'APPROACHING' and macro_risk != 'high':
        macro_risk = 'medium'
    elif event_phase in ('PASSED', 'NONE'):
        last_live = state.get('last_event_live_at')
        if last_live:
            try:
                last_live_dt = datetime.fromisoformat(last_live)
                mins_since = (datetime.now(timezone.utc) - last_live_dt).total_seconds() / 60
                if mins_since >= 30:
                    state.pop('last_event_live_at', None)
                elif macro_risk == 'low':
                    macro_risk = 'medium'
            except Exception:
                pass

    # 6. Severity label + warnings
    severity = _severity_label(macro_risk, headline_risk, market_risk)
    warnings = _build_warnings(macro_risk, headline_risk, market_risk, next_event, event_phase)

    # 7. Patch state — read above in step 5; never destroy existing market_snapshot or other fields

    state['macro_risk']           = macro_risk
    state['headline_risk']        = headline_risk
    state['market_news_risk']     = market_risk
    state['headline_severity']    = severity
    state['last_market_severity'] = 'HIGH' if market_risk == 'high' else 'MEDIUM' if market_risk == 'medium' else 'LOW'
    state['last_headline']        = last_headline
    state['last_market_headline'] = last_market_hl
    state['headline_guidance']    = headline_guidance
    state['last_market_guidance'] = market_guidance
    state['active_warnings']      = warnings
    state['next_event']           = next_event
    state['minutes_to_event']     = mins_to_event
    state['event_phase']          = event_phase

    # Store news items for the /news endpoint (last 10)
    state['_news_items'] = [
        {
            'headline': i['headline'],
            'summary':  i['summary'][:200],
            'source':   i['source'],
            'url':      i['url'],
        }
        for i in items[:10]
    ]

    _write_risk(state)

    print(f'[donna_news] Cycle complete — macro:{macro_risk} headline:{headline_risk} '
          f'market:{market_risk} phase:{event_phase} headlines:{len(items)}')
1

# ── immediate risk check (on-demand / every 5 min) ────────────
_IMMEDIATE_TRIGGERS = [
    'cpi', 'inflation', 'fed ', 'federal reserve', 'fomc',
    'rate hike', 'rate cut', 'rate decision', 'rate pause',
    'nonfarm', 'payroll', 'powell', 'recession', 'stagflation',
    'treasury yield', 'debt ceiling', 'banking crisis',
]

def immediate_risk_check() -> dict:
    """
    Fetches the latest Finnhub headlines right now and immediately sets
    headline_risk=HIGH in donna_risk_state.json if any macro risk keyword
    is detected. Returns {'triggered': bool, 'matched_words': list, 'top_headline': str}.
    Safe to call from a 5-minute loop for rapid headline response.
    """
    print(f'[donna_news] immediate_risk_check at {_now_ny().strftime("%H:%M:%S")} ET')

    items = _fetch_finnhub_news()
    if not items:
        return {'triggered': False, 'matched_words': [], 'top_headline': ''}

    all_text    = ' '.join(i['headline'] + ' ' + i['summary'] for i in items).lower()
    matched     = [w.strip() for w in _IMMEDIATE_TRIGGERS if w in all_text]
    top_headline = items[0]['headline']

    if matched:
        state = _read_risk()
        state['headline_risk']       = 'high'
        state['last_headline']       = top_headline
        state['_immediate_triggers'] = matched[:6]
        _write_risk(state)
        print(f'[donna_news] IMMEDIATE escalation — headline_risk=HIGH, matched: {matched[:6]}')

    return {
        'triggered':     bool(matched),
        'matched_words': matched,
        'top_headline':  top_headline,
    }
