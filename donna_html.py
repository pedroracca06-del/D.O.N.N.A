"""donna_html.py — DASHBOARD_HTML template."""
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>D.O.N.N.A v5.0</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600;700;900&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
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

/* ── GROK INTELLIGENCE ── */
.grok-card{
  padding:22px 26px 20px;border-radius:18px;
  border:1px solid var(--line);background:var(--panel);
  box-shadow:var(--shadow2);position:relative;overflow:hidden;
  min-height:120px;
}
#hvPlaybook{min-height:80px}
#hvSignals{min-height:80px}
#newsList{min-height:120px}
#hvSectors{min-height:80px}
#caDivergenceList{min-height:60px}
.grok-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,var(--green),var(--gold));
  border-radius:18px 18px 0 0;
}
.grok-card-header{display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.grok-pulse-dot{
  width:8px;height:8px;border-radius:50%;background:var(--green);
  animation:pulse 2s ease-in-out infinite;flex-shrink:0;
}
.grok-card-title{
  font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;letter-spacing:.5px;
  color:var(--text);flex:1;
}
.grok-powered-badge{
  font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1px;text-transform:uppercase;
  padding:3px 9px;border-radius:5px;
  background:var(--panel2);color:var(--muted2);border:1px solid var(--line);
}
.grok-sentiment-badge{
  display:inline-flex;align-items:center;
  padding:4px 12px;border-radius:8px;
  font-family:'Space Mono',monospace;font-size:9px;font-weight:700;
  letter-spacing:1.5px;text-transform:uppercase;
}
.grok-sentiment-badge.sentiment-BULLISH{background:var(--green2);color:var(--green);border:1px solid rgba(30,110,65,.25)}
.grok-sentiment-badge.sentiment-BEARISH{background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.25)}
.grok-sentiment-badge.sentiment-NEUTRAL{background:var(--panel2);color:var(--muted2);border:1px solid var(--line)}
.grok-sentiment-badge.sentiment-MIXED{background:rgba(184,134,11,.08);color:var(--yellow);border:1px solid rgba(184,134,11,.25)}
.grok-headline{
  font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;
  line-height:1.15;letter-spacing:.3px;margin-bottom:10px;color:var(--text);
}
.grok-summary{font-size:13px;color:var(--muted);line-height:1.65;margin-bottom:10px}
.grok-sentiment-reason{font-size:12px;color:var(--muted2);line-height:1.5;font-style:italic;margin-bottom:14px}
.grok-trade-read{
  padding:13px 16px 13px 18px;
  border-radius:0 10px 10px 0;
  background:var(--panel2);
  border-top:1px solid var(--line);border-right:1px solid var(--line);border-bottom:1px solid var(--line);
  border-left:3px solid var(--gold);
  font-size:13px;color:var(--text);line-height:1.7;margin-bottom:16px;font-weight:500;
}
.grok-names-row{display:flex;flex-wrap:wrap;gap:7px}
.grok-name-chip{
  display:inline-block;padding:5px 14px;border-radius:999px;
  background:var(--panel2);border:1px solid var(--line);
  font-family:'Rajdhani',sans-serif;font-size:13px;font-weight:700;
  color:var(--text);cursor:pointer;transition:all .15s;letter-spacing:.3px;
  text-decoration:none;
}
.grok-name-chip:hover{background:var(--bg2);border-color:var(--muted);color:var(--text);text-decoration:none}
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

/* ── ECON CALENDAR ── */
.econ-day-header{
  font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;
  padding:6px 0 4px;margin-top:6px;border-bottom:1px solid var(--line);margin-bottom:4px;
}
.econ-day-header.today{color:var(--text);font-weight:700}
.econ-day-header.other{color:var(--muted2)}
.econ-day-header:first-child{margin-top:0}
.econ-event{display:flex;align-items:flex-start;gap:7px;padding:6px 0;border-bottom:1px solid var(--line2)}
.econ-event:last-child{border-bottom:none}
.econ-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;margin-top:4px}
.econ-dot.high{background:#f87171}.econ-dot.medium{background:#fbbf24}.econ-dot.low{background:#facc15}
.econ-time{font-family:'Space Mono',monospace;font-size:8px;color:var(--muted2);flex-shrink:0;width:34px;padding-top:2px}
.econ-body{flex:1;min-width:0}
.econ-title-row{display:flex;align-items:baseline;gap:6px;flex-wrap:wrap}
.econ-title{font-size:11px;color:var(--text);font-weight:600;line-height:1.35}
.econ-date-muted{font-size:9px;color:var(--muted2);font-family:'Space Mono',monospace;white-space:nowrap}
.econ-meta{font-size:9px;color:var(--muted2);margin-top:3px;font-family:'Space Mono',monospace;line-height:1.5}
.econ-verdict{
  display:inline-block;margin-left:4px;padding:1px 6px;border-radius:4px;
  font-family:'Space Mono',monospace;font-size:8px;font-weight:700;letter-spacing:.5px;vertical-align:middle;
}
.econ-verdict.hot{background:#7f1d1d;color:#fca5a5}
.econ-verdict.inline{background:#374151;color:#9ca3af}
.econ-verdict.miss{background:#14532d;color:#86efac}
.econ-no-events{font-size:12px;color:var(--muted2);padding:4px 0}
.econ-sub{display:flex;align-items:center;gap:5px;margin-top:3px;flex-wrap:wrap}
.econ-vals{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2)}

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

/* ── SCENARIO ENGINE ── */
.scenario-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-top:16px}
.scenario-card{
  padding:20px 22px;border-radius:16px;
  border:1px solid var(--line);
  background:var(--panel);
  position:relative;overflow:hidden;
  transition:border-color .15s;
}
.scenario-card:hover{border-color:var(--muted2)}
.scenario-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:16px 16px 0 0;
}
.scenario-card.conf-HIGH::before{background:var(--green)}
.scenario-card.conf-MEDIUM::before{background:var(--yellow)}
.scenario-card.conf-LOW::before{background:var(--line)}
.sc-trigger{
  font-family:'Rajdhani',sans-serif;font-size:17px;font-weight:700;
  color:var(--yellow);line-height:1.3;margin-bottom:10px;
}
.sc-reaction{font-size:13px;color:var(--text);line-height:1.6;margin-bottom:10px}
.sc-levels{
  font-family:'Space Mono',monospace;font-size:11px;
  color:var(--blue);letter-spacing:.5px;margin-bottom:10px;
  padding:8px 10px;border-radius:8px;background:rgba(37,99,235,.05);
  border:1px solid rgba(37,99,235,.1);
}
.sc-watch{font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:12px}
.sc-conf{
  display:inline-flex;align-items:center;gap:6px;
  font-family:'Space Mono',monospace;font-size:10px;font-weight:700;
  letter-spacing:1px;padding:4px 10px;border-radius:6px;
}
.sc-conf.HIGH{background:var(--green2);color:var(--green);border:1px solid rgba(30,110,65,.2)}
.sc-conf.MEDIUM{background:rgba(184,134,11,.08);color:var(--yellow);border:1px solid rgba(184,134,11,.2)}
.sc-conf.LOW{background:var(--panel2);color:var(--muted);border:1px solid var(--line)}
.sc-conf-dot{width:6px;height:6px;border-radius:50%;background:currentColor}
.scenario-header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px}
.scenario-meta{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2);letter-spacing:1px}
.gen-btn{
  padding:8px 16px;border-radius:8px;border:1px solid var(--line);
  background:var(--panel2);color:var(--text);
  cursor:pointer;font-family:'Rajdhani',sans-serif;font-size:13px;font-weight:700;
  letter-spacing:1px;transition:border-color .15s;white-space:nowrap;
}
.gen-btn:hover{border-color:var(--muted2)}
.gen-btn:disabled{opacity:.5;cursor:not-allowed}
@keyframes spin{to{transform:rotate(360deg)}}
.gen-btn.loading::after{content:' ⟳';display:inline-block;animation:spin .7s linear infinite}
@media(max-width:900px){.scenario-grid{grid-template-columns:1fr}}

