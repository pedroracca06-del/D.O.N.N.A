"""ui/pages/overview.py — Overview (dashboard) page markup, extracted
verbatim from ui/html.py during the interface-modularization foundation
(commit #9). No content, id, class, or copy change.
"""
OVERVIEW_HTML = '''  <!-- ════════════════════ DASHBOARD ════════════════════ -->
  <div class="page active" id="page-dashboard">
    <div style="display:grid;grid-template-columns:1fr 300px;gap:16px;align-items:start">

      <!-- ── LEFT MAIN COLUMN ── -->
      <div class="vstack">

        <!-- 1. HERO MARKET BANNER -->
        <div id="dbHero" class="card" style="padding:22px 26px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:20px">
            <div class="db-hero-left">
              <div id="dbRegimeText" style="font-size:32px;font-weight:700;font-family:Rajdhani,sans-serif;letter-spacing:.5px;color:var(--muted)">—</div>
              <div id="dbMarketTone" style="margin-top:5px;font-size:13px;color:var(--muted);line-height:1.4">—</div>
              <div id="dbSessionLabel" style="margin-top:12px;font-size:11px;color:var(--muted2);font-family:Space Mono,monospace">—</div>
            </div>
            <div class="db-hero-right">
              <div id="dbMacroPosture" class="db-posture-badge">—</div>
            </div>
          </div>
        </div>

        <!-- 2. RISK BADGES ROW -->
        <div id="dbBadges" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="card db-badge-card">
            <div class="db-badge-label">MACRO RISK</div>
            <div class="db-badge-value" id="dbBadgeMacro" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-badge-card">
            <div class="db-badge-label">SESSION</div>
            <div class="db-badge-value" id="dbBadgeSession" style="color:var(--muted)">—</div>
          </div>
        </div>

        <!-- 3. MARKET DRIVER PANEL -->
        <div id="dbDriver" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">MARKET DRIVER</div>
            <div id="dbDriverPrimary" style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:5px;line-height:1.3">—</div>
            <div id="dbDriverRegime" style="font-size:11px;color:var(--muted2);margin-bottom:10px;font-family:Space Mono,monospace">—</div>
            <ul id="dbDriverBullets" style="margin:0;padding-left:16px;font-size:12px;color:var(--muted);line-height:1.7"></ul>
          </div>
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">PRIMARY CATALYST</div>
            <div id="dbCatalystHeadline" style="font-size:14px;font-weight:700;color:var(--text);line-height:1.3;margin-bottom:8px">—</div>
            <div id="dbCatalystSummary" style="font-size:12px;color:var(--muted);line-height:1.55;margin-bottom:10px">—</div>
            <div id="dbCatalystSentiment" style="display:inline-block;padding:3px 10px;border-radius:4px;font-family:Space Mono,monospace;font-size:10px;font-weight:700;background:var(--panel2);color:var(--muted2)">—</div>
          </div>
        </div>

        <!-- 5. MARKET BOARD -->
        <div id="dbMarketBoard" style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px">
          <div class="card db-market-tile" data-sym="NQ">
            <div class="db-tile-sym">NQ</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-market-tile" data-sym="ES">
            <div class="db-tile-sym">ES</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-market-tile" data-sym="VIX">
            <div class="db-tile-sym">VIX</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-market-tile" data-sym="DXY">
            <div class="db-tile-sym">DXY</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-market-tile" data-sym="GOLD">
            <div class="db-tile-sym">GOLD</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
        </div>

      </div><!-- end left column -->

      <!-- ── RIGHT SIDEBAR ── -->
      <div class="vstack">


        <!-- ECONOMIC CALENDAR -->
        <div id="dbCalendar" class="panel">
          <div class="kicker" style="margin-bottom:10px">MACRO RADAR</div>
          <div id="sidebarEconCalendar"></div>
        </div>

        <!-- NOVA SAYS -->
        <div id="dbDonnaSays" class="panel">
          <div class="kicker" style="margin-bottom:8px">NOVA SAYS</div>
          <div id="dbDonnaSaysText" style="font-size:13px;color:var(--text);line-height:1.65">—</div>
        </div>

      </div><!-- end sidebar -->

    </div>
  </div>

'''
