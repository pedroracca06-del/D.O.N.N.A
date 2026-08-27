"""donna_assistant.py — DONNA assistant LLM, context summary, action dispatch."""
from __future__ import annotations

import uuid

from core.state import (
    load_risk_state, load_assistant_state, save_assistant_state, load_alert_history,
)
from intelligence.gateway import request_intelligence
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

try:
    from engines.liquidity import load_liquidity as _load_liq, format_for_assistant as _liq_fmt
except Exception:
    _load_liq = None
    _liq_fmt  = None

try:
    from engines.synthesis import load_synthesis as _load_syn, format_for_assistant as _syn_fmt
except Exception:
    _load_syn = None
    _syn_fmt  = None

try:
    from engines.session_memory import load_session_memory as _load_mem, format_for_assistant as _mem_fmt
except Exception:
    _load_mem = None
    _mem_fmt  = None

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

    liq_line = ''
    if _load_liq and _liq_fmt:
        try:
            liq_line = _liq_fmt(_load_liq())
        except Exception:
            pass

    syn_line = ''
    if _load_syn and _syn_fmt:
        try:
            syn_line = _syn_fmt(_load_syn())
        except Exception:
            pass

    mem_line = ''
    if _load_mem and _mem_fmt:
        try:
            mem_line = _mem_fmt(_load_mem())
        except Exception:
            pass

    cached_context = (
        f"Session: {risk.get('nova_session') or risk.get('donna_session')}\n"
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

    cross_line  = f'\n{cm_line}'   if cm_line   else ''
    struct_line = f'\n{ms_line}'   if ms_line   else ''
    part_line   = f'\n{p_line}'    if p_line    else ''
    liq_line_s  = f'\n{liq_line}'  if liq_line  else ''
    mem_line_s  = f'\n{mem_line}'  if mem_line  else ''
    syn_line_s  = f'\n{syn_line}'  if syn_line  else ''
    return f"{reality_line}{cross_line}{struct_line}{part_line}{liq_line_s}{mem_line_s}{syn_line_s}\n\n{cached_context}"


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
    """Call NOVA Intelligence for assistant chat, via the gateway (spec §14 commit #5).

    Returns {'action', 'value', 'reply', 'outcome', 'error_code', 'cached'} on
    both success and every ordinary gateway failure -- callers never see a raw
    exception or provider detail from this function. Prompt-build failures and
    unexpected non-provider adapter exceptions are not caught here; they
    propagate to the route.

    `outcome` exists because a reply string alone cannot tell a caller whether
    NOVA answered. The gateway already distinguishes these cases via
    `success` / `error_code`; the previous version of this function collapsed
    them into a bare reply, which is why the page rendered
    "AI features are not configured right now." as a NOVA analysis. The four
    values are disjoint and exhaustive for a non-raising call:

        'ok'          a real answer -- and the only outcome that may act
        'empty'       the provider succeeded but returned no reply text
        'malformed'   the provider succeeded but the payload is not the
                      {action,value,reply} contract
        'unavailable' the gateway failed; `reply` is its user-safe message
                      and `error_code` is the fixed-vocabulary reason
    """
    response = request_intelligence(
        'assistant',
        {
            'message': message,
            'system_context': summarize_system_context(),
        },
        user_id='pedro',
        request_id=str(uuid.uuid4()),
    )

    if not response.success:
        return {
            'action': 'none',
            'value': '',
            'reply': response.user_message,
            'outcome': 'unavailable',
            'error_code': response.error_code,
            'cached': False,
        }

    data = response.structured_data
    # A success envelope still has to carry the agreed payload. parse_response()
    # can hand back None or a non-conforming object; that is a distinct failure
    # from "the gateway was down", and must not be reported as an answer.
    if not isinstance(data, dict) or 'reply' not in data:
        return {
            'action': 'none',
            'value': '',
            'reply': '',
            'outcome': 'malformed',
            'error_code': 'MALFORMED_OUTPUT',
            'cached': bool(response.cached),
        }

    reply = str(data.get('reply') or '').strip()
    return {
        'action': str(data.get('action') or 'none'),
        'value': data.get('value') or '',
        'reply': reply,
        'outcome': 'ok' if reply else 'empty',
        'error_code': None,
        'cached': bool(response.cached),
    }
