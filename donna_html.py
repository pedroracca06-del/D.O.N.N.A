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
  --bg:#060d1a;
  --bg2:#091220;
  --panel:#0e1c35;
  --panel2:#122040;
  --line:rgba(100,160,255,.10);
  --line2:rgba(100,160,255,.06);
  --text:#e8f2ff;
  --muted:#7a99c8;
  --muted2:#4d6a9a;
  --blue:#4d8fff;
  --blue2:#2563eb;
  --blue3:#1a3f80;
  --green:#00e5a0;
  --green2:rgba(0,229,160,.12);
  --yellow:#ffc93c;
  --red:#ff4d6d;
  --red2:rgba(255,77,109,.12);
  --gold:#f0b429;
  --shadow:0 24px 64px rgba(0,0,0,.45);
  --shadow2:0 8px 24px rgba(0,0,0,.3);
  --radius:18px;
  --radius2:12px;
}

html,body{min-height:100%;background:var(--bg)}
body{
  font-family:'Inter',sans-serif;
  color:var(--text);
  background:
    radial-gradient(ellipse at 0% 100%, rgba(0,229,160,.07) 0%, transparent 40%),
    radial-gradient(ellipse at 100% 0%, rgba(37,99,235,.12) 0%, transparent 35%),
    radial-gradient(ellipse at 50% 50%, rgba(14,28,53,.8) 0%, transparent 100%),
    var(--bg);
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
  background:linear-gradient(135deg,#fff 30%,var(--blue) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
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
  background:rgba(0,229,160,.07);border:1px solid rgba(0,229,160,.2);
  font-family:'Space Mono',monospace;font-size:11px;color:#00e5a0;font-weight:700;
  letter-spacing:1px;
}
.dot{
  width:8px;height:8px;border-radius:50%;background:var(--green);
  box-shadow:0 0 10px rgba(0,229,160,.9);
  animation:pulse 2s ease-in-out infinite;
}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(.85)}}
.nav{display:flex;gap:8px}
.tab-btn{
  font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;letter-spacing:1px;
  border:1px solid var(--line);padding:9px 18px;border-radius:10px;
  background:rgba(255,255,255,.03);color:var(--muted);
  cursor:pointer;transition:all .2s ease;text-transform:uppercase;
}
.tab-btn:hover{color:var(--text);border-color:rgba(77,143,255,.3);background:rgba(77,143,255,.07)}
.tab-btn.active{
  background:linear-gradient(135deg,var(--blue),var(--blue2));
  border-color:transparent;color:#fff;
  box-shadow:0 4px 20px rgba(37,99,235,.4);
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
  background:rgba(255,77,109,.07);border:1px solid rgba(255,77,109,.18);
}
.ticker-wrap{
  overflow:hidden;border-radius:var(--radius2);
  background:var(--panel);border:1px solid var(--line2);
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
  background:linear-gradient(180deg,rgba(16,32,64,.98),rgba(10,22,48,.99));
  border:1px solid var(--line);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:17px;
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
.risk-low{background:rgba(0,229,160,.12);color:var(--green);border:1px solid rgba(0,229,160,.25)}
.risk-medium{background:rgba(255,201,60,.10);color:var(--yellow);border:1px solid rgba(255,201,60,.25)}
.risk-high{background:rgba(255,77,109,.12);color:var(--red);border:1px solid rgba(255,77,109,.25)}

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
  padding:13px 16px;border-radius:12px;margin-bottom:10px;
  border-left:3px solid var(--blue);
  background:rgba(77,143,255,.06);
}
.obs-item:last-child{margin-bottom:0}
.obs-item.high{border-left-color:var(--red);background:rgba(255,77,109,.06)}
.obs-item.medium{border-left-color:var(--yellow);background:rgba(255,201,60,.06)}
.obs-item.low{border-left-color:var(--muted2);background:rgba(255,255,255,.03)}
.obs-title{font-size:13px;font-weight:700;margin-bottom:4px}
.obs-body{font-size:12px;color:var(--muted);line-height:1.5}

/* ── CROSS-ASSET INTELLIGENCE ── */
.ca-mode-badge{
  font-family:'Space Mono',monospace;font-size:10px;font-weight:700;letter-spacing:1px;
  padding:4px 10px;border-radius:6px;text-transform:uppercase;
}
.ca-mode-ALIGNED  {background:rgba(0,229,160,.12);color:var(--green);border:1px solid rgba(0,229,160,.25)}
.ca-mode-MIXED    {background:rgba(255,201,60,.10);color:var(--yellow);border:1px solid rgba(255,201,60,.25)}
.ca-mode-DIVERGING{background:rgba(255,140,50,.12);color:#ff8c32;border:1px solid rgba(255,140,50,.3)}
.ca-mode-WARNING  {background:rgba(255,77,109,.12);color:var(--red);border:1px solid rgba(255,77,109,.3)}
.ca-div-item{
  padding:10px 12px;border-radius:10px;margin-bottom:8px;
  border-left:3px solid var(--muted2);background:rgba(255,255,255,.03);
}
.ca-div-item:last-child{margin-bottom:0}
.ca-div-item.HIGH{border-left-color:var(--red);background:rgba(255,77,109,.05)}
.ca-div-item.MEDIUM{border-left-color:var(--yellow);background:rgba(255,201,60,.05)}
.ca-div-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:8px}
.ca-div-name{font-size:12px;font-weight:700;color:var(--text)}
.ca-sev-badge{
  font-family:'Space Mono',monospace;font-size:9px;font-weight:700;letter-spacing:.5px;
  padding:2px 7px;border-radius:4px;flex-shrink:0;
}
.ca-sev-HIGH  {background:rgba(255,77,109,.15);color:var(--red);border:1px solid rgba(255,77,109,.3)}
.ca-sev-MEDIUM{background:rgba(255,201,60,.12);color:var(--yellow);border:1px solid rgba(255,201,60,.25)}
.ca-div-meaning{font-size:11px;color:var(--muted);line-height:1.5;margin-bottom:4px}
.ca-div-watch{font-size:11px;color:var(--muted2);line-height:1.4}
.ca-div-watch b{color:var(--text);font-weight:600}
.ca-clean{font-size:12px;color:var(--green);padding:6px 0;opacity:.85}

