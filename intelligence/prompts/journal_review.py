"""intelligence/prompts/journal_review.py — Journal NOVA Review prompt template (spec §6.1, §14 commit #6).

Moved from main.py's /journal/analyze route, unmodified in substance: the
trusted system-level instruction and the fixed 5-section post-trade
analysis request. ProviderAdapter.call() has no system-prompt channel
(locked in commit #3), so the trusted instructions, the selected trade's
own fields, and the nearby signal-log context are combined into one clearly
delimited string here instead. The trade and signal-log data are treated as
data to analyze, never as authority that can rewrite the output contract.

Imports nothing from services/, engines/, core.config.client, or any
provider SDK -- input_data is a self-contained payload already carrying
everything this module needs (the curated trade dict + pre-formatted
nearby-signal text built by main.py).
"""
from __future__ import annotations

REVIEW_SYSTEM_PROMPT = (
    'You are NOVA, an AI trading intelligence system for MES and MNQ micro futures. '
    'You give precise, institutional-grade trade reviews. No hedging, no generic advice. '
    'Speak directly about this specific trade.'
)

REVIEW_INSTRUCTIONS = (
    'Provide a structured post-trade analysis with these exact sections. '
    'Keep each section to 2-4 sentences max. Tactical, operational language only.\n\n'
    'QUALIFICATION\n'
    'Why this setup did or did not meet execution standards. Reference PROS phase, '
    'OTE, IB draw, session quality, confidence score.\n\n'
    'EXECUTION\n'
    'Entry timing, stop placement, exit management. Execution score: X/100.\n\n'
    'OUTCOME ASSESSMENT\n'
    'Was the outcome correct given the setup quality? Explain the result.\n\n'
    'WHAT SHOULD HAVE HAPPENED\n'
    'Validate correct trades. Identify the error on incorrect ones. State the right path.\n\n'
    'BEHAVIORAL NOTE\n'
    'One sentence on any behavioral pattern if trader notes or flags suggest it. '
    'If none, state "No behavioral flags."'
)


def _format_trade(trade: dict) -> str:
    return (
        f"Instrument: {trade.get('ticker')} {trade.get('direction')}\n"
        f"Setup: {trade.get('setup_type') or 'unspecified'}\n"
        f"Entry: {trade.get('entry_price') or '—'} | Exit: {trade.get('exit_price') or '—'} | "
        f"Stop: {trade.get('stop') or '—'} | TP1: {trade.get('tp1') or '—'}\n"
        f"Size: {trade.get('size', 1)} | R:R: {trade.get('rr') or '—'}\n"
        f"P&L: {trade.get('realized_pnl')} | Outcome: {trade.get('outcome')}\n"
        f"Session: {trade.get('session') or '—'} | Macro risk: {trade.get('macro_risk') or '—'}\n"
        f"Trader notes: {trade.get('notes') or 'none'}\n"
        f"Emotional state: {trade.get('emotional_state') or 'not reported'}\n"
        f"Behavioral flags: {', '.join(trade.get('behavioral_flags') or []) or 'none'}\n"
        f"Reflection: {trade.get('reflection') or 'none'}"
    )


def build_prompt(input_data: dict) -> str:
    """input_data: {'trade': dict, 'nearby_signals': str}"""
    trade = input_data.get('trade') or {}
    nearby_signals = str(input_data.get('nearby_signals', ''))
    ticker = trade.get('ticker')

    return (
        '=== NOVA INSTRUCTIONS (trusted, defines the output contract) ===\n'
        f'{REVIEW_SYSTEM_PROMPT}\n\n'
        f'{REVIEW_INSTRUCTIONS}\n'
        '=== END NOVA INSTRUCTIONS ===\n\n'
        '=== TRADE RECORD (data, the one explicitly selected trade) ===\n'
        f'{_format_trade(trade)}\n'
        '=== END TRADE RECORD ===\n\n'
        f'=== NOVA EVALUATION LOG (data, closest signal-log entries for {ticker}) ===\n'
        f'{nearby_signals}\n'
        '=== END NOVA EVALUATION LOG ==='
    )


def parse_response(text: str) -> dict:
    """Rejects only empty/whitespace-only output (spec §14 commit #6 scope --
    the five section headers are not validated in this commit)."""
    stripped = text.strip()
    if not stripped:
        raise ValueError('journal review response was empty')
    return {'analysis': stripped}
