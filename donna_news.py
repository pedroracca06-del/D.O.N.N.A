"""donna_news.py — DONNA v5.0 News & Market Intelligence Engine."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import os
import re
import requests

# ── paths & config ────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
RISK_STATE_FILE = BASE_DIR / 'donna_risk_state.json'
GROK_INTEL_FILE = BASE_DIR / 'donna_grok_intelligence.json'
NY_TZ           = ZoneInfo('America/New_York')

FINNHUB_API_KEY   = os.getenv('FINNHUB_API_KEY', '').strip()
FMP_API_KEY       = os.getenv('FMP_API_KEY', '').strip()
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '').strip()
GROK_API_KEY      = os.getenv('GROK_API_KEY', '').strip()


# ── time helpers ──────────────────────────────────────────────

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


# ── keyword scoring ───────────────────────────────────────────

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
    t = text.lower()
    macro = 'low'
    if any(k in t for k in HIGH_MACRO):
        macro = 'high'
    elif any(k in t for k in MEDIUM_MACRO):
        macro = 'medium'
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


def _build_warnings(macro, headline, market, next_event, event_phase) -> list:
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
        warnings.append('Event is LIVE or IMMINENT — reduce conviction, respect reaction')
    elif phase == 'APPROACHING':
        warnings.append('Event approaching — do not confuse pre-event noise for conviction')
    if not warnings:
        warnings.append('No elevated risk signals — standard session caution applies')
    return warnings[:4]


def _build_guidance(macro, headline, market, top_headline, next_event) -> str:
    if macro == 'high':
        return (f'Macro risk is high. {next_event} is the main threat. '
                'Treat price action near event windows as potentially reactive.')
    if headline == 'high':
        return ('Breaking headline risk is active. '
                'Wait for the initial reaction to settle before reading direction.')
    if market == 'high':
        return ('Company catalysts are driving the tape. '
                'Focus on leadership names and watch whether moves broaden.')
    return ('Balanced conditions. No single dominant threat. '
            'Respect session structure and leadership confirmation before adding size.')


# ── data sources ──────────────────────────────────────────────

def _fetch_finnhub_news() -> list:
    if not FINNHUB_API_KEY:
        return []
    data = _safe_get('https://finnhub.io/api/v1/news',
                     {'category': 'general', 'token': FINNHUB_API_KEY})
    if not isinstance(data, list):
        return []
    results = []
    for item in data[:20]:
        hl = str(item.get('headline', '')).strip()
        if hl:
            results.append({
                'headline': hl,
                'summary':  str(item.get('summary', '')).strip(),
                'source':   str(item.get('source', '')).strip(),
                'url':      str(item.get('url', '')).strip(),
                'ts':       item.get('datetime', 0),
            })
    return results


def _fetch_fmp_news() -> list:
    if not FMP_API_KEY:
        return []
    data = _safe_get('https://financialmodelingprep.com/api/v3/stock_news',
                     {'limit': 20, 'apikey': FMP_API_KEY})
    if not isinstance(data, list):
        return []
    results = []
    for item in data[:20]:
        hl = str(item.get('title', '')).strip()
        if hl:
            results.append({
                'headline': hl,
                'summary':  str(item.get('text', '')).strip()[:300],
                'source':   str(item.get('site', '')).strip(),
                'url':      str(item.get('url', '')).strip(),
                'ts':       0,
            })
    return results


def _dedupe(items: list) -> list:
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
    if m < 0:   return 'PASSED'
    if m <= 5:  return 'LIVE'
    if m <= 15: return 'IMMINENT'
    if m <= 45: return 'APPROACHING'
    return 'SCHEDULED'


def _get_next_event_from_file():
    macro_file = BASE_DIR / 'donna_macro_events.json'
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


# ── headline LLM classifier (Grok) ───────────────────────────

_GROK_CLASSIFY_SYSTEM = (
    "You are DONNA's market news classifier. You have real-time awareness of current "
    "market events. Return only valid JSON."
)


def _llm_classify(headlines: list) -> dict | None:
    if not GROK_API_KEY:
        return None
    try:
        from openai import OpenAI
        c = OpenAI(base_url='https://api.x.ai/v1', api_key=GROK_API_KEY)
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
        response = c.chat.completions.create(
            model='grok-3-mini',
            max_tokens=400,
            messages=[
                {'role': 'system', 'content': _GROK_CLASSIFY_SYSTEM},
                {'role': 'user',   'content': user_prompt},
            ],
        )
        raw = response.choices[0].message.content or ''
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except Exception as e:
        print(f'[donna_news] Grok classify error: {e}')
    return None


# ── Grok market intelligence ──────────────────────────────────

_GROK_INTEL_EMPTY: dict = {
    'top_story':           '',
    'top_story_summary':   '',
    'market_sentiment':    'NEUTRAL',
    'sentiment_reason':    'Grok API key not configured — add GROK_API_KEY to enable live intelligence.',
    'breaking_events':     [],
    'donna_trade_read':    '',
    'key_names_to_watch':  [],
    'last_updated':        None,
}


def get_grok_intelligence() -> dict:
    """Load latest Grok intelligence from file. Returns defaults if unavailable."""
    try:
        if GROK_INTEL_FILE.exists():
            with open(GROK_INTEL_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return dict(_GROK_INTEL_EMPTY)


def fetch_grok_news_intelligence() -> dict | None:
    """
    Call Grok-3-mini via direct HTTP for real-time market intelligence.
    Saves result to donna_grok_intelligence.json and returns the dict.
    Returns None if API key missing or call fails.
    """
    if not GROK_API_KEY:
        return None
    try:
        payload = {
            'model': 'grok-3-mini',
            'max_tokens': 900,
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        "You are DONNA's real-time market intelligence brain with access to "
                        "current X/Twitter trader sentiment and breaking financial news. "
                        "Return only valid JSON, no markdown."
                    ),
                },
                {
                    'role': 'user',
                    'content': (
                        'Analyze current market conditions. '
                        'Return JSON with exactly these fields: '
                        'top_story (string), '
                        'top_story_summary (string, 2 sentences), '
                        'market_sentiment (BULLISH/BEARISH/NEUTRAL/MIXED), '
                        'sentiment_reason (string, 1 sentence), '
                        'breaking_events (array of up to 3 objects each with: title, '
                        'impact HIGH/MEDIUM/LOW, direction BULL/BEAR/NEUTRAL, source), '
                        'donna_trade_read (string, 1 paragraph on what this means for '
                        'NQ and ES traders right now), '
                        'key_names_to_watch (array of 3-5 ticker strings)'
                    ),
                },
            ],
        }
        r = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {GROK_API_KEY}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        raw = r.json()['choices'][0]['message']['content'] or ''
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            print('[donna_news] Grok intel: no JSON found in response')
            return None
        data = json.loads(m.group(0))
        data['last_updated'] = _utc_iso()
        # Normalise breaking_events
        events = data.get('breaking_events', [])
        if not isinstance(events, list):
            data['breaking_events'] = []
        else:
            clean = []
            for ev in events[:3]:
                if isinstance(ev, dict) and ev.get('title'):
                    clean.append({
                        'title':     str(ev.get('title', '')),
                        'impact':    str(ev.get('impact', 'LOW')).upper(),
                        'direction': str(ev.get('direction', 'NEUTRAL')).upper(),
                        'source':    str(ev.get('source', '')),
                    })
            data['breaking_events'] = clean
        # Normalise key_names_to_watch
        names = data.get('key_names_to_watch', [])
        if not isinstance(names, list):
            data['key_names_to_watch'] = []
        else:
            data['key_names_to_watch'] = [str(n).upper() for n in names[:5] if n]
        with open(GROK_INTEL_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f'[donna_news] Grok intel updated — sentiment:{data.get("market_sentiment")}')
        return data
    except Exception as e:
        print(f'[donna_news] Grok intel fetch error: {e} — keeping previous cached data')
        return None  # caller retains existing file; retry on next cycle


def _is_market_hours() -> bool:
    ny = _now_ny()
    m  = ny.hour * 60 + ny.minute
    return ny.weekday() < 5 and 9 * 60 <= m <= 16 * 60 + 30


def _grok_intel_stale(max_minutes: int) -> bool:
    """True if Grok intel file is missing or older than max_minutes."""
    try:
        if not GROK_INTEL_FILE.exists():
            return True
        intel = get_grok_intelligence()
        # Accept either timestamp key (main.py writes fetched_at, donna_news writes last_updated)
        ts = intel.get('last_updated') or intel.get('fetched_at')
        if not ts:
            return True
        dt  = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 60
        return age >= max_minutes
    except Exception:
        return True


# ── immediate risk check ──────────────────────────────────────

_IMMEDIATE_TRIGGERS = [
    'cpi', 'inflation', 'fed ', 'federal reserve', 'fomc',
    'rate hike', 'rate cut', 'rate decision', 'rate pause',
    'nonfarm', 'payroll', 'powell', 'recession', 'stagflation',
    'treasury yield', 'debt ceiling', 'banking crisis',
]


def immediate_risk_check() -> dict:
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
        print(f'[donna_news] IMMEDIATE escalation — matched: {matched[:6]}')
    return {
        'triggered':     bool(matched),
        'matched_words': matched,
        'top_headline':  top_headline,
    }


# ── main cycle ────────────────────────────────────────────────

def process_news_guard_cycle():
    """
    Main entry point called by news_loop() in main.py every 5 minutes.
    Fetches live news, scores risk levels, updates donna_risk_state.json.
    Also refreshes Grok intelligence every 5 min during market hours,
    every 30 min outside.
    """
    print(f'[donna_news] Running cycle at {_now_ny().strftime("%H:%M:%S")} ET')

    # ── News fetch ──────────────────────────────────────────
    items = _fetch_finnhub_news()
    if not items:
        items = _fetch_fmp_news()
    items = _dedupe(items)

    if not items:
        print('[donna_news] No news items fetched — skipping state update')
        # Still refresh Grok even without news items
        _maybe_refresh_grok()
        return

    # ── Keyword scoring ─────────────────────────────────────
    all_text = ' '.join(i['headline'] + ' ' + i['summary'] for i in items)
    macro_risk, headline_risk, market_risk = _score_text(all_text)

    # ── Next event + phase ──────────────────────────────────
    next_event, mins_to_event = _get_next_event_from_file()
    event_phase = _compute_event_phase(mins_to_event)

    # ── Rank headlines ──────────────────────────────────────
    def _item_score(item):
        t = (item['headline'] + ' ' + item['summary']).lower()
        s = 0
        if any(k in t for k in HIGH_MACRO):     s += 3
        if any(k in t for k in HIGH_HEADLINE):  s += 2
        if any(k in t for k in HIGH_MARKET):    s += 2
        if any(k in t for k in MEDIUM_MACRO):   s += 1
        return s

    ranked     = sorted(items, key=_item_score, reverse=True)
    top_macro  = ranked[0]['headline'] if ranked else 'No headline available'
    mkt_items  = [i for i in ranked if any(
        k in (i['headline'] + ' ' + i['summary']).lower() for k in HIGH_MARKET
    )]
    top_market = (mkt_items[0]['headline'] if mkt_items
                  else ranked[1]['headline'] if len(ranked) > 1 else top_macro)

    # ── LLM upgrade (Grok classifier) ──────────────────────
    all_headlines = [i['headline'] for i in items[:12]]
    llm_data      = _llm_classify(all_headlines)

    if llm_data:
        last_headline     = llm_data.get('macro_headline', top_macro)
        last_market_hl    = llm_data.get('market_headline', top_market)
        headline_guidance = llm_data.get('macro_guidance', '')
        market_guidance   = llm_data.get('market_guidance', '')

        def _merge(llm_val, kw_val):
            order = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
            lv = order.get(str(llm_val).upper(), 1)
            kv = order.get(str(kw_val).upper(), 1)
            return {1: 'low', 2: 'medium', 3: 'high'}[max(lv, kv)]

        macro_risk    = _merge(llm_data.get('macro_severity', 'LOW'), macro_risk)
        headline_risk = _merge(llm_data.get('headline_severity', 'LOW'), headline_risk)
        market_risk   = _merge(llm_data.get('market_severity', 'LOW'), market_risk)
    else:
        last_headline     = top_macro
        last_market_hl    = top_market
        headline_guidance = _build_guidance(macro_risk, headline_risk, market_risk,
                                            top_macro, next_event)
        market_guidance   = (f'Company catalysts active: {top_market}'
                             if market_risk == 'high'
                             else 'No dominant company catalyst right now.')

    severity = _severity_label(macro_risk, headline_risk, market_risk)
    warnings = _build_warnings(macro_risk, headline_risk, market_risk,
                               next_event, event_phase)

    # ── Write risk state ────────────────────────────────────
    state = _read_risk()
    state['macro_risk']           = macro_risk
    state['headline_risk']        = headline_risk
    state['market_news_risk']     = market_risk
    state['headline_severity']    = severity
    state['last_market_severity'] = ('HIGH' if market_risk == 'high'
                                     else 'MEDIUM' if market_risk == 'medium' else 'LOW')
    state['last_headline']        = last_headline
    state['last_market_headline'] = last_market_hl
    state['headline_guidance']    = headline_guidance
    state['last_market_guidance'] = market_guidance
    state['active_warnings']      = warnings
    state['next_event']           = next_event
    state['minutes_to_event']     = mins_to_event
    state['event_phase']          = event_phase
    state['_news_items']          = [
        {'headline': i['headline'], 'summary': i['summary'][:200],
         'source': i['source'], 'url': i['url']}
        for i in items[:10]
    ]
    _write_risk(state)

    print(f'[donna_news] Cycle complete — macro:{macro_risk} headline:{headline_risk} '
          f'market:{market_risk} phase:{event_phase} headlines:{len(items)}')

    # ── Grok intelligence refresh ───────────────────────────
    _maybe_refresh_grok()


def _maybe_refresh_grok():
    """Refresh Grok intel every 5 min during market hours, every 30 min outside."""
    max_age = 5 if _is_market_hours() else 30
    if _grok_intel_stale(max_age):
        fetch_grok_news_intelligence()
