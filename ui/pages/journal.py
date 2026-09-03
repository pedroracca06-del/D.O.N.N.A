"""ui/pages/journal.py — Journal page markup (id="page-journal") plus the
Trade Detail and Log Trade modals.

Approved composition (artifact b22fcc6b frame 2 desktop, f1b6ec63 frames 4-6
mobile), implemented in place of the previous tabbed card stack:

  1. Page identity + primary action (Log Trade)
  2. Compact performance rail -- five flat cells, dividers, no card chrome
  3. Filter chips
  4. Two balanced columns:
       left  = selectable trade ledger -> ledger footer -> daily P&L
       right = master-detail trade review -> performance breakdown
  5. Mobile: the same regions stack in task order -- ledger, selected-trade
     review, daily P&L, then supporting breakdown -- while ledger rows collapse
     to compact summaries.

The analytical blocks are split between the two columns so neither side turns
into a tall strip of unused space when the ledger and review have different
amounts of content.

DATA HONESTY
Every figure is read from GET /journal/data -- `trades` (the genuine records)
and `stats` (core.state.compute_journal_stats). Nothing on this page is
invented. Regions the stored records cannot support render the approved
explicit unavailable state instead of a placeholder value:

  * Reasoning timeline, NOVA review and chart snapshot appear only when the
    selected record genuinely carries them.
  * Win rate always displays its sample size; a 100% rate from a single trade
    is shown as a low-sample reading, never as a headline.
  * Profit factor is blank-with-reason when there are no losing trades --
    compute_journal_stats returns 0.0 in that case, and rendering "0.00"
    would read as catastrophic performance rather than "not yet meaningful".

IDS PRESERVED
Every id the previous markup exposed to ui/scripts.py is still present, so no
JS lookup 404s: jOpenModal, jOvTrades/jOvPnl/jOvEvals/jOvWinRate/jOvPF/jOvWeek,
jTabCount-trades, jTabCount-signals, jFilterBar, journalCardList,
jSigFilterBar, jSignalFeedList, and the analytics ids (jaExpectancy,
jaTotalTrades, jaWinRate, jaWRSub, jaPF, jaAvgWL, jaAvgWin, jaAvgLoss,
setupTypeGrid, sessionBreakdownGrid, regimeBreakdownGrid,
behavioralAnalyticsGrid, emotionalAnalyticsGrid). The ones the approved
composition no longer surfaces are kept in a hidden legacy container rather
than deleted, so renderSignalFeed() and the analytics renderer keep writing
successfully while the visible page follows the approved design.
"""
JOURNAL_HTML = '''  <!-- ════════════════════ JOURNAL ════════════════════ -->
  <div class="page" id="page-journal">
    <div class="vstack">

      <!-- 1. PAGE IDENTITY + PRIMARY ACTION -->
      <div class="jn-page-id">
        <div class="jn-id-left">
          <div class="jn-kicker">Trading Operating System</div>
          <h1>Journal</h1>
        </div>
        <div class="jn-id-meta">
          <span class="jn-conn connecting" id="jnIdentityStatus"><span class="d"></span>Connecting&hellip;</span>
          <span class="jn-ver">SERVER-SAVED JOURNAL</span>
        </div>
        <button class="jn-action" id="jOpenModal" type="button" aria-label="Log a new trade">
          <span aria-hidden="true">+</span> Log Trade
        </button>
      </div>

      <div class="jn-work-tabs" role="tablist" aria-label="Journal workspaces">
        <button class="active" id="jWorkTab-dashboard" data-jview="dashboard" type="button">Dashboard</button>
        <button id="jWorkTab-plans" data-jview="plans" type="button">Pre-Market Plan</button>
        <button id="jWorkTab-trades" data-jview="trades" type="button">Trade Log</button>
        <button id="jWorkTab-reflections" data-jview="reflections" type="button">Reflections</button>
        <button id="jWorkTab-studies" data-jview="studies" type="button">Study Book</button>
        <button id="jWorkTab-goals" data-jview="goals" type="button">Goals &amp; System</button>
      </div>

      <section class="jn-work-view active" id="jWorkView-dashboard" data-jview-panel="dashboard">
      <div class="jn-dashboard-toolbar" id="jDashboardControls" aria-label="Dashboard population"></div>

      <!-- 2. PERFORMANCE RAIL — compute_journal_stats() results.
           Every cell carries a sub-line naming the population it was computed
           from, so no figure is readable without its sample size. -->
      <div class="jn-rail" id="jnRail" aria-label="Performance summary">
        <div class="ri">
          <div class="l" id="jnNetPnlLabel">Net P&amp;L &middot; All time</div>
          <div class="v" id="jnNetPnl">&mdash;</div>
          <div class="s" id="jnNetPnlSub">&mdash;</div>
        </div>
        <div class="ri">
          <div class="l">This Week</div>
          <div class="v" id="jnWeekPnl">&mdash;</div>
          <div class="s" id="jnWeekPnlSub">&mdash;</div>
        </div>
        <div class="ri">
          <div class="l">Profit Factor</div>
          <div class="v" id="jnProfitFactor">&mdash;</div>
          <div class="s" id="jnProfitFactorSub">&mdash;</div>
        </div>
        <div class="ri">
          <div class="l">Avg Win / Loss</div>
          <div class="v" id="jnAvgWL">&mdash;</div>
          <div class="s" id="jnAvgWLSub">&mdash;</div>
        </div>
        <div class="ri">
          <div class="l">Win Rate</div>
          <div class="v" id="jnWinRate">&mdash;</div>
          <div class="s" id="jnWinRateSub">&mdash;</div>
        </div>
      </div>
      <div class="jn-rail-note" id="jnRailNote" style="display:none"></div>

      <div class="jn-dashboard-grid">
        <section class="jn-dash-panel jn-equity-panel" aria-labelledby="jnEquityTitle">
          <div class="jn-sec-head"><h2 id="jnEquityTitle">Cumulative P&amp;L</h2><span class="meta" id="jnEquityMeta">&mdash;</span></div>
          <div class="jn-equity" id="jnEquity"><div class="jn-none">Loading equity curve&hellip;</div></div>
        </section>
        <section class="jn-dash-panel" aria-labelledby="jnDashDailyTitle">
          <div class="jn-sec-head"><h2 id="jnDashDailyTitle">Daily P&amp;L</h2><span class="meta" id="jnDashDailyMeta">&mdash;</span></div>
          <div class="jn-dash-daily" id="jnDashDaily"><div class="jn-none">Loading sessions&hellip;</div></div>
        </section>
        <section class="jn-dash-panel jn-calendar-panel" aria-labelledby="jnCalendarTitle">
          <div class="jn-sec-head"><h2 id="jnCalendarTitle">Monthly Calendar</h2><span class="meta" id="jnCalendarMeta">&mdash;</span></div>
          <div class="jn-calendar-summary" id="jnCalendarSummary"></div>
          <div class="jn-calendar" id="jnCalendar"><div class="jn-none">Loading calendar&hellip;</div></div>
        </section>
        <div class="jn-dashboard-side">
          <section class="jn-dash-panel" aria-labelledby="jnWeeklyTitle">
            <div class="jn-sec-head"><h2 id="jnWeeklyTitle">Weekly P&amp;L</h2><span class="meta" id="jnWeeklyMeta">&mdash;</span></div>
            <div class="jn-weekly" id="jnWeekly"><div class="jn-none">Loading weeks&hellip;</div></div>
          </section>
          <section class="jn-dash-panel" aria-labelledby="jnModelsTitle">
            <div class="jn-sec-head"><h2 id="jnModelsTitle">Model Performance</h2><span class="meta">Approved models</span></div>
            <div class="jn-models" id="jnModels"><div class="jn-none">Loading models&hellip;</div></div>
          </section>
        </div>
      </div>
      </section>

      <!-- 3. FILTER CHIPS -->
      <section class="jn-work-view" id="jWorkView-trades" data-jview-panel="trades">
      <div class="jn-filters" id="jFilterBar" aria-label="Filter trades"></div>

      <!-- 4. LEDGER + REVIEW -->
      <div class="jn-main">

        <!-- LEFT COLUMN -->
        <div class="jn-left">
          <section class="jn-ledger-wrap" aria-labelledby="jnLedgerTitle">
            <h2 class="jn-sr-only" id="jnLedgerTitle">Trade ledger</h2>
            <div class="jn-ledger-scroll">
              <table class="jn-ledger" id="jnLedger">
                <caption class="jn-sr-only">Closed trades. Use the arrow keys to move between rows and Enter or Space to open a trade in the review panel.</caption>
                <thead>
                  <tr>
                    <th scope="col">Date &middot; Time</th>
                    <th scope="col">Instr</th>
                    <th scope="col">Dir</th>
                    <th scope="col" class="num">Entry</th>
                    <th scope="col" class="num">Exit</th>
                    <th scope="col" class="num">Result</th>
                    <th scope="col" class="ses"><span class="jn-th-full">Session &middot; Regime</span><span class="jn-th-abbr">Session</span></th>
                  </tr>
                </thead>
                <tbody id="jnLedgerBody">
                  <tr><td colspan="7" class="jn-none">Loading trades&hellip;</td></tr>
                </tbody>
              </table>
            </div>
            <div class="jn-ledger-foot" id="jnLedgerFoot"></div>
          </section>

          <!-- DAILY P&L STRIP -->
          <section class="jn-daily" aria-labelledby="jnDailyTitle">
            <div class="jn-sec-head">
              <h2 id="jnDailyTitle">Daily Net P&amp;L</h2>
              <span class="meta" id="jnDailyMeta">&mdash;</span>
            </div>
            <div class="jn-dp-ctx" id="jnDailyCtx" style="display:none"></div>
            <div class="jn-daily-chart" id="jnDaily"><div class="jn-none">&mdash;</div></div>
            <div class="jn-bd-note" id="jnDailyNote" style="display:none"></div>
          </section>
        </div>

        <!-- RIGHT COLUMN — REVIEW + SUPPORTING PERFORMANCE CONTEXT -->
        <div class="jn-right">
          <aside class="jn-review" id="jnReview" aria-labelledby="jnReviewTitle" aria-live="polite">
            <h2 class="jn-sr-only" id="jnReviewTitle">Trade review</h2>
            <div class="jn-review-inner" id="jnReviewInner">
              <div class="jn-none jn-review-empty">Select a trade to review it.</div>
            </div>
          </aside>

          <section class="jn-breakdown" aria-labelledby="jnBreakdownTitle">
            <div class="jn-sec-head">
              <h2 id="jnBreakdownTitle">Performance Breakdown</h2>
              <span class="meta" id="jnBreakdownMeta">&mdash;</span>
            </div>
            <div class="jn-bd-grid">
              <div class="jn-bd-block">
                <h3>By Regime &mdash; Win Rate</h3>
                <div class="jn-bars" id="jnByRegime"><div class="jn-none">&mdash;</div></div>
              </div>
              <div class="jn-bd-block">
                <h3>By Session &mdash; Net P&amp;L</h3>
                <div class="jn-bars" id="jnBySession"><div class="jn-none">&mdash;</div></div>
              </div>
              <div class="jn-bd-block">
                <h3>By Direction</h3>
                <div class="jn-bars" id="jnByDirection"><div class="jn-none">&mdash;</div></div>
                <div class="jn-bd-note" id="jnByDirectionNote" style="display:none"></div>
              </div>
              <div class="jn-bd-block">
                <h3>By Setup &mdash; Trades</h3>
                <div class="jn-bars" id="jnBySetup"><div class="jn-none">&mdash;</div></div>
              </div>
            </div>
          </section>
        </div>

      </div>
      </section>

      <section class="jn-work-view" id="jWorkView-plans" data-jview-panel="plans">
        <div class="jn-workspace-head"><div><div class="jn-kicker">Before the bell</div><h2>Pre-Market Plans</h2></div><span>Link intent to execution</span></div>
        <form class="jn-entry-form" id="jPlanForm">
          <div class="jn-form-grid"><label>Date<input id="jPlanDate" type="date" required></label><label>Book<select id="jPlanBook"><option>LIVE</option><option>PAPER</option></select></label><label>Account<input id="jPlanAccount" placeholder="APEX 50K"></label><label>Directional posture<select id="jPlanBias"><option>NEUTRAL</option><option>BULLISH</option><option>BEARISH</option></select></label></div>
          <label>Economic events<textarea id="jPlanEvents" placeholder="Time, event, expected impact"></textarea></label><label>Key levels<textarea id="jPlanLevels" placeholder="PDH/PDL, Asia and London H/L, hourly levels, ORB context"></textarea></label><label>Game plan<textarea id="jPlanGame" placeholder="What must price do before you act?"></textarea></label>
          <div class="jn-form-grid"><label>Invalidation<textarea id="jPlanInvalidation" placeholder="What proves the plan wrong?"></textarea></label><label>Risk limit<input id="jPlanRisk" placeholder="1% / $ amount"></label></div>
          <label class="jn-upload-field" for="jPlanScreenshot"><span class="jn-upload-title">Attach pre-market charts</span><span class="jn-upload-copy" id="jPlanScreenshotName">PNG, JPEG, or WebP &middot; up to 8 MB</span></label><input class="jn-file-input" id="jPlanScreenshot" type="file" accept="image/png,image/jpeg,image/webp">
          <button class="jn-action" type="submit">Save Pre-Market Plan</button><div class="jn-form-status" id="jPlanStatus" aria-live="polite"></div>
        </form><div class="jn-record-list" id="jPlanList"></div>
      </section>

      <section class="jn-work-view" id="jWorkView-reflections" data-jview-panel="reflections">
        <div class="jn-workspace-head"><div><div class="jn-kicker">Review the process</div><h2>Reflections</h2></div><span>Weekly &middot; Monthly &middot; Quarterly</span></div>
        <form class="jn-entry-form" id="jReflectionForm"><div class="jn-form-grid"><label>Period<select id="jReflectionPeriod"><option>WEEKLY</option><option>MONTHLY</option><option>QUARTERLY</option></select></label><label>Date<input id="jReflectionDate" type="date" required></label><label>Execution rating / 10<input id="jReflectionRating" type="number" min="0" max="10" step="0.5"></label><label>Title<input id="jReflectionTitle" placeholder="Week 1 Review" required></label></div><label>What happened<textarea id="jReflectionSummary"></textarea></label><div class="jn-form-grid"><label>What went well<textarea id="jReflectionWentWell"></textarea></label><label>Lessons learned<textarea id="jReflectionLessons"></textarea></label></div><label>One improvement for the next period<textarea id="jReflectionImprovement"></textarea></label><button class="jn-action" type="submit">Save Reflection</button><div class="jn-form-status" id="jReflectionStatus" aria-live="polite"></div></form><div class="jn-record-list" id="jReflectionList"></div>
      </section>

      <section class="jn-work-view" id="jWorkView-studies" data-jview-panel="studies">
        <div class="jn-workspace-head"><div><div class="jn-kicker">Research library</div><h2>Study Book</h2></div><span>Observation and paper evidence</span></div>
        <form class="jn-entry-form" id="jStudyForm"><div class="jn-form-grid"><label>Date<input id="jStudyDate" type="date" required></label><label>Scope<select id="jStudyScope"><option>DAILY</option><option>WEEKLY</option><option>MONTHLY</option><option>ASIA</option><option>LONDON</option><option>NY_AM</option><option>NY_LUNCH</option><option>NY_PM</option></select></label><label>Instrument<input id="jStudyInstrument" value="NQ"></label><label>Model<select id="jStudyModel"><option>KLR</option><option>OTE</option><option>ORB</option><option>POWELL_10AM</option><option>EXPERIMENTAL</option></select></label></div><label>Study title<input id="jStudyTitle" placeholder="NY PM 13:30 reversal" required></label><label>What are you studying?<textarea id="jStudyDescription"></textarea></label><div class="jn-form-grid"><label>Hypothesis<textarea id="jStudyHypothesis"></textarea></label><label>Conclusion<textarea id="jStudyConclusion"></textarea></label></div><label class="jn-upload-field" for="jStudyScreenshot"><span class="jn-upload-title">Attach study chart</span><span class="jn-upload-copy" id="jStudyScreenshotName">PNG, JPEG, or WebP &middot; up to 8 MB</span></label><input class="jn-file-input" id="jStudyScreenshot" type="file" accept="image/png,image/jpeg,image/webp"><button class="jn-action" type="submit">Save Study</button><div class="jn-form-status" id="jStudyStatus" aria-live="polite"></div></form><div class="jn-record-list" id="jStudyList"></div>
      </section>

      <section class="jn-work-view" id="jWorkView-goals" data-jview-panel="goals">
        <div class="jn-workspace-head"><div><div class="jn-kicker">Process over outcome</div><h2>Goals &amp; Trading System</h2></div><span>Rules remain visible and auditable</span></div>
        <div class="jn-goals-grid"><form class="jn-entry-form" id="jGoalForm"><div class="jn-form-grid"><label>Period<select id="jGoalPeriod"><option>DAILY</option><option>WEEKLY</option><option>MONTHLY</option><option>QUARTERLY</option><option>ANNUAL</option></select></label><label>Target date<input id="jGoalDate" type="date"></label></div><label>Goal<input id="jGoalTitle" placeholder="Follow every risk rule" required></label><label>Checklist items<textarea id="jGoalChecklist" placeholder="One item per line"></textarea></label><button class="jn-action" type="submit">Add Goal</button><div class="jn-form-status" id="jGoalStatus" aria-live="polite"></div></form><section class="jn-system-card"><div class="jn-sec-head"><h2>Locked NOVA System</h2><span>Current rules</span></div><div id="jSystemSummary"></div></section></div><div class="jn-record-list" id="jGoalList"></div>
      </section>

      <!-- LEGACY CONTAINERS — not part of the approved composition.
           Kept present (hidden) so renderSignalFeed() and the analytics
           renderer keep writing to real elements instead of failing their
           lookups. No visual surface, no duplicate ids. -->
      <div id="jnLegacy" hidden aria-hidden="true">
        <span id="jTabCount-trades">0</span><span id="jTabCount-signals">0</span>
        <span id="jOvTrades">&mdash;</span><span id="jOvPnl">&mdash;</span>
        <span id="jOvEvals">&mdash;</span><span id="jOvWinRate">&mdash;</span>
        <span id="jOvPF">&mdash;</span><span id="jOvWeek">&mdash;</span>
        <div id="journalCardList"></div>
        <div id="jSigFilterBar"></div><div id="jSignalFeedList"></div>
        <span id="jaExpectancy">&mdash;</span><span id="jaTotalTrades">0</span>
        <span id="jaWinRate">&mdash;</span><span id="jaWRSub">&mdash;</span>
        <span id="jaPF">&mdash;</span><span id="jaAvgWL">&mdash;</span>
        <span id="jaAvgWin">&mdash;</span><span id="jaAvgLoss">&mdash;</span>
        <div id="setupTypeGrid"></div><div id="sessionBreakdownGrid"></div>
        <div id="regimeBreakdownGrid"></div><div id="behavioralAnalyticsGrid"></div>
        <div id="emotionalAnalyticsGrid"></div>
      </div>

    </div><!-- /journal vstack -->
  </div><!-- /page-journal -->

'''

