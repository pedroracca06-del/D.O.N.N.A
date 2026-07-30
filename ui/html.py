"""ui/html.py — DASHBOARD_HTML composer.

Interface-modularization foundation (commit #9): this file used to
contain the entire ~3900-line dashboard (CSS + HTML + JS) as one inline
triple-quoted string. It now only assembles DASHBOARD_HTML from the
modules below.

Commit #11 (information-architecture restructuring): only the nav
button *visible text* changed here (Dashboard -> Overview, News ->
Markets, Assistant -> NOVA Intelligence). Every `data-page` value and
every `id="page-*"` container is unchanged -- the internal navigation
mechanism, routes, and backend contracts are untouched. See
ui/pages/overview.py and ui/pages/market_news.py for the rest of
commit #11's approved restructuring (Morning Brief addition, Macro
Radar / NOVA Says consolidation).

Visual-system changes and responsive behavior remain deferred to a
later, separately-approved commit.
"""
from ui.styles import DASHBOARD_CSS
from ui.scripts import DASHBOARD_SCRIPT
from ui.pages import (
    OVERVIEW_HTML, MARKET_NEWS_HTML, NOVA_AI_HTML,
    JOURNAL_MODALS_HTML, SETTINGS_HTML, JOURNAL_HTML,
)

DASHBOARD_HTML = (
    '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>NOVA v5.0</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600;700;900&display=swap" rel="stylesheet">
<style>
'''
    + DASHBOARD_CSS +
    '''</style>
</head>
<body>
<div class="wrap">

  <!-- TOPBAR -->
  <div class="topbar">
    <div class="brand">
      <h1>NOVA</h1>
      <span class="brand-tag">v5.0 // LIVE MARKET CORE</span>
    </div>
    <div class="top-right">
      <div class="nav">
        <button class="tab-btn active" data-page="dashboard">Overview</button>
        <button class="tab-btn" data-page="journal">Journal</button>
        <button class="tab-btn" data-page="news">Markets</button>
        <button class="tab-btn" data-page="assistant">NOVA Intelligence</button>
        <button class="tab-btn" data-page="settings">Settings</button>
      </div>
      <div class="status-badge"><span class="dot"></span>ONLINE</div>
    </div>
  </div>

  <!-- LIVE STRIP -->
  <div class="live-strip-row">
    <div class="live-label">⬤ LIVE INTELLIGENCE</div>
    <div class="ticker-wrap">
      <div class="ticker-track" id="liveStrip">Loading...</div>
    </div>
    <div class="session-chip">
      <div class="lab">Current Session</div>
      <div class="val" id="sessionVal">—</div>
    </div>
  </div>

'''
    + OVERVIEW_HTML + MARKET_NEWS_HTML + NOVA_AI_HTML
    + JOURNAL_MODALS_HTML + SETTINGS_HTML + JOURNAL_HTML +
    '''  <!-- FOOTER -->
  <div class="footer">
    <span>NOVA v5.0 // LIVE MARKET CORE</span>
    <span id="lastUpdated">Connecting...</span>
  </div>

</div>

<script>
'''
    + DASHBOARD_SCRIPT +
    '''</script>
</body>
</html>'''
)
