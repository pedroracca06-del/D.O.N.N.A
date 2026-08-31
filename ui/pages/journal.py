"""ui/pages/journal.py — Journal page markup (id="page-journal") plus the
Trade Detail and Log Trade modals.

Approved composition (artifact b22fcc6b frame 2 desktop, f1b6ec63 frames 4-6
mobile), implemented in place of the previous tabbed card stack:

  1. Page identity + primary action (Log Trade)
  2. Compact performance rail -- five flat cells, dividers, no card chrome
  3. Filter chips
  4. Two balanced columns:
       left  = selectable trade ledger -> ledger footer -> performance
               breakdown (regime / session / direction / setup) -> daily P&L
       right = master-detail trade review panel (sticky on desktop)
  5. Mobile: the same regions stacked, ledger rows collapse to compact
     summaries, review panel lands last -- matching frames 4-6.

The left column carries the breakdown and daily-P&L blocks specifically so the
lower-left does not become dead space beneath a short ledger, which is what the
approved desktop frame shows.

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
          <div class="jn-kicker">Performance Review</div>
          <h1>Journal</h1>
        </div>
        <div class="jn-id-meta">
          <span class="jn-conn connecting" id="jnIdentityStatus"><span class="d"></span>Connecting&hellip;</span>
          <span class="jn-ver">v5.0 // LIVE MARKET CORE</span>
        </div>
        <button class="jn-action" id="jOpenModal" type="button" aria-label="Log a new trade">
          <span aria-hidden="true">+</span> Log Trade
        </button>
      </div>

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

      <!-- 3. FILTER CHIPS -->
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

          <!-- PERFORMANCE BREAKDOWN -->
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

        <!-- RIGHT COLUMN — MASTER-DETAIL REVIEW -->
        <aside class="jn-review" id="jnReview" aria-labelledby="jnReviewTitle" aria-live="polite">
          <h2 class="jn-sr-only" id="jnReviewTitle">Trade review</h2>
          <div class="jn-review-inner" id="jnReviewInner">
            <div class="jn-none jn-review-empty">Select a trade to review it.</div>
          </div>
        </aside>

      </div>

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
        <div style="font-family:\'Rajdhani\',sans-serif;font-size:20px;font-weight:700;letter-spacing:1px">LOG TRADE</div>
        <button class="j-modal-close" onclick="closeJModal()">✕</button>
      </div>
      <div class="vstack" style="gap:12px">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div><label class="trade-label">Ticker</label><input class="trade-input" id="jTicker" type="text" placeholder="MNQ, MES…" /></div>
          <div><label class="trade-label">Date</label><input class="trade-input" id="jDate" type="date" /></div>
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
          <label class="trade-label">Realized P&amp;L ($)</label>
          <input class="trade-input" id="jRealizedPnl" type="number" step="any" placeholder="e.g. 120.00 or -60" style="font-size:16px;font-weight:700" />
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
          <div><label class="trade-label">Entry <span style="color:var(--muted2);font-size:8px">opt</span></label><input class="trade-input" id="jEntry" type="number" step="any" placeholder="0.00" /></div>
          <div><label class="trade-label">Exit <span style="color:var(--muted2);font-size:8px">opt</span></label><input class="trade-input" id="jExit" type="number" step="any" placeholder="0.00" /></div>
          <div><label class="trade-label">Size</label><input class="trade-input" id="jSize" type="number" step="any" placeholder="1" /></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div><label class="trade-label">Stop</label><input class="trade-input" id="jStop" type="number" step="any" placeholder="0.00" /></div>
          <div><label class="trade-label">TP1</label><input class="trade-input" id="jTp1" type="number" step="any" placeholder="0.00" /></div>
        </div>
        <div><label class="trade-label">Setup Type</label><input class="trade-input" id="jSetup" type="text" placeholder="PROS_LONG, ORB_E1…" /></div>
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
        <div><label class="trade-label">Notes</label><input class="trade-input" id="jNotes" type="text" placeholder="What happened…" /></div>
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
