from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path

app = FastAPI(title="DONNA V3")
BASE_DIR = Path(__file__).parent


@app.get("/")
def root():
    return {"status": "Donna V3 online"}


@app.get("/dashboard-data")
def dashboard_data():
    return {
        "status": "online",
        "donna_session": "OFF_HOURS",
        "macro_risk": "low",
        "headline_risk": "medium",
        "market_news_risk": "medium",
        "next_event": "FOMC Member Bowman Speaks",
        "minutes_to_event": 95,
        "event_phase": "LATER_TODAY_OR_SOON",
        "donna_time": "2026-04-15T16:22:31-04:00",
        "dominant_driver": "Balanced Conditions",
        "secondary_driver": "Geopolitical Risk",
        "market_regime": "Neutral",
        "market_threat": "None",
        "market_confidence": "Low",
        "market_summary": "No strong market driver currently detected.",
        "last_headline": "Bessent suggests Fed should hold off on rate cuts for now amid war uncertainty - Politico",
        "headline_guidance": "Policy communication risk is elevated. Watch indices, USD, and rates.",
        "last_market_headline": "Tech Leads, Dow Lags As Oil Holds Near $92: What's Moving Markets Wednesday?",
        "last_market_guidance": "Broad market catalyst detected. Elevated index sensitivity.",
        "last_market_symbol": "QQQ",
        "last_market_severity": "MEDIUM",
        "active_warnings": [
            "HEADLINE: Moderate headline pressure active",
            "MARKET: Broad market catalyst is raising market-news pressure"
        ],
        "alerts": [],
        "market_rows": [
            {"symbol": "US 10-YR", "price": "4.281", "change": "+0.025", "pct": "+0.587 ▲", "dir": "up"},
            {"symbol": "EUR/USD", "price": "1.18", "change": "+0", "pct": "+0.009 ▲", "dir": "up"},
            {"symbol": "GOLD", "price": "4,816.6", "change": "-33.5", "pct": "-0.69 ▼", "dir": "down"},
            {"symbol": "OIL (MAY)", "price": "91.13", "change": "-0.15", "pct": "-0.16 ▼", "dir": "down"},
            {"symbol": "NASDAQ", "price": "24,016.017", "change": "+376.934", "pct": "+1.6 ▲", "dir": "up"},
            {"symbol": "S&P 500", "price": "7,022.95", "change": "+55.57", "pct": "+0.8 ▲", "dir": "up"},
            {"symbol": "DJIA", "price": "48,463.72", "change": "-72.27", "pct": "-0.15 ▼", "dir": "down"},
            {"symbol": "VIX", "price": "18.17", "change": "-0.19", "pct": "-1.03 ▼", "dir": "down"}
        ],
        "chart": {
            "symbol": "NQ",
            "label": "NASDAQ / NQ",
            "price": "23,885.49",
            "change": "+246.41 (+1.04%)",
            "range": "1D",
            "points": [62, 68, 64, 74, 79, 76, 84, 88, 86, 93, 97, 102, 98, 106, 111, 108, 114, 120, 117, 125, 132]
        }
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
<title>D.O.N.N.A</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#020817;
  --bg2:#071327;
  --panel:#0d1b31;
  --panel2:#12233f;
  --line:rgba(255,255,255,.08);
  --text:#edf4ff;
  --muted:#8ea4c5;
  --blue:#4f84ff;
  --blue2:#295fe5;
  --green:#43f7ad;
  --yellow:#ffd44f;
  --red:#ff637d;
  --shadow:0 16px 40px rgba(0,0,0,.34);
  --radius:22px;
}
body{
  font-family:Inter,Arial,sans-serif;
  color:var(--text);
  background:
    radial-gradient(circle at 0% 100%, rgba(67,247,173,.12), transparent 20%),
    radial-gradient(circle at 100% 0%, rgba(79,132,255,.16), transparent 25%),
    linear-gradient(180deg,var(--bg2),var(--bg));
  min-height:100vh;
  padding:28px;
}
.wrap{max-width:1540px;margin:0 auto}
.topbar{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;flex-wrap:wrap;margin-bottom:14px}
.brand h1{font-size:54px;letter-spacing:4px;font-weight:900;line-height:1}
.brand p{margin-top:8px;color:var(--muted);font-size:13px}
.top-right{display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap}
.online{
  display:flex;align-items:center;gap:10px;padding:10px 16px;border-radius:999px;
  background:rgba(67,247,173,.08);border:1px solid rgba(67,247,173,.22);font-weight:900;color:#afffd7;font-size:13px
}
.dot{width:9px;height:9px;border-radius:50%;background:var(--green);box-shadow:0 0 14px rgba(67,247,173,.8)}
.nav{display:flex;gap:10px;flex-wrap:wrap}
.nav button{
  border:none;cursor:pointer;padding:12px 16px;border-radius:14px;background:rgba(255,255,255,.04);
  color:#edf4ff;font-weight:800;border:1px solid rgba(255,255,255,.06)
}
.nav button.active{background:linear-gradient(135deg,var(--blue),var(--blue2));box-shadow:var(--shadow)}
.live-row{display:grid;grid-template-columns:200px 1fr 200px;gap:12px;align-items:center;margin-bottom:16px}
.live-pill,.session-pill,.tape{
  background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)
}
.live-pill{padding:14px 16px;color:#ffc0cc;border-color:rgba(255,99,125,.24);background:rgba(255,99,125,.08);font-size:12px;font-weight:900;letter-spacing:1.4px;text-transform:uppercase}
.session-pill{padding:14px 16px;text-align:center}
.session-pill .lab{font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted)}
.session-pill .val{margin-top:5px;font-size:18px;font-weight:900}
.tape{padding:14px 18px;display:flex;gap:34px;overflow:hidden;white-space:nowrap;font-size:13px;font-weight:700;color:#e7f0ff}
.tape span b{color:#fff}
.grid-hero{display:grid;grid-template-columns:1.45fr 1fr;gap:16px;margin-bottom:16px}
.panel,.card{
  background:linear-gradient(180deg, rgba(18,35,63,.92), rgba(13,27,49,.96));
  border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:22px
}
.kicker{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:var(--muted);margin-bottom:12px}
.hero-title{font-size:30px;font-weight:900;line-height:1.08;max-width:720px}
.hero-sub{margin-top:12px;font-size:15px;color:var(--muted)}
.focus-box{display:grid;gap:16px}
.mini-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.mini{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:14px}
.mini .lab{font-size:10px;color:var(--muted);letter-spacing:1.2px;text-transform:uppercase}
.mini .val{font-size:16px;font-weight:900;margin-top:8px;line-height:1.25}
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px}
.stat-card .lab{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.8px;margin-bottom:14px}
.stat-card .val{font-size:48px;font-weight:900;line-height:1;text-transform:uppercase}
.stat-card .sub{margin-top:10px;color:var(--muted);font-size:14px}
.low{color:var(--green)} .medium{color:var(--yellow)} .high{color:var(--red)}
.tabs{display:none}.tabs.active{display:block}
.section-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:16px}
.stack{display:grid;gap:16px}
.feed-item{padding:14px 0;border-bottom:1px solid rgba(255,255,255,.07);font-size:14px;line-height:1.45}
.feed-item:last-child{border-bottom:none}
.row{display:flex;justify-content:space-between;gap:16px;padding:14px 0;border-bottom:1px solid rgba(255,255,255,.07)}
.row:last-child{border-bottom:none}
.row .k{color:#dfeafb}.row .v{color:var(--muted);text-align:right}
.badges{display:flex;gap:10px;flex-wrap:wrap}
.badge{padding:9px 12px;border-radius:999px;font-size:12px;font-weight:800;background:rgba(255,99,125,.08);border:1px solid rgba(255,99,125,.24);color:#ffc0cc}
.chart-shell{display:grid;grid-template-columns:1.6fr .85fr;gap:16px}
.chart-panel{padding:0;overflow:hidden}
.chart-head{padding:22px 22px 0 22px}
.chip-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}
.chip,.range-btn{
  border:none;cursor:pointer;padding:10px 14px;border-radius:14px;background:rgba(255,255,255,.05);
  color:#edf4ff;font-weight:800;border:1px solid rgba(255,255,255,.06)
}
.range-btn.active,.chip.active{background:rgba(255,255,255,.12)}
.chart-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap}
.chart-symbol{font-size:18px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:1px}
.chart-price{font-size:64px;font-weight:900;line-height:1;margin-top:8px}
.chart-change{font-size:18px;font-weight:900;margin-top:8px;color:var(--green)}
.canvas-wrap{padding:0 22px 22px 22px}
.canvas-box{height:420px;border-radius:20px;border:1px solid rgba(255,255,255,.06);background:linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,.01));padding:18px;position:relative}
.canvas-box canvas{width:100%;height:100%}
.mini-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;padding:0 22px 22px 22px}
.small-card{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:18px;padding:16px}
.small-card .lab{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1.2px}
.small-card .val{margin-top:8px;font-size:16px;font-weight:900}
.trade-side .title{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.6px;margin-bottom:14px}
.table-card table{width:100%;border-collapse:collapse;font-size:14px}
.table-card th{color:var(--muted);text-align:left;padding:0 0 12px 0;font-size:12px;text-transform:uppercase;letter-spacing:1.4px;border-bottom:1px solid rgba(255,255,255,.08)}
.table-card td{padding:12px 0;border-bottom:1px solid rgba(255,255,255,.06);font-weight:700}
.table-card tr:last-child td{border-bottom:none}
.up{color:var(--green)} .down{color:var(--red)}
.footer{margin-top:16px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:12px}
@media(max-width:1200px){
  .grid-hero,.chart-shell,.section-grid{grid-template-columns:1fr}
  .stat-grid{grid-template-columns:repeat(2,1fr)}
  .live-row{grid-template-columns:1fr}
}
@media(max-width:760px){
  body{padding:16px}
  .brand h1{font-size:38px}
  .chart-price{font-size:42px}
  .stat-grid{grid-template-columns:1fr}
  .mini-stats{grid-template-columns:1fr}
}
</style>
</head>
<body>
<div class=\"wrap\">
  <div class=\"topbar\">
    <div class=\"brand\">
      <h1>D.O.N.N.A</h1>
      <p>Dynamic Operational Neural Network Assistant // Command Center</p>
    </div>
    <div class=\"top-right\">
      <div class=\"nav\">
        <button class=\"tab-btn active\" data-tab=\"dashboard\">Dashboard</button>
        <button class=\"tab-btn\" data-tab=\"trading\">Trading</button>
        <button class=\"tab-btn\" data-tab=\"news\">News</button>
        <button class=\"tab-btn\" data-tab=\"assistant\">Assistant</button>
      </div>
      <div class=\"online\"><span class=\"dot\"></span>ONLINE</div>
    </div>
  </div>

  <div class=\"live-row\">
    <div class=\"live-pill\">Live Intelligence</div>
    <div class=\"tape\" id=\"tape\"></div>
    <div class=\"session-pill\"><div class=\"lab\">Current Session</div><div class=\"val\" id=\"sessionVal\">OFF_HOURS</div></div>
  </div>

  <div class=\"grid-hero\">
    <div class=\"panel\">
      <div class=\"kicker\">Donna Overview</div>
      <div class=\"hero-title\" id=\"heroTitle\">Balanced Conditions is leading current conditions.</div>
      <div class=\"hero-sub\" id=\"heroSub\">No strong market driver currently detected.</div>
    </div>
    <div class=\"panel focus-box\">
      <div>
        <div class=\"kicker\">Daily Focus</div>
        <div style=\"font-size:18px;font-weight:900\">Build Donna into a true command center.</div>
      </div>
      <div class=\"mini-grid\">
        <div class=\"mini\"><div class=\"lab\">Donna Time</div><div class=\"val\" id=\"donnaTime\">-</div></div>
        <div class=\"mini\"><div class=\"lab\">Event Phase</div><div class=\"val\" id=\"eventPhase\">-</div></div>
      </div>
      <div>
        <div class=\"kicker\">Next Event Window</div>
        <div style=\"font-size:18px;font-weight:900\" id=\"nextEventHero\">-</div>
        <div class=\"hero-sub\" id=\"nextEventSub\">-</div>
      </div>
    </div>
  </div>

  <div class=\"stat-grid\">
    <div class=\"card stat-card\"><div class=\"lab\">Macro Risk</div><div class=\"val low\" id=\"macroRisk\">LOW</div><div class=\"sub\">Red-folder and macro event pressure</div></div>
    <div class=\"card stat-card\"><div class=\"lab\">Headline Risk</div><div class=\"val medium\" id=\"headlineRisk\">MEDIUM</div><div class=\"sub\">Global market-moving headline pressure</div></div>
    <div class=\"card stat-card\"><div class=\"lab\">Market Risk</div><div class=\"val medium\" id=\"marketRisk\">MEDIUM</div><div class=\"sub\">Company and sector catalyst pressure</div></div>
    <div class=\"card stat-card\"><div class=\"lab\">Next Event</div><div class=\"val\" style=\"font-size:18px;line-height:1.15\" id=\"nextEventCard\">FOMC Member Bowman Speaks</div><div class=\"sub\" id=\"nextEventMinutes\">95 minutes remaining</div></div>
  </div>

  <div class=\"tabs active\" id=\"tab-dashboard\">
    <div class=\"section-grid\">
      <div class=\"stack\">
        <div class=\"panel\"><div class=\"kicker\">Active Warnings</div><div class=\"badges\" id=\"warnings\"></div></div>
        <div class=\"panel\">
          <div class=\"kicker\">Donna Internal Clock</div>
          <div class=\"row\"><div class=\"k\">New York Time</div><div class=\"v\" id=\"clockNY\">-</div></div>
          <div class=\"row\"><div class=\"k\">Day</div><div class=\"v\">Wednesday</div></div>
          <div class=\"row\"><div class=\"k\">Session</div><div class=\"v\" id=\"clockSession\">-</div></div>
          <div class=\"row\"><div class=\"k\">Event Phase</div><div class=\"v\" id=\"clockPhase\">-</div></div>
          <div class=\"row\"><div class=\"k\">Event Time NY</div><div class=\"v\">2026-04-15 05:45 PM UTC-04:00</div></div>
        </div>
      </div>
      <div class=\"stack\">
        <div class=\"panel\"><div class=\"kicker\">Recent Donna Alerts</div><div class=\"feed-item\">No alerts yet</div></div>
        <div class=\"panel\">
          <div class=\"kicker\">Market Driver Engine</div>
          <div class=\"row\"><div class=\"k\">Dominant Driver</div><div class=\"v\" id=\"domDriver\">-</div></div>
          <div class=\"row\"><div class=\"k\">Secondary Driver</div><div class=\"v\" id=\"secDriver\">-</div></div>
          <div class=\"row\"><div class=\"k\">Regime</div><div class=\"v\" id=\"regime\">-</div></div>
          <div class=\"row\"><div class=\"k\">Threat</div><div class=\"v\" id=\"threat\">-</div></div>
          <div class=\"row\"><div class=\"k\">Confidence</div><div class=\"v\" id=\"confidence\">-</div></div>
          <div class=\"hero-sub\" id=\"driverSummary\">No strong market driver currently detected.</div>
        </div>
      </div>
    </div>
  </div>

  <div class=\"tabs\" id=\"tab-trading\">
    <div class=\"chart-shell\">
      <div class=\"panel chart-panel\">
        <div class=\"chart-head\">
          <div class=\"kicker\">Trading Command Center</div>
          <div class=\"chip-row\" id=\"symbolRow\">
            <button class=\"chip active\" data-symbol=\"NQ\">NQ</button>
            <button class=\"chip\" data-symbol=\"ES\">ES</button>
            <button class=\"chip\" data-symbol=\"SPX\">SPX</button>
            <button class=\"chip\" data-symbol=\"BTC\">BTC</button>
            <button class=\"chip\" data-symbol=\"NVDA\">NVDA</button>
            <button class=\"chip\" data-symbol=\"TSLA\">TSLA</button>
          </div>
          <div class=\"chart-top\">
            <div>
              <div class=\"chart-symbol\" id=\"chartLabel\">NASDAQ / NQ</div>
              <div class=\"chart-price\" id=\"chartPrice\">23,885.49</div>
              <div class=\"chart-change\" id=\"chartChange\">+246.41 (+1.04%)</div>
            </div>
            <div class=\"chip-row\" id=\"rangeRow\">
              <button class=\"range-btn active\">1D</button>
              <button class=\"range-btn\">5D</button>
              <button class=\"range-btn\">1M</button>
              <button class=\"range-btn\">6M</button>
              <button class=\"range-btn\">1Y</button>
            </div>
          </div>
        </div>
        <div class=\"canvas-wrap\">
          <div class=\"canvas-box\"><canvas id=\"tradeChart\"></canvas></div>
        </div>
        <div class=\"mini-stats\">
          <div class=\"small-card\"><div class=\"lab\">Momentum</div><div class=\"val\">Constructive</div><div class=\"hero-sub\">Trend state</div></div>
          <div class=\"small-card\"><div class=\"lab\">Risk Tone</div><div class=\"val\">Balanced</div><div class=\"hero-sub\">Volatility pressure</div></div>
          <div class=\"small-card\"><div class=\"lab\">Donna Read</div><div class=\"val\">AI Leadership</div><div class=\"hero-sub\">Current driver</div></div>
        </div>
      </div>

      <div class=\"stack trade-side\">
        <div class=\"panel\">
          <div class=\"title\">Donna Trade Intelligence</div>
          <div class=\"row\"><div class=\"k\">Bias</div><div class=\"v\">Bullish Intraday</div></div>
          <div class=\"row\"><div class=\"k\">Regime</div><div class=\"v\" id=\"tradeRegime\">Neutral</div></div>
          <div class=\"row\"><div class=\"k\">Dominant Driver</div><div class=\"v\" id=\"tradeDriver\">Balanced Conditions</div></div>
          <div class=\"row\"><div class=\"k\">Threat</div><div class=\"v\" id=\"tradeThreat\">None</div></div>
          <div class=\"row\"><div class=\"k\">Event Risk</div><div class=\"v\" id=\"tradeEvent\">Bowman Speaks</div></div>
          <div class=\"row\"><div class=\"k\">Confidence</div><div class=\"v\" id=\"tradeConfidence\">Low</div></div>
          <div class=\"hero-sub\">Donna is aligning trading conditions with macro timing and current market drivers.</div>
        </div>

        <div class=\"panel table-card\">
          <div class=\"title\">Market Pulse</div>
          <table>
            <thead><tr><th>Symbol</th><th>Price</th><th>Change</th><th>%Change</th></tr></thead>
            <tbody id=\"marketTable\"></tbody>
          </table>
        </div>

        <div class=\"panel\">
          <div class=\"title\">Recent Alerts</div>
          <div class=\"feed-item\">No alerts yet</div>
        </div>
      </div>
    </div>
  </div>

  <div class=\"tabs\" id=\"tab-news\">
    <div class=\"section-grid\">
      <div class=\"stack\">
        <div class=\"panel\"><div class=\"kicker\">Top Story</div><div style=\"font-size:28px;font-weight:900;line-height:1.12\" id=\"topStory\">-</div><div class=\"hero-sub\" id=\"topStoryNote\">-</div></div>
        <div class=\"panel\"><div class=\"kicker\">Donna Briefing</div><div class=\"feed-item\"><b>Dominant Driver:</b> <span id=\"newsDriver\"></span></div><div class=\"feed-item\"><b>Secondary Driver:</b> <span id=\"newsSecond\"></span></div><div class=\"feed-item\"><b>Regime:</b> <span id=\"newsRegime\"></span></div><div class=\"feed-item\"><b>Threat:</b> <span id=\"newsThreat\"></span></div><div class=\"feed-item\"><b>Confidence:</b> <span id=\"newsConfidence\"></span></div><div class=\"hero-sub\" id=\"newsSummary\"></div></div>
      </div>
      <div class=\"stack\">
        <div class=\"panel\"><div class=\"kicker\">Macro Countdown</div><div style=\"font-size:28px;font-weight:900;line-height:1.12\" id=\"macroTitle\">-</div><div class=\"hero-sub\" id=\"macroSub\">-</div></div>
        <div class=\"panel\"><div class=\"kicker\">Market Catalyst</div><div style=\"font-size:24px;font-weight:900;line-height:1.2\" id=\"marketTitle\">-</div><div class=\"hero-sub\" id=\"marketSub\">-</div></div>
        <div class=\"panel\"><div class=\"kicker\">Live News Tape</div><div class=\"feed-item\"><b>Latest Headline:</b> <span id=\"latestHeadline\"></span></div><div class=\"feed-item\"><b>Latest Market Story:</b> <span id=\"latestMarket\"></span></div></div>
      </div>
    </div>
  </div>

  <div class=\"tabs\" id=\"tab-assistant\">
    <div class=\"section-grid\">
      <div class=\"panel\"><div class=\"kicker\">Donna AI Assistant</div><div class=\"feed-item\">Donna online. Ask for risk, time, session, event timing, news, alerts, or give a command.</div><div class=\"feed-item\">Assistant routes can be wired into this layout next.</div></div>
      <div class=\"panel\"><div class=\"kicker\">Assistant State</div><div class=\"feed-item\">Daily focus, tasks, reminders, and quick actions can live here cleanly without breaking the platform.</div></div>
    </div>
  </div>

  <div class=\"footer\"><div>Donna Core Recovery Build</div><div id=\"footerTime\">last update: -</div></div>