/* ── HERO BANNER ── */
.hero-banner{
  padding:16px 20px;border-radius:16px;
  border:1px solid rgba(77,143,255,.2);
  background:
    radial-gradient(circle at top right, rgba(37,99,235,.15) 0%, transparent 50%),
    linear-gradient(180deg,rgba(16,32,64,.98),rgba(10,22,48,.99));
  box-shadow:var(--shadow);
}
.hero-eyebrow{
  font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2.5px;
  color:var(--blue);text-transform:uppercase;margin-bottom:8px;
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
  border:1px solid var(--line);background:rgba(255,255,255,.03);
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
/* ── PLAYBOOK BAR (slim single-row) ── */
.playbook-bar{
  display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  padding:10px 16px;border-radius:10px;
  background:var(--panel);border:1px solid var(--line2);
  font-size:12px;
}
.pb-bar-label{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1px;color:var(--muted2);text-transform:uppercase;margin-right:4px}
.pb-bar-val{font-weight:600;color:var(--text)}
.pb-bar-sep{color:var(--line);font-size:14px}
.pb-bar-note{color:var(--muted);flex:1;font-size:11px}
/* ── PLAYBOOK NAV BTN ── */
.playbook-btn{background:linear-gradient(135deg,rgba(139,92,246,.12),rgba(139,92,246,.05))!important;border-color:rgba(139,92,246,.25)!important;color:#a78bfa!important}
.playbook-btn.active{background:linear-gradient(135deg,#5b21b6,#4c1d95)!important;border-color:transparent!important;color:#fff!important;box-shadow:0 4px 20px rgba(139,92,246,.35)!important}

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

/* ── NEWS (Bloomberg-CNBC redesign) ── */
.breaking-bar{
  display:flex;align-items:center;gap:0;overflow:hidden;
  border-radius:10px;background:rgba(255,77,109,.08);
  border:1px solid rgba(255,77,109,.25);height:38px;margin-bottom:0;
}
.breaking-label{
  flex-shrink:0;padding:0 14px;font-family:'Space Mono',monospace;
  font-size:10px;letter-spacing:2px;color:var(--red);text-transform:uppercase;
  border-right:1px solid rgba(255,77,109,.25);height:100%;
  display:flex;align-items:center;background:rgba(255,77,109,.12);
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
  background:var(--panel);text-align:center;transition:border-color .2s;
}
.index-tile:hover{border-color:rgba(77,143,255,.3)}
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
.news-layout{display:grid;grid-template-columns:1fr 320px;gap:16px;align-items:start}
.feature-story{
  padding:20px 22px;border-radius:16px;
  border:1px solid rgba(77,143,255,.2);
  background:radial-gradient(circle at top right,rgba(37,99,235,.15) 0%,transparent 50%),
    linear-gradient(180deg,rgba(16,32,64,.98),rgba(10,22,48,.99));
  box-shadow:var(--shadow);
}
.story-tag{
  display:inline-block;padding:3px 10px;border-radius:6px;margin-bottom:10px;
  font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;
  text-transform:uppercase;font-weight:700;
}
.story-tag.MACRO{background:rgba(77,143,255,.15);color:var(--blue);border:1px solid rgba(77,143,255,.3)}
.story-tag.MARKET{background:rgba(0,229,160,.12);color:var(--green);border:1px solid rgba(0,229,160,.25)}
.story-tag.ENERGY{background:rgba(240,180,41,.12);color:var(--gold);border:1px solid rgba(240,180,41,.25)}
.story-tag.GEOPOLITICAL{background:rgba(255,77,109,.12);color:var(--red);border:1px solid rgba(255,77,109,.3)}
.story-tag.CALENDAR{background:rgba(255,201,60,.1);color:var(--yellow);border:1px solid rgba(255,201,60,.25)}
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
  box-shadow:var(--shadow2);
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
  background:rgba(77,143,255,.1);border:1px solid rgba(77,143,255,.2);
  font-family:'Rajdhani',sans-serif;font-size:14px;font-weight:700;color:var(--blue);
}

/* ── ASSISTANT (JARVIS redesign) ── */
.donna-header{
  text-align:center;padding:24px 20px 16px;
  border-bottom:1px solid var(--line2);margin-bottom:0;
}
@keyframes donnaGlow{
  0%,100%{text-shadow:0 0 20px rgba(0,229,160,.4),0 0 40px rgba(0,229,160,.15)}
  50%{text-shadow:0 0 30px rgba(0,229,160,.7),0 0 60px rgba(0,229,160,.25)}
}
.donna-logo{
  font-family:'Rajdhani',sans-serif;font-size:52px;font-weight:700;letter-spacing:12px;
  background:linear-gradient(135deg,var(--green) 0%,var(--blue) 60%,#fff 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  animation:donnaGlow 3s ease-in-out infinite;line-height:1;
}
.donna-online-row{
  display:flex;align-items:center;justify-content:center;gap:8px;margin-top:8px;
}
.donna-online-dot{
  width:7px;height:7px;border-radius:50%;background:var(--green);
  box-shadow:0 0 8px rgba(0,229,160,.9);animation:pulse 2s ease-in-out infinite;
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
  border-radius:14px;
  background:rgba(0,5,12,.55);
  border:1px solid rgba(0,229,160,.18);
  box-shadow:0 0 30px rgba(0,229,160,.05),inset 0 0 40px rgba(0,0,0,.3);
  padding:16px;margin-bottom:12px;
}
.chat-terminal::-webkit-scrollbar{width:4px}
.chat-terminal::-webkit-scrollbar-track{background:transparent}
.chat-terminal::-webkit-scrollbar-thumb{background:rgba(0,229,160,.25);border-radius:2px}
.msg{margin-bottom:12px;max-width:82%;line-height:1.55;font-size:13px;clear:both}
.msg.user{
  float:right;text-align:right;
  padding:10px 14px;border-radius:14px 14px 4px 14px;
  background:rgba(77,143,255,.16);border:1px solid rgba(77,143,255,.3);
  color:var(--text);
}
.msg.assistant{
  float:left;
  padding:10px 14px 10px 16px;border-radius:14px 14px 14px 4px;
  background:rgba(0,229,160,.06);
  border:1px solid rgba(0,229,160,.15);
  border-left:3px solid var(--green);
}
.msg-clearfix{clear:both;display:table;width:100%}
.msg .role{
  display:block;font-family:'Space Mono',monospace;font-size:9px;
  letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:5px;
}
.msg.user .role{color:rgba(77,143,255,.7)}
.msg.assistant .role{color:var(--green);opacity:.8}
.msg-tag{
  display:inline-block;margin-top:6px;padding:2px 8px;border-radius:5px;
  font-family:'Space Mono',monospace;font-size:8px;letter-spacing:1.5px;
  text-transform:uppercase;
}
.msg-tag.ANALYSIS{background:rgba(77,143,255,.15);color:var(--blue);border:1px solid rgba(77,143,255,.25)}
.msg-tag.EXECUTION{background:rgba(0,229,160,.12);color:var(--green);border:1px solid rgba(0,229,160,.22)}
.msg-tag.RISK{background:rgba(255,77,109,.12);color:var(--red);border:1px solid rgba(255,77,109,.22)}
.msg-tag.CALENDAR{background:rgba(255,201,60,.1);color:var(--yellow);border:1px solid rgba(255,201,60,.22)}
.typing-indicator{
  float:left;clear:both;padding:10px 16px;border-radius:14px 14px 14px 4px;
  background:rgba(0,229,160,.06);border:1px solid rgba(0,229,160,.15);border-left:3px solid var(--green);
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
  padding:8px 14px;border-radius:10px;cursor:pointer;
  border:1px solid rgba(0,229,160,.2);background:rgba(0,229,160,.06);
  color:var(--green);font-family:'Space Mono',monospace;font-size:10px;
  letter-spacing:.5px;transition:all .2s;
}
.quick-cmd-btn:hover{background:rgba(0,229,160,.12);border-color:rgba(0,229,160,.4);
  box-shadow:0 0 12px rgba(0,229,160,.15)}
.chat-input-row{display:flex;gap:10px}
.chat-input{
  flex:1;padding:12px 16px;border-radius:12px;
  border:1px solid rgba(0,229,160,.2);background:rgba(0,0,0,.3);
  color:var(--text);font-family:'Inter',sans-serif;font-size:13px;
  outline:none;transition:border-color .2s,box-shadow .2s;
}
.chat-input:focus{
  border-color:rgba(0,229,160,.5);
  box-shadow:0 0 16px rgba(0,229,160,.12);
}
.send-btn{
  padding:12px 22px;border-radius:12px;border:none;cursor:pointer;
  background:linear-gradient(135deg,#00e5a0,#00c87a);
  color:#060d1a;font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;
  letter-spacing:1px;transition:all .2s;white-space:nowrap;
}
.send-btn:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(0,229,160,.35)}
.send-btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.asst-state-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.state-card{
  padding:10px 14px;border-radius:12px;
  background:rgba(255,255,255,.03);border:1px solid var(--line2);
  margin-bottom:8px;transition:border-color .2s;
}
.state-card:last-child{margin-bottom:0}
.state-card:hover{border-color:rgba(77,143,255,.2)}
.state-card-text{font-size:13px;color:var(--text);line-height:1.4;flex:1}
.state-list-item{
  display:flex;justify-content:space-between;align-items:center;
  padding:9px 0;border-bottom:1px solid var(--line2);font-size:13px;
}
.state-list-item:last-child{border-bottom:none}
.del-btn{
  background:none;border:none;color:var(--muted2);cursor:pointer;
  font-size:15px;padding:2px 6px;border-radius:6px;transition:all .15s;
}
.del-btn:hover{background:var(--red2);color:var(--red)}
.add-row{display:flex;gap:8px;margin-top:10px}
.add-input{
  flex:1;padding:9px 12px;border-radius:10px;
  border:1px solid var(--line);background:rgba(255,255,255,.04);
  color:var(--text);font-size:13px;outline:none;
}
.add-input:focus{border-color:rgba(77,143,255,.35)}
.add-btn{
  padding:9px 14px;border-radius:10px;border:1px solid rgba(77,143,255,.3);
  background:rgba(77,143,255,.1);color:var(--blue);
  cursor:pointer;font-size:13px;font-weight:600;transition:all .2s;
}
.add-btn:hover{background:rgba(77,143,255,.18)}

/* ── ALERT ITEMS ── */
.alert-item{
  padding:12px 14px;border-radius:12px;margin-bottom:10px;
  border:1px solid var(--line);background:rgba(255,255,255,.03);
}
.alert-item:last-child{margin-bottom:0}
.alert-header{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}
.alert-ticker{font-family:'Rajdhani',sans-serif;font-size:18px;font-weight:700;letter-spacing:1px}
.alert-signal{
  font-family:'Space Mono',monospace;font-size:10px;padding:3px 8px;border-radius:6px;
  background:rgba(77,143,255,.12);border:1px solid rgba(77,143,255,.22);color:var(--blue);
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
  background:linear-gradient(180deg,rgba(16,32,64,.98),rgba(10,22,48,.99));
  position:relative;overflow:hidden;
  transition:border-color .2s,box-shadow .2s;
}
.scenario-card:hover{border-color:rgba(77,143,255,.25);box-shadow:0 8px 28px rgba(0,0,0,.3)}
.scenario-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:16px 16px 0 0;
}
.scenario-card.conf-HIGH::before{background:linear-gradient(90deg,var(--green),rgba(0,229,160,.4))}
.scenario-card.conf-MEDIUM::before{background:linear-gradient(90deg,var(--yellow),rgba(255,201,60,.4))}
.scenario-card.conf-LOW::before{background:linear-gradient(90deg,var(--muted2),rgba(74,106,154,.4))}
.sc-trigger{
  font-family:'Rajdhani',sans-serif;font-size:17px;font-weight:700;
  color:var(--yellow);line-height:1.3;margin-bottom:10px;
}
.sc-reaction{font-size:13px;color:var(--text);line-height:1.6;margin-bottom:10px}
.sc-levels{
  font-family:'Space Mono',monospace;font-size:11px;
  color:var(--blue);letter-spacing:.5px;margin-bottom:10px;
  padding:8px 10px;border-radius:8px;background:rgba(77,143,255,.06);
  border:1px solid rgba(77,143,255,.12);
}
.sc-watch{font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:12px}
.sc-conf{
  display:inline-flex;align-items:center;gap:6px;
  font-family:'Space Mono',monospace;font-size:10px;font-weight:700;
  letter-spacing:1px;padding:4px 10px;border-radius:6px;
}
.sc-conf.HIGH{background:rgba(0,229,160,.1);color:var(--green);border:1px solid rgba(0,229,160,.25)}
.sc-conf.MEDIUM{background:rgba(255,201,60,.1);color:var(--yellow);border:1px solid rgba(255,201,60,.25)}
.sc-conf.LOW{background:rgba(255,255,255,.04);color:var(--muted);border:1px solid var(--line)}
.sc-conf-dot{width:6px;height:6px;border-radius:50%;background:currentColor}
.scenario-header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px}
.scenario-meta{font-family:'Space Mono',monospace;font-size:9px;color:var(--muted2);letter-spacing:1px}
.gen-btn{
  padding:8px 16px;border-radius:10px;border:1px solid rgba(77,143,255,.3);
  background:rgba(77,143,255,.08);color:var(--blue);
  cursor:pointer;font-family:'Rajdhani',sans-serif;font-size:13px;font-weight:700;
  letter-spacing:1px;transition:all .2s;white-space:nowrap;
}
.gen-btn:hover{background:rgba(77,143,255,.16);border-color:rgba(77,143,255,.5)}
.gen-btn:disabled{opacity:.5;cursor:not-allowed}
@keyframes spin{to{transform:rotate(360deg)}}
.gen-btn.loading::after{content:' ⟳';display:inline-block;animation:spin .7s linear infinite}
@media(max-width:900px){.scenario-grid{grid-template-columns:1fr}}

/* ── JOURNAL TAB ── */
.journal-btn {
  background:linear-gradient(135deg,rgba(240,180,41,.10),rgba(240,180,41,.04)) !important;
  border-color:rgba(240,180,41,.25) !important;
  color:var(--gold) !important;
}
.journal-btn.active {
  background:linear-gradient(135deg,#92400e,#78350f) !important;
  border-color:transparent !important;color:#fff !important;
  box-shadow:0 4px 20px rgba(240,180,41,.3) !important;
}
.journal-stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.journal-stat{text-align:center;padding:18px 14px}
.journal-stat .js-lab{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:10px}
.journal-stat .js-val{font-family:'Rajdhani',sans-serif;font-size:28px;font-weight:700;letter-spacing:1px;line-height:1}
.journal-stat .js-sub{margin-top:6px;font-size:11px;color:var(--muted2)}
.trade-label{font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px;display:block}
.trade-input,.trade-select{
  width:100%;padding:10px 12px;border-radius:10px;
  border:1px solid var(--line);background:rgba(255,255,255,.04);
  color:var(--text);font-family:'Inter',sans-serif;font-size:13px;
  outline:none;transition:border-color .2s;
}
.trade-input:focus,.trade-select:focus{border-color:rgba(77,143,255,.4)}
.trade-select option{background:#0e1c35;color:var(--text)}
.submit-trade-btn{
  width:100%;padding:13px;border-radius:12px;border:none;cursor:pointer;
  background:linear-gradient(135deg,var(--gold),#d97706);
  color:#000;font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;
  letter-spacing:1px;transition:all .2s;margin-top:4px;
}
.submit-trade-btn:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(240,180,41,.4)}
.submit-trade-btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.outcome-WIN{color:var(--green)}.outcome-LOSS{color:var(--red)}.outcome-BREAKEVEN{color:var(--yellow)}
.j-date-header{background:rgba(240,180,41,.06);border-bottom:1px solid rgba(240,180,41,.12)}
.j-date-header td{padding:7px 14px;font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1.5px;color:var(--gold);text-transform:uppercase;font-weight:700}
.j-filter-bar{display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.j-filter-btn{padding:5px 14px;border-radius:8px;border:1px solid var(--line);background:rgba(255,255,255,.03);color:var(--muted2);font-family:\'Space Mono\',monospace;font-size:9px;letter-spacing:1px;cursor:pointer;transition:all .15s;text-transform:uppercase}
.j-filter-btn:hover{border-color:rgba(240,180,41,.4);color:var(--gold)}
.j-filter-btn.active{background:rgba(240,180,41,.12);border-color:rgba(240,180,41,.4);color:var(--gold)}
.regime-breakdown-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-top:12px}
.regime-card{padding:14px 16px;border-radius:12px;border:1px solid var(--line);background:rgba(255,255,255,.03)}
.regime-card .rc-name{font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;margin-bottom:8px}
.regime-card .rc-wr{font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;line-height:1}
.regime-card .rc-sub{font-size:11px;color:var(--muted2);margin-top:4px}
@media(max-width:900px){.journal-stats-grid{grid-template-columns:1fr 1fr}}
@media(max-width:540px){.journal-stats-grid{grid-template-columns:1fr}}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(77,143,255,.2);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:rgba(77,143,255,.35)}

/* ── RESPONSIVE ── */
@media(max-width:1200px){
  .hero-grid,.main-grid,.stat-grid{grid-template-columns:1fr 1fr}
  .stat-grid{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:760px){
  body{padding:12px}
  .brand h1{font-size:32px}
  .hero-title{font-size:26px}
  .hero-grid,.main-grid,.stat-grid,.asst-state-grid,.live-strip-row{grid-template-columns:1fr}
}

/* ═══════════════════════════════════════
   H.A.R.V.E.Y EXECUTION TAB
   ═══════════════════════════════════════ */

.harvey-btn {
  background: linear-gradient(135deg, rgba(0,229,160,.15), rgba(0,229,160,.05)) !important;
  border-color: rgba(0,229,160,.3) !important;
  color: var(--green) !important;
}
.harvey-btn.active {
  background: linear-gradient(135deg, #047857, #065f46) !important;
  border-color: transparent !important;
  color: #fff !important;
  box-shadow: 0 4px 20px rgba(0,229,160,.35) !important;
}

.verdict-banner {
  border-radius: 18px;
  padding: 28px 30px;
  border: 1px solid var(--line);
  position: relative;
  overflow: hidden;
}
.verdict-banner::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  opacity: .06;
  border-radius: 18px;
}
.verdict-banner.green { border-color: rgba(0,229,160,.35); background: linear-gradient(135deg, rgba(4,120,87,.15), rgba(10,22,48,.99)); }
.verdict-banner.green::before { background: var(--green) }
.verdict-banner.red { border-color: rgba(255,77,109,.35); background: linear-gradient(135deg, rgba(153,27,27,.15), rgba(10,22,48,.99)); }
.verdict-banner.red::before { background: var(--red) }
.verdict-banner.yellow { border-color: rgba(255,201,60,.3); background: linear-gradient(135deg, rgba(180,83,9,.12), rgba(10,22,48,.99)); }
.verdict-banner.yellow::before { background: var(--yellow) }

.verdict-label { font-family: 'Space Mono', monospace; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 12px; color: var(--muted2); }
.verdict-word { font-family: 'Rajdhani', sans-serif; font-size: 72px; font-weight: 700; line-height: 1; letter-spacing: 2px; }
.verdict-banner.green .verdict-word { color: var(--green) }
.verdict-banner.red   .verdict-word { color: var(--red) }
.verdict-banner.yellow .verdict-word { color: var(--yellow) }
.verdict-reason { margin-top: 14px; font-size: 14px; line-height: 1.65; color: var(--muted); max-width: 80ch; }
.verdict-grid { display: grid; grid-template-columns: 1.3fr .7fr; gap: 18px; align-items: start; }

.bias-wrap { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.bias-gauge { width: 100%; height: 14px; background: rgba(255,255,255,.06); border-radius: 999px; overflow: hidden; border: 1px solid var(--line); }
.bias-fill { height: 100%; border-radius: 999px; transition: width .6s ease, background .6s ease; }
.bias-score-big { font-family: 'Rajdhani', sans-serif; font-size: 52px; font-weight: 700; line-height: 1; }
.bias-direction { font-family: 'Space Mono', monospace; font-size: 13px; font-weight: 700; letter-spacing: 2px; }

.orb-card { border-radius: var(--radius); padding: 20px 22px; border: 1px solid var(--line); background: linear-gradient(180deg, rgba(16,32,64,.98), rgba(10,22,48,.99)); }
.orb-status-pill { display: inline-block; padding: 5px 14px; border-radius: 999px; font-family: 'Space Mono', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 12px; }
.orb-FORMING    { background: rgba(255,201,60,.12); border: 1px solid rgba(255,201,60,.3); color: var(--yellow) }
.orb-SET        { background: rgba(77,143,255,.12);  border: 1px solid rgba(77,143,255,.3);  color: var(--blue) }
.orb-ACTIVE     { background: rgba(0,229,160,.12);   border: 1px solid rgba(0,229,160,.3);   color: var(--green) }
.orb-WATCH      { background: rgba(77,143,255,.12);  border: 1px solid rgba(77,143,255,.3);  color: var(--blue) }
.orb-WAIT       { background: rgba(255,255,255,.06); border: 1px solid var(--line);          color: var(--muted) }
.orb-PENDING    { background: rgba(255,255,255,.04); border: 1px solid var(--line2);         color: var(--muted2) }
.orb-PRE-MARKET { background: rgba(255,255,255,.04); border: 1px solid var(--line2);         color: var(--muted2) }
.orb-RANGING    { background: rgba(255,201,60,.08);  border: 1px solid rgba(255,201,60,.2);  color: var(--yellow) }

.orb-status-label { font-family: 'Rajdhani', sans-serif; font-size: 26px; font-weight: 700; margin-bottom: 8px; }
.orb-note { font-size: 13px; color: var(--muted); line-height: 1.6; }

.fib-table { width: 100%; border-collapse: collapse }
.fib-table td { padding: 7px 0; border-bottom: 1px solid var(--line2); font-size: 13px; font-weight: 600; }
.fib-table tr:last-child td { border-bottom: none }
.fib-label { font-family: 'Space Mono', monospace; font-size: 10px; color: var(--muted2); letter-spacing: 1px; }
.fib-price { text-align: right; color: var(--text) }
.fib-high  { color: var(--green) }
.fib-low   { color: var(--red) }
.fib-rs    { text-align: right; width: 28px; }
.fib-tag-r { font-family:'Space Mono',monospace; font-size:9px; font-weight:700; color:var(--red);
             background:rgba(255,77,109,.10); border:1px solid rgba(255,77,109,.25);
             padding:1px 5px; border-radius:3px; letter-spacing:.5px; }
.fib-tag-s { font-family:'Space Mono',monospace; font-size:9px; font-weight:700; color:var(--green);
             background:rgba(0,229,160,.08); border:1px solid rgba(0,229,160,.20);
             padding:1px 5px; border-radius:3px; letter-spacing:.5px; }
.fib-pivot-row td { font-weight:900 !important; }
.fib-pivot-row .fib-label { color:var(--gold) !important; }
.fib-pivot-row .fib-price { color:var(--gold) !important; }
.fib-pivot-row { background:rgba(240,180,41,.05); }
.fib-cur-row td { padding:2px 0; border-bottom:1px solid var(--line2); }
.fib-cur-line { display:flex; align-items:center; gap:5px; }
.fib-cur-line::before,.fib-cur-line::after { content:''; flex:1; height:1px; background:var(--blue); opacity:.5; }
.fib-cur-tag { font-family:'Space Mono',monospace; font-size:9px; font-weight:700;
               color:var(--blue); white-space:nowrap; }

.signal-card { padding: 13px 16px; border-radius: 12px; border: 1px solid var(--line2); background: rgba(255,255,255,.03); margin-bottom: 8px; transition: background .15s; }
.signal-card:last-child { margin-bottom: 0 }
.signal-card:hover { background: rgba(255,255,255,.05) }
.signal-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }
.signal-ticker { font-family: 'Rajdhani', sans-serif; font-size: 20px; font-weight: 700; letter-spacing: 1px; }
.signal-verdict { font-family: 'Space Mono', monospace; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 6px; letter-spacing: 1px; }
.sv-TAKE    { background: rgba(0,229,160,.15); color: var(--green); border: 1px solid rgba(0,229,160,.3) }
.sv-CAUTION { background: rgba(255,201,60,.12); color: var(--yellow); border: 1px solid rgba(255,201,60,.25) }
.sv-SKIP    { background: rgba(255,77,109,.12); color: var(--red); border: 1px solid rgba(255,77,109,.25) }
.signal-meta { font-size: 11px; color: var(--muted2); margin-bottom: 4px }
.signal-summary { font-size: 12px; color: var(--muted); line-height: 1.5 }

.divergence-alert { padding: 12px 16px; border-radius: 12px; background: rgba(255,201,60,.07); border: 1px solid rgba(255,201,60,.2); display: flex; align-items: flex-start; gap: 12px; }
.divergence-icon { font-size: 18px; flex-shrink: 0; margin-top: 2px; }
.divergence-text { font-size: 13px; color: var(--yellow); line-height: 1.5; }

.harvey-top-grid { display: grid; grid-template-columns: 1.3fr .7fr; gap: 16px; align-items: start; }
.harvey-mid-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; align-items: start; }
.harvey-bot-grid { display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; align-items: start; }

/* ── RISK ENGINE PANEL ── */
.re-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.re-cell {
  padding: 14px 16px; border-radius: 14px;
  border: 1px solid var(--line); background: var(--panel);
}
.re-cell.stop {
  border-color: rgba(255,77,109,.5);
  background: rgba(255,77,109,.08);
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
  background: rgba(255,77,109,.12); border: 2px solid rgba(255,77,109,.5);
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
  border: 1px solid var(--line); background: rgba(255,255,255,.04);
  color: var(--text); font-family: 'Space Mono', monospace; font-size: 11px;
  outline: none; transition: border-color .2s;
}
.re-input:focus { border-color: rgba(0,229,160,.4) }
.re-calc-btn {
  padding: 8px 16px; border-radius: 10px; border: 1px solid rgba(0,229,160,.3);
  background: rgba(0,229,160,.08); color: var(--green);
  font-family: 'Rajdhani', sans-serif; font-size: 14px; font-weight: 700;
  cursor: pointer; transition: all .2s; white-space: nowrap;
}
.re-calc-btn:hover { background: rgba(0,229,160,.15); border-color: rgba(0,229,160,.5) }
.re-reset-btn {
  padding: 8px 16px; border-radius: 10px; border: 1px solid rgba(255,77,109,.3);
  background: rgba(255,77,109,.08); color: var(--red);
  font-family: 'Rajdhani', sans-serif; font-size: 13px; font-weight: 700;
  cursor: pointer; transition: all .2s;
}
.re-reset-btn:hover { background: rgba(255,77,109,.18) }
@media(max-width:1100px) {
  .re-grid { grid-template-columns: 1fr 1fr }
}

@media(max-width:1100px) {
  .harvey-top-grid, .harvey-mid-grid, .harvey-bot-grid, .verdict-grid { grid-template-columns: 1fr }
}

/* ── RISK BAR PULSE ── */
@keyframes strip-pulse-red {
  0%,100% { box-shadow:0 0 0 0 rgba(255,77,109,0);border-color:rgba(255,77,109,.2) }
  50%      { box-shadow:0 0 14px 3px rgba(255,77,109,.35);border-color:rgba(255,77,109,.55) }
}
@keyframes strip-pulse-yellow {
  0%,100% { box-shadow:0 0 0 0 rgba(255,201,60,0);border-color:rgba(255,201,60,.15) }
  50%      { box-shadow:0 0 10px 2px rgba(255,201,60,.25);border-color:rgba(255,201,60,.45) }
}
.ticker-wrap.risk-high   { animation:strip-pulse-red    2s ease-in-out infinite }
.ticker-wrap.risk-medium { animation:strip-pulse-yellow 2.5s ease-in-out infinite }

/* ── SESSION PLAYBOOK CARD ── */
.playbook-grid {
  display:grid;grid-template-columns:repeat(4,1fr);gap:16px;align-items:start;
}
.playbook-cell { }
.playbook-cell .pb-val {
  font-family:'Rajdhani',sans-serif;font-size:16px;font-weight:700;letter-spacing:.3px;
  line-height:1.2;margin-top:4px;
}
.playbook-cell .pb-note {
  font-size:12px;color:var(--muted);line-height:1.6;margin-top:4px;
}
@media(max-width:900px){ .playbook-grid{grid-template-columns:1fr 1fr} }
@media(max-width:540px){ .playbook-grid{grid-template-columns:1fr} }

/* ── SSE signal dot on nav button ── */
.harvey-btn { position: relative }
.signal-dot {
  position: absolute;
  top: 6px; right: 6px;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--green);
  display: none;
  box-shadow: 0 0 6px var(--green);
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
  0%   { box-shadow: 0 0 0 0 rgba(0,229,160,.6) }
  50%  { box-shadow: 0 0 0 18px rgba(0,229,160,0) }
  100% { box-shadow: 0 0 0 0 rgba(0,229,160,0) }
}
.verdict-banner.flash { animation: banner-flash .7s ease-out }
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
        <button class="tab-btn playbook-btn" data-page="playbook">Playbook</button>
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
    <div class="vstack">

      <!-- HERO (compact) -->
      <div class="hero-banner">
        <div class="hero-eyebrow">Command Overview</div>
        <div class="hero-grid">
          <div>
            <div class="hero-title" id="heroTitle">Loading market intelligence...</div>
            <div class="hero-sub" id="heroSub">Connecting to live data feeds.</div>
            <div style="margin-top:8px;font-size:11px;color:var(--muted2)" id="donnaTime">—</div>
          </div>
          <div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:10px">
              <div class="chip">
                <span class="chip-label">Driver</span>
                <span class="chip-value" id="driverDominant">—</span>
              </div>
              <div class="chip">
                <span class="chip-label">Bias</span>
                <span class="chip-value" id="morningBias">—</span>
              </div>
              <div class="chip" id="regimeChipWrap" style="border-color:rgba(255,255,255,.08)">
                <span class="chip-label">Regime</span>
                <span class="chip-value" id="regimeChipLabel">—</span>
              </div>
              <div class="chip">
                <span class="chip-label">Session</span>
                <span class="chip-value" id="sessionSig" style="font-size:13px">—</span>
              </div>
            </div>
            <div class="hero-warn-list" id="warningsList"></div>
            <div style="margin-top:8px;font-size:11px;color:var(--muted);line-height:1.5" id="morningRead">—</div>
          </div>
        </div>
      </div>

      <!-- SESSION PLAYBOOK BAR -->
      <div class="playbook-bar">
        <span class="pb-bar-label">Session</span><span class="pb-bar-val" id="playbookSession">—</span>
        <span class="pb-bar-sep">·</span>
        <span class="pb-bar-label">Driver</span><span class="pb-bar-val" id="playbookDriver">—</span>
        <span class="pb-bar-sep">·</span>
        <span class="pb-bar-label">Events</span><span class="pb-bar-val" id="playbookEvents">—</span>
        <span class="pb-bar-sep">·</span>
        <span class="pb-bar-note" id="playbookTactical">—</span>
      </div>

      <!-- RISK STRIP -->
      <div class="stat-grid">
        <div class="card stat-card">
          <div class="s-lab">Macro Risk</div>
          <div class="s-val" id="macroRisk">—</div>
          <div class="s-sub">Event timing &amp; macro pressure</div>
        </div>
        <div class="card stat-card">
          <div class="s-lab">Headline Risk</div>
          <div class="s-val" id="headlineRisk">—</div>
          <div class="s-sub">Breaking-news sensitivity</div>
        </div>
        <div class="card stat-card">
          <div class="s-lab">Market Risk</div>
          <div class="s-val" id="marketRisk">—</div>
          <div class="s-sub">Company &amp; sector catalyst pressure</div>
        </div>
        <div class="card stat-card">
          <div class="s-lab">NQ Session</div>
          <div class="s-val" id="sessionSigBig" style="font-size:18px;line-height:1.2">—</div>
          <div class="s-sub" id="sessionSigSub">—</div>
        </div>
      </div>

      <!-- MAIN GRID -->
      <div class="main-grid">

        <!-- LEFT -->
        <div class="left-stack">

          <!-- MARKET DRIVER ENGINE (compressed) -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:8px">Market Driver Engine</div>
            <div class="kv-row" style="padding:7px 0">
              <span class="kv-k">Regime</span>
              <span class="kv-v" id="driverRegime">—</span>
            </div>
            <div class="kv-row" style="padding:7px 0">
              <span class="kv-k">Driver</span>
              <span class="kv-v" id="driverDominant2">—</span>
            </div>
            <div style="margin-top:10px;font-size:12px;color:var(--muted);line-height:1.55" id="driverSummary">—</div>
          </div>

          <!-- CROSS-ASSET INTELLIGENCE -->
          <div class="panel" id="crossAssetPanel">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
              <div class="kicker" style="margin-bottom:0">Cross-Asset Intelligence</div>
              <span class="ca-mode-badge" id="caModeBadge">—</span>
            </div>
            <div id="caDivergenceList">
              <div class="ca-clean">Assets are aligned — tape is clean</div>
            </div>
          </div>

          <!-- MAJOR INDEXES -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">Market Board</div>
            <table>
              <thead><tr><th>Index</th><th>Last</th><th>Chg</th><th>% Chg</th></tr></thead>
              <tbody id="majorIndexesTable"></tbody>
            </table>
          </div>

          <!-- MARKET MOVERS (Live) -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">Live Movers</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
              <div>
                <div class="kicker" style="margin-bottom:6px;color:var(--green)">Gainers</div>
                <table>
                  <thead><tr><th>Sym</th><th>Last</th><th>%Chg</th></tr></thead>
                  <tbody id="gainersTable"></tbody>
                </table>
              </div>
              <div>
                <div class="kicker" style="margin-bottom:6px;color:var(--red)">Losers</div>
                <table>
                  <thead><tr><th>Sym</th><th>Last</th><th>%Chg</th></tr></thead>
                  <tbody id="losersTable"></tbody>
                </table>
              </div>
            </div>
          </div>

        </div>

        <!-- RIGHT -->
        <div class="right-stack">

          <!-- DONNA OBSERVATIONS -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:10px">Live Observations</div>
            <div id="observationsList"></div>
          </div>

          <!-- TOP STORY -->
          <div class="panel">
            <div class="kicker" style="margin-bottom:8px">Primary Catalyst</div>
            <div style="font-size:20px;font-weight:700;font-family:Rajdhani,sans-serif;line-height:1.15;margin-bottom:8px" id="topStory">—</div>
            <div style="font-size:12px;color:var(--muted);line-height:1.55" id="topStoryNote">—</div>
          </div>

        </div>

      </div>
    </div>
  </div>

  <!-- ════════════════════ NEWS ════════════════════ -->
  <div class="page" id="page-news">
    <div class="vstack">

      <!-- BREAKING NEWS BAR -->
      <div class="breaking-bar">
        <div class="breaking-label">Breaking</div>
        <div class="breaking-ticker-wrap">
          <div class="breaking-ticker-track" id="breakingTickerTrack">
            <span class="breaking-item">Loading live headlines...</span>
          </div>
        </div>
      </div>

      <!-- 5 INDEX TILES -->
      <div class="index-tiles" id="indexTiles">
        <div class="index-tile"><div class="index-tile-name">NASDAQ</div><div class="index-tile-val" id="tileNASDAQ">—</div><div class="index-tile-chg" id="tileNASDAQchg">—</div></div>
        <div class="index-tile"><div class="index-tile-name">S&amp;P 500</div><div class="index-tile-val" id="tileSPX">—</div><div class="index-tile-chg" id="tileSPXchg">—</div></div>
        <div class="index-tile"><div class="index-tile-name">DJIA</div><div class="index-tile-val" id="tileDJIA">—</div><div class="index-tile-chg" id="tileDJIAchg">—</div></div>
        <div class="index-tile"><div class="index-tile-name">DXY</div><div class="index-tile-val" id="tileDXY">—</div><div class="index-tile-chg" id="tileDXYchg">—</div></div>
        <div class="index-tile"><div class="index-tile-name">VIX</div><div class="index-tile-val" id="tileVIX">—</div><div class="index-tile-chg" id="tileVIXchg">—</div></div>
      </div>

      <!-- MAIN CONTENT + SIDEBAR -->
      <div class="news-layout">

        <!-- LEFT: FEATURE STORY + NEWS FEED -->
        <div class="vstack" style="gap:14px">

          <!-- FEATURE STORY -->
          <div class="feature-story">
            <div id="featureStoryTag" class="story-tag MACRO">MACRO</div>
            <div class="feature-headline" id="featureHeadline">Loading top story...</div>
            <div class="feature-note" id="featureNote">—</div>
          </div>

          <!-- NUMBERED NEWS FEED -->
          <div class="panel">
            <div class="kicker">Live Feed</div>
            <div class="section-title" style="margin-bottom:14px">Market Intelligence</div>
            <div id="newsList"></div>
          </div>

        </div>

        <!-- RIGHT SIDEBAR -->
        <div class="news-sidebar-panel">

          <div class="sidebar-section">
            <div class="sidebar-kicker">DONNA&#39;s Read</div>
            <div class="donna-read" id="donnaRead">—</div>
          </div>

          <div class="sidebar-section">
            <div class="sidebar-kicker">Risk Levels</div>
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
          </div>

          <div class="sidebar-section">
            <div class="sidebar-kicker">Event Phase</div>
            <div id="sidebarEventPhase" style="font-family:'Rajdhani',sans-serif;font-size:20px;font-weight:700;color:var(--yellow)">—</div>
            <div id="sidebarNextEvent" style="font-size:12px;color:var(--muted);margin-top:4px">—</div>
          </div>

          <div class="sidebar-section">
            <div class="sidebar-kicker">Names to Watch</div>
            <div id="sidebarWatchNames">—</div>
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

      <!-- TASKS + REMINDERS -->
      <div class="asst-state-grid">

        <!-- FOCUS + TASKS -->
        <div class="panel">
          <div class="kicker">Daily Agenda</div>
          <div class="section-title" style="margin-bottom:8px">Focus &amp; Tasks</div>
          <div style="padding:10px 14px;border-radius:10px;background:rgba(0,229,160,.06);border:1px solid rgba(0,229,160,.15);font-size:13px;color:var(--text);margin-bottom:14px;line-height:1.5" id="dailyFocus">—</div>
          <div id="tasksList"></div>
          <div class="add-row">
            <input class="add-input" id="taskInput" type="text" placeholder="Add a task..." />
            <button class="add-btn" id="addTaskBtn">+ Add</button>
          </div>
        </div>

        <!-- REMINDERS -->
        <div class="panel">
          <div class="kicker">Reminders</div>
          <div class="section-title" style="margin-bottom:14px">Active Reminders</div>
          <div id="remindersList"></div>
          <div class="add-row">
            <input class="add-input" id="reminderInput" type="text" placeholder="Add a reminder..." />
            <button class="add-btn" id="addReminderBtn">+ Add</button>
          </div>
        </div>

      </div>

    </div>
  </div>

  <!-- ════════════════════ H.A.R.V.E.Y ════════════════════ -->
  <div class="page" id="page-harvey">
    <div class="vstack">

      <!-- VERDICT BANNER -->
      <div class="verdict-banner yellow" id="harveyVerdict">
        <div class="verdict-grid">
          <div>
            <div class="verdict-label">H.A.R.V.E.Y // Execution Verdict</div>
            <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:4px">
              <div class="verdict-word" id="harveyVerdictWord">—</div>
              <div id="harveyRegimeRow" style="display:flex;gap:8px;align-items:center;padding:4px 12px;border-radius:8px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08)">
                <span style="font-family:Space Mono,monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase">Regime</span>
                <span id="harveyRegimeLabel" style="font-family:Rajdhani,sans-serif;font-size:15px;font-weight:700">—</span>
                <span style="color:var(--muted2);font-size:11px">·</span>
                <span style="font-family:Space Mono,monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase">Mode</span>
                <span id="harveyHarveyMode" style="font-family:Rajdhani,sans-serif;font-size:15px;font-weight:700">—</span>
              </div>
            </div>
            <div class="verdict-reason" id="harveyVerdictReason">Loading execution intelligence...</div>
          </div>
          <div class="bias-wrap" style="padding:10px 0">
            <div class="bias-score-big" id="harveyBiasScore">—</div>
            <div class="bias-direction" id="harveyBiasDir">—</div>
            <div style="width:100%;margin-top:8px">
              <div style="font-family:Space Mono,monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px;text-align:center">Bias Score / 100</div>
              <div class="bias-gauge"><div class="bias-fill" id="harveyBiasFill" style="width:50%"></div></div>
              <div style="display:flex;justify-content:space-between;margin-top:4px">
                <span style="font-family:Space Mono,monospace;font-size:9px;color:var(--red)">SHORT</span>
                <span style="font-family:Space Mono,monospace;font-size:9px;color:var(--muted2)">NEUTRAL</span>
                <span style="font-family:Space Mono,monospace;font-size:9px;color:var(--green)">LONG</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ORB + SESSION ROW -->
      <div class="harvey-top-grid">
        <div class="orb-card">
          <div class="kicker">Opening Range</div>
          <div class="section-title" style="margin-bottom:14px">ORB Manager</div>
          <div class="orb-status-pill orb-PENDING" id="harveyOrbPill">PENDING</div>
          <div class="orb-status-label" id="harveyOrbStatus">—</div>
          <div class="orb-note" id="harveyOrbNote">—</div>
          <div style="margin-top:16px" id="harveyDivergence"></div>
        </div>
        <div class="panel">
          <div class="kicker">Session</div>
          <div class="section-title" style="margin-bottom:14px">Context</div>
          <div class="kv-row"><span class="kv-k">Session</span><span class="kv-v" id="harveySession">—</span></div>
          <div class="kv-row"><span class="kv-k">Day</span><span class="kv-v" id="harveyDay">—</span></div>
          <div class="kv-row"><span class="kv-k">Next Event</span><span class="kv-v" id="harveyNextEvent">—</span></div>
          <div class="kv-row"><span class="kv-k">Event Phase</span><span class="kv-v" id="harveyEventPhase">—</span></div>
          <div class="kv-row"><span class="kv-k">Macro Risk</span><span class="kv-v" id="harveyMacroRisk">—</span></div>
          <div class="kv-row"><span class="kv-k">Session Label</span><span class="kv-v" id="harveySessionLabel">—</span></div>
          <div class="kv-row"><span class="kv-k">NQ Points</span><span class="kv-v up" id="harveyNqPts">—</span></div>
          <div class="kv-row"><span class="kv-k">ES Points</span><span class="kv-v up" id="harveyEsPts">—</span></div>
        </div>
      </div>

      <!-- FIB LEVELS + PULSE -->
      <div class="harvey-mid-grid">
        <div class="panel">
          <div class="kicker" style="color:var(--green)">NQ Futures</div>
          <div class="section-title" style="margin-bottom:4px">Key Levels</div>
          <div style="font-family:Rajdhani,sans-serif;font-size:28px;font-weight:700;margin-bottom:14px" id="harveyNqLast">—</div>
          <table class="fib-table" id="harveyNqFibs"><tr><td colspan="3" class="neutral" style="font-size:12px">Loading...</td></tr></table>
        </div>
        <div class="panel">
          <div class="kicker" style="color:var(--blue)">ES Futures</div>
          <div class="section-title" style="margin-bottom:4px">Key Levels</div>
          <div style="font-family:Rajdhani,sans-serif;font-size:28px;font-weight:700;margin-bottom:14px" id="harveyEsLast">—</div>
          <table class="fib-table" id="harveyEsFibs"><tr><td colspan="3" class="neutral" style="font-size:12px">Loading...</td></tr></table>
        </div>
        <div class="panel">
          <div class="kicker">Execution View</div>
          <div class="section-title" style="margin-bottom:14px">Trade Intel</div>
          <div class="kv-row"><span class="kv-k">Bias</span><span class="kv-v" id="harveyMorningBias">—</span></div>
          <div class="kv-row"><span class="kv-k">Open Quality</span><span class="kv-v" id="harveyOpenQuality">—</span></div>
          <div class="kv-row"><span class="kv-k">Focus</span><span class="kv-v" id="harveyFocus">—</span></div>
          <div class="kv-row"><span class="kv-k">Watch First</span><span class="kv-v" id="harveyWatchFirst">—</span></div>
          <div style="margin-top:14px;padding:12px 14px;border-radius:10px;background:rgba(255,255,255,.03);border:1px solid var(--line2);font-size:13px;color:var(--muted);line-height:1.6" id="harveyFirstRead">—</div>
        </div>
      </div>

      <!-- ── RISK ENGINE PANEL ── -->
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

        <!-- STOP TRADING BANNER -->
        <div class="re-stop-banner" id="reStopBanner">
          ⛔ STOP TRADING — Session risk limit reached. Clear flag to resume.
        </div>

        <!-- 4-CELL GRID -->
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

        <!-- TRADE CALCULATOR INPUTS -->
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

      <!-- SIGNAL HISTORY + WHAT MATTERS -->
      <div class="harvey-bot-grid">
        <div class="panel">
          <div class="kicker">TradingView Feed</div>
          <div class="section-title" style="margin-bottom:14px">Last 10 Signals</div>
          <div id="harveySignals">
            <div class="obs-item low"><div class="obs-body">No signals received yet. Connect your TradingView indicator to the webhook.</div></div>
          </div>
        </div>
        <div class="panel">
          <div class="kicker">Donna Intelligence</div>
          <div class="section-title" style="margin-bottom:14px">What Matters Now</div>
          <div style="font-size:15px;font-weight:600;line-height:1.5;margin-bottom:12px;color:var(--text)" id="harveyWmHeadline">—</div>
          <div style="font-size:13px;color:var(--muted);line-height:1.65;margin-bottom:14px" id="harveyWmSummary">—</div>
          <div class="kv-row"><span class="kv-k">Mode</span><span class="kv-v" id="harveyWmMode">—</span></div>
          <div class="kv-row"><span class="kv-k">Risk to Conviction</span><span class="kv-v" id="harveyWmRtc">—</span></div>
          <div style="margin-top:14px;padding:12px 14px;border-radius:10px;background:rgba(0,229,160,.05);border:1px solid rgba(0,229,160,.12);font-size:13px;color:var(--muted);line-height:1.6" id="harveyWmFocus">—</div>
        </div>
      </div>

    </div>
  </div>

  <!-- ════════════════════ PLAYBOOK ════════════════════ -->
  <div class="page" id="page-playbook">
    <div class="vstack">

      <div class="hero-banner">
        <div class="hero-eyebrow">AI Scenario Engine</div>
        <div class="scenario-header">
          <div>
            <div class="hero-title" style="color:#a78bfa">Today\'s Playbook</div>
            <div class="hero-sub">If/then scenarios generated from live market conditions, active regime, and today\'s macro calendar.</div>
          </div>
          <div style="display:flex;align-items:center;gap:14px;flex-shrink:0">
            <div class="scenario-meta" id="scenarioMeta">—</div>
            <button class="gen-btn" id="scenarioGenBtn">GENERATE</button>
          </div>
        </div>
      </div>

      <div id="scenarioGrid" class="scenario-grid">
        <div class="scenario-card">
          <div class="sc-reaction" style="color:var(--muted2)">Click GENERATE to build today\'s if/then playbook from live market conditions and macro calendar.</div>
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
// ════════ TAB NAVIGATION ════════
document.querySelectorAll('.tab-btn[data-page]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn[data-page]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('page-' + btn.dataset.page).classList.add('active');
    if (btn.dataset.page === 'journal') refreshJournal();
    if (btn.dataset.page === 'harvey') refreshHarvey();
    if (btn.dataset.page === 'playbook') refreshScenarios();
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

// ════════ RENDER DASHBOARD ════════
function renderDashboard(d) {
  const risk = d.risk || {};
  const driver = d.driver || {};
  const morning = d.morning_edge || {};
  const sig = d.session_significance || {};
  const wm = d.what_matters_now || {};
  const obs = d.observations || [];
  const alerts = d.raw_trade_alerts || [];
  const movers = d.market_movers_engine || {};
  const liveMovers = d.live_movers || {};
  const news = d.news || [];

  // Live strip + session
  setText('sessionVal', risk.donna_session || '—');
  updateStrip(d.live_strip || []);

  // Risk bar pulse
  const stripEl = document.querySelector('.ticker-wrap');
  if (stripEl) {
    const macroLevel = (risk.macro_risk || '').toLowerCase();
    stripEl.classList.remove('risk-high', 'risk-medium');
    if (macroLevel === 'high') stripEl.classList.add('risk-high');
    else if (macroLevel === 'medium') stripEl.classList.add('risk-medium');
  }

  // Hero (compact)
  setText('heroTitle', wm.headline || driver.dominant_driver || '—');
  setText('heroSub', wm.summary || driver.market_summary || '—');
  setText('donnaTime', risk.donna_time_ny ? risk.donna_time_ny.substring(0,19).replace('T',' ') + ' ET' : '—');
  setText('driverDominant', driver.dominant_driver || '—');
  setText('morningBias', morning.today_bias || '—');

  // Regime chip (color-coded)
  const regimeData = d.regime || {};
  const rcColorMap = {green:'rgba(0,229,160,.35)',blue:'rgba(77,143,255,.35)',yellow:'rgba(255,201,60,.3)',red:'rgba(255,77,109,.35)',muted:'rgba(255,255,255,.08)'};
  const rcTextMap  = {green:'var(--green)',blue:'var(--blue)',yellow:'var(--yellow)',red:'var(--red)',muted:'var(--muted)'};
  const rcWrap = document.getElementById('regimeChipWrap');
  if (rcWrap) rcWrap.style.borderColor = rcColorMap[regimeData.regime_color] || 'rgba(255,255,255,.08)';
  const rcLabel = document.getElementById('regimeChipLabel');
  if (rcLabel) {
    rcLabel.textContent = regimeData.regime ? `${regimeData.regime}  ·  ${regimeData.harvey_mode}` : '—';
    rcLabel.style.color = rcTextMap[regimeData.regime_color] || 'var(--text)';
  }

  // Session chip (hero 2×2 grid, bottom-right)
  const sessionSigEl = document.getElementById('sessionSig');
  if (sessionSigEl) { sessionSigEl.textContent = sig.label || '—'; }

  // Warnings — compact hw-item list inside hero
  const warnings = risk.active_warnings || [];
  setHtml('warningsList', warnings.slice(0,3).map(w =>
    `<div class="hw-item"><span class="hw-dot"></span>${w}</div>`
  ).join('') || '');
  setText('morningRead', morning.first_read || '—');

  // Risk stat strip
  setHtml('macroRisk', riskBadge(risk.macro_risk));
  setHtml('headlineRisk', riskBadge(risk.headline_risk));
  setHtml('marketRisk', riskBadge(risk.market_news_risk));
  const sessionSigBig = document.getElementById('sessionSigBig');
  if (sessionSigBig) sessionSigBig.textContent = sig.label || '—';
  setText('sessionSigSub', sig.nq_points ? `NQ ${sig.nq_points}pts  ·  ES ${sig.es_points}pts` : '—');

  // Driver engine (compressed — 2 rows + summary)
  setText('driverDominant2', driver.dominant_driver || '—');
  setText('driverRegime', driver.market_regime || '—');
  setText('driverSummary', driver.market_summary || '—');

  // Major indexes
  const idx = d.major_indexes || [];
  setHtml('majorIndexesTable', idx.map(r => `
    <tr>
      <td>${r.symbol}</td>
      <td class="${dirClass(r.pct)}">${r.last}</td>
      <td class="${dirClass(r.pct)}">${r.chg}</td>
      <td class="${dirClass(r.pct)}">${r.pct}</td>
    </tr>`).join('') || '<tr><td colspan="4" class="neutral">No data</td></tr>');

  // Gainers / Losers
  const gainers = (liveMovers.gainers || []).slice(0, 5);
  const losers  = (liveMovers.losers  || []).slice(0, 5);
  setHtml('gainersTable', gainers.map(r => `
    <tr>
      <td class="up">${r.symbol}</td><td>${r.last}</td><td class="up">${r.pct}</td>
    </tr>`).join('') || '<tr><td colspan="3" class="neutral">—</td></tr>');
  setHtml('losersTable', losers.map(r => `
    <tr>
      <td class="dn">${r.symbol}</td><td>${r.last}</td><td class="dn">${r.pct}</td>
    </tr>`).join('') || '<tr><td colspan="3" class="neutral">—</td></tr>');

  // Observations
  setHtml('observationsList', obs.map(o => `
    <div class="obs-item ${o.priority || 'low'}">
      <div class="obs-title">${o.title || '—'}</div>
      <div class="obs-body">${o.summary || ''}</div>
    </div>`).join('') || '<div class="obs-item low"><div class="obs-body">No observations yet.</div></div>');

  // Top story
  setText('topStory', risk.last_headline || wm.headline || '—');
  setText('topStoryNote', risk.headline_guidance || wm.summary || '—');

  // Session playbook bar (slim)
  const pb = d.session_playbook || {};
  setText('playbookSession', pb.session_type || '—');
  setText('playbookDriver', pb.dominant_driver || '—');
  const evts = pb.key_events || [];
  setText('playbookEvents', evts.length ? evts.map(e => e.split('—').pop().trim()).join(' · ') : 'None');
  setText('playbookTactical', pb.tactical_note || '—');

  // Scenarios — update playbook page silently in background
  if (d.scenarios) renderScenarios(d.scenarios);

  // Cross-asset intelligence card
  if (d.cross_asset_intelligence) renderCrossAsset(d.cross_asset_intelligence);

  // Footer
  setText('lastUpdated', `Last sync: ${new Date().toLocaleTimeString('en-US', {hour12:true, hour:'2-digit', minute:'2-digit', second:'2-digit'})} ET`);
}

// ════════ CROSS-ASSET INTELLIGENCE ════════
function renderCrossAsset(ca) {
  if (!ca) return;
  const mode = ca.cross_asset_mode || 'ALIGNED';
  const divs = ca.divergences || [];

  const badge = document.getElementById('caModeBadge');
  if (badge) {
    badge.textContent = mode;
    badge.className = 'ca-mode-badge ca-mode-' + mode;
  }

  const list = document.getElementById('caDivergenceList');
  if (!list) return;

  if (!divs.length) {
    const clean = '<div class="ca-clean">Assets are aligned — tape is clean</div>';
    if (list.innerHTML !== clean) list.innerHTML = clean;
    return;
  }

  const html = divs.map(d => `
    <div class="ca-div-item ${d.severity}">
      <div class="ca-div-header">
        <span class="ca-div-name">${d.name}</span>
        <span class="ca-sev-badge ca-sev-${d.severity}">${d.severity}</span>
      </div>
      <div class="ca-div-meaning">${d.what_it_means}</div>
      <div class="ca-div-watch"><b>Watch:</b> ${d.watch_for}</div>
    </div>`).join('');
  if (list.innerHTML !== html) list.innerHTML = html;
}

// ═══════════════════════════════════════
// H.A.R.V.E.Y RENDERER
// ═══════════════════════════════════════

function renderHarvey(d) {
  const bias      = d.bias_score      || 50;
  const biasDir   = d.bias_direction  || 'NEUTRAL';
  const verdict   = d.verdict         || 'WAIT';
  const reason    = d.verdict_reason  || '—';
  const vcolor    = d.verdict_color   || 'yellow';
  const orb       = d.orb_status      || '—';
  const orbNote   = d.orb_note        || '—';
  const orbQ      = d.orb_quality     || 'PENDING';
  const sig       = d.session_significance || {};
  const morning   = d.morning_edge    || {};
  const wm        = d.what_matters    || {};
  const ctx       = d.session_context || {};
  const signals   = d.last_signals    || d.raw_trade_alerts || [];
  const div       = d.divergence      || null;
  const nqFibs    = d.nq_fibs         || {};
  const esFibs    = d.es_fibs         || {};

  const vb = document.getElementById('harveyVerdict');
  if (vb) vb.className = `verdict-banner ${vcolor}`;
  setText('harveyVerdictWord',   verdict);
  setText('harveyVerdictReason', reason);

  // Regime row in verdict banner
  const regimePayload  = d.regime || {};
  const hvRcTextMap = {green:'var(--green)',blue:'var(--blue)',yellow:'var(--yellow)',red:'var(--red)',muted:'var(--muted2)'};
  const hvRcColor = hvRcTextMap[regimePayload.regime_color] || 'var(--text)';
  const hvRegimeEl = document.getElementById('harveyRegimeLabel');
  if (hvRegimeEl) { hvRegimeEl.textContent = regimePayload.regime || '—'; hvRegimeEl.style.color = hvRcColor; }
  const hvModeEl = document.getElementById('harveyHarveyMode');
  if (hvModeEl) { hvModeEl.textContent = regimePayload.harvey_mode || '—'; hvModeEl.style.color = hvRcColor; }

  const biasColor = bias >= 60 ? 'var(--green)' : bias <= 40 ? 'var(--red)' : 'var(--yellow)';
  const bsEl = document.getElementById('harveyBiasScore');
  if (bsEl) { bsEl.textContent = bias; bsEl.style.color = biasColor; }
  const bdEl = document.getElementById('harveyBiasDir');
  if (bdEl) { bdEl.textContent = biasDir; bdEl.style.color = biasColor; }
  const bfEl = document.getElementById('harveyBiasFill');
  if (bfEl) {
    bfEl.style.width = bias + '%';
    bfEl.style.background = `linear-gradient(90deg, ${bias >= 60 ? 'var(--green)' : bias <= 40 ? 'var(--red)' : 'var(--yellow)'}, ${bias >= 60 ? '#00b37a' : bias <= 40 ? '#cc2244' : '#d97706'})`;
  }

  const pillEl = document.getElementById('harveyOrbPill');
  if (pillEl) { pillEl.className = `orb-status-pill orb-${orbQ}`; pillEl.textContent = orbQ; }
  setText('harveyOrbStatus', orb);
  setText('harveyOrbNote',   orbNote);

  const divEl = document.getElementById('harveyDivergence');
  if (divEl) {
    divEl.innerHTML = (div && div.active) ? `
      <div class="divergence-alert">
        <div class="divergence-icon">⚠</div>
        <div class="divergence-text"><strong>NQ/ES Divergence Detected</strong><br>${div.note}</div>
      </div>` : '';
  }

  setText('harveySession',    ctx.session    || d.donna_session || '—');
  setText('harveyDay',        ctx.day        || '—');
  setText('harveyNextEvent',  ctx.next_event || '—');
  setText('harveyEventPhase', ctx.event_phase|| '—');
  setHtml('harveyMacroRisk',  riskBadge(d.macro_risk));
  setText('harveySessionLabel', sig.label    || '—');
  setText('harveyNqPts', sig.nq_points ? sig.nq_points + ' pts (' + (sig.nq_pct||0) + '%)' : '—');
  setText('harveyEsPts', sig.es_points ? sig.es_points + ' pts (' + (sig.es_pct||0) + '%)' : '—');

  function fibRows(fibs, highClass, lowClass, currentPrice) {
    if (!fibs || !fibs.high) return '<tr><td colspan="3" class="neutral" style="font-size:12px">No price data</td></tr>';
    const fmt = p => p ? p.toLocaleString('en-US', {minimumFractionDigits: 2}) : '—';
    const levels = [
      ['HIGH',  fibs.high,    highClass],
      ['78.6%', fibs.fib_786, ''],
      ['61.8%', fibs.fib_618, ''],
      ['50.0%', fibs.fib_500, ''],
      ['38.2%', fibs.fib_382, ''],
      ['23.6%', fibs.fib_236, ''],
      ['LOW',   fibs.low,     lowClass],
    ];
    const cur = parseFloat(currentPrice) || 0;
    const curRow = cur > 0 ? `<tr class="fib-cur-row"><td colspan="3"><div class="fib-cur-line"><span class="fib-cur-tag">▶ ${fmt(cur)}</span></div></td></tr>` : '';
    let rows = '';
    let inserted = false;
    for (const [label, price, cls] of levels) {
      const isPivot = label === '50.0%';
      const trCls = isPivot ? ' class="fib-pivot-row"' : '';
      const isAbove = cur > 0 && price !== undefined && price <= cur;
      if (!inserted && cur > 0 && price !== undefined && price <= cur) {
        rows += curRow;
        inserted = true;
      }
      const rsTag = cur <= 0 ? '' : (price > cur
        ? '<td class="fib-rs"><span class="fib-tag-r">R</span></td>'
        : '<td class="fib-rs"><span class="fib-tag-s">S</span></td>');
      rows += `<tr${trCls}><td class="fib-label">${label}</td><td class="fib-price ${cls}">${fmt(price)}</td>${rsTag || '<td class="fib-rs"></td>'}</tr>`;
    }
    if (!inserted && cur > 0) rows += curRow;
    return rows;
  }

  const nqDir = (d.nq_pct || 0) >= 0 ? 'up' : 'dn';
  const esDir = (d.es_pct || 0) >= 0 ? 'up' : 'dn';
  const nqEl = document.getElementById('harveyNqLast');
  if (nqEl) { nqEl.textContent = d.nq_last || '—'; nqEl.className = nqDir; }
  const esEl = document.getElementById('harveyEsLast');
  if (esEl) { esEl.textContent = d.es_last || '—'; esEl.className = esDir; }
  setHtml('harveyNqFibs', fibRows(nqFibs, 'fib-high', 'fib-low', d.nq_last));
  setHtml('harveyEsFibs', fibRows(esFibs, 'fib-high', 'fib-low', d.es_last));

  setText('harveyMorningBias',  morning.today_bias   || '—');
  setText('harveyOpenQuality',  morning.open_quality || '—');
  setText('harveyFocus',        morning.focus        || '—');
  setText('harveyWatchFirst',   (morning.watch_first || []).slice(0,4).join('  ·  ') || '—');
  setText('harveyFirstRead',    morning.first_read   || '—');

  setText('harveyWmHeadline', wm.headline    || '—');
  setText('harveyWmSummary',  wm.summary     || '—');
  setText('harveyWmMode',     (wm.mode||'—').replace(/_/g,' ').toUpperCase());
  setText('harveyWmRtc',      wm.risk_to_conviction || '—');
  setText('harveyWmFocus',    wm.focus_reason || '—');

  const sigEl = document.getElementById('harveySignals');
  if (sigEl) {
    if (signals && signals.length) {
      sigEl.innerHTML = signals.slice(0,10).map(s => `
        <div class="signal-card">
          <div class="signal-top">
            <span class="signal-ticker">${s.ticker || '—'}</span>
            <div style="display:flex;gap:8px;align-items:center">
              <span style="font-family:Space Mono,monospace;font-size:10px;color:var(--muted2)">${s.timeframe||''}</span>
              <span class="signal-verdict sv-${s.verdict||'SKIP'}">${s.verdict||'—'}</span>
            </div>
          </div>
          <div class="signal-meta">${s.signal||''} · ${s.session||''} · $${s.price||'—'} · Confidence: ${s.confidence||'—'}</div>
          <div class="signal-summary">${s.summary||''}</div>
        </div>`).join('');
    } else {
      sigEl.innerHTML = '<div class="obs-item low"><div class="obs-body">No signals yet. Waiting for TradingView webhook.</div></div>';
    }
  }

  if (d.cross_asset_intelligence) renderCrossAsset(d.cross_asset_intelligence);
}

async function refreshHarvey() {
  try {
    const res = await fetch('/harvey-data');
    if (!res.ok) return;
    const d = await res.json();
    renderHarvey(d);
    if (d.risk_engine) renderRiskEngine(d.risk_engine);
  } catch(e) {
    console.error('HARVEY refresh error:', e);
  }
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

  // Breaking ticker
  const tickerItems = news.slice(0, 6).map(n => n.headline || '').filter(Boolean);
  if (tickerItems.length) {
    const track = document.getElementById('breakingTickerTrack');
    if (track) {
      const doubled = [...tickerItems, ...tickerItems];
      track.innerHTML = doubled.map(h => `<span class="breaking-item">${h}</span>`).join('');
    }
  }

  // Index tiles helper
  function setTile(idVal, idChg, val, chg, pct, dir) {
    const elV = document.getElementById(idVal);
    const elC = document.getElementById(idChg);
    if (elV) {
      elV.textContent = val !== '-' ? (typeof val === 'number' ? val.toLocaleString(undefined,{maximumFractionDigits:2}) : val) : '—';
      elV.style.color = dir === 'up' ? 'var(--green)' : dir === 'down' ? 'var(--red)' : 'var(--text)';
    }
    if (elC) {
      elC.textContent = pct || '—';
      elC.style.color = dir === 'up' ? 'var(--green)' : dir === 'down' ? 'var(--red)' : 'var(--muted)';
    }
    const tileEl = elV && elV.closest('.index-tile');
    if (tileEl) {
      tileEl.classList.remove('up','dn');
      if (dir === 'up') tileEl.classList.add('up');
      else if (dir === 'down') tileEl.classList.add('dn');
    }
  }

  // Populate index tiles from market snapshot
  const nasdaq = snap.NASDAQ || {};
  const spx = snap.SPX || {};
  const djia = snap.DJIA || {};
  const dxy = snap.DXY || {};
  const vix = snap.VIX || {};

  function snapDir(obj) {
    const p = parseFloat(obj.pct);
    if (isNaN(p)) return '';
    return p >= 0 ? 'up' : 'down';
  }
  setTile('tileNASDAQ','tileNASDAQchg', nasdaq.last||'-', nasdaq.chg||'-', nasdaq.pct != null ? (parseFloat(nasdaq.pct)>=0?'+':'')+parseFloat(nasdaq.pct).toFixed(2)+'%':null, snapDir(nasdaq));
  setTile('tileSPX','tileSPXchg', spx.last||'-', spx.chg||'-', spx.pct != null ? (parseFloat(spx.pct)>=0?'+':'')+parseFloat(spx.pct).toFixed(2)+'%':null, snapDir(spx));
  setTile('tileDJIA','tileDJIAchg', djia.last||'-', djia.chg||'-', djia.pct != null ? (parseFloat(djia.pct)>=0?'+':'')+parseFloat(djia.pct).toFixed(2)+'%':null, snapDir(djia));
  setTile('tileDXY','tileDXYchg', dxy.last||'-', dxy.chg||'-', dxy.pct != null ? (parseFloat(dxy.pct)>=0?'+':'')+parseFloat(dxy.pct).toFixed(2)+'%':null, snapDir(dxy));
  setTile('tileVIX','tileVIXchg', vix.last||'-', vix.chg||'-', vix.pct != null ? (parseFloat(vix.pct)>=0?'+':'')+parseFloat(vix.pct).toFixed(2)+'%':null, snapDir(vix));

  // Feature story — top macro headline
  const featureText = risk.last_headline || news[0]?.headline || '—';
  const featureNote = risk.headline_guidance || risk.last_market_guidance || '—';
  const featureTag = classifyHeadlineTag(featureText);
  const ftEl = document.getElementById('featureStoryTag');
  if (ftEl) { ftEl.textContent = featureTag; ftEl.className = 'story-tag ' + featureTag; }
  setText('featureHeadline', featureText);
  setText('featureNote', featureNote);

  // Numbered news feed
  setHtml('newsList', news.length ? news.map((n, i) => {
    const tag = classifyHeadlineTag(n.headline);
    return `<div class="news-numbered-item">
      <div class="news-num">${i+1}.</div>
      <div class="news-body">
        <div class="news-headline">${n.headline || '—'} <span class="story-tag ${tag}" style="font-size:8px;padding:2px 6px;margin-left:6px">${tag}</span></div>
        <div class="news-meta">${n.source || '—'}</div>
        ${n.summary && n.summary !== n.headline ? `<div class="news-summary">${n.summary}</div>` : ''}
        ${n.url ? `<a class="news-link" href="${n.url}" target="_blank" rel="noopener">Read more →</a>` : ''}
      </div>
    </div>`;
  }).join('') : '<div class="obs-item low"><div class="obs-body">No live news loaded yet.</div></div>');

  // Sidebar
  setText('donnaRead', risk.last_market_guidance || risk.headline_guidance || '—');

  function setRiskBadge(id, level) {
    const el = document.getElementById(id);
    if (!el) return;
    const l = (level || 'medium').toLowerCase();
    el.textContent = l.toUpperCase();
    el.className = 'risk-badge risk-' + l;
  }
  setRiskBadge('sidebarMacroRisk', risk.macro_risk);
  setRiskBadge('sidebarHeadlineRisk', risk.headline_risk);
  setRiskBadge('sidebarMarketRisk', risk.market_news_risk);

  const phase = risk.event_phase || '—';
  setText('sidebarEventPhase', phase);
  setText('sidebarNextEvent', risk.next_event || '—');

  // Names to watch from movers
  const leaders = movers.leaders || [];
  const threats = movers.threats || [];
  const watchAll = [...leaders, ...threats].slice(0, 8);
  const watchEl = document.getElementById('sidebarWatchNames');
  if (watchEl) {
    watchEl.innerHTML = watchAll.length
      ? watchAll.map(m => `<span class="watch-name">${m.ticker}</span>`).join('')
      : '<span style="font-size:12px;color:var(--muted2)">—</span>';
  }
}

// ════════ RENDER ASSISTANT STATE ════════
function renderAssistantState(asst) {
  if (!asst) return;
  setText('dailyFocus', asst.daily_focus || '—');

  const tasks = asst.tasks || [];
  setHtml('tasksList', tasks.map((t, i) => `
    <div class="state-list-item">
      <span class="state-card-text">${t}</span>
      <button class="del-btn" onclick="deleteTask(${i})" title="Remove">✕</button>
    </div>`).join('') || '<div style="color:var(--muted2);font-size:13px;padding:8px 0">No tasks.</div>');

  const reminders = asst.reminders || [];
  setHtml('remindersList', reminders.map((r, i) => `
    <div class="state-list-item">
      <span class="state-card-text">${r}</span>
      <button class="del-btn" onclick="deleteReminder(${i})" title="Remove">✕</button>
    </div>`).join('') || '<div style="color:var(--muted2);font-size:13px;padding:8px 0">No reminders.</div>');
}

// ════════ MAIN REFRESH ════════
async function refresh() {
  try {
    const res = await fetch('/dashboard-data');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const d = await res.json();

    renderDashboard(d);
    renderNews(d);
    renderAssistantState(d.assistant);
    renderHarvey(d);
    refreshHarvey();

  } catch (err) {
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
    if (data.assistant) renderAssistantState(data.assistant);
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

// ════════ TASK / REMINDER ACTIONS ════════
async function deleteTask(index) {
  try {
    const res = await fetch('/assistant/delete-task', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({index})
    });
    const data = await res.json();
    if (data.assistant) renderAssistantState(data.assistant);
  } catch(e) { console.error(e); }
}

async function deleteReminder(index) {
  try {
    const res = await fetch('/assistant/delete-reminder', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({index})
    });
    const data = await res.json();
    if (data.assistant) renderAssistantState(data.assistant);
  } catch(e) { console.error(e); }
}

document.getElementById('addTaskBtn').addEventListener('click', async () => {
  const val = document.getElementById('taskInput').value.trim();
  if (!val) return;
  document.getElementById('taskInput').value = '';
  try {
    const res = await fetch('/assistant/add-task', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({task: val})
    });
    const data = await res.json();
    if (data.assistant) renderAssistantState(data.assistant);
  } catch(e) { console.error(e); }
});

document.getElementById('addReminderBtn').addEventListener('click', async () => {
  const val = document.getElementById('reminderInput').value.trim();
  if (!val) return;
  document.getElementById('reminderInput').value = '';
  try {
    const res = await fetch('/assistant/add-reminder', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({reminder: val})
    });
    const data = await res.json();
    if (data.assistant) renderAssistantState(data.assistant);
  } catch(e) { console.error(e); }
});

document.getElementById('taskInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('addTaskBtn').click();
});
document.getElementById('reminderInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('addReminderBtn').click();
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
    const banner = document.getElementById('harveyVerdict');
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

document.getElementById('scenarioGenBtn').addEventListener('click', () => refreshScenarios(true));

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
  applyDailyPnl('jPnlToday',     dp.today);
  applyDailyPnl('jPnlYesterday', dp.yesterday);
  applyDailyPnl('jPnlWeek',      dp.this_week);

  // Stats row
  setText('jTotalTrades', stats.total || 0);
  const wr = stats.win_rate || 0;
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
        const entryDisp = t.entry_price !== null && t.entry_price !== undefined ? t.entry_price : '—';
        const exitDisp  = t.exit_price  !== null && t.exit_price  !== undefined ? t.exit_price  : '—';
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

refresh();
setInterval(refresh, 20000);
refreshJournal();
setInterval(refreshJournal, 30000);
connectSSE();
</script>
</body>
</html>'''
