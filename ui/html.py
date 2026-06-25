"""donna_html.py — DASHBOARD_HTML template."""
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>NOVA v5.0</title>
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
</style>
</head>
<body>
<div class="wrap">

  <!-- TOPBAR -->
  <div class="topbar">
    <div class="brand">
      <h1>NOVA</h1>
      <span class="brand-tag">v5.0 // LIVE MARKET CORE</span>
    </div>
    <div class="top-right">
      <div class="nav">
        <button class="tab-btn active" data-page="dashboard">Dashboard</button>
        <button class="tab-btn" data-page="alerts">Alerts<span class="signal-dot" id="feedUnreadDot" style="display:none"></span></button>
        <button class="tab-btn" data-page="journal">Journal</button>
        <button class="tab-btn" data-page="news">News</button>
        <button class="tab-btn" data-page="assistant">Assistant</button>
        <button class="tab-btn harvey-btn" data-page="harvey">H.A.R.V.E.Y<span class="signal-dot" id="harveySignalDot"></span></button>
        <button class="tab-btn" data-page="execution">EXECUTION</button>
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
          <div class="kicker" style="margin-bottom:10px">MACRO RADAR</div>
          <div id="sidebarEconCalendar"></div>
        </div>

        <!-- NOVA SAYS -->
        <div id="dbDonnaSays" class="panel">
          <div class="kicker" style="margin-bottom:8px">NOVA SAYS</div>
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

          <!-- 3. MACRO RADAR -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">Macro Radar</div>
            <div id="sidebarEconCalendar2"><div class="econ-no-events">Loading events...</div></div>
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

          <!-- 5. NOVA SAYS -->
          <div class="donna-says-box">
            <div class="donna-says-label">NOVA Says</div>
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

        <!-- NOVA HEADER -->
        <div class="donna-header">
          <div class="donna-logo">NOVA</div>
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

      <!-- ── HARVEY SUB-NAV ── -->
      <div class="j-subnav">
        <button class="j-subnav-btn active" id="hvTab-harvey" onclick="switchHvSubTab(\'harvey\')">HARVEY</button>
        <button class="j-subnav-btn" id="hvTab-mr" onclick="switchHvSubTab(\'mr\')">MARKET REALITY</button>
        <button class="j-subnav-btn" id="hvTab-draws" onclick="switchHvSubTab(\'draws\')">DRAWS</button>
      </div>

      <!-- ── HARVEY SECTION ── -->
      <div id="hv-section-harvey">

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

          <!-- 3. INTELLIGENCE SUMMARY -->
          <div class="panel" style="padding:16px 20px">
            <div class="kicker" style="color:var(--blue);margin-bottom:10px">Intelligence Summary</div>
            <div class="hv-intel-grid">
              <div class="hv-intel-row">
                <span class="hv-intel-label">THESIS</span>
                <span class="hv-intel-val" id="hvIntelThesis">—</span>
              </div>
              <div class="hv-intel-row">
                <span class="hv-intel-label">DRAW</span>
                <span class="hv-intel-val" id="hvIntelDraw">—</span>
              </div>
              <div class="hv-intel-row">
                <span class="hv-intel-label">RVOL</span>
                <span class="hv-intel-val" id="hvIntelRvol">—</span>
              </div>
              <div class="hv-intel-row">
                <span class="hv-intel-label">MR2</span>
                <span class="hv-intel-val" id="hvIntelMr2">—</span>
              </div>
              <div class="hv-intel-row">
                <span class="hv-intel-label">WATCH</span>
                <span class="hv-intel-val" id="hvIntelWatch">—</span>
              </div>
            </div>
          </div>

          <!-- 4. DONNA'S PLAYBOOK -->
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

          <!-- 4. NOVA SAYS -->
          <div class="hv-donna-says">
            <span class="hv-donna-says-label">NOVA Says</span>
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

      </div><!-- /hv-section-harvey -->

      <!-- ── MARKET REALITY SECTION ── -->
      <div id="hv-section-mr" style="display:none">
      <div class="panel" style="padding:16px 20px">
        <div class="gov-header-row">
          <div>
            <div class="mr-page-title">MARKET REALITY</div>
            <div class="fd-meta" style="margin-top:3px">Fact-based objective market state · MR2 engine · no narrative</div>
          </div>
          <div style="display:flex;align-items:center;gap:10px">
            <span class="fd-meta" id="mrLastUpdated">—</span>
            <button class="fd-refresh-btn" onclick="refreshMarketReality()">↻ REFRESH</button>
          </div>
        </div>

        <!-- State + block flags -->
        <div style="margin-bottom:14px">
          <div id="mrStateBadge" class="mr-state-badge mr-state-neutral">—</div>
          <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap" id="mrBlockFlags">
            <span class="mr-block-flag mr-block-clear">LONGS CLEAR</span>
            <span class="mr-block-flag mr-block-clear">SHORTS CLEAR</span>
          </div>
        </div>

        <!-- Price grid -->
        <div class="mr-grid" id="mrGrid">
          <div class="mr-cell"><div class="mr-cell-label">NQ PRICE</div><div class="mr-cell-val" id="mrNqPrice">—</div><div class="mr-cell-sub" id="mrNqPct">—</div></div>
          <div class="mr-cell"><div class="mr-cell-label">ES PRICE</div><div class="mr-cell-val" id="mrEsPrice">—</div><div class="mr-cell-sub" id="mrEsPct">—</div></div>
          <div class="mr-cell"><div class="mr-cell-label">VIX</div><div class="mr-cell-val" id="mrVix">—</div><div class="mr-cell-sub" id="mrVixSub">volatility index</div></div>
          <div class="mr-cell"><div class="mr-cell-label">MR2 SCORE</div><div class="mr-cell-val" id="mrScore">—</div><div class="mr-cell-sub">bull − bear points</div><div class="mr-score-bar"><div class="mr-score-fill-bull" id="mrScoreBar" style="width:50%"></div></div></div>
          <div class="mr-cell"><div class="mr-cell-label">SESSION</div><div class="mr-cell-val" id="mrSession" style="font-size:14px">—</div><div class="mr-cell-sub" id="mrRegime">—</div></div>
          <div class="mr-cell"><div class="mr-cell-label">WEEKLY STRUCTURE</div><div class="mr-cell-val" id="mrWeekly" style="font-size:14px">—</div><div class="mr-cell-sub" id="mrDisplacement">—</div></div>
        </div>

        <!-- Fact breakdown -->
        <div style="margin-top:16px">
          <div class="fd-meta" style="letter-spacing:2px;margin-bottom:8px">FACT BREAKDOWN</div>
          <div id="mrFactBreakdown" style="font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2);line-height:2">Loading...</div>
        </div>

        <!-- Block reason -->
        <div id="mrBlockReasonWrap" style="display:none;margin-top:12px;padding:10px 14px;border-radius:9px;border:1px solid rgba(255,68,68,.2);background:rgba(255,68,68,.04)">
          <div class="fd-meta" style="margin-bottom:4px;letter-spacing:1px">BLOCK REASON</div>
          <div id="mrBlockReason" style="font-size:11px;color:var(--muted);line-height:1.5"></div>
        </div>
      </div>
      </div><!-- /hv-section-mr -->

      <!-- ── DRAWS SECTION ── -->
      <div id="hv-section-draws" style="display:none">
        <div class="panel" style="padding:24px">
          <div class="kicker" style="margin-bottom:8px">DRAW VALIDATION</div>
          <div style="font-size:13px;color:var(--muted);line-height:1.6">
            Draw validation telemetry is being collected via the signal log
            (<code style="font-family:\'Space Mono\',monospace;font-size:10px;color:var(--gold)">draw_category</code>,
            <code style="font-family:\'Space Mono\',monospace;font-size:10px;color:var(--gold)">draw_independent</code>,
            <code style="font-family:\'Space Mono\',monospace;font-size:10px;color:var(--gold)">draw_tp1_pts</code>).
            <br><br>
            Categories tracked: <strong>STRONG</strong> · <strong>CONDITIONAL</strong> · <strong>CIRCULAR</strong><br>
            <br>
            Full draw analysis dashboard will be built after observation phase completes.
          </div>
        </div>
      </div><!-- /hv-section-draws -->

    </div>
  </div>


  <!-- TRADE DETAIL MODAL -->
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

  <div class="page" id="page-execution">
    <div class="vstack">

      <!-- ── HEARTBEAT BAR ── -->
      <div class="exec-heartbeat">
        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
          <div class="exec-pulse offline" id="novaPulse"></div>
          <span class="exec-hb-label" id="novaStatusLabel">CONNECTING</span>
        </div>
        <div class="exec-hb-sep"></div>
        <span class="exec-hb-chip" id="novaSessionChip">SESSION</span>
        <span class="exec-hb-chip" id="novaMacroChip">MACRO —</span>
        <span class="exec-hb-chip" id="novaRedFolderChip">RED FOLDER —</span>
        <span class="exec-hb-chip" id="novaThesisChip">THESIS —</span>
        <div style="flex:1"></div>
        <span style="font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2);white-space:nowrap" id="novaLastSync">—</span>
      </div>

      <!-- ── EXECUTION CENTER SUB-NAV ── -->
      <div class="j-subnav">
        <button class="j-subnav-btn active" id="ecTab-execution" onclick="switchEcTab(\'execution\')">EXECUTION</button>
        <button class="j-subnav-btn" id="ecTab-governance" onclick="switchEcTab(\'governance\')">GOVERNANCE</button>
        <button class="j-subnav-btn" id="ecTab-audit" onclick="switchEcTab(\'audit\')">AUDIT</button>
      </div>

      <!-- ── EXECUTION ── -->
      <div id="ec-section-execution">
        <div class="exec-state-grid">

          <!-- Current State -->
          <div class="panel">
            <div class="kicker">NOVA EXECUTION STATE</div>
            <div id="novaPnlHero" class="exec-pnl-hero" style="color:var(--muted2)">—</div>
            <div class="exec-kv">
              <span class="exec-kv-lab">Active Thesis</span>
              <span class="exec-kv-val" id="novaThesisVal">—</span>
            </div>
            <div class="exec-kv">
              <span class="exec-kv-lab">Market Regime</span>
              <span class="exec-kv-val" id="novaRegimeVal">—</span>
            </div>
            <div class="exec-kv">
              <span class="exec-kv-lab">Session</span>
              <span class="exec-kv-val" id="novaSessionVal">—</span>
            </div>
            <div class="exec-kv">
              <span class="exec-kv-lab">Trades Today</span>
              <span class="exec-kv-val" id="novaTradesVal">—</span>
            </div>
            <div class="exec-kv">
              <span class="exec-kv-lab">Risk Used</span>
              <span class="exec-kv-val" id="novaRiskVal">—</span>
            </div>
            <div class="exec-kv">
              <span class="exec-kv-lab">Open Exposure</span>
              <span class="exec-kv-val" id="novaExposureVal">FLAT</span>
            </div>
          </div>

          <!-- Governance State -->
          <div class="panel">
            <div class="kicker">GOVERNANCE STATE</div>
            <div style="font-size:12px;color:var(--muted);margin-bottom:14px">Active locks and cooldowns constraining execution.</div>
            <div class="exec-kv">
              <span class="exec-kv-lab">Execution Gate</span>
              <span class="exec-kv-val" id="novaCanExec">—</span>
            </div>
            <div class="exec-kv">
              <span class="exec-kv-lab">Macro Lock</span>
              <span class="exec-kv-val" id="novaMacroLock">—</span>
            </div>
            <div class="exec-kv">
              <span class="exec-kv-lab">Red Folder</span>
              <span class="exec-kv-val" id="novaRedFolderVal">—</span>
            </div>
            <div class="exec-kv">
              <span class="exec-kv-lab">SPY Cooldown</span>
              <span class="exec-kv-val mono" id="novaSpyCooldown">—</span>
            </div>
            <div class="exec-kv">
              <span class="exec-kv-lab">QQQ Cooldown</span>
              <span class="exec-kv-val mono" id="novaQqqCooldown">—</span>
            </div>
            <div class="exec-kv">
              <span class="exec-kv-lab">Thesis Age</span>
              <span class="exec-kv-val mono" id="novaThesisAge">—</span>
            </div>
          </div>
        </div>

        <!-- ── OPEN POSITIONS — broker reality first ── -->
        <div class="panel" style="margin-top:16px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">
            <div>
              <div class="kicker">OPEN POSITIONS</div>
              <div style="font-size:12px;color:var(--muted);margin-bottom:14px">Live Alpaca broker state — every open position, matched against NOVA's journal. A position can exist here with no journal entry; that gap is shown, never hidden.</div>
            </div>
            <div id="novaCloseAllWrap" style="display:none">
              <button class="submit-trade-btn" id="novaCloseAllBtn" style="width:auto;padding:8px 18px;font-size:11px;margin:0;background:var(--red);border-color:var(--red);color:#fff" onclick="closeAllPositionsConfirm()">CLOSE ALL POSITIONS</button>
            </div>
          </div>
          <div id="novaPositionsList">
            <div style="color:var(--muted2);font-size:12px;font-style:italic">Loading...</div>
          </div>
        </div>
      </div>

      <!-- ── GOVERNANCE ── -->
      <div id="ec-section-governance" style="display:none">
        <div class="panel" style="padding:16px 20px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
            <div>
              <div class="kicker" style="margin-bottom:2px">EXECUTION GATES</div>
              <div style="font-size:12px;color:var(--muted)">All execution gates · live state · no assumptions</div>
            </div>
            <div style="display:flex;align-items:center;gap:10px">
              <span class="fd-meta" id="govLastUpdated">—</span>
              <button class="fd-refresh-btn" onclick="refreshGovernance()">↻ REFRESH</button>
            </div>
          </div>

          <div class="gov-section-label">SYSTEM GATES</div>
          <div class="gov-gate-list" id="govSystemGates">
            <div class="gov-gate"><span class="gov-gate-name">Loading...</span></div>
          </div>

          <div class="gov-section-label">RISK GATES</div>
          <div class="gov-gate-list" id="govRiskGates">
            <div class="gov-gate"><span class="gov-gate-name">Loading...</span></div>
          </div>

          <div class="gov-section-label">POSITION GATES</div>
          <div class="gov-gate-list" id="govPositionGates">
            <div class="gov-gate"><span class="gov-gate-name">Loading...</span></div>
          </div>

          <div class="gov-section-label">COOLDOWNS</div>
          <div class="gov-gate-list" id="govCooldowns">
            <div class="gov-gate"><span class="gov-gate-name">Loading...</span></div>
          </div>

          <div id="govLockoutsWrap" style="display:none;margin-top:8px">
            <div class="gov-section-label">RECENT LOCKOUTS</div>
            <div class="gov-lockouts" id="govLockouts"></div>
          </div>

          <div id="govBlockedWrap" style="display:none;margin-top:8px">
            <div class="gov-section-label">BLOCKED SIGNALS TODAY</div>
            <div class="gov-lockouts" id="govBlocked"></div>
          </div>
        </div>
      </div>

      <!-- ── AUDIT ── -->
      <div id="ec-section-audit" style="display:none">

        <div class="panel">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;gap:12px;flex-wrap:wrap">
            <div>
              <div class="kicker" style="margin-bottom:4px">REJECTION INTELLIGENCE</div>
              <div class="section-title">Blocked Signal Flow</div>
              <div style="font-size:12px;color:var(--muted);margin-top:4px">Every blocked signal is logged. NOVA is self-aware.</div>
            </div>
            <div style="text-align:right;flex-shrink:0">
              <div style="font-family:\'Rajdhani\',sans-serif;font-size:36px;font-weight:700;line-height:1;color:var(--text)" id="rejTodayCount">—</div>
              <div style="font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2);letter-spacing:1px;text-transform:uppercase;margin-top:2px">blocked today</div>
            </div>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start">
            <div>
              <div style="font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1.2px;color:var(--muted2);text-transform:uppercase;margin-bottom:10px">Last Blocked Signal</div>
              <div id="rejLastCard">
                <div style="color:var(--muted2);font-size:12px;font-style:italic">No rejections logged yet.</div>
              </div>
            </div>
            <div>
              <div style="font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1.2px;color:var(--muted2);text-transform:uppercase;margin-bottom:10px">Top Rejection Reasons</div>
              <div id="rejBreakdownList">
                <div style="color:var(--muted2);font-size:12px;font-style:italic">—</div>
              </div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
            <div>
              <div class="kicker" style="margin-bottom:4px">SESSION SCORECARD</div>
              <div class="section-title">Execution Quality</div>
            </div>
            <span id="novaGrade" style="font-family:\'Rajdhani\',sans-serif;font-size:48px;font-weight:700;line-height:1;color:var(--muted2)">—</span>
          </div>

          <div class="sc2-cells">
            <div class="sc2-cell">
              <div class="sc2-num" id="sc2Taken" style="color:var(--text)">0</div>
              <div class="sc2-lab">Taken</div>
            </div>
            <div class="sc2-cell">
              <div class="sc2-num" id="sc2Blocked" style="color:var(--muted2)">—</div>
              <div class="sc2-lab">Blocked Today</div>
            </div>
            <div class="sc2-cell">
              <div class="sc2-num" id="sc2WinRate" style="color:var(--muted2)">—</div>
              <div class="sc2-lab">Win Rate</div>
            </div>
            <div class="sc2-cell">
              <div class="sc2-num" id="sc2Pnl" style="color:var(--muted2)">—</div>
              <div class="sc2-lab">P&amp;L Today</div>
            </div>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
            <div class="sc2-detail-cell">
              <div class="exec-kv-lab" style="display:block;margin-bottom:6px">Best Trade</div>
              <div class="exec-kv-val" id="sc2Best" style="text-align:left">—</div>
            </div>
            <div class="sc2-detail-cell">
              <div class="exec-kv-lab" style="display:block;margin-bottom:6px">Worst Trade</div>
              <div class="exec-kv-val" id="sc2Worst" style="text-align:left">—</div>
            </div>
            <div class="sc2-detail-cell">
              <div class="exec-kv-lab" style="display:block;margin-bottom:6px">Governance Actions</div>
              <div class="exec-kv-val mono" id="sc2GovActions" style="text-align:left">—</div>
            </div>
          </div>
        </div>

      </div>

    </div>
  </div>

  <!-- ════════════════════ ALERTS ════════════════════ -->
  <div class="page" id="page-alerts">
    <div class="vstack">
      <div class="panel" style="padding:16px 20px">

        <!-- Header -->
        <div class="fd-page-header">
          <div>
            <div class="fd-page-title">ALERTS</div>
            <div class="fd-meta" style="margin-top:3px">Intelligence · Executions · Governance · System events</div>
          </div>
          <div style="display:flex;align-items:center;gap:10px">
            <span class="fd-meta" id="fdLastUpdated">—</span>
            <button class="fd-refresh-btn" onclick="refreshFeed()">↻ REFRESH</button>
          </div>
        </div>

        <!-- Stats row -->
        <div class="fd-stats-row" id="fdStatsRow">
          <span class="fd-stat" style="color:var(--muted2)">Loading...</span>
        </div>

        <!-- Category filter -->
        <div class="fd-filter-bar">
          <span class="fd-meta" style="margin-right:2px">CATEGORY</span>
          <button class="fd-filter-btn active" data-fd-cat="all" onclick="setFdCat(\'all\',this)">ALL</button>
          <button class="fd-filter-btn" data-fd-cat="intelligence" onclick="setFdCat(\'intelligence\',this)">INTELLIGENCE</button>
          <button class="fd-filter-btn" data-fd-cat="execution" onclick="setFdCat(\'execution\',this)">EXECUTION</button>
          <button class="fd-filter-btn" data-fd-cat="system" onclick="setFdCat(\'system\',this)">SYSTEM</button>
          <button class="fd-filter-btn" data-fd-cat="market" onclick="setFdCat(\'market\',this)">MARKET</button>
        </div>

        <!-- Date / symbol filter -->
        <div class="fd-filter-bar">
          <span class="fd-meta" style="margin-right:2px">DATE</span>
          <button class="fd-filter-btn active" data-fd-date="today" onclick="setFdDate(\'today\',this)">TODAY</button>
          <button class="fd-filter-btn" data-fd-date="all" onclick="setFdDate(\'all\',this)">ALL TIME</button>
          <div class="fd-sep"></div>
          <span class="fd-meta" style="margin-right:2px">SYM</span>
          <button class="fd-filter-btn active" data-fd-sym="all" onclick="setFdSym(\'all\',this)">ALL</button>
          <button class="fd-filter-btn" data-fd-sym="ES" onclick="setFdSym(\'ES\',this)">ES</button>
          <button class="fd-filter-btn" data-fd-sym="NQ" onclick="setFdSym(\'NQ\',this)">NQ</button>
        </div>

        <!-- Notification banner (shown when permission not yet granted or blocked) -->
        <div class="fd-notify-banner" id="fdNotifBanner" style="display:none">
          <span id="fdNotifBannerText">Enable browser notifications for EXECUTION_READY and Grade A/B alerts</span>
          <button class="fd-notify-btn" id="fdNotifBannerBtn" onclick="requestFeedNotifPermission()">ENABLE NOTIFICATIONS</button>
        </div>

        <!-- Cards -->
        <div id="feedBody">
          <div class="fd-empty">Loading feed...</div>
        </div>

        <!-- Load more -->
        <div style="text-align:center;margin-top:10px;display:none" id="fdLoadMore">
          <button class="fd-load-btn" onclick="loadMoreFeed()">LOAD MORE</button>
        </div>

      </div><!-- /panel -->
    </div><!-- /vstack -->
  </div><!-- /page-alerts -->

  <!-- ════════════════════ JOURNAL ════════════════════ -->
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

  <!-- ════════════════════ GOVERNANCE ════════════════════ -->
  <!-- FOOTER -->
  <div class="footer">
    <span>NOVA v5.0 // LIVE MARKET CORE</span>
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
    if (btn.dataset.page === 'harvey') { refreshHarvey(); switchHvSubTab('harvey'); }
    if (btn.dataset.page === 'execution') { refreshExecutionTab(); refreshGovernance(); }
    if (btn.dataset.page === 'alerts') { _fdOffset = 0; _fdCards = []; clearFeedUnread(); refreshFeed(); }
    if (btn.dataset.page === 'journal') { refreshJournal(); switchJTab('trades'); }
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
  const _rawReason = lockouts.length ? lockouts[0].reason : '';
  const _reasonMap = {'MACRO_LOCK':'MACRO RISK HIGH','EOD_LOCK':'EOD LOCK ACTIVE','RED_FOLDER':'RED FOLDER ACTIVE','DAILY_LOSS':'DAILY LOSS LIMIT HIT','RISK_LIMIT':'RISK LIMIT REACHED'};
  const _reasonKey = Object.keys(_reasonMap).find(k => _rawReason.toUpperCase().includes(k)) || '';
  setText('dbExecReason', _reasonKey ? _reasonMap[_reasonKey] : _rawReason);
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

  // Intelligence summary
  renderIntelligencePanel(d);
}

