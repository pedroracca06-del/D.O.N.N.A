"""ui/pages/journal.py — Journal page markup (id="page-journal") plus the
Trade Detail and Log Trade modals, extracted verbatim from ui/html.py
during the interface-modularization foundation (commit #9).

Ownership-vs-DOM-position note: the two modals were physically located
between the Assistant and Settings page divs in the original single file
(they are position:fixed overlays, so their DOM position does not affect
rendering). They are Journal features (trade detail review, manual trade
logging), so they are owned by this module for a clearer boundary, while
the composer in ui/html.py still emits them at their original position in
the assembled document so the rendered output is unchanged.
"""
JOURNAL_HTML = '''  <!-- ════════════════════ JOURNAL ════════════════════ -->
  <div class="page" id="page-journal">
    <div class="vstack">

      <!-- HEADER -->
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:4px">
        <div>
          <div style="font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:2px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px">Operational Intelligence</div>
          <div style="font-family:\'Rajdhani\',sans-serif;font-size:30px;font-weight:700;letter-spacing:2px;color:var(--text)">JOURNAL</div>
        </div>
        <button class="submit-trade-btn" id="jOpenModal" style="width:auto;padding:10px 22px;margin-top:0;font-size:13px;letter-spacing:1.5px">+ LOG TRADE</button>
      </div>

      <!-- OVERVIEW STRIP -->
      <div class="j-overview" id="jOverviewStrip">
        <div class="j-ov-item"><div class="j-ov-lab">Today\'s Trades</div><div class="j-ov-val" id="jOvTrades" style="color:var(--text)">—</div></div>
        <div class="j-ov-div"></div>
        <div class="j-ov-item"><div class="j-ov-lab">Today\'s P&amp;L</div><div class="j-ov-val" id="jOvPnl" style="color:var(--muted2)">—</div></div>
        <div class="j-ov-div"></div>
        <div class="j-ov-item"><div class="j-ov-lab">NOVA Evaluations</div><div class="j-ov-val" id="jOvEvals" style="color:var(--text)">—</div></div>
        <div class="j-ov-div"></div>
        <div class="j-ov-item"><div class="j-ov-lab">Win Rate</div><div class="j-ov-val" id="jOvWinRate" style="color:var(--muted2)">—</div></div>
        <div class="j-ov-div"></div>
        <div class="j-ov-item"><div class="j-ov-lab">Profit Factor</div><div class="j-ov-val" id="jOvPF" style="color:var(--muted2)">—</div></div>
        <div class="j-ov-div"></div>
        <div class="j-ov-item"><div class="j-ov-lab">This Week</div><div class="j-ov-val" id="jOvWeek" style="color:var(--muted2)">—</div></div>
      </div>

      <!-- SUB NAVIGATION -->
      <div class="j-subnav">
        <button class="j-subnav-btn active" id="jTab-trades" onclick="switchJTab(\'trades\')">Trades<span class="j-subnav-count" id="jTabCount-trades">0</span></button>
        <button class="j-subnav-btn" id="jTab-signals" onclick="switchJTab(\'signals\')">Evaluations<span class="j-subnav-count" id="jTabCount-signals">0</span></button>
        <button class="j-subnav-btn" id="jTab-analytics" onclick="switchJTab(\'analytics\')">Analytics</button>
      </div>

      <!-- TRADES PANEL -->
      <div id="jPanel-trades">
        <div class="j-filter-bar" id="jFilterBar"></div>
        <div id="journalCardList">
          <div style="text-align:center;padding:40px;color:var(--muted2);font-size:13px">No trades logged yet.</div>
        </div>
      </div>

      <!-- EVALUATIONS PANEL -->
      <div id="jPanel-signals" style="display:none">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:8px">
          <div style="font-size:12px;color:var(--muted)">NOVA\'s per-cycle evaluation log — every assessment, grade, and reasoning entry.</div>
          <div class="j-filter-bar" id="jSigFilterBar" style="margin-bottom:0"></div>
        </div>
        <div id="jSignalFeedList">
          <div style="text-align:center;padding:40px;color:var(--muted2);font-size:13px">Loading signal feed...</div>
        </div>
      </div>

      <!-- ANALYTICS PANEL -->
      <div id="jPanel-analytics" style="display:none">
        <div style="margin-bottom:20px">
          <div class="kicker">Performance Summary</div>
          <div class="j-analytics-grid" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))">
            <div class="j-stat-card" style="border-color:rgba(184,134,11,.2)"><div class="jsc-lab">Expectancy</div><div class="jsc-val" id="jaExpectancy" style="font-size:22px">—</div><div class="jsc-sub">Per trade avg $</div></div>
            <div class="j-stat-card"><div class="jsc-lab">Total Trades</div><div class="jsc-val" id="jaTotalTrades">0</div><div class="jsc-sub">All logged</div></div>
            <div class="j-stat-card"><div class="jsc-lab">Win Rate</div><div class="jsc-val" id="jaWinRate">—</div><div class="jsc-sub" id="jaWRSub">—</div></div>
            <div class="j-stat-card"><div class="jsc-lab">Profit Factor</div><div class="jsc-val" id="jaPF">—</div><div class="jsc-sub" id="jaAvgWL">—</div></div>
            <div class="j-stat-card"><div class="jsc-lab">Avg Win</div><div class="jsc-val" id="jaAvgWin" style="color:var(--green)">—</div><div class="jsc-sub" id="jaAvgLoss">Avg L: —</div></div>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;align-items:start">
          <div class="panel"><div class="kicker">By Setup Type</div><div class="section-title" style="margin-bottom:12px">Setup Performance</div><div class="regime-breakdown-grid" id="setupTypeGrid"><div class="regime-card"><div class="rc-sub">No trades yet.</div></div></div></div>
          <div class="panel"><div class="kicker">By Session</div><div class="section-title" style="margin-bottom:12px">Session Performance</div><div class="regime-breakdown-grid" id="sessionBreakdownGrid"><div class="regime-card"><div class="rc-sub">No trades yet.</div></div></div></div>
          <div class="panel"><div class="kicker">By Market Regime</div><div class="section-title" style="margin-bottom:12px">Regime Performance</div><div class="regime-breakdown-grid" id="regimeBreakdownGrid"><div class="regime-card"><div class="rc-sub">No trades yet.</div></div></div></div>
          <div class="panel"><div class="kicker">Behavioral Patterns</div><div class="section-title" style="margin-bottom:12px">Error Frequency</div><div id="behavioralAnalyticsGrid"><div style="font-size:12px;color:var(--muted2);padding:12px 0">No behavioral flags recorded yet.</div></div></div>
        </div>
        <div class="panel"><div class="kicker">Emotional Intelligence</div><div class="section-title" style="margin-bottom:6px">State vs Performance</div><div style="font-size:12px;color:var(--muted);margin-bottom:14px">Correlation between reported emotional state and trade outcome.</div><div id="emotionalAnalyticsGrid"><div style="font-size:12px;color:var(--muted2);padding:8px 0">No emotional state data yet.</div></div></div>
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