/* ── JOURNAL TAB ── */
.journal-btn {
  background:var(--panel) !important;
  border-color:rgba(184,134,11,.3) !important;
  color:var(--gold) !important;
}
.journal-btn.active {
  background:var(--text) !important;
  border-color:var(--text) !important;color:var(--panel) !important;
}
.journal-stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.journal-stat{text-align:center;padding:18px 14px}
.journal-stat .js-lab{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:10px}
.journal-stat .js-val{font-family:'Rajdhani',sans-serif;font-size:28px;font-weight:700;letter-spacing:1px;line-height:1}
.journal-stat .js-sub{margin-top:6px;font-size:11px;color:var(--muted2)}
.trade-label{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px;display:block}
.trade-input,.trade-select{
  width:100%;padding:10px 12px;border-radius:10px;
  border:1px solid var(--line);background:var(--panel2);
  color:var(--text);font-family:system-ui,-apple-system,sans-serif;font-size:13px;
  outline:none;transition:border-color .15s;
}
.trade-input:focus,.trade-select:focus{border-color:var(--muted2)}
.trade-select option{background:var(--panel);color:var(--text)}
.submit-trade-btn{
  width:100%;padding:13px;border-radius:10px;border:1px solid var(--text);cursor:pointer;
  background:var(--text);
  color:var(--panel);font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;
  letter-spacing:1px;transition:opacity .15s;margin-top:4px;
}
.submit-trade-btn:hover{opacity:.82}
.submit-trade-btn:disabled{opacity:.4;cursor:not-allowed}
.outcome-WIN{color:var(--green)}.outcome-LOSS{color:var(--red)}.outcome-BREAKEVEN{color:var(--yellow)}
.j-date-header{background:rgba(240,180,41,.06);border-bottom:1px solid rgba(240,180,41,.12)}
.j-date-header td{padding:7px 14px;font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1.5px;color:var(--gold);text-transform:uppercase;font-weight:700}
.j-filter-bar{display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.j-filter-btn{padding:5px 14px;border-radius:8px;border:1px solid var(--line);background:var(--panel2);color:var(--muted2);font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1px;cursor:pointer;transition:all .15s;text-transform:uppercase}
.j-filter-btn:hover{border-color:rgba(184,134,11,.3);color:var(--gold)}
.j-filter-btn.active{background:rgba(184,134,11,.08);border-color:rgba(184,134,11,.3);color:var(--gold)}
.regime-breakdown-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-top:12px}
.regime-card{padding:14px 16px;border-radius:12px;border:1px solid var(--line);background:var(--panel2)}
.regime-card .rc-name{font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;margin-bottom:8px}
.regime-card .rc-wr{font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;line-height:1}
.regime-card .rc-sub{font-size:11px;color:var(--muted2);margin-top:4px}
@media(max-width:900px){.journal-stats-grid{grid-template-columns:1fr 1fr}}
@media(max-width:540px){.journal-stats-grid{grid-template-columns:1fr}}

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
</style>
</head>
<body>
<div class="wrap">

  <!-- TOPBAR -->
  <div class="topbar">
    <div class="brand">
      <h1>D.O.N.N.A</h1>
      <span class="brand-tag">v5.0 // LIVE MARKET CORE</span>
    </div>
    <div class="top-right">
      <div class="nav">
        <button class="tab-btn active" data-page="dashboard">Dashboard</button>
        <button class="tab-btn" data-page="news">News</button>
        <button class="tab-btn" data-page="assistant">Assistant</button>
        <button class="tab-btn harvey-btn" data-page="harvey">H.A.R.V.E.Y<span class="signal-dot" id="harveySignalDot"></span></button>
        <button class="tab-btn journal-btn" data-page="journal">Journal</button>
      </div>
      <div class="status-badge"><span class="dot"></span>ONLINE</div>
    </div>
  </div>

  <!-- LIVE STRIP -->
  <div class="live-strip-row">
    <div class="live-label">⬤ LIVE INTELLIGENCE</div>
    <div class="ticker-wrap">
      <div class="ticker-track" id="liveStrip">Loading...</div>
    </div>
    <div class="session-chip">
      <div class="lab">Current Session</div>
      <div class="val" id="sessionVal">—</div>
    </div>
  </div>

  <!-- ════════════════════ DASHBOARD ════════════════════ -->
  <div class="page active" id="page-dashboard">
    <div style="display:grid;grid-template-columns:1fr 300px;gap:16px;align-items:start">

      <!-- ── LEFT MAIN COLUMN ── -->
      <div class="vstack">

        <!-- 1. HERO MARKET BANNER -->
        <div id="dbHero" class="card" style="padding:22px 26px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:20px">
            <div class="db-hero-left">
              <div id="dbRegimeText" style="font-size:32px;font-weight:700;font-family:Rajdhani,sans-serif;letter-spacing:.5px;color:var(--muted)">—</div>
              <div id="dbMarketTone" style="margin-top:5px;font-size:13px;color:var(--muted);line-height:1.4">—</div>
              <div id="dbSessionLabel" style="margin-top:12px;font-size:11px;color:var(--muted2);font-family:Space Mono,monospace">—</div>
            </div>
            <div class="db-hero-right">
              <div id="dbExecBadge" class="db-exec-badge" style="color:var(--muted)">—</div>
              <div id="dbExecReason" style="margin-top:4px;font-size:11px;color:var(--muted2);line-height:1.4">—</div>
              <div id="dbMacroPosture" class="db-posture-badge">—</div>
            </div>
          </div>
        </div>

        <!-- 2. RISK BADGES ROW -->
        <div id="dbBadges" style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px">
          <div class="card db-badge-card">
            <div class="db-badge-label">EXECUTION</div>
            <div class="db-badge-value" id="dbBadgeExec" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-badge-card">
            <div class="db-badge-label">MACRO RISK</div>
            <div class="db-badge-value" id="dbBadgeMacro" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-badge-card">
            <div class="db-badge-label">RED FOLDER</div>
            <div class="db-badge-value" id="dbBadgeRedFolder" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-badge-card">
            <div class="db-badge-label">SESSION</div>
            <div class="db-badge-value" id="dbBadgeSession" style="color:var(--muted)">—</div>
          </div>
        </div>

        <!-- 3. MARKET DRIVER PANEL -->
        <div id="dbDriver" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">MARKET DRIVER</div>
            <div id="dbDriverPrimary" style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:5px;line-height:1.3">—</div>
            <div id="dbDriverRegime" style="font-size:11px;color:var(--muted2);margin-bottom:10px;font-family:Space Mono,monospace">—</div>
            <ul id="dbDriverBullets" style="margin:0;padding-left:16px;font-size:12px;color:var(--muted);line-height:1.7"></ul>
          </div>
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">PRIMARY CATALYST</div>
            <div id="dbCatalystHeadline" style="font-size:14px;font-weight:700;color:var(--text);line-height:1.3;margin-bottom:8px">—</div>
            <div id="dbCatalystSummary" style="font-size:12px;color:var(--muted);line-height:1.55;margin-bottom:10px">—</div>
            <div id="dbCatalystSentiment" style="display:inline-block;padding:3px 10px;border-radius:4px;font-family:Space Mono,monospace;font-size:10px;font-weight:700;background:var(--panel2);color:var(--muted2)">—</div>
          </div>
        </div>

        <!-- 4. EXECUTION MONITOR -->
        <div id="dbExecution" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="panel">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
              <div class="kicker" style="margin-bottom:0">EXECUTION MONITOR</div>
              <span id="execStatusPill" class="exec-status-pill exec-status-active">
                <span id="execStatusDot" class="exec-status-dot" style="background:var(--green)"></span>
                <span id="execStatusText">ACTIVE</span>
              </span>
            </div>
            <div id="execPnlBig" class="exec-pnl-big" style="margin-bottom:14px;color:var(--text)">—</div>
            <div class="exec-row">
              <span class="exec-row-label">Account Equity</span>
              <span class="exec-row-val" id="execEquity">—</span>
            </div>
            <div class="exec-row">
              <span class="exec-row-label">Trades Today</span>
              <span class="exec-row-val" id="execTrades">—</span>
            </div>
            <div class="exec-row">
              <span class="exec-row-label">Risk Used Today</span>
              <span class="exec-row-val" id="execRiskUsed">—</span>
            </div>
            <div class="exec-row">
              <span class="exec-row-label">Red Folder In</span>
              <span class="exec-row-val" id="execRedFolder">—</span>
            </div>
            <div class="exec-row" style="align-items:flex-start;padding-top:10px;border-bottom:none">
              <span class="exec-row-label">Last Signal</span>
              <div id="execLastSignal" class="exec-row-val">—</div>
            </div>
          </div>
          <div class="panel">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
              <div class="kicker" style="margin-bottom:0">SESSION SCORECARD</div>
              <span id="donnaGrade" class="donna-grade-big" style="color:var(--muted2)">—</span>
            </div>
            <div id="scorecardPnlBig" class="exec-pnl-big" style="margin-bottom:10px;color:var(--text)">—</div>
            <div class="sc-cells">
              <div class="sc-cell"><div class="sc-cell-num up" id="scWins">0</div><div class="sc-cell-lab">Wins</div></div>
              <div class="sc-cell"><div class="sc-cell-num dn" id="scLosses">0</div><div class="sc-cell-lab">Losses</div></div>
              <div class="sc-cell"><div class="sc-cell-num" id="scBe" style="color:var(--muted)">0</div><div class="sc-cell-lab">B/E</div></div>
            </div>
            <div class="exec-row">
              <span class="exec-row-label">Win Rate</span>
              <span class="exec-row-val" id="scWinRate">—</span>
            </div>
            <div class="exec-row">
              <span class="exec-row-label">Best Trade</span>
              <span class="exec-row-val up" id="scBest">—</span>
            </div>
            <div class="exec-row" style="border-bottom:none">
              <span class="exec-row-label">Worst Trade</span>
              <span class="exec-row-val dn" id="scWorst">—</span>
            </div>
          </div>
        </div>

        <!-- 5. MARKET BOARD -->
        <div id="dbMarketBoard" style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px">
          <div class="card db-market-tile" data-sym="NQ">
            <div class="db-tile-sym">NQ</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-market-tile" data-sym="ES">
            <div class="db-tile-sym">ES</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-market-tile" data-sym="VIX">
            <div class="db-tile-sym">VIX</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-market-tile" data-sym="DXY">
            <div class="db-tile-sym">DXY</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
          <div class="card db-market-tile" data-sym="GOLD">
            <div class="db-tile-sym">GOLD</div>
            <div class="db-tile-val" style="color:var(--text)">—</div>
            <div class="db-tile-pct" style="color:var(--muted)">—</div>
          </div>
        </div>

      </div><!-- end left column -->

      <!-- ── RIGHT SIDEBAR ── -->
      <div class="vstack">

        <!-- HARVEY SNAPSHOT -->
        <div id="dbHarveySnap" class="panel">
          <div class="kicker" style="margin-bottom:10px">HARVEY SNAPSHOT</div>
          <div id="dbHvVerdict" style="font-size:30px;font-weight:700;font-family:Rajdhani,sans-serif;letter-spacing:.5px;color:var(--yellow);margin-bottom:6px">—</div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px">
            <span id="dbHvConfidence" style="font-family:Space Mono,monospace;font-size:10px;color:var(--muted2)">—</span>
            <span id="dbHvRegime" style="padding:2px 8px;border-radius:4px;font-family:Space Mono,monospace;font-size:9px;background:var(--panel2);color:var(--muted2)">—</span>
          </div>
          <div class="exec-row">
            <span class="exec-row-label">Bias Score</span>
            <span class="exec-row-val" id="dbHvBias">—</span>
          </div>
          <div class="exec-row" style="border-bottom:none">
            <span class="exec-row-label">Last Signal</span>
            <span class="exec-row-val" id="dbHvLastSig">—</span>
          </div>
        </div>

        <!-- ECONOMIC CALENDAR -->
        <div id="dbCalendar" class="panel">
          <div class="kicker" style="margin-bottom:10px">ECONOMIC CALENDAR</div>
          <div id="sidebarEconCalendar"></div>
        </div>

        <!-- DONNA SAYS -->
        <div id="dbDonnaSays" class="panel">
          <div class="kicker" style="margin-bottom:8px">DONNA SAYS</div>
          <div id="dbDonnaSaysText" style="font-size:13px;color:var(--text);line-height:1.65">—</div>
        </div>

      </div><!-- end sidebar -->

    </div>
  </div>

  <!-- ════════════════════ NEWS ════════════════════ -->
  <div class="page" id="page-news">
    <div class="vstack">

      <!-- LIVE FUTURES TICKER STRIP -->
      <div class="news-futures-strip">
        <div class="news-futures-label">Live</div>
        <div class="news-futures-track-wrap">
          <div class="news-futures-track" id="newsFuturesTrack">
            <span class="nf-item"><span class="nf-sym">NQ</span><span class="nf-val">—</span><span class="nf-pct">—</span></span>
          </div>
        </div>
      </div>

      <!-- BREAKING NEWS BAR -->
      <div class="breaking-bar">
        <div class="breaking-label">Breaking</div>
        <div class="breaking-ticker-wrap">
          <div class="breaking-ticker-track" id="breakingTickerTrack">
            <span class="breaking-item">Loading live headlines...</span>
          </div>
        </div>
      </div>

      <!-- 5 INDEX TILES (customizable) -->
      <div class="index-tiles" id="indexTiles">
        <div class="index-tile"><button class="tile-edit-btn" title="Change symbol">✎</button><div class="index-tile-name">NQ</div><div class="index-tile-val">—</div><div class="index-tile-chg">—</div></div>
        <div class="index-tile"><button class="tile-edit-btn" title="Change symbol">✎</button><div class="index-tile-name">ES</div><div class="index-tile-val">—</div><div class="index-tile-chg">—</div></div>
        <div class="index-tile"><button class="tile-edit-btn" title="Change symbol">✎</button><div class="index-tile-name">VIX</div><div class="index-tile-val">—</div><div class="index-tile-chg">—</div></div>
        <div class="index-tile"><button class="tile-edit-btn" title="Change symbol">✎</button><div class="index-tile-name">DXY</div><div class="index-tile-val">—</div><div class="index-tile-chg">—</div></div>
        <div class="index-tile"><button class="tile-edit-btn" title="Change symbol">✎</button><div class="index-tile-name">GOLD</div><div class="index-tile-val">—</div><div class="index-tile-chg">—</div></div>
      </div>

      <!-- MAIN 2-COLUMN GRID: 70% left / 30% right -->
      <div class="news-layout">

        <!-- ─── LEFT COLUMN ─── -->
        <div class="vstack" style="gap:14px">

          <!-- 1. DONNA'S MARKET READ -->
          <div class="grok-card">
            <div class="grok-card-header">
              <div class="grok-pulse-dot"></div>
              <div class="grok-card-title">DONNA&#39;s Market Read</div>
              <div class="grok-powered-badge">Powered by Grok</div>
              <div id="grokSentimentBadge" class="grok-sentiment-badge sentiment-NEUTRAL">NEUTRAL</div>
            </div>
            <div class="grok-headline" id="grokTopStory">Fetching latest market intelligence from Grok...</div>
            <div class="grok-summary" id="grokSummary" style="min-height:18px"></div>
            <div class="grok-sentiment-reason" id="grokSentimentReason" style="min-height:14px"></div>
            <div class="grok-trade-read" id="grokTradeRead" style="min-height:18px"></div>
            <div class="grok-names-row" id="grokKeyNames"></div>
          </div>

          <!-- 2. LIVE FEED -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:12px">Live Feed</div>
            <div id="newsList"><div class="obs-item low"><div class="obs-body">Loading headlines...</div></div></div>
          </div>

        </div>

        <!-- ─── RIGHT SIDEBAR 30% ─── -->
        <div class="vstack" style="gap:14px">

          <!-- 1. X SENTIMENT -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">X Sentiment</div>
            <div id="sidebarGrokSentiment" style="margin-bottom:6px">—</div>
            <div class="donna-read" id="donnaRead">—</div>
            <div class="grok-names-row" style="margin-top:10px" id="sidebarGrokChips"></div>
          </div>

          <!-- 2. RISK LEVELS -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">Risk Levels</div>
            <div class="risk-level-row">
              <span class="risk-level-label">Macro</span>
              <span id="sidebarMacroRisk" class="risk-badge risk-medium">MEDIUM</span>
            </div>
            <div class="risk-level-row">
              <span class="risk-level-label">Headline</span>
              <span id="sidebarHeadlineRisk" class="risk-badge risk-medium">MEDIUM</span>
            </div>
            <div class="risk-level-row">
              <span class="risk-level-label">Market</span>
              <span id="sidebarMarketRisk" class="risk-badge risk-medium">MEDIUM</span>
            </div>
            <div class="risk-level-row" style="border-bottom:none">
              <span class="risk-level-label">Event Phase</span>
              <span id="sidebarEventPhase" style="font-family:'Rajdhani',sans-serif;font-size:14px;font-weight:700;color:var(--yellow)">—</span>
            </div>
            <div id="sidebarNextEvent" style="font-size:11px;color:var(--muted);margin-top:6px;padding-top:6px;border-top:1px solid var(--line2)">—</div>
          </div>

          <!-- 3. ECONOMIC CALENDAR -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">Economic Calendar</div>
            <div id="sidebarEconCalendar"><div class="econ-no-events">Loading events...</div></div>
          </div>

          <!-- 4. TRENDING MOVERS (compact vertical list) -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">Trending Movers</div>
            <div class="movers-col-title gainers" style="margin-bottom:6px">▲ Gainers</div>
            <div id="moversGainers"><div class="mover-row"><span class="mover-sym" style="color:var(--muted2)">Loading...</span></div></div>
            <div style="border-top:1px solid var(--line);margin:10px 0"></div>
            <div class="movers-col-title losers" style="margin-bottom:6px">▼ Losers</div>
            <div id="moversLosers"><div class="mover-row"><span class="mover-sym" style="color:var(--muted2)">Loading...</span></div></div>
          </div>

          <!-- 5. DONNA SAYS -->
          <div class="donna-says-box">
            <div class="donna-says-label">DONNA Says</div>
            <div class="donna-says-text" id="donnaSaysText">Monitoring market conditions...</div>
          </div>

        </div>

      </div>

    </div>
  </div>

  <!-- ════════════════════ ASSISTANT ════════════════════ -->
  <div class="page" id="page-assistant">
    <div class="vstack">

      <!-- COMMAND INTERFACE PANEL -->
      <div class="panel" style="padding:0;overflow:hidden">

        <!-- DONNA HEADER -->
        <div class="donna-header">
          <div class="donna-logo">D.O.N.N.A</div>
          <div class="donna-online-row">
            <div class="donna-online-dot"></div>
            <span class="donna-online-text">Online</span>
          </div>
          <div class="donna-tagline">Dynamic Operations &amp; Neural Network Assistant · Command Interface v5</div>
        </div>

        <!-- CHAT AREA -->
        <div style="padding:16px">
          <div class="chat-terminal" id="assistantOutput">
            <div class="msg assistant">
              <span class="role">DONNA</span>
              Command interface ready. I am monitoring macro conditions, market structure, and risk levels. Ask me anything or use a quick command below.
              <div><span class="msg-tag ANALYSIS">ANALYSIS</span></div>
            </div>
            <div class="msg-clearfix"></div>
          </div>
          <div class="typing-indicator" id="typingIndicator">
            <span class="typing-dots"><span></span><span></span><span></span></span>&nbsp;&nbsp;DONNA is thinking...
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

  <!-- ════════════════════ H.A.R.V.E.Y ════════════════════ -->
  <div class="page" id="page-harvey">
    <div class="vstack">

      <!-- Execution status strip -->
      <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;padding:6px 0 2px">
        <div style="font-family:Space Mono,monospace;font-size:9px;letter-spacing:2px;color:var(--muted2);text-transform:uppercase">Bot</div>
        <div id="hvBotStatus" style="font-family:Rajdhani,sans-serif;font-size:15px;font-weight:700;color:var(--muted)">—</div>
        <div style="color:var(--line2)">·</div>
        <div style="font-family:Space Mono,monospace;font-size:9px;letter-spacing:2px;color:var(--muted2);text-transform:uppercase">Trades Left Today</div>
        <div id="hvTradesLeft" style="font-family:Rajdhani,sans-serif;font-size:15px;font-weight:700">—</div>
      </div>

      <div class="hv-layout">
        <!-- ── LEFT COLUMN ── -->
        <div class="hv-left">

          <!-- 1. VERDICT BANNER -->
          <div class="hv-verdict-card yellow" id="hvVerdictCard">
            <div class="verdict-label">H.A.R.V.E.Y // Execution Verdict</div>
            <div class="verdict-word" id="hvVerdictWord">—</div>
            <div class="verdict-reason" id="hvVerdictReason">Loading execution intelligence...</div>
            <div class="hv-gauge-wrap">
              <div style="display:flex;justify-content:space-between;font-family:Space Mono,monospace;font-size:9px;color:var(--muted2);letter-spacing:1px;margin-bottom:6px">
                <span style="color:var(--red)">SHORT</span>
                <span id="hvBiasScore">— / 100</span>
                <span style="color:var(--green)">LONG</span>
              </div>
              <div class="hv-gauge-track"><div class="hv-gauge-fill" id="hvGaugeFill" style="width:50%"></div></div>
            </div>
          </div>

          <!-- 2. NQ + ES PRICE CARDS -->
          <div class="hv-price-row">
            <div class="hv-price-card">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                <div class="kicker" style="margin-bottom:0;color:var(--green)">NQ Futures</div>
                <div style="font-family:Rajdhani,sans-serif;font-size:28px;font-weight:700" id="hvNqLast">—</div>
              </div>
              <div style="font-family:Space Mono,monospace;font-size:11px" id="hvNqChg">—</div>
              <div style="margin-top:8px;font-size:12px;color:var(--muted)" id="hvNqSummary">—</div>
            </div>
            <div class="hv-price-card">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                <div class="kicker" style="margin-bottom:0;color:var(--blue)">ES Futures</div>
                <div style="font-family:Rajdhani,sans-serif;font-size:28px;font-weight:700" id="hvEsLast">—</div>
              </div>
              <div style="font-family:Space Mono,monospace;font-size:11px" id="hvEsChg">—</div>
              <div style="margin-top:8px;font-size:12px;color:var(--muted)" id="hvEsSummary">—</div>
            </div>
          </div>

          <!-- 3. DONNA'S PLAYBOOK -->
          <div class="hv-playbook">
            <div class="kicker" style="margin-bottom:8px;color:var(--yellow)">Donna's Playbook</div>
            <ul id="hvPlaybook">
              <li>Loading playbook rules...</li>
            </ul>
          </div>

          <!-- 4. SIGNAL HISTORY (last 5 from /alerts-data) -->
          <div class="panel">
            <div class="kicker">TradingView Feed</div>
            <div class="section-title" style="margin-bottom:14px">Last 5 Signals</div>
            <div id="hvSignals">
              <div class="obs-item low"><div class="obs-body">No signals received yet. Connect your TradingView indicator to the webhook.</div></div>
            </div>
          </div>

        </div>

        <!-- ── RIGHT SIDEBAR ── -->
        <div class="hv-right">

          <!-- 1. SESSION STATS 2x2 -->
          <div class="panel">
            <div class="kicker">Context</div>
            <div class="section-title" style="margin-bottom:12px">Session Stats</div>
            <div class="hv-stats-grid">
              <div class="hv-stat-cell">
                <div class="hv-stat-label">Session</div>
                <div class="hv-stat-value" id="hvSession">—</div>
              </div>
              <div class="hv-stat-cell">
                <div class="hv-stat-label">Day</div>
                <div class="hv-stat-value" id="hvDay">—</div>
              </div>
              <div class="hv-stat-cell">
                <div class="hv-stat-label">Label</div>
                <div class="hv-stat-value" id="hvSessionLabel">—</div>
              </div>
              <div class="hv-stat-cell">
                <div class="hv-stat-label">Macro Risk</div>
                <div class="hv-stat-value" id="hvMacroRisk">—</div>
              </div>
            </div>
          </div>

          <!-- 2. ORB STATUS (ES ONLY) -->
          <div class="panel">
            <div class="hv-orb-badge">ES ONLY</div>
            <div class="kicker">Opening Range</div>
            <div class="section-title" style="margin-bottom:12px">ORB Status</div>
            <div class="orb-status-pill orb-PENDING" id="hvOrbPill">PENDING</div>
            <div class="orb-status-label" id="hvOrbStatus" style="margin-top:10px">—</div>
            <div class="orb-note" id="hvOrbNote">—</div>
          </div>

          <!-- 3. SECTOR BIAS (6 sectors from /sp500-heatmap) -->
          <div class="panel">
            <div class="kicker">Market Internals</div>
            <div class="section-title" style="margin-bottom:12px">Sector Bias</div>
            <div id="hvSectors"><div style="font-size:13px;color:var(--muted2)">Loading sectors...</div></div>
          </div>

          <!-- 4. DONNA SAYS -->
          <div class="hv-donna-says">
            <span class="hv-donna-says-label">Donna Says</span>
            <span id="hvDonnaSays">Loading...</span>
          </div>

        </div>
      </div>

      <!-- RISK ENGINE (preserved) -->
      <div class="panel">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:10px">
          <div>
            <div class="kicker" style="color:var(--red)">Layer 4 · Risk Management</div>
            <div class="section-title">Risk Engine</div>
          </div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <span style="font-family:Space Mono,monospace;font-size:10px;color:var(--muted2)">Acct $</span>
            <input class="re-input" id="reAccountSize" style="width:90px;flex:none" placeholder="25000" />
            <span style="font-family:Space Mono,monospace;font-size:10px;color:var(--muted2)">Risk %</span>
            <input class="re-input" id="reRiskPct" style="width:60px;flex:none" placeholder="1.0" />
            <button class="re-calc-btn" id="reSaveSettings">SAVE</button>
            <button class="re-reset-btn" id="reResetStop" title="Clear STOP flag">RESET STOP</button>
          </div>
        </div>
        <div class="re-stop-banner" id="reStopBanner">
          ⛔ STOP TRADING — Session risk limit reached. Clear flag to resume.
        </div>
        <div class="re-grid" id="reGrid" style="margin-top:14px">
          <div class="re-cell" id="rePosCell">
            <div class="re-label">Position Size</div>
            <div class="re-value" id="rePosValue">—</div>
            <div class="re-note" id="rePosNote">Enter entry &amp; stop below</div>
          </div>
          <div class="re-cell" id="reRRCell">
            <div class="re-label">R/R Ratio</div>
            <div class="re-value" id="reRRValue">—</div>
            <div class="re-note" id="reRRNote">Enter entry, stop &amp; target</div>
          </div>
          <div class="re-cell" id="reDDCell">
            <div class="re-label">Drawdown</div>
            <div class="re-value" id="reDDValue">—</div>
            <div class="re-note" id="reDDNote">—</div>
          </div>
          <div class="re-cell" id="reLossCell">
            <div class="re-label">Session Losses</div>
            <div class="re-value" id="reLossValue">—</div>
            <div class="re-note" id="reLossNote">—</div>
          </div>
        </div>
        <div class="re-calc-row">
          <input class="re-input" id="reEntry"  placeholder="Entry price"  type="number" step="any" />
          <input class="re-input" id="reStop"   placeholder="Stop price"   type="number" step="any" />
          <input class="re-input" id="reTarget" placeholder="Target price" type="number" step="any" />
          <select class="re-input" id="reDir" style="flex:none;width:90px">
            <option value="LONG">LONG</option>
            <option value="SHORT">SHORT</option>
          </select>
          <button class="re-calc-btn" id="reCalcBtn">CALCULATE</button>
        </div>
      </div>

    </div>
  </div>

  <!-- ════════════════════ JOURNAL ════════════════════ -->
  <div class="page" id="page-journal">
    <div class="vstack">

      <!-- HERO -->
      <div class="hero-banner" style="padding:20px 28px">
        <div class="hero-eyebrow">Edge Database</div>
        <div class="hero-title" style="font-size:28px;color:var(--gold)">Trade Journal</div>
        <div class="hero-sub" style="font-size:13px">Every trade logged builds DONNA\'s understanding of when you perform best. Tag, review, learn.</div>
      </div>

      <!-- DAILY P&L SUMMARY -->
      <div class="card" style="padding:14px 24px;display:flex;align-items:center;gap:28px;flex-wrap:wrap">
        <span style="font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;white-space:nowrap">Daily P&amp;L</span>
        <div style="display:flex;gap:36px;flex:1;flex-wrap:wrap">
          <div>
            <div style="font-size:9px;color:var(--muted2);letter-spacing:1px;text-transform:uppercase;margin-bottom:3px">Today</div>
            <div id="jPnlToday" style="font-family:\'Rajdhani\',sans-serif;font-size:24px;font-weight:700;line-height:1">—</div>
          </div>
          <div>
            <div style="font-size:9px;color:var(--muted2);letter-spacing:1px;text-transform:uppercase;margin-bottom:3px">Yesterday</div>
            <div id="jPnlYesterday" style="font-family:\'Rajdhani\',sans-serif;font-size:24px;font-weight:700;line-height:1">—</div>
          </div>
          <div>
            <div style="font-size:9px;color:var(--muted2);letter-spacing:1px;text-transform:uppercase;margin-bottom:3px">This Week</div>
            <div id="jPnlWeek" style="font-family:\'Rajdhani\',sans-serif;font-size:24px;font-weight:700;line-height:1">—</div>
          </div>
        </div>
      </div>

      <!-- STATS ROW -->
      <div class="journal-stats-grid">
        <div class="card journal-stat">
          <div class="js-lab">Total Trades</div>
          <div class="js-val" id="jTotalTrades">0</div>
          <div class="js-sub">All logged entries</div>
        </div>
        <div class="card journal-stat">
          <div class="js-lab">Win Rate</div>
          <div class="js-val" id="jWinRate">0%</div>
          <div class="js-sub" id="jWinRateSub">0W / 0L / 0BE</div>
        </div>
        <div class="card journal-stat">
          <div class="js-lab">Profit Factor</div>
          <div class="js-val" id="jProfitFactor">0.00</div>
          <div class="js-sub" id="jAvgWinLoss">Avg W: — / Avg L: —</div>
        </div>
        <div class="card journal-stat">
          <div class="js-lab">Best Regime</div>
          <div class="js-val" id="jBestRegime" style="font-size:17px;line-height:1.2">—</div>
          <div class="js-sub" id="jWorstRegime">Worst: —</div>
        </div>
      </div>

      <!-- MAIN LAYOUT: history + form -->
      <div style="display:grid;grid-template-columns:1.5fr .5fr;gap:16px;align-items:start">

        <!-- TRADE HISTORY -->
        <div class="panel">
          <div class="kicker">History</div>
          <div class="section-title" style="margin-bottom:12px">Trade Log</div>
          <div class="j-filter-bar" id="jFilterBar"></div>
          <div style="overflow-x:auto">
            <table>
              <thead>
                <tr>
                  <th>Date</th><th>Time (ET)</th><th>Ticker</th><th>Dir</th><th>Entry</th><th>Exit</th>
                  <th>Size</th><th>P&amp;L</th><th>Setup</th><th>Regime</th><th>Session</th>
                  <th>Bias</th><th>Verdict</th><th>Outcome</th><th></th>
                </tr>
              </thead>
              <tbody id="journalTableBody">
                <tr><td colspan="15" class="neutral" style="text-align:center;padding:20px">No trades logged yet.</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- QUICK ADD FORM -->
        <div class="panel">
          <div class="kicker">Log Trade</div>
          <div class="section-title" style="margin-bottom:14px">Quick Add</div>
          <div class="vstack" style="gap:10px">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div>
                <label class="trade-label">Ticker</label>
                <input class="trade-input" id="jTicker" type="text" placeholder="MNQ, SPY…" />
              </div>
              <div>
                <label class="trade-label">Date</label>
                <input class="trade-input" id="jDate" type="date" />
              </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              <div>
                <label class="trade-label">Direction</label>
                <select class="trade-select" id="jDirection">
                  <option value="LONG">LONG</option>
                  <option value="SHORT">SHORT</option>
                </select>
              </div>
              <div>
                <label class="trade-label">Outcome</label>
                <select class="trade-select" id="jOutcome">
                  <option value="WIN">WIN</option>
                  <option value="LOSS">LOSS</option>
                  <option value="BREAKEVEN">BREAKEVEN</option>
                </select>
              </div>
            </div>
            <div>
              <label class="trade-label">Realized P&amp;L ($) <span style="color:var(--muted2);font-size:9px;font-weight:400">— type actual dollar amount, e.g. 468.85 or -120</span></label>
              <input class="trade-input" id="jRealizedPnl" type="number" step="any" placeholder="e.g. 468.85 or -120" style="font-size:16px;font-weight:700;letter-spacing:.5px" />
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
              <div>
                <label class="trade-label">Entry <span style="color:var(--muted2);font-size:9px">opt</span></label>
                <input class="trade-input" id="jEntry" type="number" step="any" placeholder="0.00" />
              </div>
              <div>
                <label class="trade-label">Exit <span style="color:var(--muted2);font-size:9px">opt</span></label>
                <input class="trade-input" id="jExit" type="number" step="any" placeholder="0.00" />
              </div>
              <div>
                <label class="trade-label">Size</label>
                <input class="trade-input" id="jSize" type="number" step="any" placeholder="1" />
              </div>
            </div>
            <div>
              <label class="trade-label">Setup</label>
              <input class="trade-input" id="jSetup" type="text" placeholder="ORB, VWAP, Breakout…" />
            </div>
            <input class="trade-input" id="jNotes" type="text" placeholder="Notes (optional)" style="font-size:12px;color:var(--muted)" />
            <button class="submit-trade-btn" id="jSubmitBtn">LOG TRADE</button>
            <div id="jFormMsg" style="text-align:center;font-size:12px;display:none"></div>
          </div>
        </div>

      </div>

      <!-- REGIME BREAKDOWN -->
      <div class="panel">
        <div class="kicker">Edge Analysis</div>
        <div class="section-title" style="margin-bottom:6px">Performance by Regime</div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:14px">Which market regime do you trade best in? Auto-tagged at time of logging.</div>
        <div class="regime-breakdown-grid" id="regimeBreakdownGrid">
          <div class="regime-card"><div class="rc-sub">No trades yet.</div></div>
        </div>
      </div>

      <!-- SESSION BREAKDOWN -->
      <div class="panel">
        <div class="kicker">Edge Analysis</div>
        <div class="section-title" style="margin-bottom:6px">Performance by Session</div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:14px">Asia, London, NY Cash — which session gives you the cleanest edge?</div>
        <div class="regime-breakdown-grid" id="sessionBreakdownGrid">
          <div class="regime-card"><div class="rc-sub">No trades yet.</div></div>
        </div>
      </div>

    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    <span>D.O.N.N.A v5.0 // LIVE MARKET CORE</span>
    <span id="lastUpdated">Connecting...</span>
  </div>

