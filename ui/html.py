"""ui/html.py — DASHBOARD_HTML composer.

Interface-modularization foundation (commit #9): this file used to
contain the entire ~3900-line dashboard (CSS + HTML + JS) as one inline
triple-quoted string. It now only assembles DASHBOARD_HTML from the
modules below — the exported DASHBOARD_HTML contract, every DOM id,
every request the frontend makes, every polling interval, and all modal/
form behavior are unchanged. The only intentional content change in this
commit is documented in ui/pages/settings.py and ui/scripts.py: removal
of the Settings page's "Trading Subsystem" retirement-status card, per
Pedro's mandatory correction that the retired Execution Bot / legacy
trading subsystem must not appear anywhere in Interface V1.

Navigation relabeling, dead-code removal, panel consolidation, the
Morning Brief addition, visual-system changes, and responsive behavior
are all deliberately deferred to later, separately-approved commits.
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
        <button class="tab-btn active" data-page="dashboard">Dashboard</button>
        <button class="tab-btn" data-page="journal">Journal</button>
        <button class="tab-btn" data-page="news">News</button>
        <button class="tab-btn" data-page="assistant">Assistant</button>
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
