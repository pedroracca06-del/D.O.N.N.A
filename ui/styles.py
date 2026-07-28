"""ui/styles.py — NOVA dashboard CSS, extracted verbatim from ui/html.py
during the interface-modularization foundation (commit #9). No visual,
selector, or rule change was made — this is the exact same CSS text that
was previously inline inside DASHBOARD_HTML's <style> block.
"""
DASHBOARD_CSS = '''*{box-sizing:border-box;margin:0;padding:0}
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
  --shadow:0 1px 3px rgba(0,0,0,.07);
  --shadow2:0 1px 2px rgba(0,0,0,.05);
  --radius:16px;
  --radius2:10px;
}
@media(prefers-color-scheme:dark){
  :root{
    --bg:#0d0d0d;
    --bg2:#111111;
    --panel:#161616;
    --panel2:#1c1c1c;
    --line:#262626;
    --line2:#1e1e1e;
    --text:#f0f0f0;
    --muted:#888888;
    --muted2:#555555;
    --blue:#60a5fa;
    --blue2:#3b82f6;
    --green:#4ade80;
    --green2:rgba(74,222,128,.1);
    --yellow:#fbbf24;
    --red:#ff6b6b;
    --red2:rgba(255,107,107,.1);
    --gold:#fbbf24;
    --shadow:0 1px 4px rgba(0,0,0,.4);
    --shadow2:0 1px 3px rgba(0,0,0,.3);
  }
}

html,body{min-height:100%;background:var(--bg)}
body{
  font-family:system-ui,-apple-system,sans-serif;
  color:var(--text);
  background:var(--bg);
  padding:20px 24px 40px;
}
.wrap{max-width:1560px;margin:0 auto}

/* ── TOPBAR ── */
.topbar{
  display:flex;justify-content:space-between;align-items:center;
  gap:16px;flex-wrap:wrap;margin-bottom:16px;
}
.brand{display:flex;align-items:baseline;gap:16px}
.brand h1{
  font-family:'Rajdhani',sans-serif;
  font-size:42px;font-weight:700;letter-spacing:6px;
  color:var(--text);
  line-height:1;
}
.brand-tag{
  font-family:'Space Mono',monospace;
  font-size:10px;color:var(--muted2);letter-spacing:1px;
  border:1px solid var(--line);padding:4px 8px;border-radius:6px;
}
.top-right{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.status-badge{
  display:flex;align-items:center;gap:8px;
  padding:8px 14px;border-radius:999px;
  background:var(--green2);border:1px solid rgba(30,110,65,.2);
  font-family:'Space Mono',monospace;font-size:11px;color:var(--green);font-weight:700;
  letter-spacing:1px;
}
.dot{
  width:8px;height:8px;border-radius:50%;background:var(--green);
  animation:pulse 2s ease-in-out infinite;
}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(.85)}}
.nav{display:flex;gap:6px}
.tab-btn{
  font-family:'Rajdhani',sans-serif;font-size:14px;font-weight:700;letter-spacing:.5px;
  border:1px solid var(--line);padding:8px 16px;border-radius:8px;
  background:var(--panel);color:var(--muted);
  cursor:pointer;transition:all .15s ease;text-transform:uppercase;
}
.tab-btn:hover{color:var(--text);border-color:var(--muted2)}
.tab-btn.active{
  background:var(--text);
  border-color:var(--text);color:var(--panel);
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

/* ── CROSS-ASSET INTELLIGENCE ── */
.ca-mode-badge{
  font-family:'Space Mono',monospace;font-size:10px;font-weight:700;letter-spacing:1px;
  padding:4px 10px;border-radius:6px;text-transform:uppercase;
}
.ca-mode-ALIGNED  {background:var(--green2);color:var(--green);border:1px solid rgba(30,110,65,.2)}
.ca-mode-MIXED    {background:rgba(184,134,11,.08);color:var(--yellow);border:1px solid rgba(184,134,11,.2)}
.ca-mode-DIVERGING{background:rgba(180,83,9,.08);color:#b45309;border:1px solid rgba(180,83,9,.2)}
.ca-mode-WARNING  {background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.2)}
.ca-div-item{
  padding:10px 12px;border-radius:10px;margin-bottom:8px;
  border-left:3px solid var(--line);background:var(--panel2);
}
.ca-div-item:last-child{margin-bottom:0}
.ca-div-item.HIGH{border-left-color:var(--red);background:var(--red2)}
.ca-div-item.MEDIUM{border-left-color:var(--yellow);background:rgba(184,134,11,.05)}
.ca-div-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:8px}
.ca-div-name{font-size:12px;font-weight:700;color:var(--text)}
.ca-sev-badge{
  font-family:'Space Mono',monospace;font-size:9px;font-weight:700;letter-spacing:.5px;
  padding:2px 7px;border-radius:4px;flex-shrink:0;
}
.ca-sev-HIGH  {background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.2)}
.ca-sev-MEDIUM{background:rgba(184,134,11,.08);color:var(--yellow);border:1px solid rgba(184,134,11,.2)}
.ca-div-meaning{font-size:11px;color:var(--muted);line-height:1.5;margin-bottom:4px}
.ca-div-watch{font-size:11px;color:var(--muted2);line-height:1.4}
.ca-div-watch b{color:var(--text);font-weight:600}
.ca-clean{font-size:12px;color:var(--green);padding:6px 0;opacity:.85}

/* ── HERO BANNER ── */
.hero-banner{
  padding:16px 20px;border-radius:20px;
  border:1px solid var(--line);
  background:var(--panel);
  box-shadow:var(--shadow2);
}
.hero-eyebrow{
  font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2.5px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:8px;
}
.hero-title{
  font-family:'Rajdhani',sans-serif;font-size:28px;font-weight:700;
  line-height:1.05;letter-spacing:.5px;
}
.hero-sub{
  margin-top:8px;font-size:13px;line-height:1.6;color:var(--muted);max-width:80ch;
}
.hero-grid{display:grid;grid-template-columns:1.25fr .75fr;gap:16px;align-items:start}
.chip-stack{display:grid;gap:8px}
.chip{
  border-radius:10px;padding:8px 12px;
  border:1px solid var(--line);background:var(--panel2);
}
.chip-label{
  display:block;font-family:'Space Mono',monospace;font-size:9px;
  letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:4px;
}
.chip-value{
  display:block;font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;letter-spacing:.3px;
}
/* ── HERO WARNINGS (inline in hero) ── */
.hero-warn-list{margin-top:10px;border-top:1px solid var(--line2);padding-top:8px}
.hw-item{display:flex;align-items:baseline;gap:7px;padding:3px 0;font-size:11px;color:var(--muted)}
.hw-dot{width:5px;height:5px;border-radius:50%;background:var(--yellow);flex-shrink:0;margin-top:2px}

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

/* ── EXEC MONITOR + SESSION SCORECARD ── */
.exec-cards-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.exec-status-pill{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;
  border-radius:999px;font-family:'Space Mono',monospace;font-size:10px;font-weight:700;letter-spacing:1px}
.exec-status-active {background:var(--green2);color:var(--green);border:1px solid rgba(30,110,65,.2)}
.exec-status-paused {background:rgba(184,134,11,.08);color:var(--yellow);border:1px solid rgba(184,134,11,.2)}
.exec-status-blocked{background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.2)}
.exec-status-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.exec-pnl-big{font-family:'Rajdhani',sans-serif;font-size:40px;font-weight:700;line-height:1;letter-spacing:1px}
.exec-row{display:flex;justify-content:space-between;align-items:baseline;gap:8px;
  padding:8px 0;border-bottom:1px solid var(--line2)}
.exec-row:last-child{border-bottom:none}
.exec-row-label{font-size:12px;color:var(--muted)}
.exec-row-val{font-size:13px;font-weight:700;color:var(--text);text-align:right;max-width:65%}
.sc-cells{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:12px 0}
.sc-cell{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px 12px;text-align:center}
.sc-cell-num{font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:700;line-height:1}
.sc-cell-lab{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2);letter-spacing:1px;text-transform:uppercase;margin-top:3px}
.donna-grade-big{font-family:'Rajdhani',sans-serif;font-size:52px;font-weight:700;line-height:1;letter-spacing:2px}
@media(max-width:900px){.exec-cards-grid{grid-template-columns:1fr}}

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
.news-layout{display:grid;grid-template-columns:7fr 3fr;gap:16px;align-items:start}
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

#hvPlaybook{min-height:80px}
#hvSignals{min-height:80px}
#newsList{min-height:120px}
#hvSectors{min-height:80px}
#caDivergenceList{min-height:60px}
.breaking-events-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.breaking-event-card{
  padding:14px 16px;border-radius:14px;
  border:1px solid var(--line);background:var(--panel);
}
.breaking-event-badges{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
.impact-badge{
  font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1px;
  padding:2px 8px;border-radius:5px;font-weight:700;text-transform:uppercase;
}
.impact-badge.impact-HIGH{background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.2)}
.impact-badge.impact-MEDIUM{background:rgba(184,134,11,.08);color:var(--yellow);border:1px solid rgba(184,134,11,.2)}
.impact-badge.impact-LOW{background:var(--panel2);color:var(--muted2);border:1px solid var(--line)}
.dir-badge{
  font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1px;
  padding:2px 8px;border-radius:5px;font-weight:700;text-transform:uppercase;
}
.dir-badge.dir-BULL{background:var(--green2);color:var(--green);border:1px solid rgba(30,110,65,.2)}
.dir-badge.dir-BEAR{background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.2)}
.dir-badge.dir-NEUTRAL{background:var(--panel2);color:var(--muted2);border:1px solid var(--line)}
.breaking-event-title{font-size:12px;font-weight:600;line-height:1.4;color:var(--text);margin-bottom:4px}
.breaking-event-source{font-size:10px;color:var(--muted2);font-family:'Space Mono',monospace}
@media(max-width:900px){.breaking-events-grid{grid-template-columns:1fr}}

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

/* ── ALERT ITEMS ── */
.alert-item{
  padding:12px 14px;border-radius:12px;margin-bottom:10px;
  border:1px solid var(--line);background:var(--panel2);
}
.alert-item:last-child{margin-bottom:0}
.alert-header{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}
.alert-ticker{font-family:'Rajdhani',sans-serif;font-size:18px;font-weight:700;letter-spacing:1px}
.alert-signal{
  font-family:'Space Mono',monospace;font-size:10px;padding:3px 8px;border-radius:6px;
  background:rgba(37,99,235,.08);border:1px solid rgba(37,99,235,.15);color:var(--blue);
}
.alert-meta{font-size:11px;color:var(--muted2);margin-bottom:6px}
.alert-body{font-size:12px;color:var(--muted);line-height:1.5}
.verdict-TAKE{color:var(--green)}
.verdict-CAUTION{color:var(--yellow)}
.verdict-SKIP{color:var(--red)}

/* ── FOOTER ── */
.footer{
  margin-top:24px;display:flex;justify-content:space-between;
  gap:12px;flex-wrap:wrap;
  font-family:'Space Mono',monospace;font-size:10px;color:var(--muted2);
  letter-spacing:.5px;
}

/* ── JOURNAL TAB ── */
.journal-btn{background:var(--panel) !important;border-color:rgba(184,134,11,.3) !important;color:var(--gold) !important}
.journal-btn.active{background:var(--text) !important;border-color:var(--text) !important;color:var(--panel) !important}
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

/* ── NOVA FEED ── */
.fd-page-header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:14px}
.fd-page-title{font-family:\'Rajdhani\',sans-serif;font-size:22px;font-weight:700;letter-spacing:1px}
.fd-meta{font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2);letter-spacing:.5px}
.fd-filter-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.fd-filter-btn{padding:5px 14px;border-radius:8px;border:1px solid var(--line);background:var(--panel2);color:var(--muted2);font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1px;cursor:pointer;transition:all .15s;text-transform:uppercase}
.fd-filter-btn:hover{border-color:rgba(184,134,11,.3);color:var(--gold)}
.fd-filter-btn.active{background:rgba(184,134,11,.08);border-color:rgba(184,134,11,.3);color:var(--gold)}
.fd-refresh-btn{padding:5px 14px;border-radius:8px;border:1px solid var(--line);background:transparent;color:var(--muted2);font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1px;cursor:pointer;transition:all .15s;text-transform:uppercase}
.fd-refresh-btn:hover{color:var(--text);border-color:var(--muted2)}
.fd-card{border:1px solid var(--line);border-radius:10px;background:var(--panel);padding:10px 14px;margin-bottom:7px}
.fd-card.fd-signal{border-left:3px solid var(--line)}
.fd-card.fd-signal.fd-alerted{border-left-color:var(--gold)}
.fd-card.fd-signal.fd-grade-a{border-left-color:var(--green)}
.fd-card.fd-signal.fd-grade-b{border-left-color:var(--yellow)}
.fd-card.fd-governance{border-left:3px solid var(--muted2);background:var(--panel2)}
.fd-card.fd-execution{border-left:3px solid var(--blue)}
.fd-card.fd-mr2change{border-left:3px solid rgba(96,165,250,.4)}
.fd-row1{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:4px}
.fd-ts{font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2);white-space:nowrap;min-width:60px}
.fd-symbol{font-family:\'Rajdhani\',sans-serif;font-size:14px;font-weight:700}
.fd-badge{font-family:\'Space Mono\',monospace;font-size:8px;font-weight:700;padding:2px 6px;border-radius:4px;text-transform:uppercase;letter-spacing:.5px;border:1px solid transparent}
.fd-badge.dir-long{color:var(--green);background:var(--green2);border-color:rgba(74,222,128,.2)}
.fd-badge.dir-short{color:var(--red);background:var(--red2);border-color:rgba(255,107,107,.2)}
.fd-badge.grade-a{color:var(--green)}
.fd-badge.grade-b{color:var(--yellow)}
.fd-badge.grade-c,.fd-badge.grade-d{color:var(--muted2)}
.fd-badge.st-er{color:var(--gold);background:rgba(184,134,11,.08);border-color:rgba(184,134,11,.2)}
.fd-badge.st-hu{color:var(--blue);background:rgba(96,165,250,.08);border-color:rgba(96,165,250,.2)}
.fd-badge.st-ev{color:var(--muted2);background:rgba(160,160,160,.05);border-color:var(--line)}
.fd-badge.st-inv{color:var(--red);background:var(--red2);border-color:rgba(255,107,107,.2)}
.fd-badge.st-nt{color:var(--muted2);background:rgba(160,160,160,.05);border-color:var(--line)}
.fd-badge.ev-gov{color:var(--muted2);background:rgba(160,160,160,.05);border-color:var(--line)}
.fd-badge.ev-exec{color:var(--blue);background:rgba(96,165,250,.08);border-color:rgba(96,165,250,.2)}
.fd-badge.ev-mr2{color:var(--blue2);background:rgba(96,165,250,.06);border-color:rgba(96,165,250,.15)}
.fd-badge.ev-intel{color:var(--gold);background:rgba(184,134,11,.08);border-color:rgba(184,134,11,.2)}
.fd-badge.ev-market{color:var(--yellow);background:rgba(250,204,21,.06);border-color:rgba(250,204,21,.2)}
.fd-card.fd-intelligence{border-left:3px solid rgba(184,134,11,.5)}
.fd-card.fd-market{border-left:3px solid rgba(250,204,21,.4)}
.fd-row2{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.fd-chip{font-family:\'Space Mono\',monospace;font-size:8px;color:var(--muted2);letter-spacing:.3px;white-space:nowrap}
.fd-chip strong{color:var(--text);font-weight:700}
.fd-rationale{font-size:11px;color:var(--muted);line-height:1.5;margin-top:6px;padding-top:6px;border-top:1px solid var(--line);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.fd-gov-reason{font-size:11px;color:var(--muted);margin-top:3px;line-height:1.4}
.fd-empty{text-align:center;padding:60px 20px;color:var(--muted2);font-family:\'Space Mono\',monospace;font-size:11px}
.fd-load-btn{padding:7px 22px;border-radius:8px;border:1px solid var(--line);background:var(--panel2);color:var(--muted2);font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1px;cursor:pointer;transition:all .15s;text-transform:uppercase}
.fd-load-btn:hover{border-color:var(--muted2);color:var(--text)}
.fd-stats-row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--line)}
.fd-stat{font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2)}
.fd-stat strong{color:var(--text)}
.fd-sep{width:1px;background:var(--line);align-self:stretch;margin:0 4px}
.fd-rationale-full{font-size:11px;color:var(--muted);line-height:1.6;margin-top:6px;padding-top:6px;border-top:1px solid var(--line)}
.fd-entry-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:5px}
.fd-entry-cell{font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2)}
.fd-entry-cell strong{color:var(--text);display:block;font-size:11px;margin-top:1px}
.fd-expand-btn{font-family:\'Space Mono\',monospace;font-size:8px;letter-spacing:.5px;color:var(--muted2);background:none;border:none;cursor:pointer;padding:2px 0;margin-top:4px;transition:color .15s}
.fd-expand-btn:hover{color:var(--gold)}
.fd-notify-banner{display:flex;align-items:center;gap:10px;padding:8px 14px;background:rgba(0,128,255,.07);border:1px solid rgba(0,128,255,.2);border-radius:8px;margin-bottom:12px;font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2)}
.fd-notify-btn{padding:4px 12px;border-radius:6px;border:1px solid rgba(0,128,255,.3);background:rgba(0,128,255,.1);color:#60a5fa;font-family:\'Space Mono\',monospace;font-size:8px;cursor:pointer;letter-spacing:.5px;transition:all .15s}
.fd-notify-btn:hover{background:rgba(0,128,255,.2)}

/* ── MARKET REALITY PAGE ── */
.mr-page-title{font-family:\'Rajdhani\',sans-serif;font-size:22px;font-weight:700;letter-spacing:1px;margin-bottom:4px}
.mr-state-badge{display:inline-block;padding:6px 18px;border-radius:8px;font-family:\'Rajdhani\',sans-serif;font-size:20px;font-weight:700;letter-spacing:2px;margin-bottom:4px}
.mr-state-bull-dom{background:rgba(0,200,81,.12);border:1px solid rgba(0,200,81,.3);color:#00c851}
.mr-state-bull-lean{background:rgba(0,200,81,.06);border:1px solid rgba(0,200,81,.2);color:#00c851}
.mr-state-bear-dom{background:rgba(255,68,68,.12);border:1px solid rgba(255,68,68,.3);color:#ff4444}
.mr-state-bear-lean{background:rgba(255,68,68,.06);border:1px solid rgba(255,68,68,.2);color:#ff4444}
.mr-state-panic{background:rgba(255,0,0,.2);border:1px solid rgba(255,0,0,.5);color:#ff0000}
.mr-state-range{background:rgba(160,160,160,.1);border:1px solid var(--line);color:var(--muted)}
.mr-state-neutral{background:rgba(160,160,160,.08);border:1px solid var(--line);color:var(--muted2)}
.mr-block-flag{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:7px;font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:.5px;font-weight:700;margin:2px}
.mr-block-active{background:rgba(255,68,68,.1);border:1px solid rgba(255,68,68,.35);color:#ff4444}
.mr-block-clear{background:rgba(0,200,81,.07);border:1px solid rgba(0,200,81,.2);color:#00c851}
.mr-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-top:14px}
.mr-cell{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:12px 16px}
.mr-cell-label{font-family:\'Space Mono\',monospace;font-size:8px;letter-spacing:1px;color:var(--muted2);text-transform:uppercase;margin-bottom:4px}
.mr-cell-val{font-size:18px;font-weight:700;font-family:\'Rajdhani\',sans-serif;color:var(--text)}
.mr-cell-sub{font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2);margin-top:2px}
.mr-score-bar{height:6px;border-radius:3px;background:var(--line);margin-top:6px;overflow:hidden}
.mr-score-fill-bull{height:100%;background:var(--green);border-radius:3px;transition:width .4s}
.mr-score-fill-bear{height:100%;background:var(--red);border-radius:3px;transition:width .4s}

/* ── GOVERNANCE PAGE ── */
.gov-page-title{font-family:\'Rajdhani\',sans-serif;font-size:22px;font-weight:700;letter-spacing:1px;margin-bottom:4px}
.gov-gate-list{display:flex;flex-direction:column;gap:6px;margin-top:12px}
.gov-gate{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-radius:10px;border:1px solid var(--line);background:var(--panel2);transition:border-color .15s}
.gov-gate-name{font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:.5px;color:var(--muted2);text-transform:uppercase;flex:1}
.gov-gate-detail{font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2);margin:0 10px;text-align:right;flex:2}
.gov-status{display:inline-block;padding:3px 10px;border-radius:5px;font-family:\'Space Mono\',monospace;font-size:8px;letter-spacing:.5px;font-weight:700;min-width:56px;text-align:center}
.gov-open{background:rgba(0,200,81,.1);border:1px solid rgba(0,200,81,.25);color:#00c851}
.gov-locked{background:rgba(255,68,68,.1);border:1px solid rgba(255,68,68,.3);color:#ff4444}
.gov-warn{background:rgba(255,187,51,.1);border:1px solid rgba(255,187,51,.3);color:#ffbb33}
.gov-off{background:rgba(160,160,160,.08);border:1px solid var(--line);color:var(--muted2)}
.gov-section-label{font-family:\'Space Mono\',monospace;font-size:8px;letter-spacing:2px;color:var(--muted2);text-transform:uppercase;margin-top:14px;margin-bottom:6px;padding-left:2px}
.gov-lockouts{margin-top:10px;padding:10px 14px;border-radius:10px;border:1px solid rgba(255,68,68,.2);background:rgba(255,68,68,.04)}
.gov-lockout-item{font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted);padding:3px 0;border-bottom:1px solid var(--line)}
.gov-lockout-item:last-child{border-bottom:none}
.gov-header-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}

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

/* ── TRADE CARDS ── */
.j-date-group{margin-bottom:20px}
.j-date-label{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--gold);text-transform:uppercase;font-weight:700;padding:6px 0;border-bottom:1px solid rgba(240,180,41,.15);margin-bottom:10px}
.trade-card{border:1px solid var(--line);border-radius:12px;background:var(--panel2);padding:14px 18px;margin-bottom:10px;transition:border-color .15s;border-left:3px solid transparent}
.trade-card:hover{border-color:rgba(184,134,11,.3)}
.trade-card.outcome-WIN{border-left-color:var(--green)}
.trade-card.outcome-LOSS{border-left-color:var(--red)}
.trade-card.outcome-BREAKEVEN{border-left-color:var(--yellow)}
.trade-card.outcome-OPEN{border-left-color:var(--muted2)}
.tc-badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.tc-badge{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:.8px;text-transform:uppercase;padding:2px 7px;border-radius:4px;background:rgba(0,0,0,.04);color:var(--muted2);border:1px solid var(--line)}
.tc-badge.b-auto{background:rgba(184,134,11,.08);color:var(--gold);border-color:rgba(184,134,11,.25)}
.tc-badge.b-tier{background:rgba(30,110,65,.07);color:var(--green);border-color:rgba(30,110,65,.2)}
.tc-main{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}
.tc-ticker{font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:700;line-height:1}
.tc-dir{font-family:'Space Mono',monospace;font-size:9px;font-weight:700;padding:2px 8px;border-radius:5px;margin-left:8px;vertical-align:middle}
.tc-dir.long{background:rgba(30,110,65,.1);color:var(--green)}
.tc-dir.short{background:rgba(192,57,43,.09);color:var(--red)}
.tc-pnl{font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;line-height:1}
.tc-time{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2);text-align:right;margin-top:2px}
.tc-exec{font-family:'Space Mono',monospace;font-size:10px;color:var(--muted);margin-bottom:8px;letter-spacing:.3px}
.tc-ctx{font-size:11px;color:var(--muted2);display:flex;gap:14px;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:8px;margin-top:8px;align-items:center;line-height:1.4}
.tc-ctx strong{color:var(--text)}
.tc-footer{display:flex;justify-content:space-between;align-items:center;margin-top:8px}
.tc-outcome-badge{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1px;font-weight:700;padding:3px 9px;border-radius:5px;text-transform:uppercase}
.tc-outcome-badge.WIN{background:rgba(30,110,65,.09);color:var(--green)}
.tc-outcome-badge.LOSS{background:rgba(192,57,43,.09);color:var(--red)}
.tc-outcome-badge.BREAKEVEN{background:rgba(184,134,11,.09);color:var(--gold)}
.tc-outcome-badge.OPEN{background:rgba(0,0,0,.05);color:var(--muted2)}
/* ── TOGGLE BUTTONS ── */
.toggle-group{display:flex;gap:6px}
.toggle-btn{flex:1;padding:10px 6px;border-radius:10px;border:1px solid var(--line);background:var(--panel2);color:var(--muted2);font-family:'Space Mono',monospace;font-size:10px;font-weight:700;letter-spacing:.8px;cursor:pointer;transition:all .15s;text-transform:uppercase}
.toggle-btn:hover{border-color:var(--muted2);color:var(--text)}
.toggle-btn.active-long{background:rgba(30,110,65,.1);border-color:var(--green);color:var(--green)}
.toggle-btn.active-short{background:rgba(192,57,43,.08);border-color:var(--red);color:var(--red)}
.toggle-btn.active-win{background:rgba(30,110,65,.1);border-color:var(--green);color:var(--green)}
.toggle-btn.active-loss{background:rgba(192,57,43,.08);border-color:var(--red);color:var(--red)}
.toggle-btn.active-be{background:rgba(184,134,11,.08);border-color:var(--gold);color:var(--gold)}

/* ── EXECUTION TAB v2 ── */
.exec-heartbeat{display:flex;align-items:center;gap:14px;padding:14px 24px;border-radius:12px;border:1px solid var(--line);background:var(--panel2);flex-wrap:wrap}
.exec-pulse{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.exec-pulse.active{background:var(--green);box-shadow:0 0 7px rgba(30,110,65,.5)}
.exec-pulse.blocked{background:var(--red);box-shadow:0 0 7px rgba(192,57,43,.5)}
.exec-pulse.paused{background:var(--yellow);box-shadow:0 0 5px rgba(184,134,11,.4)}
.exec-pulse.offline{background:var(--muted2)}
.exec-hb-label{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:1.2px;font-weight:700;text-transform:uppercase}
.exec-hb-sep{width:1px;height:20px;background:var(--line);flex-shrink:0}
.exec-hb-chip{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:.8px;padding:4px 11px;border-radius:6px;border:1px solid var(--line);background:var(--panel);color:var(--muted2);text-transform:uppercase;white-space:nowrap}
.exec-hb-chip.green{background:rgba(30,110,65,.08);border-color:rgba(30,110,65,.25);color:var(--green)}
.exec-hb-chip.red{background:rgba(192,57,43,.08);border-color:rgba(192,57,43,.25);color:var(--red)}
.exec-hb-chip.yellow{background:rgba(184,134,11,.08);border-color:rgba(184,134,11,.25);color:var(--gold)}
.exec-hb-chip.blue{background:rgba(37,99,235,.07);border-color:rgba(37,99,235,.2);color:var(--blue)}
.exec-state-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}
.exec-kv{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid var(--line)}
.exec-kv:last-child{border-bottom:none}
.exec-kv-lab{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:.8px;color:var(--muted2);text-transform:uppercase;flex-shrink:0}
.exec-kv-val{font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;text-align:right;line-height:1.2}
.exec-kv-val.mono{font-family:'Space Mono',monospace;font-size:11px;font-weight:400}
.exec-pnl-hero{font-family:'Rajdhani',sans-serif;font-size:38px;font-weight:700;line-height:1;letter-spacing:.5px;margin-bottom:16px}
.rej-last-card{border:1px solid rgba(192,57,43,.2);border-radius:10px;background:rgba(192,57,43,.03);padding:14px 16px}
.rej-code-badge{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1px;color:var(--red);text-transform:uppercase;background:rgba(192,57,43,.08);border:1px solid rgba(192,57,43,.2);padding:2px 7px;border-radius:4px;display:inline-block;margin-bottom:8px}
.rej-ticker-row{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}
.rej-ticker{font-family:'Rajdhani',sans-serif;font-size:20px;font-weight:700}
.rej-reason{font-size:12px;color:var(--muted);line-height:1.5}
.rej-bar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.rej-bar-label{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:.6px;color:var(--muted2);text-transform:uppercase;flex:0 0 auto;max-width:170px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rej-bar-track{flex:1;height:4px;border-radius:3px;background:var(--line);overflow:hidden;min-width:30px}
.rej-bar-fill{height:100%;border-radius:3px;background:rgba(192,57,43,.6)}
.rej-count{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2);width:24px;text-align:right;flex-shrink:0}
.sc2-cells{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}
.sc2-cell{text-align:center;padding:14px 8px;border-radius:10px;background:var(--panel2);border:1px solid var(--line)}
.sc2-num{font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;line-height:1;margin-bottom:4px}
.sc2-lab{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1px;color:var(--muted2);text-transform:uppercase}
.sc2-detail-cell{padding:10px 14px;background:var(--panel2);border-radius:10px;border:1px solid var(--line)}
.sc2-detail-cell .exec-kv-lab{display:block;margin-bottom:6px}
@media(max-width:960px){.exec-state-grid{grid-template-columns:1fr}.sc2-cells{grid-template-columns:1fr 1fr}}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(0,0,0,.12);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:rgba(0,0,0,.2)}

/* ── RESPONSIVE ── */
@media(max-width:1200px){
  .hero-grid,.main-grid,.stat-grid{grid-template-columns:1fr 1fr}
  .stat-grid{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:760px){
  body{padding:12px}
  .brand h1{font-size:32px}
  .hero-title{font-size:26px}
  .hero-grid,.main-grid,.stat-grid,.live-strip-row{grid-template-columns:1fr}
}

/* ═══════════════════════════════════════
   H.A.R.V.E.Y EXECUTION TAB
   ═══════════════════════════════════════ */

.harvey-btn {
  position: relative;
  background: var(--panel) !important;
  border-color: rgba(30,110,65,.3) !important;
  color: var(--green) !important;
}
.harvey-btn.active {
  background: var(--text) !important;
  border-color: var(--text) !important;
  color: var(--panel) !important;
}

.verdict-banner {
  border-radius: 18px;
  padding: 28px 30px;
  border: 1px solid var(--line);
  background: var(--panel);
  position: relative;
  overflow: hidden;
}
.verdict-banner.green { border-color: rgba(30,110,65,.3); background: var(--green2); }
.verdict-banner.red { border-color: rgba(192,57,43,.3); background: var(--red2); }
.verdict-banner.yellow { border-color: rgba(184,134,11,.25); background: rgba(184,134,11,.05); }

.verdict-label { font-family: 'Space Mono', monospace; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 12px; color: var(--muted2); }
.verdict-word { font-family: 'Rajdhani', sans-serif; font-size: 72px; font-weight: 700; line-height: 1; letter-spacing: 2px; }
.verdict-banner.green .verdict-word { color: var(--green) }
.verdict-banner.red   .verdict-word { color: var(--red) }
.verdict-banner.yellow .verdict-word { color: var(--yellow) }
.verdict-reason { margin-top: 14px; font-size: 14px; line-height: 1.65; color: var(--muted); max-width: 80ch; }
.verdict-grid { display: grid; grid-template-columns: 1.3fr .7fr; gap: 18px; align-items: start; }

.bias-wrap { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.bias-gauge { width: 100%; height: 14px; background: var(--panel2); border-radius: 999px; overflow: hidden; border: 1px solid var(--line); }
.bias-fill { height: 100%; border-radius: 999px; transition: width .6s ease, background .6s ease; }
.bias-score-big { font-family: 'Rajdhani', sans-serif; font-size: 52px; font-weight: 700; line-height: 1; }
.bias-direction { font-family: 'Space Mono', monospace; font-size: 13px; font-weight: 700; letter-spacing: 2px; }

.orb-card { border-radius: var(--radius); padding: 20px 22px; border: 1px solid var(--line); background: var(--panel); }
.orb-status-pill { display: inline-block; padding: 5px 14px; border-radius: 999px; font-family: 'Space Mono', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 12px; }
.orb-FORMING    { background: rgba(184,134,11,.08); border: 1px solid rgba(184,134,11,.2); color: var(--yellow) }
.orb-SET        { background: rgba(37,99,235,.08);  border: 1px solid rgba(37,99,235,.15);  color: var(--blue) }
.orb-ACTIVE     { background: var(--green2);         border: 1px solid rgba(30,110,65,.2);  color: var(--green) }
.orb-WATCH      { background: rgba(37,99,235,.08);  border: 1px solid rgba(37,99,235,.15);  color: var(--blue) }
.orb-WAIT       { background: var(--panel2);         border: 1px solid var(--line);          color: var(--muted) }
.orb-PENDING    { background: var(--panel2);         border: 1px solid var(--line2);         color: var(--muted2) }
.orb-PRE-MARKET { background: var(--panel2);         border: 1px solid var(--line2);         color: var(--muted2) }
.orb-RANGING    { background: rgba(184,134,11,.06);  border: 1px solid rgba(184,134,11,.15); color: var(--yellow) }

.orb-status-label { font-family: 'Rajdhani', sans-serif; font-size: 26px; font-weight: 700; margin-bottom: 8px; }
.orb-note { font-size: 13px; color: var(--muted); line-height: 1.6; }

.pi-verdict { font-size:13px; color:var(--muted); line-height:1.55; padding:10px 12px;
              border-radius:8px; background:var(--panel2); border:1px solid var(--line);
              margin-bottom:12px; font-style:italic; }
.pi-table { width:100%; border-collapse:collapse; }
.pi-table td { padding:6px 0; border-bottom:1px solid var(--line); font-size:13px; font-weight:600; }
.pi-table tr:last-child td { border-bottom:none; }
.pi-label { font-family:'Space Mono',monospace; font-size:10px; color:var(--muted2); letter-spacing:.5px; }
.pi-price { text-align:right; color:var(--text); }
.pi-rs    { text-align:right; width:28px; }
.pi-tag-r { font-family:'Space Mono',monospace; font-size:9px; font-weight:700; color:var(--red);
            background:var(--red2); border:1px solid rgba(192,57,43,.2);
            padding:1px 5px; border-radius:3px; letter-spacing:.5px; }
.pi-tag-s { font-family:'Space Mono',monospace; font-size:9px; font-weight:700; color:var(--green);
            background:var(--green2); border:1px solid rgba(30,110,65,.2);
            padding:1px 5px; border-radius:3px; letter-spacing:.5px; }
.pi-cur-row td { padding:4px 0; border-bottom:2px solid rgba(240,180,41,.5) !important; }
.pi-cur-line { display:flex; align-items:center; gap:7px; }
.pi-cur-line::before,.pi-cur-line::after { content:''; flex:1; height:1px; background:var(--gold); opacity:.5; }
.pi-cur-tag { font-family:'Space Mono',monospace; font-size:10px; font-weight:700;
              color:var(--gold); white-space:nowrap; }
.pi-nearest-r td { font-weight:900 !important; }
.pi-nearest-r .pi-label { color:var(--red) !important; }
.pi-nearest-r .pi-price { color:var(--red) !important; }
.pi-nearest-s td { font-weight:900 !important; }
.pi-nearest-s .pi-label { color:var(--green) !important; }
.pi-nearest-s .pi-price { color:var(--green) !important; }
.pi-level-pdh { color:var(--green) !important; }
.pi-level-pdl { color:var(--red) !important; }
.pi-level-orb { color:var(--yellow) !important; }
.pi-range-wrap { margin-top:14px; }
.pi-range-track { position:relative; height:4px; background:var(--line); border-radius:2px; margin:5px 0 2px; }
.pi-range-fill { position:absolute; top:0; left:0; height:100%; border-radius:2px;
                 background:linear-gradient(90deg,var(--red),var(--yellow),var(--green)); opacity:.5; }
.pi-range-dot { position:absolute; top:-5px; width:13px; height:13px; border-radius:50%;
                transform:translateX(-50%); border:2px solid var(--panel); }

.signal-card { padding: 13px 16px; border-radius: 12px; border: 1px solid var(--line); background: var(--panel2); margin-bottom: 8px; transition: background .15s; }
.signal-card:last-child { margin-bottom: 0 }
.signal-card:hover { background: var(--panel) }
.signal-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }
.signal-ticker { font-family: 'Rajdhani', sans-serif; font-size: 20px; font-weight: 700; letter-spacing: 1px; }
.signal-verdict { font-family: 'Space Mono', monospace; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 6px; letter-spacing: 1px; }
.sv-TAKE    { background: var(--green2); color: var(--green); border: 1px solid rgba(30,110,65,.2) }
.sv-CAUTION { background: rgba(184,134,11,.08); color: var(--yellow); border: 1px solid rgba(184,134,11,.2) }
.sv-SKIP    { background: var(--red2); color: var(--red); border: 1px solid rgba(192,57,43,.2) }
.signal-meta { font-size: 11px; color: var(--muted2); margin-bottom: 4px }
.signal-summary { font-size: 12px; color: var(--muted); line-height: 1.5 }

.divergence-alert { padding: 12px 16px; border-radius: 12px; background: rgba(184,134,11,.06); border: 1px solid rgba(184,134,11,.18); display: flex; align-items: flex-start; gap: 12px; }
.divergence-icon { font-size: 18px; flex-shrink: 0; margin-top: 2px; }
.divergence-text { font-size: 13px; color: var(--yellow); line-height: 1.5; }

.harvey-top-grid { display: grid; grid-template-columns: 1.3fr .7fr; gap: 16px; align-items: start; }
.harvey-mid-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; align-items: start; }
.harvey-bot-grid { display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; align-items: start; }

/* ── RISK ENGINE PANEL ── */
.re-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.re-cell {
  padding: 14px 16px; border-radius: 14px;
  border: 1px solid var(--line); background: var(--panel2);
}
.re-cell.stop {
  border-color: rgba(192,57,43,.4);
  background: var(--red2);
  animation: strip-pulse-red 1.8s ease-in-out infinite;
}
.re-label {
  font-family: 'Space Mono', monospace; font-size: 9px;
  letter-spacing: 2px; color: var(--muted2); text-transform: uppercase; margin-bottom: 8px;
}
.re-value {
  font-family: 'Rajdhani', sans-serif; font-size: 22px; font-weight: 700; line-height: 1;
}
.re-note {
  margin-top: 6px; font-size: 11px; color: var(--muted); line-height: 1.4;
}
.re-valid   { color: var(--green) }
.re-invalid { color: var(--red) }
.re-warn    { color: var(--yellow) }
.re-ok      { color: var(--green) }
.re-stop-banner {
  display: none; padding: 14px 20px; border-radius: 14px;
  background: var(--red2); border: 2px solid rgba(192,57,43,.4);
  color: var(--red); font-family: 'Rajdhani', sans-serif;
  font-size: 20px; font-weight: 700; letter-spacing: 2px;
  text-align: center; margin-bottom: 0;
  animation: strip-pulse-red 1.8s ease-in-out infinite;
}
.re-stop-banner.active { display: block }
.re-calc-row {
  display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap;
}
.re-input {
  flex: 1; min-width: 90px; padding: 8px 12px; border-radius: 10px;
  border: 1px solid var(--line); background: var(--panel2);
  color: var(--text); font-family: 'Space Mono', monospace; font-size: 11px;
  outline: none; transition: border-color .15s;
}
.re-input:focus { border-color: var(--muted2) }
.re-calc-btn {
  padding: 8px 16px; border-radius: 10px; border: 1px solid rgba(30,110,65,.3);
  background: var(--green2); color: var(--green);
  font-family: 'Rajdhani', sans-serif; font-size: 14px; font-weight: 700;
  cursor: pointer; transition: border-color .15s; white-space: nowrap;
}
.re-calc-btn:hover { border-color: rgba(30,110,65,.5) }
.re-reset-btn {
  padding: 8px 16px; border-radius: 10px; border: 1px solid rgba(192,57,43,.25);
  background: var(--red2); color: var(--red);
  font-family: 'Rajdhani', sans-serif; font-size: 13px; font-weight: 700;
  cursor: pointer; transition: border-color .15s;
}
.re-reset-btn:hover { border-color: rgba(192,57,43,.4) }
@media(max-width:1100px) {
  .re-grid { grid-template-columns: 1fr 1fr }
}

@media(max-width:1100px) {
  .harvey-top-grid, .harvey-mid-grid, .harvey-bot-grid, .verdict-grid { grid-template-columns: 1fr }
}

/* ── NEW HARVEY LAYOUT ── */
.hv-layout { display: grid; grid-template-columns: 1fr 320px; gap: 16px; align-items: start; }
.hv-left, .hv-right { display: flex; flex-direction: column; gap: 14px; }

.hv-verdict-card { border-radius: var(--radius); padding: 24px 26px; border: 1px solid var(--line); background: var(--panel); position: relative; overflow: hidden; }
.hv-verdict-card.green  { border-color: rgba(30,110,65,.3);   background: var(--green2); }
.hv-verdict-card.red    { border-color: rgba(192,57,43,.3);   background: var(--red2); }
.hv-verdict-card.yellow { border-color: rgba(184,134,11,.25); background: rgba(184,134,11,.05); }

.hv-gauge-wrap { margin-top: 14px; }
.hv-gauge-track { width: 100%; height: 10px; background: var(--panel2); border-radius: 999px; overflow: hidden; border: 1px solid var(--line); }
.hv-gauge-fill { height: 100%; border-radius: 999px; transition: width .6s ease, background .6s ease; }

.hv-price-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.hv-price-card { padding: 18px 20px; border-radius: var(--radius); border: 1px solid var(--line); background: var(--panel); }

.hv-intel-grid { display: grid; gap: 6px; margin-top: 4px; }
.hv-intel-row { display: grid; grid-template-columns: 90px 1fr; gap: 8px; align-items: baseline; }
.hv-intel-label { font-family: "Space Mono", monospace; font-size: 9px; letter-spacing: 1.5px; color: var(--muted2); text-transform: uppercase; padding-top: 2px; }
.hv-intel-val { font-size: 12px; color: var(--text); line-height: 1.5; }
.hv-intel-val.bull { color: var(--green); }
.hv-intel-val.bear { color: var(--red); }
.hv-intel-val.warn { color: var(--yellow); }

.hv-playbook { padding: 18px 20px; border-radius: var(--radius); border: 1px solid rgba(184,134,11,.25); border-left: 3px solid var(--yellow); background: rgba(184,134,11,.04); }
.hv-playbook ul { margin: 8px 0 0; padding-left: 18px; }
.hv-playbook li { font-size: 13px; color: var(--muted); line-height: 1.65; margin-bottom: 4px; }
.hv-playbook li:last-child { margin-bottom: 0; }

.hv-stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.hv-stat-cell { padding: 12px 14px; border-radius: 10px; border: 1px solid var(--line); background: var(--panel2); }
.hv-stat-label { font-family: 'Space Mono', monospace; font-size: 9px; letter-spacing: 1.5px; color: var(--muted2); text-transform: uppercase; margin-bottom: 6px; }
.hv-stat-value { font-family: 'Rajdhani', sans-serif; font-size: 17px; font-weight: 700; line-height: 1.2; }

.hv-orb-badge { font-family: 'Space Mono', monospace; font-size: 9px; letter-spacing: 1.5px; color: var(--yellow); text-transform: uppercase; background: rgba(184,134,11,.08); border: 1px solid rgba(184,134,11,.2); border-radius: 4px; padding: 2px 8px; display: inline-block; margin-bottom: 10px; }

.hv-sector-row { display: flex; align-items: center; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid var(--line); }
.hv-sector-row:last-child { border-bottom: none; }
.hv-sector-name { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .5px; }
.hv-sector-pct  { font-family: 'Space Mono', monospace; font-size: 12px; font-weight: 700; }

.hv-donna-says { padding: 16px 18px; border-radius: var(--radius); border: 1px solid rgba(0,229,160,.12); background: rgba(0,229,160,.04); font-size: 13px; color: var(--muted); line-height: 1.65; font-style: italic; }
.hv-donna-says-label { font-family: 'Space Mono', monospace; font-size: 9px; letter-spacing: 2px; color: var(--green); text-transform: uppercase; font-style: normal; display: block; margin-bottom: 8px; }

@media(max-width:1100px) {
  .hv-layout, .hv-price-row { grid-template-columns: 1fr; }
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

/* ── SSE signal dot on nav button ── */
.signal-dot {
  position: absolute;
  top: 6px; right: 6px;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--green);
  display: none;
}
.signal-dot.active { display: block; animation: dot-pulse 1.2s ease-in-out 3 forwards }
@keyframes dot-pulse {
  0%,100% { opacity: 1; transform: scale(1) }
  50%      { opacity: .4; transform: scale(1.6) }
}

/* ── verdict banner flash on new signal ── */
@keyframes donnaFadeIn { from { opacity: 0 } to { opacity: 1 } }
body.donna-first-load { animation: donnaFadeIn .3s ease-out both; }
@keyframes banner-flash {
  0%   { box-shadow: 0 0 0 0 rgba(30,110,65,.4) }
  50%  { box-shadow: 0 0 0 14px rgba(30,110,65,0) }
  100% { box-shadow: 0 0 0 0 rgba(30,110,65,0) }
}
.verdict-banner.flash { animation: banner-flash .7s ease-out }
.db-market-tile{padding:14px 16px;text-align:center}
.db-tile-sym{font-size:9px;font-family:Space Mono,monospace;letter-spacing:1.5px;color:var(--muted2);margin-bottom:5px}
.db-tile-val{font-size:22px;font-weight:700;font-family:Rajdhani,sans-serif;line-height:1}
.db-tile-pct{font-size:11px;font-family:Space Mono,monospace;margin-top:3px}
.db-hero-left{flex:1}
.db-hero-right{text-align:right;min-width:220px}
.db-exec-badge{font-size:20px;font-weight:700;font-family:Rajdhani,sans-serif;letter-spacing:1px}
.db-posture-badge{display:inline-block;padding:3px 10px;border-radius:4px;font-family:Space Mono,monospace;font-size:10px;font-weight:700;margin-top:6px}
.db-badge-card{padding:14px 16px}
.db-badge-label{font-size:9px;font-family:Space Mono,monospace;letter-spacing:1.2px;color:var(--muted2);margin-bottom:6px}
.db-badge-value{font-size:16px;font-weight:700;font-family:Rajdhani,sans-serif}
/* ── NOVA REPLAY TAB ── */
.rp-card{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:16px}
.rp-section-lbl{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:2px;color:var(--gold);text-transform:uppercase;margin-bottom:8px;border-bottom:1px solid rgba(184,134,11,.18);padding-bottom:4px}
.rp-concl{font-family:'Space Mono',monospace;font-size:9px;font-weight:700;letter-spacing:1px;padding:3px 9px;border-radius:5px;display:inline-block}
.rp-concl-good{color:var(--green);background:rgba(74,222,128,.08);border:1px solid rgba(74,222,128,.3)}
.rp-concl-bad{color:var(--yellow);background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.3)}
.rp-concl-skip{color:var(--blue);background:rgba(96,165,250,.08);border:1px solid rgba(96,165,250,.3)}
.rp-concl-missed{color:var(--red);background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.3)}
.rp-concl-insuf{color:var(--muted2);background:rgba(100,116,139,.06);border:1px solid var(--line)}
.rp-field{display:flex;flex-direction:column;gap:2px;min-width:70px}
.rp-field-lab{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1px;color:var(--muted2);text-transform:uppercase}
.rp-field-val{font-size:13px;font-weight:600;color:var(--text);font-family:'Rajdhani',sans-serif}
.rp-lesson{background:rgba(184,134,11,.04);border:1px solid rgba(184,134,11,.12);border-radius:8px;padding:10px 14px;font-size:12px;color:var(--muted);font-style:italic;line-height:1.6;margin-top:8px}
.rp-tbl{width:100%;border-collapse:collapse}
.rp-tbl th{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1px;text-transform:uppercase;color:var(--muted2);padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
.rp-tbl td{padding:8px 10px;border-bottom:1px solid rgba(100,116,139,.1);vertical-align:middle;font-family:'Space Mono',monospace;font-size:10px;color:var(--text)}
.rp-tbl tr:last-child td{border-bottom:none}
.rp-tbl tr:hover td{background:rgba(100,116,139,.04)}
.rp-sim-card{border:1px solid var(--line);border-radius:10px;padding:11px 14px;margin-bottom:8px;background:var(--panel2)}
.rp-badge{font-family:'Space Mono',monospace;font-size:8px;letter-spacing:.8px;padding:2px 7px;border-radius:4px;border:1px solid var(--line);color:var(--muted2);display:inline-block;margin-right:3px;margin-bottom:2px}
.rp-select{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:.8px;padding:5px 8px;background:var(--panel2);border:1px solid var(--line);border-radius:6px;color:var(--muted2);cursor:pointer;min-width:120px}
.rp-btn{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;padding:5px 12px;border:1px solid var(--line);border-radius:6px;background:none;color:var(--muted2);cursor:pointer;text-transform:uppercase}
.rp-btn:hover{color:var(--text);border-color:var(--muted2)}
.rp-empty{text-align:center;padding:32px;color:var(--muted2);font-size:13px}
'''