</div>

<script>
// ════════ CUSTOMIZABLE INDEX TILES ════════
const SYMBOL_LIST = ['NQ','ES','SPX','NASDAQ','DJIA','DXY','VIX','US10Y','GOLD','SILVER','OIL','BTC','ETH'];
const DEFAULT_PREFS = ['NQ','ES','VIX','DXY','GOLD'];
const LS_KEY = 'user_index_prefs';
let _lastDashData = null;
let _activePicker = null;

function loadIndexPrefs() {
  try {
    const v = JSON.parse(localStorage.getItem(LS_KEY));
    if (Array.isArray(v) && v.length === 5) return v;
  } catch(e){}
  return [...DEFAULT_PREFS];
}
function saveIndexPrefs(prefs) {
  localStorage.setItem(LS_KEY, JSON.stringify(prefs));
}

let _liveBtcVix = {};

// Shared price formatter — always uses en-US locale with comma separators
function formatPrice(val, decimals) {
  const n = parseFloat(val);
  if (isNaN(n) || n === 0) return '—';
  const d = (decimals !== undefined) ? decimals : 2;
  return n.toLocaleString('en-US', {minimumFractionDigits: d, maximumFractionDigits: d});
}

function getSymbolData(sym, d) {
  // Always try market_snapshot first for every symbol (yfinance — most accurate)
  const snap = ((d.risk || {}).market_snapshot) || {};
  const s = snap[sym];
  if (s && s.last && s.last !== '-') {
    const disp = formatPrice(s.last, 2);
    if (disp !== '—') {
      const p = parseFloat(s.pct);
      return {
        val: disp, chg: s.chg || '—',
        pct: isNaN(p) ? null : (p >= 0 ? '+' : '') + p.toFixed(2) + '%',
        dir: isNaN(p) ? '' : (p >= 0 ? 'up' : 'down')
      };
    }
  }

  // BTC comes from the dedicated /btc-vix endpoint
  if (sym === 'BTC') {
    const q = _liveBtcVix[sym] || {};
    const last = q.last || 0;
    if (!last) return {val: '—', chg: '—', pct: null, dir: ''};
    const p = parseFloat(q.pct || 0);
    return {
      val: last.toLocaleString('en-US', {maximumFractionDigits: 0}),
      chg: (q.chg || 0).toFixed(2),
      pct: (p >= 0 ? '+' : '') + p.toFixed(2) + '%',
      dir: p >= 0 ? 'up' : 'down'
    };
  }

  // VIX: try btc-vix endpoint
  if (sym === 'VIX') {
    const q = _liveBtcVix['VIX'] || {};
    if (q.last) {
      const p = parseFloat(q.pct || 0);
      return {
        val: formatPrice(q.last, 2),
        chg: (q.chg || 0).toFixed(2),
        pct: (p >= 0 ? '+' : '') + p.toFixed(2) + '%',
        dir: p >= 0 ? 'up' : 'down'
      };
    }
  }

  // Futures macro pulse
  const pulseRow = (d.futures_macro_pulse || []).find(r => r.symbol === sym);
  if (pulseRow && pulseRow.last && pulseRow.last !== '-' && pulseRow.last !== '—') {
    const disp = formatPrice(pulseRow.last, 2);
    if (disp !== '—') return {val: disp, chg: pulseRow.chg || '—', pct: pulseRow.pct || null, dir: pulseRow.dir || ''};
  }

  // Major indexes
  const idxLabelMap = {NASDAQ: 'NASDAQ', SPX: 'S&P 500', DJIA: 'DJIA', DXY: 'DXY', US10Y: 'US 10Y'};
  const label = idxLabelMap[sym] || sym;
  const row = (d.major_indexes || []).find(r => r.symbol === label);
  if (row && row.last && row.last !== '-' && row.last !== '—') {
    const disp = formatPrice(row.last, 2);
    if (disp !== '—') return {val: disp, chg: row.chg || '—', pct: row.pct || null, dir: row.dir || ''};
  }

  return {val: '—', chg: '—', pct: null, dir: ''};
}

