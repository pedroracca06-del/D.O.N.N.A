"""Regression coverage for the final production-interface follow-ups."""
from __future__ import annotations

import inspect
import re

from engines import engines, synthesis
from ui.html import DASHBOARD_HTML
from ui.styles import DASHBOARD_CSS


def test_thesis_label_shortening_never_cuts_a_word_midway():
    label = 'Primary draw PWL conflicts with unfinished bullish market structure'
    shortened = synthesis._short_label(label, 55)
    assert len(shortened) <= 55
    assert shortened.endswith('…')
    assert shortened[:-1] in label
    assert label[len(shortened) - 1].isspace()


def test_gold_quote_candidates_never_silently_substitute_an_etf(monkeypatch):
    requested = []

    def fake_quote(symbol):
        requested.append(symbol)
        return None

    monkeypatch.setattr(engines, 'get_quote_with_fallback', fake_quote)
    assert engines.get_futures_quote('GOLD') is None
    assert requested == ['GC=F']
    source = inspect.getsource(engines.get_futures_quote)
    assert "'GOLD': ['GC=F']" in source
    assert "'GOLD': ['GC=F', 'GLD']" not in source


def test_meaningful_page_kickers_meet_the_11px_floor():
    for selector in ('.mk-kicker', '#page-assistant .ni-kicker', '#page-settings .st-kicker'):
        match = re.search(re.escape(selector) + r'\s*\{([^}]+)\}', DASHBOARD_CSS)
        assert match, selector
        assert 'font-size:11px' in match.group(1), selector


def test_dashboard_embeds_a_favicon_without_an_external_request():
    assert '<link rel="icon" href="data:image/svg+xml,' in DASHBOARD_HTML
    assert 'href="/favicon.ico"' not in DASHBOARD_HTML


def test_verified_render_host_replaces_the_obsolete_example():
    from core import config

    source = inspect.getsource(config)
    assert 'https://d-o-n-n-a.onrender.com' in source
    assert 'https://donna.onrender.com' not in source
