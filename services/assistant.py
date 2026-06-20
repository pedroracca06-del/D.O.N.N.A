"""donna_assistant.py — DONNA assistant LLM, context summary, action dispatch."""
from __future__ import annotations

import json
import re

from core.config import client, ANTHROPIC_ASSISTANT_MODEL
from core.state import (
    load_risk_state, load_assistant_state, save_assistant_state, load_alert_history,
)
from engines.engines import (
    build_market_driver_engine, build_morning_edge,
    build_session_significance, build_market_movers_engine,
)
from engines.market_reality import load_market_reality, format_reality_for_assistant
try:
    from engines.market_reality_v2 import load_market_reality_v2, format_for_assistant as _mr2_fmt
except Exception:
    load_market_reality_v2 = None
    _mr2_fmt = None
try:
    from engines.cross_market import load_cross_market as _load_cm, format_for_assistant as _cm_fmt
except Exception:
    _load_cm = None
    _cm_fmt  = None

try:
    from engines.market_structure import load_market_structure as _load_ms, format_for_assistant as _ms_fmt
except Exception:
    _load_ms = None
    _ms_fmt  = None

try:
    from engines.participation import load_participation as _load_p, format_for_assistant as _p_fmt
except Exception:
    _load_p = None
    _p_fmt  = None

ASSISTANT_SYSTEM_PROMPT = (
    'You are Donna, an elite market intelligence assistant. '
    'MR2 (Market Reality 2.0) is objective ground truth — it overrides any cached session narrative. '
    'When MR2 state is BEARISH_DOMINANT or PANIC_SELLING: acknowledge bearish conditions first. '
    'When MR2 state is BULLISH_DOMINANT: acknowledge bullish conditions. '
    'When LONGS_BLOCKED or SHORTS_BLOCKED: respect the execution rule explicitly. '
    'Return JSON only — no text outside the JSON object: '
    '{"action":"none|set_focus|add_task|add_reminder|clear_tasks|clear_reminders","value":"","reply":"1-3 sentences"}'
)


def parse_json_loose(text, fallback):
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        m = re.search(r'\{.*\}', text, re.S)
        return json.loads(m.group(0)) if m else fallback
    except Exception:
        return fallback


def summarize_system_context() -> str:
    risk      = load_risk_state()
    driver    = build_market_driver_engine(risk)
    morning   = build_morning_edge(risk)
    sig       = build_session_significance(risk)
    movers    = build_market_movers_engine()
    assistant = load_assistant_state()
    mr2 = load_market_reality_v2() if load_market_reality_v2 else {}

    # MR2 ground truth prepended first so Claude reads objective state before any narrative.
    # V1 loaded only as fallback when V2 is unavailable — avoids unconditional dual read.
    if mr2 and _mr2_fmt:
        reality_line = _mr2_fmt(mr2)
    else:
        mr = load_market_reality()
        reality_line = format_reality_for_assistant(mr)

    cm_line = ''
    if _load_cm and _cm_fmt:
        try:
            cm_line = _cm_fmt(_load_cm())
        except Exception:
            pass

    ms_line = ''
    if _load_ms and _ms_fmt:
        try:
            ms_line = _ms_fmt(_load_ms())
        except Exception:
            pass

    p_line = ''
    if _load_p and _p_fmt:
        try:
            p_line = _p_fmt(_load_p())
        except Exception:
            pass

    cached_context = (
        f"Session: {risk.get('donna_session')}\n"
        f"Macro Risk: {risk.get('macro_risk')}\n"
        f"Headline Risk: {risk.get('headline_risk')}\n"
        f"Market Risk: {risk.get('market_news_risk')}\n"
        f"Next Event: {risk.get('next_event')}\n"
        f"Event Phase: {risk.get('event_phase')}\n"
        f"Dominant Driver: {driver.get('dominant_driver')}\n"
        f"Threat: {driver.get('market_threat')}\n"
        f"Session Significance: {sig.get('label')}\n"
        f"Session Summary: {sig.get('summary')}\n"
        f"Morning Bias: {morning.get('today_bias')}\n"
        f"Focus: {morning.get('focus')}\n"
        f"Likely Leaders: {[x['ticker'] for x in movers['leaders']]}\n"
        f"Likely Threats: {[x['ticker'] for x in movers['threats']]}\n"
        f"Daily Focus: {assistant.get('daily_focus')}"
    )

    cross_line  = f'\n{cm_line}' if cm_line else ''
    struct_line = f'\n{ms_line}' if ms_line else ''
    part_line   = f'\n{p_line}'  if p_line  else ''
    return f"{reality_line}{cross_line}{struct_line}{part_line}\n\n{cached_context}"


def apply_assistant_action(action, value):
    state  = load_assistant_state()
    action = str(action or 'none').strip().lower()
    value  = str(value or '').strip()

    if action == 'set_focus' and value:
        state['daily_focus'] = value
    elif action == 'add_task' and value:
        state['tasks'].append(value)
        state['tasks'] = state['tasks'][:20]
    elif action == 'add_reminder' and value:
        state['reminders'].append(value)
        state['reminders'] = state['reminders'][:20]
    elif action == 'clear_tasks':
        state['tasks'] = []
    elif action == 'clear_reminders':
        state['reminders'] = []

    save_assistant_state(state)
    return state


def call_assistant_llm(message: str) -> dict:
    """Call Claude for assistant chat. Returns {'action', 'value', 'reply'}."""
    fallback = {'action': 'none', 'value': '', 'reply': ''}
    if not client:
        return fallback

    response = client.messages.create(
        model=ANTHROPIC_ASSISTANT_MODEL,
        system=ASSISTANT_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': f'User message:\n{message}\n\nSystem context:\n{summarize_system_context()}'}],
        max_tokens=400,
    )
    raw = response.content[0].text
    parsed = parse_json_loose(raw, fallback)

    # Log parse failures so we can see what Claude actually returned
    reply = str(parsed.get('reply', '')).strip()
    if not reply:
        print(f'[assistant] parse miss — raw response: {raw[:300]!r}')

    return {
        'action': str(parsed.get('action', 'none')).strip().lower(),
        'value':  str(parsed.get('value', '')).strip(),
        'reply':  reply or 'No reply generated.',
    }