function applyTileData(tileEl, sym, data) {
  // Always show all 5 tiles; keep existing displayed value when no new data arrives
  tileEl.style.display = '';
  const nameEl = tileEl.querySelector('.index-tile-name');
  const valEl  = tileEl.querySelector('.index-tile-val');
  const chgEl  = tileEl.querySelector('.index-tile-chg');
  if (nameEl) nameEl.textContent = sym;
  const noData = !data.val || data.val === '—' || data.val === '-';
  if (!noData && valEl) {
    // data.val is pre-formatted by getSymbolData (e.g. "20,708.93")
    valEl.textContent = data.val;
    valEl.style.color = data.dir === 'up' ? 'var(--green)' : data.dir === 'down' ? 'var(--red)' : 'var(--text)';
  }
  if (!noData && chgEl) {
    chgEl.textContent = data.pct || '—';
    chgEl.style.color = data.dir === 'up' ? 'var(--green)' : data.dir === 'down' ? 'var(--red)' : 'var(--muted)';
  }
  tileEl.classList.remove('up','dn');
  if (data.dir === 'up') tileEl.classList.add('up');
  else if (data.dir === 'down') tileEl.classList.add('dn');
}

function refreshTilePrefs(d) {
  const prefs = loadIndexPrefs();
  document.querySelectorAll('#indexTiles .index-tile').forEach((tile, i) => {
    const sym = prefs[i] || DEFAULT_PREFS[i];
    applyTileData(tile, sym, getSymbolData(sym, d));
  });
}

function renderDashMajorIndexes(d) {
  const prefs = loadIndexPrefs();
  setHtml('majorIndexesTable', prefs.map(sym => {
    const data = getSymbolData(sym, d);
    const dc = data.dir === 'up' ? 'up' : data.dir === 'down' ? 'dn' : 'neutral';
    return `<tr><td>${sym}</td><td class="${dc}">${data.val}</td><td class="${dc}">${data.chg}</td><td class="${dc}">${data.pct || '—'}</td></tr>`;
  }).join('') || '<tr><td colspan="4" class="neutral">No data</td></tr>');
}

function closeTilePicker() {
  if (_activePicker) { _activePicker.remove(); _activePicker = null; }
}

function openTilePicker(tileIdx) {
  closeTilePicker();
  const prefs = loadIndexPrefs();
  const tile = document.querySelectorAll('#indexTiles .index-tile')[tileIdx];
  if (!tile) return;
  const picker = document.createElement('div');
  picker.className = 'tile-picker open';
  SYMBOL_LIST.forEach(sym => {
    const item = document.createElement('div');
    item.className = 'tile-picker-item' + (prefs[tileIdx] === sym ? ' active' : '');
    item.textContent = sym;
    item.addEventListener('click', e => {
      e.stopPropagation();
      prefs[tileIdx] = sym;
      saveIndexPrefs(prefs);
      if (_lastDashData) { refreshTilePrefs(_lastDashData); renderDashMajorIndexes(_lastDashData); }
      closeTilePicker();
    });
    picker.appendChild(item);
  });
  const reset = document.createElement('div');
  reset.className = 'tile-picker-reset';
  reset.textContent = '↺ Reset defaults';
  reset.addEventListener('click', e => {
    e.stopPropagation();
    saveIndexPrefs([...DEFAULT_PREFS]);
    if (_lastDashData) { refreshTilePrefs(_lastDashData); renderDashMajorIndexes(_lastDashData); }
    closeTilePicker();
  });
  picker.appendChild(reset);
  tile.appendChild(picker);
  _activePicker = picker;
}

function initTileEditors() {
  document.querySelectorAll('#indexTiles .index-tile').forEach((tile, i) => {
    const btn = tile.querySelector('.tile-edit-btn');
    if (btn) {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        (_activePicker && _activePicker.parentElement === tile) ? closeTilePicker() : openTilePicker(i);
      });
    }
  });
  document.addEventListener('click', closeTilePicker);
}

// ════════ TAB NAVIGATION ════════
document.querySelectorAll('.tab-btn[data-page]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn[data-page]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('page-' + btn.dataset.page).classList.add('active');
    if (btn.dataset.page === 'journal') refreshJournal();
    if (btn.dataset.page === 'harvey') refreshHarvey();
  });
});

// ════════ HELPERS ════════
function setText(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  const v = val || '—';
  if (el.textContent !== v) el.textContent = v;
}
function setHtml(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  const v = val || '';
  if (el.innerHTML !== v) el.innerHTML = v;
}
function riskClass(level) {
  const l = (level || '').toLowerCase();
  if (l === 'high') return 'risk-high';
  if (l === 'medium') return 'risk-medium';
  return 'risk-low';
}
function riskBadge(level) {
  return `<span class="risk-badge ${riskClass(level)}">${(level||'—').toUpperCase()}</span>`;
}
function dirClass(pct) {
  const n = parseFloat(String(pct).replace('%',''));
  if (isNaN(n)) return '';
  return n >= 0 ? 'up' : 'dn';
}

// ════════ LIVE STRIP ════════
function buildStrip(items) {
  if (!items || !items.length) return '';
  return items.map(item => {
    const val = item.value || '—';
    return `<span class="ticker-item"><b>${item.label}:</b> ${val}</span>`;
  }).join('');
}
function updateStrip(items) {
  const el = document.getElementById('liveStrip');
  if (!el) return;
  const newHtml = buildStrip(items);
  // Only rebuild (and reset animation) if content actually changed
  if (el.innerHTML !== newHtml) el.innerHTML = newHtml;
}

// ════════ DASHBOARD ENGINE ════════
let _dbStateEngine = null;
let _dbExecGate    = null;
let _dbHarveyCache = null;
let _dbGrokCache   = null;

function renderDashboard() {
  const se   = _dbStateEngine || {};
  const eg   = _dbExecGate    || {};
  const hv   = _dbHarveyCache || {};
  const grok = _dbGrokCache   || {};
  const risk = (_lastDashData || {}).risk || {};
  const snap = risk.market_snapshot || {};

  // ── Live strip + session (shared topbar)
  if (_lastDashData) {
    setText('sessionVal', risk.donna_session || '—');
    updateStrip((_lastDashData.live_strip) || []);
  }
  const stripEl = document.querySelector('.ticker-wrap');
  if (stripEl) {
    const ml = (se.macro_risk || risk.macro_risk || '').toLowerCase();
    stripEl.classList.remove('risk-high','risk-medium');
    if (ml === 'high') stripEl.classList.add('risk-high');
    else if (ml === 'medium') stripEl.classList.add('risk-medium');
  }

  // ── HERO ──
  const regime = se.market_regime || 'UNKNOWN';
  const macro  = (se.macro_risk || risk.macro_risk || 'low').toLowerCase();
  const session = se.session_state || risk.donna_session || '';
  const regimeEl = document.getElementById('dbRegimeText');
  if (regimeEl) {
    regimeEl.textContent = regime;
    const rCol = {TRENDING_UP:'var(--green)',TRENDING_DOWN:'var(--red)',RANGING:'var(--yellow)',VOLATILE:'var(--red)',EVENT_DRIVEN:'var(--yellow)',UNKNOWN:'var(--muted)'};
    regimeEl.style.color = rCol[regime] || 'var(--muted)';
  }
  const toneMap = {
    TRENDING_UP:   macro === 'high' ? 'Trending higher — macro conditions elevated, respect event risk' : 'Trending higher — momentum environment, tech leading',
    TRENDING_DOWN: macro === 'high' ? 'Trending lower — macro conditions elevated' : 'Trending lower — respect the tape',
    RANGING:       'Range-bound tape — reduced edge, fade extremes only',
    VOLATILE:      'Volatile conditions — reduce size, protect capital',
    EVENT_DRIVEN:  'Macro conditions elevated — respect event risk',
    UNKNOWN:       'Connecting to live market intelligence...',
  };
  setText('dbMarketTone', toneMap[regime] || '—');

  const canExec = eg.can_execute !== false;
  const lockouts = Array.isArray(eg.risk_lockouts) ? eg.risk_lockouts : [];
  const execBadge = document.getElementById('dbExecBadge');
  if (execBadge) {
    execBadge.textContent = canExec ? 'EXECUTION ENABLED' : 'EXECUTION BLOCKED';
    execBadge.style.color = canExec ? 'var(--green)' : 'var(--red)';
  }
  setText('dbExecReason', lockouts.length ? lockouts[0].reason : '');
  const macroEl = document.getElementById('dbMacroPosture');
  if (macroEl) {
    macroEl.textContent = 'MACRO ' + macro.toUpperCase();
    macroEl.style.color      = macro === 'high' ? 'var(--red)' : macro === 'medium' ? 'var(--yellow)' : 'var(--green)';
    macroEl.style.background = macro === 'high' ? 'var(--red2)' : macro === 'medium' ? 'rgba(255,201,60,.1)' : 'rgba(0,229,160,.1)';
  }

  // ── BADGES ──
  const bExec = document.getElementById('dbBadgeExec');
  if (bExec) { bExec.textContent = canExec ? 'ENABLED' : 'BLOCKED'; bExec.style.color = canExec ? 'var(--green)' : 'var(--red)'; }
  const bMacro = document.getElementById('dbBadgeMacro');
  if (bMacro) { bMacro.textContent = macro.toUpperCase(); bMacro.style.color = macro === 'high' ? 'var(--red)' : macro === 'medium' ? 'var(--yellow)' : 'var(--green)'; }
  const rf   = eg.red_folder_lock;
  const bRf  = document.getElementById('dbBadgeRedFolder');
  if (bRf) {
    const rfStr = rf === true ? 'ACTIVE' : rf === 'APPROACHING' ? 'APPROACHING' : 'CLEAR';
    bRf.textContent = rfStr;
    bRf.style.color = rf === true ? 'var(--red)' : rf === 'APPROACHING' ? 'var(--yellow)' : 'var(--green)';
  }
  const bSess = document.getElementById('dbBadgeSession');
  if (bSess) {
    const sLbl = {NEW_YORK_CASH:'NY CASH',LONDON:'LONDON',ASIA:'ASIA',OFF_HOURS:'OFF HOURS'};
    const sCol = {NEW_YORK_CASH:'var(--green)',LONDON:'var(--blue)',ASIA:'var(--yellow)',OFF_HOURS:'var(--muted)'};
    bSess.textContent = sLbl[session] || session || '—';
    bSess.style.color = sCol[session] || 'var(--muted)';
  }

  // ── DRIVER ──
  const driver = (_lastDashData || {}).driver || {};
  const wm     = (_lastDashData || {}).what_matters_now || {};
  setText('dbDriverPrimary', driver.dominant_driver || wm.headline || '—');
  setText('dbDriverRegime',  driver.market_regime   || regime || '—');
  const bullets = [];
  if (driver.market_summary) bullets.push(driver.market_summary);
  if (wm.headline && wm.headline !== driver.dominant_driver) bullets.push(wm.headline);
  if (wm.summary)  bullets.push(wm.summary);
  const bullEl = document.getElementById('dbDriverBullets');
  if (bullEl) setHtml('dbDriverBullets', bullets.slice(0,3).map(b => `<li>${b}</li>`).join('') || '<li>Awaiting market intelligence...</li>');

  // ── CATALYST ──
  setText('dbCatalystHeadline', grok.top_story || risk.last_headline || '—');
  setText('dbCatalystSummary',  grok.top_story_summary || grok.sentiment_reason || risk.headline_guidance || '—');
  const sent    = (grok.market_sentiment || 'NEUTRAL').toUpperCase();
  const sentEl  = document.getElementById('dbCatalystSentiment');
  if (sentEl) {
    sentEl.textContent      = sent;
    const sCol = {BULLISH:'var(--green)',BEARISH:'var(--red)',MIXED:'var(--yellow)',NEUTRAL:'var(--muted)'};
    const sBg  = {BULLISH:'rgba(0,229,160,.1)',BEARISH:'var(--red2)',MIXED:'rgba(255,201,60,.1)',NEUTRAL:'var(--panel2)'};
    sentEl.style.color      = sCol[sent] || 'var(--muted)';
    sentEl.style.background = sBg[sent]  || 'var(--panel2)';
  }

  // ── MARKET BOARD ──
  ['NQ','ES','VIX','DXY','GOLD'].forEach(sym => {
    const data = getSymbolData(sym, _lastDashData || {});
    const tile = document.querySelector(`.db-market-tile[data-sym="${sym}"]`);
    if (!tile) return;
    const valEl = tile.querySelector('.db-tile-val');
    const pctEl = tile.querySelector('.db-tile-pct');
    if (valEl) { valEl.textContent = data.val || '—'; valEl.style.color = data.dir === 'up' ? 'var(--green)' : data.dir === 'down' ? 'var(--red)' : 'var(--text)'; }
    if (pctEl) { pctEl.textContent = data.pct || '—'; pctEl.style.color = data.dir === 'up' ? 'var(--green)' : data.dir === 'down' ? 'var(--red)' : 'var(--muted)'; }
  });

  // ── HARVEY SNAPSHOT (sidebar) ──
  const verdict = hv.verdict || '—';
  const vEl = document.getElementById('dbHvVerdict');
  if (vEl) {
    vEl.textContent = verdict;
    const vCol = {BUY:'var(--green)',SELL:'var(--red)',WAIT:'var(--yellow)',STOP:'var(--red)'};
    vEl.style.color = vCol[verdict] || 'var(--yellow)';
  }
  const bias = hv.bias_score || 0;
  setText('dbHvConfidence', bias ? bias + '% confidence' : '—');
  setText('dbHvRegime',     ((hv.regime || {}).regime) || regime || '—');
  setText('dbHvBias',       bias ? `${bias} / 100 — ${hv.bias_direction || 'NEUTRAL'}` : '—');
  const sigs    = hv.last_signals || [];
  const lastSig = sigs[0];
  const _hvEt = lastSig && lastSig.timestamp ? new Date(lastSig.timestamp).toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit', hour12:false, timeZone:'America/New_York'}) : '';
  setText('dbHvLastSig', lastSig ? `${lastSig.ticker || '—'} · ${_hvEt}` : 'No recent signals');

  // ── DONNA SAYS ──
  let donnaSays = hv.donna_read || '';
  if (!donnaSays) {
    if (!canExec && macro === 'high') donnaSays = 'Macro conditions elevated. No entries until risk clears. Respect the lock.';
    else if (!canExec)               donnaSays = 'Execution blocked. Review all lockout conditions before placing trades.';
    else if (regime === 'TRENDING_UP')   donnaSays = 'Momentum environment. Look for pullbacks to key support. ES and NQ confirming direction.';
    else if (regime === 'TRENDING_DOWN') donnaSays = 'Trend is down. Avoid chasing longs. Wait for clean setup at key structure.';
    else if (regime === 'RANGING')       donnaSays = 'Range-bound tape. Reduce size. Fade extremes only.';
    else if (regime === 'VOLATILE')      donnaSays = 'Volatile conditions. Reduce size. Protect capital above all else.';
    else donnaSays = 'Connecting to live market intelligence...';
  }
  setText('dbDonnaSaysText', donnaSays);

  // ── Footer ──
  setText('lastUpdated', `Last sync: ${new Date().toLocaleTimeString('en-US', {hour12:true, hour:'2-digit', minute:'2-digit', second:'2-digit'})} ET`);
}

async function fetchStateEngine() {
  try {
    const res = await fetch('/state-engine');
    if (!res.ok) return;
    _dbStateEngine = await res.json();
    renderDashboard();
  } catch(e) { console.error('fetchStateEngine:', e); }
}

async function fetchExecutionGate() {
  try {
    const res = await fetch('/execution-gate');
    if (!res.ok) return;
    _dbExecGate = await res.json();
    renderDashboard();
  } catch(e) { console.error('fetchExecutionGate:', e); }
}

