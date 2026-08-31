"""ui/styles.py — NOVA dashboard CSS, extracted verbatim from ui/html.py
during the interface-modularization foundation (commit #9). No visual,
selector, or rule change was made — this is the exact same CSS text that
was previously inline inside DASHBOARD_HTML's <style> block.
"""
DASHBOARD_CSS = '''*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#080b12;
  --bg2:#0d1420;
  --panel:#10161f;
  --panel2:#131b29;
  --line:#232b3a;
  --line2:#1c2330;
  --text:#f3f6fb;
  --muted:#a7b1c2;
  --muted2:#828ca0;
  --blue:#4f8dff;
  --blue2:#3b82f6;
  --blue-text:#8fb8ff;
  --green:#3ddc97;
  --green2:rgba(61,220,151,.12);
  --yellow:#fbbf24;
  --red:#ff6b6b;
  --red2:rgba(255,107,107,.12);
  --gold:#e0ab4e;
  --ai:#9b8cff;
  --ai2:rgba(155,140,255,.13);
  --shadow:0 1px 4px rgba(0,0,0,.45);
  --shadow2:0 2px 8px rgba(0,0,0,.35);
  --radius:16px;
  --radius2:10px;
  --sidebar-w:224px;
  --tablet-nav-h:60px;
  --mobile-nav-h:64px;
}
@media(prefers-color-scheme:light){
  :root{
    --bg:#f7f5f2;
    --bg2:#edeae5;
    --panel:#ffffff;
    --panel2:#fafaf9;
    --line:#e8e2d9;
    --line2:#f0ebe4;
    --text:#1a1a1a;
    --muted:#6b5e50;
    --muted2:#9a8e80;
    --blue:#2563eb;
    --blue2:#1d4ed8;
    --green:#1e6e41;
    --green2:rgba(30,110,65,.08);
    --yellow:#b8860b;
    --red:#c0392b;
    --red2:rgba(192,57,43,.08);
    --gold:#b8860b;
    --ai:#6d28d9;
    --ai2:rgba(109,40,217,.08);
    --shadow:0 1px 3px rgba(0,0,0,.07);
    --shadow2:0 1px 2px rgba(0,0,0,.05);
  }
}

html,body{min-height:100%;background:var(--bg)}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  color:var(--text);
  background:var(--bg);
  padding:0;
}
.wrap{max-width:1560px;margin:0 auto;padding:20px 24px 40px}

/* ── APP SHELL ── */
.app-shell{display:flex;align-items:stretch;min-height:100vh}
.main-content{flex:1;min-width:0}

/* ── SIDEBAR / RESPONSIVE NAV ── */
.sidebar{
  flex-shrink:0;width:var(--sidebar-w);
  display:flex;flex-direction:column;gap:24px;
  padding:20px 14px;
  background:var(--bg2);border-right:1px solid var(--line);
  position:sticky;top:0;height:100vh;overflow-y:auto;
}
.sidebar-brand{display:flex;align-items:center;gap:10px;padding:0 8px}
.sidebar-mark{
  width:26px;height:26px;border-radius:7px;flex-shrink:0;
  background:linear-gradient(135deg,var(--blue),var(--ai));
}
.sidebar-brand-text{display:flex;flex-direction:column;gap:1px;min-width:0}
.sidebar-wordmark{
  font-family:'Rajdhani',sans-serif;font-size:19px;font-weight:700;
  letter-spacing:4px;color:var(--text);line-height:1.05;
}
/* Approved brand subtitle. "Market Intelligence" names what the product is,
   so it is meaningful text and sits on the 11px floor like every other
   meaningful label -- not the 10px optional-kicker exception it previously
   claimed. Letter-spacing tightened so it still fits the 224px sidebar on
   one line at the larger size. */
.sidebar-subtitle{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.9px;
  color:var(--muted2);text-transform:uppercase;white-space:nowrap;
}
/* Backend connection state -- never a hard-coded "All systems normal". */
.sidebar-status{
  margin-top:auto;display:flex;align-items:center;gap:8px;
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.4px;
  padding:8px 10px;border-radius:8px;background:var(--panel2);
  color:var(--muted2);
}
.sidebar-status .d{width:7px;height:7px;border-radius:50%;background:var(--muted2);flex-shrink:0}
.sidebar-status.online{color:var(--green)}.sidebar-status.online .d{background:var(--green)}
.sidebar-status.offline{color:var(--red)}.sidebar-status.offline .d{background:var(--red)}
.sidebar-status.connecting{color:var(--muted2)}.sidebar-status.connecting .d{background:var(--muted2)}
.content-header{
  display:flex;justify-content:space-between;align-items:center;
  gap:16px;flex-wrap:wrap;margin-bottom:16px;
}
.brand-tag{
  font-family:'Space Mono',monospace;
  font-size:10px;color:var(--muted2);letter-spacing:1px;
  border:1px solid var(--line);padding:4px 8px;border-radius:6px;
}
.status-badge{
  display:flex;align-items:center;gap:8px;
  padding:8px 14px;border-radius:999px;
  background:var(--green2);border:1px solid rgba(52,211,153,.25);
  font-family:'Space Mono',monospace;font-size:11px;color:var(--green);font-weight:700;
  letter-spacing:1px;
}
.dot{
  width:8px;height:8px;border-radius:50%;background:var(--green);
  animation:pulse 2s ease-in-out infinite;
}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(.85)}}
.nav{display:flex;flex-direction:column;gap:4px;flex:1}
/* Sentence case per the approved design family (was uppercase). min-height
   44px meets the touch-target floor without changing the nav's layout. */
.tab-btn{
  display:flex;align-items:center;gap:10px;
  font-family:'Rajdhani',sans-serif;font-size:14px;font-weight:700;letter-spacing:.3px;
  border:1px solid transparent;padding:11px 12px;border-radius:8px;min-height:44px;
  background:transparent;color:var(--muted);text-align:left;
  cursor:pointer;transition:all .15s ease;
}
.tab-btn::before{
  content:'';display:block;flex-shrink:0;width:18px;height:18px;
  background-color:currentColor;
  -webkit-mask-image:var(--icon);mask-image:var(--icon);
  -webkit-mask-size:contain;mask-size:contain;
  -webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;
  -webkit-mask-position:center;mask-position:center;
}
.tab-btn[data-page="dashboard"]{--icon:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23000%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Crect x=%223%22 y=%223%22 width=%228%22 height=%228%22 rx=%221.5%22/%3E%3Crect x=%2213%22 y=%223%22 width=%228%22 height=%225%22 rx=%221.5%22/%3E%3Crect x=%2213%22 y=%2212%22 width=%228%22 height=%229%22 rx=%221.5%22/%3E%3Crect x=%223%22 y=%2215%22 width=%228%22 height=%226%22 rx=%221.5%22/%3E%3C/svg%3E')}
.tab-btn[data-page="journal"]{--icon:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23000%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M6 3h11a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V3Z%22/%3E%3Cpath d=%22M6 3a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2%22/%3E%3Cline x1=%229%22 y1=%228%22 x2=%2214%22 y2=%228%22/%3E%3Cline x1=%229%22 y1=%2212%22 x2=%2214%22 y2=%2212%22/%3E%3C/svg%3E')}
.tab-btn[data-page="news"]{--icon:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23000%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpolyline points=%223 17 9 11 13 15 21 6%22/%3E%3Cpolyline points=%2215 6 21 6 21 12%22/%3E%3C/svg%3E')}
.tab-btn[data-page="assistant"]{--icon:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23000%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z%22/%3E%3Cpath d=%22M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z%22/%3E%3C/svg%3E')}
.tab-btn[data-page="settings"]{--icon:url('data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23000%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%223%22/%3E%3Cpath d=%22M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z%22/%3E%3C/svg%3E')}
.tab-btn:hover{color:var(--text);background:var(--panel2)}
.tab-btn.active{
  background:rgba(79,141,255,.14);
  border-color:rgba(79,141,255,.35);color:#dce9ff;
}

/* ── LIVE STRIP ── */
.live-strip-row{
  display:grid;grid-template-columns:160px 1fr 200px;gap:10px;
  align-items:center;margin-bottom:16px;
}
.live-label{
  font-family:'Space Mono',monospace;font-size:10px;letter-spacing:2px;
  color:var(--red);text-transform:uppercase;
  padding:12px 14px;border-radius:var(--radius2);
  background:var(--red2);border:1px solid rgba(192,57,43,.15);
}
.ticker-wrap{
  overflow:hidden;border-radius:var(--radius2);
  background:var(--panel);border:1px solid var(--line);
  height:42px;display:flex;align-items:center;position:relative;
}
.ticker-wrap::before,.ticker-wrap::after{
  content:'';position:absolute;top:0;bottom:0;width:40px;z-index:2;
}
.ticker-wrap::before{left:0;background:linear-gradient(to right,var(--panel),transparent)}
.ticker-wrap::after{right:0;background:linear-gradient(to left,var(--panel),transparent)}
.ticker-track{
  display:inline-flex;white-space:nowrap;padding-left:100%;
  animation:tickerMove 35s linear infinite;
}
@keyframes tickerMove{0%{transform:translateX(0)}100%{transform:translateX(-100%)}}
.ticker-item{
  padding-right:36px;font-family:'Space Mono',monospace;font-size:11px;
  color:var(--muted);
}
.ticker-item b{color:var(--text);font-weight:700}
.ticker-item .up{color:var(--green)}
.ticker-item .dn{color:var(--red)}
.session-chip{
  font-family:'Rajdhani',sans-serif;
  text-align:center;padding:10px 14px;border-radius:var(--radius2);
  background:var(--panel);border:1px solid var(--line);
}
.session-chip .lab{font-size:10px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase}
.session-chip .val{font-size:20px;font-weight:700;margin-top:2px;letter-spacing:1px}

/* ── SHARED PANEL ── */
.panel,.card{
  background:var(--panel);
  border:1px solid var(--line);border-radius:var(--radius);
  box-shadow:var(--shadow2);padding:17px;
}
.panel-sm{padding:11px 14px}
.kicker{
  font-family:'Space Mono',monospace;font-size:10px;letter-spacing:2px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:10px;
}
.section-title{
  font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:700;
  letter-spacing:.5px;line-height:1.1;
}
.page{display:none}.page.active{display:block}
.vstack{display:grid;gap:16px}

/* ── TABLES ── */
table{width:100%;border-collapse:collapse}
th{
  font-family:'Space Mono',monospace;font-size:10px;letter-spacing:1.5px;
  color:var(--muted2);text-transform:uppercase;text-align:left;
  padding:0 0 10px;border-bottom:1px solid var(--line2);
}
td{
  padding:11px 0;border-bottom:1px solid var(--line2);
  font-size:14px;font-weight:600;
}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--panel2)}
.up{color:var(--green)}.dn{color:var(--red)}
.neutral{color:var(--muted)}

/* ── RISK BADGES ── */
.risk-badge{
  display:inline-block;padding:4px 10px;border-radius:6px;
  font-family:'Space Mono',monospace;font-size:11px;font-weight:700;
  letter-spacing:1px;text-transform:uppercase;
}
.risk-low{background:var(--green2);color:var(--green);border:1px solid rgba(30,110,65,.2)}
.risk-medium{background:rgba(184,134,11,.08);color:var(--yellow);border:1px solid rgba(184,134,11,.2)}
.risk-high{background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.2)}

/* ── KV ROWS ── */
.kv-row{
  display:flex;justify-content:space-between;align-items:center;gap:12px;
  padding:11px 0;border-bottom:1px solid var(--line2);
}
.kv-row:last-child{border-bottom:none}
.kv-k{color:var(--muted);font-size:13px}
.kv-v{color:var(--text);font-size:13px;font-weight:600;text-align:right;max-width:60%}

/* ── OBSERVATION CARDS ── */
.obs-item{
  padding:13px 16px;border-radius:10px;margin-bottom:10px;
  border-left:3px solid var(--muted2);
  background:var(--panel2);border:1px solid var(--line);
}
.obs-item:last-child{margin-bottom:0}
.obs-item.high{border-left-color:var(--red);background:var(--red2)}
.obs-item.medium{border-left-color:var(--yellow);background:rgba(184,134,11,.05)}
.obs-item.low{border-left-color:var(--line);background:var(--panel2)}
.obs-title{font-size:13px;font-weight:700;margin-bottom:4px}
.obs-body{font-size:12px;color:var(--muted);line-height:1.5}

/* ── STAT GRID ── */
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.stat-card{text-align:center;padding:18px 14px}
.stat-card .s-lab{
  font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:10px;
}
.stat-card .s-val{
  font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;letter-spacing:1px;
  line-height:1;
}
.stat-card .s-sub{margin-top:6px;font-size:11px;color:var(--muted2);line-height:1.4}

/* ── MAIN GRID ── */
.main-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;align-items:start}
.left-stack,.right-stack{display:grid;gap:16px}

/* ── KV ROW (shared: Settings) ── */
.exec-row{display:flex;justify-content:space-between;align-items:baseline;gap:8px;
  padding:8px 0;border-bottom:1px solid var(--line2)}
.exec-row:last-child{border-bottom:none}
.exec-row-label{font-size:12px;color:var(--muted)}
.exec-row-val{font-size:13px;font-weight:700;color:var(--text);text-align:right;max-width:65%}

/* ── NEWS ── */
.breaking-bar{
  display:flex;align-items:center;gap:0;overflow:hidden;
  border-radius:10px;background:var(--red2);
  border:1px solid rgba(192,57,43,.2);height:38px;margin-bottom:0;
}
.breaking-label{
  flex-shrink:0;padding:0 14px;font-family:'Space Mono',monospace;
  font-size:10px;letter-spacing:2px;color:var(--red);text-transform:uppercase;
  border-right:1px solid rgba(192,57,43,.2);height:100%;
  display:flex;align-items:center;background:rgba(192,57,43,.1);
}
.breaking-ticker-wrap{
  flex:1;overflow:hidden;position:relative;height:100%;display:flex;align-items:center;
}
.breaking-ticker-track{
  display:inline-flex;white-space:nowrap;padding-left:100%;
  animation:tickerMove 50s linear infinite;font-size:12px;font-weight:600;color:var(--text);
  gap:0;
}
.breaking-item{margin-right:60px;color:var(--text)}
.breaking-item::before{content:'▸ ';color:var(--red);margin-right:4px}
.index-tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}
.index-tile{
  padding:14px 16px;border-radius:14px;border:1px solid var(--line);
  background:var(--panel);text-align:center;transition:border-color .15s;
  position:relative;
}
.index-tile:hover{border-color:var(--muted2)}
/* ── CUSTOMIZABLE TILE PICKER ── */
.tile-edit-btn{
  position:absolute;top:6px;right:6px;
  width:18px;height:18px;border-radius:4px;
  border:1px solid var(--line);background:var(--panel2);
  color:var(--muted2);font-size:10px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  opacity:0;transition:opacity .15s;padding:0;line-height:1;
}
.index-tile:hover .tile-edit-btn{opacity:1}
.tile-picker{
  position:absolute;top:calc(100% + 4px);left:0;right:0;z-index:200;
  background:var(--panel);border:1px solid var(--line);border-radius:10px;
  box-shadow:0 4px 20px rgba(0,0,0,.12);padding:4px;
  display:none;
}
.tile-picker.open{display:block}
.tile-picker-item{
  padding:6px 10px;border-radius:6px;font-family:'Space Mono',monospace;
  font-size:10px;letter-spacing:.5px;cursor:pointer;color:var(--text);
  transition:background .1s;
}
.tile-picker-item:hover{background:var(--panel2)}
.tile-picker-item.active{color:var(--green);font-weight:700}
.tile-picker-reset{
  padding:5px 10px 4px;font-family:'Space Mono',monospace;font-size:9px;
  letter-spacing:.5px;cursor:pointer;color:var(--muted2);
  border-top:1px solid var(--line);margin-top:2px;padding-top:6px;
}
.tile-picker-reset:hover{color:var(--red)}
.index-tile-name{
  font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:6px;
}
.index-tile-val{
  font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:700;line-height:1;
}
.index-tile-chg{
  margin-top:4px;font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.5px;
}
.index-tile.up{border-left:3px solid var(--green)}
.index-tile.dn{border-left:3px solid var(--red)}
.feature-story{
  padding:20px 22px;border-radius:16px;
  border:1px solid var(--line);
  background:var(--panel);
  box-shadow:var(--shadow2);
}
.story-tag{
  display:inline-block;padding:3px 10px;border-radius:6px;margin-bottom:10px;
  font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;
  text-transform:uppercase;font-weight:700;
}
.story-tag.MACRO{background:rgba(37,99,235,.08);color:var(--blue);border:1px solid rgba(37,99,235,.15)}
.story-tag.MARKET{background:var(--green2);color:var(--green);border:1px solid rgba(30,110,65,.2)}
.story-tag.ENERGY{background:rgba(184,134,11,.08);color:var(--gold);border:1px solid rgba(184,134,11,.2)}
.story-tag.GEOPOLITICAL{background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.2)}
.story-tag.CALENDAR{background:rgba(184,134,11,.08);color:var(--yellow);border:1px solid rgba(184,134,11,.2)}
.feature-headline{
  font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;
  line-height:1.1;letter-spacing:.3px;margin-bottom:10px;
}
.feature-note{font-size:13px;color:var(--muted);line-height:1.6}
.news-numbered-item{
  display:flex;gap:12px;padding:13px 0;border-bottom:1px solid var(--line2);
}
.news-numbered-item:last-child{border-bottom:none}
.news-num{
  flex-shrink:0;width:22px;font-family:'Space Mono',monospace;
  font-size:11px;color:var(--muted2);padding-top:2px;
}
.news-body{}
.news-headline{font-size:13px;font-weight:600;line-height:1.45;color:var(--text)}
.news-meta{margin-top:4px;font-size:11px;color:var(--muted2)}
.news-summary{margin-top:5px;font-size:12px;color:var(--muted);line-height:1.5}
.news-link{color:var(--blue);font-size:11px;text-decoration:none}
.news-link:hover{text-decoration:underline}
.news-sidebar-panel{
  padding:18px;border-radius:16px;
  border:1px solid var(--line);background:var(--panel);
  box-shadow:var(--shadow);
}
.sidebar-section{margin-bottom:20px}
.sidebar-section:last-child{margin-bottom:0}
.sidebar-kicker{
  font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:10px;
  padding-bottom:6px;border-bottom:1px solid var(--line2);
}
.donna-read{font-size:12px;color:var(--muted);line-height:1.6}
.risk-level-row{
  display:flex;justify-content:space-between;align-items:center;
  padding:7px 0;border-bottom:1px solid var(--line2);
}
.risk-level-row:last-child{border-bottom:none}
.risk-level-label{font-size:12px;color:var(--muted)}
.watch-name{
  display:inline-block;padding:3px 10px;border-radius:6px;margin:3px 3px 3px 0;
  background:rgba(37,99,235,.06);border:1px solid rgba(37,99,235,.12);
  font-family:'Rajdhani',sans-serif;font-size:14px;font-weight:700;color:var(--blue);
}

#newsList{min-height:120px}

/* ── NEWS FUTURES STRIP ── */
.news-futures-strip{
  display:flex;align-items:center;gap:0;overflow:hidden;
  border-radius:10px;background:var(--panel);border:1px solid var(--line);height:36px;
}
.news-futures-label{
  flex-shrink:0;padding:0 12px;font-family:'Space Mono',monospace;
  font-size:9px;letter-spacing:2px;color:var(--muted2);text-transform:uppercase;
  border-right:1px solid var(--line);height:100%;
  display:flex;align-items:center;background:var(--panel2);white-space:nowrap;
}
.news-futures-track-wrap{flex:1;overflow:hidden;position:relative;height:100%;display:flex;align-items:center}
.news-futures-track{
  display:inline-flex;white-space:nowrap;padding-left:100%;
  animation:tickerMove 45s linear infinite;
}
.nf-item{
  margin-right:28px;font-family:'Space Mono',monospace;font-size:10px;
  display:inline-flex;align-items:center;gap:5px;
}
.nf-sym{color:var(--muted2);letter-spacing:1px;font-size:9px;text-transform:uppercase}
.nf-val{color:var(--text);font-weight:700}
.nf-pct{font-size:9px}.nf-pct.up{color:var(--green)}.nf-pct.dn{color:var(--red)}

/* ── TRENDING MOVERS ── */
.movers-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.movers-col-title{
  font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;text-transform:uppercase;
  margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid var(--line2);
}
.movers-col-title.gainers{color:var(--green)}.movers-col-title.losers{color:var(--red)}
.mover-row{
  display:flex;justify-content:space-between;align-items:center;
  padding:7px 0;border-bottom:1px solid var(--line2);
}
.mover-row:last-child{border-bottom:none}
.mover-left{display:flex;flex-direction:column}
.mover-sym{font-family:'Rajdhani',sans-serif;font-size:14px;font-weight:700;color:var(--text)}
.mover-name{font-size:10px;color:var(--muted2)}
.mover-pct{font-family:'Space Mono',monospace;font-size:11px;font-weight:700}
.mover-pct.up{color:var(--green)}.mover-pct.dn{color:var(--red)}

/* ── SECTOR HEAT / TREEMAP ── */
.donna-says-box{padding:16px 18px;border-radius:14px;background:var(--bg2);border:1px solid var(--line)}
.donna-says-label{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:2px;text-transform:uppercase;color:var(--muted2);margin-bottom:8px}
.donna-says-text{font-size:12px;color:#888;line-height:1.65}

/* ── MACRO RADAR (Economic Calendar) ── */
.econ-no-events{font-size:12px;color:var(--muted2);padding:4px 0}
.mre-day-sep{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;padding:8px 0 6px;margin-top:10px;border-bottom:1px solid var(--line);margin-bottom:8px}
.mre-day-sep:first-child{margin-top:0}
.mre-day-sep.today{color:var(--text);font-weight:700}
.mre-day-sep.other{color:var(--muted2)}
/* Event cards */
.macro-radar-event{border-radius:10px;margin-bottom:8px;overflow:hidden;border:1px solid var(--line);border-left:3px solid transparent}
.macro-radar-event.impact-high{border-color:rgba(192,57,43,.25);border-left-color:var(--red)}
.macro-radar-event.impact-high.live{box-shadow:0 0 0 1px rgba(192,57,43,.2)}
.macro-radar-event.impact-medium{border-left-color:var(--gold)}
.macro-radar-event.impact-low{border-left-color:var(--line);border-color:transparent}
.macro-radar-event.released{opacity:.55}
.mre-header{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;gap:8px}
.mre-header.impact-high{background:rgba(192,57,43,.04)}
.mre-header.impact-medium{background:rgba(184,134,11,.03)}
.mre-header.impact-low{background:transparent;padding:6px 10px}
.mre-impact-badge{display:flex;align-items:center;gap:5px;font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1px;text-transform:uppercase;font-weight:700}
.mre-impact-badge.high{color:var(--red)}
.mre-impact-badge.medium{color:var(--gold)}
.mre-impact-badge.low{color:var(--muted2)}
.mre-impact-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.mre-impact-dot.high{background:var(--red)}
.mre-impact-dot.medium{background:var(--gold)}
.mre-impact-dot.low{background:var(--muted2);opacity:.5}
/* Countdown badges */
.mre-countdown{font-family:'Space Mono',monospace;font-size:8px;font-weight:700;letter-spacing:.8px;padding:3px 8px;border-radius:5px;text-transform:uppercase;white-space:nowrap;flex-shrink:0}
.mre-countdown.live{background:rgba(192,57,43,.14);color:var(--red);animation:_mrePulse 1.4s ease-in-out infinite}
.mre-countdown.lock{background:rgba(192,57,43,.1);color:var(--red)}
.mre-countdown.soon{background:rgba(192,57,43,.08);color:var(--red)}
.mre-countdown.upcoming{background:rgba(184,134,11,.08);color:var(--gold)}
.mre-countdown.future{color:var(--muted2);padding:0}
.mre-countdown.released{color:var(--muted2);padding:0}
@keyframes _mrePulse{0%,100%{opacity:1}50%{opacity:.5}}
/* Card body */
.mre-body{padding:0 12px 10px}
.mre-title-high{font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;line-height:1.2;color:var(--text);margin-bottom:5px}
.mre-title-med{font-family:'Rajdhani',sans-serif;font-size:14px;font-weight:700;line-height:1.2;color:var(--text);margin-bottom:4px}
.mre-meta-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.mre-time{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2);white-space:nowrap}
.mre-vals{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2)}
.mre-verdict{display:inline-block;padding:1px 6px;border-radius:4px;font-family:'Space Mono',monospace;font-size:8px;font-weight:700}
.mre-verdict.hot{background:rgba(192,57,43,.1);color:var(--red)}
.mre-verdict.miss{background:rgba(30,110,65,.1);color:var(--green)}
.mre-verdict.inline{background:rgba(0,0,0,.05);color:var(--muted2)}
/* Gov lock bar */
.mre-gov-bar{padding:5px 12px;border-top:1px solid rgba(192,57,43,.15);background:rgba(192,57,43,.04);display:flex;align-items:center;gap:6px;font-family:'Space Mono',monospace;font-size:7px;color:var(--red);letter-spacing:.5px;text-transform:uppercase}
/* Compact LOW rows */
.mre-compact{display:flex;align-items:center;gap:8px;padding:4px 10px;border-radius:6px}
.mre-compact:hover{background:var(--panel2)}
.mre-compact .mre-time{width:34px;flex-shrink:0}
.mre-compact-title{font-size:11px;color:var(--muted);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mre-compact-dot{width:4px;height:4px;border-radius:50%;background:var(--muted2);opacity:.4;flex-shrink:0}

/* ── ASSISTANT ── */
.donna-header{
  text-align:center;padding:24px 20px 16px;
  border-bottom:1px solid var(--line);margin-bottom:0;
}
.donna-logo{
  font-family:'Rajdhani',sans-serif;font-size:52px;font-weight:700;letter-spacing:12px;
  color:var(--text);line-height:1;
}
.donna-online-row{
  display:flex;align-items:center;justify-content:center;gap:8px;margin-top:8px;
}
.donna-online-dot{
  width:7px;height:7px;border-radius:50%;background:var(--green);
  animation:pulse 2s ease-in-out infinite;
}
.donna-online-text{
  font-family:'Space Mono',monospace;font-size:10px;letter-spacing:2.5px;
  color:var(--green);text-transform:uppercase;
}
.donna-tagline{
  margin-top:6px;font-family:'Space Mono',monospace;font-size:9px;
  letter-spacing:1.5px;color:var(--muted2);
}
.chat-terminal{
  min-height:320px;max-height:500px;overflow-y:auto;
  border-radius:12px;
  background:var(--panel2);
  border:1px solid var(--line);
  padding:16px;margin-bottom:12px;
}
.chat-terminal::-webkit-scrollbar{width:4px}
.chat-terminal::-webkit-scrollbar-track{background:transparent}
.chat-terminal::-webkit-scrollbar-thumb{background:rgba(0,0,0,.12);border-radius:2px}
.msg{margin-bottom:12px;max-width:82%;line-height:1.55;font-size:13px;clear:both}
.msg.user{
  float:right;text-align:right;
  padding:10px 14px;border-radius:14px 14px 4px 14px;
  background:var(--text);color:var(--panel);
  border:none;
}
.msg.assistant{
  float:left;
  padding:10px 14px 10px 16px;border-radius:14px 14px 14px 4px;
  background:var(--panel);
  border:1px solid var(--line);
  border-left:3px solid var(--green);
}
.msg-clearfix{clear:both;display:table;width:100%}
.msg .role{
  display:block;font-family:'Space Mono',monospace;font-size:9px;
  letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:5px;
}
.msg.user .role{color:rgba(255,255,255,.5)}
.msg.assistant .role{color:var(--green)}
.msg-tag{
  display:inline-block;margin-top:6px;padding:2px 8px;border-radius:5px;
  font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1.5px;
  text-transform:uppercase;
}
.msg-tag.ANALYSIS{background:rgba(37,99,235,.08);color:var(--blue);border:1px solid rgba(37,99,235,.15)}
.msg-tag.EXECUTION{background:var(--green2);color:var(--green);border:1px solid rgba(30,110,65,.2)}
.msg-tag.RISK{background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.2)}
.msg-tag.CALENDAR{background:rgba(184,134,11,.08);color:var(--yellow);border:1px solid rgba(184,134,11,.2)}
.typing-indicator{
  float:left;clear:both;padding:10px 16px;border-radius:14px 14px 14px 4px;
  background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--green);
  font-family:'Space Mono',monospace;font-size:11px;color:var(--green);
  display:none;margin-bottom:12px;
}
.typing-indicator.active{display:block}
@keyframes blink{0%,80%,100%{opacity:.2}40%{opacity:1}}
.typing-dots span{display:inline-block;width:5px;height:5px;border-radius:50%;
  background:var(--green);margin:0 2px;animation:blink 1.4s infinite}
.typing-dots span:nth-child(2){animation-delay:.2s}
.typing-dots span:nth-child(3){animation-delay:.4s}
.quick-cmds{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.quick-cmd-btn{
  padding:7px 13px;border-radius:8px;cursor:pointer;
  border:1px solid var(--line);background:var(--panel2);
  color:var(--muted);font-family:'Space Mono',monospace;font-size:10px;
  letter-spacing:.5px;transition:all .15s;
}
.quick-cmd-btn:hover{border-color:var(--muted2);color:var(--text)}
.chat-input-row{display:flex;gap:10px}
.chat-input{
  flex:1;padding:12px 16px;border-radius:10px;
  border:1px solid var(--line);background:var(--panel2);
  color:var(--text);font-family:system-ui,-apple-system,sans-serif;font-size:13px;
  outline:none;transition:border-color .15s;
}
.chat-input:focus{border-color:var(--muted2)}
.send-btn{
  padding:12px 22px;border-radius:10px;border:1px solid var(--text);cursor:pointer;
  background:var(--text);
  color:var(--panel);font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;
  letter-spacing:1px;transition:opacity .15s;white-space:nowrap;
}
.send-btn:hover{opacity:.82}
.send-btn:disabled{opacity:.4;cursor:not-allowed}
.del-btn{
  background:none;border:none;color:var(--muted2);cursor:pointer;
  font-size:15px;padding:2px 6px;border-radius:6px;transition:all .15s;
}
.del-btn:hover{background:var(--red2);color:var(--red)}


/* ── FOOTER ──
   Both halves are meaningful: the left names the running build, the right
   (#lastUpdated) is the page's freshness statement -- the only place the
   last successful sync time is reported. Neither is decorative, so both sit
   on the 11px meaningful-text floor rather than the former 10px. */
.footer{
  margin-top:24px;display:flex;justify-content:space-between;
  gap:12px;flex-wrap:wrap;
  font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);
  letter-spacing:.5px;
}

/* ── JOURNAL TAB ── */
/* sub-nav */
.j-subnav{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:20px;padding-bottom:0}
.j-subnav-btn{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;padding:9px 18px;border:none;background:none;color:var(--muted2);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;transition:all .15s}
.j-subnav-btn:hover{color:var(--text)}
.j-subnav-btn.active{color:var(--gold);border-bottom-color:var(--gold)}
.j-subnav-count{display:inline-block;background:rgba(184,134,11,.12);color:var(--gold);border-radius:10px;padding:1px 7px;font-size:8px;margin-left:6px;vertical-align:middle}
/* overview header */
.j-overview{display:flex;gap:28px;align-items:center;flex-wrap:wrap;padding:14px 20px;border-radius:12px;background:var(--panel2);border:1px solid var(--line);margin-bottom:16px}
.j-ov-item{display:flex;flex-direction:column;gap:3px}
.j-ov-lab{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase}
.j-ov-val{font-family:'Rajdhani',sans-serif;font-size:20px;font-weight:700;line-height:1}
.j-ov-div{width:1px;background:var(--line);align-self:stretch}
/* intelligence trade card */
.itc{border:1px solid var(--line);border-radius:14px;background:var(--panel2);padding:16px 18px;margin-bottom:12px;border-left:3px solid transparent;transition:border-color .15s}
.itc:hover{border-color:rgba(184,134,11,.25)}
.itc.outcome-WIN{border-left-color:var(--green)}
.itc.outcome-LOSS{border-left-color:var(--red)}
.itc.outcome-BREAKEVEN{border-left-color:var(--yellow)}
.itc.outcome-OPEN{border-left-color:var(--muted2)}
.itc-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px}
.itc-badges{display:flex;gap:5px;flex-wrap:wrap;align-items:center}
.itc-badge{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1px;padding:3px 8px;border-radius:6px;border:1px solid var(--line);color:var(--muted);text-transform:uppercase;background:var(--panel)}
.itc-badge.b-grade-a{border-color:rgba(74,222,128,.4);color:var(--green);background:rgba(74,222,128,.06)}
.itc-badge.b-grade-b{border-color:rgba(251,191,36,.4);color:var(--yellow);background:rgba(251,191,36,.06)}
.itc-badge.b-grade-c{border-color:var(--line);color:var(--muted2)}
.itc-badge.b-nova{border-color:rgba(96,165,250,.4);color:var(--blue);background:rgba(96,165,250,.06)}
.itc-badge.b-session-a{border-color:rgba(74,222,128,.3);color:var(--green)}
.itc-pnl{font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:700;line-height:1;text-align:right}
.itc-time{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2);margin-top:2px;text-align:right}
.itc-exec{font-family:'Space Mono',monospace;font-size:11px;color:var(--text);padding:8px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:8px 0;display:flex;gap:20px;flex-wrap:wrap}
.itc-exec-item{display:flex;flex-direction:column;gap:2px}
.itc-exec-lab{font-size:8px;color:var(--muted2);letter-spacing:1px;text-transform:uppercase}
.itc-exec-val{font-size:12px;font-weight:700;color:var(--text)}
.itc-nova{background:rgba(184,134,11,.04);border:1px solid rgba(184,134,11,.12);border-radius:8px;padding:10px 12px;margin:8px 0;font-size:12px;color:var(--muted);font-style:italic;line-height:1.5}
.itc-nova-label{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1.5px;color:var(--gold);text-transform:uppercase;margin-bottom:5px;font-style:normal}
.itc-ctx{display:flex;gap:16px;flex-wrap:wrap;margin-top:8px}
.itc-ctx-item{display:flex;flex-direction:column;gap:2px}
.itc-ctx-lab{font-family:'Space Mono',monospace;font-size:8px;color:var(--muted2);letter-spacing:1px;text-transform:uppercase}
.itc-ctx-val{font-size:11px;font-weight:600;color:var(--text)}
.itc-footer{display:flex;justify-content:space-between;align-items:center;margin-top:10px;padding-top:8px;border-top:1px solid var(--line)}
.itc-outcome-badge{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1.5px;padding:3px 10px;border-radius:6px;text-transform:uppercase;font-weight:700}
.itc-outcome-badge.WIN{background:rgba(74,222,128,.1);color:var(--green);border:1px solid rgba(74,222,128,.3)}
.itc-outcome-badge.LOSS{background:rgba(255,107,107,.1);color:var(--red);border:1px solid rgba(255,107,107,.3)}
.itc-outcome-badge.BREAKEVEN{background:rgba(251,191,36,.1);color:var(--yellow);border:1px solid rgba(251,191,36,.3)}
.itc-outcome-badge.OPEN{background:rgba(160,160,160,.1);color:var(--muted);border:1px solid var(--line)}
/* signal feed */
.sf-card{border:1px solid var(--line);border-radius:12px;background:var(--panel2);padding:12px 16px;margin-bottom:8px;transition:border-color .15s}
.sf-card:hover{border-color:rgba(184,134,11,.2)}
.sf-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.sf-meta{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.sf-time{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2)}
.sf-symbol{font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;color:var(--text)}
.sf-cmd{font-family:'Space Mono',monospace;font-size:9px;font-weight:700;padding:2px 8px;border-radius:5px;text-transform:uppercase}
.sf-cmd.WAIT{color:var(--muted2);background:rgba(160,160,160,.08);border:1px solid var(--line)}
.sf-cmd.WATCH{color:var(--yellow);background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.2)}
.sf-cmd.BUY,.sf-cmd.LONG{color:var(--green);background:rgba(74,222,128,.08);border:1px solid rgba(74,222,128,.2)}
.sf-cmd.SELL,.sf-cmd.SHORT{color:var(--red);background:rgba(255,107,107,.08);border:1px solid rgba(255,107,107,.2)}
.sf-grade{font-family:'Space Mono',monospace;font-size:9px;font-weight:700}
.sf-grade.A{color:var(--green)}.sf-grade.B{color:var(--yellow)}.sf-grade.C,.sf-grade.D{color:var(--muted2)}
.sf-chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:5px}
.sf-chip{font-family:'Space Mono',monospace;font-size:8px;color:var(--muted2);letter-spacing:.5px}
.sf-chip strong{color:var(--text)}
.sf-notes{font-size:11px;color:var(--muted);font-style:italic;margin-top:6px;padding-top:6px;border-top:1px solid var(--line);line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
/* analytics */
.j-analytics-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px}
.j-stat-card{padding:16px;border-radius:12px;border:1px solid var(--line);background:var(--panel2);text-align:center}
.j-stat-card .jsc-lab{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:8px}
.j-stat-card .jsc-val{font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;line-height:1}
.j-stat-card .jsc-sub{font-size:10px;color:var(--muted2);margin-top:4px}
.regime-breakdown-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-top:12px}
.regime-card{padding:14px 16px;border-radius:12px;border:1px solid var(--line);background:var(--panel2)}
.regime-card .rc-name{font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;margin-bottom:8px}
.regime-card .rc-wr{font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;line-height:1}
.regime-card .rc-sub{font-size:11px;color:var(--muted2);margin-top:4px}
/* log trade modal */
.j-modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px}
.j-modal{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:28px;width:100%;max-width:500px;max-height:90vh;overflow-y:auto}
.j-modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
.j-modal-close{background:none;border:none;font-size:20px;cursor:pointer;color:var(--muted);padding:4px 8px;border-radius:6px}
.j-modal-close:hover{color:var(--text)}
.trade-label{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px;display:block}
.trade-input,.trade-select{width:100%;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:var(--panel2);color:var(--text);font-family:system-ui,-apple-system,sans-serif;font-size:13px;outline:none;transition:border-color .15s}
.trade-input:focus,.trade-select:focus{border-color:var(--muted2)}
.submit-trade-btn{width:100%;padding:13px;border-radius:10px;border:1px solid var(--text);cursor:pointer;background:var(--text);color:var(--panel);font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;letter-spacing:1px;transition:opacity .15s;margin-top:4px}
.submit-trade-btn:hover{opacity:.82}
.submit-trade-btn:disabled{opacity:.4;cursor:not-allowed}
.j-filter-bar{display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.j-filter-btn{padding:5px 14px;border-radius:8px;border:1px solid var(--line);background:var(--panel2);color:var(--muted2);font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1px;cursor:pointer;transition:all .15s;text-transform:uppercase}
.j-filter-btn:hover{border-color:rgba(184,134,11,.3);color:var(--gold)}
.j-filter-btn.active{background:rgba(184,134,11,.08);border-color:rgba(184,134,11,.3);color:var(--gold)}
@media(max-width:600px){.j-overview{gap:16px}.itc-exec{gap:12px}.sf-chips{gap:6px}}

/* ── PAGE HEADER (shared: Settings) ── */
.fd-page-header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:14px}
.fd-page-title{font-family:\'Rajdhani\',sans-serif;font-size:22px;font-weight:700;letter-spacing:1px}
.fd-meta{font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2);letter-spacing:.5px}
.fd-refresh-btn{padding:5px 14px;border-radius:8px;border:1px solid var(--line);background:transparent;color:var(--muted2);font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1px;cursor:pointer;transition:all .15s;text-transform:uppercase}
.fd-refresh-btn:hover{color:var(--text);border-color:var(--muted2)}

/* ── NOVA REVIEW PANEL ── */
.itc-review{margin-top:10px;border:1px solid rgba(184,134,11,.15);border-radius:10px;overflow:hidden}
.itc-review-hdr{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;cursor:pointer;background:rgba(184,134,11,.04);transition:background .15s}
.itc-review-hdr:hover{background:rgba(184,134,11,.08)}
.itc-review-hdr-label{font-family:\'Space Mono\',monospace;font-size:8px;letter-spacing:1.5px;color:var(--gold);text-transform:uppercase}
.itc-review-hdr-ts{font-family:\'Space Mono\',monospace;font-size:8px;color:var(--muted2)}
.itc-review-body{padding:12px 14px;font-size:12px;color:var(--muted);line-height:1.65;display:none;white-space:pre-wrap}
.itc-review-body.open{display:block}
.nova-gen-btn{font-family:\'Space Mono\',monospace;font-size:8px;letter-spacing:1px;padding:5px 14px;border-radius:7px;border:1px solid rgba(184,134,11,.3);background:rgba(184,134,11,.06);color:var(--gold);cursor:pointer;transition:all .15s;text-transform:uppercase;margin-top:8px}
.nova-gen-btn:hover{background:rgba(184,134,11,.12);border-color:rgba(184,134,11,.5)}
.nova-gen-btn:disabled{opacity:.5;cursor:not-allowed}
/* behavioral */
.itc-behavioral{margin-top:8px;padding-top:8px;border-top:1px solid var(--line)}
.itc-beh-label{font-family:\'Space Mono\',monospace;font-size:8px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px}
.beh-flags{display:flex;gap:6px;flex-wrap:wrap}
.beh-flag{font-family:\'Space Mono\',monospace;font-size:8px;padding:2px 8px;border-radius:5px;background:rgba(192,57,43,.08);color:var(--red);border:1px solid rgba(192,57,43,.2)}
.beh-state{font-family:\'Space Mono\',monospace;font-size:8px;padding:2px 8px;border-radius:5px;background:rgba(96,165,250,.08);color:var(--blue);border:1px solid rgba(96,165,250,.2);display:inline-block;margin-bottom:5px}
.beh-reflection{font-size:11px;color:var(--muted);font-style:italic;margin-top:5px}
/* checkbox flags */
.flag-checks{display:flex;gap:10px;flex-wrap:wrap;margin-top:4px}
.flag-check{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--text);cursor:pointer}
.flag-check input{width:14px;height:14px;cursor:pointer;accent-color:var(--gold)}

/* ── TRADE DETAIL MODAL ── */
.jtd-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:1100;display:flex;align-items:flex-start;justify-content:center;padding:24px;overflow-y:auto}
.jtd-modal{background:var(--panel);border:1px solid var(--line);border-radius:16px;width:100%;max-width:900px;min-height:400px;margin:auto}
.jtd-header{display:flex;justify-content:space-between;align-items:center;padding:18px 24px;border-bottom:1px solid var(--line);gap:12px;flex-wrap:wrap}
.jtd-title{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.jtd-close{background:none;border:none;font-size:18px;cursor:pointer;color:var(--muted);padding:4px 10px;border-radius:6px}
.jtd-close:hover{color:var(--text)}
.jtd-body{padding:20px 24px;display:grid;gap:16px}
.jtd-screenshot{width:100%;border-radius:10px;border:1px solid var(--line);overflow:hidden;background:var(--panel2)}
.jtd-screenshot img{width:100%;display:block;border-radius:9px}
.jtd-section-label{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:2px;color:var(--muted2);text-transform:uppercase;margin-bottom:10px}
.jtd-two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.jtd-kv-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.jtd-kv{display:flex;flex-direction:column;gap:3px}
.jtd-kv-lab{font-family:'Space Mono',monospace;font-size:8px;color:var(--muted2);letter-spacing:1px;text-transform:uppercase}
.jtd-kv-val{font-size:13px;font-weight:600;color:var(--text)}
.jtd-gate{display:flex;align-items:center;gap:6px;padding:5px 0;border-bottom:1px solid var(--line2)}
.jtd-gate:last-child{border-bottom:none}
.jtd-gate-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.jtd-gate-name{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted);text-transform:uppercase;flex:1}
.jtd-gate-val{font-family:'Space Mono',monospace;font-size:9px;font-weight:700}
/* reasoning timeline */
.jtd-timeline{display:flex;flex-direction:column;gap:0}
.jtd-tl-item{display:flex;gap:12px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--line2)}
.jtd-tl-item:last-child{border-bottom:none}
.jtd-tl-dot-col{display:flex;flex-direction:column;align-items:center;padding-top:3px;flex-shrink:0}
.jtd-tl-dot{width:9px;height:9px;border-radius:50%;border:2px solid var(--line);background:var(--panel2);flex-shrink:0}
.jtd-tl-dot.active{background:var(--gold);border-color:var(--gold)}
.jtd-tl-line{width:1px;flex:1;background:var(--line2);min-height:12px;margin-top:3px}
.jtd-tl-content{flex:1;min-width:0}
.jtd-tl-time{font-family:'Space Mono',monospace;font-size:8px;color:var(--muted2);margin-bottom:3px}
.jtd-tl-cmd{font-family:'Space Mono',monospace;font-size:9px;font-weight:700;color:var(--text)}
.jtd-tl-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:3px}
.jtd-tl-chip{font-family:'Space Mono',monospace;font-size:8px;color:var(--muted2)}
.jtd-tl-chip strong{color:var(--text)}
.jtd-tl-note{font-size:10px;color:var(--muted);font-style:italic;margin-top:3px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.jtd-review{background:rgba(184,134,11,.04);border:1px solid rgba(184,134,11,.12);border-radius:10px;padding:14px 16px;font-size:12px;color:var(--muted);white-space:pre-wrap;line-height:1.65}
@media(max-width:640px){.jtd-two-col{grid-template-columns:1fr}.jtd-kv-grid{grid-template-columns:1fr}}

/* ── JOURNAL DATE GROUPS ── */
.j-date-group{margin-bottom:20px}
.j-date-label{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--gold);text-transform:uppercase;font-weight:700;padding:6px 0;border-bottom:1px solid rgba(240,180,41,.15);margin-bottom:10px}
/* ── TOGGLE BUTTONS ── */
.toggle-group{display:flex;gap:6px}
.toggle-btn{flex:1;padding:10px 6px;border-radius:10px;border:1px solid var(--line);background:var(--panel2);color:var(--muted2);font-family:'Space Mono',monospace;font-size:10px;font-weight:700;letter-spacing:.8px;cursor:pointer;transition:all .15s;text-transform:uppercase}
.toggle-btn:hover{border-color:var(--muted2);color:var(--text)}
.toggle-btn.active-long{background:rgba(30,110,65,.1);border-color:var(--green);color:var(--green)}
.toggle-btn.active-short{background:rgba(192,57,43,.08);border-color:var(--red);color:var(--red)}
.toggle-btn.active-win{background:rgba(30,110,65,.1);border-color:var(--green);color:var(--green)}
.toggle-btn.active-loss{background:rgba(192,57,43,.08);border-color:var(--red);color:var(--red)}
.toggle-btn.active-be{background:rgba(184,134,11,.08);border-color:var(--gold);color:var(--gold)}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(0,0,0,.12);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:rgba(0,0,0,.2)}

/* ── RESPONSIVE SHELL ── */
@media(max-width:1023px){
  .app-shell{flex-direction:column}
  .sidebar{
    position:sticky;top:0;left:0;right:0;height:auto;width:100%;
    flex-direction:row;align-items:center;gap:8px;
    padding:8px 12px;overflow-x:auto;overflow-y:visible;
    z-index:500;
  }
  .sidebar-brand{display:none}
  .nav{flex-direction:row;flex:1;gap:6px}
  .tab-btn{
    flex-direction:column;gap:4px;padding:8px 6px;font-size:11px;
    white-space:normal;text-align:center;flex:1;justify-content:center;
  }
  .main-grid,.stat-grid{grid-template-columns:1fr 1fr}
  .stat-grid{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:767px){
  .wrap{padding:14px 14px 88px}
  .sidebar{
    position:fixed;top:auto;bottom:0;left:0;right:0;
    height:var(--mobile-nav-h);
    border-right:none;border-top:1px solid var(--line);
    box-shadow:0 -2px 10px rgba(0,0,0,.3);
  }
  /* 11px is the meaningful-label typography floor. Navigation labels are
     meaningful labels, not optional kickers, so they may not sit at 9px.
     Letter-spacing is tightened so "NOVA Intelligence" still fits. */
  .tab-btn{font-size:11px;padding:6px 3px;letter-spacing:0;line-height:1.15}
  .tab-btn::before{width:17px;height:17px}
  /* The sidebar's connection chip is a SIDEBAR footer element. Once the
     sidebar becomes the fixed 5-item bottom bar there is no room left for a
     sixth item, and the chip was rendering 21px past the right edge of a
     390px viewport -- its label visibly cut ("Connecte"). The approved
     mobile composition shows five nav items in that bar and nothing else.
     Hidden, not removed: _ovSetConnection() still writes this element's
     class and text every cycle, and the same genuine connection state stays
     visible on Overview itself (#ovIdentityStatus) and, on every other
     page, in the shared .content-header. No state is lost, only the
     duplicate that had nowhere to fit. */
  .sidebar-status{display:none}
  .main-grid,.stat-grid,.live-strip-row{grid-template-columns:1fr}
  /* Minimum compatibility fix: Overview's Account Summary (4 equal
     columns) and Markets' index-tiles row (5 equal columns) are fixed via
     inline style/CSS and fit their former fixed-width desktop shell, but
     overflow a 390px viewport -- collapse them to 2 columns here without
     touching any page's markup, ids, or labels.

     #dbMarketBoard is deliberately NOT in this list. It is the Overview
     Market Board, whose approved mobile treatment is one full-width quote
     row per instrument (symbol / value / signed change), set further down
     with `.ov-quotes`. Forcing two columns here beat that rule on ID +
     !important and crowded each pair, so a tile's symbol collided with the
     preceding tile's percentage (`+0.95%DXY`). */
  #ovAcctSummary>div,#indexTiles{grid-template-columns:1fr 1fr!important}
  /* .donna-logo's fixed 52px size + 12px letter-spacing (NOVA Intelligence
     page heading) overflows a 390px viewport regardless of live data,
     since the heading text itself is static -- shrink it here only. */
  .donna-logo{font-size:23px;letter-spacing:2px}
}

/* ── RISK BAR PULSE ── */
@keyframes strip-pulse-red {
  0%,100% { border-color:rgba(192,57,43,.2) }
  50%      { border-color:rgba(192,57,43,.55) }
}
@keyframes strip-pulse-yellow {
  0%,100% { border-color:rgba(184,134,11,.15) }
  50%      { border-color:rgba(184,134,11,.45) }
}
.ticker-wrap.risk-high   { animation:strip-pulse-red    2s ease-in-out infinite }
.ticker-wrap.risk-medium { animation:strip-pulse-yellow 2.5s ease-in-out infinite }

@keyframes donnaFadeIn { from { opacity: 0 } to { opacity: 1 } }
body.donna-first-load { animation: donnaFadeIn .3s ease-out both; }

/* ═══════════════════════ OVERVIEW (approved composition) ═══════════════════════
   Command-center hierarchy: page identity -> flat status rail -> hero (Morning
   Brief + session structure) -> secondary band (Performance / Market Driver /
   Primary Catalyst) -> quote board. New rules only -- .panel/.card/.kicker
   above are untouched shared primitives still used by other pages. */

/* ── DESKTOP FIT (1440x1000, DPR 1) ────────────────────────────────────────
   Overview must fit the viewport without vertical scrolling. The dominant
   waste was double spacing: `.vstack` already applies `gap:16px` between its
   children, yet every Overview band ALSO carried its own margin-bottom, so
   each seam was spaced twice (~72px of pure duplication). Collapsing the
   redundant margins and letting the grid gap own the rhythm removes that
   without shrinking a single component or losing any content.
   Scoped to Overview so no other page's spacing changes. */
#page-dashboard .vstack{gap:14px}
#page-dashboard .ov-page-id,
#page-dashboard .ov-rail,
#page-dashboard .ov-hero,
#page-dashboard .ov-second,
#page-dashboard .ov-board{margin-bottom:0}
/* The shared shell reserves 40px below the footer and 24px above it, which
   is generous scroll padding -- unnecessary on a page designed to fit.
   Desktop only: below 768px the nav is FIXED to the bottom edge, and the
   mobile `.wrap` rule's 88px of bottom padding is what keeps the last row
   (Market Board's final tile) from sitting underneath it. This override is
   declared after that media block, so leaving it unscoped would win the
   cascade on mobile and re-occlude the tile by ~14px. */
@media(min-width:768px){
  .wrap:has(> #page-dashboard.active){padding-bottom:18px}
}
.wrap:has(> #page-dashboard.active) > .footer{margin-top:12px}

/* Region titles are now semantic h2/h3 rather than styled divs. Reset the
   UA's default margin/size so promoting the tag changed no visual. */
.ov-sl .name,.ov-region .rl,.ov-board .bl h2{margin:0;font-size:inherit;font-weight:inherit}
.ov-board .bl h2{font:inherit;letter-spacing:inherit;text-transform:inherit;color:inherit}

.ov-page-id{
  display:flex;align-items:flex-end;justify-content:space-between;
  gap:16px;flex-wrap:wrap;margin-bottom:12px;
}
.ov-id-right{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding-bottom:3px}
/* Genuine backend connection state, mirrored from the sidebar. */
.ov-conn{
  display:inline-flex;align-items:center;gap:7px;
  font-family:'Space Mono',monospace;font-size:11px;font-weight:700;
  letter-spacing:1px;text-transform:uppercase;color:var(--muted2);
}
.ov-conn .d{width:7px;height:7px;border-radius:50%;background:var(--muted2);flex-shrink:0}
.ov-conn.online{color:var(--green)}.ov-conn.online .d{background:var(--green)}
.ov-conn.offline{color:var(--red)}.ov-conn.offline .d{background:var(--red)}
/* Application version -- optional uppercase kicker, so 10px is permitted. */
/* Version/build identity is meaningful metadata, not an optional kicker, so it
   sits on the 11px floor. Letter-spacing eased 1px -> .8px so the longer glyph
   run still fits beside the connection badge without wrapping the identity row. */
.ov-ver{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.8px;
  color:var(--muted2);text-transform:uppercase;
}
.ov-page-id .ov-kicker{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:2px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:7px;
}
.ov-page-id h1{
  font-size:30px;font-weight:700;letter-spacing:.2px;margin:0;
  font-family:'Rajdhani',sans-serif;color:var(--text);
}

/* ── STATUS RAIL: flat terminal band, not KPI cards ── */
.ov-rail{
  display:grid;grid-template-columns:repeat(4,1fr);
  border-top:1px solid var(--line);border-bottom:1px solid var(--line2);
  margin-bottom:16px;
}
.ov-rail .ri{padding:12px 18px 13px}
.ov-rail .ri + .ri{border-left:1px solid var(--line2)}
.ov-rail .ri:first-child{padding-left:2px}
.ov-rail .ri .l{
  display:flex;align-items:center;gap:7px;font-size:11px;letter-spacing:1px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:5px;
}
.ov-rail .ri .l .d{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.ov-rail .ri .v{font-size:18px;font-weight:700;line-height:1.2;font-family:'Rajdhani',sans-serif}
/* The rail's supporting line is explanatory prose ("Trending higher --
   momentum environment, tech leading"), not a label or a kicker, so it takes
   the 13px reading floor rather than the 11px label floor. */
.ov-rail .ri .s{font-size:13px;color:var(--muted);margin-top:3px;line-height:1.4}

/* ── HERO: one surface, two panes -- Morning Brief (primary) + session structure ── */
.ov-hero{
  background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  box-shadow:0 12px 32px rgba(0,0,0,.35);
  display:grid;grid-template-columns:1.5fr 1fr;
  margin-bottom:16px;overflow:hidden;
}
.ov-brief{padding:20px 26px 16px;display:flex;flex-direction:column;min-width:0}
.ov-brief .ov-sl{display:flex;align-items:baseline;gap:12px;margin-bottom:12px;flex-wrap:wrap}
.ov-brief .ov-sl .name{
  font-family:'Space Mono',monospace;font-size:11.5px;font-weight:700;letter-spacing:1.6px;
  color:var(--gold);text-transform:uppercase;
}
.ov-brief .ov-sl .meta{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2)}
/* Brief headline -- the engine's real `thesis`, given the approved
   editorial weight instead of being buried in a monospace block. */
.ov-mb-headline{
  font-family:'Rajdhani',sans-serif;font-size:19px;font-weight:700;
  line-height:1.26;color:var(--text);margin:0 0 8px;letter-spacing:.2px;
}
/* Proportional body (was a monospace <pre>): real paragraphs and lists. */
.ov-brief-body{font-size:13.5px;line-height:1.6;color:var(--muted);margin:0}
.ov-brief-body p{margin:0 0 8px}
.ov-brief-body p:last-child{margin-bottom:0}
.ov-brief-body .ov-mb-list{list-style:none;margin:0 0 8px;padding:0}
.ov-brief-body .ov-mb-list li{padding:3px 0 3px 14px;position:relative}
.ov-brief-body .ov-mb-list li::before{content:'';position:absolute;left:2px;top:11px;width:5px;height:1.5px;background:var(--blue)}
/* Structured engine sections (THESIS / PARTICIPATION / MACRO). The engine
   emits these as labelled lines; rendering them as a description list makes
   the label a real label -- semantically and visually -- and lets the value
   read as proportional prose instead of a machine-style run-on. Only the
   LABEL is transformed for display (title case); the value is rendered
   exactly as the engine emitted it. */
.ov-brief-body .ov-mb-sections{
  display:grid;grid-template-columns:auto 1fr;gap:3px 14px;margin:0 0 8px;
}
.ov-brief-body .ov-mb-sections dt{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.7px;
  color:var(--muted2);text-transform:uppercase;font-weight:700;
  white-space:nowrap;line-height:1.55;
}
.ov-brief-body .ov-mb-sections dd{margin:0;font-size:13.5px;line-height:1.55;color:var(--muted)}
/* Facts footer -- only fields the endpoint genuinely returned. */
/* The facts carry full sentences ("Contest resolves bullish if PDH holds and
   RVOL expands above 1.0"), so the VALUE side is reading content and takes the
   13px floor. Their `b` labels stay on the 11px label floor above. */
.ov-mb-footer{
  margin-top:9px;padding-top:8px;border-top:1px solid var(--line2);
  display:flex;flex-wrap:wrap;gap:4px 18px;font-size:13px;line-height:1.45;color:var(--muted);
}
/* Draw / Watch / Confidence each name the value beside them, so they are
   meaningful labels and take the 11px floor -- not the 10.5px they carried,
   which an element-only audit had missed because the text sits in a bare <b>. */
.ov-mb-fact b{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.7px;
  color:var(--muted2);text-transform:uppercase;font-weight:700;margin-right:5px;
}
/* The provenance disclosure previously lived here as its own content line.
   It now rides the section kicker's meta span (approved treatment), so this
   rule has no element left to style and is removed rather than left dead. */
.ov-structure{
  border-left:1px solid var(--line);
  background:linear-gradient(180deg,rgba(79,141,255,.04),transparent 40%);
  padding:20px 24px 16px;display:flex;flex-direction:column;min-width:0;
}
/* Approved treatment: a mono uppercase blue kicker, matching MORNING BRIEF's
   gold one on the other side of the same surface. The Morning Brief rule is
   scoped to `.ov-brief`, so `.ov-structure`'s heading was inheriting nothing
   but the size reset and rendering as proportional sentence case. */
.ov-structure .ov-sl .name{
  font-family:'Space Mono',monospace;font-size:11.5px;font-weight:700;letter-spacing:1.6px;
  color:var(--blue-text);text-transform:uppercase;
}
.ov-px-now{display:flex;align-items:baseline;gap:12px;margin:2px 0 4px;flex-wrap:wrap}
/* Freshness chip flush right on the price row. `margin-left:auto` only
   applies once it shares that row; if the row wraps on a narrow viewport the
   chip simply drops beneath the price rather than overlapping it. */
.ov-px-now .ov-fresh{margin-left:auto;align-self:center}
.ov-px-now .sym{font-size:12px;letter-spacing:1.5px;color:var(--muted2);font-family:'Space Mono',monospace}
.ov-px-now .px{font-family:'Space Mono',monospace;font-size:28px;font-weight:700;letter-spacing:-.5px}
.ov-px-now .chg{font-family:'Space Mono',monospace;font-size:13px;font-weight:700}
.ov-ladder{position:relative;flex:1;min-height:190px;margin:12px 0 4px}
.ov-ladder::before{content:'';position:absolute;left:7px;top:6px;bottom:6px;width:1px;background:var(--line2)}
.ov-lvl{position:absolute;left:0;right:0;display:flex;align-items:center;gap:10px;transform:translateY(-50%)}
.ov-lvl .tick{width:15px;height:1px;background:var(--line2);flex-shrink:0}
.ov-lvl .nm{font-family:'Space Mono',monospace;font-size:11.5px;letter-spacing:.7px;color:var(--muted);width:96px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0}
.ov-lvl .pr{font-family:'Space Mono',monospace;font-size:12.5px;color:var(--muted);flex:1}
.ov-lvl .st{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.7px;text-transform:uppercase}
.ov-lvl.draw .nm,.ov-lvl.draw .pr{color:var(--gold);font-weight:700}
.ov-lvl.draw .st{color:var(--gold)}
.ov-lvl.swept .st{color:var(--muted2)}
.ov-lvl.untapped .st{color:var(--green)}
.ov-lvl.now .tick{width:15px;height:3px;background:var(--blue);box-shadow:0 0 8px rgba(79,141,255,.8)}
.ov-lvl.now .nm{color:var(--blue-text);font-weight:700}
.ov-lvl.now .pr{color:var(--text);font-weight:700}

/* ── SECONDARY BAND: Performance | Market Driver | Primary Catalyst ── */
.ov-second{
  background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  display:grid;grid-template-columns:1.15fr 1fr 1fr;margin-bottom:16px;
}
.ov-region{padding:16px 22px 14px;min-width:0}
.ov-region + .ov-region{border-left:1px solid var(--line)}
.ov-region .rl{
  font-family:'Space Mono',monospace;font-size:11px;font-weight:700;letter-spacing:1.4px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:12px;
}
.ov-pnl-line{display:flex;align-items:baseline;gap:12px;margin-bottom:4px;flex-wrap:wrap}
.ov-pnl-line .big{font-family:'Space Mono',monospace;font-size:24px;font-weight:700}
.ov-pnl-line .lab{font-size:11px;letter-spacing:.7px;color:var(--muted2);text-transform:uppercase}
.ov-perf-sub{font-size:12.5px;color:var(--muted);margin-bottom:11px}
.ov-perf-sub b{color:var(--text);font-family:'Space Mono',monospace;font-weight:700}
.ov-act-list{border-top:1px solid var(--line2);padding-top:4px}
.ov-act-row{
  display:flex;align-items:center;gap:10px;padding:7px 0;
  border-bottom:1px solid var(--line2);font-size:13px;
}
.ov-act-row:last-child{border-bottom:none;padding-bottom:0}
.ov-act-row .sym{font-weight:700;width:30px}
.ov-act-row .dir{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.6px;width:50px}
.ov-act-row .amt{margin-left:auto;font-family:'Space Mono',monospace;font-size:13px;font-weight:700}
.ov-regime-line{font-size:15.5px;font-weight:700;color:var(--blue-text);margin-bottom:10px}
/* Restored approved hierarchy: driver headline above its bullets. */
.ov-drv-head{
  font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;
  color:var(--blue-text);line-height:1.3;margin-bottom:8px;
}
.ov-drv{list-style:none;margin:0;padding:0}
.ov-drv li{font-size:13px;color:var(--muted);line-height:1.5;padding:4px 0 4px 15px;position:relative}
.ov-drv li::before{content:'';position:absolute;left:2px;top:11px;width:5px;height:1.5px;background:var(--blue)}
/* Empty / unavailable / loading copy. 13px = the explanatory-content floor. */
.ov-drv li.ov-none::before{display:none}
.ov-none{font-size:13px;color:var(--muted2);line-height:1.5}
.ov-err{font-size:13px;color:var(--red);line-height:1.5}
.ov-cat-h{font-size:14px;font-weight:700;color:var(--text);line-height:1.38;margin-bottom:6px}
.ov-cat-p{font-size:13px;color:var(--muted);line-height:1.5;margin-bottom:10px}
.ov-senti{height:5px;border-radius:3px;background:var(--panel2);overflow:hidden;margin-bottom:6px}
.ov-senti .fill{height:100%;background:linear-gradient(90deg,var(--blue),var(--ai))}
.ov-senti-l{font-size:11px;color:var(--muted2);display:flex;justify-content:space-between}
.ov-senti-l .mid{color:var(--muted)}

/* ── QUOTE BOARD: flat rail, not cards-in-a-card ──
   Styles the EXISTING .db-market-tile/.db-tile-* hooks that renderDashboard()
   in ui/scripts.py already targets via querySelector -- no JS change needed,
   only the visual treatment of the tile the script already fills in. */
.ov-board{border-top:1px solid var(--line2);padding-top:12px;margin-bottom:12px}
.ov-board .bl{
  font-family:'Space Mono',monospace;font-size:11px;font-weight:700;letter-spacing:1.4px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:11px;
  display:flex;gap:12px;align-items:center;
}
.ov-quotes{display:grid;grid-template-columns:repeat(5,1fr)}
.ov-quotes .db-market-tile{padding:2px 22px 4px;position:relative;text-align:left}
.ov-quotes .db-market-tile + .db-market-tile{border-left:1px solid var(--line2)}
.ov-quotes .db-market-tile:first-child{padding-left:2px}
.ov-quotes .db-tile-sym{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.1px;color:var(--muted2);margin-bottom:6px}
.ov-quotes .db-tile-val{font-family:'Space Mono',monospace;font-size:21px;font-weight:700;letter-spacing:-.3px;line-height:1.1}
.ov-quotes .db-tile-pct{font-family:'Space Mono',monospace;font-size:12px;font-weight:700;margin-top:4px}

/* ── Catalyst sentiment badge: base look here, JS sets color/background per data ── */
.ov-sent-badge{
  display:inline-block;padding:3px 10px;border-radius:4px;
  font-family:'Space Mono',monospace;font-size:11px;font-weight:700;
  background:var(--panel2);color:var(--muted2);
}

/* ── DATA-FRESHNESS TAGS: shared vocabulary for current/delayed/stale/unavailable/prototype ── */
.ov-fresh{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.5px;padding:2px 8px;
  border-radius:5px;text-transform:uppercase;font-weight:700;
  display:inline-flex;align-items:center;gap:5px;
}
.ov-fresh .fd{width:5px;height:5px;border-radius:50%;flex-shrink:0}
/* Freshness states. The chip's TEXT always names the state; these colours
   are redundant reinforcement only, never the sole carrier of meaning.
   'cached', 'nofresh' and 'failure' are distinct from 'live' by design --
   cached/undetermined data must never be able to render as live. */
.ov-fresh.live{background:var(--green2);color:var(--green)}.ov-fresh.live .fd{background:var(--green)}
.ov-fresh.cached{background:rgba(79,141,255,.12);color:var(--blue)}.ov-fresh.cached .fd{background:var(--blue)}
.ov-fresh.stale{background:rgba(224,171,78,.12);color:var(--gold)}.ov-fresh.stale .fd{background:var(--gold)}
.ov-fresh.delayed{background:rgba(224,171,78,.12);color:var(--gold)}.ov-fresh.delayed .fd{background:var(--gold)}
.ov-fresh.nofresh{background:var(--panel2);color:var(--muted)}.ov-fresh.nofresh .fd{background:var(--muted)}
.ov-fresh.failure{background:var(--red2);color:var(--red)}.ov-fresh.failure .fd{background:var(--red)}
.ov-fresh.loading{background:var(--panel2);color:var(--muted2)}.ov-fresh.loading .fd{background:var(--muted2)}
.ov-fresh.unavailable{background:var(--panel2);color:var(--muted2)}.ov-fresh.unavailable .fd{background:var(--muted2)}
.ov-fresh.proto{background:var(--ai2);color:#c3b8ff}.ov-fresh.proto .fd{background:var(--ai)}

/* Status-rail dots have no colour of their own -- renderDashboard() paints
   each from the state it represents. Neutral is the honest resting value
   before any state has arrived, and the fixed value for Session (which is
   informational, not a good/bad grade). */
.ov-rail .ri .l .d{background:var(--muted2)}
.ov-rail .ri .l .d.neutral{background:var(--blue)}
/* "derived from Regime" states where Market Tone comes from, which makes it
   source/provenance information rather than an optional kicker -- so it takes
   the 11px floor. It stays visually subordinate to the cell's own label through
   colour and weight, not through undersized type. */
.ov-rail .ri .l .drv{
  font-size:11px;letter-spacing:.3px;color:var(--muted2);
  text-transform:uppercase;font-weight:600;margin-left:6px;
}

/* ── Overview-only suppression of the legacy shell chrome ──────────────────
   `.content-header` (v5.0 // LIVE MARKET CORE + ONLINE badge) and
   `.live-strip-row` (ticker + session chip) are rendered by the shared shell
   above EVERY page, but neither appears in Overview's approved composition --
   Overview opens on its own page-identity block. They are hidden here for
   Overview only, via :has() on the active page, so they remain present and
   fully functional on Journal / Markets / NOVA Intelligence / Settings.
   Hidden rather than removed: renderDashboard() still writes to #liveStrip
   and #sessionVal, and those writes must keep succeeding. */
.wrap:has(> #page-dashboard.active) > .content-header,
.wrap:has(> #page-dashboard.active) > .live-strip-row,
.wrap:has(> #page-journal.active) > .content-header,
.wrap:has(> #page-journal.active) > .live-strip-row,
.wrap:has(> #page-news.active) > .content-header,
.wrap:has(> #page-news.active) > .live-strip-row,
.wrap:has(> #page-assistant.active) > .content-header,
.wrap:has(> #page-assistant.active) > .live-strip-row,
.wrap:has(> #page-assistant.active) > .footer{display:none}

@media(max-width:1023px){
  .ov-rail{grid-template-columns:1fr 1fr}
  .ov-rail .ri:nth-child(2n+1){padding-left:2px}
  .ov-rail .ri:nth-child(2n){border-left:1px solid var(--line2)}
  .ov-rail .ri:nth-child(1),.ov-rail .ri:nth-child(2){border-bottom:1px solid var(--line2)}
  .ov-hero{grid-template-columns:1fr}
  .ov-structure{border-left:none;border-top:1px solid var(--line)}
  .ov-second{grid-template-columns:1fr}
  .ov-region + .ov-region{border-left:none;border-top:1px solid var(--line)}
}
@media(max-width:767px){
  .ov-brief{padding:16px 18px 14px}
  .ov-structure{padding:16px 18px 14px}
  .ov-px-now .px{font-size:24px}
  /* A 390px column is too narrow for a label/value pair side by side once
     the label is "PARTICIPATION", so the sections stack: label above value.
     Neither is shrunk -- the label stays on the 11px floor and the value on
     the 13.5px reading size. */
  .ov-brief-body .ov-mb-sections{grid-template-columns:1fr;gap:0}
  .ov-brief-body .ov-mb-sections dd{margin-bottom:8px}
  .ov-brief-body .ov-mb-sections dd:last-child{margin-bottom:0}
  /* In the 2-up rail the cell is too narrow to hold "MARKET TONE" and its
     provenance on one line, so the two interleaved mid-phrase. Giving the
     provenance its own line keeps both readable without dropping the
     disclosure or shrinking it below the 11px floor.
     `.l` is a flex row, so `display:block` alone still left the provenance
     as a flex sibling that wrapped mid-phrase beside the label
     ("MARKET | DERIVED / TONE | FROM / | REGIME"). `flex:0 0 100%` on a
     wrapping row is what actually breaks it onto its own line. */
  .ov-rail .ri .l{flex-wrap:wrap}
  .ov-rail .ri .l .drv{display:block;flex:0 0 100%;margin-left:0;margin-top:2px}
  /* Approved mobile quote board: one full-width row per instrument --
     symbol rail left, value carrying the row, signed change flush right.
     Every part is nowrap and the value column is the only flexible one, so
     a long value pushes the row's own spacing rather than overrunning the
     change beside it. Touch-safe row height comes from the 10px padding. */
  .ov-quotes{grid-template-columns:1fr}
  .ov-quotes .db-market-tile{
    display:flex;align-items:baseline;gap:12px;padding:10px 2px;
    border-left:none !important;border-bottom:1px solid var(--line2);
  }
  .ov-quotes .db-market-tile:last-child{border-bottom:none}
  .ov-quotes .db-tile-sym{margin-bottom:0;width:46px;flex:none;white-space:nowrap}
  .ov-quotes .db-tile-val{font-size:19px;flex:1;min-width:0;white-space:nowrap}
  .ov-quotes .db-tile-pct{margin-top:0;flex:none;text-align:right;white-space:nowrap}
}

/* ═══════════════════════ JOURNAL (approved composition) ═══════════════════
   Mirrors artifact b22fcc6b frame 2 (desktop) and f1b6ec63 frames 4-6
   (mobile): identity row -> flat performance rail -> filter chips -> two
   balanced columns (ledger + breakdown + daily P&L on the left, sticky trade
   review on the right). New `.jn-*` rules only; the legacy `.j-*`/`.jtd-*`
   primitives are untouched because the Log Trade and Trade Detail modals
   still use them. */

.jn-sr-only{
  position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip:rect(0 0 0 0);white-space:nowrap;border:0;
}

/* ── DESKTOP FIT (1440x1000, DPR 1) ───────────────────────────────────────
   `.vstack` already applies gap:16px between its children, so a band that
   ALSO carries its own margin-bottom is spaced twice -- the same duplication
   Overview had. Four seams were costing ~110px instead of ~56px. Collapsing
   the redundant margins and letting the grid gap own the rhythm recovers the
   difference without shrinking a single component or dropping any content.
   Scoped to Journal so no other page's spacing changes. */
#page-journal .vstack{gap:14px}
#page-journal > .vstack > .jn-page-id,
#page-journal > .vstack > .jn-rail,
#page-journal > .vstack > .jn-rail-note,
#page-journal > .vstack > .jn-filters{margin-bottom:0}
#page-journal > .vstack > .jn-rail-note{margin-top:0}
/* Journal is a scrolling page, not a fits-in-one-screen page, so it keeps the
   shared shell's scroll padding rather than Overview's tightened value. */

/* ── Identity row ── */
.jn-page-id{
  display:flex;align-items:flex-end;justify-content:space-between;
  gap:16px;flex-wrap:wrap;margin-bottom:12px;
}
.jn-page-id .jn-id-left{margin-right:auto}
.jn-kicker{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:2px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:5px;
}
.jn-page-id h1{
  font-family:'Rajdhani',sans-serif;font-size:34px;font-weight:700;
  letter-spacing:.5px;margin:0;line-height:1.05;color:var(--text);
}
.jn-id-meta{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding-bottom:3px}
.jn-conn{
  display:inline-flex;align-items:center;gap:7px;
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;
  text-transform:uppercase;color:var(--muted2);
}
.jn-conn .d{width:7px;height:7px;border-radius:50%;background:var(--muted2);flex-shrink:0}
.jn-conn.online{color:var(--green)}.jn-conn.online .d{background:var(--green)}
.jn-conn.offline{color:var(--red)}.jn-conn.offline .d{background:var(--red)}
.jn-ver{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;
  color:var(--muted2);text-transform:uppercase;
}
.jn-action{
  font-family:'Space Mono',monospace;font-size:11.5px;font-weight:700;letter-spacing:1.2px;
  text-transform:uppercase;padding:11px 20px;min-height:44px;
  border-radius:9px;border:1px solid var(--blue);background:rgba(79,141,255,.1);
  color:var(--blue-text);cursor:pointer;transition:background .15s;
}
.jn-action:hover{background:rgba(79,141,255,.18)}

/* ── Performance rail ── */
.jn-rail{
  display:grid;grid-template-columns:repeat(5,1fr);
  border-top:1px solid var(--line2);border-bottom:1px solid var(--line2);
  margin-bottom:12px;
}
.jn-rail .ri{padding:12px 18px 13px}
.jn-rail .ri + .ri{border-left:1px solid var(--line2)}
.jn-rail .ri:first-child{padding-left:2px}
.jn-rail .ri .l{
  font-size:11px;letter-spacing:1px;color:var(--muted2);
  text-transform:uppercase;margin-bottom:5px;
}
.jn-rail .ri .v{
  font-family:'Space Mono',monospace;font-size:21px;font-weight:700;
  line-height:1.2;letter-spacing:-.3px;color:var(--text);
}
.jn-rail .ri .v.up{color:var(--green)}
.jn-rail .ri .v.down{color:var(--red)}
.jn-rail .ri .v.flat{color:var(--muted)}
/* A small-sample reading is never given the confident treatment. */
.jn-rail .ri .v.lowsample{color:var(--muted)}
.jn-rail .ri .s{font-size:13px;color:var(--muted);margin-top:3px;line-height:1.4}
/* The caveat repeats what the rail already says, so it is a footnote hanging
   off the rail -- one line, no fill, no card. The leading marker carries the
   warning without relying on colour. */
.jn-rail-note{
  font-size:13px;color:var(--muted);line-height:1.45;margin:-6px 0 10px;
  padding:0 2px;display:flex;align-items:baseline;gap:7px;
}
.jn-rail-note::before{
  /* Literal glyph rather than a CSS hex escape: this stylesheet lives
     inside a Python string, where a backslash followed by digits is read
     as an octal escape and the marker arrives mangled. */
  content:'⚠';font-size:12px;color:var(--gold);flex-shrink:0;line-height:1;
}

/* ── Filter chips ── */
.jn-filters{display:flex;flex-wrap:wrap;gap:8px 18px;margin-bottom:14px;align-items:center}
.jn-fgroup{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.jn-fglabel{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;
  text-transform:uppercase;color:var(--muted2);margin-right:3px;
}
/* A dimension the records cannot support is shown, disabled, with the reason
   stated -- never hidden silently and never filled with invented options. */
.jn-fgroup.is-disabled{opacity:.75}
.jn-fnone{font-size:12.5px;color:var(--muted2);font-style:italic}
.jn-chip{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.8px;
  padding:8px 14px;min-height:36px;border-radius:8px;
  border:1px solid var(--line);background:var(--panel2);color:var(--muted);
  cursor:pointer;transition:all .15s;
}
.jn-chip:hover{border-color:var(--muted2);color:var(--text)}
.jn-chip.active{background:rgba(79,141,255,.14);border-color:var(--blue);color:var(--blue-text);font-weight:700}

/* ── Two-column body ── */
.jn-main{display:grid;grid-template-columns:1.55fr 1fr;gap:16px;align-items:start}
.jn-left{display:flex;flex-direction:column;gap:16px;min-width:0}

/* ── Ledger ── */
.jn-ledger-wrap{
  background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:6px 0 0;overflow:hidden;
}
.jn-ledger-scroll{overflow-x:auto}
.jn-ledger{width:100%;border-collapse:collapse;font-size:13px;min-width:0}
.jn-ledger thead th{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;
  text-transform:uppercase;color:var(--muted2);font-weight:700;text-align:left;
  padding:9px 12px;border-bottom:1px solid var(--line2);white-space:nowrap;
}
.jn-ledger th.num,.jn-ledger td.num{text-align:right}
.jn-ledger td{padding:10px 12px;border-bottom:1px solid var(--line2);vertical-align:middle}
.jn-ledger tbody tr:last-child td{border-bottom:none}
.jn-row{cursor:pointer;transition:background .12s;position:relative}
.jn-row:hover{background:var(--panel2)}
.jn-row.selected{background:rgba(79,141,255,.09)}
/* Selection is carried by a left rail AND a background, so it never depends
   on colour perception alone. */
.jn-row.selected td:first-child{box-shadow:inset 3px 0 0 var(--blue)}
.jn-row .jn-d{font-family:'Space Mono',monospace;font-size:12.5px;color:var(--text);display:block}
.jn-row .jn-t{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);display:block;margin-top:2px}
.jn-instr{font-weight:700;font-size:13.5px}
.jn-dir{
  font-family:'Space Mono',monospace;font-size:11px;font-weight:700;letter-spacing:.8px;
  padding:2px 7px;border-radius:4px;
}
.jn-dir.long{background:var(--green2);color:var(--green)}
.jn-dir.short{background:var(--red2);color:var(--red)}
.jn-res{font-family:'Space Mono',monospace;font-size:13px;font-weight:700;white-space:nowrap}
.jn-res.up,.up{color:var(--green)}
.jn-res.down,.down{color:var(--red)}
.jn-res.flat,.flat{color:var(--muted)}
.jn-mark{margin-right:4px;font-size:11px}
.jn-ledger td.ses{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);text-align:right;white-space:nowrap}
.jn-th-abbr{display:none}
.jn-dim{color:var(--muted2)}
.jn-none{font-size:13px;color:var(--muted2);line-height:1.5;padding:18px 12px;text-align:center}
.jn-err{font-size:13px;color:var(--red);line-height:1.5;padding:18px 12px;text-align:center}
.jn-ledger-foot{
  font-size:12.5px;color:var(--muted);padding:10px 12px;
  border-top:1px solid var(--line2);
}
.jn-ledger-foot b{font-family:'Space Mono',monospace}

/* ── Breakdown ── */
.jn-breakdown,.jn-daily{
  background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:14px 18px 16px;
}
.jn-sec-head{
  display:flex;align-items:baseline;justify-content:space-between;gap:12px;
  flex-wrap:wrap;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--line2);
}
.jn-sec-head h2{
  font-family:'Space Mono',monospace;font-size:11.5px;font-weight:700;letter-spacing:1.6px;
  color:var(--gold);text-transform:uppercase;margin:0;
}
.jn-sec-head .meta{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2)}
.jn-bd-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px 22px}
.jn-bd-block h3{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;
  text-transform:uppercase;color:var(--muted2);margin:0 0 8px;font-weight:700;
}
.jn-bars{display:flex;flex-direction:column;gap:6px}
.jn-bar-row{display:grid;grid-template-columns:minmax(60px,auto) 1fr auto;gap:10px;align-items:center}
.jn-bar-lab{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.jn-bar-lab.jn-absent{font-style:italic;color:var(--muted2)}
.jn-bar-track{height:6px;border-radius:3px;background:var(--panel2);overflow:hidden}
.jn-bar-fill{height:100%;background:var(--blue);border-radius:3px}
.jn-bar-fill.up{background:var(--green)}
.jn-bar-fill.down{background:var(--red)}
.jn-bar-val{font-family:'Space Mono',monospace;font-size:12.5px;font-weight:700;white-space:nowrap;color:var(--text)}
.jn-n{font-size:11px;color:var(--muted2);font-weight:400;margin-left:3px}
.jn-bd-note{font-size:13px;color:var(--muted2);line-height:1.5;margin-top:8px}

/* ── Daily P&L ── */
/* ── Daily Net P&L ──────────────────────────────────────────────────────
   A plotting surface rather than a row of bars: gridlines on the quarters, a
   heavier zero line, axis values only where the scale actually reaches, and
   dates along the bottom. The aggregation behind it is unchanged -- the chart
   draws the sessions that exist and leaves the rest of the timeline alone. */
.jn-daily-chart{
  display:grid;grid-template-columns:minmax(0,1fr);
  grid-template-rows:auto auto;
}
.jn-daily-chart.is-empty{display:block}

/* Y axis */
.jn-dp-yax{grid-column:1;grid-row:1;padding:20px 0;display:flex;align-items:stretch;z-index:3;pointer-events:none}
.jn-dp-yin{position:relative;width:100%;height:var(--plot-h,168px)}
.jn-dp-yin span{
  position:absolute;left:10px;transform:translateY(-50%);
  font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);
  white-space:nowrap;letter-spacing:.2px;
}

/* The surface itself: seated slightly below the card, not floating on it. */
.jn-dp-surface{
  grid-column:1;grid-row:1;position:relative;padding:20px 12px 20px 58px;
  border:1px solid var(--line2);border-radius:10px;
  background:
    linear-gradient(180deg, rgba(255,255,255,.022), rgba(255,255,255,0) 42%),
    var(--panel2);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.035);
}
.jn-dp-inner{position:relative;height:var(--plot-h,168px)}
.jn-dp-gl{position:absolute;left:0;right:0;height:1px;background:var(--line2);opacity:.55}
/* The baseline is the one line that carries meaning, so it outweighs the grid. */
.jn-zero{position:absolute;left:0;right:0;top:var(--pos,100%);height:1px;background:var(--muted2);z-index:2}

/* Bars. One column per genuine session -- one session centres in the full
   width, ten spread across it -- with the width capped so a sparse chart
   still reads as deliberate. */
.jn-dp-bars{position:absolute;inset:0;display:grid;grid-template-columns:repeat(var(--n,1),minmax(0,1fr));z-index:1}
.jn-dp-bar{
  grid-column:var(--i);position:relative;display:block;
  background:none;border:0;padding:0;margin:0 auto;width:100%;max-width:78px;
  cursor:pointer;font:inherit;color:inherit;
}
.jn-dp-bar .jn-col-plot{
  display:grid;grid-template-rows:var(--pos,100%) var(--neg,0%);height:100%;
  padding:0 12px;
}
.jn-col-pos{position:relative;display:flex;align-items:flex-end;justify-content:center}
.jn-col-neg{position:relative;display:flex;align-items:flex-start;justify-content:center}
.jn-dbar{
  width:100%;display:block;
  transition:filter .15s, transform .15s;
}
.jn-dbar.up{
  height:var(--mag);min-height:3px;border-radius:4px 4px 0 0;
  background:linear-gradient(180deg, var(--green), color-mix(in srgb, var(--green) 68%, #0b111c));
}
.jn-dbar.down{
  height:var(--mag);min-height:3px;border-radius:0 0 4px 4px;
  background:linear-gradient(0deg, var(--red), color-mix(in srgb, var(--red) 68%, #0b111c));
}
/* Breakeven is a real session with no magnitude: a flat neutral tick, never a
   bar with invented height. */
.jn-dbar.flat{height:3px;background:var(--muted2);border-radius:2px;opacity:.9}

/* Per-bar value, parked just outside the plot in the surface padding so a
   full-height bar never collides with it. */
.jn-dp-v{
  position:absolute;left:-6px;right:-6px;bottom:100%;margin-bottom:5px;
  font-family:'Space Mono',monospace;font-size:11px;font-weight:700;
  text-align:center;white-space:nowrap;
}
.jn-col-neg .jn-dp-v{bottom:auto;top:100%;margin:5px 0 0}
.jn-dp-v.up{color:var(--green)}
.jn-dp-v.down{color:var(--red)}
.jn-dp-v.flat{color:var(--muted2)}
.jn-dp-vm,.jn-dp-d{display:none}

/* X axis */
.jn-dp-xax{
  grid-column:1;grid-row:2;display:grid;
  grid-template-columns:repeat(var(--n,1),minmax(0,1fr));padding:8px 12px 0 58px;
}
.jn-dp-xax span{
  grid-column:var(--i);text-align:center;
  font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);white-space:nowrap;
}

/* Hover / focus */
.jn-dp-bar:hover .jn-dbar{filter:brightness(1.14)}
.jn-dp-bar:focus-visible{outline:none}
.jn-dp-bar:focus-visible .jn-col-plot{
  outline:2px solid var(--blue);outline-offset:1px;border-radius:6px;
}
.jn-dp-tip{
  position:absolute;left:50%;bottom:calc(100% + 10px);transform:translateX(-50%);
  display:none;flex-direction:column;gap:2px;z-index:5;
  background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:8px 11px;box-shadow:0 8px 22px -10px rgba(0,0,0,.75);
  font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);
  white-space:nowrap;pointer-events:none;
}
.jn-dp-tip b{color:var(--text);font-size:11px}
.jn-dp-tip .up{color:var(--green)}
.jn-dp-tip .down{color:var(--red)}
.jn-dp-tip .flat{color:var(--muted2)}
.jn-dp-bar:hover .jn-dp-tip,.jn-dp-bar:focus-visible .jn-dp-tip{display:flex}

/* Compact computed context under the heading -- four figures, no second rail. */
.jn-dp-ctx{
  display:flex;flex-wrap:wrap;gap:6px 26px;margin:-2px 0 14px;
}
.jn-dp-ci{display:flex;align-items:baseline;gap:7px}
.jn-dp-ci .k{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.6px;
  text-transform:uppercase;color:var(--muted2);
}
.jn-dp-ci .v{
  font-family:'Space Mono',monospace;font-size:13px;font-weight:700;color:var(--text);
  display:flex;align-items:baseline;gap:5px;
}
.jn-dp-ci .v.up{color:var(--green)}
.jn-dp-ci .v.down{color:var(--red)}
.jn-dp-ci .v i{font-style:normal;font-size:11px;font-weight:400;color:var(--muted2)}

/* ── Review panel ── */
.jn-review{
  background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px 20px 18px;position:sticky;top:16px;min-width:0;
}
.jn-review-empty{padding:44px 12px}
.jn-rv-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap}
.jn-rv-title{font-family:'Rajdhani',sans-serif;font-size:23px;font-weight:700;letter-spacing:.5px;display:flex;align-items:center;gap:9px}
.jn-rv-pnl{font-family:'Space Mono',monospace;font-size:21px;font-weight:700;white-space:nowrap}
.jn-rv-sub{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);margin-top:3px}
.jn-kv-grid{
  display:grid;grid-template-columns:1fr 1fr;gap:11px 18px;
  margin:14px 0 4px;padding-top:13px;border-top:1px solid var(--line2);
}
.jn-kv .k{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.8px;
  text-transform:uppercase;color:var(--muted2);margin-bottom:2px;
}
.jn-kv .v{font-size:13.5px;color:var(--text);font-weight:600;word-break:break-word}
.jn-rv-block{margin-top:16px}
.jn-rv-block h3{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;
  text-transform:uppercase;color:var(--muted2);margin:0 0 8px;font-weight:700;
}
.jn-rv-block p{font-size:13px;color:var(--muted);line-height:1.55;margin:0}
.jn-tl{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:9px}
.jn-tl li{position:relative;padding-left:15px}
.jn-tl li::before{content:'';position:absolute;left:0;top:6px;width:6px;height:6px;border-radius:50%;background:var(--blue)}
.jn-tl-t{display:block;font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2)}
.jn-tl-c{display:block;font-size:13px;color:var(--muted);line-height:1.5;margin-top:2px}
.jn-quote{
  margin:0;padding:11px 14px;border-left:2px solid var(--blue);
  background:rgba(79,141,255,.06);border-radius:0 7px 7px 0;
  font-size:13px;color:var(--muted);line-height:1.55;
}
/* Approved explicit unavailable state -- a stated absence, not a blank. */
.jn-empty-box{
  border:1px dashed var(--line2);border-radius:9px;padding:16px 14px;text-align:center;
  font-size:13px;color:var(--muted);line-height:1.5;
}
.jn-empty-box span{display:block;font-size:11px;color:var(--muted2);margin-top:5px}
.jn-shot{width:100%;height:auto;border-radius:8px;border:1px solid var(--line2);display:block}

/* ── Tablet ── */
@media(max-width:1023px){
  .jn-main{grid-template-columns:1fr}
  .jn-review{position:static}
  .jn-rail{grid-template-columns:repeat(3,1fr)}
  .jn-rail .ri:nth-child(3n+1){padding-left:2px;border-left:none}
  .jn-rail .ri:nth-child(n+4){border-top:1px solid var(--line2)}
}

/* ── Mobile: the approved compact treatment (frames 4-6) ── */
@media(max-width:767px){
  /* The approved mobile reference has no full-width action band. Log Trade
     becomes a compact action beside the title; the connection/version meta
     drops to its own line beneath. Touch target stays at 44px. */
  .jn-page-id{
    display:grid;grid-template-columns:1fr auto;align-items:center;
    grid-template-areas:'title action' 'meta meta';gap:6px 12px;
  }
  .jn-page-id h1{font-size:27px}
  .jn-id-left{grid-area:title;margin-right:0}
  .jn-action{grid-area:action;width:auto;padding:11px 14px;min-height:44px;font-size:11px;letter-spacing:.8px}
  .jn-id-meta{grid-area:meta;padding-bottom:0;gap:9px}
  .jn-filters{gap:8px 12px}
  .jn-fglabel{font-size:11px}
  .jn-rail-note{font-size:13px;margin:-4px 0 8px}
  .jn-rail{grid-template-columns:1fr 1fr}
  .jn-rail .ri{padding:11px 14px}
  .jn-rail .ri:nth-child(2n+1){padding-left:2px;border-left:none}
  .jn-rail .ri:nth-child(n+3){border-top:1px solid var(--line2)}
  .jn-rail .ri .v{font-size:19px}
  /* Entry and Exit are dropped so the remaining columns stay legible at
     390px -- both values are still shown in full in the review panel. */
  .jn-ledger th:nth-child(4),.jn-ledger td:nth-child(4),
  .jn-ledger th:nth-child(5),.jn-ledger td:nth-child(5){display:none}
  /* Five columns need 368.8px of min-content in the 360px the card offers,
     so the table was spilling ~9px past its own card and relying on the
     scroll wrapper to hide it. Tighter gutters make it fit outright. */
  .jn-ledger td{padding:12px 7px}
  .jn-row{min-height:44px}
  /* Session/Regime is the widest column; letting it -- and its header --
     wrap is what keeps the whole ledger inside 390px instead of pushing
     the table into a horizontal scroll. */
  .jn-ledger th.ses,.jn-ledger td.ses{white-space:normal;text-align:right;font-size:11px}
  .jn-th-full{display:none}
  .jn-th-abbr{display:inline}
  .jn-ledger thead th{padding:9px 6px}
  .jn-chip{min-height:44px;padding:11px 16px}
  .jn-bd-grid{grid-template-columns:1fr;gap:16px}
  .jn-breakdown,.jn-daily,.jn-review{padding:14px 16px 16px}
  /* At 390px ten labelled columns cannot carry a signed dollar value at 11px,
     so the module turns on its side: date, structured track, value. Same
     surface, same semantics, same zero origin -- read left to right. */
  .jn-daily-chart{grid-template-columns:minmax(0,1fr);row-gap:0}
  .jn-dp-yax,.jn-dp-xax{display:none}
  .jn-dp-surface{grid-column:1;padding:12px 13px}
  .jn-dp-inner{height:auto}
  .jn-dp-gl{display:none}
  .jn-dp-bars{position:static;display:flex;flex-direction:column;gap:2px}
  .jn-dp-bar{
    display:grid;grid-template-columns:38px minmax(0,1fr) auto;
    align-items:center;gap:10px;max-width:none;
    /* Each row is a real button, so it carries a real touch target. The track
       stays 14px; the rest of the 44px is hit area around it. */
    min-height:44px;
  }
  .jn-dp-d{
    display:block;font-family:'Space Mono',monospace;font-size:11px;
    color:var(--muted2);text-align:left;
  }
  /* The track is drawn, not implied -- the bar extends inside a visible rail
     from a zero origin that stays put whatever the data does. */
  .jn-dp-bar .jn-col-plot{
    position:relative;padding:0;height:14px;
    grid-template-rows:none;grid-template-columns:var(--neg,0%) var(--pos,100%);
    background:var(--panel);border:1px solid var(--line2);border-radius:4px;
  }
  .jn-col-neg{grid-column:1;align-items:center;justify-content:flex-end}
  .jn-col-pos{grid-column:2;align-items:center;justify-content:flex-start}
  .jn-dbar{height:8px}
  .jn-dbar.up{width:var(--mag);height:8px;min-width:3px;border-radius:0 3px 3px 0;
    background:linear-gradient(90deg, color-mix(in srgb, var(--green) 74%, #0b111c), var(--green))}
  .jn-dbar.down{width:var(--mag);height:8px;min-width:3px;border-radius:3px 0 0 3px;
    background:linear-gradient(270deg, color-mix(in srgb, var(--red) 74%, #0b111c), var(--red))}
  .jn-dbar.flat{width:3px;height:8px}
  .jn-dp-v{display:none}
  .jn-dp-vm{
    display:block;font-family:'Space Mono',monospace;font-size:11px;font-weight:700;
    text-align:right;white-space:nowrap;min-width:62px;
  }
  .jn-dp-vm.up{color:var(--green)}
  .jn-dp-vm.down{color:var(--red)}
  .jn-dp-vm.flat{color:var(--muted2)}
  .jn-zero{left:var(--neg,0%);right:auto;top:0;bottom:0;width:1px;height:auto;z-index:2}
  .jn-dp-bar:focus-visible .jn-col-plot{outline:2px solid var(--blue);outline-offset:2px}
  .jn-dp-tip{display:none!important}
  .jn-dp-ctx{gap:5px 18px;margin-bottom:12px}
  .jn-dp-ci .v{font-size:12.5px}
  .jn-kv-grid{grid-template-columns:1fr 1fr;gap:10px 14px}
  /* Three stacked unavailable sections should not read as three empty cards.
     They stay explicit -- name, message and reason -- but compact. */
  .jn-rv-block{margin-top:13px}
  .jn-empty-box{
    padding:9px 11px;text-align:left;border-radius:7px;
    font-size:12.5px;line-height:1.45;
  }
  .jn-empty-box span{font-size:11px;margin-top:2px}
  .jn-rv-title{font-size:21px}
  .jn-rv-pnl{font-size:19px}
}

/* ── FOCUS STATE (kept last so it wins over any earlier outline:none) ── */
:focus-visible{outline:2px solid var(--blue);outline-offset:2px}

/* ── REDUCED MOTION ────────────────────────────────────────────────────────
   The interface runs several INFINITE animations (the status-dot `pulse`,
   the `tickerMove` marquees, `_mrePulse`, `blink`). Continuous motion that
   never stops is exactly what prefers-reduced-motion exists to suppress, and
   the stylesheet previously honoured that preference nowhere.

   This block has zero effect for anyone who has not asked their OS for
   reduced motion, so it changes no approved visual. Transitions are reduced
   to a near-zero duration rather than removed outright, so state changes
   still land instantly instead of appearing broken; infinite animations are
   stopped on their first frame. */
@media (prefers-reduced-motion: reduce){
  *,*::before,*::after{
    animation-duration:.001ms !important;
    animation-iteration-count:1 !important;
    transition-duration:.001ms !important;
    scroll-behavior:auto !important;
  }
  /* The marquees translate as their whole reason for existing -- pin them to
     their start position so the text stays readable and still. */
  .ticker-track,.news-ticker-track{animation:none !important;transform:none !important}
}

/* ═══════════════════════ MARKETS (approved composition) ═══════════════════
   Artifact 55c387a4 — screenshot #1 live, #3 cached. One analytical grid:
   Cross-Asset Pulse spans both right-hand rows, Market Structure spans the
   full width beneath, and whichever upper card is shorter stretches its
   surface so the two columns always terminate on the same line.

   Typography note: this page uses the same 'Space Mono' / 'Rajdhani'
   declarations the rest of the app already carries. NOVA ships no font link,
   so both fall back — deliberately not changed here, because adding a font
   CDN would alter Overview and Journal too. */

#page-news .mk-wrap{max-width:1400px}

/* ── identity ── */
.mk-id{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:12px}
.mk-kicker{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:2px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:5px;
}
.mk-title{
  font-family:'Rajdhani',sans-serif;font-size:31px;font-weight:700;
  letter-spacing:1.5px;margin:0;line-height:1;color:var(--text);
}
.mk-id-meta{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding-bottom:3px}
.mk-clock{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2)}
/* One freshness vocabulary for the whole page. */
.mk-fresh{
  display:inline-flex;align-items:center;gap:6px;font-family:'Space Mono',monospace;
  font-size:11px;padding:4px 9px;border-radius:999px;
  border:1px solid var(--line);background:var(--panel2);color:var(--muted);
}
.mk-fresh::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--muted2)}
.mk-fresh.live{color:#7ee3b4;border-color:rgba(61,220,151,.32);background:rgba(61,220,151,.10)}
.mk-fresh.live::before{background:var(--green)}
.mk-fresh.stale{color:#f3cd7a;border-color:rgba(251,191,36,.32);background:rgba(251,191,36,.10)}
.mk-fresh.stale::before{background:var(--yellow)}
.mk-fresh.down{color:#ff9d9d;border-color:rgba(255,107,107,.34);background:rgba(255,107,107,.10)}
.mk-fresh.down::before{background:var(--red)}
.mk-fresh.loading::before,.mk-fresh.connecting::before{animation:mkPulse 1.4s ease-in-out infinite}
@keyframes mkPulse{0%,100%{opacity:.35}50%{opacity:1}}
.mk-action{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.8px;
  padding:9px 14px;min-height:36px;border-radius:8px;cursor:pointer;
  border:1px solid rgba(155,140,255,.36);background:var(--ai2);color:#c3b9ff;
}
.mk-action:hover{border-color:var(--ai);color:#d6cfff}
.mk-action:focus-visible{outline:2px solid var(--blue);outline-offset:1px}

/* on-demand summary — hidden until asked for, so it never disturbs the grid */
.mk-summary{
  background:var(--panel);border:1px solid rgba(155,140,255,.28);
  border-radius:var(--radius2);padding:14px 16px;margin-bottom:12px;
}
.mk-sum-head{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.8px;
  text-transform:uppercase;color:#c3b9ff;margin-bottom:9px;
}
#novaMarketSummaryLoading{font-size:13px;color:var(--muted)}
#novaMarketSummaryText{font-size:13px;color:var(--text);line-height:1.6}
/* Empty and error are different outcomes and must not share a treatment: a
   summary the model declined to produce is not a failed request. */
/* var(--red), not a hard-coded hex: this carries forward the intent of the
   uncommitted working-tree edit, whose literal line no longer exists because
   the summary markup was rewritten. 6.54:1 on --panel. */
#novaMarketSummaryError.mk-sum-err{font-size:13px;color:var(--red)}
#novaMarketSummaryError.mk-sum-empty{font-size:13px;color:var(--muted)}
.mk-action[aria-expanded="true"]{background:rgba(155,140,255,.22);color:#d6cfff}

/* ── the grid ── */
.mk-grid{
  display:grid;
  grid-template-columns:minmax(0,2fr) minmax(300px,1fr);
  grid-template-areas:
    "rail       rail"
    "pulse      pulse"
    "structure  volatility"
    "news       news"
    "prov       prov";
  gap:12px;align-items:start;
}
.mk-rail{grid-area:rail}
.mk-left,.mk-side{display:contents}
.mk-pulse{grid-area:pulse;align-self:start;display:flex;flex-direction:column}
.mk-struct{grid-area:structure}
.mk-vol{grid-area:volatility}
.mk-news{grid-area:news;align-self:start}
.mk-prov{grid-area:prov}

.mk-panel{
  background:var(--panel);border:1px solid var(--line);
  border-radius:var(--radius2);padding:14px 16px 15px;min-width:0;
}
.mk-pulse{padding:14px 0 0}
.mk-pulse .mk-ph{padding:0 16px}
.mk-pulse-body{min-width:0}
.mk-ph{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:11px}
.mk-ph h2{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.8px;
  text-transform:uppercase;color:var(--blue-text);margin:0;font-weight:700;
}
.mk-sub{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2)}
.mk-foot{
  margin-top:auto;padding:9px 16px 12px;border-top:1px solid var(--line2);
  font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);line-height:1.5;
}
.mk-foot code,.mk-lad-note code,.mk-vnote code,.mk-prov code{
  font-family:'Space Mono',monospace;font-size:11px;color:var(--muted);
}

/* ── session + risk rail ── */
.mk-rail{
  display:grid;grid-template-columns:200px repeat(3,minmax(0,1fr)) 226px;
  background:var(--panel);border:1px solid var(--line);
  border-radius:var(--radius2);overflow:hidden;
}
.mk-cell{padding:11px 15px;border-right:1px solid var(--line2);min-width:0}
.mk-cell:last-child{border-right:0}
.mk-ck{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.6px;
  text-transform:uppercase;color:var(--muted2);margin-bottom:5px;
}
.mk-cv{font-family:'Rajdhani',sans-serif;font-size:19px;font-weight:700;line-height:1.05;letter-spacing:.5px;color:var(--text)}
.mk-cv-sm{font-size:17px}
.mk-cv small{
  font-family:'Space Mono',monospace;font-size:11px;font-weight:400;
  color:var(--muted);letter-spacing:0;display:block;margin-top:4px;
}
.mk-badge{
  display:inline-block;font-family:'Space Mono',monospace;font-size:11px;
  font-weight:700;letter-spacing:1px;padding:3px 9px;border-radius:6px;text-transform:uppercase;
}
.mk-badge.low{color:#7ee3b4;background:rgba(61,220,151,.13);box-shadow:inset 0 0 0 1px rgba(61,220,151,.3)}
.mk-badge.medium{color:#f3cd7a;background:rgba(251,191,36,.13);box-shadow:inset 0 0 0 1px rgba(251,191,36,.3)}
.mk-badge.high{color:#ff9d9d;background:rgba(255,107,107,.13);box-shadow:inset 0 0 0 1px rgba(255,107,107,.32)}
.mk-badge.none{color:var(--muted);background:var(--panel2);box-shadow:inset 0 0 0 1px var(--line)}

/* ── cross-asset table ── */
table.mk-xa{width:100%;border-collapse:collapse;font-size:13px}
table.mk-xa thead th{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.2px;
  text-transform:uppercase;color:var(--muted2);font-weight:700;text-align:left;
  padding:8px 10px;border-bottom:1px solid var(--line);background:var(--panel2);
}
table.mk-xa th.n,table.mk-xa td.n{text-align:right}
table.mk-xa th.mvc,table.mk-xa td.mvc{width:120px;padding-left:14px}
table.mk-xa td{padding:7px 10px;border-bottom:1px solid var(--line2);vertical-align:middle}
table.mk-xa tbody tr:last-child td{border-bottom:0}
.mk-row{transition:background .12s;cursor:pointer}
.mk-row:hover{background:rgba(79,141,255,.055)}
.mk-row.is-sel{background:rgba(79,141,255,.11);box-shadow:inset 2px 0 0 var(--blue)}
.mk-row:focus-visible{outline:2px solid var(--blue);outline-offset:-2px}
.mk-row.mk-muted .mk-last,.mk-row.mk-muted .mk-pct{color:var(--muted)}
.mk-row.mk-muted .mk-mv i{opacity:.45}
.mk-sym{font-family:'Space Mono',monospace;font-size:12.5px;font-weight:700;letter-spacing:.6px;color:var(--text)}
.mk-grp{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.4px;text-transform:uppercase;color:var(--muted2)}
.mk-last{font-family:'Space Mono',monospace;font-size:13px;font-weight:700;font-variant-numeric:tabular-nums;color:var(--text)}
.mk-pct{font-family:'Space Mono',monospace;font-size:12.5px;font-weight:700;font-variant-numeric:tabular-nums}
.mk-last.up,.mk-pct.up{color:var(--green)}
.mk-last.dn,.mk-pct.dn{color:var(--red)}
.mk-last.flat,.mk-pct.flat{color:var(--muted2)}
/* magnitude only — a restatement of the percentage in the same row */
.mk-mv{
  display:inline-block;position:relative;height:9px;width:104px;
  background:#0a0f18;border:1px solid var(--line2);border-radius:3px;overflow:hidden;
}
.mk-mv::after{content:'';position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--muted2);opacity:.55}
.mk-mv i{position:absolute;top:0;bottom:0;left:50%;display:block}
.mk-mv i.up{background:linear-gradient(90deg,rgba(61,220,151,.55),var(--green));border-radius:0 3px 3px 0}
.mk-mv i.dn{background:linear-gradient(270deg,rgba(255,107,107,.55),var(--red));border-radius:3px 0 0 3px}

/* ── volatility & direction ── */
.mk-vrow{display:flex;align-items:baseline;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid var(--line2)}
.mk-vrow:last-child{border-bottom:0}
.mk-vrow-block{display:block}
.mk-vhead{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
.mk-vk{font-size:13px;color:var(--muted)}
.mk-vv{font-family:'Space Mono',monospace;font-size:13.5px;font-weight:700;font-variant-numeric:tabular-nums;color:var(--text)}
.mk-vv.up{color:var(--green)} .mk-vv.dn{color:var(--red)}
.mk-vsub{color:var(--muted2);font-weight:400}
.mk-na{color:var(--muted2);font-weight:400;font-size:13px}
.mk-breadth{display:flex;gap:3px;margin-top:9px}
.mk-breadth i{height:7px;flex:1;border-radius:2px;background:var(--line)}
.mk-breadth i.up{background:var(--green)} .mk-breadth i.dn{background:var(--red)}
.mk-vnote{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);margin-top:7px;line-height:1.5}

/* ── news & catalysts ── */
.mk-news #mkNewsBody{display:grid;grid-template-columns:minmax(300px,.8fr) minmax(0,1.2fr);gap:0 28px}
.mk-news-section+.mk-news-section{margin-top:14px;padding-top:13px;border-top:1px solid var(--line)}
.mk-news #mkNewsBody .mk-news-section+.mk-news-section{margin-top:0;padding-top:0;border-top:0;border-left:1px solid var(--line);padding-left:28px}
.mk-news-label{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);margin-bottom:3px}
.mk-cat{display:flex;gap:11px;padding:10px 0;border-bottom:1px solid var(--line2);align-items:flex-start}
.mk-cat:last-child{border-bottom:0}
.mk-cat-t{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);width:82px;flex:0 0 82px;padding-top:1px;font-variant-numeric:tabular-nums}
.mk-cat-b{min-width:0}
.mk-cat-h{font-size:13px;line-height:1.45;color:var(--text);display:block}
.mk-cat-link{color:inherit;text-decoration:none}
.mk-cat-link:hover{text-decoration:underline;text-underline-offset:2px}
.mk-cat-link:focus-visible{outline:2px solid var(--blue);outline-offset:2px;border-radius:2px}
.mk-cat-m{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);margin-top:3px;display:block}
.mk-imp{display:inline-block;width:6px;height:6px;border-radius:50%;margin-top:6px;flex-shrink:0;background:var(--muted2)}
.mk-imp.high{background:var(--red)} .mk-imp.medium{background:var(--yellow)}

/* ── notes / skeletons ── */
.mk-note{
  font-size:13px;color:var(--muted);line-height:1.5;padding:13px 14px;
  border:1px dashed var(--line);border-radius:8px;background:rgba(255,255,255,.012);
}
.mk-pulse .mk-note{margin:0 16px 14px}
.mk-note b{display:block;color:var(--text);font-size:13px;margin-bottom:3px}
.mk-note.err{border-color:rgba(255,107,107,.34);background:rgba(255,107,107,.06)}
.mk-note.err b{color:#ff9d9d}
.mk-skel-rows{display:flex;flex-direction:column;gap:9px;padding:2px 0 6px}
.mk-pulse .mk-skel-rows{padding:2px 16px 14px}
.mk-skel-rows i{
  display:block;height:12px;border-radius:5px;
  background:linear-gradient(90deg,var(--panel2) 25%,#182034 50%,var(--panel2) 75%);
  background-size:200% 100%;animation:mkSk 1.3s linear infinite;
}
.mk-skel-rows i:nth-child(2){width:70%} .mk-skel-rows i:nth-child(4){width:55%}
@keyframes mkSk{0%{background-position:200% 0}100%{background-position:-200% 0}}

/* ── market structure ── */
.mk-switch{display:inline-flex;gap:5px;background:var(--panel2);padding:3px;border-radius:8px;border:1px solid var(--line2)}
.mk-switch button{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;
  padding:6px 15px;min-height:44px;min-width:52px;border:0;border-radius:6px;
  background:none;color:var(--muted2);cursor:pointer;font-weight:700;
}
.mk-switch button:hover{color:var(--text)}
.mk-switch button[aria-pressed="true"]{background:rgba(79,141,255,.16);color:var(--blue-text);box-shadow:inset 0 0 0 1px rgba(79,141,255,.3)}
.mk-switch button:focus-visible{outline:2px solid var(--blue);outline-offset:1px}
.mk-lad{display:grid;grid-template-columns:auto minmax(0,1fr);gap:0 10px}
.mk-lad-y{position:relative;width:74px}
.mk-lad-y span{
  position:absolute;right:0;transform:translateY(-50%);
  font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);
  white-space:nowrap;font-variant-numeric:tabular-nums;
}
.mk-lad-plot{
  position:relative;height:250px;overflow:hidden;
  border:1px solid var(--line2);border-radius:8px;
  background:linear-gradient(180deg,rgba(255,255,255,.02),rgba(255,255,255,0) 46%),var(--panel2);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.035);
}
.mk-gl{position:absolute;left:0;right:0;height:1px;background:var(--line2);opacity:.6}
.mk-lvl{position:absolute;left:0;right:0;height:0;display:flex;align-items:center}
.mk-lvl-bar{position:absolute;left:0;right:0;height:1px}
.mk-lvl.untapped .mk-lvl-bar{background:repeating-linear-gradient(90deg,var(--blue) 0 6px,transparent 6px 11px);opacity:.85}
.mk-lvl.swept .mk-lvl-bar{background:var(--line);opacity:.9}
.mk-lvl.unknown .mk-lvl-bar{background:repeating-linear-gradient(90deg,var(--muted2) 0 4px,transparent 4px 9px);opacity:.6}
/* Lane placement: --lane is set per level by the renderer, and the lane width
   is a token so mobile can use a narrower one without the renderer knowing
   anything about breakpoints. */
.mk-lvl-tag{
  position:relative;z-index:2;
  margin-left:calc(9px + var(--lane,0) * var(--mk-lane-w,272px));
  font-family:'Space Mono',monospace;font-size:11px;
  padding:2px 8px;border-radius:5px;background:var(--panel);border:1px solid var(--line);
  color:var(--muted);white-space:nowrap;
}
.mk-lvl.untapped .mk-lvl-tag{color:var(--blue-text);border-color:rgba(79,141,255,.4)}
.mk-lvl-px{
  font-variant-numeric:tabular-nums;color:var(--muted2);margin-left:10px;
  padding-left:10px;border-left:1px solid var(--line2);
}
.mk-lvl-px em{font-style:normal;color:var(--muted);margin-left:8px}
.mk-lad-now{position:absolute;left:0;right:0;height:2px;background:var(--green);z-index:3;box-shadow:0 0 0 1px rgba(61,220,151,.25)}
.mk-lad-now b{
  position:absolute;right:8px;top:-10px;font-family:'Space Mono',monospace;font-size:11px;
  font-weight:700;color:#0b1a14;background:var(--green);padding:2px 7px;border-radius:5px;
  font-variant-numeric:tabular-nums;
}
/* A snapshot price is degraded data. It never wears the live green: the line
   and its label go amber, the same colour the freshness chip uses for cached. */
.mk-lad-now.is-fallback{background:var(--yellow);box-shadow:0 0 0 1px rgba(251,191,36,.25)}
.mk-lad-now.is-fallback b{background:var(--yellow);color:#241c05}
.mk-lg.f i{background:var(--yellow)}
.mk-lad-note.degraded{
  border-top-color:rgba(251,191,36,.34);color:var(--muted);
  background:rgba(251,191,36,.06);border-radius:0 0 8px 8px;padding:11px 12px;margin-top:11px;
}
.mk-lad-note.degraded b{color:#f3cd7a}
.mk-lad-legend{display:flex;gap:16px;margin-top:10px;flex-wrap:wrap}
.mk-lg{display:inline-flex;align-items:center;gap:7px;font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2)}
.mk-lg i{width:16px;height:2px;display:block}
.mk-lg.u i{background:repeating-linear-gradient(90deg,var(--blue) 0 4px,transparent 4px 7px)}
.mk-lg.s i{background:var(--line)}
.mk-lg.n i{background:repeating-linear-gradient(90deg,var(--muted2) 0 4px,transparent 4px 7px)}
.mk-lg.p i{background:var(--green)}
.mk-lad-note{
  font-size:13px;color:var(--muted);line-height:1.5;margin-top:11px;
  border-top:1px solid var(--line2);padding-top:11px;
}

/* ── provenance ── */
.mk-prov{
  display:flex;flex-wrap:wrap;gap:8px 22px;font-family:'Space Mono',monospace;
  font-size:11px;color:var(--muted2);padding:11px 16px;
  border:1px solid var(--line2);border-radius:var(--radius2);background:var(--panel);
}
.mk-prov b{color:var(--muted);font-weight:400}

/* ── mobile: approved order, stacked ── */
@media(max-width:767px){
  .mk-id{display:block;margin-bottom:12px}
  .mk-title{font-size:27px}
  .mk-id-meta{margin-top:9px;padding-bottom:0;gap:10px}
  .mk-action{min-height:44px;padding:12px 14px}
  /* Areas reset to one column; order pinned explicitly because desktop spans
     Market Structure across both columns, which one column cannot express
     through document order alone. */
  .mk-grid{grid-template-columns:minmax(0,1fr);grid-template-areas:none}
  .mk-grid > *{grid-area:auto;grid-column:1}
  .mk-pulse{align-self:auto;display:block;padding:14px 0 0}
  .mk-news{align-self:auto}
  .mk-news #mkNewsBody{display:block}
  .mk-news #mkNewsBody .mk-news-section+.mk-news-section{margin-top:14px;padding-top:13px;padding-left:0;border-left:0;border-top:1px solid var(--line)}
  .mk-foot{margin-top:0}
  .mk-rail{order:1} .mk-pulse{order:2} .mk-struct{order:3}
  .mk-vol{order:4} .mk-news{order:5} .mk-prov{order:6}
  .mk-rail{grid-template-columns:1fr 1fr}
  .mk-cell{border-right:1px solid var(--line2);border-bottom:1px solid var(--line2)}
  .mk-cell:nth-child(2n){border-right:0}
  .mk-cell:nth-child(1){grid-column:1/-1;border-right:0}
  .mk-cell:last-child{grid-column:1/-1;border-bottom:0}
  /* Five labelled columns need ~445px at 390px wide. Rather than scroll or
     clip, each row becomes its own small layout: instrument over asset class,
     last over change, percent held right. Only the move bar is dropped,
     because it restates the percentage beside it. */
  table.mk-xa,table.mk-xa thead,table.mk-xa tbody{display:block}
  table.mk-xa thead tr,table.mk-xa tbody tr{
    display:grid;grid-template-columns:minmax(0,1fr) auto 72px;
    column-gap:10px;align-items:center;padding:6px 10px;
  }
  table.mk-xa thead tr{grid-template-areas:'sym last pct'}
  table.mk-xa tbody tr{
    grid-template-areas:'sym last pct' 'grp chg pct';
    min-height:44px;border-bottom:1px solid var(--line2);
  }
  table.mk-xa tbody tr:last-child{border-bottom:0}
  table.mk-xa thead th,table.mk-xa tbody td{padding:0;border:0}
  table.mk-xa thead th:nth-child(1){grid-area:sym}
  table.mk-xa thead th:nth-child(3){grid-area:last;text-align:right}
  table.mk-xa thead th:nth-child(5){grid-area:pct;text-align:right}
  table.mk-xa thead th:nth-child(2),table.mk-xa thead th:nth-child(4),
  table.mk-xa thead th:nth-child(6),table.mk-xa tbody td:nth-child(6){display:none}
  table.mk-xa tbody td:nth-child(1){grid-area:sym}
  table.mk-xa tbody td:nth-child(2){grid-area:grp;font-size:11px}
  table.mk-xa tbody td:nth-child(3){grid-area:last;text-align:right}
  table.mk-xa tbody td:nth-child(4){grid-area:chg;text-align:right;font-size:11px}
  table.mk-xa tbody td:nth-child(5){grid-area:pct;text-align:right}
  .mk-lad-plot{height:210px}
  .mk-lad-y{width:58px}
  /* At 260px of plot the price and the status word cannot ride along; the
     line style and legend carry status, and the level name carries identity. */
  .mk-lvl-px,.mk-lvl-st{display:none}
  .mk-lad-plot{--mk-lane-w:62px}
  .mk-prov{gap:6px 16px}
}

/* ══════════════════════════════════════════════════════════════════════════
   NOVA INTELLIGENCE  (#page-assistant)
   Every rule below is scoped to #page-assistant, or to `.app-shell:has()` /
   `.wrap:has()` on the active page, so nothing here can reach Overview,
   Journal, Markets or Settings.
   ══════════════════════════════════════════════════════════════════════════ */

/* ── page identity ── */
#page-assistant .ni-id{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:12px}
#page-assistant .ni-kicker{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:2px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:5px;
}
#page-assistant .ni-id h1{
  font-family:'Rajdhani',sans-serif;font-size:31px;font-weight:700;
  letter-spacing:1.5px;margin:0;line-height:1;
}
#page-assistant .ni-id-meta{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding-bottom:3px}
/* one freshness vocabulary, matching Overview / Journal / Markets */
#page-assistant .ni-fresh{
  display:inline-flex;align-items:center;gap:6px;font-family:'Space Mono',monospace;font-size:11px;
  padding:4px 9px;border-radius:999px;border:1px solid var(--line);background:var(--panel2);color:var(--muted);
}
#page-assistant .ni-fresh::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--muted2)}
#page-assistant .ni-fresh.ok{color:#7ee3b4;border-color:rgba(61,220,151,.32);background:rgba(61,220,151,.10)}
#page-assistant .ni-fresh.ok::before{background:var(--green)}
#page-assistant .ni-fresh.stale{color:#f3cd7a;border-color:rgba(251,191,36,.32);background:rgba(251,191,36,.10)}
#page-assistant .ni-fresh.stale::before{background:var(--yellow)}
#page-assistant .ni-fresh.down{color:#ff9d9d;border-color:rgba(255,107,107,.34);background:rgba(255,107,107,.10)}
#page-assistant .ni-fresh.down::before{background:var(--red)}
#page-assistant .ni-fresh.busy::before{animation:niPulse 1.4s ease-in-out infinite}
@keyframes niPulse{0%,100%{opacity:.35}50%{opacity:1}}

/* ── grid ── */
#page-assistant .ni-grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(300px,1fr);gap:12px;min-height:0}
#page-assistant .ni-thread{display:flex;flex-direction:column;min-width:0;min-height:0}
#page-assistant .ni-rail{display:flex;flex-direction:column;gap:12px;min-width:0;min-height:0}
#page-assistant .ni-panel{padding:14px 16px 15px;border-radius:var(--radius2)}
#page-assistant .ni-ph{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:11px}
#page-assistant .ni-ph h2{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.8px;text-transform:uppercase;
  color:#c3b9ff;margin:0;font-weight:700;
}
#page-assistant .ni-sub{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2)}

/* ── conversation ── */
#page-assistant .ni-log{
  flex:1;min-height:0;overflow-y:auto;padding:2px 2px 4px;
  display:flex;flex-direction:column;gap:14px;
}
#page-assistant .ni-log:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
#page-assistant .ni-turn{display:flex;flex-direction:column;gap:9px}
#page-assistant .ni-q{
  align-self:flex-end;max-width:78%;background:rgba(79,141,255,.13);border:1px solid rgba(79,141,255,.28);
  border-radius:12px 12px 4px 12px;padding:10px 14px;font-size:13px;line-height:1.5;
}
#page-assistant .ni-q .ni-who{
  display:block;font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;
  color:var(--blue-text);margin-bottom:4px;
}
#page-assistant .ni-a{
  background:var(--panel);border:1px solid var(--line);border-radius:12px 12px 12px 4px;overflow:hidden;
}
#page-assistant .ni-a-head{display:flex;align-items:center;gap:9px;padding:10px 14px 0;flex-wrap:wrap}
#page-assistant .ni-a-who{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;color:#c3b9ff;font-weight:700;
}
#page-assistant .ni-a-body{padding:7px 14px 12px;font-size:13px;line-height:1.62;color:var(--text);max-width:74ch}
#page-assistant .ni-a-body p{margin:0 0 .85em}
#page-assistant .ni-a-body p:last-child{margin:0}

/* Grounding strip. Two different facts, kept apart deliberately:
   AVAILABILITY + AGE of each source is provable -- eight GET routes return the
   data and seven carry last_updated. WHETHER THE ASSISTANT INCORPORATED a
   source is NOT reported by /assistant/chat, and cannot be inferred from a
   200: summarize_system_context() wraps each optional context line in a bare
   except, so a healthy route can still be absent from the prompt. The strip
   therefore says "available", never "used". */
#page-assistant .ni-ground{border-top:1px solid var(--line2);background:var(--panel2);padding:9px 14px 10px}
#page-assistant .ni-ground-k{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;
  color:var(--muted2);margin-bottom:6px;
}
#page-assistant .ni-chips{display:flex;flex-wrap:wrap;gap:5px}
#page-assistant .ni-chip{
  font-family:'Space Mono',monospace;font-size:11px;padding:3px 8px;border-radius:5px;border:1px solid var(--line);
  background:var(--panel);color:var(--muted);display:inline-flex;align-items:center;gap:5px;
}
#page-assistant .ni-chip::before{content:'';width:5px;height:5px;border-radius:50%;background:var(--muted2)}
#page-assistant .ni-chip.on{color:#7ee3b4;border-color:rgba(61,220,151,.30)}
#page-assistant .ni-chip.on::before{background:var(--green)}
#page-assistant .ni-chip.stale{color:#f3cd7a;border-color:rgba(251,191,36,.30)}
#page-assistant .ni-chip.stale::before{background:var(--yellow)}
#page-assistant .ni-chip.off{color:var(--muted2);border-style:dashed}
#page-assistant .ni-chip.off::before{background:transparent;box-shadow:inset 0 0 0 1px var(--muted2)}
#page-assistant .ni-ground-note{font-size:12.5px;color:var(--muted2);line-height:1.45;margin-top:8px}
#page-assistant .ni-ground-note b{color:var(--muted);font-weight:400}

/* honest classification of what a line is */
#page-assistant .ni-kind{
  font-family:'Space Mono',monospace;font-size:11px;padding:2px 7px;border-radius:5px;letter-spacing:.6px;
}
#page-assistant .ni-kind.infer{color:#c3b9ff;background:var(--ai2);box-shadow:inset 0 0 0 1px rgba(155,140,255,.3)}
#page-assistant .ni-kind.na{color:var(--muted2);background:var(--panel2);box-shadow:inset 0 0 0 1px var(--line)}
#page-assistant .ni-kind.warn{color:#f3cd7a;background:rgba(251,191,36,.12);box-shadow:inset 0 0 0 1px rgba(251,191,36,.32)}
#page-assistant .ni-kind.bad{color:#ff9d9d;background:rgba(255,107,107,.12);box-shadow:inset 0 0 0 1px rgba(255,107,107,.34)}
#page-assistant .ni-a-note{
  display:flex;gap:8px;align-items:flex-start;padding:9px 14px;background:rgba(155,140,255,.06);
  border-top:1px solid rgba(155,140,255,.2);font-size:12.5px;color:var(--muted);line-height:1.45;
}

/* states inside the log */
#page-assistant .ni-state-note{
  font-size:13px;color:var(--muted);line-height:1.55;padding:14px;border:1px dashed var(--line);
  border-radius:10px;background:rgba(255,255,255,.012);
}
#page-assistant .ni-state-note b{display:block;color:var(--text);margin-bottom:4px}
#page-assistant .ni-state-note code{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted)}
#page-assistant .ni-state-note.err{border-color:rgba(255,107,107,.34);background:rgba(255,107,107,.06)}
#page-assistant .ni-state-note.err b{color:#ff9d9d}
#page-assistant .ni-state-note.warn{border-color:rgba(251,191,36,.32);background:rgba(251,191,36,.06)}
#page-assistant .ni-state-note.warn b{color:#f3cd7a}
#page-assistant .ni-skel{display:flex;flex-direction:column;gap:8px}
#page-assistant .ni-skel i{
  display:block;height:11px;border-radius:5px;
  background:linear-gradient(90deg,var(--panel2) 25%,#182034 50%,var(--panel2) 75%);
  background-size:200% 100%;animation:niSk 1.3s linear infinite;
}
#page-assistant .ni-skel i:nth-child(2){width:82%}
#page-assistant .ni-skel i:nth-child(3){width:58%}
@keyframes niSk{0%{background-position:200% 0}100%{background-position:-200% 0}}
#page-assistant .ni-thinking{
  display:inline-flex;align-items:center;gap:8px;font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);
}
#page-assistant .ni-thinking i{
  width:5px;height:5px;border-radius:50%;background:var(--ai);display:inline-block;animation:niBlink 1.2s infinite;
}
#page-assistant .ni-thinking i:nth-child(2){animation-delay:.2s}
#page-assistant .ni-thinking i:nth-child(3){animation-delay:.4s}
@keyframes niBlink{0%,80%,100%{opacity:.25}40%{opacity:1}}

/* ── composer ── */
#page-assistant .ni-composer{
  margin-top:12px;background:var(--panel);border:1px solid var(--line);
  border-radius:var(--radius2);padding:11px 12px;
}
#page-assistant .ni-suggest{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:9px}
#page-assistant .ni-sg{
  font-family:'Space Mono',monospace;font-size:11px;padding:8px 12px;min-height:36px;border-radius:8px;
  border:1px solid var(--line);background:var(--panel2);color:var(--muted);cursor:pointer;
}
#page-assistant .ni-sg:hover{border-color:var(--muted2);color:var(--text)}
#page-assistant .ni-sg:focus-visible{outline:2px solid var(--blue);outline-offset:1px}
#page-assistant .ni-sg[disabled]{opacity:.5;cursor:default}
#page-assistant .ni-crow{display:flex;gap:9px;align-items:flex-end}
#page-assistant .ni-cfield{flex:1;min-width:0;display:flex;flex-direction:column;gap:4px}
#page-assistant .ni-cfield label{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted2);
}
#page-assistant .ni-cinput{
  width:100%;background:var(--panel2);border:1px solid var(--line);border-radius:8px;
  padding:11px 12px;font-size:13px;color:var(--text);min-height:44px;line-height:1.5;
}
#page-assistant .ni-cinput::placeholder{color:var(--muted2)}
/* A real outline, not a box-shadow standing in for one: outline survives
   forced-colors mode and is what an audit can actually measure. */
#page-assistant .ni-cinput:focus-visible{outline:2px solid var(--blue);outline-offset:1px;border-color:var(--blue)}
#page-assistant .ni-cinput:focus{border-color:var(--blue)}
#page-assistant .ni-ask{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;padding:12px 18px;min-height:44px;
  border-radius:8px;cursor:pointer;background:rgba(155,140,255,.16);color:#c3b9ff;
  border:1px solid rgba(155,140,255,.34);font-weight:700;
}
#page-assistant .ni-ask:hover{background:rgba(155,140,255,.24)}
#page-assistant .ni-ask:focus-visible{outline:2px solid var(--blue);outline-offset:1px}
#page-assistant .ni-ask[disabled]{opacity:.55;cursor:default}
#page-assistant .ni-chint{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);margin-top:7px}

/* ── rail ── */
#page-assistant .ni-srow{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:8px 0;border-bottom:1px solid var(--line2);
}
#page-assistant .ni-srow:last-child{border-bottom:0}
#page-assistant .ni-sk{font-size:13px;color:var(--muted)}
#page-assistant .ni-sv{font-family:'Space Mono',monospace;font-size:12px;color:var(--muted2);white-space:nowrap}
#page-assistant .ni-sv.on{color:#7ee3b4}
#page-assistant .ni-sv.stale{color:#f3cd7a}
#page-assistant .ni-sv.off{color:var(--muted2)}
#page-assistant .ni-rail-note{
  font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);line-height:1.5;margin-top:9px;
  padding-top:9px;border-top:1px solid var(--line2);
}
#page-assistant .ni-rail-note b{color:var(--muted);font-weight:400}
#page-assistant .ni-rail-note code{font-size:11px}
#page-assistant .ni-rail-empty{font-size:13px;color:var(--muted2)}
#page-assistant .ni-task{
  display:flex;gap:8px;align-items:flex-start;padding:7px 0;border-bottom:1px solid var(--line2);
  font-size:13px;color:var(--muted);
}
#page-assistant .ni-task:last-child{border-bottom:0}
#page-assistant .ni-task::before{
  content:'';width:5px;height:5px;border-radius:50%;background:var(--muted2);margin-top:7px;flex-shrink:0;
}
#page-assistant .ni-focus-line{font-size:13px;color:var(--text);line-height:1.5}
#page-assistant .ni-lim{font-size:12.5px;color:var(--muted2);line-height:1.5}
#page-assistant .ni-lim b{color:var(--muted);font-weight:400}
#page-assistant .ni-lim-open{color:#f3cd7a}
#page-assistant .ni-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}

/* ── desktop workspace ──────────────────────────────────────────────────────
   The composer must be reachable without scrolling the page, so on desktop the
   shell becomes a fixed-height workspace and the two columns scroll inside
   themselves. Deliberately inside min-width:768px: an unscoped fit rule placed
   after the mobile media block wins on mobile too and collapses the page. */
@media(min-width:768px){
  .app-shell:has(> .main-content #page-assistant.active){height:100vh;min-height:100vh;overflow:hidden}
  .app-shell:has(> .main-content #page-assistant.active) .main-content{
    min-height:0;display:flex;flex-direction:column;overflow:hidden;
  }
  .app-shell:has(> .main-content #page-assistant.active) > .main-content > .wrap{
    flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden;padding-bottom:20px;
  }
  #page-assistant.active{flex:1;min-height:0;display:flex;flex-direction:column}
  #page-assistant .ni-grid{flex:1;min-height:0}
  #page-assistant .ni-rail{overflow-y:auto}
}

/* ── mobile ── */
@media(max-width:767px){
  #page-assistant .ni-id{display:block;margin-bottom:12px}
  #page-assistant .ni-id h1{font-size:27px}
  #page-assistant .ni-id-meta{margin-top:9px;padding-bottom:0}
  /* Single column, and the context rail moves BELOW the conversation: the
     answer is the reason the page exists, so it leads. */
  #page-assistant .ni-grid{grid-template-columns:minmax(0,1fr);gap:12px}
  #page-assistant .ni-log{overflow:visible}
  #page-assistant .ni-q{max-width:88%}
  #page-assistant .ni-a-body{max-width:none}
  /* 44px floor for every touch target on the page. */
  #page-assistant .ni-sg{min-height:44px;padding:12px 14px}
  #page-assistant .ni-crow{flex-direction:column;align-items:stretch;gap:9px}
  #page-assistant .ni-ask{width:100%;padding:12px 16px}
}

/* ══════════════════════════════════════════════════════════════════════════
   SETTINGS  (#page-settings)
   Every selector below is scoped to #page-settings, so nothing here can
   reach Overview, Journal, Markets or NOVA Intelligence.
   ══════════════════════════════════════════════════════════════════════════ */

/* ── identity ── */
#page-settings .st-id{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:9px}
#page-settings .st-kicker{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:2px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:5px;
}
#page-settings .st-id h1{
  font-family:'Rajdhani',sans-serif;font-size:28px;font-weight:700;letter-spacing:1.5px;margin:0;line-height:1;
}
#page-settings .st-id-meta{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding-bottom:3px}
#page-settings .st-fresh{
  display:inline-flex;align-items:center;gap:6px;font-family:'Space Mono',monospace;font-size:11px;
  padding:4px 9px;border-radius:999px;border:1px solid var(--line);background:var(--panel2);color:var(--muted);
}
#page-settings .st-fresh::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--muted2)}
#page-settings .st-fresh.ok{color:#7ee3b4;border-color:rgba(61,220,151,.32);background:rgba(61,220,151,.10)}
#page-settings .st-fresh.ok::before{background:var(--green)}
#page-settings .st-fresh.down{color:#ff9d9d;border-color:rgba(255,107,107,.34);background:rgba(255,107,107,.10)}
#page-settings .st-fresh.down::before{background:var(--red)}
#page-settings .st-fresh.busy::before{animation:stPulse 1.4s ease-in-out infinite}
@keyframes stPulse{0%,100%{opacity:.35}50%{opacity:1}}

/* ── configuration status band ── */
#page-settings .st-band{
  display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:var(--radius2);overflow:hidden;margin-bottom:9px;
}
#page-settings .st-bcell{background:var(--panel);padding:9px 14px 10px;display:flex;flex-direction:column;gap:2px;min-width:0}
#page-settings .st-bk{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.1px;text-transform:uppercase;color:var(--muted2);
}
#page-settings .st-bv{font-family:'Rajdhani',sans-serif;font-size:20px;font-weight:700;line-height:1.05;letter-spacing:.6px}
#page-settings .st-bv.ok{color:#7ee3b4}
#page-settings .st-bv.env{color:#f3cd7a}
#page-settings .st-bv.ro{color:var(--muted)}
#page-settings .st-bv.no{color:var(--muted2)}
#page-settings .st-bs{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2)}

/* ── independent column stacks ──────────────────────────────────────────────
   `align-items:start`, not stretch: each column flows on its own, so the third
   left-hand section starts straight after Working Memory rather than waiting
   for the taller rail to end. */
#page-settings .st-grid{
  display:grid;grid-template-columns:minmax(0,1.42fr) minmax(310px,1fr);gap:12px;align-items:start;
}
#page-settings .st-col{display:flex;flex-direction:column;gap:12px;min-width:0}
#page-settings .st-panel{
  padding:11px 15px 12px;border-radius:var(--radius2);min-width:0;display:flex;flex-direction:column;
}
#page-settings .st-ph{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:4px}
#page-settings .st-ph h2{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.8px;text-transform:uppercase;
  color:#c3b9ff;margin:0;font-weight:700;
}
#page-settings .st-pdesc{font-size:12.5px;color:var(--muted2);line-height:1.45;margin:0 0 9px}
#page-settings .st-pdesc b{color:var(--muted);font-weight:400}

/* scope badges: where a value actually lives */
#page-settings .st-tag{
  font-family:'Space Mono',monospace;font-size:11px;padding:2px 7px;border-radius:5px;letter-spacing:.5px;white-space:nowrap;
}
#page-settings .st-tag.env{color:#f3cd7a;background:rgba(251,191,36,.12);box-shadow:inset 0 0 0 1px rgba(251,191,36,.30)}
#page-settings .st-tag.browser{color:#8fb8ff;background:rgba(79,141,255,.12);box-shadow:inset 0 0 0 1px rgba(79,141,255,.30)}
#page-settings .st-tag.server{color:#7ee3b4;background:rgba(61,220,151,.12);box-shadow:inset 0 0 0 1px rgba(61,220,151,.28)}
#page-settings .st-tag.na{color:var(--muted2);background:var(--panel2);box-shadow:inset 0 0 0 1px var(--line)}

/* ── rows ── */
#page-settings .st-row{
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:6px 0;border-bottom:1px solid var(--line2);
}
#page-settings .st-row:last-child{border-bottom:0}
#page-settings .st-rk{font-size:13px;color:var(--muted);min-width:0}
#page-settings .st-rsub{
  display:block;font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2);margin-top:2px;
}
#page-settings .st-rv{font-family:'Space Mono',monospace;font-size:12px;color:var(--text);text-align:right;white-space:nowrap}
#page-settings .st-rv.on{color:#7ee3b4}
#page-settings .st-rv.off{color:var(--muted2)}
#page-settings .st-rv.warn{color:#f3cd7a}

/* ── tile picker: the one genuinely savable preference ── */
#page-settings .st-tiles{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin:1px 0 8px}
#page-settings .st-tile{
  font-family:'Space Mono',monospace;font-size:11px;padding:10px 8px;min-height:44px;border-radius:8px;cursor:pointer;
  border:1px solid var(--line);background:var(--panel2);color:var(--muted);
  display:inline-flex;align-items:center;justify-content:center;gap:6px;
}
#page-settings .st-tile:hover{border-color:var(--muted2);color:var(--text)}
#page-settings .st-tile:focus-visible{outline:2px solid var(--blue);outline-offset:1px}
#page-settings .st-tile[aria-pressed="true"]{
  color:#c3b9ff;background:rgba(155,140,255,.14);border-color:rgba(155,140,255,.34);font-weight:700;
}
/* Literal glyphs, not CSS backslash escapes: this stylesheet lives inside a
   Python string, where a CSS \2713 is read as the octal escape \271 plus '3'
   and renders as garbage. Same for \26A0. */
#page-settings .st-tile[aria-pressed="true"]::before{content:'✓';font-size:11px}
#page-settings .st-count{font-family:'Space Mono',monospace;font-size:11px;color:var(--muted2)}
#page-settings .st-count.bad{color:#ff9d9d}

/* ── save bar ── */
#page-settings .st-savebar{
  display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:8px;padding-top:8px;border-top:1px solid var(--line2);
}
#page-settings .st-btn{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.8px;padding:11px 16px;min-height:44px;
  border-radius:8px;cursor:pointer;border:1px solid var(--line);background:var(--panel2);color:var(--muted);font-weight:700;
}
#page-settings .st-btn:hover{border-color:var(--muted2);color:var(--text)}
#page-settings .st-btn:focus-visible{outline:2px solid var(--blue);outline-offset:1px}
#page-settings .st-btn.primary{background:rgba(155,140,255,.16);color:#c3b9ff;border-color:rgba(155,140,255,.34)}
#page-settings .st-btn.primary:hover{background:rgba(155,140,255,.24)}
#page-settings .st-btn.danger{background:rgba(255,107,107,.10);color:#ff9d9d;border-color:rgba(255,107,107,.32)}
#page-settings .st-btn.danger:hover{background:rgba(255,107,107,.18)}
#page-settings .st-btn[disabled]{opacity:.5;cursor:default}
#page-settings .st-btn[disabled]:hover{border-color:var(--line);color:var(--muted)}
#page-settings .st-savemsg{font-family:'Space Mono',monospace;font-size:11px;display:inline-flex;align-items:center;gap:6px}
#page-settings .st-savemsg.idle{color:var(--muted2)}
#page-settings .st-savemsg.dirty{color:#f3cd7a}
#page-settings .st-savemsg.saving{color:var(--muted)}
#page-settings .st-savemsg.ok{color:#7ee3b4}
#page-settings .st-savemsg.err{color:#ff9d9d}
#page-settings .st-sp{
  width:9px;height:9px;border-radius:50%;border:2px solid rgba(167,177,194,.3);border-top-color:var(--muted);
  display:inline-block;animation:stSpin .7s linear infinite;
}
@keyframes stSpin{to{transform:rotate(360deg)}}
#page-settings .st-fielderr{
  font-size:12.5px;color:#ff9d9d;line-height:1.45;margin-top:9px;display:flex;gap:7px;align-items:flex-start;
}
#page-settings .st-fielderr[hidden]{display:none}
#page-settings .st-fielderr::before{content:'⚠';flex-shrink:0}

/* ── notes and callouts ── */
#page-settings .st-note{
  font-size:12.5px;color:var(--muted2);line-height:1.4;margin-top:8px;padding-top:8px;border-top:1px solid var(--line2);
}
#page-settings .st-note[hidden]{display:none}
#page-settings .st-note b{color:var(--muted);font-weight:400}
#page-settings .st-note code{font-family:'Space Mono',monospace;font-size:11px}
#page-settings .st-callout{border-radius:8px;padding:9px 11px;font-size:12.5px;line-height:1.4;margin-top:9px}
#page-settings .st-callout code{font-family:'Space Mono',monospace;font-size:11px}
#page-settings .st-callout.warn{color:#f3cd7a;background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.26)}
#page-settings .st-callout.warn b{color:#ffd88a;font-weight:700}
#page-settings .st-callout.err{
  color:#ff9d9d;background:rgba(255,107,107,.07);border:1px solid rgba(255,107,107,.28);margin:0 0 12px;
}
#page-settings .st-callout.err b{color:#ffb3b3;font-weight:700}

/* Confirmation stays the size of the action it governs — it never grows to
   fill the page. */
#page-settings .st-confirm{
  margin-top:9px;border:1px solid rgba(255,107,107,.32);background:rgba(255,107,107,.06);
  border-radius:8px;padding:12px 13px;max-width:560px;
}
#page-settings .st-confirm h3{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;
  color:#ff9d9d;margin:0 0 6px;font-weight:700;
}
#page-settings .st-confirm p{font-size:12.5px;color:var(--muted);line-height:1.5;margin:0 0 10px}
#page-settings .st-confirm code{font-family:'Space Mono',monospace;font-size:11px}
#page-settings .st-confirm .st-cbtns{display:flex;gap:8px;flex-wrap:wrap}

/* ── boundaries list ── */
#page-settings .st-bgrid{display:flex;flex-direction:column;gap:0}
#page-settings .st-bitem{padding:5px 0;border-bottom:1px solid var(--line2);min-width:0}
#page-settings .st-bitem:last-child{border-bottom:0}
#page-settings .st-bitem h3{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1px;text-transform:uppercase;
  color:var(--muted);margin:0 0 3px;font-weight:700;
}
#page-settings .st-bitem p{font-size:12.5px;color:var(--muted2);line-height:1.4;margin:0}
#page-settings .st-bitem p b{color:var(--muted);font-weight:400}
#page-settings .st-bitem code{font-family:'Space Mono',monospace;font-size:11px}

/* ── loading / unavailable, sized to the content they stand in for ── */
#page-settings .st-skel{display:flex;flex-direction:column;gap:9px}
#page-settings .st-skel i{
  display:block;height:12px;border-radius:5px;
  background:linear-gradient(90deg,var(--panel2) 25%,#182034 50%,var(--panel2) 75%);
  background-size:200% 100%;animation:stSk 1.3s linear infinite;
}
#page-settings .st-skel.rows i{height:34px}
#page-settings .st-skel.st-tiles-sk{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px}
#page-settings .st-skel.st-tiles-sk i{height:44px}
#page-settings .st-skel i:nth-child(even){opacity:.75}
@keyframes stSk{0%{background-position:200% 0}100%{background-position:-200% 0}}
#page-settings .st-unavail{
  display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:8px;
  min-height:150px;border:1px dashed rgba(255,107,107,.30);border-radius:8px;
  background:rgba(255,107,107,.04);padding:20px 18px;
}
#page-settings .st-unavail .u1{
  font-family:'Space Mono',monospace;font-size:11px;letter-spacing:1.2px;text-transform:uppercase;
  color:#ff9d9d;font-weight:700;
}
#page-settings .st-unavail .u2{font-size:12.5px;color:var(--muted2);line-height:1.5;max-width:34ch}
#page-settings .st-unavail code{font-family:'Space Mono',monospace;font-size:11px}
#page-settings .st-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}

/* ── state driving ──────────────────────────────────────────────────────────
   `display:revert` reverts to the USER-AGENT value (block for a div), not to
   the value this stylesheet set, so revealing a grid or flex container that
   way silently turns it into a block. Each element declares its intrinsic
   display in --st-d and the reveal rule restores that. */
#page-settings [data-when]{--st-d:block}
#page-settings .st-band[data-when],#page-settings .st-tiles[data-when],
#page-settings .st-skel.st-tiles-sk[data-when]{--st-d:grid}
#page-settings .st-skel[data-when],#page-settings .st-unavail[data-when],
#page-settings .st-savebar[data-when],#page-settings .st-fielderr[data-when]{--st-d:flex}
/* The doubled [data-when] raises this to specificity (1,2,0) so it outranks
   two-class component rules such as `.st-skel.st-tiles-sk{display:grid}`.
   Without it the loading skeleton kept rendering underneath the loaded tiles
   — 144px of duplicate content that the state attribute appeared to hide. */
#page-settings [data-when][data-when]{display:none}
#page-settings[data-st-state="loaded"]  [data-when~="loaded"][data-when],
#page-settings[data-st-state="loading"] [data-when~="loading"][data-when],
#page-settings[data-st-state="error"]   [data-when~="error"][data-when]{display:var(--st-d)}
#page-settings[data-st-state="loaded"] .st-fielderr[hidden],
#page-settings[data-st-state="loaded"] .st-note[hidden]{display:none}

/* ── desktop: the legacy shell chrome is suppressed for this page too ── */
.wrap:has(> #page-settings.active) > .content-header,
.wrap:has(> #page-settings.active) > .live-strip-row,
.wrap:has(> #page-settings.active) > .footer{display:none}
/* Settings is composed to fit 1440x1000; the shared wrap padding is trimmed
   for this page only so the clean state needs no desktop scrolling. */
.wrap:has(> #page-settings.active){padding-top:12px;padding-bottom:8px}

/* ── mobile ── */
@media(max-width:767px){
  #page-settings .st-id{display:block}
  #page-settings .st-id h1{font-size:27px}
  #page-settings .st-id-meta{margin-top:9px;padding-bottom:0}
  #page-settings .st-band{grid-template-columns:repeat(2,1fr)}
  #page-settings .st-grid{grid-template-columns:minmax(0,1fr)}
  #page-settings .st-row{flex-direction:column;align-items:flex-start;gap:4px}
  #page-settings .st-rv{text-align:left}
  #page-settings .st-tiles,#page-settings .st-skel.st-tiles-sk{grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
  /* 44px floor for every touch target on the page. */
  #page-settings .st-btn{width:100%;justify-content:center;text-align:center}
  #page-settings .st-savebar{flex-direction:column;align-items:stretch}
  #page-settings .st-savemsg{justify-content:center;padding:4px 0}
  #page-settings .st-confirm{max-width:none}
  #page-settings .st-confirm .st-cbtns{flex-direction:column}
}
'''
