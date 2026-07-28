"""ui/pages/settings.py — Settings page markup (id="page-settings"),
extracted from ui/html.py during the interface-modularization foundation
(commit #9).

One intentional, Pedro-approved content change is included here (not a
modularization side effect): the "Trading Subsystem" status block (a
"TRADING SUBSYSTEM" kicker, a Status readout, and an explanatory
paragraph naming H.A.R.V.E.Y and the Execution Bot as retired) has been
removed per the mandatory correction that the retired Execution Bot /
legacy trading subsystem must not appear anywhere in Interface V1 --
including as a Settings status card, even a "this is retired" card.
Settings now reports only active, user-relevant system and integration
information: Integrations and System. Every other line is byte-for-byte
identical to the corresponding lines previously inline in DASHBOARD_HTML.
"""
SETTINGS_HTML = '''  <!-- ════════════════════ SETTINGS ════════════════════ -->
  <div class="page" id="page-settings">
    <div class="vstack">
      <div class="panel" style="padding:16px 20px">

        <!-- Header -->
        <div class="fd-page-header">
          <div>
            <div class="fd-page-title">SETTINGS</div>
            <div class="fd-meta" style="margin-top:3px">Platform status · integrations · system info</div>
          </div>
          <div style="display:flex;align-items:center;gap:10px">
            <button class="fd-refresh-btn" onclick="refreshSettings()">↻ REFRESH</button>
          </div>
        </div>

        <!-- Integrations -->
        <div class="kicker" style="margin:20px 0 8px">INTEGRATIONS</div>
        <div id="setIntegrations">
          <div class="exec-row"><span class="exec-row-label">Loading...</span></div>
        </div>

        <!-- System -->
        <div class="kicker" style="margin:20px 0 8px">SYSTEM</div>
        <div class="exec-row">
          <span class="exec-row-label">Chat model</span>
          <span class="exec-row-val" id="setChatModel">—</span>
        </div>
        <div class="exec-row">
          <span class="exec-row-label">Fast model</span>
          <span class="exec-row-val" id="setFastModel">—</span>
        </div>
        <div class="exec-row" style="border-bottom:none">
          <span class="exec-row-label">Server time (ET)</span>
          <span class="exec-row-val" id="setServerTime">—</span>
        </div>

      </div><!-- /panel -->
    </div><!-- /vstack -->
  </div><!-- /page-settings -->

'''