async function fetchHarveyData() {
  try {
    const res = await fetch('/harvey-data');
    if (!res.ok) return;
    _dbHarveyCache = await res.json();
    renderDashboard();
  } catch(e) { console.error('fetchHarveyData:', e); }
}

async function fetchGrokIntel() {
  try {
    const res = await fetch('/grok-intelligence');
    if (!res.ok) return;
    const g = await res.json();
    if (!g.error) { _dbGrokCache = g; renderDashboard(); }
  } catch(e) { console.error('fetchGrokIntel:', e); }
}

function dashClock() {
  const el = document.getElementById('dbSessionLabel');
  if (!el) return;
  const se = _dbStateEngine || {};
  const session = se.session_state || '';
  const sLbl = {NEW_YORK_CASH:'NY Cash',LONDON:'London',ASIA:'Asia',OFF_HOURS:'Off Hours'};
  const label = sLbl[session] || session || '';
  const now = new Date();
  const nyTime = now.toLocaleString('en-US', {timeZone:'America/New_York', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false});
  el.textContent = (label ? label + ' · ' : '') + nyTime + ' ET';
}

// ═══════════════════════════════════════
// H.A.R.V.E.Y NEW RENDERER
// ═══════════════════════════════════════

function renderHarveyNew(d) {
  // Verdict banner
  const verdict = d.verdict || 'WAIT';
  const vcolor  = d.verdict_color || 'yellow';
  const card = document.getElementById('hvVerdictCard');
  if (card) card.className = `hv-verdict-card ${vcolor}`;
  setText('hvVerdictWord',   verdict);
  setText('hvVerdictReason', d.verdict_reason || '—');

  // Bias gauge
  const bias      = d.bias_score || 50;
  const biasDir   = d.bias_direction || 'NEUTRAL';
  const biasColor = bias >= 60 ? 'var(--green)' : bias <= 40 ? 'var(--red)' : 'var(--yellow)';
  const scoreEl = document.getElementById('hvBiasScore');
  if (scoreEl) { scoreEl.textContent = `${bias} / 100 — ${biasDir}`; scoreEl.style.color = biasColor; }
  const fill = document.getElementById('hvGaugeFill');
  if (fill) {
    fill.style.width = bias + '%';
    fill.style.background = bias >= 60
      ? 'linear-gradient(90deg,var(--green),#00b37a)'
      : bias <= 40
        ? 'linear-gradient(90deg,#cc2244,var(--red))'
        : 'linear-gradient(90deg,var(--yellow),#d97706)';
  }

  // Price cards — prefer market_snapshot (yfinance) over harvey payload
  let nqC   = parseFloat(d.nq_last) || 0;
  let esC   = parseFloat(d.es_last) || 0;
  let nqPct = d.nq_pct || 0;
  let esPct = d.es_pct || 0;
  const _hvSnap = ((_lastDashData || {}).risk || {}).market_snapshot || {};
  const _nqS = _hvSnap['NQ'], _esS = _hvSnap['ES'];
  if (_nqS && _nqS.last && _nqS.last > 1000) { nqC = parseFloat(_nqS.last) || nqC; nqPct = parseFloat(_nqS.pct) || nqPct; }
  if (_esS && _esS.last && _esS.last > 1000) { esC = parseFloat(_esS.last) || esC; esPct = parseFloat(_esS.pct) || esPct; }
  const fmtPx  = p => p > 0 ? formatPrice(p, 2) : '—';
  const fmtPct = p => (p >= 0 ? '+' : '') + parseFloat(p).toFixed(2) + '%';
  const pctCol = p => p >= 0 ? 'var(--green)' : 'var(--red)';

  const nqEl = document.getElementById('hvNqLast');
  if (nqEl) { nqEl.textContent = fmtPx(nqC); nqEl.style.color = nqC > 0 ? pctCol(nqPct) : 'var(--muted)'; }
  const nqChgEl = document.getElementById('hvNqChg');
  if (nqChgEl) { nqChgEl.textContent = nqC > 0 ? fmtPct(nqPct) : '—'; nqChgEl.style.color = pctCol(nqPct); }
  setText('hvNqSummary', nqC > 0 ? (nqPct >= 0 ? "Trading above yesterday's reference" : "Trading below yesterday's reference") : 'Waiting for price data...');

  const esEl = document.getElementById('hvEsLast');
  if (esEl) { esEl.textContent = fmtPx(esC); esEl.style.color = esC > 0 ? pctCol(esPct) : 'var(--muted)'; }
  const esChgEl = document.getElementById('hvEsChg');
  if (esChgEl) { esChgEl.textContent = esC > 0 ? fmtPct(esPct) : '—'; esChgEl.style.color = pctCol(esPct); }
  setText('hvEsSummary', esC > 0 ? (esPct >= 0 ? "Trading above yesterday's reference" : "Trading below yesterday's reference") : 'Waiting for price data...');

  // Playbook
  const morning = d.morning_edge || {};
  const wm = d.what_matters || {};
  const rules = [];
  if (morning.today_bias)   rules.push('Bias: ' + morning.today_bias);
  if (morning.focus)        rules.push('Focus: ' + morning.focus);
  if (morning.open_quality) rules.push('Open Quality: ' + morning.open_quality);
  if (morning.first_read)   rules.push(morning.first_read);
  if (wm.headline)          rules.push(wm.headline);
  if (!rules.length) rules.push('Awaiting morning edge data...');
  const pbEl = document.getElementById('hvPlaybook');
  if (pbEl) pbEl.innerHTML = rules.map(r => '<li>' + r + '</li>').join('');

  // Session stats
  const ctx = d.session_context || {};
  setText('hvSession',      ctx.session      || d.donna_session || '—');
  setText('hvDay',          ctx.day          || '—');
  setText('hvSessionLabel', (d.session_significance || {}).label || '—');
  setHtml('hvMacroRisk',    riskBadge(d.macro_risk));

  // ORB status (ES only)
  const orbQ = d.orb_quality || 'PENDING';
  const pill = document.getElementById('hvOrbPill');
  if (pill) { pill.className = 'orb-status-pill orb-' + orbQ; pill.textContent = orbQ; }
  setText('hvOrbStatus', d.orb_status || '—');
  setText('hvOrbNote',   d.orb_note   || '—');

  // Donna says
  setText('hvDonnaSays', wm.focus_reason || wm.summary || d.verdict_reason || '—');

  // Risk engine
  if (d.risk_engine) renderRiskEngine(d.risk_engine);
}

async function refreshHarvey() {
  try {
    const res = await fetch('/harvey-data');
    if (!res.ok) return;
    const d = await res.json();
    renderHarveyNew(d);
  } catch(e) {
    console.error('HARVEY refresh error:', e);
  }
}

function renderHvSignals(signals) {
  const el = document.getElementById('hvSignals');
  if (!el) return;
  if (!signals || !signals.length) {
    el.innerHTML = '<div class="obs-item low"><div class="obs-body">No signals received yet. Connect your TradingView indicator to the webhook.</div></div>';
    return;
  }
  el.innerHTML = signals.slice(0, 5).map(s =>
    '<div class="signal-card">' +
    '<div class="signal-top">' +
    '<span class="signal-ticker">' + (s.ticker || '—') + '</span>' +
    '<div style="display:flex;gap:8px;align-items:center">' +
    '<span style="font-family:Space Mono,monospace;font-size:10px;color:var(--muted2)">' + (s.timeframe||'') + '</span>' +
    '<span class="signal-verdict sv-' + (s.verdict||'SKIP') + '">' + (s.verdict||'—') + '</span>' +
    '</div></div>' +
    '<div class="signal-meta">' + (s.signal||'') + ' · ' + (s.session||'') + ' · $' + (s.price||'—') + '</div>' +
    '<div class="signal-summary">' + (s.summary||'') + '</div>' +
    '</div>'
  ).join('');
}

async function refreshHvAlerts() {
  try {
    const res = await fetch('/alerts-data');
    if (!res.ok) return;
    const d = await res.json();
    renderHvSignals(d.alerts || d.raw_trade_alerts || []);
  } catch(e) {}
}

function _hvUpdateExec(d) {
  const taken = d.daily_trades_taken !== undefined ? d.daily_trades_taken : null;
  const limit = 2;
  const left  = taken !== null ? Math.max(0, limit - taken) : null;

  const botEl = document.getElementById('hvBotStatus');
  if (botEl) {
    const mode = d.broker_mode || (d.available ? 'LIVE' : 'OFFLINE');
    botEl.textContent = mode;
    botEl.style.color = d.available === false ? 'var(--red)' : 'var(--green)';
  }
  const leftEl = document.getElementById('hvTradesLeft');
  if (leftEl) leftEl.textContent = left !== null ? left + ' of ' + limit + ' remaining' : '—';
}

async function refreshHvExec() {
  try {
    const res = await fetch('/execution-status');
    if (!res.ok) return;
    const d = await res.json();
    _hvUpdateExec(d);
  } catch(e) {}
}

