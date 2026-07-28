"""ui/pages — per-page HTML fragments composed by ui/html.py.

Each module exports one (or, for Journal, two) plain string constant
containing that page's markup, extracted verbatim from the former
monolithic ui/html.py during the interface-modularization foundation
(commit #9). This package performs no rendering itself — ui/html.py
imports these constants and concatenates them in the same order the
original single-file template used.
"""
from ui.pages.overview import OVERVIEW_HTML
from ui.pages.market_news import MARKET_NEWS_HTML
from ui.pages.nova_ai import NOVA_AI_HTML
from ui.pages.journal import JOURNAL_HTML, JOURNAL_MODALS_HTML
from ui.pages.settings import SETTINGS_HTML

__all__ = [
    'OVERVIEW_HTML', 'MARKET_NEWS_HTML', 'NOVA_AI_HTML',
    'JOURNAL_HTML', 'JOURNAL_MODALS_HTML', 'SETTINGS_HTML',
]
