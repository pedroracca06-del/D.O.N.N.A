"""donna_assistant.py — DONNA assistant LLM, context summary, action dispatch."""
from __future__ import annotations

import uuid

from core.state import (
    load_risk_state, load_assistant_state, save_assistant_state, load_alert_history,
)
from intelligence.gateway import request_intelligence
from intelligence.current_knowledge import CurrentKnowledgeIntegrityError, retrieve_current_prime
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

def _summarize_system_context_parts() -> tuple[str, list[str]]:
    risk      = load_risk_state()
    driver    = build_market_driver_engine(risk)
    morning   = build_morning_edge(risk)
    sig       = build_session_significance(risk)
    movers    = build_market_movers_engine()
    assistant = load_assistant_state()
    mr2 = load_market_reality_v2() if load_market_reality_v2 else {}
    context_sources = ['session_risk', 'working_memory']

    # Market Reality is included early as one evidence source, never as infallible authority.
    # V1 loaded only as fallback when V2 is unavailable — avoids unconditional dual read.
    if mr2 and _mr2_fmt:
        reality_line = _mr2_fmt(mr2)
        if reality_line:
            context_sources.append('market_reality')
    else:
        mr = load_market_reality()
        reality_line = format_reality_for_assistant(mr)
        if reality_line:
            context_sources.append('market_reality')

    cm_line = ''
    if _load_cm and _cm_fmt:
        try:
            cm_line = _cm_fmt(_load_cm())
            if cm_line:
                context_sources.append('cross_market')
        except Exception:
            pass

    ms_line = ''
    if _load_ms and _ms_fmt:
        try:
            ms_line = _ms_fmt(_load_ms())
            if ms_line:
                context_sources.append('market_structure')
        except Exception:
            pass

    p_line = ''
    if _load_p and _p_fmt:
        try:
            p_line = _p_fmt(_load_p())
            if p_line:
                context_sources.append('participation')
        except Exception:
            pass

    liq_line = ''
    if _load_liq and _liq_fmt:
        try:
            liq_line = _liq_fmt(_load_liq())
            if liq_line:
                context_sources.append('liquidity')
        except Exception:
            pass

    syn_line = ''
    if _load_syn and _syn_fmt:
        try:
            syn_line = _syn_fmt(_load_syn())
            if syn_line:
                context_sources.append('synthesis')
        except Exception:
            pass

    mem_line = ''
    if _load_mem and _mem_fmt:
        try:
            mem_line = _mem_fmt(_load_mem())
            if mem_line:
                context_sources.append('session_memory')
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
    context = f"{reality_line}{cross_line}{struct_line}{part_line}{liq_line_s}{mem_line_s}{syn_line_s}\n\n{cached_context}"
    return context, context_sources


def summarize_system_context() -> str:
    """Backward-compatible text-only system context."""
    return _summarize_system_context_parts()[0]


def summarize_system_context_with_sources() -> tuple[str, list[str]]:
    """Return generated context plus source classes present in that context."""
    return _summarize_system_context_parts()


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
    system_context, context_sources = summarize_system_context_with_sources()
    try:
        current_knowledge = retrieve_current_prime(message)
    except CurrentKnowledgeIntegrityError:
        return {
            'action': 'none',
            'value': '',
            'reply': 'Current PRIME knowledge is unavailable because its authority package failed integrity validation.',
            'outcome': 'unavailable',
            'error_code': None,
            'cached': False,
            'context_sources': context_sources,
            'knowledge_sources': [],
            'knowledge_provenance': [],
            'knowledge_authority': 'unavailable',
        }
    # Doctrine travels in its own field, never appended to the generated
    # context. Sharing a field would have let any headline or user sentence
    # that types a [CURRENT SOURCE: ...] marker arrive with the same standing
    # as text NOVA actually read from Git-authoritative files; the prompt
    # module gives this field its own section and neutralises that marker
    # everywhere else.
    if current_knowledge.text:
        context_sources.append('current_prime_knowledge')
    knowledge_sources = list(current_knowledge.sources)
    hashes = list(getattr(current_knowledge, 'source_hashes', ()))
    knowledge_provenance = [
        {'source': src, 'sha256': hashes[i] if i < len(hashes) else None}
        for i, src in enumerate(knowledge_sources)
    ]

    response = request_intelligence(
        'assistant',
        {
            'message': message,
            'system_context': system_context,
            'current_knowledge': current_knowledge.text,
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
            'context_sources': context_sources,
            'knowledge_sources': knowledge_sources,
            'knowledge_provenance': knowledge_provenance,
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
            'context_sources': context_sources,
            'knowledge_sources': knowledge_sources,
            'knowledge_provenance': knowledge_provenance,
        }

    reply = str(data.get('reply') or '').strip()
    return {
        'action': str(data.get('action') or 'none'),
        'value': data.get('value') or '',
        'reply': reply,
        'outcome': 'ok' if reply else 'empty',
        'error_code': None,
        'cached': bool(response.cached),
        'context_sources': context_sources,
        'knowledge_sources': knowledge_sources,
        'knowledge_provenance': knowledge_provenance,
        'knowledge_authority': 'current',
    }