function renderHvSectors(stocks) {
  const el = document.getElementById('hvSectors');
  if (!el) return;
  if (!stocks || !stocks.length) {
    el.innerHTML = '<div style="font-size:13px;color:var(--muted2)">Loading sectors...</div>';
    return;
  }
  el.innerHTML = stocks.slice(0, 6).map(s => {
    const pct = parseFloat(s.percent_change) || 0;
    const col = pct >= 0.5 ? 'var(--green)' : pct <= -0.5 ? 'var(--red)' : 'var(--yellow)';
    return '<div class="hv-sector-row">' +
      '<span class="hv-sector-name">' + (s.name || '—').toUpperCase() + '</span>' +
      '<span class="hv-sector-pct" style="color:' + col + '">' + (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%</span>' +
      '</div>';
  }).join('');
}

async function refreshHvSectors() {
  try {
    const res = await fetch('/sp500-heatmap');
    if (!res.ok) return;
    const d = await res.json();
    renderHvSectors(d.stocks || []);
  } catch(e) {}
}

// ════════ RISK ENGINE ════════
function renderRiskEngine(re) {
  if (!re) return;

  const stop = !!re.stop_trading;
  const banner = document.getElementById('reStopBanner');
  if (banner) banner.classList.toggle('active', stop);

  // Position size
  const pos = re.position_size || {};
  const posEl  = document.getElementById('rePosValue');
  const posNote = document.getElementById('rePosNote');
  if (posEl) {
    if (pos.max_units != null) {
      posEl.textContent = pos.max_units + ' units';
      posEl.className = 're-value ' + (pos.valid ? 're-ok' : 're-warn');
    } else {
      posEl.textContent = '—';
      posEl.className = 're-value re-warn';
    }
  }
  if (posNote) posNote.textContent = pos.note || '—';

  // R/R
  const rr = re.rr || {};
  const rrEl   = document.getElementById('reRRValue');
  const rrNote = document.getElementById('reRRNote');
  if (rrEl) {
    if (rr.rr != null) {
      rrEl.textContent = rr.rr + ':1';
      rrEl.className = 're-value ' + (rr.valid ? 're-valid' : 're-invalid');
    } else {
      rrEl.textContent = '—';
      rrEl.className = 're-value re-warn';
    }
  }
  if (rrNote) rrNote.textContent = rr.note || '—';

  // Drawdown
  const dd = re.drawdown || {};
  const ddEl   = document.getElementById('reDDValue');
  const ddNote = document.getElementById('reDDNote');
  const ddCell = document.getElementById('reDDCell');
  if (ddEl) {
    ddEl.textContent = dd.daily_pnl != null ? '$' + dd.daily_pnl.toFixed(0) : '—';
    const cls = dd.daily_breach || dd.weekly_breach ? 're-invalid' : dd.status === 'WARNING' ? 're-warn' : 're-ok';
    ddEl.className = 're-value ' + cls;
  }
  if (ddNote) ddNote.textContent = dd.status_note || '—';
  if (ddCell) {
    ddCell.classList.toggle('stop', !!(dd.daily_breach || dd.weekly_breach));
  }

  // Session losses
  const sl = re.session_losses || {};
  const slEl   = document.getElementById('reLossValue');
  const slNote = document.getElementById('reLossNote');
  const slCell = document.getElementById('reLossCell');
  if (slEl) {
    slEl.textContent = sl.consecutive_losses != null ? sl.consecutive_losses : '—';
    slEl.className = 're-value ' + (sl.stop_triggered ? 're-invalid' : sl.consecutive_losses >= 2 ? 're-warn' : 're-ok');
  }
  if (slNote) slNote.textContent = sl.note || '—';
  if (slCell) slCell.classList.toggle('stop', !!sl.stop_triggered);

  // Pre-fill settings if available
  const accEl = document.getElementById('reAccountSize');
  const rPctEl = document.getElementById('reRiskPct');
  if (accEl && !accEl.value && re.account_size) accEl.placeholder = re.account_size;
  if (rPctEl && !rPctEl.value && re.risk_pct)   rPctEl.placeholder = re.risk_pct;
}

async function reCalculate() {
  const entry  = parseFloat(document.getElementById('reEntry')?.value);
  const stop   = parseFloat(document.getElementById('reStop')?.value);
  const target = parseFloat(document.getElementById('reTarget')?.value);
  const dir    = document.getElementById('reDir')?.value || 'LONG';
  if (isNaN(entry) || isNaN(stop)) return;
  const params = new URLSearchParams({ entry, stop, direction: dir });
  if (!isNaN(target)) params.set('target', target);
  try {
    const res = await fetch('/risk-engine-data?' + params.toString());
    const d = await res.json();
    renderRiskEngine(d);
  } catch(e) { console.error('Risk engine calc error:', e); }
}

async function reSaveSettings() {
  const account_size = parseFloat(document.getElementById('reAccountSize')?.value);
  const risk_pct     = parseFloat(document.getElementById('reRiskPct')?.value);
  const body = {};
  if (!isNaN(account_size)) body.account_size = account_size;
  if (!isNaN(risk_pct))     body.risk_pct     = risk_pct;
  if (!Object.keys(body).length) return;
  try {
    await fetch('/risk-engine/settings', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    refreshHarvey();
  } catch(e) { console.error('Risk engine settings error:', e); }
}

async function reResetStop() {
  try {
    await fetch('/risk-engine/reset-stop', { method: 'POST' });
    refreshHarvey();
  } catch(e) { console.error('Risk engine reset error:', e); }
}

document.getElementById('reCalcBtn')?.addEventListener('click', reCalculate);
document.getElementById('reSaveSettings')?.addEventListener('click', reSaveSettings);
document.getElementById('reResetStop')?.addEventListener('click', reResetStop);
['reEntry','reStop','reTarget'].forEach(id => {
  document.getElementById(id)?.addEventListener('keydown', e => { if (e.key === 'Enter') reCalculate(); });
});

// ════════ GROK INTELLIGENCE ════════
async function refreshGrokIntelligence() {
  try {
    const res = await fetch('/grok-intelligence');
    if (!res.ok) return;
    const g = await res.json();
    if (g.error) return; // no cached data yet — keep placeholder text

    const sent = (g.market_sentiment || 'NEUTRAL').toUpperCase();

    // Main card badge
    const badgeEl = document.getElementById('grokSentimentBadge');
    if (badgeEl) {
      badgeEl.textContent = sent;
      badgeEl.className = 'grok-sentiment-badge sentiment-' + sent;
    }

    // Main card fields — only update when there's real content
    if (g.top_story)         setText('grokTopStory',        g.top_story);
    if (g.top_story_summary) setText('grokSummary',         g.top_story_summary);
    if (g.donna_trade_read)  setText('grokTradeRead',       g.donna_trade_read);
    if (g.sentiment_reason)  setText('grokSentimentReason', g.sentiment_reason);

    // Ticker chips (main card + sidebar)
    const names = Array.isArray(g.key_names_to_watch) ? g.key_names_to_watch : [];
    const chipsHtml = names.length
      ? names.map(n => `<a href="https://finance.yahoo.com/quote/${encodeURIComponent(n)}" target="_blank" rel="noopener" class="grok-name-chip">${n}</a>`).join('')
      : '';
    const namesEl = document.getElementById('grokKeyNames');
    if (namesEl && chipsHtml) namesEl.innerHTML = chipsHtml;
    const sideChipsEl = document.getElementById('sidebarGrokChips');
    if (sideChipsEl && chipsHtml) sideChipsEl.innerHTML = chipsHtml;

    // Sidebar X Sentiment card
    const sgEl = document.getElementById('sidebarGrokSentiment');
    if (sgEl) {
      const sentColor = sent==='BULLISH' ? 'var(--green)' : sent==='BEARISH' ? 'var(--red)' : sent==='MIXED' ? 'var(--yellow)' : 'var(--muted2)';
      sgEl.innerHTML = `<span style="font-family:Rajdhani,sans-serif;font-size:22px;font-weight:700;color:${sentColor};letter-spacing:.5px">${sent}</span>`;
    }
    if (g.sentiment_reason) setText('donnaRead', g.sentiment_reason);

  } catch(e) {
    console.error('refreshGrokIntelligence failed:', e);
  }
}

// ════════ NEWS FUTURES STRIP ════════
async function refreshNewsFuturesStrip() {
  try {
    const [idxRes, pulseRes, bvRes] = await Promise.all([
      fetch('/major-indexes').then(r => r.json()),
      fetch('/futures-macro-pulse').then(r => r.json()),
      fetch('/btc-vix').then(r => r.json()),
    ]);
    const map = {};
    (pulseRes.rows || []).forEach(r => { map[r.symbol] = r; });
    (idxRes.rows || []).forEach(r => {
      const sym = r.symbol === 'S&P 500' ? 'SPX' : r.symbol;
      if (!map[sym]) map[sym] = r;
    });
    // Merge BTC and VIX from dedicated endpoint
    _liveBtcVix = bvRes;
    ['BTC','VIX'].forEach(sym => {
      const q = bvRes[sym] || {};
      if (q.last) {
        const p = parseFloat(q.pct || 0);
        map[sym] = {
          symbol: sym,
          last: sym === 'BTC'
            ? q.last.toLocaleString(undefined, {maximumFractionDigits: 0})
            : q.last.toFixed(2),
          pct: (p >= 0 ? '+' : '') + p.toFixed(2) + '%',
          dir: p >= 0 ? 'up' : 'dn',
        };
      }
    });
    // Override NQ and ES from market_snapshot (yfinance) if value is valid (> 1000)
    ['NQ','ES'].forEach(sym => {
      const snap = ((_lastDashData || {}).risk || {}).market_snapshot || {};
      const s = snap[sym];
      if (s && s.last && s.last > 1000) {
        const p = parseFloat(s.pct || 0);
        map[sym] = {
          symbol: sym,
          last: formatPrice(s.last, 2),
          pct: (p >= 0 ? '+' : '') + p.toFixed(2) + '%',
          dir: p >= 0 ? 'up' : 'dn',
        };
      }
    });
    const wanted = ['NQ','ES','DXY','GOLD','OIL','VIX','BTC'];
    let html = '';
    wanted.forEach(sym => {
      const d    = map[sym] || {};
      const last = d.last || '';
      const pct  = d.pct  || '';
      if (!last || last === '—' || last === '-') return; // skip missing
      const dir  = d.dir  || (String(pct).startsWith('+') ? 'up' : String(pct).startsWith('-') ? 'dn' : '');
      html += `<span class="nf-item"><span class="nf-sym">${sym}</span><span class="nf-val">${last}</span><span class="nf-pct ${dir}">${pct}</span></span>`;
    });
    const track = document.getElementById('newsFuturesTrack');
    if (track && html) track.innerHTML = html + html;
  } catch(e) { console.error('refreshNewsFuturesStrip:', e); }
}

// ════════ TRENDING MOVERS ════════
async function refreshTrendingMovers() {
  try {
    const res = await fetch('/trending-movers');
    if (!res.ok) return;
    const d = await res.json();
    function moverRow(m) {
      const isUp = String(m.pct).startsWith('+');
      const cls  = isUp ? 'up' : 'dn';
      return `<div class="mover-row">
        <div class="mover-left">
          <div class="mover-sym">${m.symbol}</div>
          <div class="mover-name">${m.name}</div>
        </div>
        <div class="mover-pct ${cls}">${m.pct}</div>
      </div>`;
    }
    const gEl = document.getElementById('moversGainers');
    const lEl = document.getElementById('moversLosers');
    if (gEl) gEl.innerHTML = (d.gainers||[]).map(moverRow).join('') || '<div class="econ-no-events">No data</div>';
    if (lEl) lEl.innerHTML = (d.losers||[]).map(moverRow).join('')  || '<div class="econ-no-events">No data</div>';
  } catch(e) { console.error('refreshTrendingMovers:', e); }
}


// ════════ ECON CALENDAR ════════
function renderEconCalendar(events) {
  const el = document.getElementById('sidebarEconCalendar');
  if (!el) return;

  const nyNow   = new Date(new Date().toLocaleString('en-US', { timeZone:'America/New_York' }));
  const todayStr = nyNow.toISOString().slice(0,10);
  const nowMin   = nyNow.getHours() * 60 + nyNow.getMinutes();

  // Build Mon–Fri dates for this week
  const dow = nyNow.getDay();
  const monOffset = dow === 0 ? -6 : 1 - dow;
  const weekDays = [];
  for (let i = 0; i < 5; i++) {
    const d = new Date(nyNow);
    d.setDate(nyNow.getDate() + monOffset + i);
    weekDays.push(d.toISOString().slice(0,10));
  }

  const DAY_ABBR = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
  const MON_ABBR = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];

  function dayLabel(ds) {
    const [y,m,d] = ds.split('-').map(Number);
    const dt = new Date(y, m-1, d);
    return `${DAY_ABBR[dt.getDay()]} ${MON_ABBR[dt.getMonth()]} ${d}`;
  }

  // Group events by date
  const byDate = {};
  (events || []).forEach(ev => {
    const k = (ev.date || todayStr).slice(0,10);
    if (!byDate[k]) byDate[k] = [];
    byDate[k].push(ev);
  });

  function verdict(ev) {
    const a = parseFloat(ev.actual), f = parseFloat(ev.forecast);
    if (isNaN(a) || isNaN(f) || f === 0) return '';
    const diff = (a - f) / Math.abs(f);
    if (diff >  0.05) return '<span class="econ-verdict hot">HOT</span>';
    if (diff < -0.05) return '<span class="econ-verdict miss">MISS</span>';
    return '<span class="econ-verdict inline">INLINE</span>';
  }

  function evRow(ev, isToday) {
    const imp    = (ev.importance || 'low').toLowerCase();
    const dotCls = imp === 'high' ? 'high' : imp === 'medium' ? 'medium' : 'low';
    const [hh,mm]= (ev.time_et || '00:00').split(':').map(Number);
    const isPast = isToday && (hh * 60 + mm) <= nowMin;
    let sub = '';
    if (isToday && isPast) {
      const a = ev.actual   != null ? ev.actual   : '—';
      const f = ev.forecast != null ? ev.forecast : '—';
      sub = `<div class="econ-sub"><span class="econ-vals">A:${a} · F:${f}</span>${verdict(ev)}</div>`;
    } else if (ev.forecast != null || ev.previous != null) {
      const parts = [];
      if (ev.forecast != null) parts.push(`F:${ev.forecast}`);
      if (ev.previous != null) parts.push(`P:${ev.previous}`);
      sub = `<div class="econ-sub"><span class="econ-vals">${parts.join(' · ')}</span></div>`;
    }
    return `<div class="econ-event">
      <div class="econ-dot ${dotCls}"></div>
      <div class="econ-time">${ev.time_et || '?'}</div>
      <div class="econ-body"><div class="econ-title">${ev.title || '—'}</div>${sub}</div>
    </div>`;
  }

  let html = '';
  for (const ds of weekDays) {
    const dayEvts = byDate[ds] || [];
    const isToday = ds === todayStr;
    if (!isToday && !dayEvts.length) continue;
    const label = isToday ? `TODAY — ${dayLabel(ds)}` : dayLabel(ds);
    html += `<div class="econ-day-header ${isToday ? 'today' : 'other'}">${label}</div>`;
    if (dayEvts.length) {
      html += dayEvts.map(ev => evRow(ev, isToday)).join('');
    } else {
      html += '<div class="econ-no-events">No scheduled events</div>';
    }
  }

  el.innerHTML = html || '<div class="econ-no-events">No events this week</div>';
}

async function refreshEconCalendar() {
  try {
    const res = await fetch('/calendar');
    if (!res.ok) return;
    const data = await res.json();
    renderEconCalendar(data.events || []);
  } catch(e) { console.error('refreshEconCalendar:', e); }
}

// ════════ RENDER NEWS ════════
function classifyHeadlineTag(text) {
  const t = (text || '').toLowerCase();
  if (/war|conflict|sanction|geopolit|iran|russia|ukraine|missile|military|nato|troops|attack/.test(t)) return 'GEOPOLITICAL';
  if (/oil|energy|opec|gas|crude|pipeline/.test(t)) return 'ENERGY';
  if (/fed|rate|yield|inflation|cpi|pce|gdp|macro|recession|fomc|powell/.test(t)) return 'MACRO';
  if (/earnings|beat|miss|guidance|revenue|eps|ipo|merger|acquisition/.test(t)) return 'MARKET';
  if (/calendar|event|data|report|release|scheduled/.test(t)) return 'CALENDAR';
  return 'MARKET';
}

function renderNews(d) {
  const risk = d.risk || {};
  const movers = d.market_movers_engine || {};
  const news = d.news || [];
  const snap = (risk.market_snapshot) || {};

  // Economic calendar from macro events in dashboard payload
  const calEvents = (d.calendar && d.calendar.events) ? d.calendar.events : [];
  renderEconCalendar(calEvents);

  // Breaking ticker
  const tickerItems = news.slice(0, 6).map(n => n.headline || '').filter(Boolean);
  if (tickerItems.length) {
    const track = document.getElementById('breakingTickerTrack');
    if (track) {
      const doubled = [...tickerItems, ...tickerItems];
      track.innerHTML = doubled.map(h => `<span class="breaking-item">${h}</span>`).join('');
    }
  }

  // Populate index tiles from user prefs
  _lastDashData = d;
  refreshTilePrefs(d);

  // Feature story — top macro headline
  const featureText = risk.last_headline || news[0]?.headline || '—';
  const featureNote = risk.headline_guidance || risk.last_market_guidance || '—';
  const featureTag = classifyHeadlineTag(featureText);
  const ftEl = document.getElementById('featureStoryTag');
  if (ftEl) { ftEl.textContent = featureTag; ftEl.className = 'story-tag ' + featureTag; }
  setText('featureHeadline', featureText);
  setText('featureNote', featureNote);

  // Live feed — tag colors: GEOPOLITICAL red, MARKET blue, MACRO amber, ENERGY gold, CALENDAR gray
  const tagStyle = {
    GEOPOLITICAL: 'background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.2)',
    MARKET:       'background:rgba(37,99,235,.08);color:var(--blue);border:1px solid rgba(37,99,235,.15)',
    MACRO:        'background:rgba(184,134,11,.08);color:var(--yellow);border:1px solid rgba(184,134,11,.2)',
    ENERGY:       'background:rgba(184,134,11,.08);color:var(--gold);border:1px solid rgba(184,134,11,.2)',
    CALENDAR:     'background:var(--panel2);color:var(--muted2);border:1px solid var(--line)',
  };
  setHtml('newsList', news.length ? news.map((n, i) => {
    const tag  = classifyHeadlineTag(n.headline);
    const tSty = tagStyle[tag] || tagStyle.MARKET;
    const ts   = n.datetime ? new Date(n.datetime * 1000).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',hour12:true}) : '';
    return `<div class="news-numbered-item">
      <div class="news-num">${i+1}.</div>
      <div class="news-body">
        <div style="margin-bottom:5px"><span style="display:inline-block;padding:2px 8px;border-radius:5px;font-family:Space Mono,monospace;font-size:8px;font-weight:700;letter-spacing:1px;text-transform:uppercase;${tSty}">${tag}</span></div>
        <div class="news-headline">${n.headline || '—'}</div>
        <div class="news-meta">${n.source || '—'}${ts ? ' · ' + ts : ''}</div>
        ${n.summary && n.summary !== n.headline ? `<div class="news-summary">${n.summary}</div>` : ''}
        ${n.url ? `<a class="news-link" href="${n.url}" target="_blank" rel="noopener">Read more →</a>` : ''}
      </div>
    </div>`;
  }).join('') : '<div class="obs-item low"><div class="obs-body">No live news loaded yet.</div></div>');

  // Sidebar risk levels
  function setRiskBadge(id, level) {
    const el = document.getElementById(id);
    if (!el) return;
    const l = (level || 'medium').toLowerCase();
    el.textContent = l.toUpperCase();
    el.className = 'risk-badge risk-' + l;
  }
  setRiskBadge('sidebarMacroRisk',    risk.macro_risk);
  setRiskBadge('sidebarHeadlineRisk', risk.headline_risk);
  setRiskBadge('sidebarMarketRisk',   risk.market_news_risk);

  setText('sidebarEventPhase', risk.event_phase || '—');
  setText('sidebarNextEvent',  risk.next_event  || 'No upcoming events');

  // DONNA SAYS — market guidance text
  const donnaSays = risk.last_market_guidance || risk.headline_guidance || risk.last_headline || '';
  if (donnaSays) setText('donnaSaysText', donnaSays);
}

// ════════ EXEC MONITOR + SESSION SCORECARD ════════
function _fmtPnl(v) {
  const n = parseFloat(v);
  if (v == null || isNaN(n)) return '—';
  return (n >= 0 ? '+$' : '-$') + Math.abs(n).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
}
function _fmtUsd(v) {
  const n = parseFloat(v);
  if (v == null || isNaN(n)) return '—';
  return '$' + n.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
}
function _donnaGrade(winRate, todayPnl) {
  if (winRate >= 65 && todayPnl > 0) return 'A';
  if (winRate >= 50 && todayPnl >= 0) return 'B';
  if (winRate >= 40) return 'C';
  return 'D';
}

async function refreshExecMonitor() {
  const _setExecPlaceholder = (msg) => {
    const pillEl = document.getElementById('execStatusPill');
    const dotEl  = document.getElementById('execStatusDot');
    const txtEl  = document.getElementById('execStatusText');
    if (pillEl) pillEl.className = 'exec-status-pill exec-status-paused';
    if (dotEl)  dotEl.style.background = 'var(--muted2)';
    if (txtEl)  txtEl.textContent = 'CONNECTING';
    const pnlEl = document.getElementById('execPnlBig');
    if (pnlEl) { pnlEl.textContent = '$0.00'; pnlEl.style.color = 'var(--muted)'; }
    ['execEquity','execTrades'].forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.textContent = '—'; el.style.color = 'var(--muted2)'; }
    });
    const rfEl = document.getElementById('execRedFolder');
    if (rfEl) { rfEl.textContent = 'Checking schedule...'; rfEl.style.color = 'var(--muted2)'; }
    const sigEl = document.getElementById('execLastSignal');
    if (sigEl) { sigEl.textContent = msg; sigEl.style.color = 'var(--muted2)'; }
  };
  try {
    const res = await fetch('/execution-status');
    if (!res.ok) { _setExecPlaceholder('Execution monitor — connect Alpaca to activate'); return; }
    const s = await res.json();
    if (!s.available) {
      _setExecPlaceholder('Execution monitor offline — Alpaca credentials not configured');
      return;
    }

    const pillEl = document.getElementById('execStatusPill');
    const dotEl  = document.getElementById('execStatusDot');
    const txtEl  = document.getElementById('execStatusText');
    if (s.daily_loss_limit_hit) {
      if (pillEl) pillEl.className = 'exec-status-pill exec-status-blocked';
      if (dotEl)  dotEl.style.background = 'var(--red)';
      if (txtEl)  txtEl.textContent = 'BLOCKED';
    } else if (s.red_folder_window_active) {
      if (pillEl) pillEl.className = 'exec-status-pill exec-status-paused';
      if (dotEl)  dotEl.style.background = 'var(--yellow)';
      if (txtEl)  txtEl.textContent = 'PAUSED';
    } else {
      if (pillEl) pillEl.className = 'exec-status-pill exec-status-active';
      if (dotEl)  dotEl.style.background = 'var(--green)';
      if (txtEl)  txtEl.textContent = 'ACTIVE';
    }

    const pnl   = s.current_pnl_today ?? s.account?.pnl_today;
    const pnlEl = document.getElementById('execPnlBig');
    if (pnlEl) {
      pnlEl.textContent = _fmtPnl(pnl);
      const n = parseFloat(pnl);
      pnlEl.style.color = isNaN(n) ? 'var(--muted)' : n >= 0 ? 'var(--green)' : 'var(--red)';
    }

    const eqEl = document.getElementById('execEquity');
    if (eqEl) { eqEl.textContent = _fmtUsd(s.account?.equity); eqEl.style.color = 'var(--text)'; }

    const trEl = document.getElementById('execTrades');
    if (trEl) { trEl.textContent = s.daily_trades_taken != null ? `${s.daily_trades_taken} today` : '0 today'; trEl.style.color = 'var(--text)'; }

    const rfEl = document.getElementById('execRedFolder');
    if (rfEl) {
      if (s.red_folder_window_active) {
        rfEl.textContent = 'ACTIVE NOW';
        rfEl.style.color = 'var(--red)';
      } else if (s.minutes_to_next_event != null) {
        const mins = Math.round(parseFloat(s.minutes_to_next_event));
        rfEl.textContent = mins > 0 ? `${mins} min — ${s.next_red_folder_event || ''}` : 'Imminent';
        rfEl.style.color = mins <= 15 ? 'var(--yellow)' : 'var(--text)';
      } else {
        rfEl.textContent = 'No event scheduled';
        rfEl.style.color = 'var(--muted)';
      }
    }
  } catch(e) {
    _setExecPlaceholder('Execution monitor — connecting...');
    console.error('refreshExecMonitor failed:', e);
  }
}

