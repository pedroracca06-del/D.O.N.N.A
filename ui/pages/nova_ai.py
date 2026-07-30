"""ui/pages/nova_ai.py — NOVA Intelligence (assistant) page markup
(id="page-assistant", kept unchanged internally -- only the nav's and
page's visible text changed).

Commit #11 correction: the page's rendered heading (`.donna-logo`, the
large stylized title at the top of the Command Interface panel) was
"NOVA" -- it did not match the approved page heading "NOVA Intelligence"
even though the nav label had already been corrected. Only that one
text node changed; the per-message chat role tag ("NOVA" as the
assistant's speaker label inside chat bubbles) and the "NOVA is
thinking..." typing-indicator copy are conversational identity text, not
the page heading, and are unchanged.
"""
NOVA_AI_HTML = '''  <!-- ════════════════════ ASSISTANT ════════════════════ -->
  <div class="page" id="page-assistant">
    <div class="vstack">

      <!-- COMMAND INTERFACE PANEL -->
      <div class="panel" style="padding:0;overflow:hidden">

        <!-- NOVA HEADER -->
        <div class="donna-header">
          <div class="donna-logo">NOVA Intelligence</div>
          <div class="donna-online-row">
            <div class="donna-online-dot"></div>
            <span class="donna-online-text">Online</span>
          </div>
          <div class="donna-tagline">Neural Operations &amp; Volatility Assistant · Command Interface v5</div>
        </div>

        <!-- CHAT AREA -->
        <div style="padding:16px">
          <div class="chat-terminal" id="assistantOutput">
            <div class="msg assistant">
              <span class="role">NOVA</span>
              Command interface ready. I am monitoring macro conditions, market structure, and risk levels. Ask me anything or use a quick command below.
              <div><span class="msg-tag ANALYSIS">ANALYSIS</span></div>
            </div>
            <div class="msg-clearfix"></div>
          </div>
          <div class="typing-indicator" id="typingIndicator">
            <span class="typing-dots"><span></span><span></span><span></span></span>&nbsp;&nbsp;NOVA is thinking...
          </div>
          <div class="quick-cmds">
            <button class="quick-cmd-btn" data-cmd="What matters now">What matters now</button>
            <button class="quick-cmd-btn" data-cmd="Current regime">Current regime</button>
            <button class="quick-cmd-btn" data-cmd="Is this a good tape?">Is this a good tape?</button>
            <button class="quick-cmd-btn" data-cmd="Key risks today">Key risks today</button>
          </div>
          <div class="chat-input-row">
            <input class="chat-input" id="assistantInput" type="text" placeholder="Enter command or question..." />
            <button class="send-btn" id="assistantSend">SEND</button>
          </div>
        </div>

      </div>

    </div>
  </div>

'''
