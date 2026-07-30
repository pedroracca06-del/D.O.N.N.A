"""ui/pages/overview.py — Overview (dashboard) page markup.

Commit #11 correction: the page is a single vertical stack (not a
2-column grid) so its DOM order and visual reading order are identical
and unambiguous, in the approved hierarchy --
  1. Page identity and current system status (Hero, Risk badges)
  2. Deterministic Morning Brief
  3. Core account/performance summary
  4. Recent activity
  5. Supporting diagnostics (Market Driver, Primary Catalyst, Market Board)
-- correcting the prior main-column/sidebar split, where sections 2-4
rendered beside section 5 instead of before it. No existing active data
source, DOM id, or backend contract used by the retained sections
(Hero, Risk badges, Market Driver, Primary Catalyst, Market Board) was
changed -- only their position. The Morning Brief, Account Summary, and
Recent Activity panels read from already-active, already-approved
backend contracts (`GET /morning-brief` and the existing `/journal/data`
poll) -- no new route, no new provider call, no new external request.
"""
OVERVIEW_HTML = '''  <!-- ════════════════════ DASHBOARD ════════════════════ -->
  <div class="page active" id="page-dashboard">
    <div class="vstack">

      <!-- 1. PAGE IDENTITY -->
      <div style="margin-bottom:2px">
        <div style="font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px">Live Market Intelligence</div>
        <div style="font-family:'Rajdhani',sans-serif;font-size:30px;font-weight:700;letter-spacing:2px;color:var(--text)">OVERVIEW</div>
      </div>

      <!-- 1. HERO MARKET BANNER (current system status) -->
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

      <!-- 1. RISK BADGES ROW (current system status) -->
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

      <!-- 2. DETERMINISTIC MORNING BRIEF (read-only; GET /morning-brief) -->
      <div id="ovMorningBrief" class="panel">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div class="kicker" style="margin-bottom:0">MORNING BRIEF</div>
          <span id="ovMbDateLabel" style="font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2)">—</span>
        </div>
        <div id="ovMbLoading" style="font-size:12px;color:var(--muted)">Loading morning brief...</div>
        <div id="ovMbEmpty" style="display:none;font-size:12px;color:var(--muted2)">No morning brief available yet.</div>
        <div id="ovMbError" style="display:none;font-size:12px;color:#e05252"></div>
        <div id="ovMbStale" style="display:none;font-size:10px;color:var(--yellow);margin-bottom:6px;font-family:'Space Mono',monospace;letter-spacing:.5px;text-transform:uppercase">Stale — showing last available brief</div>
        <pre id="ovMbText" style="display:none;white-space:pre-wrap;font-family:'Space Mono',monospace;font-size:11px;color:var(--text);line-height:1.7;margin:0"></pre>
      </div>

      <!-- 3. CORE ACCOUNT / PERFORMANCE SUMMARY (from existing /journal/data) -->
      <div id="ovAcctSummary" class="panel">
        <div class="kicker" style="margin-bottom:10px">ACCOUNT SUMMARY</div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px">
          <div>
            <div style="font-size:9px;color:var(--muted2);font-family:'Space Mono',monospace;letter-spacing:1px;text-transform:uppercase">Today's P&amp;L</div>
            <div id="ovAcctPnl" style="font-size:18px;font-weight:700;font-family:Rajdhani,sans-serif;color:var(--muted2)">—</div>
          </div>
          <div>
            <div style="font-size:9px;color:var(--muted2);font-family:'Space Mono',monospace;letter-spacing:1px;text-transform:uppercase">Win Rate</div>
            <div id="ovAcctWinRate" style="font-size:18px;font-weight:700;font-family:Rajdhani,sans-serif;color:var(--muted2)">—</div>
          </div>
          <div>
            <div style="font-size:9px;color:var(--muted2);font-family:'Space Mono',monospace;letter-spacing:1px;text-transform:uppercase">Trades Today</div>
            <div id="ovAcctTrades" style="font-size:18px;font-weight:700;font-family:Rajdhani,sans-serif;color:var(--text)">—</div>
          </div>
          <div>
            <div style="font-size:9px;color:var(--muted2);font-family:'Space Mono',monospace;letter-spacing:1px;text-transform:uppercase">This Week</div>
            <div id="ovAcctWeek" style="font-size:18px;font-weight:700;font-family:Rajdhani,sans-serif;color:var(--muted2)">—</div>
          </div>
        </div>
      </div>

      <!-- 4. RECENT ACTIVITY (from existing /journal/data) -->
      <div id="ovRecentActivity" class="panel">
        <div class="kicker" style="margin-bottom:10px">RECENT ACTIVITY</div>
        <div id="ovRecentTrades" style="font-size:12px;color:var(--muted2)">No trades logged yet.</div>
      </div>

      <!-- 5. SUPPORTING DIAGNOSTICS: MARKET DRIVER + CATALYST -->
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

      <!-- 5. SUPPORTING DIAGNOSTICS: MARKET BOARD -->
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

    </div>
  </div>

'''
