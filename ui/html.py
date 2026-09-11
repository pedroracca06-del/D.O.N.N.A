"""ui/html.py — DASHBOARD_HTML composer.

Commit #9 split the former ~3900-line inline monolith into the modules
below. Commit #11 changed only the nav buttons' visible text (Dashboard
-> Overview, News -> Markets, Assistant -> NOVA Intelligence); every
`data-page`/`id="page-*"` value, route, and backend contract stayed
unchanged. See ui/pages/overview.py and ui/pages/market_news.py for the
rest of #11 (Morning Brief, Macro Radar / NOVA Says consolidation).

Commit #12 (visual-system shell checkpoint): sidebar (desktop) /
compact-bar (tablet) / bottom-bar (mobile) responsive shell, dark-
authoritative tokens, CSS-only nav icons. `data-page` values, button
text, and click semantics unchanged -- only container markup/
positioning changed. No external font/icon/CDN request. Page-specific
redesigns remain deferred.
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
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%23050505'/%3E%3Cpath d='M16 46V18h7l18 20V18h7v28h-7L23 26v20z' fill='%23c59b51'/%3E%3C/svg%3E" />
<style>
'''
    + DASHBOARD_CSS +
    '''</style>
</head>
<body>
<div class="app-shell">

  <!-- SIDEBAR / RESPONSIVE NAV (desktop: left sidebar, tablet: compact bar, mobile: bottom bar) -->
  <nav class="sidebar" aria-label="Primary">
    <div class="sidebar-brand">
      <span class="sidebar-mark" aria-hidden="true"></span>
      <span class="sidebar-brand-text">
        <span class="sidebar-wordmark">NOVA</span>
        <span class="sidebar-subtitle">Market Intelligence</span>
      </span>
    </div>
    <div class="nav">
      <button class="tab-btn active" data-page="dashboard" aria-current="page">Overview</button>
      <button class="tab-btn" data-page="journal">Journal</button>
      <button class="tab-btn" data-page="news">News</button>
      <button class="tab-btn" data-page="assistant">NOVA Intelligence</button>
      <button class="tab-btn" data-page="settings">Settings</button>
    </div>
    <!-- Backend connection state, set by _ovSetConnection() from the actual
         /dashboard-data cycle. Deliberately NOT a hard-coded "All systems
         normal": the frontend cannot substantiate a whole-system health
         claim, so it reports only what it can prove. -->
    <button class="theme-toggle" id="themeToggle" type="button" aria-label="Switch color mode">◐ &nbsp;Light mode</button>
    <div class="sidebar-status connecting" id="sidebarStatus"><span class="d"></span>Connecting…</div>
  </nav>

  <div class="main-content">
  <div class="wrap">

  <!-- CONTENT HEADER -->
  <div class="content-header">
    <span class="brand-tag">v5.0 // LIVE MARKET CORE</span>
    <div class="status-badge"><span class="dot"></span>ONLINE</div>
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
  </div>

</div>

<script>
'''
    + DASHBOARD_SCRIPT +
    '''</script>
</body>
</html>'''
)