</div>

<script>
let state = null;

function setActiveTab(name){
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tabs').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => setActiveTab(btn.dataset.tab));
});

document.querySelectorAll('.range-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
});

document.querySelectorAll('.chip').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.chip').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('chartLabel').textContent = btn.dataset.symbol + ' / LIVE';
  });
});

function riskClass(v){
  v = String(v || '').toLowerCase();
  if(v === 'high') return 'high';
  if(v === 'medium') return 'medium';
  return 'low';
}

function drawChart(points){
  const canvas = document.getElementById('tradeChart');
  const parent = canvas.parentElement;
  const ratio = window.devicePixelRatio || 1;
  const w = parent.clientWidth - 36;
  const h = parent.clientHeight - 36;
  canvas.width = w * ratio;
  canvas.height = h * ratio;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);
  ctx.clearRect(0,0,w,h);

  ctx.strokeStyle = 'rgba(255,255,255,.08)';
  ctx.lineWidth = 1;
  for(let i=1;i<5;i++){
    const y = (h/5)*i;
    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke();
  }

  const min = Math.min(...points), max = Math.max(...points);
  const pad = 20;
  ctx.beginPath();
  points.forEach((p,i)=>{
    const x = (i/(points.length-1)) * (w - pad*2) + pad;
    const y = h - (((p-min)/(max-min || 1)) * (h - pad*2) + pad);
    if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
  });
  ctx.strokeStyle = '#58a6ff';
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.lineTo(w-pad, h-pad);
  ctx.lineTo(pad, h-pad);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0,0,0,h);
  grad.addColorStop(0,'rgba(88,166,255,.28)');
  grad.addColorStop(1,'rgba(88,166,255,.02)');
  ctx.fillStyle = grad;
  ctx.fill();
}

