"""ui/pages/settings.py — Settings page markup (id="page-settings").

Approved composition: a configuration status band, then two INDEPENDENT
column stacks — left holds what a person can act on, right is a read-only
status rail. The left column runs Overview Tiles -> Working Memory -> Not
Configurable Here; the right runs Integrations -> System. The columns are not
stretched to a shared height, so the third left-hand section begins straight
after Working Memory instead of waiting for the taller rail to end.

Four things here are load-bearing rather than decorative:

1.  Every panel carries the scope of its values — "This browser",
    "Server · persists", "Environment", "Read-only". Where a setting actually
    lives determines what a save can promise, so it is stated, not implied.

2.  Integrations say "Configured" / "Not configured", never CONNECTED. The
    backend proves only that a key string is present: /check-env returns
    bool(ANTHROPIC_API_KEY) and friends. It does not test reachability,
    validity or remaining credit, so an expired or out-of-credit key still
    reads Configured. The page this replaces printed CONNECTED — and printed
    it for Discord even with no credential at all, because that row read a
    module-import flag.

3.  Secrets never reach the browser. Variable NAMES are shown; values are
    not returned by any route, and nothing here renders, masks or measures
    one.

4.  Nothing from the retired trading and execution subsystem appears — no
    control, no readout, and no path to one.

The dynamic regions (tiles, working memory, integrations, system rows) are
filled by refreshSettings(); the markup carries the loading state so the page
is meaningful before any script runs.
"""
SETTINGS_HTML = '''  <!-- ════════════════════ SETTINGS ════════════════════ -->
  <div class="page" id="page-settings" data-st-state="loading">

    <!-- PAGE IDENTITY -->
    <div class="st-id">
      <div>
        <div class="st-kicker">System</div>
        <h1>Settings</h1>
      </div>
      <div class="st-id-meta">
        <span class="st-fresh busy" id="setStatusPill">Reading system state</span>
      </div>
    </div>

    <!-- CONFIGURATION STATUS BAND -->
    <div class="st-band" id="setBand" data-when="loaded">
      <div class="st-bcell">
        <span class="st-bk">Editable here</span>
        <span class="st-bv ok" id="setCountEditable">—</span>
        <span class="st-bs">tile preference &middot; working memory</span>
      </div>
      <div class="st-bcell">
        <span class="st-bk">Environment-managed</span>
        <span class="st-bv env" id="setCountEnv">—</span>
        <span class="st-bs" id="setCountEnvSub">&mdash;</span>
      </div>
      <div class="st-bcell">
        <span class="st-bk">Read-only system</span>
        <span class="st-bv ro" id="setCountReadonly">—</span>
        <span class="st-bs">models, time, feeds, files</span>
      </div>
      <div class="st-bcell">
        <span class="st-bk">Not configurable</span>
        <span class="st-bv no">3</span>
        <span class="st-bs">stored but unread</span>
      </div>
    </div>
    <div class="st-band" data-when="loading">
      <div class="st-bcell"><span class="st-bk">Editable here</span><div class="st-skel"><i style="height:20px;width:32px"></i></div></div>
      <div class="st-bcell"><span class="st-bk">Environment-managed</span><div class="st-skel"><i style="height:20px;width:32px"></i></div></div>
      <div class="st-bcell"><span class="st-bk">Read-only system</span><div class="st-skel"><i style="height:20px;width:32px"></i></div></div>
      <div class="st-bcell"><span class="st-bk">Not configurable</span><div class="st-skel"><i style="height:20px;width:32px"></i></div></div>
    </div>

    <!-- Backend-unavailable banner. The page this replaces kept displaying the
         last good values, including a connection claim it could not prove,
         with nothing to say the read had failed. -->
    <div class="st-callout err" data-when="error" role="alert">
      <b>System state could not be read.</b> <code>/check-env</code> and <code>/system-health</code> did not
      respond, so values are withheld rather than shown stale.
    </div>

    <div class="st-grid">

      <!-- ══ LEFT — what can actually be changed ══ -->
      <div class="st-col">

        <section class="panel st-panel" aria-labelledby="setPrefTitle">
          <div class="st-ph"><h2 id="setPrefTitle">Overview tiles</h2><span class="st-tag browser">This browser</span></div>
          <p class="st-pdesc">Which five instruments Overview shows. <b>Saved in this browser only &mdash; not on the
            server, and not on your other devices.</b></p>

          <div class="st-tiles" id="setTiles" role="group" aria-labelledby="setTilesLabel" data-when="loaded"></div>
          <div class="st-skel st-tiles-sk" data-when="loading"><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
          <div class="st-unavail" data-when="error">
            <span class="u1">Preference not loaded</span>
            <span class="u2">Read from this browser once the system is reachable. Nothing was changed.</span>
          </div>
          <div id="setTilesLabel" class="st-sr">Overview tiles &mdash; choose exactly five instruments</div>
          <span class="st-count" id="setTileCount" data-when="loaded">&mdash;</span>

          <div class="st-fielderr" id="setTileErr" data-when="loaded" role="alert" hidden>
            Overview shows exactly five tiles. Deselect the extras before saving.
          </div>

          <div class="st-savebar" data-when="loaded">
            <button class="st-btn primary" id="setSaveTiles" type="button" disabled>Save preferences</button>
            <button class="st-btn" id="setDiscardTiles" type="button" hidden>Discard</button>
            <span class="st-savemsg idle" id="setSaveMsg">No unsaved changes</span>
          </div>
          <div class="st-note" id="setSaveNote" hidden>
            <b>&ldquo;Saved&rdquo; means written and read back</b> &mdash; the stored value was re-read and matched.
          </div>
        </section>

        <section class="panel st-panel" aria-labelledby="setWmTitle">
          <div class="st-ph"><h2 id="setWmTitle">Working memory</h2><span class="st-tag server">Server &middot; persists</span></div>
          <p class="st-pdesc">The only thing NOVA remembers between sessions. Edited on <b>NOVA Intelligence</b>;
            shown here so there is one place to clear it.</p>

          <div id="setWmRows" data-when="loaded"></div>
          <div class="st-skel rows" data-when="loading"><i></i><i></i><i></i><i></i></div>
          <div class="st-unavail" data-when="error">
            <span class="u1">Working memory not read</span>
            <span class="u2"><code>/assistant-data</code> did not respond. Nothing was cleared.</span>
          </div>

          <div class="st-savebar" id="setWmActions" data-when="loaded">
            <button class="st-btn danger" id="setClearTasks" type="button">Clear all tasks</button>
            <button class="st-btn danger" id="setClearReminders" type="button">Clear all reminders</button>
          </div>
          <div id="setConfirm"></div>
          <div class="st-note">Irreversible, applied at once. The only destructive action in Settings.</div>
        </section>

        <!-- Begins immediately after Working Memory: the columns flow
             independently, so this does not wait for the taller rail. -->
        <section class="panel st-panel" aria-labelledby="setLimTitle">
          <div class="st-ph"><h2 id="setLimTitle">Not configurable here</h2><span class="st-tag na">Audited</span></div>
          <div class="st-bgrid">
            <div class="st-bitem"><h3>Stored but unread</h3>
              <p><code>theme_mode</code>, <code>layout_density</code> &mdash; persisted, but <b>nothing reads them</b>.</p></div>
            <div class="st-bitem"><h3>Overridden by environment</h3>
              <p><code>telegram_alert_mode</code> &mdash; stored, but <code>TELEGRAM_ALERT_MODE</code> wins.
              <b>The stored value is silently ignored.</b></p></div>
            <div class="st-bitem"><h3>No write path exists</h3>
              <p>Keys, tokens and model names come from the environment; <b>no route can write any of them</b>.
              Anything from the retired trading subsystem is absent entirely.</p></div>
          </div>
        </section>
      </div>

      <!-- ══ RIGHT — read-only status rail ══ -->
      <div class="st-col">

        <section class="panel st-panel" aria-labelledby="setIntTitle">
          <div class="st-ph"><h2 id="setIntTitle">Integrations</h2><span class="st-tag env">Environment</span></div>
          <p class="st-pdesc">Set through deployment environment variables, <b>not editable here</b>. Secrets never
            reach the browser.</p>

          <div id="setIntegrations" data-when="loaded"></div>
          <div class="st-skel rows" data-when="loading"><i></i><i></i><i></i><i></i><i></i><i></i></div>
          <div class="st-unavail" data-when="error">
            <span class="u1">Integration state unknown</span>
            <span class="u2">Presence cannot be asserted while <code>/check-env</code> is unreachable.</span>
          </div>

          <div class="st-callout warn" data-when="loaded">
            <b>Configured is not connected.</b> The server checks only that a key is <i>present</i> &mdash; not
            reachable, valid, or in credit.
          </div>
          <div class="st-note"><b>No key can be added, replaced or removed here</b> &mdash; no route exists to do it.</div>
        </section>

        <section class="panel st-panel" aria-labelledby="setSysTitle">
          <div class="st-ph"><h2 id="setSysTitle">System</h2><span class="st-tag na">Read-only</span></div>
          <div id="setSystemRows" data-when="loaded"></div>
          <div class="st-skel rows" data-when="loading"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
          <div class="st-unavail" data-when="error">
            <span class="u1">System state unknown</span>
            <span class="u2"><code>/system-health</code> did not respond.</span>
          </div>
        </section>
      </div>
    </div>
  </div>

'''
