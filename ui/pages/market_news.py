"""ui/pages/market_news.py — Markets page markup (id="page-news", kept
unchanged internally per commit #11's "don't rename internal ids unless
strictly necessary" instruction -- only the nav's visible label changed,
in ui/html.py).

Commit #11 correction: the entire page (not just the sidebar) is now a
single vertical stack in the approved reading order --
  1. Market summary and major market context (futures ticker, index
     tiles, NOVA Market Summary)
  2. Macro Radar
  3. News Guard / active news feed (breaking ticker, Live Feed)
  4. Supporting market data (Risk Levels, Trending Movers)
-- so a reader scanning top-to-bottom sees one coherent order instead of
two parallel columns racing each other. A page-identity heading
("MARKETS") was added, matching Overview/Journal/Settings. No active
data source, DOM id, or route used by any panel changed -- only page
position and the removal of the old `.news-layout` 7fr/3fr column split
(Risk Levels and Trending Movers keep a same-level 1fr/1fr pairing
inside section 4 only, since they are both "supporting data" and do not
compete with the page's primary reading order).
"""
MARKET_NEWS_HTML = '''  <!-- ════════════════════ NEWS ════════════════════ -->
  <div class="page" id="page-news">
    <div class="vstack">

      <!-- PAGE IDENTITY -->
      <div style="margin-bottom:2px">
        <div style="font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px">Live Market Intelligence</div>
        <div style="font-family:'Rajdhani',sans-serif;font-size:30px;font-weight:700;letter-spacing:2px;color:var(--text)">MARKETS</div>
      </div>

      <!-- 1. MARKET SUMMARY & MAJOR MARKET CONTEXT -->

      <!-- LIVE FUTURES TICKER STRIP -->
      <div class="news-futures-strip">
        <div class="news-futures-label">Live</div>
        <div class="news-futures-track-wrap">
          <div class="news-futures-track" id="newsFuturesTrack">
            <span class="nf-item"><span class="nf-sym">NQ</span><span class="nf-val">—</span><span class="nf-pct">—</span></span>
          </div>
        </div>
      </div>

      <!-- 5 INDEX TILES (customizable) -->
      <div class="index-tiles" id="indexTiles">
        <div class="index-tile"><button class="tile-edit-btn" title="Change symbol">✎</button><div class="index-tile-name">NQ</div><div class="index-tile-val">—</div><div class="index-tile-chg">—</div></div>
        <div class="index-tile"><button class="tile-edit-btn" title="Change symbol">✎</button><div class="index-tile-name">ES</div><div class="index-tile-val">—</div><div class="index-tile-chg">—</div></div>
        <div class="index-tile"><button class="tile-edit-btn" title="Change symbol">✎</button><div class="index-tile-name">VIX</div><div class="index-tile-val">—</div><div class="index-tile-chg">—</div></div>
        <div class="index-tile"><button class="tile-edit-btn" title="Change symbol">✎</button><div class="index-tile-name">DXY</div><div class="index-tile-val">—</div><div class="index-tile-chg">—</div></div>
        <div class="index-tile"><button class="tile-edit-btn" title="Change symbol">✎</button><div class="index-tile-name">GOLD</div><div class="index-tile-val">—</div><div class="index-tile-chg">—</div></div>
      </div>

      <!-- MARKET SUMMARY (manual-only, NOVA Intelligence V1 -- never auto-called;
           the one active NOVA-generated market-interpretation presentation) -->
      <div class="panel" id="novaMarketSummaryPanel">
        <div class="kicker" style="margin-bottom:10px">NOVA Market Summary</div>
        <button class="nova-gen-btn" id="novaMarketSummaryBtn" onclick="generateMarketSummary()">Generate NOVA Summary</button>
        <div id="novaMarketSummaryLoading" style="display:none;font-size:11px;color:var(--muted);margin-top:8px">Generating summary...</div>
        <div id="novaMarketSummaryText" style="display:none;font-size:12px;color:var(--text);line-height:1.6;margin-top:8px"></div>
        <div id="novaMarketSummaryError" style="display:none;font-size:11px;color:#e05252;margin-top:8px"></div>
      </div>

      <!-- 2. MACRO RADAR (the one active Macro Radar presentation) -->
      <div class="panel">
        <div class="kicker" style="margin-bottom:10px">Macro Radar</div>
        <div id="sidebarEconCalendar2"><div class="econ-no-events">Loading events...</div></div>
      </div>

      <!-- 3. NEWS GUARD / ACTIVE NEWS FEED -->

      <!-- BREAKING NEWS BAR -->
      <div class="breaking-bar">
        <div class="breaking-label">Breaking</div>
        <div class="breaking-ticker-wrap">
          <div class="breaking-ticker-track" id="breakingTickerTrack">
            <span class="breaking-item">Loading live headlines...</span>
          </div>
        </div>
      </div>

      <!-- LIVE FEED -->
      <div class="panel">
        <div class="kicker" style="margin-bottom:12px">Live Feed</div>
        <div id="newsList"><div class="obs-item low"><div class="obs-body">Loading headlines...</div></div></div>
      </div>

      <!-- 4. SUPPORTING MARKET DATA -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">

        <!-- RISK LEVELS (News Guard output) -->
        <div class="panel">
          <div class="kicker" style="margin-bottom:10px">Risk Levels</div>
          <div class="risk-level-row">
            <span class="risk-level-label">Macro</span>
            <span id="sidebarMacroRisk" class="risk-badge risk-medium">MEDIUM</span>
          </div>
          <div class="risk-level-row">
            <span class="risk-level-label">Headline</span>
            <span id="sidebarHeadlineRisk" class="risk-badge risk-medium">MEDIUM</span>
          </div>
          <div class="risk-level-row">
            <span class="risk-level-label">Market</span>
            <span id="sidebarMarketRisk" class="risk-badge risk-medium">MEDIUM</span>
          </div>
          <div class="risk-level-row" style="border-bottom:none">
            <span class="risk-level-label">Event Phase</span>
            <span id="sidebarEventPhase" style="font-family:'Rajdhani',sans-serif;font-size:14px;font-weight:700;color:var(--yellow)">—</span>
          </div>
          <div id="sidebarNextEvent" style="font-size:11px;color:var(--muted);margin-top:6px;padding-top:6px;border-top:1px solid var(--line2)">—</div>
        </div>

        <!-- TRENDING MOVERS (compact vertical list) -->
        <div class="panel">
          <div class="kicker" style="margin-bottom:10px">Trending Movers</div>
          <div class="movers-col-title gainers" style="margin-bottom:6px">▲ Gainers</div>
          <div id="moversGainers"><div class="mover-row"><span class="mover-sym" style="color:var(--muted2)">Loading...</span></div></div>
          <div style="border-top:1px solid var(--line);margin:10px 0"></div>
          <div class="movers-col-title losers" style="margin-bottom:6px">▼ Losers</div>
          <div id="moversLosers"><div class="mover-row"><span class="mover-sym" style="color:var(--muted2)">Loading...</span></div></div>
        </div>

      </div>

    </div>
  </div>

'''