function renderIntelligencePanel(d) {
  const intel = (d.intelligence) || {};
  const syn  = intel.synthesis    || {};
  const mr2  = intel.mr2          || {};
  const liq  = intel.liquidity    || {};
  const part = intel.participation || {};
  const mem  = intel.session_memory || {};

  // THESIS — state + confidence + market_thesis (truncated)
  const thState  = syn.thesis_state || '';
  const thConf   = syn.confidence   ? ' [' + syn.confidence + ']' : '';
  const thText   = (syn.market_thesis || '').substring(0, 90);
  const thSuffix = (syn.market_thesis || '').length > 90 ? '...' : '';
  const thStr    = thState ? thState + thConf + (thText ? ' — ' + thText + thSuffix : '') : '—';
  const thEl = document.getElementById('hvIntelThesis');
  if (thEl) {
    thEl.textContent = thStr;
    thEl.className = 'hv-intel-val' + (thState.includes('BULL') ? ' bull' : thState.includes('BEAR') ? ' bear' : '');
  }

  // DRAW — primary liquidity draw for NQ
  const liqNq   = (liq.nq || {});
  const draw    = liqNq.primary_draw || {};
  const dLabel  = draw.label || '';
  const dPts    = draw.distance_pts ? Math.round(Math.abs(parseFloat(draw.distance_pts))) + 'pts' : '';
  const dSide   = draw.side === 'BELOW' ? 'below' : draw.side === 'ABOVE' ? 'above' : '';
  const uAbove  = liqNq.untapped_above !== undefined ? liqNq.untapped_above : '—';
  const uBelow  = liqNq.untapped_below !== undefined ? liqNq.untapped_below : '—';
  const drawStr = dLabel ? dLabel + (dPts ? ' (' + dPts + ' ' + dSide + ')' : '') + ' — ' + uAbove + ' above / ' + uBelow + ' below untapped' : '—';
  setText('hvIntelDraw', drawStr);

  // RVOL — NQ RVOL + session type + bias
  const nqPart  = (part.nq || {});
  const rvolVal = nqPart.rvol ? parseFloat(nqPart.rvol).toFixed(2) + 'x' : '—';
  const sessT   = part.session_type || '—';
  const bias    = part.participation_bias || '—';
  const rvolEl  = document.getElementById('hvIntelRvol');
  if (rvolEl) {
    rvolEl.textContent = 'RVOL ' + rvolVal + ' — ' + sessT + ' — ' + bias;
    const rvolNum = parseFloat(nqPart.rvol || 0);
    rvolEl.className = 'hv-intel-val' + (rvolNum >= 1.5 ? ' bull' : rvolNum > 0 && rvolNum < 0.7 ? ' bear' : '');
  }

  // MR2 — state + score + fact counts
  const mr2State = mr2.state || '—';
  const mr2Score = mr2.score !== undefined ? mr2.score : '—';
  const bullF    = mr2.bull_fact_count !== undefined ? mr2.bull_fact_count : '—';
  const bearF    = mr2.bear_fact_count !== undefined ? mr2.bear_fact_count : '—';
  const mr2El    = document.getElementById('hvIntelMr2');
  if (mr2El) {
    mr2El.textContent = mr2State + ' (score ' + mr2Score + ') — ' + bullF + ' bull / ' + bearF + ' bear facts';
    mr2El.className = 'hv-intel-val' + (mr2State.includes('BULL') ? ' bull' : mr2State.includes('BEAR') ? ' bear' : mr2State === 'CONFLICTED' ? ' warn' : '');
  }

  // WATCH — thesis_condition or session narrative
  const condition = (syn.thesis_condition || '').trim();
  const narrative = (mem.rolling_narrative || '').trim();
  const watchRaw  = (condition && !condition.startsWith('Insufficient')) ? condition : (narrative || '—');
  const watchStr  = watchRaw.substring(0, 140) + (watchRaw.length > 140 ? '...' : '');
  setText('hvIntelWatch', watchStr);
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
    ddEl.textContent = dd.daily_pnl != null ? _fmtUsd(dd.daily_pnl) : '—';
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
// ════════ MACRO RADAR (Economic Calendar) ════════
function renderEconCalendar(events) {
  const targets = [
    document.getElementById('sidebarEconCalendar'),
    document.getElementById('sidebarEconCalendar2'),
  ].filter(Boolean);
  if (!targets.length) return;

  const nyNow    = new Date(new Date().toLocaleString('en-US', { timeZone:'America/New_York' }));
  const todayStr = nyNow.toISOString().slice(0,10);
  const nowMin   = nyNow.getHours() * 60 + nyNow.getMinutes();

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

  const byDate = {};
  (events || []).forEach(ev => {
    const k = (ev.date || todayStr).slice(0,10);
    if (!byDate[k]) byDate[k] = [];
    byDate[k].push(ev);
  });

  function _verdictHtml(ev) {
    const a = parseFloat(ev.actual), f = parseFloat(ev.forecast);
    if (isNaN(a) || isNaN(f) || f === 0) return '';
    const diff = (a - f) / Math.abs(f);
    if (diff >  0.05) return '<span class="mre-verdict hot">HOT</span>';
    if (diff < -0.05) return '<span class="mre-verdict miss">MISS</span>';
    return '<span class="mre-verdict inline">INLINE</span>';
  }

  function _countdown(evMin, hasActual, isToday) {
    if (!isToday) return null;
    const diff = evMin - nowMin;
    if (hasActual || diff < -45) return { label: 'RELEASED', cls: 'released' };
    if (diff < 0)               return { label: 'POST EVENT', cls: 'released' };
    if (diff === 0)             return { label: 'LIVE NOW',   cls: 'live' };
    if (diff <= 5)              return { label: 'IMMINENT',   cls: 'live' };
    if (diff <= 20)             return { label: `IN ${diff} MIN`, cls: 'soon' };
    if (diff <= 90)             return { label: `IN ${diff} MIN`, cls: 'upcoming' };
    const h = Math.floor(diff / 60), m = diff % 60;
    return { label: `IN ${h}h${m ? ` ${m}m` : ''}`, cls: 'future' };
  }

  function evCard(ev, isToday, isPast) {
    const imp      = (ev.importance || 'low').toLowerCase();
    const isHigh   = imp === 'high';
    const isMedium = imp === 'medium';
    const [hh, mm] = (ev.time_et || '00:00').split(':').map(Number);
    const evMin    = hh * 60 + mm;
    const hasActual = ev.actual != null && ev.actual !== '' && ev.actual !== '—';
    const cd       = _countdown(evMin, hasActual, isToday);
    const isLive   = cd && cd.cls === 'live';
    const isRel    = cd && cd.cls === 'released';
    // Past-day events are always displayed as released (dimmed, no governance bar)
    const displayRel = isRel || (isPast === true);

    // Data values row
    const valParts = [];
    if (hasActual)            valParts.push(`A: ${ev.actual}`);
    if (ev.forecast != null)  valParts.push(`F: ${ev.forecast}`);
    if (ev.previous != null && !hasActual) valParts.push(`P: ${ev.previous}`);
    const valsHtml    = valParts.length ? `<span class="mre-vals">${valParts.join(' · ')}</span>` : '';
    const verdictHtml = hasActual ? _verdictHtml(ev) : '';

    const cdHtml = cd ? `<span class="mre-countdown ${cd.cls}">${cd.label}</span>` : '';

    // LOW — compact inline row
    if (!isHigh && !isMedium) {
      return `<div class="macro-radar-event impact-low${displayRel?' released':''}">
  <div class="mre-compact">
    <span class="mre-compact-dot"></span>
    <span class="mre-time">${ev.time_et || '?'}</span>
    <span class="mre-compact-title">${ev.title || '—'}</span>
    ${valsHtml}
    ${cdHtml}
  </div>
</div>`;
    }

    // MEDIUM / HIGH — full card; govBar only for today's non-released events
    const govBar = isHigh && isToday && !displayRel
      ? `<div class="mre-gov-bar">⚠ RED FOLDER WINDOW · EXECUTION MAY LOCK DURING THIS EVENT</div>`
      : '';
    const cardCls = `macro-radar-event impact-${imp}${isLive ? ' live' : ''}${displayRel ? ' released' : ''}`;

    return `<div class="${cardCls}">
  <div class="mre-header impact-${imp}">
    <div class="mre-impact-badge ${imp}">
      <div class="mre-impact-dot ${imp}"></div>${imp.toUpperCase()}
    </div>
    ${cdHtml}
  </div>
  <div class="mre-body">
    <div class="${isHigh ? 'mre-title-high' : 'mre-title-med'}">${ev.title || '—'}</div>
    <div class="mre-meta-row">
      <span class="mre-time">${ev.time_et || '?'} ET</span>
      ${valsHtml}${verdictHtml}
    </div>
  </div>
  ${govBar}
</div>`;
  }

  let html = '';
  for (const ds of weekDays) {
    const dayEvts = (byDate[ds] || []).sort((a, b) => (a.time_et || '').localeCompare(b.time_et || ''));
    const isToday = ds === todayStr;
    const isPast  = ds < todayStr;
    if (!isToday && !dayEvts.length) continue;
    const todayLabel = `▶ TODAY · ${dayLabel(ds)}`;
    html += `<div class="mre-day-sep ${isToday ? 'today' : 'other'}">${isToday ? todayLabel : dayLabel(ds)}</div>`;
    if (dayEvts.length) {
      html += dayEvts.map(ev => evCard(ev, isToday, isPast)).join('');
    } else {
      html += '<div class="econ-no-events">No scheduled events</div>';
    }
  }

  const final = html || '<div class="econ-no-events">No events this week</div>';
  targets.forEach(el => { el.innerHTML = final; });
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

// ════════ EXECUTION TAB v2 ════════
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
function _fmtCount(v) {
  const n = parseInt(v, 10);
  if (v == null || isNaN(n)) return '—';
  return n.toLocaleString('en-US');
}
function _fmtPrice(v) {
  const n = parseFloat(v);
  if (v == null || isNaN(n)) return '—';
  return n.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
}
function _execGrade(winRate, todayPnl) {
  if (winRate >= 65 && todayPnl > 0) return 'A';
  if (winRate >= 50 && todayPnl >= 0) return 'B';
  if (winRate >= 40) return 'C';
  return 'D';
}
function _setChip(id, text, cls) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = 'exec-hb-chip' + (cls ? ' ' + cls : '');
}
function _setKv(id, text, color) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  if (color) el.style.color = color;
}

