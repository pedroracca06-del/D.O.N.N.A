"""ui/pages/overview.py — Overview (dashboard) page markup.

Approved command-center composition (design-review round, 2026-08):
  1. Page identity (kicker + title)
  2. Flat market-status rail -- Macro Risk / Session / Regime / Market Tone
     (not four equal-weight KPI cards)
  3. Hero: one surface, two panes --
       left  = deterministic Morning Brief (the primary intelligence surface)
       right = NQ session-structure level ladder (PDH/PDL/ONH/ONL/PWH + current
               price), sourced from the already-active GET /market-structure
               and GET /liquidity engines. This is the one new frontend read
               this commit adds -- both routes already exist and are already
               used elsewhere in the app; Overview did not consume them before.
               No new backend endpoint, no new provider call.
  4. Secondary band: one surface, three regions --
       Performance (Account Summary + Recent Activity, unified) |
       Market Driver | Primary Catalyst (Supporting Diagnostics)
  5. Market Board as a flat quote-board rail (not five tiles inside a card)

Data-honesty note (rail sub-captions): the approved mockup showed four
independent-looking descriptive captions ("No red-folder lock", "Momentum:
strong", "Breadth confirming", etc). Real NOVA state does not carry four
independent dimensions here -- Regime and Market Tone are the SAME
underlying `regime` signal (a short code plus its existing human-readable
sentence, both already computed by renderDashboard()). Rather than invent
descriptive strings with no backing data, this implementation reuses the
two real, already-existing fields (dbRegimeText, dbMarketTone) across the
Regime/Market Tone cells, and reuses dbBadgeMacro/dbMacroPosture and
dbBadgeSession/dbSessionLabel (all real, already-computed) for the other
two. See ui/scripts.py renderDashboard() for exactly what populates each.

Every id that existed before this pass (dbHero, dbRegimeText, dbMarketTone,
dbSessionLabel, dbMacroPosture, dbBadgeMacro, dbBadgeSession, dbDriverPrimary,
dbDriverRegime, dbDriverBullets, dbCatalystHeadline, dbCatalystSummary,
dbCatalystSentiment, dbMarketBoard + its 5 .db-market-tile[data-sym]
children, ovMorningBrief + its 6 state ids, ovAcctSummary + its 4 value ids,
ovAcctTrades, ovRecentActivity, ovRecentTrades) is unchanged -- same id,
same backend contract, same JS function in ui/scripts.py populating it.
Only the surrounding markup, classes, and visual composition changed.
`dbDriverPrimary` is kept in the DOM (hidden) since renderDashboard() still
writes to it, but the approved composition shows the regime line + bullets,
not a repeated headline. New ids added for the session-structure region
(ovStructPx/ovStructChg/ovLadder/ovStructFresh) are additive; see
ui/scripts.py's renderMarketStructure() for what populates them.
"""
OVERVIEW_HTML = '''  <!-- ════════════════════ DASHBOARD ════════════════════ -->
  <div class="page active" id="page-dashboard">
    <div class="vstack">

      <!-- 1. PAGE IDENTITY
           Carries the approved online/version treatment inline with the page
           title (NOT the rejected legacy .content-header band). The status
           chip shows genuine backend connection state set by
           _ovSetConnection(); the version string is the application's own
           5.0, the same constant main.py passes to FastAPI(version=...). -->
      <div class="ov-page-id">
        <div class="ov-id-left">
          <div class="ov-kicker">Live Market Intelligence</div>
          <h1>Overview</h1>
        </div>
        <div class="ov-id-right">
          <span class="ov-conn connecting" id="ovIdentityStatus"><span class="d"></span>Connecting…</span>
          <span class="ov-ver">v5.0 // LIVE MARKET CORE</span>
        </div>
      </div>

      <!-- dbHero: kept as a non-visual anchor. No JS writes to this id itself
           (only to its former children, all relocated into the rail below);
           kept present only so nothing that ever looked it up 404s. -->
      <div id="dbHero" style="display:none" aria-hidden="true"></div>

      <!-- 2. STATUS RAIL (current system status; unchanged ids, restyled as a flat rail) -->
      <!-- Status dots carry NO hard-coded colour. Each one is painted by
           renderDashboard() from the actual state it represents, and every
           cell's state is also stated in words (the .v value line) so the
           rail reads correctly with colour ignored entirely. Session is
           informational, not a risk grade, so it keeps a fixed neutral
           accent rather than implying a good/bad reading. -->
      <div class="ov-rail" id="dbBadges">
        <div class="ri">
          <div class="l"><span class="d" id="ovDotMacro"></span>Macro Risk</div>
          <div class="v" id="dbBadgeMacro" style="color:var(--muted)">—</div>
          <div class="s" id="dbMacroPosture">—</div>
        </div>
        <div class="ri">
          <div class="l"><span class="d neutral" id="ovDotSession"></span>Session</div>
          <div class="v" id="dbBadgeSession" style="color:var(--muted)">—</div>
          <div class="s" id="dbSessionLabel">—</div>
        </div>
        <div class="ri">
          <div class="l"><span class="d" id="ovDotRegime"></span>Regime</div>
          <div class="v" id="dbRegimeText" style="color:var(--muted)">—</div>
          <div class="s" id="dbDriverRegime">—</div>
        </div>
        <div class="ri">
          <!-- Market Tone is not an independent signal: it is the same
               `regime` code rendered as prose. Labelled as derived so the
               rail cannot be misread as four independent dimensions. -->
          <div class="l"><span class="d" id="ovDotTone"></span>Market Tone<span class="drv">derived from Regime</span></div>
          <div class="v" id="dbMarketToneShort">—</div>
          <div class="s" id="dbMarketTone">—</div>
        </div>
      </div>

      <!-- 3. HERO: Morning Brief (primary intelligence surface) + session structure -->
      <div class="ov-hero">
        <section class="ov-brief" id="ovMorningBrief" aria-labelledby="ovMbTitle">
          <!-- Provenance rides the section kicker (approved treatment:
               "MORNING BRIEF  Today · 08:32 ET · Deterministic engine")
               rather than consuming its own content line below the brief.
               The disclosure is unchanged in wording, only relocated;
               #ovMbDateLabel still holds nothing but the endpoint's
               date_label, so setText() keeps working untouched. -->
          <div class="ov-sl">
            <h2 class="name" id="ovMbTitle">Morning Brief</h2>
            <span class="meta"><span id="ovMbDateLabel">—</span> · Deterministic engine · no AI call</span>
          </div>
          <div id="ovMbLoading" class="ov-none">Loading morning brief…</div>
          <div id="ovMbEmpty" class="ov-none" style="display:none">No morning brief available yet.</div>
          <div id="ovMbError" class="ov-err" style="display:none" role="alert"></div>
          <div id="ovMbStale" class="ov-fresh stale" style="display:none;margin-bottom:8px"><span class="fd"></span>Stale — showing last available brief</div>
          <!-- Headline = the engine's real `thesis` field (or, absent that, a
               deterministically promoted first line). Body renders as
               proportional paragraphs, not a monospace <pre> block. -->
          <h3 class="ov-mb-headline" id="ovMbHeadline" style="display:none"></h3>
          <div class="ov-brief-body" id="ovMbText" style="display:none"></div>
          <!-- Facts footer, built only from fields the endpoint returns. -->
          <div class="ov-mb-footer" id="ovMbFooter" style="display:none"></div>
        </section>
        <section class="ov-structure" id="ovStructure" aria-labelledby="ovStructTitle">
          <div class="ov-sl">
            <h2 class="name" id="ovStructTitle">NQ Session Structure</h2>
          </div>
          <!-- Freshness sits inline with the price/status area, as the
               approved reference shows, instead of wrapping onto its own
               line under the heading. Same element, same id, same class
               vocabulary -- _ovSetFreshness() is unchanged, and the state it
               reports is still derived only from the producing engine's
               timestamp. -->
          <div class="ov-px-now">
            <span class="sym">NQ</span>
            <span class="px" id="ovStructPx">—</span>
            <span class="chg" id="ovStructChg"></span>
            <span id="ovStructFresh" class="ov-fresh loading"><span class="fd"></span>Checking…</span>
          </div>
          <div class="ov-ladder" id="ovLadder">
            <div class="ov-none" style="padding-top:8px">Loading session structure…</div>
          </div>
        </section>
      </div>

      <!-- 4. SECONDARY BAND: Performance (unified) | Market Driver | Primary Catalyst -->
      <div class="ov-second">
        <section class="ov-region" id="ovAcctSummary" aria-labelledby="ovPerfTitle">
          <h2 class="rl" id="ovPerfTitle">Performance</h2>
          <div class="ov-pnl-line">
            <span class="big" id="ovAcctPnl" style="color:var(--muted2)">—</span>
            <span class="lab">Today's P&amp;L</span>
          </div>
          <div class="ov-perf-sub">
            This week <b id="ovAcctWeek">—</b> ·
            Trades today <b id="ovAcctTrades">—</b> ·
            Win rate <b id="ovAcctWinRate">—</b>
          </div>
          <div class="ov-act-list" id="ovRecentActivity">
            <div id="ovRecentTrades" class="ov-none">No trades logged yet.</div>
          </div>
        </section>
        <section class="ov-region" aria-labelledby="ovDriverTitle">
          <h2 class="rl" id="ovDriverTitle">Market Driver</h2>
          <!-- Approved hierarchy: the real dominant-driver headline is now
               VISIBLE above the bullets (it was previously written to this
               node while it was hidden, and thrown away). -->
          <div class="ov-drv-head" id="dbDriverPrimary">—</div>
          <ul class="ov-drv" id="dbDriverBullets"><li class="ov-none">Loading market driver…</li></ul>
        </section>
        <section class="ov-region" aria-labelledby="ovCatTitle">
          <h2 class="rl" id="ovCatTitle">Primary Catalyst</h2>
          <div class="ov-cat-h" id="dbCatalystHeadline">Loading catalyst…</div>
          <!-- Collapses entirely when guidance is absent; no stray dash. -->
          <div class="ov-cat-p" id="dbCatalystSummary" style="display:none"></div>
          <div class="ov-sent-badge" id="dbCatalystSentiment">Sentiment unavailable</div>
        </section>
      </div>

      <!-- 5. MARKET BOARD: flat quote-board rail -->
      <section class="ov-board" aria-labelledby="ovBoardTitle">
        <!-- Freshness starts as "Checking…" and is only ever set from an
             upstream producer timestamp by renderDashboard(); it is never
             assumed live just because a request succeeded. -->
        <div class="bl"><h2 id="ovBoardTitle">Market Board</h2> <span class="ov-fresh loading" id="ovBoardFresh"><span class="fd"></span>Checking…</span></div>
        <div class="ov-quotes" id="dbMarketBoard">
          <div class="db-market-tile" data-sym="NQ">
            <div class="db-tile-sym">NQ</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="db-market-tile" data-sym="ES">
            <div class="db-tile-sym">ES</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="db-market-tile" data-sym="VIX">
            <div class="db-tile-sym">VIX</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="db-market-tile" data-sym="DXY">
            <div class="db-tile-sym">DXY</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="db-market-tile" data-sym="GOLD">
            <div class="db-tile-sym">GOLD</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
        </div>
      </section>

    </div>
  </div>

'''
