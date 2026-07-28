"""ui/pages/market_news.py — Market & News page markup (id="page-news"),
extracted verbatim from ui/html.py during the interface-modularization
foundation (commit #9). No content, id, class, or copy change — the
module is renamed for the later IA commit; the page id inside the markup
deliberately stays "page-news" in this commit since renaming it is
explicitly deferred to the information-architecture commit.
"""
MARKET_NEWS_HTML = '''  <!-- ════════════════════ NEWS ════════════════════ -->
  <div class="page" id="page-news">
    <div class="vstack">

      <!-- LIVE FUTURES TICKER STRIP -->
      <div class="news-futures-strip">
        <div class="news-futures-label">Live</div>
        <div class="news-futures-track-wrap">
          <div class="news-futures-track" id="newsFuturesTrack">
            <span class="nf-item"><span class="nf-sym">NQ</span><span class="nf-val">—</span><span class="nf-pct">—</span></span>
          </div>
        </div>
      </div>

      <!-- BREAKING NEWS BAR -->
      <div class="breaking-bar">
        <div class="breaking-label">Breaking</div>
        <div class="breaking-ticker-wrap">
          <div class="breaking-ticker-track" id="breakingTickerTrack">
            <span class="breaking-item">Loading live headlines...</span>
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

      <!-- MAIN 2-COLUMN GRID: 70% left / 30% right -->
      <div class="news-layout">

        <!-- ─── LEFT COLUMN ─── -->
        <div class="vstack" style="gap:14px">

          <!-- 1. LIVE FEED -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:12px">Live Feed</div>
            <div id="newsList"><div class="obs-item low"><div class="obs-body">Loading headlines...</div></div></div>
          </div>

        </div>

        <!-- ─── RIGHT SIDEBAR 30% ─── -->
        <div class="vstack" style="gap:14px">

          <!-- 1. RISK LEVELS -->
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

          <!-- 2b. NOVA MARKET SUMMARY (manual-only, NOVA Intelligence V1 -- never auto-called) -->
          <div class="panel" id="novaMarketSummaryPanel">
            <div class="kicker" style="margin-bottom:10px">NOVA Market Summary</div>
            <button class="nova-gen-btn" id="novaMarketSummaryBtn" onclick="generateMarketSummary()">Generate NOVA Summary</button>
            <div id="novaMarketSummaryLoading" style="display:none;font-size:11px;color:var(--muted);margin-top:8px">Generating summary...</div>
            <div id="novaMarketSummaryText" style="display:none;font-size:12px;color:var(--text);line-height:1.6;margin-top:8px"></div>
            <div id="novaMarketSummaryError" style="display:none;font-size:11px;color:#e05252;margin-top:8px"></div>
          </div>

          <!-- 3. MACRO RADAR -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">Macro Radar</div>
            <div id="sidebarEconCalendar2"><div class="econ-no-events">Loading events...</div></div>
          </div>

          <!-- 4. TRENDING MOVERS (compact vertical list) -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">Trending Movers</div>
            <div class="movers-col-title gainers" style="margin-bottom:6px">▲ Gainers</div>
            <div id="moversGainers"><div class="mover-row"><span class="mover-sym" style="color:var(--muted2)">Loading...</span></div></div>
            <div style="border-top:1px solid var(--line);margin:10px 0"></div>
            <div class="movers-col-title losers" style="margin-bottom:6px">▼ Losers</div>
            <div id="moversLosers"><div class="mover-row"><span class="mover-sym" style="color:var(--muted2)">Loading...</span></div></div>
          </div>

          <!-- 5. NOVA SAYS -->
          <div class="donna-says-box">
            <div class="donna-says-label">NOVA Says</div>
            <div class="donna-says-text" id="donnaSaysText">Monitoring market conditions...</div>
          </div>

        </div>

      </div>

    </div>
  </div>

'''