async function refreshExecutionTab() {
  try {
    // Parallel fetch: orchestration + execution-status + rejections + journal + positions
    const [orchRes, execRes, rejRes, jRes, posRes] = await Promise.all([
      fetch('/orchestration-status'),
      fetch('/execution-status'),
      fetch('/execution/rejections?limit=50'),
      fetch('/journal/data'),
      fetch('/execution/positions'),
    ]);

    const orch = orchRes.ok  ? await orchRes.json() : null;
    const exec = execRes.ok  ? await execRes.json() : null;
    const rej  = rejRes.ok   ? await rejRes.json()  : null;
    const j    = jRes.ok     ? await jRes.json()    : null;
    const pos  = posRes.ok   ? await posRes.json()  : null;

    _renderHeartbeat(orch, exec);
    _renderExecutionState(orch, exec);
    _renderGovernanceState(orch, exec);
    _renderRejections(rej);
    _renderSessionScorecard(j, rej);
    _renderPositionsTable(pos);

    const syncEl = document.getElementById('novaLastSync');
    if (syncEl) syncEl.textContent = 'Synced ' + new Date().toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:true}) + ' ET';
  } catch(e) {
    console.error('refreshExecutionTab failed:', e);
  }
}

function _renderHeartbeat(orch, exec) {
  const pulseEl = document.getElementById('novaPulse');
  const labelEl = document.getElementById('novaStatusLabel');

  const canExec   = orch?.can_execute !== false;
  const macroLock = orch?.macro_lock;
  const rfLock    = orch?.red_folder_lock;
  const daily     = exec?.daily_loss_limit_hit;

  let pulseClass = 'active', labelText = 'ACTIVE';
  if (daily || macroLock) { pulseClass = 'blocked'; labelText = 'BLOCKED'; }
  else if (rfLock)        { pulseClass = 'paused';  labelText = 'PAUSED'; }
  else if (!exec?.available) { pulseClass = 'offline'; labelText = 'OFFLINE'; }

  if (pulseEl) pulseEl.className = 'exec-pulse ' + pulseClass;
  if (labelEl) { labelEl.textContent = labelText; labelEl.style.color = pulseClass === 'active' ? 'var(--green)' : pulseClass === 'blocked' ? 'var(--red)' : pulseClass === 'paused' ? 'var(--gold)' : 'var(--muted2)'; }

  // Session chip
  const session = exec?.session || orch?.session || (_lastDashData?.risk?.donna_session) || '';
  const sessMap = {NEW_YORK_CASH:'NY CASH',LONDON:'LONDON',ASIA:'ASIA',OFF_HOURS:'OFF HOURS'};
  const sessColMap = {NEW_YORK_CASH:'green',LONDON:'blue',ASIA:'yellow',OFF_HOURS:''};
  _setChip('novaSessionChip', sessMap[session] || session || 'SESSION', sessColMap[session] || '');

  // Macro chip
  const macro = (_lastDashData?.risk?.macro_risk || '').toUpperCase();
  _setChip('novaMacroChip', 'MACRO ' + (macro || '—'), macro === 'HIGH' ? 'red' : macro === 'MEDIUM' ? 'yellow' : macro === 'LOW' ? 'green' : '');

  // Red folder chip
  _setChip('novaRedFolderChip', rfLock === true ? 'RED FOLDER ACTIVE' : rfLock === 'APPROACHING' ? 'RED FOLDER SOON' : 'RED FOLDER CLEAR', rfLock === true ? 'red' : rfLock === 'APPROACHING' ? 'yellow' : 'green');

  // Thesis chip
  const thesis = orch?.active_thesis || '—';
  const thesisDir = orch?.thesis_direction || '';
  _setChip('novaThesisChip', 'THESIS ' + thesis + (thesisDir ? ' ' + thesisDir : ''), thesis === 'NEUTRAL' || thesis === '—' ? '' : 'blue');
}

function _renderExecutionState(orch, exec) {
  const pnl = exec?.current_pnl_today ?? exec?.account?.pnl_today;
  const pnlEl = document.getElementById('novaPnlHero');
  if (pnlEl) {
    pnlEl.textContent = _fmtPnl(pnl);
    const n = parseFloat(pnl);
    pnlEl.style.color = isNaN(n) ? 'var(--muted2)' : n >= 0 ? 'var(--green)' : 'var(--red)';
  }

  const thesis = orch?.active_thesis || '—';
  const thesisDir = orch?.thesis_direction || '';
  _setKv('novaThesisVal', thesis + (thesisDir ? ' · ' + thesisDir : ''), thesis === 'NEUTRAL' || thesis === '—' ? 'var(--muted2)' : 'var(--blue)');

  const regime = (_lastDashData?.risk?.active_regime) || exec?.regime || '—';
  const rCol = {TRENDING_UP:'var(--green)',TRENDING_DOWN:'var(--red)',RANGING:'var(--yellow)',VOLATILE:'var(--red)',EVENT_DRIVEN:'var(--gold)',UNKNOWN:'var(--muted2)'};
  _setKv('novaRegimeVal', regime.replace(/_/g,' '), rCol[regime] || 'var(--text)');

  const session = exec?.session || (_lastDashData?.risk?.donna_session) || '';
  const sessMap = {NEW_YORK_CASH:'NY CASH',LONDON:'LONDON',ASIA:'ASIA',OFF_HOURS:'OFF HOURS'};
  _setKv('novaSessionVal', sessMap[session] || session || '—');

  _setKv('novaTradesVal', exec?.daily_trades_taken != null ? exec.daily_trades_taken + ' today' : '—');
  _setKv('novaRiskVal', exec?.risk_used_today != null ? _fmtUsd(exec.risk_used_today) + ' / $1,000' : '—');

  const positions = orch?.open_positions || [];
  const liveExp   = orch?.live_alpaca_exposure || [];
  const posStr = positions.length ? positions.map(p => (p.symbol || p.ticker || '?') + (p.side ? ' ' + p.side : '')).join(', ')
               : liveExp.length   ? liveExp.map(p => (p.symbol || '?') + (p.side ? ' ' + p.side : '')).join(', ')
               : 'FLAT';
  _setKv('novaExposureVal', posStr, positions.length || liveExp.length ? 'var(--text)' : 'var(--muted2)');
}

function _renderGovernanceState(orch, exec) {
  const canExec = orch?.can_execute !== false;
  _setKv('novaCanExec', canExec ? 'OPEN' : 'BLOCKED', canExec ? 'var(--green)' : 'var(--red)');

  const macroLock = orch?.macro_lock;
  _setKv('novaMacroLock', macroLock ? 'LOCKED' : 'CLEAR', macroLock ? 'var(--red)' : 'var(--green)');

  const rf = orch?.red_folder_lock;
  const rfTxt = rf === true ? 'ACTIVE' : rf === 'APPROACHING' ? 'APPROACHING' : 'CLEAR';
  _setKv('novaRedFolderVal', rfTxt, rf === true ? 'var(--red)' : rf === 'APPROACHING' ? 'var(--gold)' : 'var(--green)');

  const spyMins = orch?.spy_cooldown_remaining_minutes;
  _setKv('novaSpyCooldown', spyMins > 0 ? spyMins + ' min remaining' : 'CLEAR', spyMins > 0 ? 'var(--gold)' : 'var(--green)');

  const qqqMins = orch?.qqq_cooldown_remaining_minutes;
  _setKv('novaQqqCooldown', qqqMins > 0 ? qqqMins + ' min remaining' : 'CLEAR', qqqMins > 0 ? 'var(--gold)' : 'var(--green)');

  const thesisAge = orch?.thesis_age_minutes;
  _setKv('novaThesisAge', thesisAge != null ? Math.round(thesisAge) + ' min ago' : '—');
}

// Broker reality first: renders every Alpaca position NOVA reports, including
// ones with no matching journal entry -- those get a visible warning instead
// of being silently absent. Close Position / Close All wired to the
// journal-synced backend in Phase 2 -- both confirm before sending.
function _renderPositionsTable(pos) {
  const wrap     = document.getElementById('novaPositionsList');
  const allWrap  = document.getElementById('novaCloseAllWrap');
  if (!wrap) return;
  const positions = pos?.positions || [];

  if (allWrap) allWrap.style.display = positions.length ? '' : 'none';

  if (!positions.length) {
    wrap.innerHTML = '<div style="color:var(--muted2);font-size:12px;font-style:italic">No open positions. Flat.</div>';
    return;
  }

  wrap.innerHTML = positions.map(function(p) {
    const sideColor = p.side === 'LONG' ? 'var(--green)' : 'var(--red)';
    const pnl       = parseFloat(p.unrealized_pnl);
    const pnlColor  = isNaN(pnl) ? 'var(--muted2)' : pnl > 0 ? 'var(--green)' : pnl < 0 ? 'var(--red)' : 'var(--muted)';
    const statusCls = p.journal_matched ? 'b-session-a' : '';
    const statusSty = p.journal_matched ? '' : 'color:var(--yellow);border-color:rgba(251,191,36,.4)';
    const curPrice  = p.current_price != null ? parseFloat(p.current_price).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—';
    const entPrice  = parseFloat(p.entry_price || 0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
    const warnHtml  = p.warning
      ? '<div style="margin-top:8px;padding:8px 10px;border-radius:8px;border:1px solid rgba(251,191,36,.4);background:rgba(251,191,36,.06);color:var(--yellow);font-size:11px;font-family:Space Mono,monospace">⚠ ' + p.warning + '</div>'
      : '';

    return (
      '<div class="gov-gate" style="flex-direction:column;align-items:stretch;gap:8px;height:auto;padding:12px 14px;margin-bottom:8px">' +
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">' +
          '<span class="itc-badge b-nova">' + (p.symbol || '?') + '</span>' +
          '<span class="itc-badge" style="color:' + sideColor + ';border-color:' + sideColor + '">' + (p.side || '—') + '</span>' +
          '<span class="itc-badge ' + statusCls + '" style="' + statusSty + '">' + (p.status || 'OPEN') + '</span>' +
          '<div style="flex:1"></div>' +
          '<button class="submit-trade-btn nova-close-pos-btn" style="width:auto;padding:6px 16px;font-size:11px;margin:0" data-symbol="' + (p.symbol || '') + '" onclick="closePositionConfirm(this)">CLOSE POSITION</button>' +
        '</div>' +
        '<div class="itc-exec" style="margin:0;border:none;padding:0">' +
          '<div class="itc-exec-item"><div class="itc-exec-lab">Qty</div><div class="itc-exec-val">' + (p.qty != null ? p.qty : '—') + '</div></div>' +
          '<div class="itc-exec-item"><div class="itc-exec-lab">Entry</div><div class="itc-exec-val">' + entPrice + '</div></div>' +
          '<div class="itc-exec-item"><div class="itc-exec-lab">Current</div><div class="itc-exec-val">' + curPrice + '</div></div>' +
          '<div class="itc-exec-item"><div class="itc-exec-lab">Unrealized P&L</div><div class="itc-exec-val" style="color:' + pnlColor + '">' + _fmtPnl(pnl) + '</div></div>' +
        '</div>' +
        warnHtml +
      '</div>'
    );
  }).join('');
}

// Phase 2: real, irreversible broker actions -- both confirm first, disable
// the button during the request, and refresh the table from whatever the
// backend actually reports afterward rather than assuming success.
async function closePositionConfirm(btn) {
  const symbol = btn.dataset.symbol;
  if (!symbol) return;
  if (!confirm('Close ' + symbol + ' position? This sends a real order to Alpaca.')) return;

  const origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'CLOSING...';
  try {
    const res = await fetch('/execution/close', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({symbol: symbol}),
    });
    const data = await res.json();
    if (data.status !== 'ok') {
      alert('Close failed for ' + symbol + ': ' + (data.error || data.reason || 'unknown error'));
      btn.disabled = false;
      btn.textContent = origText;
      return;
    }
  } catch (e) {
    alert('Close request failed for ' + symbol + ': ' + e);
    btn.disabled = false;
    btn.textContent = origText;
    return;
  }
  await refreshExecutionTab();
}

async function closeAllPositionsConfirm() {
  const btn = document.getElementById('novaCloseAllBtn');
  if (!confirm('Close ALL open positions? This sends real orders to Alpaca for every open position.')) return;

  const origText = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = 'CLOSING ALL...'; }
  try {
    const res = await fetch('/execution/close-all', {method: 'POST'});
    const data = await res.json();
    if (data.status !== 'ok') {
      alert('Close-all failed: ' + (data.error || data.reason || 'unknown error'));
    } else {
      const failed = (data.results || []).filter(r => r.status !== 'ok');
      if (failed.length) {
        alert('Closed ' + data.closed + ' of ' + (data.results || []).length + ' positions. Failed: ' +
              failed.map(r => r.symbol + ' (' + r.error + ')').join(', '));
      }
    }
  } catch (e) {
    alert('Close-all request failed: ' + e);
  }
  if (btn) { btn.disabled = false; btn.textContent = origText; }
  await refreshExecutionTab();
}

function _renderRejections(rej) {
  if (!rej) return;

  const todayStr = new Date().toISOString().slice(0, 10);
  const records  = rej.records || [];
  const todayRecs = records.filter(r => (r.timestamp_et || r.timestamp || '').startsWith(todayStr));
  const totalToday = todayRecs.length;

  const countEl = document.getElementById('rejTodayCount');
  if (countEl) { countEl.textContent = totalToday; countEl.style.color = totalToday > 0 ? 'var(--red)' : 'var(--muted2)'; }

  // Last blocked signal card
  const last = records[0];
  const lastEl = document.getElementById('rejLastCard');
  if (lastEl) {
    if (!last) {
      lastEl.innerHTML = '<div style="color:var(--muted2);font-size:12px;font-style:italic">No rejections logged yet.</div>';
    } else {
      const code    = last.rejection_code || 'UNKNOWN';
      const ticker  = last.ticker || '—';
      const dir     = last.direction || '';
      const conf    = last.confidence ? last.confidence + ' conf' : '';
      const sess    = (last.session || '').replace(/_/g,' ');
      const reason  = last.rejection_reason || last.rejection_code || '—';
      const tsRaw   = last.timestamp_et || last.timestamp || '';
      const tsDisp  = tsRaw ? tsRaw.slice(0,16).replace('T',' ') : '—';
      const setup   = last.setup_type || '';
      const dirIcon = dir === 'LONG' ? '▲' : dir === 'SHORT' ? '▼' : '';
      const dirCol  = dir === 'LONG' ? 'var(--green)' : dir === 'SHORT' ? 'var(--red)' : 'var(--muted2)';
      lastEl.innerHTML = `<div class="rej-last-card">
  <span class="rej-code-badge">${code}</span>
  <div class="rej-ticker-row">
    <span class="rej-ticker">${ticker}</span>
    ${dir ? `<span style="font-family:'Space Mono',monospace;font-size:10px;font-weight:700;color:${dirCol}">${dirIcon} ${dir}</span>` : ''}
    ${conf ? `<span style="font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2)">${conf}</span>` : ''}
  </div>
  <div class="rej-reason">${reason}</div>
  <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap">
    ${setup ? `<span style="font-family:'Space Mono',monospace;font-size:8px;color:var(--muted2);background:var(--panel);border:1px solid var(--line);padding:2px 7px;border-radius:4px">${setup}</span>` : ''}
    ${sess  ? `<span style="font-family:'Space Mono',monospace;font-size:8px;color:var(--muted2);background:var(--panel);border:1px solid var(--line);padding:2px 7px;border-radius:4px">${sess}</span>` : ''}
    <span style="font-family:'Space Mono',monospace;font-size:8px;color:var(--muted2);margin-left:auto">${tsDisp}</span>
  </div>
</div>`;
    }
  }

  // Rejection breakdown bars
  const byCode = rej.by_code || {};
  const breakdownEl = document.getElementById('rejBreakdownList');
  if (breakdownEl) {
    const entries = Object.entries(byCode).sort((a,b) => b[1] - a[1]).slice(0, 8);
    const maxVal  = entries[0]?.[1] || 1;
    if (!entries.length) {
      breakdownEl.innerHTML = '<div style="color:var(--muted2);font-size:12px;font-style:italic">No rejection history.</div>';
    } else {
      breakdownEl.innerHTML = entries.map(([code, count]) => {
        const pct = Math.round(count / maxVal * 100);
        const friendly = {
          THESIS_CONFLICT:'Thesis Conflict', COOLDOWN_ACTIVE:'Cooldown Active',
          RED_FOLDER_WINDOW:'Red Folder', MACRO_RISK:'Macro Risk',
          DAILY_LOSS_LIMIT_HIT:'Daily Loss Limit', DUPLICATE_SIGNAL:'Duplicate Signal',
          VERDICT_NOT_TAKE:'Verdict: No Take', POSITION_ALREADY_OPEN:'Already In Position',
          TRADE2_REQUIRES_WIN:'Trade 2 Requires Win', DAILY_RISK_LIMIT:'Daily Risk Cap',
          ASIA_CONFIDENCE_TOO_LOW:'Asia Conf Low', ASIA_TRADE_ALREADY_TAKEN:'Asia Limit',
          UNKNOWN_INSTRUMENT:'Unknown Instrument', STATE_GATE_BLOCKED:'State Gate',
        }[code] || code.replace(/_/g,' ');
        return `<div class="rej-bar-row">
  <span class="rej-bar-label">${friendly}</span>
  <div class="rej-bar-track"><div class="rej-bar-fill" style="width:${pct}%"></div></div>
  <span class="rej-count">${count}</span>
</div>`;
      }).join('');
    }
  }
}