async function refreshSessionScorecard() {
  const _setScorecardPlaceholder = (msg) => {
    const pnlEl = document.getElementById('scorecardPnlBig');
    if (pnlEl) { pnlEl.textContent = '$0.00'; pnlEl.style.color = 'var(--muted2)'; }
    const gradeEl = document.getElementById('donnaGrade');
    if (gradeEl) { gradeEl.textContent = '—'; gradeEl.style.color = 'var(--muted2)'; }
    const wEl = document.getElementById('scWins');   if (wEl) wEl.textContent = '0';
    const lEl = document.getElementById('scLosses'); if (lEl) lEl.textContent = '0';
    const bEl = document.getElementById('scBe');     if (bEl) bEl.textContent = '0';
    const wrEl = document.getElementById('scWinRate'); if (wrEl) wrEl.textContent = '—';
    const bestEl  = document.getElementById('scBest');  if (bestEl)  bestEl.textContent  = '—';
    const worstEl = document.getElementById('scWorst'); if (worstEl) worstEl.textContent = '—';
    const wmEl = document.getElementById('scWhatMatters');
    if (wmEl) { wmEl.textContent = msg; wmEl.style.color = 'var(--muted2)'; }
  };
  try {
    const [jRes, sRes] = await Promise.all([fetch('/journal/data'), fetch('/execution-status')]);
    const j = jRes.ok ? await jRes.json() : null;
    const s = sRes.ok ? await sRes.json() : null;

    if (!j) { _setScorecardPlaceholder('Session scorecard — connecting...'); return; }

    const trades = j?.trades || [];
    const stats  = j?.stats  || {};
    const todayStr = new Date().toISOString().slice(0, 10);
    const todayTrades = trades.filter(t => t.trade_date === todayStr && t.outcome !== 'OPEN');

    // Bug 6: today P&L — only sum realized_pnl from WIN and LOSS trades, never OPEN or null
    const todayPnl = todayTrades
      .filter(t => t.outcome === 'WIN' || t.outcome === 'LOSS')
      .reduce((sum, t) => {
        const v = parseFloat(t.realized_pnl ?? t.pnl ?? 'x');
        return sum + (isNaN(v) ? 0 : v);
      }, 0);

    if (todayTrades.length === 0) {
      _setScorecardPlaceholder('No trades today — scorecard updates after first trade');
      return;
    }

    const pnlEl = document.getElementById('scorecardPnlBig');
    if (pnlEl) {
      pnlEl.textContent = _fmtPnl(todayPnl);
      pnlEl.style.color = todayPnl >= 0 ? 'var(--green)' : 'var(--red)';
    }

    const tw = todayTrades.filter(t => t.outcome === 'WIN').length;
    const tl = todayTrades.filter(t => t.outcome === 'LOSS').length;
    const tb = todayTrades.filter(t => t.outcome === 'BREAKEVEN').length;
    // Bug 7: win rate denominator = only WIN + LOSS (exclude BREAKEVEN from rate)
    const tt = tw + tl;
    const twr = tt > 0 ? Math.round(tw / tt * 100) : 0;

    const wEl = document.getElementById('scWins');   if (wEl) wEl.textContent = tw;
    const lEl = document.getElementById('scLosses'); if (lEl) lEl.textContent = tl;
    const bEl = document.getElementById('scBe');     if (bEl) bEl.textContent = tb;
    const wrEl = document.getElementById('scWinRate');
    if (wrEl) wrEl.textContent = tt > 0 ? `${twr}%  (${tw}W / ${tl}L)` : '—';

    const todayPnls = todayTrades
      .map(t => parseFloat(t.realized_pnl ?? t.pnl ?? 'x'))
      .filter(n => !isNaN(n));
    const bestEl  = document.getElementById('scBest');
    const worstEl = document.getElementById('scWorst');
    if (todayPnls.length) {
      if (bestEl)  bestEl.textContent  = _fmtPnl(Math.max(...todayPnls));
      if (worstEl) worstEl.textContent = _fmtPnl(Math.min(...todayPnls));
    } else {
      if (bestEl)  bestEl.textContent  = '—';
      if (worstEl) worstEl.textContent = '—';
    }

    const grade   = _donnaGrade(twr, todayPnl);
    const gradeEl = document.getElementById('donnaGrade');
    if (gradeEl) {
      gradeEl.textContent = grade;
      gradeEl.style.color = {A:'var(--green)',B:'var(--blue)',C:'var(--yellow)',D:'var(--red)'}[grade] || 'var(--muted2)';
    }

    // Last DONNA_AUTO signal → Execution Monitor last signal cell
    const auto = [...trades].reverse().find(t => t.source === 'DONNA_AUTO');
    const sigEl = document.getElementById('execLastSignal');
    if (sigEl) {
      if (auto) {
        const verdict = auto.harvey_verdict || auto.outcome || '—';
        const vclr = verdict === 'TAKE' || verdict === 'WIN' ? 'var(--green)'
                   : verdict === 'LOSS' ? 'var(--red)' : 'var(--yellow)';
        const conf = auto.confidence ? `<span style="font-family:Space Mono,monospace;font-size:9px;color:var(--muted2);margin-left:4px">${auto.confidence}</span>` : '';
        const ts   = auto.time || (auto.timestamp || '').slice(11,16);
        sigEl.innerHTML = `<span style="font-weight:700">${auto.ticker || '—'}</span>
          <span style="font-family:Space Mono,monospace;font-size:9px;padding:2px 6px;border-radius:4px;background:rgba(128,128,128,.1);color:${vclr};margin-left:4px">${verdict}</span>${conf}
          <div style="font-size:11px;color:var(--muted2);margin-top:2px">${ts}</div>`;
      } else {
        sigEl.textContent = 'No auto trades yet';
        sigEl.style.color = 'var(--muted2)';
      }
    }

    // What matters now — pull from cached dashboard data
    const wmEl = document.getElementById('scWhatMatters');
    if (wmEl) {
      const wm = _lastDashData?.what_matters_now;
      wmEl.textContent = wm?.headline || wm?.summary || '—';
    }

  } catch(e) {
    _setScorecardPlaceholder('Session scorecard — connecting...');
    console.error('refreshSessionScorecard failed:', e);
  }
}

// ════════ MAIN REFRESH ════════
async function refresh() {
  try {
    const res = await fetch('/dashboard-data');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const d = await res.json();
    _lastDashData = d;
    try { renderDashboard(); } catch(e) { console.error('renderDashboard failed:', e); }
    try { renderNews(d); } catch(e) { console.error('renderNews failed:', e); }
  } catch(err) {
    console.error('Donna refresh error:', err);
    setText('lastUpdated', 'Sync error — retrying...');
  }
}

// ════════ ASSISTANT CHAT ════════
const chatOutput = document.getElementById('assistantOutput');
const chatInput = document.getElementById('assistantInput');
const sendBtn = document.getElementById('assistantSend');
const typingIndicator = document.getElementById('typingIndicator');

function inferResponseTag(text) {
  const t = (text || '').toLowerCase();
  if (/risk|danger|warning|threat|caution|stop|avoid/.test(t)) return 'RISK';
  if (/buy|sell|entry|exit|trade|execute|position|size|stop.loss|target/.test(t)) return 'EXECUTION';
  if (/earnings|fomc|cpi|event|calendar|report|release|tomorrow|today at/.test(t)) return 'CALENDAR';
  return 'ANALYSIS';
}

function appendMsg(role, text, tag) {
  const clearfix = document.createElement('div');
  clearfix.className = 'msg-clearfix';

  const el = document.createElement('div');
  el.className = 'msg ' + role;
  if (role === 'assistant') {
    const resolvedTag = tag || inferResponseTag(text);
    el.innerHTML = `<span class="role">DONNA</span>${text}<div><span class="msg-tag ${resolvedTag}">${resolvedTag}</span></div>`;
  } else {
    el.innerHTML = `<span class="role">YOU</span>${text}`;
  }
  chatOutput.appendChild(el);
  chatOutput.appendChild(clearfix);
  chatOutput.scrollTop = chatOutput.scrollHeight;
}

function showTyping(show) {
  if (typingIndicator) typingIndicator.classList.toggle('active', show);
  if (show) chatOutput.scrollTop = chatOutput.scrollHeight;
}

async function sendChat(overrideMsg) {
  const msg = overrideMsg || chatInput.value.trim();
  if (!msg) return;
  chatInput.value = '';
  sendBtn.disabled = true;
  appendMsg('user', msg);
  showTyping(true);
  try {
    const res = await fetch('/assistant/chat', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: msg})
    });
    const data = await res.json();
    showTyping(false);
    appendMsg('assistant', data.reply || 'No response.');
  } catch (err) {
    showTyping(false);
    appendMsg('assistant', 'Connection error. Please try again.');
  }
  sendBtn.disabled = false;
  chatInput.focus();
}

sendBtn.addEventListener('click', () => sendChat());
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });

document.querySelectorAll('.quick-cmd-btn').forEach(btn => {
  btn.addEventListener('click', () => sendChat(btn.dataset.cmd));
});

// ════════ SSE — REAL-TIME SIGNAL STREAM ════════
function connectSSE() {
  const es = new EventSource('/stream');

  es.onmessage = function(e) {
    let msg;
    try { msg = JSON.parse(e.data); } catch(_) { return; }
    if (msg.type !== 'signal') return;

    // Alert audio ping — 440 Hz, 100ms, low volume
    try {
      const actx = new (window.AudioContext || window.webkitAudioContext)();
      const osc  = actx.createOscillator();
      const gain = actx.createGain();
      osc.connect(gain);
      gain.connect(actx.destination);
      osc.type = 'sine';
      osc.frequency.value = 440;
      gain.gain.setValueAtTime(0, actx.currentTime);
      gain.gain.linearRampToValueAtTime(0.07, actx.currentTime + 0.01);
      gain.gain.linearRampToValueAtTime(0, actx.currentTime + 0.1);
      osc.start(actx.currentTime);
      osc.stop(actx.currentTime + 0.11);
      osc.onended = () => actx.close();
    } catch(_) {}

    // Targeted HARVEY update only — never triggers a full page refresh
    refreshHarvey();

    // Flash verdict banner
    const banner = document.getElementById('hvVerdictCard');
    if (banner) {
      banner.classList.remove('flash');
      void banner.offsetWidth; // reflow to restart animation
      banner.classList.add('flash');
      banner.addEventListener('animationend', () => banner.classList.remove('flash'), { once: true });
    }

    // Pulse the nav dot
    const dot = document.getElementById('harveySignalDot');
    if (dot) {
      dot.classList.remove('active');
      void dot.offsetWidth;
      dot.classList.add('active');
      dot.addEventListener('animationend', () => dot.classList.remove('active'), { once: true });
    }
  };

  es.onerror = function() {
    es.close();
    // Auto-reconnect after 3 s
    setTimeout(connectSSE, 3000);
  };
}

// ════════ SCENARIO ENGINE ════════
function renderScenarios(data) {
  const scenarios = data.scenarios || [];
  const genAt = data.generated_at || '';
  const source = data.source || '—';

  // Meta line
  const metaEl = document.getElementById('scenarioMeta');
  if (metaEl && genAt) {
    const ts = genAt.substring(0,16).replace('T',' ');
    metaEl.textContent = `${source.toUpperCase()} · ${ts} UTC`;
  }

  if (!scenarios.length) {
    setHtml('scenarioGrid', '<div class="scenario-card"><div class="sc-reaction" style="color:var(--muted2)">No scenarios available. Click GENERATE.</div></div>');
    return;
  }

  setHtml('scenarioGrid', scenarios.map((s, i) => {
    const conf = (s.confidence || 'MEDIUM').toUpperCase();
    const confDot = conf === 'HIGH' ? '●' : conf === 'MEDIUM' ? '◉' : '○';
    return `
      <div class="scenario-card conf-${conf}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:10px">
          <div style="font-family:Space Mono,monospace;font-size:9px;color:var(--muted2);letter-spacing:1.5px;text-transform:uppercase">Scenario ${i+1}</div>
          <span class="sc-conf ${conf}"><span class="sc-conf-dot"></span>${conf}</span>
        </div>
        <div class="sc-trigger">${s.trigger || '—'}</div>
        <div class="sc-reaction">${s.expected_reaction || '—'}</div>
        <div class="sc-levels"><span style="color:var(--muted2);font-size:9px;letter-spacing:1px">KEY LEVELS &nbsp;</span>${s.key_levels || '—'}</div>
        <div class="sc-watch"><span style="color:var(--muted2);font-size:10px;font-family:Space Mono,monospace;letter-spacing:.5px">WATCH FOR &nbsp;</span>${s.watch_for || '—'}</div>
      </div>`;
  }).join(''));
}

async function refreshScenarios(force = false) {
  const btn = document.getElementById('scenarioGenBtn');
  if (btn) { btn.disabled = true; btn.classList.add('loading'); btn.textContent = 'GENERATING'; }
  try {
    const url = force ? '/scenario-data/refresh' : '/scenario-data';
    const res = await fetch(url, force ? {method:'POST'} : undefined);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    renderScenarios(data);
  } catch(e) {
    console.error('Scenario refresh error:', e);
  }
  if (btn) { btn.disabled = false; btn.classList.remove('loading'); btn.textContent = 'GENERATE'; }
}

