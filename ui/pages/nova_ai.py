"""ui/pages/nova_ai.py — NOVA Intelligence page markup (id="page-assistant").

Approved composition: a two-column workspace — conversation on the left,
context rail on the right — replacing the single "Command Interface" panel.

Three things in here are deliberate and load-bearing, not styling choices:

1.  The rail is headed "Context available when asked", never "used" or
    "held". Eight GET routes prove each source is REACHABLE and seven return
    `last_updated`, so availability and age are provable. Whether NOVA
    actually incorporated a source is NOT reported by /assistant/chat, and
    cannot be inferred from a 200: summarize_system_context() wraps each
    optional context line in a bare `except`, so a healthy route can still be
    absent from the prompt. The page therefore claims only what it can prove.

2.  Working memory is read from the real `GET /assistant-data` and written by
    the existing POST routes. Nothing here is a mock or a second copy of that
    state.

3.  There is no "Online" indicator and no client-side response tag. Both were
    hard-coded fictions: the old dot read Online while the AI was unreachable,
    and inferResponseTag() keyword-matched the reply to invent an ANALYSIS /
    RISK / EXECUTION label the backend never asserted.

The conversation log is rendered by JS; the markup below carries the idle
state so the page is meaningful before any script runs.
"""
NOVA_AI_HTML = '''  <!-- ════════════════════ NOVA INTELLIGENCE ════════════════════ -->
  <div class="page" id="page-assistant">

    <!-- PAGE IDENTITY -->
    <div class="ni-id">
      <div>
        <div class="ni-kicker">Market Intelligence</div>
        <h1>NOVA Intelligence</h1>
      </div>
      <div class="ni-id-meta">
        <span class="ni-fresh" id="niContextFresh">Context not yet read</span>
      </div>
    </div>

    <div class="ni-grid">

      <!-- ── CONVERSATION ── -->
      <section class="ni-thread" aria-labelledby="niThreadTitle">
        <h2 id="niThreadTitle" class="ni-sr">Conversation with NOVA</h2>

        <!-- role=log + aria-live: the old chat terminal announced nothing at
             all, so a screen-reader user never learned an answer had arrived. -->
        <div class="ni-log" id="assistantOutput" role="log" aria-live="polite"
             aria-relevant="additions" aria-label="Conversation" tabindex="0">
          <div class="ni-state-note" id="niIdleNote">
            <b>Ask NOVA a question.</b>
            Each question is answered on its own — NOVA is not given the previous
            one, and returns no source links. What it can read is listed alongside.
          </div>
        </div>

        <div class="ni-composer">
          <div class="ni-suggest">
            <button class="ni-sg" type="button" data-cmd="What matters now">What matters now</button>
            <button class="ni-sg" type="button" data-cmd="Current regime">Current regime</button>
            <button class="ni-sg" type="button" data-cmd="Is this a good tape?">Is this a good tape?</button>
            <button class="ni-sg" type="button" data-cmd="Key risks today">Key risks today</button>
          </div>
          <div class="ni-crow">
            <div class="ni-cfield">
              <label for="assistantInput">Ask NOVA</label>
              <input class="ni-cinput" id="assistantInput" type="text" autocomplete="off"
                     placeholder="What is the tape telling us into the open?" />
            </div>
            <button class="ni-ask" id="assistantSend" type="button">Ask</button>
          </div>
          <div class="ni-chint">Each question is answered on its own — NOVA does not carry the previous one forward.</div>
        </div>
      </section>

      <!-- ── CONTEXT RAIL ── -->
      <aside class="ni-rail" aria-label="What NOVA can see">

        <section class="panel ni-panel" aria-labelledby="niSeeTitle">
          <div class="ni-ph">
            <h2 id="niSeeTitle">Context available when asked</h2>
            <span class="ni-sub" id="niSeeSub">8 sources</span>
          </div>
          <div id="niSources">
            <div class="ni-srow"><span class="ni-sk">Session &amp; risk posture</span><span class="ni-sv">—</span></div>
            <div class="ni-srow"><span class="ni-sk">Market reality</span><span class="ni-sv">—</span></div>
            <div class="ni-srow"><span class="ni-sk">Market structure</span><span class="ni-sv">—</span></div>
            <div class="ni-srow"><span class="ni-sk">Liquidity</span><span class="ni-sv">—</span></div>
            <div class="ni-srow"><span class="ni-sk">Participation</span><span class="ni-sv">—</span></div>
            <div class="ni-srow"><span class="ni-sk">Cross-market</span><span class="ni-sv">—</span></div>
            <div class="ni-srow"><span class="ni-sk">Synthesis</span><span class="ni-sv">—</span></div>
            <div class="ni-srow"><span class="ni-sk">Session memory</span><span class="ni-sv">—</span></div>
          </div>
          <div class="ni-rail-note">
            Availability and age are read from each source's own route. <b>Whether NOVA
            incorporated a source is not reported by the chat route — availability is
            proven, use is not.</b>
          </div>
        </section>

        <section class="panel ni-panel" aria-labelledby="niMemTitle">
          <div class="ni-ph">
            <h2 id="niMemTitle">Working memory</h2>
            <span class="ni-sub">GET /assistant-data</span>
          </div>
          <div id="niMemory">
            <div class="ni-rail-empty">Not read yet.</div>
          </div>
          <div class="ni-rail-note">
            Read from <code>GET /assistant-data</code>. NOVA can set the focus and add or
            clear these when you ask it to. Persists between sessions, and is the only
            thing NOVA remembers.
          </div>
        </section>

        <section class="panel ni-panel" aria-labelledby="niLimTitle">
          <div class="ni-ph"><h2 id="niLimTitle">Limits</h2></div>
          <div class="ni-lim">
            <b>No source citations</b> — no citation or provenance fields exist in the intelligence layer.<br>
            <b>No conversation memory</b> — only the current question is sent; earlier turns are not.<br>
            <b>Replies capped at 1–3 sentences</b> by the prompt contract, so long-form answers are unavailable.<br>
            <b>No live quotes</b> — context is stored state, not a market feed.<br>
            <b>No TradingView access, scanners, or portfolio analysis.</b><br>
            <b>Analysis only</b> — NOVA cannot place, size, or close a trade.<br>
            <span class="ni-lim-open">Which sources NOVA actually used is not returned by the
            chat route — that needs a response-contract change.</span>
          </div>
        </section>

      </aside>
    </div>
  </div>

'''
