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

ASSISTANT_SYSTEM_PROMPT = (
    'You are Donna, an elite market intelligence assistant. '
    'Return JSON only: {"action":"none|set_focus|add_task|add_reminder|clear_tasks|clear_reminders","value":"","reply":"short reply"}'
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
    risk     = load_risk_state()
    driver   = build_market_driver_engine(risk)
    morning  = build_morning_edge(risk)
    sig      = build_session_significance(risk)
    movers   = build_market_movers_engine()
    assistant = load_assistant_state()
    return (
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
        max_tokens=220,
    )
    parsed = parse_json_loose(response.content[0].text, fallback)
    return {
        'action': str(parsed.get('action', 'none')).strip().lower(),
        'value':  str(parsed.get('value', '')).strip(),
        'reply':  str(parsed.get('reply', '')).strip() or 'Donna processed the request.',
    }