JOURNAL_MODALS_HTML = '''  <!-- TRADE DETAIL MODAL -->
  <div class="jtd-backdrop" id="jtdBackdrop" style="display:none" onclick="if(event.target===this)closeTradeDetail()">
    <div class="jtd-modal">
      <div class="jtd-header">
        <div class="jtd-title" id="jtdTitle">—</div>
        <button class="jtd-close" onclick="closeTradeDetail()">✕</button>
      </div>
      <div class="jtd-body" id="jtdBody">
        <div style="text-align:center;padding:40px;color:var(--muted2)">Loading...</div>
      </div>
    </div>
  </div>

  <!-- LOG TRADE MODAL -->
  <div class="j-modal-backdrop" id="jModalBackdrop" style="display:none" onclick="if(event.target===this)closeJModal()">
    <div class="j-modal">
      <div class="j-modal-header">
        <div id="jModalTitle" style="font-family:\'Rajdhani\',sans-serif;font-size:20px;font-weight:700;letter-spacing:1px">LOG TRADE</div>
        <button class="j-modal-close" onclick="closeJModal()">✕</button>
      </div>
      <div class="vstack" style="gap:12px">
        <div>
          <label class="trade-label">Journal Book</label>
          <div class="toggle-group">
            <button type="button" class="toggle-btn active-live" id="jModeLive" onclick="setTradeMode('LIVE')">Live Trade</button>
            <button type="button" class="toggle-btn" id="jModePaper" onclick="setTradeMode('PAPER')">Paper Study</button>
          </div>
        </div>
        <div><label class="trade-label">Account</label><input class="trade-input" id="jAccount" type="text" placeholder="APEX 50K, Tradovate Live&hellip;" /></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div><label class="trade-label">Ticker</label><input class="trade-input" id="jTicker" type="text" placeholder="MNQ or NQ" /></div>
          <div><label class="trade-label">Date</label><input class="trade-input" id="jDate" type="date" /></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div><label class="trade-label">Entry Time</label><input class="trade-input" id="jEntryTime" type="time" /></div>
          <div><label class="trade-label">Exit Time</label><input class="trade-input" id="jExitTime" type="time" /></div>
        </div>
        <div>
          <label class="trade-label">Direction</label>
          <div class="toggle-group">
            <button type="button" class="toggle-btn active-long" id="jDirLong" onclick="setDir(\'LONG\')">▲ LONG</button>
            <button type="button" class="toggle-btn" id="jDirShort" onclick="setDir(\'SHORT\')">▼ SHORT</button>
          </div>
        </div>
        <div>
          <label class="trade-label">Outcome</label>
          <div class="toggle-group">
            <button type="button" class="toggle-btn active-win" id="jOutWin" onclick="setOutcome(\'WIN\')">WIN</button>
            <button type="button" class="toggle-btn" id="jOutLoss" onclick="setOutcome(\'LOSS\')">LOSS</button>
            <button type="button" class="toggle-btn" id="jOutBE" onclick="setOutcome(\'BREAKEVEN\')">BE</button>
          </div>
        </div>
        <div>
          <label class="trade-label">Net P&amp;L ($)</label>
          <input class="trade-input" id="jRealizedPnl" type="number" step="any" placeholder="e.g. 120.00 or -60" style="font-size:16px;font-weight:700" />
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
          <div><label class="trade-label">Entry <span class="jn-optional">optional</span></label><input class="trade-input" id="jEntry" type="number" step="any" placeholder="0.00" /></div>
          <div><label class="trade-label">Exit <span class="jn-optional">optional</span></label><input class="trade-input" id="jExit" type="number" step="any" placeholder="0.00" /></div>
          <div><label class="trade-label">Size</label><input class="trade-input" id="jSize" type="number" step="any" placeholder="1" /></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div><label class="trade-label">Stop</label><input class="trade-input" id="jStop" type="number" step="any" placeholder="0.00" /></div>
          <div><label class="trade-label">TP1</label><input class="trade-input" id="jTp1" type="number" step="any" placeholder="0.00" /></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div><label class="trade-label">Commission</label><input class="trade-input" id="jCommission" type="number" step="any" min="0" placeholder="0.00" /></div>
          <div><label class="trade-label">Performance / 10</label><input class="trade-input" id="jPerformanceRating" type="number" min="0" max="10" step="0.5" /></div>
        </div>
        <div><label class="trade-label">Model</label><select class="trade-input trade-select" id="jSetup"><option value="">&mdash; Select model &mdash;</option><option value="KLR">KLR</option><option value="OTE">OTE</option><option value="ORB">ORB</option><option value="POWELL_10AM">Powell 10AM</option><option value="EXPERIMENTAL">Experimental &mdash; Paper only</option></select></div>
        <div><label class="trade-label">Daily Protocol</label><input class="trade-input" id="jProtocol" type="text" placeholder="A+ only, 2 trades max, 1% risk&hellip;" /></div>
        <div><label class="trade-label">Session</label>
          <select class="trade-input trade-select" id="jSession">
            <option value="">— Select session —</option>
            <option value="NY_OPEN">NY_OPEN</option>
            <option value="NY_AM">NY_AM</option>
            <option value="NY_PM">NY_PM</option>
            <option value="LONDON">LONDON</option>
            <option value="ASIA">ASIA</option>
          </select>
        </div>
        <div><label class="trade-label">Linked Pre-Market Plan</label><select class="trade-input trade-select" id="jPremarketPlan"><option value="">&mdash; No linked plan &mdash;</option></select></div>
        <div>
          <label class="trade-label">Risk Checklist</label>
          <div class="flag-checks">
            <label class="flag-check"><input type="checkbox" id="jRiskSize" value="SIZE_WITHIN_PLAN" /> Size within plan</label>
            <label class="flag-check"><input type="checkbox" id="jRiskTrades" value="WITHIN_TRADE_LIMIT" /> Within 2-trade limit</label>
            <label class="flag-check"><input type="checkbox" id="jRiskLosses" value="WITHIN_LOSS_LIMIT" /> Fewer than 2 losses</label>
            <label class="flag-check"><input type="checkbox" id="jRiskSession" value="VALID_SESSION" /> Valid live session</label>
          </div>
        </div>
        <div>
          <label class="trade-label">PRIME Checklist</label>
          <div class="flag-checks">
            <label class="flag-check"><input type="checkbox" id="jPrimePosition" value="POSITION" /> Position</label>
            <label class="flag-check"><input type="checkbox" id="jPrimeLevel" value="RELEVANT_LEVEL" /> Relevant Level</label>
            <label class="flag-check"><input type="checkbox" id="jPrimeInteraction" value="INTERACTION" /> Interaction</label>
            <label class="flag-check"><input type="checkbox" id="jPrimeConfirmation" value="MARKET_CONFIRMATION" /> Market Confirmation</label>
            <label class="flag-check"><input type="checkbox" id="jPrimeExecution" value="EXECUTION" /> Execution</label>
          </div>
        </div>
        <div><label class="trade-label">Confluences</label><input class="trade-input" id="jConfluences" type="text" placeholder="Comma-separated evidence" /></div>
        <div><label class="trade-label">Trade Management</label><textarea class="trade-input" id="jTradeManagement" rows="2" placeholder="How did you manage the position?"></textarea></div>
        <div><label class="trade-label">Notes</label><input class="trade-input" id="jNotes" type="text" placeholder="What happened…" /></div>
        <div>
          <label class="trade-label" for="jScreenshot">Trade Screenshot <span class="jn-optional">optional</span></label>
          <label class="jn-upload-field" for="jScreenshot">
            <span class="jn-upload-title">Attach chart screenshot</span>
            <span class="jn-upload-copy" id="jScreenshotName">PNG, JPEG, or WebP · up to 8 MB</span>
          </label>
          <input id="jScreenshot" class="jn-file-input" type="file" accept="image/png,image/jpeg,image/webp" />
        </div>
        <div>
          <label class="trade-label">Emotional State</label>
          <select class="trade-input trade-select" id="jEmotionalState">
            <option value="">— Not reported —</option>
            <option value="CALM">Calm</option>
            <option value="CONFIDENT">Confident</option>
            <option value="ANXIOUS">Anxious</option>
            <option value="HESITANT">Hesitant</option>
            <option value="IMPULSIVE">Impulsive</option>
            <option value="FRUSTRATED">Frustrated</option>
          </select>
        </div>
        <div>
          <label class="trade-label">Behavioral Flags</label>
          <div class="flag-checks">
            <label class="flag-check"><input type="checkbox" id="jFlagEarlyExit" value="EARLY_EXIT" /> Early Exit</label>
            <label class="flag-check"><input type="checkbox" id="jFlagLateEntry" value="LATE_ENTRY" /> Late Entry</label>
            <label class="flag-check"><input type="checkbox" id="jFlagHesitation" value="HESITATION" /> Hesitation</label>
            <label class="flag-check"><input type="checkbox" id="jFlagOversized" value="OVERSIZED" /> Oversized</label>
            <label class="flag-check"><input type="checkbox" id="jFlagFomo" value="FOMO" /> FOMO</label>
            <label class="flag-check"><input type="checkbox" id="jFlagRevenge" value="REVENGE" /> Revenge</label>
          </div>
        </div>
        <div>
          <label class="trade-label">Post-Trade Reflection</label>
          <textarea class="trade-input" id="jReflection" rows="2" placeholder="What would you do differently? What did you learn?" style="resize:vertical;min-height:60px;font-size:12px;line-height:1.5"></textarea>
        </div>
        <button class="submit-trade-btn" id="jSubmitBtn">LOG TRADE</button>
        <div id="jFormMsg" style="text-align:center;font-size:12px;display:none"></div>
      </div>
    </div>
  </div>


'''