function _renderSessionScorecard(j, rej) {
  const trades    = j?.trades || [];
  const todayStr  = new Date().toISOString().slice(0, 10);
  const todayTrades = trades.filter(t => t.trade_date === todayStr && t.outcome !== 'OPEN');

  const todayPnl = todayTrades
    .filter(t => t.outcome === 'WIN' || t.outcome === 'LOSS')
    .reduce((sum, t) => {
      const v = parseFloat(t.realized_pnl ?? t.pnl ?? 'x');
      return sum + (isNaN(v) ? 0 : v);
    }, 0);

  const tw = todayTrades.filter(t => t.outcome === 'WIN').length;
  const tl = todayTrades.filter(t => t.outcome === 'LOSS').length;
  const tt = tw + tl;
  const twr = tt > 0 ? Math.round(tw / tt * 100) : 0;

  const takenEl = document.getElementById('sc2Taken');
  if (takenEl) { takenEl.textContent = todayTrades.length; takenEl.style.color = todayTrades.length > 0 ? 'var(--text)' : 'var(--muted2)'; }

  const rejCount = (rej?.records || []).filter(r => (r.timestamp_et || r.timestamp || '').startsWith(todayStr)).length;
  const blockedEl = document.getElementById('sc2Blocked');
  if (blockedEl) { blockedEl.textContent = rejCount; blockedEl.style.color = rejCount > 0 ? 'var(--red)' : 'var(--muted2)'; }

  const wrEl = document.getElementById('sc2WinRate');
  if (wrEl) { wrEl.textContent = tt > 0 ? twr + '%' : '—'; wrEl.style.color = twr >= 55 ? 'var(--green)' : twr >= 45 ? 'var(--gold)' : tt > 0 ? 'var(--red)' : 'var(--muted2)'; }

  const pnlEl = document.getElementById('sc2Pnl');
  if (pnlEl) { pnlEl.textContent = todayTrades.length ? _fmtPnl(todayPnl) : '—'; pnlEl.style.color = todayPnl > 0 ? 'var(--green)' : todayPnl < 0 ? 'var(--red)' : 'var(--muted2)'; }

  const todayPnls = todayTrades.map(t => parseFloat(t.realized_pnl ?? t.pnl ?? 'x')).filter(n => !isNaN(n));
  const bestEl  = document.getElementById('sc2Best');
  const worstEl = document.getElementById('sc2Worst');
  if (bestEl)  { bestEl.textContent = todayPnls.length ? _fmtPnl(Math.max(...todayPnls)) : '—'; bestEl.style.color = todayPnls.length && Math.max(...todayPnls) > 0 ? 'var(--green)' : 'var(--muted2)'; }
  if (worstEl) { worstEl.textContent = todayPnls.length ? _fmtPnl(Math.min(...todayPnls)) : '—'; worstEl.style.color = todayPnls.length && Math.min(...todayPnls) < 0 ? 'var(--red)' : 'var(--muted2)'; }

  // Governance actions = rejections + any DONNA_AUTO skipped entries
  const govEl = document.getElementById('sc2GovActions');
  if (govEl) { govEl.textContent = rejCount > 0 ? rejCount + ' block' + (rejCount !== 1 ? 's' : '') : '—'; govEl.style.color = rejCount > 0 ? 'var(--gold)' : 'var(--muted2)'; }

  const grade = tt > 0 ? _execGrade(twr, todayPnl) : '—';
  const gradeEl = document.getElementById('novaGrade');
  if (gradeEl) { gradeEl.textContent = grade; gradeEl.style.color = {A:'var(--green)',B:'var(--blue)',C:'var(--gold)',D:'var(--red)'}[grade] || 'var(--muted2)'; }
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

    // Route high-priority webhook signals through maybeSendNotif() so they get
    // the same audio + browser popup treatment as feed-polled alerts.
    // SSE payload lacks grade, so HEADS_UP goes through unevaluated (grade='').
    const sseCard = {
      subtype:         msg.signal || '',
      grade:           msg.grade  || '',
      symbol:          msg.ticker || '',
      direction:       msg.direction || '',
      strategy_family: msg.strategy_family || '',
      setup_type:      msg.setup_type || '',
      entry_zone:      '',
      rr:              '',
      mr2:             {},
      id:              'sse_' + Date.now(),
    };
    maybeSendNotif(sseCard);

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
// ══════════════════════════════════════════════════════
// JOURNAL — Intelligence System
// ══════════════════════════════════════════════════════
let journalFilter   = 'all';
let _journalData    = null;
let _signalData     = null;
let _jDirection     = 'LONG';
let _jOutcome       = 'WIN';
let _jActiveTab     = 'trades';
let _sigFilter      = 'all';

function setDir(d) {
  _jDirection = d;
  document.getElementById('jDirLong').className  = 'toggle-btn' + (d === 'LONG'  ? ' active-long'  : '');
  document.getElementById('jDirShort').className = 'toggle-btn' + (d === 'SHORT' ? ' active-short' : '');
}
function setOutcome(o) {
  _jOutcome = o;
  document.getElementById('jOutWin').className  = 'toggle-btn' + (o === 'WIN'       ? ' active-win'  : '');
  document.getElementById('jOutLoss').className = 'toggle-btn' + (o === 'LOSS'      ? ' active-loss' : '');
  document.getElementById('jOutBE').className   = 'toggle-btn' + (o === 'BREAKEVEN' ? ' active-be'   : '');
}

function openJModal()  { document.getElementById('jModalBackdrop').style.display = 'flex'; }
function closeJModal() { document.getElementById('jModalBackdrop').style.display = 'none'; }
document.getElementById('jOpenModal').addEventListener('click', openJModal);

function switchJTab(tab) {
  _jActiveTab = tab;
  ['trades','signals','analytics'].forEach(t => {
    document.getElementById('jPanel-' + t).style.display = t === tab ? '' : 'none';
    document.getElementById('jTab-' + t).classList.toggle('active', t === tab);
  });
  if (tab === 'signals' && !_signalData) refreshSignals();
}

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

function setSigFilter(f) {
  _sigFilter = f;
  if (_signalData) renderSignalFeed(_signalData);
}

// ── Trade card renderer ──────────────────────────────────────
function renderJournal(data) {
  _journalData = data;
  const stats  = data.stats  || {};
  const trades = data.trades || [];
  const todayStr = new Date().toISOString().slice(0, 10);

  // Overview strip — exclude REJECTED (governance-blocked, never executed)
  const todayTrades = trades.filter(t => t.trade_date === todayStr && t.outcome !== 'REJECTED');
  const todayPnl = todayTrades
    .filter(t => t.outcome === 'WIN' || t.outcome === 'LOSS' || t.outcome === 'EOD_CLOSE' || t.outcome === 'BREAKEVEN')
    .reduce((s, t) => s + (parseFloat(t.realized_pnl ?? t.pnl ?? 0) || 0), 0);
  const closed = trades.filter(t => t.outcome === 'WIN' || t.outcome === 'LOSS');
  const wins   = closed.filter(t => t.outcome === 'WIN').length;
  const wr     = closed.length > 0 ? (wins / closed.length * 100).toFixed(1) : null;
  const pf     = stats.profit_factor || 0;
  const weekPnl = (stats.daily_pnl || {}).this_week || 0;

  setText('jOvTrades', todayTrades.length);
  const pnlEl = document.getElementById('jOvPnl');
  if (pnlEl) {
    pnlEl.textContent = _fmtPnl(todayPnl);
    pnlEl.style.color = todayPnl > 0 ? 'var(--green)' : todayPnl < 0 ? 'var(--red)' : 'var(--muted2)';
  }
  const wrEl = document.getElementById('jOvWinRate');
  if (wrEl) {
    wrEl.textContent = wr !== null ? wr + '%' : '—';
    wrEl.style.color = wr >= 55 ? 'var(--green)' : wr >= 45 ? 'var(--yellow)' : wr !== null ? 'var(--red)' : 'var(--muted2)';
  }
  const pfEl = document.getElementById('jOvPF');
  if (pfEl) {
    pfEl.textContent = pf > 0 ? pf.toFixed(2) : '—';
    pfEl.style.color = pf >= 1.5 ? 'var(--green)' : pf >= 1.0 ? 'var(--yellow)' : pf > 0 ? 'var(--red)' : 'var(--muted2)';
  }
  const wkEl = document.getElementById('jOvWeek');
  if (wkEl) {
    const w = parseFloat(weekPnl) || 0;
    wkEl.textContent = _fmtPnl(w);
    wkEl.style.color = w > 0 ? 'var(--green)' : w < 0 ? 'var(--red)' : 'var(--muted2)';
  }

  // Trade count badge
  setText('jTabCount-trades', trades.length);

  // ── Analytics stats ──────────────────────────────────────────
  setText('jaTotalTrades', stats.total || 0);
  const jaWR = document.getElementById('jaWinRate');
  if (jaWR) { jaWR.textContent = wr !== null ? wr + '%' : '—'; jaWR.style.color = wr >= 55 ? 'var(--green)' : wr >= 45 ? 'var(--yellow)' : wr !== null ? 'var(--red)' : 'var(--muted2)'; }
  setText('jaWRSub', `${stats.wins||0}W · ${stats.losses||0}L · ${stats.breakevens||0}BE`);
  const jaPF = document.getElementById('jaPF');
  if (jaPF) { jaPF.textContent = pf > 0 ? pf.toFixed(2) : '—'; jaPF.style.color = pf >= 1.5 ? 'var(--green)' : pf >= 1.0 ? 'var(--yellow)' : pf > 0 ? 'var(--red)' : 'var(--muted2)'; }
  setText('jaBestRegime', stats.best_regime || '—');
  setText('jaWorstRegime', 'Worst: ' + (stats.worst_regime || '—'));
  setText('jAvgWinLoss', `Avg W: ${stats.avg_win ? _fmtUsd(stats.avg_win) : '—'} / Avg L: ${stats.avg_loss ? _fmtUsd(stats.avg_loss) : '—'}`);

  // Expectancy
  const exp = stats.expectancy;
  const expEl = document.getElementById('jaExpectancy');
  if (expEl && exp !== undefined) {
    expEl.textContent = _fmtPnl(exp);
    expEl.style.color = exp > 0 ? 'var(--green)' : exp < 0 ? 'var(--red)' : 'var(--muted2)';
  }
  const avgWinEl = document.getElementById('jaAvgWin');
  if (avgWinEl) { avgWinEl.textContent = stats.avg_win ? _fmtPnl(stats.avg_win) : '—'; }
  const avgLossEl = document.getElementById('jaAvgLoss');
  if (avgLossEl) { avgLossEl.textContent = 'Avg L: ' + (stats.avg_loss ? _fmtUsd(stats.avg_loss) : '—'); }

  // Helper: render a breakdown grid
  function renderBreakdownGrid(elId, data, colorMap) {
    const entries = Object.entries(data || {}).sort((a,b) => b[1].win_rate - a[1].win_rate);
    if (!entries.length) { setHtml(elId, '<div class="regime-card"><div class="rc-sub">No data yet.</div></div>'); return; }
    setHtml(elId, entries.map(([key, v]) => {
      const wrc = v.win_rate >= 55 ? 'var(--green)' : v.win_rate >= 45 ? 'var(--yellow)' : 'var(--red)';
      const borderC = (colorMap && colorMap[key]) || 'var(--line)';
      const total = (v.wins||0) + (v.losses||0) + (v.breakevens||0);
      const pnlStr = v.pnl !== undefined ? ` · ${_fmtPnl(v.pnl)}` : '';
      return `<div class="regime-card" style="border-color:${borderC}44">
        <div class="rc-name" style="color:${borderC};font-size:13px">${key.replace(/_/g,' ')}</div>
        <div class="rc-wr" style="color:${wrc}">${v.win_rate}%</div>
        <div class="rc-sub">${v.wins}W · ${v.losses}L · ${total} trades${pnlStr}</div>
      </div>`;
    }).join(''));
  }

  const regimeColorMap = {TRENDING:'var(--green)',RANGING:'var(--blue)',EVENT_DRIVEN:'var(--yellow)',RISK_OFF:'var(--red)',CONSOLIDATING:'var(--muted2)'};
  renderBreakdownGrid('regimeBreakdownGrid', stats.by_regime, regimeColorMap);
  renderBreakdownGrid('sessionBreakdownGrid', stats.by_session, null);
  renderBreakdownGrid('setupTypeGrid', stats.by_setup_type, null);

  // Behavioral error frequency
  const bfreq = stats.behavioral_frequency || {};
  const berr  = stats.behavioral_error_count || 0;
  const bEntries = Object.entries(bfreq);
  const bEl = document.getElementById('behavioralAnalyticsGrid');
  if (bEl) {
    if (!bEntries.length) {
      bEl.innerHTML = '<div style="font-size:12px;color:var(--muted2);padding:12px 0">No behavioral flags recorded yet.</div>';
    } else {
      const maxCount = Math.max(...bEntries.map(([,c]) => c));
      bEl.innerHTML = `<div style="font-size:11px;color:var(--muted);margin-bottom:10px">${berr} trade${berr!==1?'s':''} had at least one flag</div>`
        + bEntries.map(([flag, count]) => {
          const pct = Math.round(count / maxCount * 100);
          return `<div style="margin-bottom:8px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
              <span style="font-family:'Space Mono',monospace;font-size:9px;color:var(--text)">${flag.replace(/_/g,' ')}</span>
              <span style="font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2)">${count}×</span>
            </div>
            <div style="height:4px;background:var(--line);border-radius:2px;overflow:hidden">
              <div style="height:100%;width:${pct}%;background:var(--red);border-radius:2px;transition:width .4s"></div>
            </div>
          </div>`;
        }).join('');
    }
  }

  // Emotional state performance
  const byEmotion = stats.by_emotional_state || {};
  const eEntries  = Object.entries(byEmotion).sort((a,b) => b[1].win_rate - a[1].win_rate);
  const eEl = document.getElementById('emotionalAnalyticsGrid');
  if (eEl) {
    if (!eEntries.length) {
      eEl.innerHTML = '<div style="font-size:12px;color:var(--muted2);padding:8px 0">No emotional state data yet. Tag your trades to build this profile.</div>';
    } else {
      const stateColor = {CALM:'var(--green)',CONFIDENT:'var(--green)',ANXIOUS:'var(--yellow)',HESITANT:'var(--yellow)',IMPULSIVE:'var(--red)',FRUSTRATED:'var(--red)'};
      eEl.innerHTML = `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px">`
        + eEntries.map(([state, v]) => {
          const wrc = v.win_rate >= 55 ? 'var(--green)' : v.win_rate >= 45 ? 'var(--yellow)' : 'var(--red)';
          const sc  = stateColor[state] || 'var(--muted2)';
          const total = (v.wins||0) + (v.losses||0) + (v.breakevens||0);
          const pnlStr = v.pnl !== undefined ? _fmtPnl(v.pnl) : '—';
          return `<div class="regime-card" style="border-color:${sc}33">
            <div class="rc-name" style="color:${sc};font-size:13px">${state}</div>
            <div class="rc-wr" style="color:${wrc}">${v.win_rate}%</div>
            <div class="rc-sub">${v.wins}W · ${v.losses}L · ${total} trades</div>
            <div class="rc-sub" style="margin-top:4px">${pnlStr}</div>
          </div>`;
        }).join('') + '</div>';
    }
  }

  // Filter bar
  const filterLabels = {all:'All Time', week:'This Week', month:'This Month'};
  setHtml('jFilterBar', '<span style="font-size:9px;color:var(--muted2);letter-spacing:1.2px;text-transform:uppercase;font-family:Space Mono,monospace">Filter:</span>'
    + Object.entries(filterLabels).map(([f,label]) =>
        `<button class="j-filter-btn${journalFilter===f?' active':''}" onclick="setJournalFilter('${f}')">${label}</button>`
      ).join(''));

  // Filter trades by period
  const now = new Date();
  const indexed = trades.map((t, i) => ({t, origIdx: i}));
  const filtered = indexed.filter(({t}) => {
    if (journalFilter === 'all') return true;
    const ds = t.trade_date || (t.timestamp ? t.timestamp.substring(0,10) : '');
    if (!ds) return true;
    const d = new Date(ds + 'T12:00:00');
    if (journalFilter === 'week') {
      const mon = new Date(now); mon.setDate(mon.getDate() - ((mon.getDay() + 6) % 7)); mon.setHours(0,0,0,0);
      return d >= mon;
    }
    if (journalFilter === 'month') return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
    return true;
  });

  // Group by date
  const grouped = {};
  filtered.forEach(({t, origIdx}) => {
    const dk = t.trade_date || (t.timestamp ? t.timestamp.substring(0,10) : 'Unknown');
    if (!grouped[dk]) grouped[dk] = [];
    grouped[dk].push({t, origIdx});
  });
  const sortedDates = Object.keys(grouped).sort((a,b) => b.localeCompare(a));

  let cards = '';
  if (sortedDates.length === 0) {
    cards = `<div style="text-align:center;padding:48px;color:var(--muted2);font-size:13px">${trades.length ? 'No trades in this period.' : 'No trades logged yet. Click <strong>+ LOG TRADE</strong> to add your first entry.'}</div>`;
  } else {
    sortedDates.forEach(dk => {
      const dayItems = grouped[dk].slice().reverse();
      const count = dayItems.length;
      const dayPnl = dayItems.reduce((s, {t}) => {
        const v = parseFloat(t.realized_pnl ?? t.pnl ?? 0) || 0;
        return (t.outcome === 'WIN' || t.outcome === 'LOSS') ? s + v : s;
      }, 0);
      const dayPnlStr = dayPnl !== 0 ? `<span style="color:${dayPnl>0?'var(--green)':'var(--red)'};margin-left:10px;font-weight:400">${_fmtPnl(dayPnl)}</span>` : '';
      cards += `<div class="j-date-group"><div class="j-date-label">${fmtDateHeader(dk)}<span style="opacity:.5;font-weight:400;margin-left:10px">· ${count} trade${count!==1?'s':''}</span>${dayPnlStr}</div>`;
      dayItems.forEach(({t, origIdx}) => {
        const outcome    = (t.outcome || 'OPEN').toUpperCase();
        const dir        = (t.direction || '').toUpperCase();
        const dirClass   = dir === 'LONG' ? 'long' : 'short';
        const dirIcon    = dir === 'LONG' ? '▲' : '▼';
        const rawPnl     = t.realized_pnl !== undefined && t.realized_pnl !== null ? t.realized_pnl : (t.pnl || 0);
        const pnl        = parseFloat(rawPnl) || 0;
        const pnlStr     = _fmtPnl(pnl);
        const pnlColor   = pnl > 0 ? 'var(--green)' : pnl < 0 ? 'var(--red)' : 'var(--muted)';
        const timeStr    = fmtTimeET(t.timestamp);
        const grade      = (t.grade || t.tier || '').toUpperCase();
        const gradeClass = grade === 'A' ? 'b-grade-a' : grade === 'B' ? 'b-grade-b' : 'b-grade-c';
        const sessLabel  = (t.session || '').replace(/_/g, ' ');
        const setupLabel = t.setup_type || '';
        const isAuto     = t.source === 'DONNA_AUTO' || t.source === 'DONNA_AUTO_RECONSTRUCTED';

        // Badges
        let badges = '';
        if (t.ticker) badges += `<span class="itc-badge b-nova">${t.ticker}</span>`;
        if (dir) badges += `<span class="itc-badge" style="color:${dir==='LONG'?'var(--green)':'var(--red)'}">${dirIcon} ${dir}</span>`;
        if (setupLabel) badges += `<span class="itc-badge">${setupLabel.replace(/_/g,' ')}</span>`;
        if (sessLabel) badges += `<span class="itc-badge b-session-a">${sessLabel}</span>`;
        if (grade) badges += `<span class="itc-badge ${gradeClass}">Grade ${grade}</span>`;
        if (isAuto) badges += `<span class="itc-badge b-nova">AUTO</span>`;

        // Execution row
        const hasEntry = t.entry_price != null;
        const hasExit  = t.exit_price  != null;
        let execItems = '';
        if (hasEntry) execItems += `<div class="itc-exec-item"><div class="itc-exec-lab">Entry</div><div class="itc-exec-val">${parseFloat(t.entry_price).toLocaleString()}</div></div>`;
        if (hasExit)  execItems += `<div class="itc-exec-item"><div class="itc-exec-lab">Exit</div><div class="itc-exec-val">${parseFloat(t.exit_price).toLocaleString()}</div></div>`;
        if (t.stop)   execItems += `<div class="itc-exec-item"><div class="itc-exec-lab">Stop</div><div class="itc-exec-val" style="color:var(--red)">${parseFloat(t.stop).toLocaleString()}</div></div>`;
        if (t.tp1)    execItems += `<div class="itc-exec-item"><div class="itc-exec-lab">TP1</div><div class="itc-exec-val" style="color:var(--green)">${parseFloat(t.tp1).toLocaleString()}</div></div>`;
        if (t.rr)     execItems += `<div class="itc-exec-item"><div class="itc-exec-lab">R:R</div><div class="itc-exec-val">${t.rr}</div></div>`;
        if (t.size)   execItems += `<div class="itc-exec-item"><div class="itc-exec-lab">Size</div><div class="itc-exec-val">${t.size}</div></div>`;

        // NOVA intelligence block (from signal log notes)
        let novaBlock = '';
        if (t.notes || t.action) {
          const novaText = t.action || t.notes || '';
          novaBlock = `<div class="itc-nova"><div class="itc-nova-label">NOVA Assessment</div>${escHtml(novaText.substring(0,280))}${novaText.length>280?'…':''}</div>`;
        }

        // Behavioral tracking block
        let behavioralBlock = '';
        const bflags = t.behavioral_flags || [];
        const estate = t.emotional_state || '';
        const reflect = t.reflection || '';
        if (estate || bflags.length || reflect) {
          let bContent = '';
          if (estate) bContent += `<div class="beh-state">${estate}</div>`;
          if (bflags.length) bContent += `<div class="beh-flags">${bflags.map(f => `<span class="beh-flag">${f.replace(/_/g,' ')}</span>`).join('')}</div>`;
          if (reflect) bContent += `<div class="beh-reflection">"${escHtml(reflect)}"</div>`;
          behavioralBlock = `<div class="itc-behavioral"><div class="itc-beh-label">Behavioral</div>${bContent}</div>`;
        }

        // NOVA Review panel (AI analysis)
        let reviewBlock = '';
        if (t.nova_review) {
          const ts = t.nova_review_ts ? fmtTimeET(t.nova_review_ts) : '';
          reviewBlock = `<div class="itc-review">
  <div class="itc-review-hdr" id="nova-hdr-${origIdx}" onclick="toggleReview(${origIdx})">
    <span class="itc-review-hdr-label">NOVA Review</span>
    <span class="itc-review-hdr-ts">${ts} ▾</span>
  </div>
  <div class="itc-review-body" id="nova-body-${origIdx}">${escHtml(t.nova_review)}</div>
</div>`;
        } else {
          reviewBlock = `<button class="nova-gen-btn" id="nova-gen-${origIdx}" onclick="generateAnalysis(${origIdx})">Generate NOVA Review</button>`;
        }

        // Context row
        let ctxItems = '';
        if (t.macro_risk || t.active_regime) ctxItems += `<div class="itc-ctx-item"><div class="itc-ctx-lab">Macro</div><div class="itc-ctx-val">${(t.macro_risk||'—').toUpperCase()}</div></div>`;
        if (t.vix)  ctxItems += `<div class="itc-ctx-item"><div class="itc-ctx-lab">VIX</div><div class="itc-ctx-val">${parseFloat(t.vix).toFixed(1)}</div></div>`;
        if (t.regime || t.active_regime) ctxItems += `<div class="itc-ctx-item"><div class="itc-ctx-lab">Regime</div><div class="itc-ctx-val">${(t.regime||t.active_regime||'—').replace(/_/g,' ')}</div></div>`;
        if (t.pros_phase) ctxItems += `<div class="itc-ctx-item"><div class="itc-ctx-lab">PROS</div><div class="itc-ctx-val">${t.pros_phase.replace(/_/g,' ')}</div></div>`;
        if (t.ib_draw) ctxItems += `<div class="itc-ctx-item"><div class="itc-ctx-lab">IB Draw</div><div class="itc-ctx-val">${t.ib_draw}</div></div>`;
        if (t.nova_conf) ctxItems += `<div class="itc-ctx-item"><div class="itc-ctx-lab">Confidence</div><div class="itc-ctx-val">${t.nova_conf}</div></div>`;
        if (t.session_quality) ctxItems += `<div class="itc-ctx-item"><div class="itc-ctx-lab">Session Q</div><div class="itc-ctx-val" style="color:${t.session_quality==='A'?'var(--green)':'var(--yellow)'}">Grade ${t.session_quality}</div></div>`;

        cards += `<div class="itc outcome-${outcome}">
  <div class="itc-header">
    <div class="itc-badges">${badges}</div>
    <div><div class="itc-pnl" style="color:${pnlColor}">${pnlStr}</div><div class="itc-time">${timeStr}</div></div>
  </div>
  ${execItems ? `<div class="itc-exec">${execItems}</div>` : ''}
  ${novaBlock}
  ${ctxItems ? `<div class="itc-ctx">${ctxItems}</div>` : ''}
  ${behavioralBlock}
  ${reviewBlock}
  <div class="itc-footer">
    <span class="itc-outcome-badge ${outcome}">${outcome}</span>
    <div style="display:flex;gap:8px;align-items:center">
      <button style="font-family:\'Space Mono\',monospace;font-size:8px;letter-spacing:1px;padding:4px 12px;border-radius:6px;border:1px solid var(--line);background:var(--panel2);color:var(--muted);cursor:pointer;text-transform:uppercase" onclick="openTradeDetail(${origIdx})">Review</button>
      <button class="del-btn" onclick="deleteTrade(${origIdx})" title="Delete">✕</button>
    </div>
  </div>
</div>`;
      });
      cards += '</div>';
    });
  }
  setHtml('journalCardList', cards);
}

// ── Signal feed renderer ──────────────────────────────────────
function renderSignalFeed(data) {
  _signalData = data;
  const signals = data.signals || [];
  const total   = data.total || 0;

  // Update count badge
  const todayStr = new Date().toISOString().slice(0, 10);
  const todayCount = signals.filter(s => (s.date || s.timestamp || '').startsWith(todayStr)).length;
  setText('jTabCount-signals', todayCount);
  setText('jOvEvals', total);

  // Sig filter bar
  const sigFilterLabels = {all:'All', today:'Today', mnq:'MNQ', mes:'MES'};
  setHtml('jSigFilterBar', Object.entries(sigFilterLabels).map(([f, label]) =>
    `<button class="j-filter-btn${_sigFilter===f?' active':''}" onclick="setSigFilter('${f}')">${label}</button>`
  ).join(''));

  // Filter
  const filtered = signals.filter(s => {
    if (_sigFilter === 'today') return (s.date || '').startsWith(todayStr) || (s.timestamp || '').startsWith(todayStr);
    if (_sigFilter === 'mnq')   return (s.symbol || '').toUpperCase().includes('MNQ');
    if (_sigFilter === 'mes')   return (s.symbol || '').toUpperCase().includes('MES');
    return true;
  });

  if (filtered.length === 0) {
    setHtml('jSignalFeedList', '<div style="text-align:center;padding:48px;color:var(--muted2);font-size:13px">No signal entries found.</div>');
    return;
  }

  let html = '';
  filtered.forEach(s => {
    const sym     = (s.symbol || '').replace('CME_MINI:','').replace('1!','');
    const cmd     = (s.nova_cmd || 'WAIT').replace(/\\s+/g,'-').toUpperCase();
    const cmdKey  = cmd.includes('WATCH') ? 'WATCH' : cmd.includes('BUY') || cmd.includes('LONG') ? 'BUY' : cmd.includes('SELL') || cmd.includes('SHORT') ? 'SELL' : 'WAIT';
    const grade   = (s.grade || '—').toUpperCase();
    const sessQ   = s.session_quality || '';
    const conf    = s.nova_conf || '';
    const phase   = (s.pros_phase || '').replace(/_/g,' ');
    const ote     = s.pros_ote || '';
    const ibd     = s.ib_draw || '';
    const notes   = s.notes || s.action || '';
    const timeStr = s.timestamp_et || '';
    const dir     = (s.pros_direction || s.direction || '').toUpperCase();
    const dirIcon = dir === 'LONG' ? '▲' : dir === 'SHORT' ? '▼' : '';

    html += `<div class="sf-card">
  <div class="sf-header">
    <div class="sf-meta">
      <span class="sf-time">${timeStr}</span>
      <span class="sf-symbol">${sym}</span>
      <span class="sf-cmd ${cmdKey}">${s.nova_cmd || 'WAIT'}</span>
      ${dir ? `<span style="font-family:'Space Mono',monospace;font-size:9px;color:${dir==='LONG'?'var(--green)':'var(--red)'}">${dirIcon} ${dir}</span>` : ''}
    </div>
    <span class="sf-grade ${grade}">Grade ${grade}${sessQ ? ` · Q${sessQ}` : ''}</span>
  </div>
  <div class="sf-chips">
    ${phase ? `<span class="sf-chip">PROS <strong>${phase}</strong></span>` : ''}
    ${ote   ? `<span class="sf-chip">OTE <strong>${ote}</strong></span>` : ''}
    ${ibd   ? `<span class="sf-chip">IB <strong>${ibd}</strong></span>` : ''}
    ${conf  ? `<span class="sf-chip">Conf <strong>${conf}</strong></span>` : ''}
    ${s.macro_risk ? `<span class="sf-chip">Macro <strong>${(s.macro_risk||'').toUpperCase()}</strong></span>` : ''}
    ${s.vix ? `<span class="sf-chip">VIX <strong>${parseFloat(s.vix).toFixed(1)}</strong></span>` : ''}
  </div>
  ${notes ? `<div class="sf-notes">${escHtml(notes.substring(0,220))}${notes.length>220?'…':''}</div>` : ''}
</div>`;
  });
  setHtml('jSignalFeedList', html);
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Trade Detail (Phase 4 — Replay / Review) ───────────────────
async function openTradeDetail(idx) {
  document.getElementById(\'jtdBackdrop\').style.display = \'flex\';
  document.getElementById(\'jtdTitle\').innerHTML = \'<span style="color:var(--muted2);font-size:12px">Loading…</span>\';
  document.getElementById(\'jtdBody\').innerHTML = \'<div style="text-align:center;padding:40px;color:var(--muted2)">Loading trade detail…</div>\';
  try {
    const res  = await fetch(\'/journal/trade-detail\', {method:\'POST\', headers:{\'Content-Type\':\'application/json\'}, body: JSON.stringify({index: idx})});
    const data = await res.json();
    if (data.status === \'ok\') renderTradeDetail(data, idx);
  } catch(e) {
    document.getElementById(\'jtdBody\').innerHTML = \'<div style="text-align:center;padding:40px;color:var(--red)">Error loading detail.</div>\';
  }
}

function closeTradeDetail() {
  document.getElementById(\'jtdBackdrop\').style.display = \'none\';
}

function renderTradeDetail(data, idx) {
  const t   = data.trade || {};
  const tl  = data.reasoning_timeline || [];
  const tr  = data.execution_trace;

  const outcome  = (t.outcome || \'OPEN\').toUpperCase();
  const dir      = (t.direction || \'\').toUpperCase();
  const dirIcon  = dir === \'LONG\' ? \'▲\' : \'▼\';
  const dirColor = dir === \'LONG\' ? \'var(--green)\' : \'var(--red)\';
  const pnl      = parseFloat(t.realized_pnl || t.pnl || 0);
  const pnlStr   = _fmtPnl(pnl);
  const pnlColor = pnl > 0 ? \'var(--green)\' : pnl < 0 ? \'var(--red)\' : \'var(--muted)\';
  const grade    = (t.grade || \'\').toUpperCase();

  // Header
  document.getElementById(\'jtdTitle\').innerHTML =
    `<span style="font-family:\'Rajdhani\',sans-serif;font-size:18px;font-weight:700">${t.ticker||\'—\'}</span>` +
    `<span style="color:${dirColor};font-weight:700">${dirIcon} ${dir}</span>` +
    (t.setup_type ? `<span style="font-family:\'Space Mono\',monospace;font-size:9px;color:var(--muted2)">${t.setup_type.replace(/_/g,\' \')}</span>` : \'\') +
    (grade ? `<span style="font-family:\'Space Mono\',monospace;font-size:9px;color:var(--gold)">Grade ${grade}</span>` : \'\') +
    `<span style="font-family:\'Space Mono\',monospace;font-size:9px;color:${pnlColor};font-weight:700">${pnlStr}</span>`;

  let html = \'\';

  // Screenshot (first timeline entry that has one)
  const withShot = tl.find(s => s.screenshot);
  if (withShot && withShot.screenshot) {
    const fname = withShot.screenshot.split(/[\\\\/]/).pop();
    html += `<div class="jtd-screenshot"><img src="/journal/screenshot?file=${encodeURIComponent(fname)}" alt="Chart screenshot" loading="lazy" onerror="this.parentElement.style.display=\'none\'" /></div>`;
  }

  // Execution + Governance two-col
  let execHtml = \'<div class="jtd-section-label">Execution</div><div class="jtd-kv-grid">\';
  const execFields = [
    [\'Entry\', t.entry_price != null ? parseFloat(t.entry_price).toLocaleString() : \'—\'],
    [\'Exit\',  t.exit_price  != null ? parseFloat(t.exit_price).toLocaleString()  : \'—\'],
    [\'Stop\',  t.stop  ? parseFloat(t.stop).toLocaleString()  : \'—\'],
    [\'TP1\',   t.tp1   ? parseFloat(t.tp1).toLocaleString()   : \'—\'],
    [\'R:R\',   t.rr    || \'—\'],
    [\'Size\',  t.size  || 1],
    [\'Session\', (t.session||\'—\').replace(/_/g,\' \')],
    [\'Macro\',   (t.macro_risk||\'—\').toUpperCase()],
  ];
  execFields.forEach(([lab, val]) => {
    execHtml += `<div class="jtd-kv"><div class="jtd-kv-lab">${lab}</div><div class="jtd-kv-val">${val}</div></div>`;
  });
  execHtml += \'</div>\';

  // Governance gates from execution trace
  let govHtml = \'<div class="jtd-section-label">Governance at Execution</div>\';
  if (tr && tr.gates) {
    const gates = tr.gates;
    const gateItems = [
      [\'Trade Permission\', gates.trade_permission !== false],
      [\'Macro Lock\',       !gates.macro_lock],
      [\'Red Folder\',       !gates.red_folder_active],
      [\'EOD Lock\',         !gates.eod_lock],
      [\'Daily Trades\',     true, gates.daily_trade_count + \' taken\'],
    ];
    gateItems.forEach(([name, pass, extra]) => {
      const color = pass ? \'var(--green)\' : \'var(--red)\';
      const label = extra || (pass ? \'CLEAR\' : \'BLOCKED\');
      govHtml += `<div class="jtd-gate"><div class="jtd-gate-dot" style="background:${color}"></div><span class="jtd-gate-name">${name}</span><span class="jtd-gate-val" style="color:${color}">${label}</span></div>`;
    });
    if (tr.rejection_reason) {
      govHtml += `<div style="margin-top:8px;font-size:11px;color:var(--red);font-style:italic">${tr.rejection_reason}</div>`;
    }
  } else {
    govHtml += \'<div style="font-size:12px;color:var(--muted2);padding:8px 0">Manual trade — no execution trace.</div>\';
  }

  html += `<div class="jtd-two-col"><div class="panel" style="padding:14px 16px">${execHtml}</div><div class="panel" style="padding:14px 16px">${govHtml}</div></div>`;

  // Reasoning timeline
  if (tl.length) {
    let tlHtml = \'<div class="jtd-section-label">Reasoning Timeline</div><div class="jtd-timeline">\';
    tl.forEach((s, i) => {
      const isLast   = i === tl.length - 1;
      const cmd      = (s.nova_cmd || \'WAIT\').toUpperCase();
      const isActive = cmd.includes(\'EXECUTION\') || cmd.includes(\'BUY\') || cmd.includes(\'SELL\');
      const grade    = (s.grade || \'\').toUpperCase();
      const gradeColor = grade === \'A\' ? \'var(--green)\' : grade === \'B\' ? \'var(--yellow)\' : \'var(--muted2)\';
      const shotFname = s.screenshot ? s.screenshot.split(/[\\\\/]/).pop() : null;
      tlHtml += `<div class="jtd-tl-item">
        <div class="jtd-tl-dot-col">
          <div class="jtd-tl-dot${isActive?\' active\':\'\'}"></div>
          ${!isLast ? \'<div class="jtd-tl-line"></div>\' : \'\'}
        </div>
        <div class="jtd-tl-content">
          <div class="jtd-tl-time">${s.timestamp_et||\'\'}</div>
          <div class="jtd-tl-cmd">${s.nova_cmd||\'WAIT\'}${grade ? ` <span style="color:${gradeColor};font-size:8px">Grade ${grade}</span>` : \'\'}</div>
          <div class="jtd-tl-chips">
            ${s.pros_phase ? `<span class="jtd-tl-chip">PROS <strong>${(s.pros_phase||'').replace(/_/g,' ')}</strong></span>` : \'\'}
            ${s.pros_ote   ? `<span class="jtd-tl-chip">OTE <strong>${s.pros_ote}</strong></span>` : \'\'}
            ${s.nova_conf  ? `<span class="jtd-tl-chip">Conf <strong>${s.nova_conf}</strong></span>` : \'\'}
            ${s.ib_draw    ? `<span class="jtd-tl-chip">IB <strong>${s.ib_draw}</strong></span>` : \'\'}
          </div>
          ${s.action ? `<div class="jtd-tl-note">${escHtml((s.action||'').substring(0,120))}</div>` : \'\'}
          ${shotFname ? `<div style="margin-top:6px"><img src="/journal/screenshot?file=${encodeURIComponent(shotFname)}" style="width:100%;max-width:320px;border-radius:6px;border:1px solid var(--line)" loading="lazy" onerror="this.style.display=\'none\'" /></div>` : \'\'}
        </div>
      </div>` ;
    });
    tlHtml += \'</div>\';
    html += `<div class="panel" style="padding:14px 16px">${tlHtml}</div>`;
  }

  // NOVA Review
  if (t.nova_review) {
    html += `<div class="panel" style="padding:14px 16px">
      <div class="jtd-section-label">NOVA Review</div>
      <div class="jtd-review">${escHtml(t.nova_review)}</div>
    </div>`;
  } else {
    html += `<div style="text-align:center;padding:8px 0">
      <button class="nova-gen-btn" id="nova-gen-${idx}" onclick="generateAnalysis(${idx}).then(()=>openTradeDetail(${idx}))">Generate NOVA Review</button>
    </div>`;
  }

  // Behavioral
  const flags   = t.behavioral_flags || [];
  const estate  = t.emotional_state  || \'\';
  const reflect = t.reflection       || \'\';
  if (estate || flags.length || reflect) {
    let bHtml = \'<div class="jtd-section-label">Behavioral</div>\';
    if (estate) bHtml += `<div class="beh-state" style="margin-bottom:8px">${estate}</div>`;
    if (flags.length) bHtml += `<div class="beh-flags" style="margin-bottom:8px">${flags.map(f=>`<span class="beh-flag">${f.replace(/_/g,\' \')}</span>`).join(\'\')}</div>`;
    if (reflect) bHtml += `<div class="beh-reflection">"${escHtml(reflect)}"</div>`;
    html += `<div class="panel" style="padding:14px 16px">${bHtml}</div>`;
  }

  document.getElementById(\'jtdBody\').innerHTML = html;
}

async function generateAnalysis(idx) {
  const btn = document.getElementById(`nova-gen-${idx}`);
  const body = document.getElementById(`nova-body-${idx}`);
  if (btn) { btn.disabled = true; btn.textContent = \'GENERATING...\'; }
  try {
    const res  = await fetch(\'/journal/analyze\', {method:\'POST\', headers:{\'Content-Type\':\'application/json\'}, body: JSON.stringify({index: idx})});
    const data = await res.json();
    if (data.status === \'ok\') {
      if (body) { body.textContent = data.analysis; body.classList.add(\'open\'); }
      const hdr = document.getElementById(`nova-hdr-${idx}`);
      if (hdr) hdr.querySelector(\'.itc-review-hdr-ts\').textContent = \'Just now\';
      if (btn) btn.style.display = \'none\';
      refreshJournal();
    } else {
      if (btn) { btn.disabled = false; btn.textContent = \'GENERATE NOVA REVIEW\'; }
    }
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = \'GENERATE NOVA REVIEW\'; }
  }
}

function toggleReview(idx) {
  const body = document.getElementById(`nova-body-${idx}`);
  if (body) body.classList.toggle(\'open\');
}

async function refreshJournal() {
  try {
    const res = await fetch('/journal/data');
    if (!res.ok) return;
    const data = await res.json();
    renderJournal(data);
  } catch(e) { console.error('Journal refresh error:', e); }
}

async function refreshSignals() {
  try {
    const res = await fetch('/journal/signals');
    if (!res.ok) return;
    const data = await res.json();
    renderSignalFeed(data);
  } catch(e) { console.error('Signal feed error:', e); }
}

async function deleteTrade(index) {
  if (!confirm('Delete this trade entry?')) return;
  try {
    const res = await fetch('/journal/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({index})});
    const data = await res.json();
    if (data.status === 'ok') refreshJournal();
  } catch(e) { console.error(e); }
}

document.getElementById('jSubmitBtn').addEventListener('click', async () => {
  const ticker       = (document.getElementById('jTicker').value || '').trim().toUpperCase();
  const direction    = _jDirection;
  const outcome      = _jOutcome;
  const realizedRaw  = document.getElementById('jRealizedPnl').value;
  const realized_pnl = realizedRaw !== '' ? parseFloat(realizedRaw) : null;
  const entryRaw     = document.getElementById('jEntry').value;
  const exitRaw      = document.getElementById('jExit').value;
  const entry_price  = entryRaw !== '' ? parseFloat(entryRaw) : null;
  const exit_price   = exitRaw  !== '' ? parseFloat(exitRaw)  : null;
  const size         = parseFloat(document.getElementById('jSize').value) || 1;
  const stop         = document.getElementById('jStop').value !== '' ? parseFloat(document.getElementById('jStop').value) : null;
  const tp1          = document.getElementById('jTp1').value  !== '' ? parseFloat(document.getElementById('jTp1').value)  : null;
  const setup_type   = (document.getElementById('jSetup').value || '').trim();
  const session      = document.getElementById('jSession').value;
  const notes        = (document.getElementById('jNotes').value || '').trim();
  const trade_date   = document.getElementById('jDate').value || '';

  const msgEl = document.getElementById('jFormMsg');
  function showMsg(text, color) { msgEl.style.display='block'; msgEl.style.color=color; msgEl.textContent=text; }

  if (!ticker) { showMsg('Ticker is required.', 'var(--red)'); return; }
  if (realized_pnl === null && (entry_price === null || exit_price === null)) {
    showMsg('Enter Realized P&L or both Entry and Exit.', 'var(--red)'); return;
  }

  const btn = document.getElementById('jSubmitBtn');
  btn.disabled = true; btn.textContent = 'LOGGING...';
  msgEl.style.display = 'none';

  try {
    const emotional_state  = document.getElementById('jEmotionalState').value;
    const behavioral_flags = ['jFlagEarlyExit','jFlagLateEntry','jFlagHesitation','jFlagOversized','jFlagFomo','jFlagRevenge']
      .filter(id => document.getElementById(id).checked)
      .map(id => document.getElementById(id).value);
    const reflection = (document.getElementById('jReflection').value || '').trim();

    const payload = {ticker, direction, outcome, size, setup_type, session, notes, trade_date};
    if (realized_pnl !== null) payload.realized_pnl = realized_pnl;
    if (entry_price  !== null) payload.entry_price   = entry_price;
    if (exit_price   !== null) payload.exit_price    = exit_price;
    if (stop !== null) payload.stop = stop;
    if (tp1  !== null) payload.tp1  = tp1;
    if (emotional_state)         payload.emotional_state  = emotional_state;
    if (behavioral_flags.length) payload.behavioral_flags = behavioral_flags;
    if (reflection)              payload.reflection        = reflection;
    const res  = await fetch('/journal/add', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const data = await res.json();
    if (data.status === 'ok') {
      ['jTicker','jRealizedPnl','jEntry','jExit','jSize','jStop','jTp1','jSetup','jNotes','jReflection'].forEach(id => { const el = document.getElementById(id); if(el) el.value=''; });
      document.getElementById('jDate').value = todayDateStr();
      document.getElementById('jSession').value = '';
      document.getElementById('jEmotionalState').value = '';
      ['jFlagEarlyExit','jFlagLateEntry','jFlagHesitation','jFlagOversized','jFlagFomo','jFlagRevenge'].forEach(id => { const el = document.getElementById(id); if(el) el.checked = false; });
      setDir('LONG'); setOutcome('WIN');
      showMsg('Trade logged.', 'var(--green)');
      setTimeout(() => { msgEl.style.display='none'; closeJModal(); }, 1200);
      refreshJournal();
    } else {
      showMsg('Error: ' + (data.detail || 'Unknown'), 'var(--red)');
    }
  } catch(e) { showMsg('Connection error.', 'var(--red)'); }
  btn.disabled = false; btn.textContent = 'LOG TRADE';
});

['jTicker','jRealizedPnl','jEntry','jExit','jSize','jStop','jTp1','jSetup','jNotes'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('jSubmitBtn').click(); });
});

// refresh signals when switching to signals tab
document.getElementById('jTab-signals').addEventListener('click', () => refreshSignals());

// ════════ NOVA FEED ════════
let _fdDate      = 'today';
let _fdSym       = 'all';
let _fdOffset    = 0;
let _fdCards     = [];
let _fdSeenIds   = new Set();   // tracks IDs seen so far for unread detection
let _fdUnread    = 0;
let _fdNotifPerm = false;       // true once Notification.permission === 'granted'
let _fdCategory  = 'all';
const CATEGORY_TYPES = {
  intelligence: ['INTELLIGENCE', 'MR2_CHANGE'],
  execution:    ['SIGNAL', 'EXECUTION'],
  system:       ['GOVERNANCE'],
  market:       ['LIQUIDITY_EVENT', 'PARTICIPATION_EVENT'],
};

// ── Notification setup ──────────────────────────────────────────────────────
function initFeedNotifications() {
  if (!('Notification' in window)) return;
  _fdNotifPerm = Notification.permission === 'granted';
  const banner  = document.getElementById('fdNotifBanner');
  const bannerTxt = document.getElementById('fdNotifBannerText');
  const bannerBtn = document.getElementById('fdNotifBannerBtn');
  if (Notification.permission === 'default') {
    if (banner) banner.style.display = 'flex';
  } else if (Notification.permission === 'denied') {
    // Browser-level block — JS cannot re-prompt, must instruct user to reset
    if (banner) banner.style.display = 'flex';
    if (bannerTxt) bannerTxt.textContent = 'Notifications blocked by browser. Click the padlock in the address bar → Notifications → Allow, then reload.';
    if (bannerBtn) bannerBtn.style.display = 'none';
  }
}

function requestFeedNotifPermission() {
  if (!('Notification' in window)) return;
  Notification.requestPermission().then(p => {
    _fdNotifPerm = p === 'granted';
    const banner = document.getElementById('fdNotifBanner');
    if (banner) banner.style.display = 'none';
  });
}

function maybeSendNotif(card) {
  const subtype = card.subtype || '';
  const grade   = (card.grade || '').toUpperCase();
  const isHighPri = (
    subtype === 'EXECUTION_READY' ||
    (subtype === 'HEADS_UP' && (grade === 'A' || grade === 'B'))
  );
  if (!isHighPri) return;

  // Audio ping fires unconditionally — no permission needed, no tab-focus condition.
  // Higher pitch for EXECUTION_READY vs HEADS_UP so they are distinguishable by ear.
  try {
    const actx = new (window.AudioContext || window.webkitAudioContext)();
    const osc  = actx.createOscillator();
    const gain = actx.createGain();
    osc.connect(gain);
    gain.connect(actx.destination);
    osc.type = 'sine';
    osc.frequency.value = subtype === 'EXECUTION_READY' ? 880 : 660;
    gain.gain.setValueAtTime(0, actx.currentTime);
    gain.gain.linearRampToValueAtTime(0.12, actx.currentTime + 0.01);
    gain.gain.linearRampToValueAtTime(0, actx.currentTime + 0.18);
    osc.start(actx.currentTime);
    osc.stop(actx.currentTime + 0.19);
    osc.onended = () => actx.close();
    if (actx.state === 'suspended') actx.resume();
  } catch(_) {}

  // Browser popup — requires permission grant.
  if (!_fdNotifPerm) return;
  try {
    const sym  = toMarketSym(card.symbol || '');
    const dir  = card.direction || '';
    const body = [
      card.strategy_family ? card.strategy_family : '',
      card.setup_type ? card.setup_type : '',
      card.entry_zone ? 'Entry: ' + card.entry_zone : '',
      card.rr ? 'R:R ' + card.rr : '',
      (card.mr2 || {}).state ? 'MR2: ' + card.mr2.state : '',
    ].filter(Boolean).join(' · ');
    new Notification('NOVA — ' + subtype.replace('_',' ') + ' ' + grade + ' ' + sym + ' ' + dir, {
      body: body || 'New intelligence event',
      tag:  card.id || subtype,
    });
  } catch(e) {}
}

function clearFeedUnread() {
  _fdUnread = 0;
  const dot = document.getElementById('feedUnreadDot');
  if (dot) dot.style.display = 'none';
}

function setFdDate(val, btn) {
  _fdDate = val;
  document.querySelectorAll('[data-fd-date]').forEach(b => b.classList.toggle('active', b === btn));
  _fdOffset = 0; _fdCards = [];
  refreshFeed();
}
function setFdSym(val, btn) {
  _fdSym = val;
  document.querySelectorAll('[data-fd-sym]').forEach(b => b.classList.toggle('active', b === btn));
  _fdOffset = 0; _fdCards = [];
  refreshFeed();
}
function setFdCat(cat, btn) {
  _fdCategory = cat;
  document.querySelectorAll('[data-fd-cat]').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderFeed('');
}
async function loadMoreFeed() {
  _fdOffset += 50;
  await refreshFeed(true);
}

async function refreshFeed(append) {
  const params = new URLSearchParams({ limit: 50, offset: _fdOffset });
  let todayStr = '';
  if (_fdDate === 'today') {
    const t = new Date();
    todayStr = t.getFullYear() + '-' + String(t.getMonth()+1).padStart(2,'0') + '-' + String(t.getDate()).padStart(2,'0');
    params.set('date', todayStr);
  }
  if (_fdSym !== 'all') params.set('symbol', _fdSym);
  try {
    const [feedRes, statsRes] = await Promise.all([
      fetch('/api/feed?' + params),
      append ? Promise.resolve(null) : fetch('/api/feed/stats'),
    ]);
    if (!feedRes.ok) { setHtml('feedBody', '<div class="fd-empty">Feed unavailable.</div>'); return; }
    const data = await feedRes.json();
    const newCards = data.feed || [];

    // Detect genuinely new cards for unread badge + notifications.
    // maybeSendNotif() fires for all high-priority cards regardless of which tab is visible —
    // audio has no permission dependency; browser popup respects granted permission.
    // Unread badge only increments when not watching the Alerts tab.
    const isOnFeedPage = document.getElementById('page-alerts').classList.contains('active');
    newCards.forEach(c => {
      if (_fdSeenIds.has(c.id)) return;
      if (_fdSeenIds.size > 0) {          // skip first load
        maybeSendNotif(c);
        if (!isOnFeedPage) _fdUnread++;
      }
      _fdSeenIds.add(c.id);
    });
    if (_fdUnread > 0) {
      const dot = document.getElementById('feedUnreadDot');
      if (dot) dot.style.display = '';
    }

    if (!append) _fdCards = newCards;
    else _fdCards = _fdCards.concat(newCards);
    renderFeed(todayStr);
    if (statsRes && statsRes.ok) {
      const stats = await statsRes.json();
      renderFdStats(stats);
    }
    const now = new Date();
    setText('fdLastUpdated', now.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',second:'2-digit'}));
    const lm = document.getElementById('fdLoadMore');
    if (lm) lm.style.display = data.has_more ? '' : 'none';
  } catch(e) {
    console.error('Feed error:', e);
    setHtml('feedBody', '<div class="fd-empty">Connection error.</div>');
  }
}

function renderFeed(todayStr) {
  const cards = _fdCategory === 'all' ? _fdCards : _fdCards.filter(c => (CATEGORY_TYPES[_fdCategory] || []).includes(c.event_type));
  if (!cards.length) {
    let msg = 'No events for this filter.';
    if (_fdDate === 'today' && _fdCategory === 'all') msg = 'No events today (' + (todayStr||'') + ').<br>Switch to <strong>ALL TIME</strong> to see history.';
    if (_fdCategory === 'market') msg = 'No MARKET events yet. Events appear when liquidity levels are swept or RVOL shifts significantly during the session.';
    else if (_fdCategory !== 'all') msg = 'No ' + _fdCategory.toUpperCase() + ' events for this period.';
    setHtml('feedBody', '<div class="fd-empty">' + msg + '</div>');
    return;
  }
  setHtml('feedBody', cards.map(c => fdCard(c)).join(''));
}

function fdCard(c) {
  const t = c.event_type || '';
  if (t === 'SIGNAL')            return fdSignal(c);
  if (t === 'EXECUTION')         return fdExecution(c);
  if (t === 'GOVERNANCE')        return fdGovernance(c);
  if (t === 'MR2_CHANGE')        return fdMr2Change(c);
  if (t === 'INTELLIGENCE')      return fdIntelligence(c);
  if (t === 'LIQUIDITY_EVENT')   return fdMarketEvent(c);
  if (t === 'PARTICIPATION_EVENT') return fdMarketEvent(c);
  return '';
}

function fdIntelligence(c) {
  var intel = c.intelligence || {};
  var sub   = (c.subtype || 'INTELLIGENCE').replace(/_/g,' ');
  var body  = c.claude_rationale || intel.brief_text || intel.thesis || '';
  var kq    = intel.key_question || '';
  var chips = '';
  if (intel.liquidity_draw) chips += fdChip('DRAW', intel.liquidity_draw);
  if (intel.participation)  chips += fdChip('RVOL', intel.participation);
  if (intel.macro_risk)     chips += fdChip('MACRO', (intel.macro_risk||'').toUpperCase());
  if (intel.confidence)     chips += fdChip('CONF', intel.confidence);
  var html = '<div class="fd-card fd-intelligence">';
  html += '<div class="fd-row1"><span class="fd-ts">' + fdTs(c.timestamp_et) + '</span>';
  if (c.session) html += fdChip('', c.session);
  html += '<span class="fd-badge ev-intel">' + sub + '</span></div>';
  if (body) html += '<div class="fd-rationale-text" style="margin-top:6px;font-size:12px;line-height:1.6">' + body + '</div>';
  if (chips) html += '<div class="fd-row2" style="margin-top:6px">' + chips + '</div>';
  if (kq) html += '<div style="margin-top:5px;font-size:11px;color:var(--muted2);font-style:italic">&#9658; ' + kq + '</div>';
  html += '</div>';
  return html;
}

function fdMarketEvent(c) {
  var sub  = (c.subtype || 'MARKET EVENT').replace(/_/g,' ');
  var sym  = toMarketSym(c.symbol || '');
  var body = c.claude_rationale || c.description || '';
  var chips = '';
  if (c.level)        chips += fdChip('LEVEL', c.level);
  if (c.price)        chips += fdChip('PRICE', c.price);
  if (c.significance) chips += fdChip('SIG', c.significance);
  var html = '<div class="fd-card fd-market">';
  html += '<div class="fd-row1"><span class="fd-ts">' + fdTs(c.timestamp_et) + '</span>';
  if (sym) html += '<span class="fd-symbol">' + sym + '</span>';
  html += '<span class="fd-badge ev-market">' + sub + '</span></div>';
  if (body) html += '<div class="fd-rationale-text" style="margin-top:5px;font-size:12px">' + body + '</div>';
  if (chips) html += '<div class="fd-row2" style="margin-top:6px">' + chips + '</div>';
  html += '</div>';
  return html;
}

function fdTs(ts) {
  if (!ts) return '—';
  const s = String(ts).replace(' ET','').trim();
  const parts = s.split(' ');
  return parts.length >= 2 ? parts[1] : s;
}
function fdChip(label, val) {
  if (val === null || val === undefined || val === '') return '';
  return '<span class="fd-chip">' + label + ' <strong>' + val + '</strong></span>';
}
function fdGradeClass(g) {
  const m = {A:'grade-a', B:'grade-b', C:'grade-c', D:'grade-d'};
  return m[(g||'').toUpperCase()] || 'grade-d';
}
function fdDirClass(d) {
  const v = (d||'').toUpperCase();
  if (v === 'LONG' || v === 'BUY')   return 'dir-long';
  if (v === 'SHORT' || v === 'SELL') return 'dir-short';
  return '';
}
function fdSubClass(st) {
  const m = {EXECUTION_READY:'st-er', HEADS_UP:'st-hu', EVALUATED:'st-ev', INVALIDATION:'st-inv', NO_TRADE:'st-nt'};
  return m[st] || 'st-ev';
}
function toMarketSym(sym) {
  if (!sym) return sym;
  const s = sym.toUpperCase();
  if (s === 'MNQ') return 'NQ';
  if (s === 'MES') return 'ES';
  return sym;
}

function fdToggleRationale(id) {
  const el = document.getElementById('fdRat_' + id);
  if (!el) return;
  const btn = document.getElementById('fdRatBtn_' + id);
  const open = el.classList.toggle('open');
  if (btn) btn.textContent = open ? '▲ COLLAPSE' : '▼ FULL REASONING';
}

function fdSignal(c) {
  const alerted  = c.alert_fired;
  const subtype  = c.subtype || 'EVALUATED';
  const grade    = (c.grade||'').toUpperCase();
  const dir      = (c.direction||'').toUpperCase();
  const mr2      = c.mr2  || {};
  const dp       = c.dp   || {};
  const draw     = c.draw || {};
  const rat      = c.claude_rationale || c.pre_rationale || '';
  const uid      = (c.source_id || c.id || '').replace(/[^a-zA-Z0-9]/g, '_');

  let cls = 'fd-card fd-signal';
  if (alerted) {
    cls += ' fd-alerted';
    if (grade === 'A') cls += ' fd-grade-a';
    else if (grade === 'B') cls += ' fd-grade-b';
  }

  const dirBadge     = dir     ? '<span class="fd-badge ' + fdDirClass(dir) + '">' + dir + '</span>' : '';
  const gradeBadge   = grade   ? '<span class="fd-badge ' + fdGradeClass(grade) + '">' + grade + '</span>' : '';
  const subtypeBadge = subtype ? '<span class="fd-badge ' + fdSubClass(subtype) + '">' + subtype.replace(/_/g,' ') + '</span>' : '';
  const symEl        = c.symbol ? '<span class="fd-symbol">' + toMarketSym(c.symbol) + '</span>' : '';

  const dpTxt   = dp.dominance ? dp.dominance + (dp.conviction ? ' ' + dp.conviction : '') : '';
  const drawTxt = draw.name ? draw.name + (draw.category ? ' (' + draw.category + ')' : '') : '';

  const chips = [
    fdChip('FAMILY',  c.strategy_family),
    fdChip('SETUP',   c.setup_type),
    fdChip('SESSION', c.session),
    fdChip('MR2',     mr2.state),
    dpTxt  ? fdChip('DP',   dpTxt)   : '',
    drawTxt ? fdChip('DRAW', drawTxt) : '',
  ].filter(Boolean).join('');

  // Entry levels row — only for EXECUTION_READY or when any level present
  let entryRow = '';
  if (c.entry_zone || c.stop || c.tp1 || c.rr) {
    entryRow = '<div class="fd-entry-row">' +
      (c.entry_zone ? '<div class="fd-entry-cell">ENTRY<strong>' + c.entry_zone + '</strong></div>' : '') +
      (c.stop       ? '<div class="fd-entry-cell">STOP<strong>' + c.stop + '</strong></div>' : '') +
      (c.tp1        ? '<div class="fd-entry-cell">TP1<strong>' + c.tp1 + '</strong></div>' : '') +
      (c.rr         ? '<div class="fd-entry-cell">R:R<strong>' + c.rr + '</strong></div>' : '') +
      '</div>';
  }

  // MR2 block flags inline
  const blockBits = [
    mr2.block_longs  ? '<span style="color:var(--red);font-size:9px;font-weight:700">⛔ LONGS BLOCKED</span>' : '',
    mr2.block_shorts ? '<span style="color:var(--red);font-size:9px;font-weight:700">⛔ SHORTS BLOCKED</span>' : '',
  ].filter(Boolean).join(' ');

  // Rationale — first 2 lines always, expandable for full text
  let ratEl = '';
  if (rat) {
    const short = rat.length > 180 ? rat.slice(0, 180) + '…' : rat;
    if (rat.length > 180) {
      ratEl = '<div class="fd-rationale" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">' + short + '</div>' +
              '<div class="fd-rationale-full" id="fdRat_' + uid + '" style="display:none">' + rat + '</div>' +
              '<button class="fd-expand-btn" id="fdRatBtn_' + uid + '" data-uid="' + uid + '" onclick="fdToggleRationale(this.dataset.uid)" style="display:block">▼ FULL REASONING</button>';
    } else {
      ratEl = '<div class="fd-rationale" style="max-height:none;overflow:visible">' + rat + '</div>';
    }
  }

  return '<div class="' + cls + '">' +
    '<div class="fd-row1"><span class="fd-ts">' + fdTs(c.timestamp_et) + '</span>' + symEl + dirBadge + gradeBadge + subtypeBadge + '</div>' +
    '<div class="fd-row2">' + (chips || '<span class="fd-chip">no context</span>') + (blockBits ? ' ' + blockBits : '') + '</div>' +
    entryRow +
    ratEl + '</div>';
}

function fdGovernance(c) {
  const code   = c.rejection_code || 'GOV';
  const reason = c.rejection_reason || '—';
  const sym    = c.symbol ? '<span class="fd-symbol">' + toMarketSym(c.symbol) + '</span>' : '';
  const dir    = c.direction ? '<span class="fd-badge ' + fdDirClass(c.direction) + '">' + c.direction.toUpperCase() + '</span>' : '';
  const grade  = c.grade ? '<span class="fd-badge ' + fdGradeClass(c.grade) + '">' + c.grade.toUpperCase() + '</span>' : '';
  return '<div class="fd-card fd-governance">' +
    '<div class="fd-row1"><span class="fd-ts">' + fdTs(c.timestamp_et) + '</span>' +
    sym + dir + grade +
    '<span class="fd-badge ev-gov">' + code.replace(/_/g,' ') + '</span></div>' +
    '<div class="fd-gov-reason">' + reason + '</div></div>';
}

function fdExecution(c) {
  const dir    = (c.direction||'').toUpperCase();
  const sym    = c.etf || c.ticker || c.symbol || '—';
  const qty    = c.qty || 0;
  const entry  = c.entry_ref  ? _fmtPrice(c.entry_ref)  : '—';
  const stop   = c.stop_px    ? _fmtPrice(c.stop_px)    : '—';
  const target = c.target_px  ? _fmtPrice(c.target_px)  : '—';
  const risk   = c.risk_usd   ? _fmtUsd(c.risk_usd) : '—';
  return '<div class="fd-card fd-execution">' +
    '<div class="fd-row1"><span class="fd-ts">' + fdTs(c.timestamp_et) + '</span>' +
    '<span class="fd-symbol">' + sym + '</span>' +
    '<span class="fd-badge ' + fdDirClass(dir) + '">' + (dir||'?') + '</span>' +
    '<span class="fd-badge ev-exec">EXECUTED</span></div>' +
    '<div class="fd-entry-row">' +
    (qty    ? '<div class="fd-entry-cell">QTY<strong>' + qty + '</strong></div>' : '') +
    (entry !== '—' ? '<div class="fd-entry-cell">ENTRY<strong>' + entry + '</strong></div>' : '') +
    (stop  !== '—' ? '<div class="fd-entry-cell">STOP<strong>' + stop + '</strong></div>' : '') +
    (target !== '—' ? '<div class="fd-entry-cell">TARGET<strong>' + target + '</strong></div>' : '') +
    (risk  !== '—' ? '<div class="fd-entry-cell">RISK<strong>' + risk + '</strong></div>' : '') +
    '</div></div>';
}

function fdMr2Change(c) {
  const mr2 = c.mr2 || {};
  const sym = toMarketSym(c.symbol || '—');
  const sub = (c.subtype||'STATE CHANGE').replace(/_/g,' ');
  const scoreVal = mr2.score !== null && mr2.score !== undefined ? (mr2.score >= 0 ? '+' : '') + mr2.score : '';
  return '<div class="fd-card fd-mr2change">' +
    '<div class="fd-row1"><span class="fd-ts">' + fdTs(c.timestamp_et) + '</span>' +
    '<span class="fd-symbol">' + sym + '</span>' +
    '<span class="fd-badge ev-mr2">' + sub + '</span></div>' +
    '<div class="fd-row2">' +
    fdChip('FROM', mr2.from_state) + fdChip('→', mr2.state) + (scoreVal ? fdChip('SCORE', scoreVal) : '') +
    (mr2.block_longs  ? '<span class="fd-chip" style="color:var(--red);font-weight:700"><strong>⛔ LONGS BLOCKED</strong></span>'  : '') +
    (mr2.block_shorts ? '<span class="fd-chip" style="color:var(--red);font-weight:700"><strong>⛔ SHORTS BLOCKED</strong></span>' : '') +
    (mr2.block_reason ? '<span class="fd-chip" style="color:var(--muted)"><strong>' + mr2.block_reason.slice(0,80) + '</strong></span>' : '') +
    '</div></div>';
}

function renderFdStats(stats) {
  const sig = stats.signals   || {};
  const ex  = stats.execution || {};
  const bg  = sig.by_grade    || {};
  const parts = [
    '<span class="fd-stat">SIGNALS <strong>' + (sig.total||0) + '</strong></span>',
    bg.A ? '<span class="fd-stat">A <strong style="color:var(--green)">'  + bg.A + '</strong></span>' : '',
    bg.B ? '<span class="fd-stat">B <strong style="color:var(--yellow)">' + bg.B + '</strong></span>' : '',
    '<span class="fd-stat">ALERTS <strong>' + (sig.alerts_fired||0) + '</strong></span>',
    '<span class="fd-stat">EXECUTED <strong>'  + (ex.total_executed||0) + '</strong></span>',
    '<span class="fd-stat">REJECTED <strong>' + (ex.total_rejected||0) + '</strong></span>',
  ];
  setHtml('fdStatsRow', parts.filter(Boolean).join(''));
}

// ════════ MARKET REALITY ════════
function mrStateClass(state) {
  const s = (state||'').toUpperCase();
  if (s.includes('BULLISH_DOMINANT')) return 'mr-state-bull-dom';
  if (s.includes('BULLISH_LEANING'))  return 'mr-state-bull-lean';
  if (s.includes('BEARISH_DOMINANT')) return 'mr-state-bear-dom';
  if (s.includes('BEARISH_LEANING'))  return 'mr-state-bear-lean';
  if (s.includes('PANIC'))            return 'mr-state-panic';
  if (s.includes('RANGE'))            return 'mr-state-range';
  return 'mr-state-neutral';
}

async function refreshMarketReality() {
  try {
    const res = await fetch('/market-reality');
    if (!res.ok) return;
    const d = await res.json();

    // State badge
    const state = d.state || d.direction || 'UNKNOWN';
    const badge = document.getElementById('mrStateBadge');
    if (badge) {
      badge.textContent = state.replace(/_/g,' ');
      badge.className = 'mr-state-badge ' + mrStateClass(state);
    }

    // Block flags
    const flagsEl = document.getElementById('mrBlockFlags');
    if (flagsEl) {
      const blockL = d.block_longs  || (d.bullish_execution_allowed === false);
      const blockS = d.block_shorts || (d.short_execution_allowed   === false);
      flagsEl.innerHTML =
        '<span class="mr-block-flag ' + (blockL ? 'mr-block-active' : 'mr-block-clear') + '">' +
        (blockL ? '⛔' : '✓') + ' LONGS</span>' +
        '<span class="mr-block-flag ' + (blockS ? 'mr-block-active' : 'mr-block-clear') + '">' +
        (blockS ? '⛔' : '✓') + ' SHORTS</span>';
    }

    // Price cells
    const nqP = d.nq_price || 0;
    const esP = d.es_price || 0;
    const nqPct = d.nq_change_pct || d.nq_pct || 0;
    const esPct = d.es_change_pct || d.es_pct || 0;
    const vix   = d.vix || 0;
    const score = d.score !== undefined ? d.score : null;

    setText('mrNqPrice', nqP ? nqP.toLocaleString('en-US',{maximumFractionDigits:2}) : '—');
    setText('mrNqPct',   nqPct ? (nqPct >= 0 ? '+' : '') + nqPct.toFixed(2) + '%' : '—');
    setText('mrEsPrice', esP ? esP.toLocaleString('en-US',{maximumFractionDigits:2}) : '—');
    setText('mrEsPct',   esPct ? (esPct >= 0 ? '+' : '') + esPct.toFixed(2) + '%' : '—');
    setText('mrVix',     vix ? vix.toFixed(1) : '—');
    setText('mrSession', d.session || '—');
    setText('mrRegime',  d.market_regime || d.regime || '—');
    setText('mrWeekly',  (d.weekly_structure || d.structure || '—').replace(/_/g,' '));
    setText('mrDisplacement', d.displacement || '—');

    if (score !== null) {
      setText('mrScore', (score >= 0 ? '+' : '') + score);
      // Score bar: 0 = center, max ±19
      const pct = Math.min(100, Math.max(0, ((score + 19) / 38) * 100));
      const bar = document.getElementById('mrScoreBar');
      if (bar) {
        bar.style.width = Math.abs(pct - 50) + '%';
        bar.style.marginLeft = score >= 0 ? '50%' : (pct + '%');
        bar.className = score >= 0 ? 'mr-score-fill-bull' : 'mr-score-fill-bear';
      }
    }

    // Fact breakdown
    const fb = document.getElementById('mrFactBreakdown');
    if (fb) {
      const rows = [];
      if (d.bull_fact_count !== undefined) rows.push('Bull facts: +' + d.bull_fact_count);
      if (d.bear_fact_count !== undefined) rows.push('Bear facts: −' + d.bear_fact_count);
      if (d.block_longs_reason)  rows.push('Long block: ' + d.block_longs_reason);
      if (d.block_shorts_reason) rows.push('Short block: ' + d.block_shorts_reason);
      if (d.nq_week_high) rows.push('NQ week hi/lo: ' + d.nq_week_high + ' / ' + (d.nq_week_low||'—'));
      if (d.es_week_high)  rows.push('ES week hi/lo: ' + d.es_week_high  + ' / ' + (d.es_week_low||'—'));
      fb.innerHTML = rows.length ? rows.map(r => '<div>' + r + '</div>').join('') : '<div>No breakdown available</div>';
    }

    // Block reason panel
    const blockReason = d.block_longs_reason || d.block_shorts_reason || '';
    const brWrap = document.getElementById('mrBlockReasonWrap');
    if (brWrap) {
      brWrap.style.display = blockReason ? '' : 'none';
      setText('mrBlockReason', blockReason);
    }

    const ts = d.last_updated ? new Date(d.last_updated).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',second:'2-digit'}) : '—';
    setText('mrLastUpdated', ts);
  } catch(e) {
    console.error('MR error:', e);
  }
}

// ════════ GOVERNANCE ════════
function govBadge(open, label) {
  const cls = open ? 'gov-open' : 'gov-locked';
  const txt = open ? (label || 'OPEN') : (label || 'LOCKED');
  return '<span class="gov-status ' + cls + '">' + txt + '</span>';
}
function govGate(name, detail, open, label) {
  return '<div class="gov-gate">' +
    '<span class="gov-gate-name">' + name + '</span>' +
    '<span class="gov-gate-detail">' + (detail||'') + '</span>' +
    govBadge(open, label) +
    '</div>';
}
function govWarn(name, detail, warn, label) {
  const cls = warn ? 'gov-warn' : 'gov-open';
  const txt = warn ? (label || 'WARN') : 'CLEAR';
  return '<div class="gov-gate">' +
    '<span class="gov-gate-name">' + name + '</span>' +
    '<span class="gov-gate-detail">' + (detail||'') + '</span>' +
    '<span class="gov-status ' + cls + '">' + txt + '</span>' +
    '</div>';
}

async function refreshGovernance() {
  try {
    const res = await fetch('/api/governance');
    if (!res.ok) return;
    const d = await res.json();

    const execMode  = d.execution_mode || 'disabled';
    const autoExec  = d.nova_auto_execute || false;
    const tradePerm = d.trade_permission  || false;
    const tradesDay = d.daily_trade_count || 0;
    const maxTrades = d.max_trades        || 5;
    const openPos   = d.open_positions_count || 0;
    const maxPos    = d.max_concurrent_positions || 2;
    const minGrade  = d.min_grade || 'N/A';

    // System gates
    const sysHtml = [
      govGate('NOVA_AUTO_EXECUTE', 'env var — master enable', autoExec, autoExec ? 'ON' : 'OFF'),
      govGate('execution_mode',    execMode + (d.risk_tier ? ' · ' + d.risk_tier : ''), execMode !== 'disabled', execMode !== 'disabled' ? execMode.toUpperCase() : 'DISABLED'),
      govGate('min_grade',         'minimum grade required', minGrade === 'A' || minGrade === 'B' || minGrade === 'N/A', minGrade),
      govGate('trade_permission',  'daily permission flag', tradePerm, tradePerm ? 'OPEN' : 'CLOSED'),
    ].join('');
    setHtml('govSystemGates', sysHtml);

    // Risk gates
    const riskHtml = [
      govGate('eod_lock',          'no entries after 15:30 ET', !d.eod_lock,        d.eod_lock ? 'LOCKED' : 'OPEN'),
      govGate('macro_lock',        'macro event active',        !d.macro_lock,       d.macro_lock ? 'LOCKED' : 'OPEN'),
      govGate('red_folder_lock',   'red-folder event',          !d.red_folder_lock,  d.red_folder_lock ? 'LOCKED' : 'OPEN'),
      govGate('execution_lock',    'execution lock flag',       !d.execution_lock,   d.execution_lock ? 'LOCKED' : 'OPEN'),
      govWarn('size_reduction',    'adverse prior outcome',     d.size_reduction_active, d.size_reduction_active ? 'ACTIVE' : ''),
    ].join('');
    setHtml('govRiskGates', riskHtml);

    // Position gates
    const posHtml = [
      govGate('daily trades',      tradesDay + ' / ' + maxTrades + ' used', tradesDay < maxTrades, tradesDay + '/' + maxTrades),
      govGate('concurrent positions', openPos + ' / ' + maxPos + ' open', openPos < maxPos, openPos + '/' + maxPos),
      govGate('daily P&L',         _fmtUsd(d.daily_pnl || 0), (d.daily_pnl || 0) >= 0, _fmtPnl(d.daily_pnl || 0)),
    ].join('');
    setHtml('govPositionGates', posHtml);

    // Cooldowns
    const now = Date.now();
    const spyCool = d.spy_cooldown_until ? new Date(d.spy_cooldown_until) : null;
    const qqqCool = d.qqq_cooldown_until ? new Date(d.qqq_cooldown_until) : null;
    const spyActive = spyCool && spyCool > now;
    const qqqActive = qqqCool && qqqCool > now;
    const coolHtml = [
      govGate('SPY cooldown', spyActive ? 'until ' + spyCool.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'}) : 'no cooldown', !spyActive, spyActive ? 'ACTIVE' : 'CLEAR'),
      govGate('QQQ cooldown', qqqActive ? 'until ' + qqqCool.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'}) : 'no cooldown', !qqqActive, qqqActive ? 'ACTIVE' : 'CLEAR'),
    ].join('');
    setHtml('govCooldowns', coolHtml);

    // Lockouts
    const lockouts = d.risk_lockouts || [];
    const lockWrap = document.getElementById('govLockoutsWrap');
    if (lockWrap) {
      lockWrap.style.display = lockouts.length ? '' : 'none';
      setHtml('govLockouts', lockouts.slice(-8).reverse().map(l =>
        '<div class="gov-lockout-item">' + (l.reason||'') + (l.timestamp ? ' · ' + l.timestamp.slice(11,16) + 'Z' : '') + '</div>'
      ).join(''));
    }

    // Blocked signals
    const blocked = d.blocked_signals_today || [];
    const blkWrap = document.getElementById('govBlockedWrap');
    if (blkWrap) {
      blkWrap.style.display = blocked.length ? '' : 'none';
      setHtml('govBlocked', blocked.map(b =>
        '<div class="gov-lockout-item">' + (typeof b === 'string' ? b : JSON.stringify(b)) + '</div>'
      ).join(''));
    }

    const ts = d.last_updated ? new Date(d.last_updated).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',second:'2-digit'}) : '—';
    setText('govLastUpdated', ts);
  } catch(e) {
    console.error('Gov error:', e);
  }
}

// ════════ EXECUTION CENTER SUB-NAV ════════
function switchEcTab(tab) {
  ['execution','governance','audit'].forEach(function(t) {
    var btn = document.getElementById('ecTab-' + t);
    var sec = document.getElementById('ec-section-' + t);
    if (btn) btn.classList.toggle('active', t === tab);
    if (sec) sec.style.display = t === tab ? '' : 'none';
  });
  if (tab === 'governance') refreshGovernance();
}

// ════════ HARVEY SUB-NAV ════════
function switchHvSubTab(tab) {
  ['harvey','mr','draws'].forEach(function(t) {
    var btn = document.getElementById('hvTab-' + t);
    var sec = document.getElementById('hv-section-' + t);
    if (btn) btn.classList.toggle('active', t === tab);
    if (sec) sec.style.display = t === tab ? '' : 'none';
  });
  if (tab === 'mr') refreshMarketReality();
}


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
initFeedNotifications();
refresh();
setInterval(refresh, 30000);
refreshJournal();
setInterval(refreshJournal, 60000);
// Execution tab refreshes on-demand via tab click; also poll in background
setInterval(refreshExecutionTab, 30000);
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
// Feed auto-refresh every 30s to detect new events and fire browser notifications
setInterval(refreshFeed, 30000);
// Market Reality and Governance auto-refresh every 60s in background
setInterval(refreshMarketReality, 60000);
setInterval(refreshGovernance, 30000);
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