function renderTable(rows){
  const body = document.getElementById('marketTable');
  body.innerHTML = rows.map(r => `
    <tr>
      <td>${r.symbol}</td>
      <td>${r.price}</td>
      <td class="${r.dir}">${r.change}</td>
      <td class="${r.dir}">${r.pct}</td>
    </tr>
  `).join('');
}

function render(data){
  state = data;
  document.getElementById('sessionVal').textContent = data.donna_session;
  document.getElementById('heroTitle').textContent = `${data.dominant_driver} is leading current conditions.`;
  document.getElementById('heroSub').textContent = data.market_summary;
  document.getElementById('donnaTime').textContent = data.donna_time;
  document.getElementById('eventPhase').textContent = data.event_phase;
  document.getElementById('nextEventHero').textContent = data.next_event;
  document.getElementById('nextEventSub').textContent = `${data.minutes_to_event} minutes to event`;
  document.getElementById('nextEventCard').textContent = data.next_event;
  document.getElementById('nextEventMinutes').textContent = `${data.minutes_to_event} minutes remaining`;

  const macro = document.getElementById('macroRisk');
  macro.textContent = String(data.macro_risk).toUpperCase(); macro.className = 'val ' + riskClass(data.macro_risk);
  const head = document.getElementById('headlineRisk');
  head.textContent = String(data.headline_risk).toUpperCase(); head.className = 'val ' + riskClass(data.headline_risk);
  const market = document.getElementById('marketRisk');
  market.textContent = String(data.market_news_risk).toUpperCase(); market.className = 'val ' + riskClass(data.market_news_risk);

  document.getElementById('clockNY').textContent = data.donna_time;
  document.getElementById('clockSession').textContent = data.donna_session;
  document.getElementById('clockPhase').textContent = data.event_phase;
  document.getElementById('domDriver').textContent = data.dominant_driver;
  document.getElementById('secDriver').textContent = data.secondary_driver;
  document.getElementById('regime').textContent = data.market_regime;
  document.getElementById('threat').textContent = data.market_threat;
  document.getElementById('confidence').textContent = data.market_confidence;
  document.getElementById('driverSummary').textContent = data.market_summary;
  document.getElementById('warnings').innerHTML = data.active_warnings.map(x => `<span class="badge">${x}</span>`).join('');

  document.getElementById('chartLabel').textContent = data.chart.label;
  document.getElementById('chartPrice').textContent = data.chart.price;
  document.getElementById('chartChange').textContent = data.chart.change;
  document.getElementById('tradeRegime').textContent = data.market_regime;
  document.getElementById('tradeDriver').textContent = data.dominant_driver;
  document.getElementById('tradeThreat').textContent = data.market_threat;
  document.getElementById('tradeEvent').textContent = data.next_event;
  document.getElementById('tradeConfidence').textContent = data.market_confidence;
  renderTable(data.market_rows);
  drawChart(data.chart.points);

  document.getElementById('topStory').textContent = data.last_headline;
  document.getElementById('topStoryNote').textContent = data.headline_guidance;
  document.getElementById('newsDriver').textContent = data.dominant_driver;
  document.getElementById('newsSecond').textContent = data.secondary_driver;
  document.getElementById('newsRegime').textContent = data.market_regime;
  document.getElementById('newsThreat').textContent = data.market_threat;
  document.getElementById('newsConfidence').textContent = data.market_confidence;
  document.getElementById('newsSummary').textContent = data.market_summary;
  document.getElementById('macroTitle').textContent = data.next_event;
  document.getElementById('macroSub').textContent = `${data.minutes_to_event} minutes until event window.`;
  document.getElementById('marketTitle').textContent = data.last_market_headline;
  document.getElementById('marketSub').textContent = data.last_market_guidance;
  document.getElementById('latestHeadline').textContent = data.last_headline;
  document.getElementById('latestMarket').textContent = data.last_market_headline;
  document.getElementById('footerTime').textContent = 'last update: ' + data.donna_time;

  document.getElementById('tape').innerHTML = `
    <span><b>Macro:</b> ${String(data.macro_risk).toUpperCase()}</span>
    <span><b>Headline:</b> ${String(data.headline_risk).toUpperCase()}</span>
    <span><b>Market:</b> ${String(data.market_news_risk).toUpperCase()}</span>
    <span><b>Driver:</b> ${data.dominant_driver}</span>
    <span><b>Threat:</b> ${data.market_threat}</span>
    <span><b>Event:</b> ${data.next_event}</span>
    <span><b>Session:</b> ${data.donna_session}</span>
  `;
}

fetch('/dashboard-data').then(r => r.json()).then(render);
window.addEventListener('resize', () => state && drawChart(state.chart.points));
</script>
</body>
</html>"""
