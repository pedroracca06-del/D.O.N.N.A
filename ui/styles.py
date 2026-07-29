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


/* ── FOOTER ── */
.footer{
  margin-top:24px;display:flex;justify-content:space-between;
  gap:12px;flex-wrap:wrap;
  font-family:'Space Mono',monospace;font-size:10px;color:var(--muted2);
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

/* ── RESPONSIVE ── */
@media(max-width:1200px){
  .main-grid,.stat-grid{grid-template-columns:1fr 1fr}
  .stat-grid{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:760px){
  body{padding:12px}
  .brand h1{font-size:32px}
  .main-grid,.stat-grid,.live-strip-row{grid-template-columns:1fr}
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
.db-market-tile{padding:14px 16px;text-align:center}
.db-tile-sym{font-size:9px;font-family:Space Mono,monospace;letter-spacing:1.5px;color:var(--muted2);margin-bottom:5px}
.db-tile-val{font-size:22px;font-weight:700;font-family:Rajdhani,sans-serif;line-height:1}
.db-tile-pct{font-size:11px;font-family:Space Mono,monospace;margin-top:3px}
.db-hero-left{flex:1}
.db-hero-right{text-align:right;min-width:220px}
.db-posture-badge{display:inline-block;padding:3px 10px;border-radius:4px;font-family:Space Mono,monospace;font-size:10px;font-weight:700;margin-top:6px}
.db-badge-card{padding:14px 16px}
.db-badge-label{font-size:9px;font-family:Space Mono,monospace;letter-spacing:1.2px;color:var(--muted2);margin-bottom:6px}
.db-badge-value{font-size:16px;font-weight:700;font-family:Rajdhani,sans-serif}
'''
