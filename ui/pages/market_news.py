"""ui/pages/market_news.py — Markets page markup (id="page-news", kept
unchanged internally so no route, loop or renderer outside this page has to
change).

The approved composition (artifact 55c387a4, screenshots #1 live and #3
cached) replaces the previous vertical stack of cards with one analytical
workspace:

  1. Markets identity, freshness and clock
  2. Session and risk rail
  3. Cross-Asset Pulse          | 4. Volatility & Direction
     (spans both right rows)    | 5. News & Catalysts
  6. Market Structure — full width beneath both columns
  7. Sources / provenance

Both marquees are gone. The futures ticker and the five editable index tiles
are absorbed into Cross-Asset Pulse, which merges /futures-macro-pulse and
/major-indexes and de-duplicates on symbol; the breaking bar folds into News &
Catalysts. A price you have to wait for is a price you cannot scan.

Every legacy DOM id those features used is preserved in #mkLegacy below.
renderNews(), refreshTilePrefs(), renderEconCalendar() and
refreshTrendingMovers() are called from the global 30s/5min loops and from
Overview's code path -- they must keep finding their targets and succeeding.
Nothing outside this page changed.
"""
MARKET_NEWS_HTML = '''  <!-- ════════════════════ MARKETS ════════════════════ -->
  <div class="page" id="page-news">
    <div class="mk-wrap">

      <!-- 1. IDENTITY / FRESHNESS -->
      <div class="mk-id">
        <div class="mk-id-left">
          <div class="mk-kicker">Market Intelligence</div>
          <h1 class="mk-title">Markets</h1>
        </div>
        <div class="mk-id-meta">
          <span class="mk-fresh connecting" id="mkFresh">Connecting&hellip;</span>
          <span class="mk-clock" id="mkClock">&mdash;</span>
          <button class="mk-action" id="novaMarketSummaryBtn" type="button"
                  onclick="generateMarketSummary()"
                  aria-expanded="false" aria-controls="novaMarketSummaryPanel"
                  aria-label="Generate a NOVA market summary">Generate NOVA Summary</button>
        </div>
      </div>

      <!-- NOVA MARKET SUMMARY — manual only, never auto-called. Collapsed with
           the `hidden` attribute until the reader asks for one, so the approved
           geometry is untouched at rest. The click handler reveals the panel
           BEFORE writing to it, so the polite live region is already in the
           accessibility tree when the result lands.

           The handler name is deliberately not repeated in this comment: a
           test counts its occurrences across the whole dashboard to prove the
           feature has no automatic caller. -->
      <div class="mk-summary" id="novaMarketSummaryPanel" hidden>
        <div class="mk-sum-head">NOVA Market Summary</div>
        <div class="mk-sum-body" role="status" aria-live="polite">
          <div id="novaMarketSummaryLoading" style="display:none">Generating summary&hellip;</div>
          <div id="novaMarketSummaryText" style="display:none"></div>
          <div id="novaMarketSummaryError" style="display:none"></div>
        </div>
      </div>

      <div class="mk-grid">

        <!-- 2. SESSION + RISK RAIL -->
        <div class="mk-rail" id="mkRail" aria-label="Session and risk posture">
          <div class="mk-cell">
            <div class="mk-ck">Session</div>
            <div class="mk-cv" id="mkSession">&mdash;<small id="mkSessionSub"></small></div>
          </div>
          <div class="mk-cell">
            <div class="mk-ck">Macro risk</div>
            <div id="mkMacroRisk"><span class="mk-badge none">&mdash;</span></div>
          </div>
          <div class="mk-cell">
            <div class="mk-ck">Headline risk</div>
            <div id="mkHeadlineRisk"><span class="mk-badge none">&mdash;</span></div>
          </div>
          <div class="mk-cell">
            <div class="mk-ck">Market risk</div>
            <div id="mkMarketRisk"><span class="mk-badge none">&mdash;</span></div>
          </div>
          <div class="mk-cell">
            <div class="mk-ck">Event phase</div>
            <div class="mk-cv mk-cv-sm" id="mkEventPhase">&mdash;<small id="mkNextEvent"></small></div>
          </div>
        </div>

        <!-- 3. CROSS-ASSET PULSE -->
        <section class="mk-panel mk-pulse" aria-labelledby="mkPulseTitle">
          <div class="mk-ph">
            <h2 id="mkPulseTitle">Cross-asset pulse</h2>
            <span class="mk-sub" id="mkPulseMeta">&mdash;</span>
          </div>
          <div class="mk-pulse-body" id="mkPulseBody">
            <div class="mk-skel-rows"><i></i><i></i><i></i><i></i></div>
          </div>
          <div class="mk-foot" id="mkPulseFoot"></div>
        </section>

        <!-- 4. VOLATILITY & DIRECTION -->
        <section class="mk-panel mk-vol" aria-labelledby="mkVolTitle">
          <div class="mk-ph">
            <h2 id="mkVolTitle">Volatility &amp; direction</h2>
            <span class="mk-sub" id="mkVolMeta">&mdash;</span>
          </div>
          <div id="mkVolBody"><div class="mk-skel-rows"><i></i><i></i><i></i></div></div>
        </section>

        <!-- 5. NEWS & CATALYSTS -->
        <section class="mk-panel mk-news" aria-labelledby="mkNewsTitle">
          <div class="mk-ph">
            <h2 id="mkNewsTitle">News &amp; catalysts</h2>
            <span class="mk-sub" id="mkNewsMeta">&mdash;</span>
          </div>
          <div id="mkNewsBody"><div class="mk-skel-rows"><i></i><i></i><i></i></div></div>
        </section>

        <!-- 6. MARKET STRUCTURE — full width -->
        <section class="mk-panel mk-struct" aria-labelledby="mkStructTitle">
          <div class="mk-ph">
            <h2 id="mkStructTitle"><span id="mkStructSym">NQ</span> &middot; market structure</h2>
            <span class="mk-switch" role="group" aria-label="Instrument">
              <button type="button" data-mk-sym="NQ" aria-pressed="true">NQ</button>
              <button type="button" data-mk-sym="ES" aria-pressed="false">ES</button>
            </span>
          </div>
          <div id="mkStructBody"><div class="mk-skel-rows"><i></i><i></i><i></i></div></div>
        </section>

        <!-- 7. SOURCES / PROVENANCE -->
        <div class="mk-prov" id="mkProv" aria-label="Data sources"></div>

      </div>
    </div>

    <!-- ══ LEGACY TARGETS ═══════════════════════════════════════════════
         Not rendered. renderNews(), refreshTilePrefs(), renderEconCalendar()
         and refreshTrendingMovers() run on the global loops and also feed
         Overview; they keep writing here so none of them has to change and
         none of them starts throwing. -->
    <div id="mkLegacy" hidden aria-hidden="true">
      <div class="news-futures-track" id="newsFuturesTrack"></div>
      <div class="index-tiles" id="indexTiles">
        <div class="index-tile"><button class="tile-edit-btn" tabindex="-1" aria-hidden="true" title="Change symbol">&#9998;</button><div class="index-tile-name">NQ</div><div class="index-tile-val">&mdash;</div><div class="index-tile-chg">&mdash;</div></div>
        <div class="index-tile"><button class="tile-edit-btn" tabindex="-1" aria-hidden="true" title="Change symbol">&#9998;</button><div class="index-tile-name">ES</div><div class="index-tile-val">&mdash;</div><div class="index-tile-chg">&mdash;</div></div>
        <div class="index-tile"><button class="tile-edit-btn" tabindex="-1" aria-hidden="true" title="Change symbol">&#9998;</button><div class="index-tile-name">VIX</div><div class="index-tile-val">&mdash;</div><div class="index-tile-chg">&mdash;</div></div>
        <div class="index-tile"><button class="tile-edit-btn" tabindex="-1" aria-hidden="true" title="Change symbol">&#9998;</button><div class="index-tile-name">DXY</div><div class="index-tile-val">&mdash;</div><div class="index-tile-chg">&mdash;</div></div>
        <div class="index-tile"><button class="tile-edit-btn" tabindex="-1" aria-hidden="true" title="Change symbol">&#9998;</button><div class="index-tile-name">GOLD</div><div class="index-tile-val">&mdash;</div><div class="index-tile-chg">&mdash;</div></div>
      </div>
      <div id="sidebarEconCalendar2"></div>
      <div class="breaking-ticker-track" id="breakingTickerTrack"></div>
      <div id="newsList"></div>
      <span id="sidebarMacroRisk" class="risk-badge risk-medium">MEDIUM</span>
      <span id="sidebarHeadlineRisk" class="risk-badge risk-medium">MEDIUM</span>
      <span id="sidebarMarketRisk" class="risk-badge risk-medium">MEDIUM</span>
      <span id="sidebarEventPhase">&mdash;</span>
      <div id="sidebarNextEvent">&mdash;</div>
      <div id="moversGainers"></div>
      <div id="moversLosers"></div>
    </div>

  </div>

'''