document.getElementById('scenarioGenBtn')?.addEventListener('click', () => refreshScenarios(true));

// ════════ JOURNAL ════════
let journalFilter = 'all';
let _journalData  = null;

function fmtTimeET(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString('en-US', {hour:'numeric', minute:'2-digit', hour12:true, timeZone:'America/New_York'}) + ' ET';
  } catch(e) { return '—'; }
}

function fmtDateHeader(dateStr) {
  try {
    const [y,m,d] = dateStr.split('-').map(Number);
    return new Date(y, m-1, d).toLocaleDateString('en-US', {weekday:'long', month:'long', day:'numeric', year:'numeric'});
  } catch(e) { return dateStr; }
}

function setJournalFilter(f) {
  journalFilter = f;
  if (_journalData) renderJournal(_journalData);
}

function renderJournal(data) {
  _journalData = data;
  const stats  = data.stats  || {};
  const trades = data.trades || [];

  // Daily P&L banner
  const dp = stats.daily_pnl || {};
  function applyDailyPnl(elId, val) {
    const el = document.getElementById(elId);
    if (!el) return;
    const n = parseFloat(val) || 0;
    el.textContent = (n >= 0 ? '+$' : '-$') + Math.abs(n).toFixed(2);
    el.style.color  = n > 0 ? 'var(--green)' : n < 0 ? 'var(--red)' : 'var(--muted)';
  }

  // Bug 6: today P&L — recalculate from raw trades; only WIN + LOSS, skip OPEN and null
  const todayStrJ = new Date().toISOString().slice(0, 10);
  const todayPnlJ = trades
    .filter(t => t.trade_date === todayStrJ && (t.outcome === 'WIN' || t.outcome === 'LOSS'))
    .reduce((sum, t) => {
      const v = parseFloat(t.realized_pnl ?? t.pnl ?? 'x');
      return sum + (isNaN(v) ? 0 : v);
    }, 0);
  applyDailyPnl('jPnlToday',     todayPnlJ);
  applyDailyPnl('jPnlYesterday', dp.yesterday);
  applyDailyPnl('jPnlWeek',      dp.this_week);

  // Stats row
  setText('jTotalTrades', stats.total || 0);
  // Bug 7: win rate — only WIN + LOSS in denominator (exclude OPEN, BREAKEVEN)
  const jClosedCount = trades.filter(t => t.outcome === 'WIN' || t.outcome === 'LOSS').length;
  const jWinCount    = trades.filter(t => t.outcome === 'WIN').length;
  const wr = jClosedCount > 0 ? Math.round(jWinCount / jClosedCount * 1000) / 10 : 0;
  const wrEl = document.getElementById('jWinRate');
  if (wrEl) { wrEl.textContent = wr + '%'; wrEl.style.color = wr >= 55 ? 'var(--green)' : wr >= 45 ? 'var(--yellow)' : 'var(--red)'; }
  setText('jWinRateSub', `${stats.wins||0}W / ${stats.losses||0}L / ${stats.breakevens||0}BE`);
  const pf = stats.profit_factor || 0;
  const pfEl = document.getElementById('jProfitFactor');
  if (pfEl) { pfEl.textContent = pf.toFixed(2); pfEl.style.color = pf >= 1.5 ? 'var(--green)' : pf >= 1.0 ? 'var(--yellow)' : 'var(--red)'; }
  setText('jAvgWinLoss', `Avg W: ${stats.avg_win ? '$'+stats.avg_win : '—'} / Avg L: ${stats.avg_loss ? '$'+stats.avg_loss : '—'}`);
  setText('jBestRegime', stats.best_regime || '—');
  setText('jWorstRegime', 'Worst: ' + (stats.worst_regime || '—'));

  // Filter bar
  const filterLabels = {all:'All Time', week:'This Week', month:'This Month'};
  setHtml('jFilterBar', '<span style="font-size:9px;color:var(--muted2);letter-spacing:1.2px;text-transform:uppercase">Filter:</span>'
    + Object.entries(filterLabels).map(([f,label]) =>
        `<button class="j-filter-btn${journalFilter===f?' active':''}" onclick="setJournalFilter('${f}')">${label}</button>`
      ).join(''));

  // Annotate original indices then filter by selected period
  const now = new Date();
  const indexed = trades.map((t, i) => ({t, origIdx: i}));
  const filtered = indexed.filter(({t}) => {
    if (journalFilter === 'all') return true;
    const ds = t.trade_date || (t.timestamp ? t.timestamp.substring(0,10) : '');
    if (!ds) return true;
    const d = new Date(ds + 'T12:00:00');
    if (journalFilter === 'week') {
      const mon = new Date(now);
      mon.setDate(mon.getDate() - ((mon.getDay() + 6) % 7));
      mon.setHours(0,0,0,0);
      return d >= mon;
    }
    if (journalFilter === 'month') {
      return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
    }
    return true;
  });

  // Group by date, newest date first, newest trade first within each date
  const grouped = {};
  filtered.forEach(({t, origIdx}) => {
    const dk = t.trade_date || (t.timestamp ? t.timestamp.substring(0,10) : 'Unknown');
    if (!grouped[dk]) grouped[dk] = [];
    grouped[dk].push({t, origIdx});
  });
  const sortedDates = Object.keys(grouped).sort((a,b) => b.localeCompare(a));

  let rows = '';
  if (sortedDates.length === 0) {
    rows = `<tr><td colspan="15" class="neutral" style="text-align:center;padding:20px">${trades.length ? 'No trades in this period.' : 'No trades logged yet. Log your first trade using the form.'}</td></tr>`;
  } else {
    sortedDates.forEach(dk => {
      const dayItems = grouped[dk].slice().reverse();
      const count = dayItems.length;
      rows += `<tr class="j-date-header"><td colspan="15">${fmtDateHeader(dk)}<span style="opacity:.5;font-weight:400;margin-left:10px">· ${count} trade${count!==1?'s':''}</span></td></tr>`;
      dayItems.forEach(({t, origIdx}) => {
        const outcome = (t.outcome || '').toUpperCase();
        const rawPnl = t.realized_pnl !== undefined && t.realized_pnl !== null ? t.realized_pnl : (t.pnl || 0);
        const pnl = parseFloat(rawPnl) || 0;
        const dir = (t.direction || '').toUpperCase();
        const pnlColor = pnl > 0 ? 'var(--green)' : pnl < 0 ? 'var(--red)' : 'var(--yellow)';
        const dirColor = dir === 'LONG' ? 'var(--green)' : 'var(--red)';
        const timeStr = fmtTimeET(t.timestamp);
        const datDisp = t.trade_date || (t.timestamp ? t.timestamp.substring(0,10) : '—');
        const vColor = t.harvey_verdict === 'BUY' ? 'var(--green)' : t.harvey_verdict === 'SELL' ? 'var(--red)' : 'var(--yellow)';
        const pnlStr = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(2);
        const entryDisp = t.entry_price !== null && t.entry_price !== undefined ? formatPrice(t.entry_price, 2) : '—';
        const exitDisp  = t.exit_price  !== null && t.exit_price  !== undefined ? formatPrice(t.exit_price,  2) : '—';
        rows += `<tr>
          <td style="font-size:11px;color:var(--muted2);white-space:nowrap">${datDisp}</td>
          <td style="font-size:11px;color:var(--muted2);white-space:nowrap">${timeStr}</td>
          <td style="font-family:Rajdhani,sans-serif;font-size:16px;font-weight:700">${t.ticker||'—'}</td>
          <td style="color:${dirColor};font-weight:700;font-size:12px">${dir}</td>
          <td>${entryDisp}</td>
          <td>${exitDisp}</td>
          <td>${t.size||'—'}</td>
          <td style="color:${pnlColor};font-weight:700">${pnlStr}</td>
          <td style="font-size:12px;color:var(--muted)">${t.setup_type||'—'}</td>
          <td style="font-size:11px">${t.active_regime||'—'}</td>
          <td style="font-size:11px">${(t.session||'—').replace(/_/g,' ')}</td>
          <td style="font-family:Rajdhani,sans-serif;font-size:15px;font-weight:700">${t.bias_score||'—'}</td>
          <td style="font-size:11px;color:${vColor};font-weight:700">${t.harvey_verdict||'—'}</td>
          <td><span class="risk-badge outcome-${outcome}" style="font-size:10px;padding:3px 7px">${outcome}</span></td>
          <td><button class="del-btn" onclick="deleteTrade(${origIdx})" title="Delete">✕</button></td>
        </tr>`;
      });
    });
  }
  setHtml('journalTableBody', rows);

  // Regime breakdown
  const byRegime = stats.by_regime || {};
  const regimeColorMap = {TRENDING:'var(--green)',RANGING:'var(--blue)',EVENT_DRIVEN:'var(--yellow)',RISK_OFF:'var(--red)',CONSOLIDATING:'var(--muted2)'};
  const regimeCards = Object.entries(byRegime).sort((a,b) => b[1].win_rate - a[1].win_rate);
  setHtml('regimeBreakdownGrid', regimeCards.length ? regimeCards.map(([regime, rb]) => {
    const rwr = rb.win_rate || 0;
    const rc = rwr >= 55 ? 'var(--green)' : rwr >= 45 ? 'var(--yellow)' : 'var(--red)';
    const rtotal = (rb.wins||0) + (rb.losses||0) + (rb.breakevens||0);
    const borderC = regimeColorMap[regime] || 'var(--line)';
    return `<div class="regime-card" style="border-color:${borderC}44">
      <div class="rc-name" style="color:${borderC}">${regime}</div>
      <div class="rc-wr" style="color:${rc}">${rwr}%</div>
      <div class="rc-sub">${rb.wins}W · ${rb.losses}L · ${rtotal} trades</div>
    </div>`;
  }).join('') : '<div class="regime-card"><div class="rc-sub">No trades yet.</div></div>');

  // Session breakdown
  const bySession = stats.by_session || {};
  const sessionCards = Object.entries(bySession).sort((a,b) => b[1].win_rate - a[1].win_rate);
  setHtml('sessionBreakdownGrid', sessionCards.length ? sessionCards.map(([sess, sb]) => {
    const swr = sb.win_rate || 0;
    const sc = swr >= 55 ? 'var(--green)' : swr >= 45 ? 'var(--yellow)' : 'var(--red)';
    const stotal = (sb.wins||0) + (sb.losses||0) + (sb.breakevens||0);
    return `<div class="regime-card">
      <div class="rc-name">${sess.replace(/_/g,' ')}</div>
      <div class="rc-wr" style="color:${sc}">${swr}%</div>
      <div class="rc-sub">${sb.wins}W · ${sb.losses}L · ${stotal} trades</div>
    </div>`;
  }).join('') : '<div class="regime-card"><div class="rc-sub">No trades yet.</div></div>');
}

async function refreshJournal() {
  try {
    const res = await fetch('/journal/data');
    if (!res.ok) return;
    const data = await res.json();
    renderJournal(data);
  } catch(e) { console.error('Journal refresh error:', e); }
}

async function deleteTrade(index) {
  if (!confirm('Delete this trade entry?')) return;
  try {
    const res = await fetch('/journal/delete', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({index})
    });
    const data = await res.json();
    if (data.status === 'ok') refreshJournal();
  } catch(e) { console.error(e); }
}

document.getElementById('jSubmitBtn').addEventListener('click', async () => {
  const ticker        = (document.getElementById('jTicker').value || '').trim().toUpperCase();
  const direction     = document.getElementById('jDirection').value;
  const outcome       = document.getElementById('jOutcome').value;
  const realizedRaw   = document.getElementById('jRealizedPnl').value;
  const realized_pnl  = realizedRaw !== '' ? parseFloat(realizedRaw) : null;
  const entryRaw      = document.getElementById('jEntry').value;
  const exitRaw       = document.getElementById('jExit').value;
  const entry_price   = entryRaw !== '' ? parseFloat(entryRaw) : null;
  const exit_price    = exitRaw  !== '' ? parseFloat(exitRaw)  : null;
  const size          = parseFloat(document.getElementById('jSize').value) || 1;
  const setup_type    = (document.getElementById('jSetup').value || '').trim();
  const notes         = (document.getElementById('jNotes').value || '').trim();
  const trade_date    = document.getElementById('jDate').value || '';

  const msgEl = document.getElementById('jFormMsg');
  function showMsg(text, color) {
    msgEl.style.display = 'block';
    msgEl.style.color = color;
    msgEl.textContent = text;
  }

  if (!ticker) { showMsg('Ticker is required.', 'var(--red)'); return; }
  if (realized_pnl === null && (entry_price === null || exit_price === null)) {
    showMsg('Enter Realized P&L or both Entry and Exit prices.', 'var(--red)');
    return;
  }

  const btn = document.getElementById('jSubmitBtn');
  btn.disabled = true; btn.textContent = 'LOGGING...';
  msgEl.style.display = 'none';

  try {
    const payload = {ticker, direction, outcome, size, setup_type, notes, trade_date};
    if (realized_pnl !== null) payload.realized_pnl = realized_pnl;
    if (entry_price  !== null) payload.entry_price   = entry_price;
    if (exit_price   !== null) payload.exit_price    = exit_price;
    const res = await fetch('/journal/add', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === 'ok') {
      ['jTicker','jRealizedPnl','jEntry','jExit','jSize','jSetup','jNotes'].forEach(id => { document.getElementById(id).value = ''; });
      document.getElementById('jDate').value = todayDateStr();
      showMsg('Trade logged.', 'var(--green)');
      setTimeout(() => { msgEl.style.display = 'none'; }, 3000);
      refreshJournal();
    } else {
      showMsg('Error: ' + (data.detail || 'Unknown error'), 'var(--red)');
    }
  } catch(e) {
    showMsg('Connection error.', 'var(--red)');
  }
  btn.disabled = false; btn.textContent = 'LOG TRADE';
});

['jTicker','jRealizedPnl','jEntry','jExit','jSize','jSetup','jNotes'].forEach(id => {
  document.getElementById(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('jSubmitBtn').click();
  });
});

// ════════ BOOT ════════
function todayDateStr() {
  const t = new Date();
  return `${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,'0')}-${String(t.getDate()).padStart(2,'0')}`;
}
document.getElementById('jDate').value = todayDateStr();

// First-load fade-in — applies once, removed after animation completes
document.body.classList.add('donna-first-load');
document.body.addEventListener('animationend', () => document.body.classList.remove('donna-first-load'), { once: true });

initTileEditors();
refresh();
setInterval(refresh, 30000);
refreshJournal();
setInterval(refreshJournal, 60000);
refreshExecMonitor();
refreshSessionScorecard();
setInterval(refreshExecMonitor, 20000);
setInterval(refreshSessionScorecard, 20000);
refreshGrokIntelligence();
setInterval(refreshGrokIntelligence, 5 * 60 * 1000);
refreshNewsFuturesStrip();
setInterval(refreshNewsFuturesStrip, 30000);
refreshTrendingMovers();
setInterval(refreshTrendingMovers, 5 * 60 * 1000);
refreshEconCalendar();
setInterval(refreshEconCalendar, 5 * 60 * 1000);
refreshHarvey();
setInterval(refreshHarvey, 10000);
fetchStateEngine();
setInterval(fetchStateEngine, 15000);
fetchExecutionGate();
setInterval(fetchExecutionGate, 15000);
fetchHarveyData();
setInterval(fetchHarveyData, 20000);
fetchGrokIntel();
setInterval(fetchGrokIntel, 5 * 60 * 1000);
dashClock();
setInterval(dashClock, 1000);
refreshHvAlerts();
setInterval(refreshHvAlerts, 30000);
refreshHvExec();
setInterval(refreshHvExec, 20000);
refreshHvSectors();
setInterval(refreshHvSectors, 60000);
connectSSE();
</script>
</body>
</html>'''
