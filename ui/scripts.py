"""ui/scripts.py — NOVA dashboard JavaScript, extracted from ui/html.py
during the interface-modularization foundation (commit #9).

One intentional, Pedro-approved content change is included here (not a
modularization side effect): the Settings page's "Trading Subsystem"
status readout (`#setTradingStatus`, sourced from `env.trading_subsystem
_enabled`) has been removed per the mandatory correction that the retired
Execution Bot / legacy trading subsystem must not appear anywhere in
Interface V1, including as a Settings status card. Every other line of
this file is byte-for-byte identical to the corresponding lines that were
previously inline inside DASHBOARD_HTML's <script> block.
"""
DASHBOARD_SCRIPT = '''// ════════ CUSTOMIZABLE INDEX TILES ════════
const SYMBOL_LIST = ['NQ','ES','SPX','NASDAQ','DJIA','DXY','VIX','US10Y','GOLD','SILVER','OIL','BTC','ETH'];
const DEFAULT_PREFS = ['NQ','ES','VIX','DXY','GOLD'];
const LS_KEY = 'user_index_prefs';
let _lastDashData = null;
let _activePicker = null;

// The platform has two deliberate bases: true black and true white. The
// reader's explicit choice wins; otherwise NOVA follows the OS preference.
const THEME_KEY = 'nova_color_mode';
function setNovaTheme(mode, persist) {
  const chosen = mode === 'light' ? 'light' : 'dark';
  document.documentElement.dataset.theme = chosen;
  if (persist) localStorage.setItem(THEME_KEY, chosen);
  const btn = document.getElementById('themeToggle');
  if (btn) {
    btn.textContent = chosen === 'dark' ? '◐  Light mode' : '◑  Dark mode';
    btn.setAttribute('aria-label', 'Switch to ' + (chosen === 'dark' ? 'light' : 'dark') + ' mode');
  }
}
function initNovaTheme() {
  let saved = null;
  try { saved = localStorage.getItem(THEME_KEY); } catch (e) {}
  const preferred = saved === 'light' || saved === 'dark' ? saved
    : (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  setNovaTheme(preferred, false);
  const btn = document.getElementById('themeToggle');
  if (btn) btn.addEventListener('click', () => {
    setNovaTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark', true);
  });
}

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

// ── Deterministic display humanizer ──────────────────────────────────────
// Turns a machine code into readable prose for DISPLAY ONLY: underscores
// become spaces and each word is title-cased. This is a pure formatting
// transform -- it never changes, reinterprets or re-grades the underlying
// value (TRENDING_UP -> "Trending Up", NY CASH -> "NY Cash", LOW -> "Low";
// a LOW macro risk is never restated as "Normal"). Acronyms that would be
// mangled by naive title-casing are preserved verbatim.
const _KEEP_UPPER = new Set(['NY', 'ES', 'NQ', 'US', 'ET', 'VIX', 'DXY', 'ORB', 'IB', 'PDH', 'PDL', 'ONH', 'ONL', 'PWH', 'PWL', 'AM', 'PM', 'EOD', 'CPI', 'FOMC', 'PPI', 'GDP']);
function humanizeCode(code) {
  if (code === null || code === undefined || code === '') return '—';
  return String(code)
    .replace(/_/g, ' ')
    .trim()
    .split(/\\s+/)
    .map(w => _KEEP_UPPER.has(w.toUpperCase()) ? w.toUpperCase()
              : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

// Every return carries a `src` tag naming which upstream feed produced the
// number. Freshness cannot be judged without knowing that: each feed has its
// own producer timestamp (or none at all). Purely additive -- existing
// callers read .val/.chg/.pct/.dir and are unaffected.
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
        dir: isNaN(p) ? '' : (p >= 0 ? 'up' : 'down'),
        src: 'snapshot'
      };
    }
  }

  // BTC comes from the dedicated /btc-vix endpoint
  if (sym === 'BTC') {
    const q = _liveBtcVix[sym] || {};
    const last = q.last || 0;
    if (!last) return {val: '—', chg: '—', pct: null, dir: '', src: 'none'};
    const p = parseFloat(q.pct || 0);
    return {
      val: last.toLocaleString('en-US', {maximumFractionDigits: 0}),
      chg: (q.chg || 0).toFixed(2),
      pct: (p >= 0 ? '+' : '') + p.toFixed(2) + '%',
      dir: p >= 0 ? 'up' : 'down',
      src: 'btcvix'
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
        dir: p >= 0 ? 'up' : 'down',
        src: 'btcvix'
      };
    }
  }

  // Futures macro pulse
  const pulseRow = (d.futures_macro_pulse || []).find(r => r.symbol === sym);
  if (pulseRow && pulseRow.last && pulseRow.last !== '-' && pulseRow.last !== '—') {
    const disp = formatPrice(pulseRow.last, 2);
    if (disp !== '—') return {val: disp, chg: pulseRow.chg || '—', pct: pulseRow.pct || null, dir: pulseRow.dir || '', src: 'pulse'};
  }

  // Major indexes
  const idxLabelMap = {NASDAQ: 'NASDAQ', SPX: 'S&P 500', DJIA: 'DJIA', DXY: 'DXY', US10Y: 'US 10Y'};
  const label = idxLabelMap[sym] || sym;
  const row = (d.major_indexes || []).find(r => r.symbol === label);
  if (row && row.last && row.last !== '-' && row.last !== '—') {
    const disp = formatPrice(row.last, 2);
    if (disp !== '—') return {val: disp, chg: row.chg || '—', pct: row.pct || null, dir: row.dir || '', src: 'indexes'};
  }

  return {val: '—', chg: '—', pct: null, dir: '', src: 'none'};
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
initNovaTheme();
document.querySelectorAll('.tab-btn[data-page]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn[data-page]').forEach(b => {
      b.classList.remove('active');
      b.removeAttribute('aria-current');
    });
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    // Keeps the accessible "you are here" state in sync with the visual one.
    btn.setAttribute('aria-current', 'page');
    document.getElementById('page-' + btn.dataset.page).classList.add('active');
    if (btn.dataset.page === 'journal') { refreshJournal(); refreshJournalWorkspace(); switchJournalView('dashboard'); }
    if (btn.dataset.page === 'settings') { refreshSettings(); }
    if (btn.dataset.page === 'assistant') { refreshNovaIntelligence(); }
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

function renderDashboard() {
  const se   = _dbStateEngine || {};
  const risk = (_lastDashData || {}).risk || {};
  const snap = risk.market_snapshot || {};

  // ── Live strip + session (shared topbar)
  if (_lastDashData) {
    setText('sessionVal', risk.nova_session || risk.donna_session || '—');
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
  const session = se.session_state || risk.nova_session || risk.donna_session || '';
  // Documented regime -> colour mapping. Any code not listed here falls
  // through to neutral rather than borrowing a meaning it has not earned.
  const rCol = {
    TRENDING_UP:   'var(--green)',
    TRENDING_DOWN: 'var(--red)',
    RANGING:       'var(--yellow)',
    MIXED:         'var(--muted)',
    VOLATILE:      'var(--red)',
    EVENT_DRIVEN:  'var(--yellow)',
    UNKNOWN:       'var(--muted)',
  };
  const regimeColor = rCol[regime] || 'var(--muted)';
  const regimeEl = document.getElementById('dbRegimeText');
  if (regimeEl) {
    // Display-only humanization -- "TRENDING_UP" reads "Trending Up". The
    // underlying regime code is unchanged and still drives every colour and
    // downstream mapping.
    regimeEl.textContent = humanizeCode(regime);
    regimeEl.style.color = regimeColor;
  }

  // ── STATUS-RAIL DOTS ──
  // Painted from live state, never hard-coded in markup. Colour is purely
  // redundant here: each cell's value line already states its condition in
  // words, so the rail is fully readable with colour ignored.
  const macroColor = macro === 'high' ? 'var(--red)' : macro === 'medium' ? 'var(--yellow)' : 'var(--green)';
  const _setDot = (id, color) => {
    const el = document.getElementById(id);
    if (el) el.style.background = color;
  };
  _setDot('ovDotMacro', macroColor);
  _setDot('ovDotRegime', regimeColor);
  // Market Tone is the same `regime` signal expressed as prose -- it shares
  // regime's colour precisely because it is not an independent dimension.
  _setDot('ovDotTone', regimeColor);
  const toneMap = {
    TRENDING_UP:   macro === 'high' ? 'Trending higher — macro conditions elevated, respect event risk' : 'Trending higher — momentum environment, tech leading',
    TRENDING_DOWN: macro === 'high' ? 'Trending lower — macro conditions elevated' : 'Trending lower — respect the tape',
    RANGING:       'Range-bound tape — reduced edge, fade extremes only',
    MIXED:         'Mixed tape — NQ/ES diverging, no clear directional edge',
    VOLATILE:      'Volatile conditions — reduce size, protect capital',
    EVENT_DRIVEN:  'Macro conditions elevated — respect event risk',
    UNKNOWN:       'Connecting to live market intelligence...',
  };
  setText('dbMarketTone', toneMap[regime] || humanizeCode(regime));
  // Short one/two-word label for the Overview status rail's "Market Tone"
  // value slot -- a display-only shorthand for the exact same `regime`
  // signal driving dbRegimeText/dbMarketTone above, not a new/independent
  // data dimension.
  const toneShortMap = {
    TRENDING_UP: 'Constructive', TRENDING_DOWN: 'Cautious', RANGING: 'Neutral', MIXED: 'Mixed',
    VOLATILE: 'Elevated Risk', EVENT_DRIVEN: 'Event-Driven', UNKNOWN: 'Connecting…',
  };
  setText('dbMarketToneShort', toneShortMap[regime] || humanizeCode(regime));

  // Macro Risk sub-caption. Must NOT restate the value (the cell already
  // reads "Low"). Uses genuinely distinct red-folder / event-phase state
  // when risk_state supplies it, otherwise a neutral provenance label --
  // never an invented descriptive phrase.
  const macroEl = document.getElementById('dbMacroPosture');
  if (macroEl) {
    const phase = String(risk.event_phase || '').toUpperCase();
    let sub;
    if (risk.red_folder_week === true)          sub = 'Red-folder week';
    else if (phase && phase !== 'NONE')         sub = humanizeCode(phase) + ' phase';
    else if (risk.red_folder_week === false)    sub = 'No red-folder lock';
    else                                         sub = 'Deterministic macro feed';
    macroEl.textContent = sub;
  }

  // ── BADGES ──
  const bMacro = document.getElementById('dbBadgeMacro');
  if (bMacro) {
    // Humanized for display only -- LOW stays LOW in meaning, rendered "Low".
    bMacro.textContent = humanizeCode(macro);
    bMacro.style.color = macroColor;
  }
  const bSess = document.getElementById('dbBadgeSession');
  if (bSess) {
    const sLbl = {NEW_YORK_CASH:'NY Cash',LONDON:'London',ASIA:'Asia',OFF_HOURS:'Off Hours'};
    const sCol = {NEW_YORK_CASH:'var(--green)',LONDON:'var(--blue)',ASIA:'var(--yellow)',OFF_HOURS:'var(--muted)'};
    bSess.textContent = sLbl[session] || humanizeCode(session);
    bSess.style.color = sCol[session] || 'var(--muted)';
  }

  // ── DRIVER ──
  const driver = (_lastDashData || {}).driver || {};
  const wm     = (_lastDashData || {}).what_matters_now || {};
  const driverHeadline = driver.dominant_driver || wm.headline || '';
  // Approved hierarchy: a visible driver headline above the bullets. This is
  // the real `dominant_driver` the engine already computes -- previously
  // written to a hidden node and thrown away.
  const dhEl = document.getElementById('dbDriverPrimary');
  if (dhEl) {
    dhEl.textContent = driverHeadline || 'Driver unavailable';
    dhEl.style.display = '';
    dhEl.style.color = driverHeadline ? 'var(--blue)' : 'var(--muted2)';
  }
  // Regime cell's sub-caption: the dominant driver is genuinely distinct
  // information, so it never restates the regime code above it.
  setText('dbDriverRegime', driverHeadline || 'Deterministic regime engine');

  const bullets = [];
  if (driver.market_summary) bullets.push(driver.market_summary);
  if (wm.headline && wm.headline !== driver.dominant_driver) bullets.push(wm.headline);
  if (wm.summary)  bullets.push(wm.summary);
  const bullEl = document.getElementById('dbDriverBullets');
  if (bullEl) {
    // Exactly as many bullets as the engine genuinely returned -- never
    // padded to three to resemble the mockup.
    setHtml('dbDriverBullets', bullets.length
      ? bullets.slice(0, 3).map(b => `<li>${b}</li>`).join('')
      : `<li class="ov-none">${_lastDashData ? 'No driver explanation available.' : 'Loading market driver…'}</li>`);
  }

  // ── CATALYST ──
  const catHeadline = risk.last_headline || '';
  const catSummary  = risk.headline_guidance || '';
  const chEl = document.getElementById('dbCatalystHeadline');
  if (chEl) {
    chEl.textContent = catHeadline || (_lastDashData ? 'No catalyst identified.' : 'Loading catalyst…');
    chEl.style.color = catHeadline ? 'var(--text)' : 'var(--muted2)';
  }
  // Previously rendered a bare "—" whenever guidance was absent. An empty
  // field now collapses instead of leaving a stray dash on the page.
  const csEl = document.getElementById('dbCatalystSummary');
  if (csEl) {
    csEl.textContent = catSummary;
    csEl.style.display = catSummary ? '' : 'none';
  }
  // NOVA computes no directional bearish<->bullish sentiment for the
  // catalyst -- this element previously displayed a hard-coded literal
  // 'NEUTRAL', which was an invented interpretation, not data. risk_state
  // does carry a genuine headline SEVERITY, so that is shown instead,
  // explicitly labelled as severity. With no severity, the badge states it
  // is unavailable rather than implying a neutral reading. The approved
  // bearish->bullish scale is deliberately NOT drawn: no field supports a
  // deterministic position on it.
  const sentEl = document.getElementById('dbCatalystSentiment');
  if (sentEl) {
    const sev = String(risk.headline_severity || '').toUpperCase();
    const sevCol = {HIGH: 'var(--red)', MEDIUM: 'var(--yellow)', LOW: 'var(--green)'};
    sentEl.textContent = sev ? `Headline risk: ${humanizeCode(sev)}` : 'Sentiment unavailable';
    sentEl.style.color = sev ? (sevCol[sev] || 'var(--muted)') : 'var(--muted2)';
  }

  // ── MARKET BOARD ──
  // Freshness comes from the authoritative timestamp of whichever upstream
  // feed actually produced each tile's number -- NOT from the fact that
  // /dashboard-data returned 200. Tiles can legitimately come from different
  // feeds (risk_state's market_snapshot vs the dedicated /btc-vix endpoint),
  // each with its own timestamp, so every tile is scored individually and the
  // board chip reports the LEAST-CURRENT of them.
  const _dbd = _lastDashData || {};
  const _snapTs = ((_dbd.risk || {}).market_snapshot || {})._updated_at
                  || (_dbd.risk || {}).last_updated || null;
  const _srcFreshness = {
    // Written by services/finnhub.py on every snapshot refresh.
    snapshot: _ovAgeState(_snapTs),
    // Written by the /btc-vix endpoint's own cache.
    btcvix:   _ovAgeState((_liveBtcVix || {}).fetched_at),
    // futures_macro_pulse and major_indexes are assembled per-request with no
    // producer timestamp of their own -- their age is genuinely unknowable
    // from here, which is exactly what 'nofresh' says.
    pulse:    'nofresh',
    indexes:  'nofresh',
    none:     'unavailable',
  };
  const _boardStates = [];
  ['NQ','ES','VIX','DXY','GOLD'].forEach(sym => {
    const data = getSymbolData(sym, _dbd);
    const tile = document.querySelector(`.db-market-tile[data-sym="${sym}"]`);
    if (!tile) return;
    const st = _srcFreshness[data.src || 'none'] || 'nofresh';
    _boardStates.push(st);
    tile.dataset.fresh = st;
    tile.setAttribute('title', `${sym} — ${_OV_FRESH_LABEL[st] || 'Unavailable'}`);
    const valEl = tile.querySelector('.db-tile-val');
    const pctEl = tile.querySelector('.db-tile-pct');
    // Approved treatment: the PRICE stays neutral (a price is not good or
    // bad), and semantic green/red is reserved for the change, which is the
    // only part that actually carries direction. The arrow glyph repeats
    // that direction in text, so the meaning survives without colour.
    if (valEl) { valEl.textContent = data.val || '—'; valEl.style.color = 'var(--text)'; }
    if (pctEl) {
      const arrow = data.dir === 'up' ? '▲ ' : data.dir === 'down' ? '▼ ' : '';
      pctEl.textContent = data.pct ? arrow + data.pct : '—';
      pctEl.style.color = data.dir === 'up' ? 'var(--green)' : data.dir === 'down' ? 'var(--red)' : 'var(--muted)';
    }
  });
  if (_boardStates.length) {
    const worst = _ovWorstFreshness(_boardStates);
    const detail = _snapTs ? `Market snapshot last updated ${new Date(_snapTs).toLocaleString()}` : 'No producer timestamp available';
    _ovSetFreshness('ovBoardFresh', worst, detail);
  }

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

// ════════ MORNING BRIEF (Overview -- deterministic, read-only) ════════
// Reads the existing GET /morning-brief contract (engines/morning_brief.py
// build_compact_brief()) -- fully deterministic, local-JSON-only, no
// Claude/provider call, no external network request. Fetched once at
// boot only (no polling interval): the brief is a once-per-day artifact,
// and a single read is the minimal frontend behavior this addition needs.
function _mbResetStates() {
  const loadingEl    = document.getElementById('ovMbLoading');
  const emptyEl      = document.getElementById('ovMbEmpty');
  const errorEl      = document.getElementById('ovMbError');
  const staleEl      = document.getElementById('ovMbStale');
  const textEl       = document.getElementById('ovMbText');
  const headEl       = document.getElementById('ovMbHeadline');
  const footEl       = document.getElementById('ovMbFooter');
  const dateLabelEl  = document.getElementById('ovMbDateLabel');
  if (loadingEl)   loadingEl.style.display = 'none';
  if (emptyEl)     emptyEl.style.display = 'none';
  if (errorEl)     { errorEl.style.display = 'none'; errorEl.textContent = ''; }
  if (staleEl)     staleEl.style.display = 'none';
  if (textEl)      { textEl.style.display = 'none'; textEl.innerHTML = ''; }
  if (headEl)      { headEl.style.display = 'none'; headEl.textContent = ''; }
  if (footEl)      { footEl.style.display = 'none'; footEl.innerHTML = ''; }
  if (dateLabelEl) dateLabelEl.textContent = '—';
}

// Splits the engine's plain brief_text into paragraphs for proportional
// rendering. Blank-line separated blocks become <p>; a block whose lines all
// start with a bullet marker becomes a <ul>. Single newlines inside a
// paragraph are soft-wrapped rather than preserved, because brief_text is
// hard-wrapped prose, not preformatted layout.
// Display-only de-duplication of the brief body.
//
// build_compact_brief() assembles brief_text from five labelled lines
// (THESIS / DRAW / PARTICIPATION / MACRO / WATCH) whose values it ALSO
// returns as separate structured fields. Overview renders `thesis` as the
// headline and `liquidity_draw` / `key_question` / `confidence` as the facts
// footer, so three of those five lines restate, verbatim, something already
// on screen inches away.
//
// This drops a body line only when its value is genuinely already rendered,
// compared after whitespace normalisation. The THESIS line additionally
// carries the thesis STATE ("CONTESTED [MEDIUM] -- <thesis>"), which appears
// nowhere else, so the duplicated sentence is cut out of it and the state is
// kept rather than dropping the whole line. Nothing is reworded or invented,
// and PARTICIPATION / MACRO -- the lines with no duplicate -- always survive.
function _mbDedupeBody(text, headline, shown) {
  if (!text) return '';
  const norm = (s) => String(s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const headNorm = norm(headline);
  const shownSet = new Set((shown || []).map(norm).filter(Boolean));

  // Collapse runs of whitespace and shave connective punctuation left dangling
  // at either end once something has been cut out of the middle of a line.
  const tidy = (s) => String(s)
    .replace(/\\s+/g, ' ')
    .replace(/(^[\\s\\-–—:;,.]+)|([\\s\\-–—:;,.]+$)/g, '')
    .trim();

  // build_compact_brief() stamps the confidence grade into the THESIS line as
  // a bracketed token ("CONTESTED [MEDIUM] -- ...") AND returns it as the
  // `confidence` field, which Overview renders in the facts footer inches
  // away ("Confidence Medium"). Drop the bracketed copy when -- and only when
  // -- that exact value is already on screen in the footer. Square brackets
  // only: parenthesised groups ("(RVOL 0.32x)") carry measurement context
  // that appears nowhere else and must survive untouched.
  const stripShownTokens = (s) => String(s).replace(/\\[([^\\]]+)\\]/g,
    (whole, inner) => shownSet.has(norm(inner)) ? ' ' : whole);

  // tidy() is applied ONLY when a token was actually removed. Running it
  // unconditionally would shave the trailing period off any engine line that
  // simply ends in one, silently editing prose this function is supposed to
  // pass through untouched.
  const dropShownTokens = (s) => {
    const stripped = stripShownTokens(s);
    return stripped === s ? s : tidy(stripped);
  };

  const kept = text.split('\\n').map(rawLine => {
    const line = rawLine.replace(/\\s+$/, '');
    if (!line.trim()) return '';

    const m = line.match(/^([A-Z][A-Z0-9]{2,})\\s+(.+)$/);
    const label = m ? m[1] : null;
    const value = m ? m[2] : line;
    const valNorm = norm(value);
    if (!valNorm) return '';

    // Already rendered verbatim as the headline or as a facts-footer value.
    if (valNorm === headNorm || shownSet.has(valNorm)) return '';

    // Contains the headline sentence plus additional context: cut the
    // duplicate out and keep whatever genuinely-new text remains.
    if (headNorm && valNorm.indexOf(headNorm) !== -1) {
      const idx = valNorm.indexOf(headNorm);
      const remainder = tidy(value.slice(0, idx) + ' ' + value.slice(idx + headline.trim().length));
      const trimmed = dropShownTokens(remainder);
      if (!trimmed) return '';
      if (shownSet.has(norm(trimmed))) return '';
      return label ? label + ' ' + trimmed : trimmed;
    }

    // No headline overlap, but the line may still carry a bracketed token
    // whose value the facts footer is already showing.
    const cleaned = dropShownTokens(value);
    if (!cleaned || shownSet.has(norm(cleaned))) return '';
    if (cleaned !== value) return label ? label + ' ' + cleaned : cleaned;
    return line;
  }).filter(Boolean);

  // Blank-line separated, so _mbRenderBody() gives each surviving line its own
  // paragraph. Joined by a single newline they would soft-wrap into one run-on
  // block and read as a single garbled phrase ("CONTESTED [MEDIUM]
  // PARTICIPATION WEAK ..."), which is not how the approved brief reads.
  return kept.join('\\n\\n');
}

// build_compact_brief() emits its body as labelled lines -- "THESIS <value>",
// "PARTICIPATION <value>", "MACRO <value>". Those prefixes are structured
// engine output, not prose, so they are parsed into a real description list:
// the label becomes a <dt> (a genuine label, semantically and visually) and
// the value a <dd> that reads as proportional prose.
//
// Display transform is confined to the LABEL -- "PARTICIPATION" renders
// "Participation". The VALUE is emitted byte-for-byte as the engine produced
// it: nothing is reworded, reordered, summarised or invented, and a line the
// engine did not label still renders as a plain paragraph.
const _MB_SECTION = /^([A-Z][A-Z0-9]{2,})\\s+(\\S.*)$/;

function _mbRenderBody(text) {
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const out = [];
  let rows = [];
  const flushRows = () => {
    if (!rows.length) return;
    out.push('<dl class="ov-mb-sections">' + rows.join('') + '</dl>');
    rows = [];
  };

  text.split(/\\n\\s*\\n/).forEach(block => {
    const lines = block.split('\\n').map(l => l.trim()).filter(Boolean);
    if (!lines.length) return;

    const bullety = lines.every(l => /^[-•*·]\\s+/.test(l));
    if (bullety) {
      flushRows();
      out.push('<ul class="ov-mb-list">' +
        lines.map(l => `<li>${esc(l.replace(/^[-•*·]\\s+/, ''))}</li>`).join('') + '</ul>');
      return;
    }

    const joined = lines.join(' ');
    const m = joined.match(_MB_SECTION);
    if (m) {
      const label = m[1].charAt(0) + m[1].slice(1).toLowerCase();
      rows.push(`<dt>${esc(label)}</dt><dd>${esc(m[2])}</dd>`);
      return;
    }

    flushRows();
    out.push(`<p>${esc(joined)}</p>`);
  });

  flushRows();
  return out.join('');
}

function _mbShowError(msg) {
  _mbResetStates();
  const errorEl = document.getElementById('ovMbError');
  if (errorEl) { errorEl.textContent = msg || 'Morning brief unavailable.'; errorEl.style.display = 'block'; }
}

async function refreshMorningBrief() {
  let res;
  try {
    res = await fetch('/morning-brief');
  } catch (e) {
    console.error('refreshMorningBrief:', e);
    _mbShowError('Morning brief unavailable.');
    return;
  }

  let data;
  try {
    data = await res.json();
  } catch (e) {
    console.error('refreshMorningBrief (parse):', e);
    _mbShowError('Morning brief unavailable.');
    return;
  }

  if (!res.ok) {
    _mbShowError((data && data.brief_text) || 'Morning brief unavailable.');
    return;
  }
  if (data.error) {
    _mbShowError(data.brief_text || 'Morning brief unavailable.');
    return;
  }
  if (!data.brief_text) {
    _mbResetStates();
    const emptyEl = document.getElementById('ovMbEmpty');
    if (emptyEl) emptyEl.style.display = 'block';
    return;
  }

  _mbResetStates();
  setText('ovMbDateLabel', data.date_label || '—');
  // NY calendar-date string via Intl formatting -- no Date-reparsing of a
  // locale string (which can be timezone-ambiguous), just a direct
  // timezone-aware format of the current instant into "YYYY-MM-DD".
  const todayNyStr = nyTodayDateStr();
  const staleEl = document.getElementById('ovMbStale');
  if (staleEl) staleEl.style.display = (data.date && data.date !== todayNyStr) ? 'block' : 'none';

  // ── Headline ──
  // build_compact_brief() emits a real `thesis` field -- that IS the brief's
  // headline, so it is used verbatim when present. With no thesis, the first
  // meaningful line of brief_text is promoted deterministically, but only
  // when it is structurally headline-shaped (a single short sentence
  // followed by more content). Nothing is ever invented or rewritten.
  let body = data.brief_text;
  let headline = (data.thesis || '').trim();
  if (!headline) {
    const blocks = body.split(/\\n\\s*\\n/);
    const first = (blocks[0] || '').split('\\n').map(l => l.trim()).filter(Boolean).join(' ');
    if (blocks.length > 1 && first && first.length <= 160 && (first.match(/\\./g) || []).length <= 1) {
      headline = first;
      body = blocks.slice(1).join('\\n\\n');
    }
  }
  const headEl = document.getElementById('ovMbHeadline');
  if (headEl && headline) { headEl.textContent = headline; headEl.style.display = 'block'; }

  // ── Footer ──
  // Built ONLY from fields build_compact_brief() genuinely returns
  // (liquidity_draw, key_question, confidence). Any field the engine omits
  // is simply absent -- no placeholder, no invented "next event".
  // Computed BEFORE the body renders, because the body is de-duplicated
  // against whatever the footer is about to show.
  const bits = [];
  if (data.liquidity_draw) bits.push(['Draw', data.liquidity_draw]);
  if (data.key_question)   bits.push(['Watch', data.key_question]);
  if (data.confidence)     bits.push(['Confidence', humanizeCode(data.confidence)]);

  const textEl = document.getElementById('ovMbText');
  if (textEl) {
    const deduped = _mbDedupeBody(body, headline, bits.map(b => b[1]));
    if (deduped) {
      textEl.innerHTML = _mbRenderBody(deduped);
      textEl.style.display = 'block';
    } else {
      // Everything the body carried is already on screen as the headline and
      // the facts footer. Collapse it rather than render an empty block.
      textEl.innerHTML = '';
      textEl.style.display = 'none';
    }
  }

  const footEl = document.getElementById('ovMbFooter');
  if (footEl && bits.length) {
    footEl.innerHTML = bits.map(([k, v]) =>
      `<span class="ov-mb-fact"><b>${k}</b> ${String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;')}</span>`).join('');
    footEl.style.display = '';
  }
}

// ════════ OVERVIEW: SESSION STRUCTURE (Overview hero, right pane) ════════
// Reads the existing GET /market-structure (engines/market_structure.py) and
// GET /liquidity (engines/liquidity.py) contracts -- both already active,
// already polled elsewhere in the app; Overview did not consume them
// before this addition. Deterministic, local-JSON-only, no Claude/provider
// call, no external network request beyond the two same-origin GETs.
// Refreshed on the existing shared 30s dashboard cycle (called from
// refresh(); no new setInterval registration). Both routes are pure reads
// of engine-written JSON files, so the cadence costs no provider traffic --
// and unlike a single boot-time fetch, it guarantees the level ladder,
// swept/untapped classifications and primary draw keep tracking the engine
// instead of freezing for the browser's entire lifetime.
let _lastMarketStructure = null;
let _lastLiquidity = null;
let _structureFetchFailed = false;

// ── Markets page state ───────────────────────────────────────────────────
// Every value the Markets page draws comes from one of these, and each one
// records whether its own fetch succeeded. A region that could not be fetched
// says so rather than leaving the previous cycle's number on screen.
let _mkQuotes = null;          // merged, de-duplicated instrument rows
let _mkQuotesFailed = false;
let _mkQuotesAt = null;        // when the merge last succeeded
let _mkIndexRows = null;       // /major-indexes rows, for equity-index direction
let _mkSym = 'NQ';             // Market Structure instrument
const _MK_GROUPS = {
  NQ: 'Futures', ES: 'Futures',
  NASDAQ: 'Index', 'S&P 500': 'Index', SPX: 'Index', DJIA: 'Index', RUSSELL: 'Index',
  VIX: 'Volatility', US10Y: 'Rates', DXY: 'FX',
  GOLD: 'Commodity', SILVER: 'Commodity', OIL: 'Commodity', BTC: 'Crypto',
};
// The three equity indexes. Direction is counted across these alone -- folding
// VIX, DXY or rates into an "advancing" tally would make the number a lie.
const _MK_EQUITY = ['NASDAQ', 'S&P 500', 'DJIA'];


// ── Authoritative freshness ──────────────────────────────────────────────
// A 200 response only proves the SERVER answered; it says nothing about how
// old the DATA inside that response is. Every label below is therefore
// derived from a timestamp emitted by the producing engine, or from an
// explicit cache flag -- never from the fact that a fetch resolved.
//
// The age thresholds mirror health/health.py::_check_market_data() exactly
// (<15 min fresh / 15-30 aging / >30 stale) so the Overview and the system
// health page can never disagree about whether the same feed is current.
const _OV_FRESH_LABEL = {
  loading:     'Checking…',
  live:        'Live',
  cached:      'Cached',
  delayed:     'Delayed',
  stale:       'Stale',
  nofresh:     'Freshness unavailable',
  failure:     'Connection failed',
  unavailable: 'Unavailable',
};

// Severity order, used to collapse several sources into one honest
// board-level state: a board may never look fresher than its least-current
// source. 'nofresh' outranks 'stale' because a source whose age cannot be
// determined at all cannot be certified as merely-stale either.
const _OV_FRESH_RANK = {
  loading: -1, live: 0, cached: 1, delayed: 2, stale: 3,
  nofresh: 4, failure: 5, unavailable: 6,
};

function _ovAgeMinutes(iso) {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (isNaN(t)) return null;
  return (Date.now() - t) / 60000;
}

// Age -> state using the health.py ladder. A missing or unparseable
// timestamp yields 'nofresh' ("Freshness unavailable"), never 'live'.
function _ovAgeState(iso) {
  const age = _ovAgeMinutes(iso);
  if (age === null) return 'nofresh';
  if (age < 15) return 'live';
  if (age < 30) return 'delayed';
  return 'stale';
}

function _ovWorstFreshness(states) {
  let worst = 'live';
  (states || []).forEach(s => {
    const r = _OV_FRESH_RANK[s];
    if (r !== undefined && r > (_OV_FRESH_RANK[worst] ?? 0)) worst = s;
  });
  return worst;
}

function _ovSetFreshness(elId, state, detail) {
  const el = document.getElementById(elId);
  if (!el) return;
  Object.keys(_OV_FRESH_LABEL).forEach(s => el.classList.remove(s));
  el.classList.add(state);
  const label = _OV_FRESH_LABEL[state] || _OV_FRESH_LABEL.unavailable;
  // The label itself is the state -- colour is decoration only, never the
  // sole carrier of meaning.
  setHtml(elId, `<span class="fd"></span>${label}`);
  el.setAttribute('title', detail || label);
  el.setAttribute('aria-label', `Data freshness: ${label}${detail ? ' — ' + detail : ''}`);
}

// ── Connection state (sidebar footer + Overview page identity) ───────────
// This reports exactly one thing that NOVA can honestly establish from the
// browser: whether the last /dashboard-data cycle reached the backend. It is
// deliberately NOT phrased as "All systems normal" -- the frontend has no
// basis for a whole-system health claim, and the mockup's wording would have
// been a hard-coded assertion. Before the first cycle resolves it stays
// "Connecting…", never a green all-clear.
const _OV_CONN = {
  connecting: {text: 'Connecting…',      cls: 'connecting'},
  online:     {text: 'Connected',        cls: 'online'},
  offline:    {text: 'Connection failed', cls: 'offline'},
};
function _ovSetConnection(state) {
  const s = _OV_CONN[state] || _OV_CONN.connecting;
  // Journal carries the same genuine connection state in its identity row.
  ['sidebarStatus', 'ovIdentityStatus', 'jnIdentityStatus'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('connecting', 'online', 'offline');
    el.classList.add(s.cls);
    const dot = el.querySelector('.d');
    el.textContent = s.text;
    if (dot) el.prepend(dot);
    el.setAttribute('title', `Backend connection: ${s.text}`);
  });
}

function _ovStructureFreshnessState(ms) {
  // `last_updated` records when engines/market_structure.py last COMPUTED
  // this state file -- but the structural levels inside it come from a
  // SEPARATE in-memory yfinance cache with a 30-minute TTL, and
  // `levels_cached: true` means this response reused those cached levels
  // instead of re-fetching them. A freshly-computed response carrying
  // cached levels is therefore not live: the levels may be up to the full
  // cache TTL old. Honour the flag explicitly so a recently-requested
  // cached level set can never be labelled "Live".
  if (!ms) return 'unavailable';
  const ageState = _ovAgeState(ms.last_updated);
  if (ageState === 'nofresh') return 'nofresh';
  if (ms.levels_cached === true) return _ovWorstFreshness(['cached', ageState]);
  return ageState;
}

async function refreshMarketStructure() {
  try {
    const [ms, liq] = await Promise.all([
      fetch('/market-structure').then(r => r.json()),
      fetch('/liquidity').then(r => r.json()),
    ]);
    _lastMarketStructure = ms || {};
    _lastLiquidity = liq || {};
    _structureFetchFailed = false;
  } catch (e) {
    console.error('refreshMarketStructure:', e);
    // Keep the last good payload on screen rather than blanking it, but
    // record that this cycle failed so the freshness chip says so.
    _structureFetchFailed = true;
  }
  renderSessionStructure();
  renderMarkets();
}

function renderSessionStructure() {
  const ms  = _lastMarketStructure;
  const liq = _lastLiquidity;
  const ladderEl = document.getElementById('ovLadder');

  if (!ms || ms.error || !liq || liq.error || !(ms.nq && Object.keys(ms.nq).length)) {
    _ovSetFreshness('ovStructFresh', _structureFetchFailed ? 'failure' : 'unavailable');
    setText('ovStructPx', '—');
    setText('ovStructChg', '');
    if (ladderEl) {
      setHtml('ovLadder', `<div style="font-size:13px;color:var(--muted2);padding-top:8px">${
        _structureFetchFailed ? 'Could not reach the session-structure engine.' : 'Session structure unavailable.'}</div>`);
    }
    return;
  }

  // A failed cycle means what is on screen came from an EARLIER cycle, so it
  // can never be labelled better than 'failure' regardless of the payload's
  // own timestamp.
  _ovSetFreshness(
    'ovStructFresh',
    _structureFetchFailed ? 'failure' : _ovStructureFreshnessState(ms),
    ms.levels_cached === true ? 'Structural levels served from the engine cache (up to 30 min old)' : null,
  );

  // Current price: reuse the already-fetched live dashboard snapshot (same
  // helper the Market Board tiles use) so this never re-derives its own
  // price formatting; fall back to the structure engine's own snapshot
  // only if the live dashboard price isn't available yet.
  const liveNq = getSymbolData('NQ', _lastDashData || {});
  const nqLevelsSrc = (liq.nq || {});
  const enginePrice = parseFloat(nqLevelsSrc.price) || parseFloat((ms.nq || {}).current_price) || null;
  const havePriceStr = liveNq && liveNq.val && liveNq.val !== '—';
  const price = havePriceStr ? parseFloat(String(liveNq.val).replace(/,/g, '')) : enginePrice;

  setText('ovStructPx', havePriceStr ? liveNq.val : (price ? price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '—'));
  const chgEl = document.getElementById('ovStructChg');
  if (chgEl) {
    chgEl.textContent = havePriceStr ? (liveNq.pct || '') : '';
    chgEl.style.color = havePriceStr && liveNq.dir === 'up' ? 'var(--green)' : havePriceStr && liveNq.dir === 'down' ? 'var(--red)' : 'var(--muted)';
  }

  // Levels + their UNTAPPED/SWEPT classification and primary_draw selection
  // all come directly from engines/liquidity.py -- reused as-is, not
  // re-derived here.
  const levels = nqLevelsSrc.levels || [];
  if (!levels.length || !price) {
    if (ladderEl) setHtml('ovLadder', '<div style="font-size:13px;color:var(--muted2);padding-top:8px">No structural levels available yet.</div>');
    return;
  }
  const draw = nqLevelsSrc.primary_draw || null;
  const fmtPx = (v) => v.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});

  // Row placement is by PRICE ORDER (rank), not physically proportional to
  // the price gap between levels. Real intraday levels frequently cluster
  // within a few points of each other (e.g. current price sitting almost
  // exactly on an overnight high) -- a proportional layout would stack
  // those rows on top of each other and render overlapping, unreadable
  // text. Evenly-spaced rank order keeps every row legible while still
  // preserving the correct high-to-low reading order.
  // Display formatting only (not a data change): engines/liquidity.py emits
  // raw keys like 'monthly_open' alongside already-terse codes like 'PDH' --
  // normalize to the same underscore-free, uppercase presentation so every
  // row's label reads consistently regardless of the source key's length.
  const _fmtLevelLabel = (raw) => (raw || '').replace(/_/g, ' ').toUpperCase();
  const merged = levels.map(l => ({
    label: _fmtLevelLabel(l.label), price: l.price, isNow: false,
    isDraw: !!(draw && draw.label === l.label && draw.price === l.price),
    status: l.status,
  }));
  merged.push({label: 'NOW', price: price, isNow: true, isDraw: false, status: ''});
  merged.sort((a, b) => b.price - a.price);

  const PAD = 6;
  const n = merged.length;
  const step = n > 1 ? (100 - 2 * PAD) / (n - 1) : 0;

  let html = '';
  merged.forEach((row, i) => {
    const top = (PAD + i * step).toFixed(1);
    if (row.isNow) {
      html += `<div class="ov-lvl now" style="top:${top}%">` +
              `<span class="tick"></span><span class="nm">NOW</span>` +
              `<span class="pr">${fmtPx(row.price)}</span><span class="st"></span></div>`;
      return;
    }
    const cls = row.isDraw ? 'draw' : (row.status === 'SWEPT' ? 'swept' : 'untapped');
    const statusLabel = row.isDraw ? 'Draw · Untapped' : (row.status === 'SWEPT' ? 'Swept' : 'Untapped');
    html += `<div class="ov-lvl ${cls}" style="top:${top}%">` +
            `<span class="tick"></span><span class="nm">${row.label}</span>` +
            `<span class="pr">${fmtPx(row.price)}</span><span class="st">${statusLabel}</span></div>`;
  });
  if (ladderEl) setHtml('ovLadder', html);
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
    // Markets consumes the same three routes, merged and de-duplicated.
    _mkQuotes = _mkMergeQuotes(pulseRes.rows, idxRes.rows, bvRes);
    _mkIndexRows = idxRes.rows || [];
    _mkQuotesFailed = false;
    _mkQuotesAt = new Date().toISOString();
    renderMarkets();
  } catch(e) {
    console.error('refreshNewsFuturesStrip:', e);
    // Keep whatever was last good on screen, but mark it cached so it can
    // never be read as the current market.
    _mkQuotesFailed = true;
    renderMarkets();
  }
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
  renderMarkets();

  // Feature story — top macro headline
  const featureText = risk.last_headline || news[0]?.headline || '—';
  const featureNote = risk.headline_guidance || risk.last_market_guidance || '—';
  const featureTag = classifyHeadlineTag(featureText);
  const ftEl = document.getElementById('featureStoryTag');
  if (ftEl) { ftEl.textContent = featureTag; ftEl.className = 'story-tag ' + featureTag; }
  setText('featureHeadline', featureText);
  setText('featureNote', featureNote);

  // Live feed — rich, restrained accents: conflict red, market wine, macro
  // amber, energy gold and calendar gray. No blue identity treatment.
  const tagStyle = {
    GEOPOLITICAL: 'background:var(--red2);color:var(--red);border:1px solid rgba(192,57,43,.2)',
    MARKET:       'background:rgba(143,33,59,.08);color:var(--wine-text);border:1px solid rgba(143,33,59,.24)',
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
}

// ════════ SHARED FORMATTERS (used by Journal + Alerts) ════════
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
// ════════ MAIN REFRESH ════════
async function refresh() {
  try {
    const res = await fetch('/dashboard-data');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const d = await res.json();
    _lastDashData = d;
    try { renderDashboard(); } catch(e) { console.error('renderDashboard failed:', e); }
    try { renderNews(d); } catch(e) { console.error('renderNews failed:', e); }
    // renderDashboard() sets the Market Board freshness chip from the
    // producer timestamps inside `d` -- deliberately NOT set here, because
    // reaching this line only proves the request succeeded.
    _ovSetConnection('online');
  } catch(err) {
    console.error('NOVA refresh error:', err);
    setText('lastUpdated', 'Sync error — retrying...');
    // Whatever is on screen came from an earlier cycle; say so.
    _ovSetFreshness('ovBoardFresh', 'failure', 'Last /dashboard-data request failed');
    _ovSetConnection('offline');
  }
  // Session structure rides the same shared 30s cycle as the rest of the
  // dashboard. Both GET /market-structure and GET /liquidity are pure reads
  // of engine-written JSON files (engines/market_structure.py
  // load_market_structure(), engines/liquidity.py load_liquidity() -- both
  // documented "No network calls"), so this adds zero provider traffic while
  // guaranteeing swept/untapped state, primary draw and the level ladder
  // cannot sit frozen for the browser's entire lifetime. No new setInterval
  // is registered: this reuses the existing refresh() registration.
  try { await refreshMarketStructure(); } catch(e) { console.error('refreshMarketStructure failed:', e); }
}

// ════════ SETTINGS ════════
// The page this replaces had one button and no settings. Three defects are
// corrected here, and each is load-bearing:
//
//  1. "CONNECTED" was bool() of an environment string -- no reachability,
//     validity or credit check. Discord read CONNECTED with no credential at
//     all, because that field is a module-import flag. Rows now say
//     Configured / Not configured, which is the only thing /check-env proves.
//  2. A failed read left the previous values on screen. refreshSettings()
//     caught, logged to console, and touched nothing, so a reader could not
//     tell the data was stale. Failure now withholds values and says so.
//  3. Nothing was saveable. The one genuine preference (Overview tiles) is
//     exposed here, and "Saved" is shown only after the stored value is read
//     back and matches.

const ST_SYMBOLS = SYMBOL_LIST;          // the existing 13-instrument contract
const ST_REQUIRED_TILES = 5;             // Overview renders exactly five

let _stEnv = null, _stHealth = null;
let _stTiles = null;                     // working selection
let _stSavedTiles = null;                // last value read back from storage
let _stBusy = false;                     // guards double submission

function _stEl(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}
function _stSetState(state) {
  const p = document.getElementById('page-settings');
  if (p) p.dataset.stState = state;
}
function _stRow(label, value, valueCls, sub) {
  const row = _stEl('div', 'st-row');
  const k = _stEl('span', 'st-rk');
  k.appendChild(document.createTextNode(label));
  if (sub) k.appendChild(_stEl('span', 'st-rsub', sub));
  row.appendChild(k);
  row.appendChild(_stEl('span', 'st-rv' + (valueCls ? ' ' + valueCls : ''), value));
  return row;
}

// ── Overview tiles: the one genuinely savable preference ─────────────────
function _stRenderTiles() {
  const host = document.getElementById('setTiles');
  if (!host) return;
  host.textContent = '';
  ST_SYMBOLS.forEach(sym => {
    const on = _stTiles.indexOf(sym) >= 0;
    const b = _stEl('button', 'st-tile', sym);
    b.type = 'button';
    b.setAttribute('aria-pressed', String(on));
    b.addEventListener('click', () => {
      const i = _stTiles.indexOf(sym);
      if (i >= 0) _stTiles.splice(i, 1); else _stTiles.push(sym);
      _stRenderTiles();
      _stSyncSaveBar();
    });
    host.appendChild(b);
  });
}

function _stTilesDiffer() {
  if (!_stSavedTiles || !_stTiles) return false;
  if (_stTiles.length !== _stSavedTiles.length) return true;
  return _stTiles.some((s, i) => s !== _stSavedTiles[i]);
}

function _stSetMsg(cls, text, spinner) {
  const m = document.getElementById('setSaveMsg');
  if (!m) return;
  m.className = 'st-savemsg ' + cls;
  m.textContent = '';
  if (spinner) m.appendChild(_stEl('span', 'st-sp'));
  m.appendChild(document.createTextNode(text));
}

function _stSyncSaveBar() {
  const count = document.getElementById('setTileCount');
  const err = document.getElementById('setTileErr');
  const save = document.getElementById('setSaveTiles');
  const discard = document.getElementById('setDiscardTiles');
  const note = document.getElementById('setSaveNote');
  if (!count || !save) return;

  const n = _stTiles.length;
  const valid = n === ST_REQUIRED_TILES;
  const dirty = _stTilesDiffer();

  count.textContent = n + ' of ' + ST_REQUIRED_TILES + ' selected';
  count.className = 'st-count' + (valid ? '' : ' bad');
  err.hidden = valid;
  if (!valid) {
    err.textContent = n > ST_REQUIRED_TILES
      ? 'Overview shows exactly five tiles. Deselect ' + (n - ST_REQUIRED_TILES) + ' before saving.'
      : 'Overview shows exactly five tiles. Select ' + (ST_REQUIRED_TILES - n) + ' more before saving.';
  }
  if (discard) discard.hidden = !dirty;
  save.disabled = _stBusy || !dirty || !valid;
  if (_stBusy) { save.setAttribute('aria-describedby', ''); save.removeAttribute('aria-describedby'); }
  if (!valid) save.setAttribute('aria-describedby', 'setTileErr');
  else save.removeAttribute('aria-describedby');

  if (_stBusy) return;                       // the saving message stands
  if (note && dirty) note.hidden = true;
  if (!valid) _stSetMsg('err', 'Cannot save — fix the error above');
  else if (dirty) _stSetMsg('dirty', 'Unsaved changes');
  else _stSetMsg('idle', 'No unsaved changes');
}

async function _stSaveTiles() {
  if (_stBusy) return;
  if (_stTiles.length !== ST_REQUIRED_TILES) { _stSyncSaveBar(); return; }
  _stBusy = true;
  document.getElementById('setSaveTiles').disabled = true;
  document.getElementById('setSaveTiles').textContent = 'Saving…';
  _stSetMsg('saving', 'Writing to this browser', true);

  // Yield once so the saving state actually paints. Without it the write and
  // read-back run synchronously after the message is set, so the browser goes
  // straight from 'unsaved' to 'saved' and the in-flight state, though set, is
  // never observable.
  await new Promise(r => requestAnimationFrame(() => r()));

  const intended = _stTiles.slice();
  let ok = false, failure = '';
  try {
    saveIndexPrefs(intended);              // the existing storage contract
    // Read back before claiming success: a write that silently failed (quota,
    // private mode, a disabled store) must never be reported as saved.
    const stored = loadIndexPrefs();
    ok = Array.isArray(stored) && stored.length === intended.length &&
         stored.every((s, i) => s === intended[i]);
    if (!ok) failure = 'the browser did not store the value';
  } catch (e) {
    ok = false;
    failure = 'this browser refused to store it';
  }

  _stBusy = false;
  const save = document.getElementById('setSaveTiles');
  save.textContent = 'Save preferences';
  const note = document.getElementById('setSaveNote');
  if (ok) {
    _stSavedTiles = intended.slice();
    if (note) note.hidden = false;
    _stSyncSaveBar();
    _stSetMsg('ok', 'Saved — read back and confirmed');
    if (typeof renderIndexTiles === 'function' && _lastDashData) {
      try { renderIndexTiles(_lastDashData); } catch (e) {}
    }
  } else {
    if (note) note.hidden = true;
    _stSyncSaveBar();
    _stSetMsg('err', 'Not saved — ' + failure);
  }
}

// ── working memory: real GET /assistant-data, real clear routes ──────────
function _stRenderWorkingMemory(d) {
  const host = document.getElementById('setWmRows');
  if (!host) return;
  host.textContent = '';
  host.appendChild(_stRow('Daily focus', d.daily_focus ? 'set' : 'not set',
                          d.daily_focus ? '' : 'off'));
  host.appendChild(_stRow('Tasks', String((d.tasks || []).length)));
  host.appendChild(_stRow('Reminders', String((d.reminders || []).length)));
  host.appendChild(_stRow('Last written', _stAge(d.last_updated) || '—'));

  const t = document.getElementById('setClearTasks');
  const r = document.getElementById('setClearReminders');
  if (t) t.disabled = !(d.tasks || []).length;
  if (r) r.disabled = !(d.reminders || []).length;
}

function _stAge(ts) {
  if (!ts) return null;
  const s = String(ts);
  const tail = s.length > 11 ? s.slice(11) : '';
  const hasTz = s.endsWith('Z') || tail.indexOf('+') >= 0 || tail.lastIndexOf('-') > 0;
  const t = Date.parse(hasTz ? s : s + 'Z');
  if (!isFinite(t)) return null;
  const m = Math.floor((Date.now() - t) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return m + 'm ago';
  const h = Math.floor(m / 60);
  if (h < 24) return h + 'h ago';
  return Math.floor(h / 24) + 'd ago';
}

function _stCloseConfirm() {
  const host = document.getElementById('setConfirm');
  if (host) host.textContent = '';
}

// Explicit confirmation, stated in terms of what will actually happen.
function _stConfirmClear(kind, count) {
  const host = document.getElementById('setConfirm');
  if (!host) return;
  const route = kind === 'tasks' ? '/assistant/clear-tasks' : '/assistant/clear-reminders';
  const other = kind === 'tasks' ? 'Reminders and the daily focus are not affected.'
                                 : 'Tasks and the daily focus are not affected.';
  host.textContent = '';
  const box = _stEl('div', 'st-confirm');
  box.setAttribute('role', 'alertdialog');
  box.setAttribute('aria-labelledby', 'setConfirmTitle');
  box.setAttribute('aria-describedby', 'setConfirmBody');
  const h = _stEl('h3', null, 'Clear all ' + count + ' ' + kind + '?');
  h.id = 'setConfirmTitle';
  box.appendChild(h);
  const p = _stEl('p');
  p.id = 'setConfirmBody';
  p.appendChild(document.createTextNode('This calls POST ' + route +
    ' and deletes every ' + kind.replace(/s$/, '') + ' from the server immediately. '));
  p.appendChild(_stEl('b', null, 'There is no undo and no backup.'));
  p.appendChild(document.createTextNode(' ' + other));
  box.appendChild(p);
  const btns = _stEl('div', 'st-cbtns');
  const yes = _stEl('button', 'st-btn danger', 'Yes, delete ' + count + ' ' + kind);
  yes.type = 'button';
  const no = _stEl('button', 'st-btn', 'Cancel');
  no.type = 'button';
  no.addEventListener('click', _stCloseConfirm);
  yes.addEventListener('click', () => _stDoClear(kind, route, yes, no));
  btns.appendChild(yes);
  btns.appendChild(no);
  box.appendChild(btns);
  host.appendChild(box);
  yes.focus();
}

async function _stDoClear(kind, route, yesBtn, noBtn) {
  if (_stBusy) return;                       // no double submission
  _stBusy = true;
  yesBtn.disabled = true;
  noBtn.disabled = true;
  yesBtn.textContent = 'Deleting…';
  try {
    const res = await fetch(route, { method: 'POST' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    await res.json();
    _stCloseConfirm();
    _stBusy = false;
    // State is refreshed only after a confirmed success.
    await _stLoadWorkingMemory();
  } catch (e) {
    _stBusy = false;
    yesBtn.disabled = false;
    noBtn.disabled = false;
    yesBtn.textContent = 'Retry delete';
    const host = document.getElementById('setConfirm');
    const box = host && host.firstChild;
    if (box && !box.querySelector('.st-cerr')) {
      const err = _stEl('p', 'st-cerr');
      err.setAttribute('role', 'alert');
      err.style.color = '#ff9d9d';
      err.style.margin = '9px 0 0';
      err.style.fontSize = '12.5px';
      err.textContent = 'Nothing was deleted — the request failed (' + e.message + ').';
      box.appendChild(err);
    }
  }
}

async function _stLoadWorkingMemory() {
  try {
    const res = await fetch('/assistant-data');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    _stRenderWorkingMemory(await res.json());
    return true;
  } catch (e) {
    return false;
  }
}

// ── integrations + system ────────────────────────────────────────────────
// "Configured" is the strongest claim /check-env supports: it returns
// bool(<env var>). Connected, reachable, valid, funded and healthy are NOT
// proven by any current backend contract and are never asserted here.
const ST_INTEGRATIONS = [
  ['Anthropic (Claude)',    'ANTHROPIC_API_KEY',     'anthropic_key_found'],
  ['Finnhub',               'FINNHUB_API_KEY',       'finnhub_found'],
  ['FMP',                   'FMP_API_KEY',           'fmp_found'],
  ['Telegram',              'TELEGRAM_BOT_TOKEN',    'telegram_found'],
  ['Alpha Vantage',         'ALPHA_VANTAGE_API_KEY', 'alpha_vantage_found'],
  ['Discord macro channel', 'DISCORD_CHANNEL_MACRO', 'discord_macro_channel_set']
];

function _stRenderIntegrations(env) {
  const host = document.getElementById('setIntegrations');
  if (!host) return;
  host.textContent = '';
  let configured = 0;
  ST_INTEGRATIONS.forEach(([label, varName, key]) => {
    const on = !!env[key];
    if (on) configured++;
    host.appendChild(_stRow(label, on ? 'Configured' : 'Not configured',
                            on ? 'on' : 'off', varName));
  });
  setText('setCountEnv', String(ST_INTEGRATIONS.length));
  setText('setCountEnvSub', configured + ' configured · ' + (ST_INTEGRATIONS.length - configured) + ' not set');
}

function _stRenderSystem(env, health) {
  const host = document.getElementById('setSystemRows');
  if (!host) return;
  const files = ['risk_file_exists', 'alerts_file_exists', 'assistant_file_exists',
                 'settings_file_exists', 'macro_events_file_exists'];
  const present = files.filter(k => env[k]).length;
  host.textContent = '';
  host.appendChild(_stRow('Reasoning model', env.chat_model || '—', '', 'ANTHROPIC_ASSISTANT_MODEL'));
  host.appendChild(_stRow('Fast model', env.fast_model || '—', '', 'ANTHROPIC_MODEL'));
  host.appendChild(_stRow('Server time',
    health.last_time_ny ? health.last_time_ny.substring(0, 19).replace('T', ' ') : '—',
    '', 'America/New_York'));
  host.appendChild(_stRow('Macro calendar source', health.forex_factory_macro_layer || '—'));
  host.appendChild(_stRow('Cached feeds', (health.cache_keys || []).length + ' keys'));
  host.appendChild(_stRow('State files present', present + ' of ' + files.length,
    present === files.length ? 'on' : 'warn', 'risk, alerts, assistant, settings, macro'));
  // The former standalone callout, folded into the list so the card ends on a
  // row edge rather than an isolated box.
  host.appendChild(_stRow('Configuration changes', 'Deployment restart required', 'warn',
    'models and keys — a running session keeps its own'));
  setText('setCountReadonly', '6');
}

// ── page load ────────────────────────────────────────────────────────────
async function refreshSettings() {
  _stSetState('loading');
  const pill = document.getElementById('setStatusPill');
  if (pill) { pill.className = 'st-fresh busy'; pill.textContent = 'Reading system state'; }

  let env = null, health = null;
  try {
    const [envRes, healthRes] = await Promise.all([fetch('/check-env'), fetch('/system-health')]);
    if (!envRes.ok || !healthRes.ok) throw new Error('HTTP');
    env = await envRes.json();
    health = await healthRes.json();
  } catch (e) {
    // Withhold rather than leave stale values on screen.
    _stSetState('error');
    if (pill) { pill.className = 'st-fresh down'; pill.textContent = 'System unreachable'; }
    return;
  }

  _stEnv = env; _stHealth = health;
  _stSetState('loaded');
  if (pill) { pill.className = 'st-fresh ok'; pill.textContent = 'System reachable'; }

  _stSavedTiles = loadIndexPrefs();
  _stTiles = _stSavedTiles.slice();
  _stRenderTiles();
  _stSyncSaveBar();
  const note = document.getElementById('setSaveNote');
  if (note) note.hidden = true;

  _stRenderIntegrations(env);
  _stRenderSystem(env, health);
  setText('setCountEditable', '2');

  _stCloseConfirm();
  const wmOk = await _stLoadWorkingMemory();
  if (!wmOk) {
    const host = document.getElementById('setWmRows');
    if (host) {
      host.textContent = '';
      host.appendChild(_stRow('Working memory', 'not read', 'off', '/assistant-data did not respond'));
    }
    ['setClearTasks', 'setClearReminders'].forEach(id => {
      const b = document.getElementById(id);
      if (b) b.disabled = true;
    });
  }
}

(function stBindSettings() {
  const save = document.getElementById('setSaveTiles');
  if (save) save.addEventListener('click', _stSaveTiles);
  const discard = document.getElementById('setDiscardTiles');
  if (discard) discard.addEventListener('click', () => {
    if (_stBusy || !_stSavedTiles) return;
    _stTiles = _stSavedTiles.slice();
    _stRenderTiles();
    const note = document.getElementById('setSaveNote');
    if (note) note.hidden = true;
    _stSyncSaveBar();
  });
  const t = document.getElementById('setClearTasks');
  if (t) t.addEventListener('click', async () => {
    if (_stBusy) return;
    const res = await fetch('/assistant-data').then(r => r.ok ? r.json() : null).catch(() => null);
    if (!res) return;
    _stConfirmClear('tasks', (res.tasks || []).length);
  });
  const r = document.getElementById('setClearReminders');
  if (r) r.addEventListener('click', async () => {
    if (_stBusy) return;
    const res = await fetch('/assistant-data').then(x => x.ok ? x.json() : null).catch(() => null);
    if (!res) return;
    _stConfirmClear('reminders', (res.reminders || []).length);
  });
})();

// ════════ NOVA INTELLIGENCE ════════
// Three defects in the previous version are corrected here, and each fix is
// load-bearing rather than cosmetic:
//
//  1. A failure was rendered as an answer. `res.ok` and the response `status`
//     were both unchecked, so "AI features are not configured right now."
//     appeared as a NOVA message stamped ANALYSIS. Every non-answer now
//     renders as a system note, never in NOVA's voice.
//  2. The response tag was invented client-side. inferResponseTag() keyword-
//     matched the reply to produce ANALYSIS / RISK / EXECUTION / CALENDAR --
//     labels the backend never asserted, in a product that cannot execute.
//     It is gone; the only badge is "NOVA inference", which is true of every
//     reply the model returns.
//  3. Message text went through innerHTML. All text is written with
//     textContent now.

const niLog      = document.getElementById('assistantOutput');
const niInput    = document.getElementById('assistantInput');
const niAskBtn   = document.getElementById('assistantSend');
const niIdleNote = document.getElementById('niIdleNote');
const niFresh    = document.getElementById('niContextFresh');
const niSeeSub   = document.getElementById('niSeeSub');
const niSourcesEl= document.getElementById('niSources');
const niMemoryEl = document.getElementById('niMemory');

let _niBusy = false;
let _niSourceState = [];

// Each entry is a context source the assistant prompt is built from, paired
// with the route that actually serves it. Availability and age come from
// these routes -- NOT from /assistant/chat, which reports neither.
const NI_SOURCES = [
  ['Session & risk posture', '/dashboard-data'],
  ['Market reality',         '/market-reality'],
  ['Market structure',       '/market-structure'],
  ['Liquidity',              '/liquidity'],
  ['Participation',          '/participation'],
  ['Cross-market',           '/cross-market'],
  ['Synthesis',              '/synthesis'],
  ['Session memory',         '/session-memory']
];

function niEl(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}

function _niStamp(obj) {
  if (!obj || typeof obj !== 'object') return null;
  const direct = obj.last_updated || obj.updated_at || obj.generated_at || obj.timestamp;
  if (direct) return direct;
  const nests = ['risk', 'data', 'state', 'reality', 'synthesis', 'memory'];
  for (let i = 0; i < nests.length; i++) {
    const v = obj[nests[i]];
    if (v && typeof v === 'object' && v.last_updated) return v.last_updated;
  }
  return null;
}

function _niAge(ts) {
  if (!ts) return null;
  const s = String(ts);
  const tail = s.length > 11 ? s.slice(11) : '';
  const hasTz = s.endsWith('Z') || tail.indexOf('+') >= 0 || tail.lastIndexOf('-') > 0;
  const t = Date.parse(hasTz ? s : s + 'Z');
  if (!isFinite(t)) return null;
  const mins = Math.floor((Date.now() - t) / 60000);
  if (mins < 0) return 'just now';
  if (mins < 1) return 'just now';
  if (mins < 60) return mins + 'm old';
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + 'h old';
  return Math.floor(hrs / 24) + 'd old';
}

// A source is STALE past this age. 6h keeps an intraday read honest without
// flagging an overnight file the moment the session rolls.
const NI_STALE_MINUTES = 360;

function _niClassify(ok, ts) {
  if (!ok) return { cls: 'off', label: 'unavailable' };
  const age = _niAge(ts);
  if (!age) return { cls: 'on', label: 'available' };
  const s = String(ts);
  const tail = s.length > 11 ? s.slice(11) : '';
  const hasTz = s.endsWith('Z') || tail.indexOf('+') >= 0 || tail.lastIndexOf('-') > 0;
  const mins = Math.floor((Date.now() - Date.parse(hasTz ? s : s + 'Z')) / 60000);
  return { cls: mins > NI_STALE_MINUTES ? 'stale' : 'on', label: age };
}

// ── context rail ──────────────────────────────────────────────────────────
async function niRefreshSources() {
  const results = await Promise.all(NI_SOURCES.map(async ([name, route]) => {
    try {
      const res = await fetch(route);
      if (!res.ok) return { name, route, ok: false, ts: null };
      const data = await res.json();
      return { name, route, ok: true, ts: _niStamp(data) };
    } catch (e) {
      return { name, route, ok: false, ts: null };
    }
  }));

  _niSourceState = results.map(r => {
    const c = _niClassify(r.ok, r.ts);
    return { name: r.name, route: r.route, ok: r.ok, cls: c.cls, label: c.label };
  });

  niSourcesEl.textContent = '';
  _niSourceState.forEach(s => {
    const row = niEl('div', 'ni-srow');
    row.appendChild(niEl('span', 'ni-sk', s.name));
    row.appendChild(niEl('span', 'ni-sv ' + s.cls, s.label));
    niSourcesEl.appendChild(row);
  });

  const up    = _niSourceState.filter(s => s.ok).length;
  const stale = _niSourceState.filter(s => s.cls === 'stale').length;
  if (niSeeSub) niSeeSub.textContent = up + ' of ' + _niSourceState.length + ' available';

  if (niFresh) {
    niFresh.classList.remove('ok', 'stale', 'down', 'busy');
    if (up === 0) {
      niFresh.classList.add('down');
      niFresh.textContent = 'No context available';
    } else if (up < _niSourceState.length || stale > 0) {
      niFresh.classList.add('stale');
      niFresh.textContent = up + '/' + _niSourceState.length + ' available' + (stale ? ', ' + stale + ' stale' : '');
    } else {
      niFresh.classList.add('ok');
      niFresh.textContent = 'All ' + _niSourceState.length + ' sources available';
    }
  }
}

// ── working memory (real GET /assistant-data) ─────────────────────────────
function _niMemGroup(title, items, emptyText) {
  const frag = document.createDocumentFragment();
  frag.appendChild(niEl('div', 'ni-ground-k', title));
  if (!items || !items.length) {
    frag.appendChild(niEl('div', 'ni-rail-empty', emptyText));
    return frag;
  }
  items.forEach(t => frag.appendChild(niEl('div', 'ni-task', String(t))));
  return frag;
}

async function niRefreshMemory() {
  try {
    const res = await fetch('/assistant-data');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const d = await res.json();

    niMemoryEl.textContent = '';
    niMemoryEl.appendChild(niEl('div', 'ni-ground-k', 'Daily focus'));
    niMemoryEl.appendChild(
      niEl('div', d.daily_focus ? 'ni-focus-line' : 'ni-rail-empty',
           d.daily_focus || 'No focus set.')
    );
    const tasks = niEl('div');
    tasks.style.marginTop = '12px';
    tasks.appendChild(_niMemGroup('Tasks', d.tasks, 'No tasks.'));
    niMemoryEl.appendChild(tasks);
    const rem = niEl('div');
    rem.style.marginTop = '12px';
    rem.appendChild(_niMemGroup('Reminders', d.reminders, 'No reminders.'));
    niMemoryEl.appendChild(rem);

    const age = _niAge(d.last_updated);
    if (age) {
      const st = niEl('div', 'ni-ground-k', 'Saved ' + age);
      st.style.marginTop = '12px';
      niMemoryEl.appendChild(st);
    }
  } catch (e) {
    niMemoryEl.textContent = '';
    niMemoryEl.appendChild(niEl('div', 'ni-rail-empty', 'Working memory could not be read.'));
  }
}

function refreshNovaIntelligence() {
  niRefreshSources();
  niRefreshMemory();
}

// ── conversation rendering ────────────────────────────────────────────────
function niHideIdle() {
  if (niIdleNote && niIdleNote.parentNode) niIdleNote.parentNode.removeChild(niIdleNote);
}

function niScroll() { niLog.scrollTop = niLog.scrollHeight; }

function niAppendQuestion(text) {
  niHideIdle();
  const turn = niEl('div', 'ni-turn');
  const q = niEl('div', 'ni-q');
  q.appendChild(niEl('span', 'ni-who', 'You'));
  q.appendChild(document.createTextNode(String(text)));
  turn.appendChild(q);
  niLog.appendChild(turn);
  niScroll();
  return turn;
}

// The pending card carries a skeleton in the shape of the answer, so the
// arrival of a reply is a fill rather than a jump.
function niAppendPending() {
  const a = niEl('div', 'ni-a');
  const head = niEl('div', 'ni-a-head');
  head.appendChild(niEl('span', 'ni-a-who', 'NOVA'));
  const think = niEl('span', 'ni-thinking');
  think.appendChild(niEl('i'));
  think.appendChild(niEl('i'));
  think.appendChild(niEl('i'));
  think.appendChild(niEl('span', null, 'reading context'));
  head.appendChild(think);
  a.appendChild(head);
  const body = niEl('div', 'ni-a-body');
  const sk = niEl('div', 'ni-skel');
  sk.appendChild(niEl('i'));
  sk.appendChild(niEl('i'));
  sk.appendChild(niEl('i'));
  body.appendChild(sk);
  a.appendChild(body);
  niLog.appendChild(a);
  niScroll();
  return a;
}

// The grounding strip states AVAILABILITY, never use. See ui/pages/nova_ai.py
// for why the distinction is not cosmetic.
function niGroundStrip() {
  const g = niEl('div', 'ni-ground');
  g.appendChild(niEl('div', 'ni-ground-k', 'Context available when asked'));
  const chips = niEl('div', 'ni-chips');
  (_niSourceState.length ? _niSourceState : []).forEach(s => {
    const c = niEl('span', 'ni-chip ' + s.cls);
    c.appendChild(document.createTextNode(s.name + (s.cls === 'off' ? '' : ' · ' + s.label)));
    chips.appendChild(c);
  });
  if (!_niSourceState.length) chips.appendChild(niEl('span', 'ni-chip off', 'not read'));
  g.appendChild(chips);

  const down  = _niSourceState.filter(s => !s.ok).length;
  const stale = _niSourceState.filter(s => s.cls === 'stale').length;

  // The availability-is-not-use sentence is unconditional. It was previously
  // on the healthy branch only, which meant the page dropped its most
  // important caveat in exactly the degraded case where it matters most.
  if (down || stale) {
    const warn = niEl('div', 'ni-ground-note');
    warn.appendChild(niEl('b', null,
      (down ? down + ' source' + (down > 1 ? 's' : '') + ' did not answer' : '') +
      (down && stale ? ', and ' : '') +
      (stale ? stale + ' ' + (stale > 1 ? 'are' : 'is') + ' stale' : '') + '. '));
    warn.appendChild(document.createTextNode(
      'NOVA is not told which were missing or old, so treat any claim resting on them as unsupported.'));
    g.appendChild(warn);
  }

  const note = niEl('div', 'ni-ground-note');
  note.appendChild(document.createTextNode(
    'Availability and age are read from each source\u2019s own route. '));
  note.appendChild(niEl('b', null,
    'Whether NOVA incorporated each one is not reported by the chat route \u2014 availability is proven, use is not.'));
  g.appendChild(note);
  return g;
}

function niFillAnswer(card, reply) {
  card.textContent = '';
  const head = niEl('div', 'ni-a-head');
  head.appendChild(niEl('span', 'ni-a-who', 'NOVA'));
  head.appendChild(niEl('span', 'ni-kind infer', 'NOVA inference'));
  card.appendChild(head);

  const body = niEl('div', 'ni-a-body');
  body.appendChild(niEl('p', null, String(reply)));
  card.appendChild(body);

  card.appendChild(niGroundStrip());

  const note = niEl('div', 'ni-a-note');
  note.appendChild(niEl('span', 'ni-kind na', 'No citations'));
  note.appendChild(niEl('span', null,
    'The intelligence layer returns no source references. Nothing above links to a document.'));
  card.appendChild(note);
  niScroll();
}

// Every non-answer replaces the pending card with a SYSTEM note. It is never
// given NOVA's speaker label, never given the inference badge, and never
// given the grounding strip -- none of which would be true of it.
function niFillNotice(card, kind, badge, title, detail, meta) {
  card.className = 'ni-state-note ' + (kind === 'err' ? 'err' : 'warn');
  card.textContent = '';
  const b = niEl('b');
  b.appendChild(niEl('span', 'ni-kind ' + (kind === 'err' ? 'bad' : 'warn'), badge));
  b.appendChild(document.createTextNode(' ' + title));
  card.appendChild(b);
  card.appendChild(document.createTextNode(detail));
  if (meta) {
    const m = niEl('div');
    m.style.marginTop = '7px';
    m.appendChild(niEl('code', null, meta));
    card.appendChild(m);
  }
  niScroll();
}

function niSetBusy(busy) {
  _niBusy = busy;
  niAskBtn.disabled = busy;
  niAskBtn.textContent = busy ? 'Asking…' : 'Ask';
  document.querySelectorAll('#page-assistant .ni-sg').forEach(b => { b.disabled = busy; });
}

async function sendChat(overrideMsg) {
  if (_niBusy) return;
  const msg = overrideMsg || niInput.value.trim();
  if (!msg) return;
  niInput.value = '';
  niSetBusy(true);
  niAppendQuestion(msg);
  const card = niAppendPending();

  // Availability is re-read per question, so the strip describes THIS ask.
  await niRefreshSources();

  try {
    const res = await fetch('/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    });

    // Checked, unlike before: an HTTP failure is not an answer.
    if (!res.ok) {
      niFillNotice(card, 'err', 'Request failed',
        'NOVA could not be reached.',
        'The server returned an error, so there is no answer to show. Nothing was recorded.',
        'HTTP ' + res.status);
      return;
    }

    let data;
    try {
      data = await res.json();
    } catch (parseErr) {
      niFillNotice(card, 'err', 'Unreadable response',
        'The reply could not be read.',
        'The server responded, but the body was not valid JSON. No answer is being shown rather than a guess.');
      return;
    }

    const outcome = String((data && data.outcome) || (data && data.status) || 'ok');
    const reply   = data && typeof data.reply === 'string' ? data.reply.trim() : '';

    if (outcome === 'ok' && reply) {
      niFillAnswer(card, reply);
      // Only a real answer may have changed working memory.
      niRefreshMemory();
    } else if (outcome === 'unavailable') {
      niFillNotice(card, 'warn', 'AI unavailable',
        'NOVA did not answer.',
        reply || 'The intelligence layer is not available right now.',
        data.error_code ? 'error_code: ' + data.error_code : null);
    } else if (outcome === 'empty') {
      niFillNotice(card, 'warn', 'Empty reply',
        'NOVA returned no answer.',
        'The request succeeded but came back with no text. Showing nothing is more honest than filling the gap.');
    } else if (outcome === 'malformed') {
      niFillNotice(card, 'err', 'Malformed reply',
        'The response did not match the expected shape.',
        'The reply arrived but did not carry the agreed fields, so it is not being displayed as analysis.',
        data.error_code ? 'error_code: ' + data.error_code : null);
    } else {
      niFillNotice(card, 'err', 'Request failed',
        'NOVA did not answer.',
        reply || 'The request failed before an answer was produced.',
        data.error_code ? 'error_code: ' + data.error_code : null);
    }
  } catch (err) {
    niFillNotice(card, 'err', 'No connection',
      'NOVA could not be reached.',
      'The request did not complete. This is a connection failure, not an answer.');
  } finally {
    niSetBusy(false);
    niInput.focus();
  }
}

if (niAskBtn) niAskBtn.addEventListener('click', () => sendChat());
if (niInput) niInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });
document.querySelectorAll('#page-assistant .ni-sg').forEach(btn => {
  btn.addEventListener('click', () => sendChat(btn.dataset.cmd));
});

// ════════ JOURNAL ════════
// ══════════════════════════════════════════════════════
// JOURNAL — Intelligence System
// ══════════════════════════════════════════════════════
let journalFilter   = 'all';
let _journalData    = null;
let _journalWorkspace = null;
let _signalData     = null;
let _jDirection     = 'LONG';
let _jOutcome       = 'WIN';
let _jTradeMode     = 'LIVE';
let _jEditingIndex  = null;
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
function setTradeMode(mode) {
  _jTradeMode = mode === 'PAPER' ? 'PAPER' : 'LIVE';
  document.getElementById('jModeLive').className = 'toggle-btn' + (_jTradeMode === 'LIVE' ? ' active-live' : '');
  document.getElementById('jModePaper').className = 'toggle-btn' + (_jTradeMode === 'PAPER' ? ' active-paper' : '');
  const setup = document.getElementById('jSetup');
  if (setup) {
    const experimental = Array.from(setup.options).find(o => o.value === 'EXPERIMENTAL');
    if (experimental) experimental.disabled = _jTradeMode === 'LIVE';
    if (_jTradeMode === 'LIVE' && setup.value === 'EXPERIMENTAL') setup.value = '';
  }
}

function openJModal()  { document.getElementById('jModalBackdrop').style.display = 'flex'; }
function closeJModal() { document.getElementById('jModalBackdrop').style.display = 'none'; }
document.getElementById('jOpenModal').addEventListener('click', () => {
  _jEditingIndex = null;
  setText('jModalTitle','LOG TRADE'); setText('jSubmitBtn','LOG TRADE');
  openJModal();
});

function editTrade(index) {
  const all = (_journalData && _journalData.trades) || [];
  const t = all.find(row => Number(row._journal_index) === Number(index));
  if (!t) return;
  _jEditingIndex = Number(index);
  const set = (id,v) => { const el=document.getElementById(id); if(el)el.value=v==null?'':v; };
  set('jAccount',t.account);set('jTicker',t.ticker);set('jDate',t.trade_date);set('jEntryTime',t.entry_time);set('jExitTime',t.exit_time);
  set('jRealizedPnl',_jnPnl(t));set('jEntry',t.entry_price);set('jExit',t.exit_price);set('jSize',t.size);set('jStop',t.stop);set('jTp1',t.tp1);
  set('jCommission',t.commission);set('jPerformanceRating',t.performance_rating);set('jSetup',t.setup_type);set('jProtocol',t.protocol);set('jSession',t.session);
  set('jPremarketPlan',t.premarket_plan_id);set('jConfluences',(t.confluences||[]).join(', '));set('jTradeManagement',t.trade_management);set('jNotes',t.notes);set('jEmotionalState',t.emotional_state);set('jReflection',t.reflection);
  setTradeMode(_jnTradeMode(t));setDir(String(t.direction||'LONG').toUpperCase());setOutcome(_jnOutcome(t));
  const checked = new Set([...(t.behavioral_flags||[]),...(t.risk_checklist||[]),...(t.trade_checklist||[])]);
  ['jFlagEarlyExit','jFlagLateEntry','jFlagHesitation','jFlagOversized','jFlagFomo','jFlagRevenge','jRiskSize','jRiskTrades','jRiskLosses','jRiskSession','jPrimePosition','jPrimeLevel','jPrimeInteraction','jPrimeConfirmation','jPrimeExecution'].forEach(id=>{const el=document.getElementById(id);if(el)el.checked=checked.has(el.value);});
  setText('jModalTitle','EDIT TRADE');setText('jSubmitBtn','SAVE CHANGES');openJModal();
}

function switchJTab(tab) {
  _jActiveTab = tab;
  // The approved Journal composition has no sub-tab shell, so these elements
  // no longer exist. Guarded rather than removed: the nav handler still calls
  // this on every Journal activation, and renderSignalFeed() is still the
  // owner of the evaluation feed.
  ['trades','signals','analytics'].forEach(t => {
    const panel = document.getElementById('jPanel-' + t);
    const btn   = document.getElementById('jTab-' + t);
    if (panel) panel.style.display = t === tab ? '' : 'none';
    if (btn) btn.classList.toggle('active', t === tab);
  });
  if (tab === 'signals' && !_signalData) refreshSignals();
}

function switchJournalView(view) {
  const next = ['dashboard','plans','trades','reflections','studies','goals'].indexOf(view) >= 0 ? view : 'dashboard';
  document.querySelectorAll('[data-jview-panel]').forEach(panel => panel.classList.toggle('active', panel.dataset.jviewPanel === next));
  document.querySelectorAll('.jn-work-tabs [data-jview]').forEach(btn => btn.classList.toggle('active', btn.dataset.jview === next));
  if (next !== 'dashboard') window.scrollTo({top:0, behavior:'smooth'});
}

document.querySelectorAll('.jn-work-tabs [data-jview]').forEach(btn => {
  btn.addEventListener('click', () => switchJournalView(btn.dataset.jview));
});

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

// ── JOURNAL (approved composition) ────────────────────────────────────────
// Reads GET /journal/data only: `trades` are the genuine stored records and
// `stats` is core.state.compute_journal_stats(). Nothing here invents a
// figure; every region that the stored records cannot support renders an
// explicit unavailable state instead.
//
// INCLUSION RULES -- deliberately identical to compute_journal_stats() so the
// rail (backend) and the ledger/analytics (frontend) can never disagree:
//   * outcome REJECTED (governance-blocked, never executed) and OPEN (no
//     realized outcome yet) are excluded from EVERY metric and from the
//     ledger.
//   * EOD_CLOSE is a real close and is classified WIN / LOSS / BREAKEVEN by
//     the sign of its P&L.
//   * P&L prefers `realized_pnl`; with none it is derived from entry/exit and
//     size, signed by direction. A non-numeric value counts as 0.
//   * BREAKEVEN counts toward the total but toward neither wins nor losses.
//   * A record with no usable LONG/SHORT direction is excluded from
//     By-Direction only, and the exclusion is stated on screen.
//   * A record with no valid YYYY-MM-DD trade_date is excluded from Daily
//     P&L only, and that exclusion is stated on screen too.
const _JN_EXCLUDED_OUTCOMES = ['REJECTED', 'OPEN'];
const _JN_LOW_SAMPLE = 20;

let _jnSelectedKey = null;
let _jnRows = [];

function _jnNum(v) {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : null;
}

// Stable identity for a record so selection survives a refresh.
function _jnKey(t, i) {
  return String(t.order_id || `${t.trade_date || '?'}|${t.ticker || '?'}|${t.entry_price || '?'}|${i}`);
}

function _jnOutcome(t) {
  const raw = String(t.outcome || '').toUpperCase();
  if (raw !== 'EOD_CLOSE') return raw;
  const p = _jnPnl(t);
  return p > 0 ? 'WIN' : (p < 0 ? 'LOSS' : 'BREAKEVEN');
}

function _jnPnl(t) {
  const realized = _jnNum(t.realized_pnl != null ? t.realized_pnl : t.pnl);
  if (realized !== null) return realized;
  const entry = _jnNum(t.entry_price), exit = _jnNum(t.exit_price), size = _jnNum(t.size);
  if (entry === null || exit === null) return 0;
  const s = size === null ? 1 : size;
  return String(t.direction || '').toUpperCase() === 'SHORT' ? (entry - exit) * s : (exit - entry) * s;
}

function _jnClosed(trades) {
  return (trades || []).filter(t => _JN_EXCLUDED_OUTCOMES.indexOf(String(t.outcome || '').toUpperCase()) === -1);
}

function _jnDir(t) {
  const d = String(t.direction || '').toUpperCase();
  return (d === 'LONG' || d === 'SHORT') ? d : null;
}

function _jnTradeMode(t) {
  return String(t.trade_mode || 'LIVE').toUpperCase() === 'PAPER' ? 'PAPER' : 'LIVE';
}

function _jnEsc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function _jnUploadFile(index, file) {
  if (!Number.isInteger(Number(index)) || Number(index) < 0) throw new Error('This trade cannot be updated yet.');
  if (!file) throw new Error('Choose a screenshot first.');
  const allowed = ['image/png', 'image/jpeg', 'image/webp'];
  if (allowed.indexOf(file.type) === -1) throw new Error('Use a PNG, JPEG, or WebP image.');
  if (file.size > 8 * 1024 * 1024) throw new Error('Screenshot must be 8 MB or smaller.');
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('Could not read that image.'));
    reader.readAsDataURL(file);
  });
  const encoded = dataUrl.split(',')[1] || '';
  const res = await fetch('/journal/screenshot/upload', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({index:Number(index), filename:file.name, mime_type:file.type, data_base64:encoded}),
  });
  const data = await res.json();
  if (!res.ok || data.status !== 'ok') throw new Error(data.detail || 'Screenshot upload failed.');
  return data;
}

async function uploadJournalScreenshot(input, index) {
  const status = document.getElementById('jnShotStatus');
  const file = input && input.files ? input.files[0] : null;
  if (!file) return;
  if (status) { status.textContent = 'Uploading…'; status.className = 'jn-shot-status'; }
  try {
    await _jnUploadFile(index, file);
    if (status) { status.textContent = 'Screenshot attached.'; status.className = 'jn-shot-status up'; }
    await refreshJournal();
  } catch (e) {
    if (status) { status.textContent = e.message || 'Upload failed.'; status.className = 'jn-shot-status down'; }
    input.value = '';
  }
}

function _jnMoney(v) {
  const n = _jnNum(v);
  if (n === null) return '—';
  return (n >= 0 ? '+$' : '-$') + Math.abs(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function _jnPnlClass(n) {
  return n > 0 ? 'up' : (n < 0 ? 'down' : 'flat');
}

// Direction-neutral, colour-independent marker so P&L never relies on hue.
function _jnPnlMark(n) {
  return n > 0 ? '▲' : (n < 0 ? '▼' : '—');
}

function _jnValidDate(s) {
  return /^\\d{4}-\\d{2}-\\d{2}$/.test(String(s || ''));
}

// compute_journal_stats() buckets an absent regime/session under the literal
// 'UNKNOWN', and an absent setup under 'Untagged'. Those are storage keys, not
// language: shown verbatim they read as a real category. 'Untagged' is the
// established Journal vocabulary for setups and is kept; everything else that
// means "the record does not carry this" is stated as such.
const _JN_ABSENT_KEYS = ['UNKNOWN', 'NONE', 'NULL', ''];
// Daily P&L keeps ten session slots open. Slots beyond the sessions that
// genuinely exist stay empty -- the chart never invents a day to fill them.
const _JN_DAILY_SLOTS = 10;
// Axis ticks are read at a glance, so they drop the cents the bar labels keep.
function _jnMoneyAxis(v) {
  const a = Math.abs(v);
  if (a < 0.005) return '$0';
  const sign = v < 0 ? '-' : '+';
  if (a >= 10000) return sign + '$' + (a / 1000).toFixed(1) + 'k';
  return sign + '$' + Math.round(a).toLocaleString('en-US');
}
// Above this many sessions the column form cannot hold a signed dollar value
// per slot at 11px on a 390px screen, so mobile switches to the row form.
const _JN_DAILY_DENSE = 6;
function _jnBucketLabel(key, kind) {
  const k = String(key == null ? '' : key).trim();
  if (kind === 'setup' && k.toUpperCase() === 'UNTAGGED') return 'Untagged';
  if (_JN_ABSENT_KEYS.indexOf(k.toUpperCase()) !== -1) return 'Not recorded';
  return k;
}
function _jnIsAbsentBucket(key, kind) {
  return _jnBucketLabel(key, kind) === 'Not recorded';
}

// ── Region renderers ──────────────────────────────────────────────────────

function _jnRenderRail(stats, closed) {
  const total = closed.length;
  const wins = closed.filter(t => _jnOutcome(t) === 'WIN').length;
  const losses = closed.filter(t => _jnOutcome(t) === 'LOSS').length;
  const net = closed.reduce((s, t) => s + _jnPnl(t), 0);
  const winPnls = closed.filter(t => _jnOutcome(t) === 'WIN').map(_jnPnl);
  const lossPnls = closed.filter(t => _jnOutcome(t) === 'LOSS').map(_jnPnl);
  const grossWins = winPnls.reduce((s, p) => s + Math.max(0, p), 0);
  const grossLosses = lossPnls.reduce((s, p) => s + Math.abs(Math.min(0, p)), 0);

  const setCell = (id, val, sub, cls) => {
    const v = document.getElementById(id), s = document.getElementById(id + 'Sub');
    if (v) { v.textContent = val; v.className = 'v' + (cls ? ' ' + cls : ''); }
    if (s) s.textContent = sub;
  };

  const netLabel = document.getElementById('jnNetPnlLabel');
  if (netLabel) netLabel.textContent = 'Net P&L · ' + _JN_PERIODS[_jnPeriod];

  setCell('jnNetPnl', total ? _jnMoney(net) : '—',
    total ? `${total} closed trade${total === 1 ? '' : 's'}` : 'No closed trades yet',
    total ? _jnPnlClass(net) : '');

  // This-week P&L is also computed from the selected population. Instrument,
  // outcome, regime and period filters therefore cannot leave an all-time
  // number behind in an otherwise filtered rail.
  const todayNY = new Intl.DateTimeFormat('en-CA', {timeZone:'America/New_York'}).format(new Date());
  const td = todayNY.split('-').map(Number);
  const monday = new Date(Date.UTC(td[0], td[1] - 1, td[2]));
  monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7));
  const weekStart = monday.toISOString().slice(0, 10);
  const week = closed.filter(t => _jnValidDate(t.trade_date) && t.trade_date >= weekStart)
    .reduce((s, t) => s + _jnPnl(t), 0);
  setCell('jnWeekPnl', week === null ? '—' : _jnMoney(week),
    week === null ? 'Not available' : 'Week to date', week === null ? '' : _jnPnlClass(week));

  // compute_journal_stats() returns profit_factor 0.0 when there are no
  // losing trades. Rendering "0.00" would read as catastrophic rather than
  // "not yet meaningful", so that case is stated in words instead.
  const pf = grossLosses > 0 ? grossWins / grossLosses : null;
  if (!total) setCell('jnProfitFactor', '—', 'No closed trades yet');
  else if (losses === 0) setCell('jnProfitFactor', '—', `No losing trades yet (${wins} win${wins === 1 ? '' : 's'})`);
  else setCell('jnProfitFactor', pf === null ? '—' : pf.toFixed(2), `gross wins ÷ gross losses · ${total} trades`);

  const aw = winPnls.length ? grossWins / winPnls.length : null;
  const al = lossPnls.length ? grossLosses / lossPnls.length : null;
  if (!total) setCell('jnAvgWL', '—', 'No closed trades yet');
  else setCell('jnAvgWL',
    (aw ? _jnMoney(aw) : '—') + ' / ' + (al ? '-$' + Math.abs(al).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '—'),
    `${wins} win${wins === 1 ? '' : 's'} · ${losses} loss${losses === 1 ? '' : 'es'}`);

  // Win rate NEVER appears without its sample size, and a small sample is
  // labelled as such rather than presented as a headline number.
  if (!total) setCell('jnWinRate', '—', 'No closed trades yet');
  else {
    const wr = (wins / total * 100);
    const low = total < _JN_LOW_SAMPLE;
    setCell('jnWinRate', wr.toFixed(total < 10 ? 0 : 1) + '%',
      `n=${total}` + (low ? ' · low sample, not yet meaningful' : ''), low ? 'lowsample' : '');
  }

  const note = document.getElementById('jnRailNote');
  if (note) {
    if (total && total < _JN_LOW_SAMPLE) {
      note.textContent = `Every figure above is computed from ${total} closed trade${total === 1 ? '' : 's'}. Treat them as provisional until the sample grows.`;
      note.style.display = '';
    } else { note.style.display = 'none'; note.textContent = ''; }
  }
}

function _jnRenderLedger(rows, allClosedCount) {
  const body = document.getElementById('jnLedgerBody');
  const foot = document.getElementById('jnLedgerFoot');
  if (!body) return;

  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="7" class="jn-none">${allClosedCount
      ? 'No trades match this filter.' : 'No trades logged yet.'}</td></tr>`;
    if (foot) foot.textContent = allClosedCount
      ? `0 shown · filtered from ${allClosedCount} closed`
      : 'Log a trade, or let the execution path record one automatically.';
    return;
  }

  body.innerHTML = rows.map((r, i) => {
    const t = r.trade, p = r.pnl;
    const sel = r.key === _jnSelectedKey;
    const dir = _jnDir(t);
    const ses = _jnEsc(t.session || ''), reg = _jnEsc(t.active_regime || '');
    const sesReg = (ses || reg) ? [ses, reg].filter(Boolean).join(' · ') : '<span class="jn-dim">Not recorded</span>';
    return `<tr class="jn-row${sel ? ' selected' : ''}" data-key="${_jnEsc(r.key)}"
      tabindex="${sel || (i === 0 && !_jnSelectedKey) ? '0' : '-1'}" aria-selected="${sel}">
      <td><span class="jn-d">${_jnEsc(t.trade_date || '—')}</span>${t.exit_time ? `<span class="jn-t">${_jnEsc(t.exit_time)}</span>` : ''}</td>
      <td class="jn-instr">${_jnEsc(t.ticker || '—')}</td>
      <td>${dir ? `<span class="jn-dir ${dir.toLowerCase()}">${dir}</span>` : '<span class="jn-dim">—</span>'}</td>
      <td class="num">${t.entry_price != null ? _jnEsc(t.entry_price) : '—'}</td>
      <td class="num">${t.exit_price != null ? _jnEsc(t.exit_price) : '—'}</td>
      <td class="num jn-res ${_jnPnlClass(p)}"><span class="jn-mark">${_jnPnlMark(p)}</span>${_jnMoney(p)}</td>
      <td class="ses">${sesReg}</td>
    </tr>`;
  }).join('');

  if (foot) {
    const net = rows.reduce((s, r) => s + r.pnl, 0);
    foot.innerHTML = `${rows.length} closed trade${rows.length === 1 ? '' : 's'} shown` +
      (rows.length !== allClosedCount ? ` · filtered from ${allClosedCount} all-time` : '') +
      ` · net <b class="${_jnPnlClass(net)}">${_jnMoney(net)}</b>`;
  }
}

function _jnRenderReview(row) {
  const host = document.getElementById('jnReviewInner');
  if (!host) return;
  if (!row) {
    host.innerHTML = '<div class="jn-none jn-review-empty">Select a trade to review it.</div>';
    return;
  }
  const t = row.trade, p = row.pnl, dir = _jnDir(t);
  const kv = (lab, val, dim) => `<div class="jn-kv"><div class="k">${lab}</div><div class="v${dim ? ' jn-dim' : ''}">${val}</div></div>`;
  const or = (v, fallback) => (v == null || v === '') ? `<span class="jn-dim">${fallback}</span>` : _jnEsc(v);

  // Optional narrative fields render only when the record genuinely has them.
  const timeline = Array.isArray(t.reasoning_timeline) ? t.reasoning_timeline : [];
  const review = t.nova_review || t.review || '';
  const snapshot = String(t.chart_snapshot || t.screenshot || '').trim();
  const snapshotUrl = !snapshot ? ''
    : (/^(https?:|data:|blob:)/i.test(snapshot) || snapshot.startsWith('/journal/screenshot')) ? snapshot
    : '/journal/screenshot?file=' + encodeURIComponent(snapshot.split('/').pop().split(String.fromCharCode(92)).pop());
  const notes = t.notes || '';
  const linkedPlan = (_journalWorkspace && _journalWorkspace.plans || []).find(plan => String(plan.id) === String(t.premarket_plan_id || ''));
  const riskChecks = Array.isArray(t.risk_checklist) ? t.risk_checklist : [];
  const tradeChecks = Array.isArray(t.trade_checklist) ? t.trade_checklist : [];
  const confluences = Array.isArray(t.confluences) ? t.confluences : [];

  host.innerHTML = `
    <div class="jn-rv-head">
      <div class="jn-rv-title">${_jnEsc(t.ticker || '—')}${dir ? ` <span class="jn-dir ${dir.toLowerCase()}">${dir}</span>` : ''}</div>
      <div class="jn-rv-pnl ${_jnPnlClass(p)}"><span class="jn-mark">${_jnPnlMark(p)}</span>${_jnMoney(p)}</div>
    </div>
    <div class="jn-rv-sub"><span class="jn-mode ${_jnTradeMode(t).toLowerCase()}">${_jnTradeMode(t)}</span> · ${_jnEsc(t.trade_date || '—')}${t.exit_time ? ' · ' + _jnEsc(t.exit_time) : ''}${t.size != null ? ' · ' + _jnEsc(t.size) + ' unit' + (Number(t.size) === 1 ? '' : 's') : ''}</div>
    <div class="jn-kv-grid">
      ${kv('Entry', or(t.entry_price, 'Not recorded'))}
      ${kv('Exit', or(t.exit_price, 'Not recorded'))}
      ${kv('Size', or(t.size, 'Not recorded'))}
      ${kv('Model', or(t.setup_type, 'Not recorded'))}
      ${kv('Account', or(t.account, 'Not recorded'))}
      ${kv('Commission', t.commission != null ? _jnMoney(-Math.abs(Number(t.commission)||0)) : '<span class="jn-dim">Not recorded</span>')}
      ${kv('Execution rating', t.performance_rating != null ? _jnEsc(t.performance_rating) + ' / 10' : '<span class="jn-dim">Not recorded</span>')}
      ${kv('Regime at entry', or(t.active_regime, 'Not recorded'))}
      ${kv('Session', or(t.session, 'Not recorded'))}
    </div>
    ${linkedPlan ? `<div class="jn-rv-block"><h3>Linked Pre-Market Plan</h3><p>${_jnEsc(linkedPlan.date || '')} · ${_jnEsc(linkedPlan.bias || '')}<br>${_jnEsc(linkedPlan.game_plan || 'No game plan recorded.')}</p></div>` : ''}
    ${t.protocol ? `<div class="jn-rv-block"><h3>Daily Protocol</h3><p>${_jnEsc(t.protocol)}</p></div>` : ''}
    ${(riskChecks.length || tradeChecks.length) ? `<div class="jn-rv-block"><h3>Checklist Evidence</h3><p>${riskChecks.map(x=>'✓ '+_jnEsc(x.replace(/_/g,' '))).join('<br>')}${riskChecks.length&&tradeChecks.length?'<br>':''}${tradeChecks.map(x=>'✓ '+_jnEsc(x.replace(/_/g,' '))).join('<br>')}</p></div>` : ''}
    ${confluences.length ? `<div class="jn-rv-block"><h3>Confluences</h3><p>${confluences.map(x=>'• '+_jnEsc(x)).join('<br>')}</p></div>` : ''}
    ${t.trade_management ? `<div class="jn-rv-block"><h3>Trade Management</h3><p>${_jnEsc(t.trade_management)}</p></div>` : ''}
    ${notes ? `<div class="jn-rv-block"><h3>Notes</h3><p>${_jnEsc(notes)}</p></div>` : ''}
    <div class="jn-rv-block">
      <h3>Reasoning Timeline</h3>
      ${timeline.length ? `<ol class="jn-tl">${timeline.map(e => `<li><span class="jn-tl-t">${_jnEsc(e.time || '')}</span><span class="jn-tl-c">${_jnEsc(e.text || e.note || '')}</span></li>`).join('')}</ol>`
        : '<div class="jn-empty-box">No reasoning timeline stored for this trade.<span>Trades taken through the execution path record their reasoning automatically.</span></div>'}
    </div>
    <div class="jn-rv-block">
      <h3>NOVA Review</h3>
      ${review ? `<blockquote class="jn-quote">${_jnEsc(review)}</blockquote>`
        : '<div class="jn-empty-box">No NOVA review stored for this trade.<span>Reviews are generated on request and saved with the record.</span></div>'}
    </div>
    <div class="jn-rv-block">
      <h3>Chart Snapshot</h3>
      ${snapshotUrl ? `<img class="jn-shot" src="${_jnEsc(snapshotUrl)}" alt="Chart snapshot for this trade">`
        : '<div class="jn-empty-box">No chart image attached to this trade.<span>Add your own screenshot below, or let the execution path attach one automatically.</span></div>'}
      <div class="jn-shot-actions">
        <button class="jn-shot-btn" type="button" onclick="document.getElementById('jnShotInput').click()">${snapshotUrl ? 'Replace screenshot' : 'Attach screenshot'}</button>
        <input class="jn-file-input" id="jnShotInput" type="file" accept="image/png,image/jpeg,image/webp" onchange="uploadJournalScreenshot(this, ${Number(t._journal_index)})">
        <span class="jn-shot-status" id="jnShotStatus">PNG, JPEG, or WebP · up to 8 MB</span>
      </div>
    </div>
    <div class="jn-rv-actions">
      <span>This permanently removes the selected ${_jnTradeMode(t) === 'PAPER' ? 'paper study' : 'live trade'} record.</span>
      <div class="jn-record-actions"><button type="button" onclick="editTrade(${Number(t._journal_index)})">Edit Trade</button><button class="jn-delete-btn" type="button" onclick="deleteTrade(${Number(t._journal_index)})">Delete Trade</button></div>
    </div>`;
}

function _jnRenderBreakdown(stats, closed) {
  // Rebuild every bucket from the selected records. Backend all-time buckets
  // are deliberately not reused here because they would contradict the
  // active week/month/instrument/regime/outcome filters.
  const bucket = (pick, missing) => {
    const out = {};
    closed.forEach(t => {
      const key = String(pick(t) || missing);
      const row = out[key] || (out[key] = {wins:0, losses:0, breakevens:0, pnl:0, win_rate:0});
      const oc = _jnOutcome(t);
      if (oc === 'WIN') row.wins++;
      else if (oc === 'LOSS') row.losses++;
      else row.breakevens++;
      row.pnl += _jnPnl(t);
    });
    Object.keys(out).forEach(k => {
      const r = out[k], n = r.wins + r.losses + r.breakevens;
      r.win_rate = n ? r.wins / n * 100 : 0;
    });
    return out;
  };
  stats = {
    by_regime: bucket(t => t.active_regime, 'UNKNOWN'),
    by_session: bucket(t => t.session, 'UNKNOWN'),
    by_setup_type: bucket(t => t.setup_type, 'Untagged'),
  };
  const bars = (host, items, fmt, emptyMsg) => {
    const el = document.getElementById(host);
    if (!el) return;
    if (!items.length) { el.innerHTML = `<div class="jn-none">${emptyMsg}</div>`; return; }
    const max = Math.max.apply(null, items.map(i => Math.abs(i.weight))) || 1;
    el.innerHTML = items.map(i => `<div class="jn-bar-row">
      <div class="jn-bar-lab${i.absent ? ' jn-absent' : ''}">${_jnEsc(i.label)}</div>
      <div class="jn-bar-track"><div class="jn-bar-fill ${i.cls || ''}" style="width:${Math.max(2, Math.abs(i.weight) / max * 100).toFixed(1)}%"></div></div>
      <div class="jn-bar-val ${i.cls || ''}">${fmt(i)}</div>
    </div>`).join('');
  };

  const byBucket = (obj, mapper) => Object.keys(obj || {}).map(k => mapper(k, obj[k]))
    .filter(Boolean).sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight)).slice(0, 6);

  bars('jnByRegime', byBucket(stats.by_regime, (k, v) => {
    const n = (v.wins || 0) + (v.losses || 0) + (v.breakevens || 0);
    return n ? {label: _jnBucketLabel(k, 'regime'), absent: _jnIsAbsentBucket(k, 'regime'),
                weight: v.win_rate || 0, n: n, wr: v.win_rate || 0} : null;
  }), i => `${i.n} trade${i.n === 1 ? '' : 's'} · ${i.wr.toFixed(0)}% win rate`, 'No regime recorded on any trade.');

  bars('jnBySession', byBucket(stats.by_session, (k, v) => {
    const n = (v.wins || 0) + (v.losses || 0) + (v.breakevens || 0);
    return n ? {label: _jnBucketLabel(k, 'session'), absent: _jnIsAbsentBucket(k, 'session'),
                weight: v.pnl || 0, cls: _jnPnlClass(v.pnl || 0), pnl: v.pnl || 0, n: n} : null;
  }), i => `${i.n} trade${i.n === 1 ? '' : 's'} · ${_jnMoney(i.pnl)}`, 'No session recorded on any trade.');

  bars('jnBySetup', byBucket(stats.by_setup_type, (k, v) => {
    const n = (v.wins || 0) + (v.losses || 0) + (v.breakevens || 0);
    return n ? {label: _jnBucketLabel(k, 'setup'), absent: _jnIsAbsentBucket(k, 'setup'),
                weight: n, n: n} : null;
  }), i => `${i.n} trade${i.n === 1 ? '' : 's'}`, 'No setup recorded on any trade.');

  // By-Direction has no backend equivalent, so it is grouped here under the
  // same inclusion rules compute_journal_stats() applies.
  const dirs = {LONG: {n: 0, w: 0, pnl: 0}, SHORT: {n: 0, w: 0, pnl: 0}};
  let noDir = 0;
  closed.forEach(t => {
    const d = _jnDir(t);
    if (!d) { noDir++; return; }
    dirs[d].n++; dirs[d].pnl += _jnPnl(t);
    if (_jnOutcome(t) === 'WIN') dirs[d].w++;
  });
  const dirItems = ['LONG', 'SHORT'].filter(d => dirs[d].n)
    .map(d => ({label: d === 'LONG' ? 'Long' : 'Short', weight: dirs[d].n, n: dirs[d].n,
                wr: dirs[d].w / dirs[d].n * 100}));
  bars('jnByDirection', dirItems,
    i => `${i.n} trade${i.n === 1 ? '' : 's'} · ${i.wr.toFixed(0)}% win rate`,
    'No trade carries a usable direction.');

  const dnote = document.getElementById('jnByDirectionNote');
  if (dnote) {
    const parts = [];
    if (dirItems.length === 1) parts.push(`Only ${dirItems[0].label.toLowerCase()} trades recorded so far.`);
    if (noDir) parts.push(`${noDir} record${noDir === 1 ? '' : 's'} excluded — no usable direction.`);
    dnote.textContent = parts.join(' ');
    dnote.style.display = parts.length ? '' : 'none';
  }

  const meta = document.getElementById('jnBreakdownMeta');
  if (meta) meta.textContent = closed.length
    ? `${closed.length} closed trade${closed.length === 1 ? '' : 's'} · ${_JN_PERIODS[_jnPeriod].toLowerCase()}`
    : 'No closed trades yet';
}

function _jnRenderDaily(closed) {
  const host = document.getElementById('jnDaily');
  const meta = document.getElementById('jnDailyMeta');
  const note = document.getElementById('jnDailyNote');
  const ctx = document.getElementById('jnDailyCtx');
  if (!host) return;

  // ── Aggregation (verified; unchanged) ────────────────────────────────────
  // Real closed-trade P&L netted per trading date. Several trades on one date
  // collapse into that date's net. Undated records are excluded and counted.
  const byDate = {}, tradesOn = {};
  let badDate = 0;
  closed.forEach(t => {
    if (!_jnValidDate(t.trade_date)) { badDate++; return; }
    byDate[t.trade_date] = (byDate[t.trade_date] || 0) + _jnPnl(t);
    tradesOn[t.trade_date] = (tradesOn[t.trade_date] || 0) + 1;
  });
  const allDays = Object.keys(byDate).sort();
  const days = allDays.slice(-_JN_DAILY_SLOTS);

  const notes = [];
  if (badDate) notes.push(badDate + ' record' + (badDate === 1 ? '' : 's') + ' excluded — missing or invalid date.');

  if (!days.length) {
    host.className = 'jn-daily-chart is-empty';
    host.removeAttribute('data-dense');
    host.innerHTML = '<div class="jn-none">' + (closed.length
      ? 'No closed trade carries a usable date.' : 'No closed trades yet.') + '</div>';
    if (meta) meta.textContent = '—';
    if (ctx) { ctx.innerHTML = ''; ctx.style.display = 'none'; }
    if (note) {
      note.textContent = notes.join(' ');
      note.style.display = notes.length ? '' : 'none';
    }
    return;
  }

  const vals = days.map(d => byDate[d]);
  const flat = v => Math.abs(v) < 0.005;
  const maxPos = vals.reduce((m, v) => Math.max(m, v > 0 ? v : 0), 0);
  const maxNeg = vals.reduce((m, v) => Math.max(m, v < 0 ? -v : 0), 0);
  const span = (maxPos + maxNeg) || 1;
  const posPct = (maxPos === 0 && maxNeg === 0) ? 100 : (maxPos / span * 100);
  const flatSide = posPct > 0 ? 'pos' : 'neg';

  host.className = 'jn-daily-chart';
  if (days.length > _JN_DAILY_DENSE) host.setAttribute('data-dense', '1');
  else host.removeAttribute('data-dense');
  host.style.setProperty('--pos', posPct.toFixed(3) + '%');
  host.style.setProperty('--neg', (100 - posPct).toFixed(3) + '%');
  // Adaptive spacing: the track carries exactly as many columns as there are
  // genuine sessions, so one session centres and ten fill the timeline. Bar
  // width is capped so a sparse chart reads as deliberate, not stretched.
  host.style.setProperty('--n', String(days.length));
  host.style.setProperty('--rows', String(days.length));
  host.style.setProperty('--track-w', (days.length * 96) + 'px');

  // ── Y axis: only the values the scale actually reaches ───────────────────
  const yTicks = [];
  if (maxPos > 0) yTicks.push({ at: 0, label: _jnMoneyAxis(maxPos) });
  yTicks.push({ at: posPct, label: '$0' });
  if (maxNeg > 0) yTicks.push({ at: 100, label: _jnMoneyAxis(-maxNeg) });

  const yax = yTicks.map(t =>
    '<span style="top:' + t.at.toFixed(3) + '%">' + _jnEsc(t.label) + '</span>').join('');

  // Gridlines sit on quarters of the plot; the zero line is drawn separately
  // and heavier so the baseline never reads as just another gridline.
  const grid = [0, 25, 50, 75, 100].map(q =>
    '<i class="jn-dp-gl" style="top:' + q + '%"></i>').join('');

  const bars = days.map((d, i) => {
    const v = byDate[d];
    const n = tradesOn[d] || 0;
    const cls = flat(v) ? 'flat' : _jnPnlClass(v);
    const label = d.slice(5).replace('-', '/');
    // A breakeven session is neither a gain nor a loss, so it carries no sign.
    const money = flat(v) ? '$0.00' : _jnMoney(v);
    const a11y = d + ', net ' + money + ', ' + n + ' closed trade' + (n === 1 ? '' : 's');
    const magPct = flat(v) ? '0%' :
      (v > 0 ? (v / maxPos * 100) : (-v / maxNeg * 100)).toFixed(2) + '%';
    const mag = ' style="--mag:' + magPct + '"';
    const fill = '<i class="jn-dbar ' + cls + '"' + mag + '></i>';
    const value = '<span class="jn-dp-v ' + cls + '">' + _jnEsc(money) + '</span>';
    const posCell = '<span class="jn-col-pos">' +
      ((v > 0 || (flat(v) && flatSide === 'pos')) ? fill + value : '') + '</span>';
    const negCell = '<span class="jn-col-neg">' +
      ((v < 0 || (flat(v) && flatSide === 'neg')) ? fill + value : '') + '</span>';
    return '<button type="button" class="jn-dp-bar" style="--i:' + (i + 1) + ';--mag:' + magPct + '"' +
      ' aria-label="' + _jnEsc(a11y) + '">' +
      '<span class="jn-dp-d" aria-hidden="true">' + _jnEsc(label) + '</span>' +
      '<span class="jn-col-plot">' + posCell + negCell + '</span>' +
      '<span class="jn-dp-vm ' + cls + '" aria-hidden="true">' + _jnEsc(money) + '</span>' +
      '<span class="jn-dp-tip" aria-hidden="true"><b>' + _jnEsc(d) + '</b>' +
      '<span class="' + cls + '">' + _jnEsc(money) + '</span>' +
      '<span>' + n + ' closed trade' + (n === 1 ? '' : 's') + '</span></span>' +
      '</button>';
  }).join('');

  const xax = days.map((d, i) =>
    '<span style="--i:' + (i + 1) + '">' + _jnEsc(d.slice(5).replace('-', '/')) + '</span>').join('');

  host.innerHTML =
    '<div class="jn-dp-yax" aria-hidden="true"><div class="jn-dp-yin">' + yax + '</div></div>' +
    '<div class="jn-dp-surface"><div class="jn-dp-inner">' + grid +
      '<i class="jn-zero"></i><div class="jn-dp-bars">' + bars + '</div>' +
    '</div></div>' +
    '<div class="jn-dp-xax" aria-hidden="true">' + xax + '</div>';

  // ── Header scope + computed context, all from the sessions themselves ────
  const total = allDays.reduce((a, d) => a + byDate[d], 0);
  const avg = total / allDays.length;
  let bestD = allDays[0], worstD = allDays[0];
  allDays.forEach(d => {
    if (byDate[d] > byDate[bestD]) bestD = d;
    if (byDate[d] < byDate[worstD]) worstD = d;
  });
  const short = d => d.slice(5).replace('-', '/');
  if (meta) meta.textContent = 'All time · ' + allDays.length +
    ' session' + (allDays.length === 1 ? '' : 's');
  if (ctx) {
    ctx.style.display = '';
    ctx.innerHTML =
      '<div class="jn-dp-ci"><span class="k">Sessions</span><span class="v">' + allDays.length + '</span></div>' +
      '<div class="jn-dp-ci"><span class="k">Avg / session</span><span class="v ' + _jnPnlClass(avg) + '">' + _jnEsc(_jnMoney(avg)) + '</span></div>' +
      '<div class="jn-dp-ci"><span class="k">Best day</span><span class="v ' + _jnPnlClass(byDate[bestD]) + '">' + _jnEsc(_jnMoney(byDate[bestD])) + '<i>' + _jnEsc(short(bestD)) + '</i></span></div>' +
      '<div class="jn-dp-ci"><span class="k">Worst day</span><span class="v ' + _jnPnlClass(byDate[worstD]) + '">' + _jnEsc(_jnMoney(byDate[worstD])) + '<i>' + _jnEsc(short(worstD)) + '</i></span></div>';
  }

  if (allDays.length > days.length)
    notes.push('Showing the most recent ' + days.length + ' of ' + allDays.length + ' sessions.');
  else if (days.length < 5)
    notes.push('Additional sessions will populate this history.');

  if (note) {
    note.textContent = notes.join(' ');
    note.style.display = notes.length ? '' : 'none';
  }
}

// ── Selection ─────────────────────────────────────────────────────────────

function _jnSelect(key, focusRow) {
  _jnSelectedKey = key;
  const row = _jnRows.filter(r => r.key === key)[0] || null;
  _jnRenderReview(row);
  const body = document.getElementById('jnLedgerBody');
  if (!body) return;
  Array.prototype.forEach.call(body.querySelectorAll('.jn-row'), tr => {
    const on = tr.dataset.key === key;
    tr.classList.toggle('selected', on);
    tr.setAttribute('aria-selected', on ? 'true' : 'false');
    tr.tabIndex = on ? 0 : -1;
    if (on && focusRow) tr.focus();
  });
}

function _jnBindLedger() {
  const body = document.getElementById('jnLedgerBody');
  if (!body || body.dataset.bound === '1') return;
  body.dataset.bound = '1';
  body.addEventListener('click', e => {
    const tr = e.target.closest ? e.target.closest('.jn-row') : null;
    if (tr) _jnSelect(tr.dataset.key, false);
  });
  body.addEventListener('keydown', e => {
    const tr = e.target.closest ? e.target.closest('.jn-row') : null;
    if (!tr) return;
    const rows = Array.prototype.slice.call(body.querySelectorAll('.jn-row'));
    const i = rows.indexOf(tr);
    let next = null;
    if (e.key === 'ArrowDown') next = rows[Math.min(rows.length - 1, i + 1)];
    else if (e.key === 'ArrowUp') next = rows[Math.max(0, i - 1)];
    else if (e.key === 'Home') next = rows[0];
    else if (e.key === 'End') next = rows[rows.length - 1];
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); _jnSelect(tr.dataset.key, true); return; }
    if (next) { e.preventDefault(); _jnSelect(next.dataset.key, true); }
  });
}

// ── Main renderer ─────────────────────────────────────────────────────────

// Filter dimensions. Outcome and period are fixed vocabularies the data always
// supports; instrument and regime are built from the values the records
// genuinely carry, so an option that cannot match is never offered. A dimension
// with no usable recorded values renders disabled with a stated reason rather
// than being hidden silently or filled with invented entries.
const _JN_OUTCOMES = {all: 'All', wins: 'Wins', losses: 'Losses'};
const _JN_PERIODS = {today: 'Today', week: 'This week', month: 'This month', quarter: 'This quarter', all: 'All time'};
let _jnInstrument = 'all';
let _jnPeriod = 'all';
let _jnRegime = 'all';
let _jnMode = 'LIVE';
let _jnAccount = 'all';

function _jnDistinct(rows, pick) {
  const seen = [];
  rows.forEach(t => {
    const v = pick(t);
    if (v && seen.indexOf(v) === -1) seen.push(v);
  });
  return seen.sort();
}

function _jnFilterGroup(label, name, options, active, disabledReason) {
  const id = 'jnfg-' + name;
  if (disabledReason) {
    return '<div class="jn-fgroup is-disabled"><span class="jn-fglabel" id="' + id + '">' +
      _jnEsc(label) + '</span><span class="jn-fnone">' + _jnEsc(disabledReason) + '</span></div>';
  }
  return '<div class="jn-fgroup" role="group" aria-labelledby="' + id + '">' +
    '<span class="jn-fglabel" id="' + id + '">' + _jnEsc(label) + '</span>' +
    Object.keys(options).map(k =>
      '<button type="button" class="jn-chip' + (active === k ? ' active' : '') + '"' +
      ' data-fdim="' + name + '" data-fval="' + _jnEsc(k) + '"' +
      ' aria-pressed="' + (active === k) + '">' + _jnEsc(options[k]) + '</button>').join('') +
    '</div>';
}

function _jnDailyTotals(rows) {
  const out = {};
  (rows || []).forEach(t => {
    if (!_jnValidDate(t.trade_date)) return;
    out[t.trade_date] = (out[t.trade_date] || 0) + _jnPnl(t);
  });
  return out;
}

function _jnBindEquityInteraction(host, points) {
  if (!host || typeof host.querySelector !== 'function') return;
  const svg = host.querySelector('svg');
  const guide = svg && svg.querySelector('.jn-eq-guide');
  const tooltip = host && host.querySelector('.jn-eq-tooltip');
  if (!svg || !guide || !tooltip || !points.length) return;

  const tooltipDate = tooltip.querySelector('.jn-eq-tooltip-date');
  const tooltipSession = tooltip.querySelector('[data-eq-session]');
  const tooltipCumulative = tooltip.querySelector('[data-eq-cumulative]');
  const tooltipTrades = tooltip.querySelector('[data-eq-trades]');
  let activeDot = null;

  function showPoint(index) {
    const point = points[index];
    const dot = svg.querySelector('[data-eq-index="' + index + '"]');
    if (!point || !dot) return;
    if (activeDot) activeDot.classList.remove('is-active');
    activeDot = dot;
    activeDot.classList.add('is-active');

    const cx = parseFloat(dot.getAttribute('cx'));
    const cy = parseFloat(dot.getAttribute('cy'));
    guide.setAttribute('x1', cx);
    guide.setAttribute('x2', cx);
    guide.hidden = false;
    tooltipDate.textContent = point.date;
    tooltipSession.textContent = _jnMoney(point.sessionPnl);
    tooltipSession.className = point.sessionPnl > 0 ? 'up' : (point.sessionPnl < 0 ? 'down' : '');
    tooltipCumulative.textContent = _jnMoney(point.value);
    tooltipCumulative.className = point.value > 0 ? 'up' : (point.value < 0 ? 'down' : '');
    tooltipTrades.textContent = point.tradeCount + (point.tradeCount === 1 ? ' trade' : ' trades');
    tooltip.hidden = false;

    const svgBox = svg.getBoundingClientRect();
    const hostBox = host.getBoundingClientRect();
    const rawLeft = svgBox.left - hostBox.left + (cx / 700) * svgBox.width;
    const rawTop = svgBox.top - hostBox.top + (cy / 205) * svgBox.height;
    tooltip.classList.toggle('is-below', rawTop < 95);
    tooltip.style.left = Math.max(105, Math.min(host.clientWidth - 105, rawLeft)) + 'px';
    tooltip.style.top = rawTop + 'px';
  }

  function hidePoint() {
    if (activeDot) activeDot.classList.remove('is-active');
    activeDot = null;
    guide.hidden = true;
    tooltip.hidden = true;
  }

  svg.addEventListener('pointermove', event => {
    if (event.pointerType === 'touch') return;
    const box = svg.getBoundingClientRect();
    const svgX = ((event.clientX - box.left) / box.width) * 700;
    let nearest = 0;
    let distance = Infinity;
    points.forEach((point, index) => {
      const d = Math.abs(point.x - svgX);
      if (d < distance) { distance = d; nearest = index; }
    });
    showPoint(nearest);
  });
  svg.addEventListener('pointerleave', event => {
    if (event.pointerType !== 'touch') hidePoint();
  });
  svg.querySelectorAll('.jn-eq-dot[data-eq-index]').forEach(dot => {
    const index = Number(dot.dataset.eqIndex);
    dot.addEventListener('click', event => { event.stopPropagation(); showPoint(index); });
    dot.addEventListener('focus', () => showPoint(index));
    dot.addEventListener('blur', hidePoint);
  });
}

function _jnRenderDashboard(rows, allTrades, accounts) {
  const controls = document.getElementById('jDashboardControls');
  if (controls) {
    const bookCounts = {
      LIVE: allTrades.filter(t => _jnTradeMode(t) === 'LIVE').length,
      PAPER: allTrades.filter(t => _jnTradeMode(t) === 'PAPER').length,
    };
    const accountOptions = ['<button class="jn-chip' + (_jnAccount === 'all' ? ' active' : '') + '" data-jdash="account" data-value="all" type="button">All accounts</button>']
      .concat(accounts.map(a => '<button class="jn-chip' + (_jnAccount === a ? ' active' : '') + '" data-jdash="account" data-value="' + _jnEsc(a) + '" type="button">' + _jnEsc(a) + '</button>')).join('');
    controls.innerHTML = '<div class="jn-dash-controls"><span class="jn-dash-label">Book</span>' +
      '<button class="jn-chip' + (_jnMode === 'LIVE' ? ' active' : '') + '" data-jdash="mode" data-value="LIVE" type="button">Live · ' + bookCounts.LIVE + '</button>' +
      '<button class="jn-chip' + (_jnMode === 'PAPER' ? ' active' : '') + '" data-jdash="mode" data-value="PAPER" type="button">Paper · ' + bookCounts.PAPER + '</button>' +
      '<span class="jn-dash-sep"></span><span class="jn-dash-label">Account</span>' + accountOptions + '</div>' +
      '<div class="jn-dash-controls"><span class="jn-dash-label">Period</span>' +
      Object.keys(_JN_PERIODS).map(k => '<button class="jn-chip' + (_jnPeriod === k ? ' active' : '') + '" data-jdash="period" data-value="' + k + '" type="button">' + _JN_PERIODS[k] + '</button>').join('') + '</div>';
    if (controls.dataset.bound !== '1') {
      controls.dataset.bound = '1';
      controls.addEventListener('click', e => {
        const b = e.target.closest ? e.target.closest('[data-jdash]') : null;
        if (!b) return;
        if (b.dataset.jdash === 'mode') { _jnMode = b.dataset.value === 'PAPER' ? 'PAPER' : 'LIVE'; _jnAccount = 'all'; }
        else if (b.dataset.jdash === 'account') _jnAccount = b.dataset.value;
        else if (b.dataset.jdash === 'period') _jnPeriod = b.dataset.value;
        _jnSelectedKey = null;
        if (_journalData) renderJournal(_journalData);
      });
    }
  }

  const daily = _jnDailyTotals(rows);
  const days = Object.keys(daily).sort();
  const total = days.reduce((s, d) => s + daily[d], 0);
  setText('jnEquityMeta', rows.length ? _jnMoney(total) + ' · ' + rows.length + ' trades' : 'No closed trades');
  const equity = document.getElementById('jnEquity');
  if (equity) {
    if (!days.length) equity.innerHTML = '<div class="jn-none">No dated closed trades in this book.</div>';
    else {
      let running = 0;
      // Anchor every equity curve at a genuine zero starting balance. A
      // one-session population otherwise collapses to a lone midpoint dot
      // and leaves the entire plotting surface visually unused.
      const counts = {};
      rows.forEach(t => {
        if (_jnValidDate(t.trade_date)) counts[t.trade_date] = (counts[t.trade_date] || 0) + 1;
      });
      const values = [{date:'Starting balance', value:0, sessionPnl:0, tradeCount:0}].concat(
        days.map(d => ({date:d, value:(running += daily[d]), sessionPnl:daily[d], tradeCount:counts[d] || 0})));
      const min = Math.min(0, ...values.map(v => v.value));
      const max = Math.max(0, ...values.map(v => v.value));
      const flatRange = Math.abs(max - min) < .005;
      const span = Math.max(1, max - min);
      const x = i => 48 + i * (632 / (values.length - 1));
      const y = v => flatRange ? 109 : 184 - ((v - min) / span) * 150;
      const points = values.map((v, i) => x(i).toFixed(1) + ',' + y(v.value).toFixed(1)).join(' ');
      const zeroY = y(0).toFixed(1);
      const area = '48,' + zeroY + ' ' + points + ' ' + x(values.length - 1).toFixed(1) + ',' + zeroY;
      const interactivePoints = values.slice(1).map((v, index) => ({...v, x:x(index + 1)}));
      equity.innerHTML = '<svg viewBox="0 0 700 205" role="img" aria-label="Interactive cumulative P and L from ' + _jnEsc(days[0]) + ' through ' + _jnEsc(days[days.length-1]) + '">' +
        '<line class="jn-eq-grid" x1="48" y1="34" x2="680" y2="34"></line><line class="jn-eq-grid" x1="48" y1="109" x2="680" y2="109"></line><line class="jn-eq-grid" x1="48" y1="184" x2="680" y2="184"></line>' +
        '<text class="jn-eq-axis" x="2" y="38">' + _jnEsc(_jnMoney(max)) + '</text><text class="jn-eq-axis" x="18" y="188">' + _jnEsc(_jnMoney(min)) + '</text>' +
        '<polygon class="jn-eq-area" points="' + area + '"></polygon><polyline class="jn-eq-line" points="' + points + '"></polyline>' +
        '<line class="jn-eq-guide" x1="48" y1="28" x2="48" y2="184" hidden></line>' +
        '<rect class="jn-eq-hit" x="48" y="28" width="632" height="156"></rect>' +
        values.map((v,i) => '<circle class="jn-eq-dot" cx="' + x(i).toFixed(1) + '" cy="' + y(v.value).toFixed(1) + '" r="3"' + (i ? ' data-eq-index="' + (i - 1) + '" tabindex="0" role="button" aria-label="' + _jnEsc(v.date + ', session P and L ' + _jnMoney(v.sessionPnl) + ', cumulative P and L ' + _jnMoney(v.value)) + '"' : '') + '><title>' + _jnEsc(v.date + ' · ' + _jnMoney(v.value)) + '</title></circle>').join('') + '</svg>' +
        '<div class="jn-eq-tooltip" role="status" aria-live="polite" hidden><span class="jn-eq-tooltip-date"></span>' +
        '<span class="jn-eq-tooltip-row">Session P&amp;L <b data-eq-session></b></span>' +
        '<span class="jn-eq-tooltip-row">Cumulative P&amp;L <b data-eq-cumulative></b></span>' +
        '<span class="jn-eq-tooltip-row">Closed <b data-eq-trades></b></span></div>';
      if (typeof _jnBindEquityInteraction === 'function') {
        _jnBindEquityInteraction(equity, interactivePoints);
      }
    }
  }

  const recentDays = days.slice(-9);
  setText('jnDashDailyMeta', recentDays.length ? recentDays.length + ' sessions' : 'No sessions');
  const dashDaily = document.getElementById('jnDashDaily');
  if (dashDaily) {
    if (!recentDays.length) dashDaily.innerHTML = '<div class="jn-none">No daily results in this book.</div>';
    else {
      const vals = recentDays.map(d => daily[d]);
      const maxPos = Math.max(0, ...vals);
      const maxNeg = Math.max(0, ...vals.map(v => -v));
      const left = 58, right = 682, top = 25, bottom = 190, plotH = bottom - top;
      const zeroY = maxPos && maxNeg ? top + (maxPos / (maxPos + maxNeg)) * plotH : (maxPos ? bottom : top);
      const trackW = Math.min(right - left, recentDays.length * 94);
      const startX = (left + right - trackW) / 2;
      const step = trackW / recentDays.length;
      const barW = Math.min(40, step * .48);
      const bars = recentDays.map((d, i) => {
        const p = daily[d], cls = _jnPnlClass(p), x = startX + step * i + (step - barW) / 2;
        const flat = Math.abs(p) < .005;
        const h = flat ? 3 : (p > 0 ? (p / maxPos) * (zeroY - top) : (-p / maxNeg) * (bottom - zeroY));
        const y = flat ? zeroY - 1.5 : (p > 0 ? zeroY - h : zeroY);
        const labelY = p > 0 ? Math.max(14, y - 7) : (p < 0 ? Math.min(207, y + h + 14) : zeroY - 7);
        const fill = cls === 'up' ? 'var(--green)' : (cls === 'down' ? 'var(--red)' : 'var(--gold)');
        return '<g class="jn-dash-bar ' + cls + '"><rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + barW.toFixed(1) + '" height="' + Math.max(3, h).toFixed(1) + '" rx="3" fill="' + fill + '"><title>' + _jnEsc(d + ' · ' + _jnMoney(p)) + '</title></rect>' +
          '<text class="jn-dash-val ' + cls + '" x="' + (x + barW / 2).toFixed(1) + '" y="' + labelY.toFixed(1) + '">' + _jnEsc(_jnMoney(p)) + '</text>' +
          '<text class="jn-dash-date" x="' + (x + barW / 2).toFixed(1) + '" y="218">' + _jnEsc(d.slice(5).replace('-', '/')) + '</text></g>';
      }).join('');
      const topLabel = maxPos ? _jnMoneyAxis(maxPos) : '$0';
      const bottomLabel = maxNeg ? _jnMoneyAxis(-maxNeg) : '$0';
      dashDaily.innerHTML = '<svg class="jn-dash-chart" viewBox="0 0 740 228" role="img" aria-label="Daily profit and loss chart for the latest ' + recentDays.length + ' sessions">' +
        '<line class="jn-dash-grid" x1="' + left + '" y1="' + top + '" x2="' + right + '" y2="' + top + '"></line>' +
        '<line class="jn-dash-grid" x1="' + left + '" y1="' + ((top + bottom) / 2).toFixed(1) + '" x2="' + right + '" y2="' + ((top + bottom) / 2).toFixed(1) + '"></line>' +
        '<line class="jn-dash-grid" x1="' + left + '" y1="' + bottom + '" x2="' + right + '" y2="' + bottom + '"></line>' +
        '<line class="jn-dash-zero" x1="' + left + '" y1="' + zeroY.toFixed(1) + '" x2="' + right + '" y2="' + zeroY.toFixed(1) + '"></line>' +
        '<text class="jn-dash-axis" x="4" y="' + (top + 4) + '">' + _jnEsc(topLabel) + '</text>' +
        '<text class="jn-dash-axis" x="4" y="' + Math.min(205, bottom + 4) + '">' + _jnEsc(bottomLabel) + '</text>' + bars + '</svg>';
    }
  }

  const anchor = days.length ? days[days.length - 1] : new Intl.DateTimeFormat('en-CA', {timeZone:'America/New_York'}).format(new Date());
  const ay = Number(anchor.slice(0,4)), am = Number(anchor.slice(5,7));
  const first = new Date(Date.UTC(ay, am - 1, 1));
  const count = new Date(Date.UTC(ay, am, 0)).getUTCDate();
  const calDays = [];
  const leading = first.getUTCDay();
  const prevCount = new Date(Date.UTC(ay, am - 1, 0)).getUTCDate();
  for (let i=0;i<leading;i++) calDays.push('<div class="jn-cal-day outside">' + (prevCount - leading + i + 1) + '</div>');
  let green=0, red=0, flat=0;
  for (let day=1;day<=count;day++) {
    const date = ay + '-' + String(am).padStart(2,'0') + '-' + String(day).padStart(2,'0');
    const has = Object.prototype.hasOwnProperty.call(daily, date), p = has ? daily[date] : 0;
    if (has) { if (p>0) green++; else if (p<0) red++; else flat++; }
    calDays.push('<div class="jn-cal-day' + (has ? ' ' + _jnPnlClass(p) : '') + '">' + day + (has ? '<b class="' + _jnPnlClass(p) + '">' + _jnEsc(_jnMoney(p)) + '</b>' : '') + '</div>');
  }
  // Always render six complete weeks. Adjacent-month dates fill the calendar
  // naturally instead of leaving blank cells or an empty lower panel.
  let nextDay = 1;
  while (calDays.length < 42) calDays.push('<div class="jn-cal-day outside">' + nextDay++ + '</div>');
  setText('jnCalendarMeta', new Date(Date.UTC(ay, am - 1, 1)).toLocaleDateString('en-US',{month:'long',year:'numeric',timeZone:'UTC'}));
  setHtml('jnCalendarSummary','<div class="jn-cal-stat"><b class="up">' + green + '</b><span>Profit days</span></div><div class="jn-cal-stat"><b class="down">' + red + '</b><span>Loss days</span></div><div class="jn-cal-stat"><b class="flat">' + flat + '</b><span>Break even</span></div><div class="jn-cal-stat"><b>' + rows.length + '</b><span>Trades</span></div>');
  setHtml('jnCalendar','<span class="jn-cal-dow">Sun</span><span class="jn-cal-dow">Mon</span><span class="jn-cal-dow">Tue</span><span class="jn-cal-dow">Wed</span><span class="jn-cal-dow">Thu</span><span class="jn-cal-dow">Fri</span><span class="jn-cal-dow">Sat</span>' + calDays.join(''));

  const weeks = {};
  days.forEach(d => { const dt=new Date(d+'T00:00:00Z'); dt.setUTCDate(dt.getUTCDate()-((dt.getUTCDay()+6)%7)); const k=dt.toISOString().slice(0,10); weeks[k]=(weeks[k]||0)+daily[d]; });
  const weekKeys = Object.keys(weeks).sort().slice(-5), weekMax = Math.max(1,...weekKeys.map(k=>Math.abs(weeks[k])));
  setText('jnWeeklyMeta', weekKeys.length ? weekKeys.length + ' weeks' : 'No weeks');
  setHtml('jnWeekly', weekKeys.length ? weekKeys.map(k => '<div class="jn-week-row"><span>Week of ' + k.slice(5).replace('-','/') + '</span><b class="' + _jnPnlClass(weeks[k]) + '">' + _jnEsc(_jnMoney(weeks[k])) + '</b><div class="jn-week-track"><div class="jn-week-fill ' + _jnPnlClass(weeks[k]) + '" style="width:' + (Math.abs(weeks[k])/weekMax*100).toFixed(1) + '%"></div></div></div>').join('') : '<div class="jn-none">No weekly results yet.</div>');

  const models = ['KLR','OTE','ORB','POWELL_10AM'];
  const modelTotals = {}, modelCounts = {};
  rows.forEach(t => { const m=String(t.setup_type||'').toUpperCase(); if(models.indexOf(m)>=0){modelTotals[m]=(modelTotals[m]||0)+_jnPnl(t);modelCounts[m]=(modelCounts[m]||0)+1;} });
  const modelMax = Math.max(1,...models.map(m=>Math.abs(modelTotals[m]||0)));
  setHtml('jnModels', models.map(m => '<div class="jn-model-row"><span>' + (m==='POWELL_10AM'?'Powell 10AM':m) + ' · n=' + (modelCounts[m]||0) + '</span><b class="' + _jnPnlClass(modelTotals[m]||0) + '">' + (modelCounts[m] ? _jnEsc(_jnMoney(modelTotals[m])) : '—') + '</b><div class="jn-model-track"><div class="jn-model-fill" style="width:' + (modelCounts[m] ? Math.abs(modelTotals[m])/modelMax*100 : 0).toFixed(1) + '%"></div></div></div>').join(''));
}

function renderJournal(data) {
  _journalData = data;
  // Personal records are the default performance population. Entries emitted
  // by the retired execution subsystem remain available as a labelled archive
  // but can no longer silently alter the user's performance figures.
  const scope = data._activeScope || 'personal';
  const hasProvenance = Array.isArray(data.personal_trades) && Array.isArray(data.legacy_system_trades);
  const trades = hasProvenance
    ? (scope === 'legacy_system' ? data.legacy_system_trades : data.personal_trades)
    : (data.trades || []);
  const stats = hasProvenance
    ? (scope === 'legacy_system' ? data.legacy_system_stats : data.personal_stats) || {}
    : (data.stats || {});
  // Live performance and paper-study data are two separate books. Historical
  // records without an explicit mode are treated as LIVE for compatibility.
  const bookTrades = trades.filter(t => _jnTradeMode(t) === _jnMode);
  const accounts = _jnDistinct(bookTrades, t => String(t.account || 'Unassigned').trim());
  if (_jnAccount !== 'all' && accounts.indexOf(_jnAccount) === -1) _jnAccount = 'all';
  const modeTrades = bookTrades.filter(t => _jnAccount === 'all' || String(t.account || 'Unassigned').trim() === _jnAccount);
  const closed = _jnClosed(modeTrades);

  // One selected population drives the ledger and every analytical region.
  // “This week” means Monday-to-today in New York; “This month” means the
  // current NY calendar month. Rolling 7/30-day windows would make those
  // labels inaccurate around week and month boundaries.
  const todayNY = new Intl.DateTimeFormat('en-CA', {timeZone:'America/New_York'}).format(new Date());
  const td = todayNY.split('-').map(Number);
  const monday = new Date(Date.UTC(td[0], td[1] - 1, td[2]));
  monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7));
  const weekStart = monday.toISOString().slice(0, 10);
  const monthStart = todayNY.slice(0, 7) + '-01';
  const quarterMonth = Math.floor((td[1] - 1) / 3) * 3 + 1;
  const quarterStart = td[0] + '-' + String(quarterMonth).padStart(2, '0') + '-01';
  setText('jTabCount-trades', modeTrades.length);

  // Instrument and regime options come from the real records, never a literal.
  const instruments = _jnDistinct(closed, t => String(t.ticker || '').trim().toUpperCase());
  const regimes = _jnDistinct(closed, t => {
    const r = String(t.active_regime || '').trim();
    return (r && !_jnIsAbsentBucket(r, 'regime')) ? r : null;
  });
  if (_jnInstrument !== 'all' && instruments.indexOf(_jnInstrument) === -1) _jnInstrument = 'all';
  if (_jnRegime !== 'all' && regimes.indexOf(_jnRegime) === -1) _jnRegime = 'all';

  const dashboardClosed = closed.filter(t => {
    if (_jnPeriod === 'today' && t.trade_date !== todayNY) return false;
    if (_jnPeriod === 'week' && !(_jnValidDate(t.trade_date) && t.trade_date >= weekStart)) return false;
    if (_jnPeriod === 'month' && !(_jnValidDate(t.trade_date) && t.trade_date >= monthStart)) return false;
    if (_jnPeriod === 'quarter' && !(_jnValidDate(t.trade_date) && t.trade_date >= quarterStart)) return false;
    return true;
  });
  const filteredClosed = closed.filter(t => {
    const outcome = _jnOutcome(t);
    if (journalFilter === 'wins' && outcome !== 'WIN') return false;
    if (journalFilter === 'losses' && outcome !== 'LOSS') return false;
    if (_jnInstrument !== 'all' && String(t.ticker || '').trim().toUpperCase() !== _jnInstrument) return false;
    if (_jnPeriod === 'today' && t.trade_date !== todayNY) return false;
    if (_jnPeriod === 'week' && !(_jnValidDate(t.trade_date) && t.trade_date >= weekStart)) return false;
    if (_jnPeriod === 'month' && !(_jnValidDate(t.trade_date) && t.trade_date >= monthStart)) return false;
    if (_jnPeriod === 'quarter' && !(_jnValidDate(t.trade_date) && t.trade_date >= quarterStart)) return false;
    if (_jnRegime !== 'all' && String(t.active_regime || '').trim() !== _jnRegime) return false;
    return true;
  });

  _jnRenderRail(stats, dashboardClosed);
  _jnRenderBreakdown(stats, filteredClosed);
  _jnRenderDaily(filteredClosed);
  _jnRenderDashboard(dashboardClosed, trades, accounts);

  const bar = document.getElementById('jFilterBar');
  if (bar) {
    const instOpts = {all: 'All'};
    instruments.forEach(i => { instOpts[i] = i; });
    const regOpts = {all: 'All regimes'};
    regimes.forEach(r => { regOpts[r] = _jnBucketLabel(r, 'regime'); });
    const scopeHtml = hasProvenance ? _jnFilterGroup('Records', 'records', {
      personal: 'Personal journal (' + data.personal_trades.length + ')',
      legacy_system: 'Legacy system archive (' + data.legacy_system_trades.length + ')',
    }, scope, '') : '';
    const modeOpts = {
      LIVE: 'Live trades (' + trades.filter(t => _jnTradeMode(t) === 'LIVE').length + ')',
      PAPER: 'Paper studies (' + trades.filter(t => _jnTradeMode(t) === 'PAPER').length + ')',
    };
    const accountOpts = {all: 'All accounts'};
    accounts.forEach(a => { accountOpts[a] = a; });
    bar.innerHTML = scopeHtml +
      _jnFilterGroup('Book', 'mode', modeOpts, _jnMode, '') +
      _jnFilterGroup('Account', 'account', accountOpts, _jnAccount, '') +
      _jnFilterGroup('Outcome', 'outcome', _JN_OUTCOMES, journalFilter, '') +
      _jnFilterGroup('Instrument', 'instrument', instOpts, _jnInstrument,
        instruments.length ? '' : 'No instrument recorded') +
      _jnFilterGroup('Period', 'period', _JN_PERIODS, _jnPeriod, '') +
      _jnFilterGroup('Regime', 'regime', regOpts, _jnRegime,
        regimes.length ? '' : 'No regime recorded on any trade');
    if (bar.dataset.bound !== '1') {
      bar.dataset.bound = '1';
      bar.addEventListener('click', e => {
        const b = e.target.closest ? e.target.closest('[data-fdim]') : null;
        if (!b) return;
        const dim = b.dataset.fdim, val = b.dataset.fval;
        if (dim === 'records') {
          _journalData._activeScope = val;
          _jnSelectedKey = null;
        } else if (dim === 'mode') {
          _jnMode = val === 'PAPER' ? 'PAPER' : 'LIVE';
          _jnAccount = 'all';
          _jnSelectedKey = null;
        } else if (dim === 'account') {
          _jnAccount = val;
          _jnSelectedKey = null;
        } else if (dim === 'outcome') journalFilter = val;
        else if (dim === 'instrument') _jnInstrument = val;
        else if (dim === 'period') _jnPeriod = val;
        else if (dim === 'regime') _jnRegime = val;
        if (_journalData) renderJournal(_journalData);
      });
    }
  }

  // Build the ledger from that exact same selected population.
  _jnRows = filteredClosed.map((t, i) => ({key: _jnKey(t, i), trade: t, pnl: _jnPnl(t), outcome: _jnOutcome(t)}))
    .sort((a, b) => String(b.trade.trade_date || '').localeCompare(String(a.trade.trade_date || '')));

  // Selection survives a refresh when the trade still exists; otherwise it
  // falls back to the first visible row, or to the empty state.
  if (!_jnRows.some(r => r.key === _jnSelectedKey)) {
    _jnSelectedKey = _jnRows.length ? _jnRows[0].key : null;
  }

  _jnRenderLedger(_jnRows, closed.length);
  _jnBindLedger();
  _jnRenderReview(_jnRows.filter(r => r.key === _jnSelectedKey)[0] || null);
}

// Honest failure state for every Journal region.
function _jnRenderFailure(msg) {
  const text = msg || 'Journal unavailable — the last request failed.';
  ['jnNetPnl', 'jnWeekPnl', 'jnProfitFactor', 'jnAvgWL', 'jnWinRate'].forEach(id => {
    const v = document.getElementById(id), s = document.getElementById(id + 'Sub');
    if (v) { v.textContent = '—'; v.className = 'v'; }
    if (s) s.textContent = 'Unavailable';
  });
  const note = document.getElementById('jnRailNote');
  if (note) { note.textContent = text; note.style.display = ''; }
  const body = document.getElementById('jnLedgerBody');
  if (body) body.innerHTML = `<tr><td colspan="7" class="jn-err">${_jnEsc(text)}</td></tr>`;
  const foot = document.getElementById('jnLedgerFoot');
  if (foot) foot.textContent = '';
  ['jnByRegime', 'jnBySession', 'jnByDirection', 'jnBySetup', 'jnDaily'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '<div class="jn-err">Unavailable</div>';
  });
  _jnRenderReview(null);
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

function _novaReviewError(msg) {
  // Self-contained toast — survives any subsequent re-render of the card
  // or trade-detail modal, unlike writing into a nova-gen-/nova-body- element.
  const el = document.createElement(\'div\');
  el.textContent = msg;
  el.style.cssText = \'position:fixed;bottom:20px;right:20px;z-index:2000;background:rgba(192,57,43,.95);color:#fff;padding:10px 16px;border-radius:8px;font-family:"Space Mono",monospace;font-size:11px;max-width:360px;box-shadow:0 4px 16px rgba(0,0,0,.3)\';
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 6000);
}

async function generateAnalysis(idx) {
  const btn = document.getElementById(`nova-gen-${idx}`);
  const body = document.getElementById(`nova-body-${idx}`);
  if (btn) { btn.disabled = true; btn.textContent = \'GENERATING...\'; }
  try {
    const res  = await fetch(\'/journal/analyze\', {method:\'POST\', headers:{\'Content-Type\':\'application/json\'}, body: JSON.stringify({index: idx})});
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.status === \'ok\') {
      if (body) { body.textContent = data.analysis; body.classList.add(\'open\'); }
      const hdr = document.getElementById(`nova-hdr-${idx}`);
      if (hdr) hdr.querySelector(\'.itc-review-hdr-ts\').textContent = \'Just now\';
      if (btn) btn.style.display = \'none\';
      refreshJournal();
    } else {
      const msg = (data && (data.detail || data.error)) || `Request failed (HTTP ${res.status})`;
      _novaReviewError(`NOVA Review failed: ${msg}`);
      if (btn) { btn.disabled = false; btn.textContent = \'GENERATE NOVA REVIEW\'; }
    }
  } catch(e) {
    _novaReviewError(`NOVA Review failed: ${(e && e.message) || \'network error\'}`);
    if (btn) { btn.disabled = false; btn.textContent = \'GENERATE NOVA REVIEW\'; }
  }
}

function toggleReview(idx) {
  const body = document.getElementById(`nova-body-${idx}`);
  if (body) body.classList.toggle(\'open\');
}

async function generateMarketSummary() {
  // Manual-only: this function is only ever invoked by the button\'s onclick
  // handler above -- no page-load, refresh, ticker-interval, or background
  // caller may call this.
  const btn     = document.getElementById(\'novaMarketSummaryBtn\');
  const panel   = document.getElementById(\'novaMarketSummaryPanel\');
  const loading = document.getElementById(\'novaMarketSummaryLoading\');
  const textEl  = document.getElementById(\'novaMarketSummaryText\');
  const errEl   = document.getElementById(\'novaMarketSummaryError\');
  // Revealed before anything is written, so the polite live region is in
  // the accessibility tree by the time the result arrives.
  if (panel) panel.hidden = false;
  if (btn) btn.setAttribute(\'aria-expanded\', \'true\');
  if (errEl)  { errEl.style.display = \'none\'; errEl.textContent = \'\'; errEl.className = \'mk-sum-err\'; }
  if (textEl) { textEl.style.display = \'none\'; textEl.textContent = \'\'; }
  if (loading) loading.style.display = \'block\';
  if (btn) { btn.disabled = true; btn.textContent = \'GENERATING...\'; }
  try {
    const res  = await fetch(\'/market-summary\', {method: \'POST\'});
    const data = await res.json().catch(() => ({}));
    const summary = (data && typeof data.summary === \'string\') ? data.summary.trim() : \'\';
    if (res.ok && data.status === \'ok\' && summary) {
      if (textEl) { textEl.textContent = data.summary; textEl.style.display = \'block\'; }
    } else if (res.ok && data.status === \'ok\') {
      // Answered, with nothing to say. An empty result is not a failure
      // and must not be dressed as one.
      if (errEl) { errEl.className = \'mk-sum-empty\';
        errEl.textContent = \'NOVA returned no summary for the current market.\';
        errEl.style.display = \'block\'; }
    } else {
      const msg = (data && data.detail) || \'AI request failed.\';
      if (errEl) { errEl.textContent = msg; errEl.style.display = \'block\'; }
    }
  } catch (e) {
    if (errEl) { errEl.textContent = \'AI request failed.\'; errEl.style.display = \'block\'; }
  } finally {
    if (loading) loading.style.display = \'none\';
    if (btn) { btn.disabled = false; btn.textContent = \'Generate NOVA Summary\'; }
  }
}

// ════════ OVERVIEW: ACCOUNT SUMMARY + RECENT ACTIVITY ════════
// Both read from the same already-active /journal/data payload already
// fetched by refreshJournal() below -- no new route, no new polling
// registration; this renders a condensed view of existing data onto
// Overview.
//
// Deliberately reuses the backend's own already-computed stats fields
// rather than re-deriving P&L/win-rate/weekly-performance client-side --
// avoiding a second, conflicting definition of any of them:
//   - Today's P&L  -> stats.today_pnl (main.py /journal/data; computed
//     with now_ny() -- the correct, NY-based "today" boundary)
//   - Win Rate     -> stats.win_rate (core/state.py compute_journal_stats;
//     all-time -- the only win-rate figure the backend establishes; there
//     is no separate weekly win-rate contract to reuse)
//   - This Week    -> stats.daily_pnl.this_week (compute_journal_stats)
// Only "Trades Today" has no backend-computed equivalent to reuse, so it
// is counted client-side below using the same NY calendar date the
// backend used for today_pnl (via Intl.DateTimeFormat, which returns an
// already-formatted date string with no ambiguous Date-reparsing step),
// and the same REJECTED-exclusion convention already established on the
// Journal page's own overview strip.
function nyTodayDateStr() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(new Date());
}

function renderOverviewAccountSummary(data) {
  const stats  = data.personal_stats  || data.stats  || {};
  const trades = (data.personal_trades || data.trades || []).filter(t => _jnTradeMode(t) === 'LIVE');
  const todayStr = nyTodayDateStr();

  const todayTrades = trades.filter(t => t.trade_date === todayStr && t.outcome !== 'REJECTED');
  const hasTrades = (stats.total || 0) > 0;

  setText('ovAcctTrades', todayTrades.length);

  const pnlEl = document.getElementById('ovAcctPnl');
  if (pnlEl) {
    const todayPnl = parseFloat(stats.today_pnl) || 0;
    pnlEl.textContent = _fmtPnl(todayPnl);
    pnlEl.style.color = todayPnl > 0 ? 'var(--green)' : todayPnl < 0 ? 'var(--red)' : 'var(--muted2)';
  }

  const wrEl = document.getElementById('ovAcctWinRate');
  if (wrEl) {
    const wr = hasTrades ? stats.win_rate : null;
    const n  = stats.total || 0;
    // Sample size is shown alongside the rate itself, not in a separate
    // element a viewer could miss -- a 100% rate from n=1 must never read
    // as a dominant, unqualified headline number.
    wrEl.textContent = wr !== null ? `${wr}% (n=${n})` : '—';
    wrEl.style.color = (n < 5) ? 'var(--muted2)'
      : wr >= 55 ? 'var(--green)' : wr >= 45 ? 'var(--yellow)' : wr !== null ? 'var(--red)' : 'var(--muted2)';
  }

  const wkEl = document.getElementById('ovAcctWeek');
  if (wkEl) {
    const w = parseFloat((stats.daily_pnl || {}).this_week) || 0;
    wkEl.textContent = _fmtPnl(w);
    wkEl.style.color = w > 0 ? 'var(--green)' : w < 0 ? 'var(--red)' : 'var(--muted2)';
  }
}

function renderOverviewRecentActivity(data) {
  const trades = (data.personal_trades || data.trades || []).filter(t => _jnTradeMode(t) === 'LIVE');
  if (!trades.length) {
    setHtml('ovRecentTrades', 'No trades logged yet.');
    return;
  }
  // Sort by trade_date (falling back to timestamp's date portion, same
  // field precedence Journal's own grouping already uses) descending, so
  // "recent" reflects actual trade date rather than array insertion order.
  const dated = trades.map((t, i) => ({
    t, i, key: t.trade_date || (t.timestamp ? t.timestamp.substring(0, 10) : ''),
  }));
  dated.sort((a, b) => (b.key.localeCompare(a.key)) || (b.i - a.i));
  const recent = dated.slice(0, 3).map(d => d.t);

  const rows = recent.map(t => {
    const dir      = (t.direction || '').toUpperCase();
    const dirIcon  = dir === 'LONG' ? '▲' : '▼';
    const dirClass = dir === 'LONG' ? 'up' : 'dn';
    const rawPnl   = t.realized_pnl !== undefined && t.realized_pnl !== null ? t.realized_pnl : (t.pnl ?? null);
    const pnl      = rawPnl !== null ? parseFloat(rawPnl) : null;
    const pnlClass = pnl > 0 ? 'up' : pnl < 0 ? 'dn' : '';
    return `<div class="ov-act-row">
      <span class="sym">${t.ticker || '—'}</span>
      <span class="dir ${dirClass}">${dirIcon} ${dir || '—'}</span>
      <span class="amt ${pnlClass}">${_fmtPnl(pnl)}</span>
    </div>`;
  }).join('');
  setHtml('ovRecentTrades', rows);
}

async function _jwUpload(section, id, file) {
  if (!file) return;
  if (['image/png','image/jpeg','image/webp'].indexOf(file.type) < 0) throw new Error('Use a PNG, JPEG, or WebP image.');
  if (file.size > 8 * 1024 * 1024) throw new Error('Screenshot must be 8 MB or smaller.');
  const dataUrl = await new Promise((resolve,reject) => { const reader=new FileReader(); reader.onload=()=>resolve(String(reader.result||'')); reader.onerror=()=>reject(new Error('Could not read that image.')); reader.readAsDataURL(file); });
  const res = await fetch('/journal/workspace/screenshot/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({section,id,mime_type:file.type,data_base64:(dataUrl.split(',')[1]||'')})});
  const data = await res.json();
  if (!res.ok || data.status !== 'ok') throw new Error(data.detail || 'Screenshot upload failed.');
}

function _jwVal(id) { const el=document.getElementById(id); return el ? el.value.trim() : ''; }
function _jwStatus(id, text, ok) { const el=document.getElementById(id); if(el){el.textContent=text;el.style.color=ok?'var(--green)':'var(--red)';} }
function _jwParagraph(label, value) { return value ? '<p><b>' + _jnEsc(label) + '</b><br>' + _jnEsc(value) + '</p>' : ''; }

function _jwRecord(section, r) {
  let title = r.title || r.date || 'Untitled record';
  let meta = [r.period || r.scope || r.bias, r.date || r.target_date, r.book, r.instrument, r.model].filter(Boolean).join(' · ');
  let body = '';
  if (section === 'plans') body = _jwParagraph('Events',r.events)+_jwParagraph('Key levels',r.levels)+_jwParagraph('Game plan',r.game_plan)+_jwParagraph('Invalidation',r.invalidation);
  if (section === 'reflections') body = _jwParagraph('What happened',r.summary)+_jwParagraph('What went well',r.went_well)+_jwParagraph('Lessons',r.lessons)+_jwParagraph('Next improvement',r.improvement);
  if (section === 'studies') body = _jwParagraph('Study',r.description)+_jwParagraph('Hypothesis',r.hypothesis)+_jwParagraph('Conclusion',r.conclusion);
  if (section === 'goals') { const items=Array.isArray(r.checklist)?r.checklist:[]; body=(items.length?'<p><b>Checklist</b><br>'+items.map(x=>'□ '+_jnEsc(x)).join('<br>')+'</p>':'')+_jwParagraph('Notes',r.notes); }
  return '<article class="jn-record"><div class="jn-record-head"><div><h3>'+_jnEsc(title)+'</h3><div class="jn-record-meta">'+_jnEsc(meta||'Saved Journal record')+'</div></div><div class="jn-record-actions">'+
    (section==='goals'?'<button type="button" onclick="toggleJournalGoal(&quot;'+_jnEsc(r.id)+'&quot;)">'+(r.status==='COMPLETE'?'Reopen':'Complete')+'</button>':'')+
    '<button class="danger" type="button" onclick="deleteJournalWorkspaceRecord(&quot;'+section+'&quot;,&quot;'+_jnEsc(r.id)+'&quot;)">Delete</button></div></div>'+body+(r.chart_snapshot?'<img class="jn-record-shot" src="'+_jnEsc(r.chart_snapshot)+'" alt="Attached '+_jnEsc(section.slice(0,-1))+' chart screenshot">':'')+'</article>';
}

function renderJournalWorkspace(data) {
  _journalWorkspace = data;
  const sections = [['plans','jPlanList'],['reflections','jReflectionList'],['studies','jStudyList'],['goals','jGoalList']];
  sections.forEach(([section,id]) => {
    const records = Array.isArray(data[section]) ? data[section].slice().reverse() : [];
    setHtml(id, records.length ? records.map(r=>_jwRecord(section,r)).join('') : '<div class="jn-empty-records">No '+section+' saved yet.</div>');
  });
  const system = data.system || {};
  setHtml('jSystemSummary','<div class="jn-system-list"><div class="jn-system-row"><span>Approved live models</span><b>'+_jnEsc((system.approved_models||[]).join(' · '))+'</b></div><div class="jn-system-row"><span>Risk rules</span><b>'+_jnEsc((system.daily_risk_pct||1)+'% daily · '+(system.max_trades_per_day||2)+' trades max · '+(system.max_losses_per_day||2)+' losses then done')+'</b></div><div class="jn-system-row"><span>Funded sessions</span><b>'+_jnEsc((system.live_sessions||[]).join(' · '))+'</b></div><div class="jn-system-row"><span>PRIME</span><b>'+_jnEsc((system.prime_steps||[]).join(' → '))+'</b></div></div>');
  const planSelect=document.getElementById('jPremarketPlan');
  if(planSelect){const current=planSelect.value;planSelect.innerHTML='<option value="">— No linked plan —</option>'+(data.plans||[]).slice().reverse().map(p=>'<option value="'+_jnEsc(p.id)+'">'+_jnEsc((p.date||'')+' · '+(p.bias||'PLAN')+' · '+(p.account||p.book||''))+'</option>').join('');planSelect.value=current;}
}

async function refreshJournalWorkspace() {
  try { const res=await fetch('/journal/workspace'); if(!res.ok) throw new Error('HTTP '+res.status); renderJournalWorkspace(await res.json()); }
  catch(e){ console.error('Journal workspace error:',e); ['jPlanList','jReflectionList','jStudyList','jGoalList'].forEach(id=>setHtml(id,'<div class="jn-empty-records down">Workspace unavailable.</div>')); }
}

async function _jwSave(section, payload, file, statusId) {
  _jwStatus(statusId,'Saving…',true);
  const res=await fetch('/journal/workspace/'+section,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const data=await res.json();
  if(!res.ok||data.status!=='ok') throw new Error(data.detail||'Save failed.');
  if(file) await _jwUpload(section,data.record.id,file);
  _jwStatus(statusId,'Saved to NOVA.',true);
  await refreshJournalWorkspace();
}

async function deleteJournalWorkspaceRecord(section,id) {
  if(!confirm('Delete this Journal record?')) return;
  const res=await fetch('/journal/workspace/'+section+'/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
  if(res.ok) refreshJournalWorkspace();
}

async function toggleJournalGoal(id) {
  const goal=(_journalWorkspace&&_journalWorkspace.goals||[]).find(g=>String(g.id)===String(id)); if(!goal)return;
  const updated={...goal,status:goal.status==='COMPLETE'?'ACTIVE':'COMPLETE'};
  const res=await fetch('/journal/workspace/'+'goals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(updated)}); if(res.ok)refreshJournalWorkspace();
}

function _jwBindForm(id, handler) { const form=document.getElementById(id); if(form)form.addEventListener('submit',e=>{e.preventDefault();handler(form);}); }
_jwBindForm('jPlanForm', async form=>{try{const file=document.getElementById('jPlanScreenshot').files[0];await _jwSave('plans',{date:_jwVal('jPlanDate'),book:_jwVal('jPlanBook'),account:_jwVal('jPlanAccount'),bias:_jwVal('jPlanBias'),events:_jwVal('jPlanEvents'),levels:_jwVal('jPlanLevels'),game_plan:_jwVal('jPlanGame'),invalidation:_jwVal('jPlanInvalidation'),risk_limit:_jwVal('jPlanRisk')},file,'jPlanStatus');form.reset();document.getElementById('jPlanDate').value=todayDateStr();}catch(e){_jwStatus('jPlanStatus',e.message||'Save failed.',false);}});
_jwBindForm('jReflectionForm', async form=>{try{await _jwSave('reflections',{period:_jwVal('jReflectionPeriod'),date:_jwVal('jReflectionDate'),rating:_jwVal('jReflectionRating'),title:_jwVal('jReflectionTitle'),summary:_jwVal('jReflectionSummary'),went_well:_jwVal('jReflectionWentWell'),lessons:_jwVal('jReflectionLessons'),improvement:_jwVal('jReflectionImprovement')},null,'jReflectionStatus');form.reset();document.getElementById('jReflectionDate').value=todayDateStr();}catch(e){_jwStatus('jReflectionStatus',e.message||'Save failed.',false);}});
_jwBindForm('jStudyForm', async form=>{try{const file=document.getElementById('jStudyScreenshot').files[0];await _jwSave('studies',{date:_jwVal('jStudyDate'),scope:_jwVal('jStudyScope'),instrument:_jwVal('jStudyInstrument'),model:_jwVal('jStudyModel'),title:_jwVal('jStudyTitle'),description:_jwVal('jStudyDescription'),hypothesis:_jwVal('jStudyHypothesis'),conclusion:_jwVal('jStudyConclusion'),book:'PAPER'},file,'jStudyStatus');form.reset();document.getElementById('jStudyDate').value=todayDateStr();document.getElementById('jStudyInstrument').value='NQ';}catch(e){_jwStatus('jStudyStatus',e.message||'Save failed.',false);}});
_jwBindForm('jGoalForm', async form=>{try{await _jwSave('goals',{period:_jwVal('jGoalPeriod'),target_date:_jwVal('jGoalDate'),title:_jwVal('jGoalTitle'),checklist:_jwVal('jGoalChecklist').split('\\n').map(x=>x.trim()).filter(Boolean),status:'ACTIVE'},null,'jGoalStatus');form.reset();}catch(e){_jwStatus('jGoalStatus',e.message||'Save failed.',false);}});

['jPlanDate','jReflectionDate','jStudyDate'].forEach(id=>{const el=document.getElementById(id);if(el)el.value=todayDateStr();});
[['jPlanScreenshot','jPlanScreenshotName'],['jStudyScreenshot','jStudyScreenshotName']].forEach(([inputId,labelId])=>{const input=document.getElementById(inputId);if(input)input.addEventListener('change',()=>{const f=input.files&&input.files[0];setText(labelId,f?f.name+' · '+(f.size/1024/1024).toFixed(1)+' MB':'PNG, JPEG, or WebP · up to 8 MB');});});

async function refreshJournal() {
  // A failed request must not leave the previous cycle's figures on screen
  // looking current -- every Journal region states that it is unavailable.
  // Overview's own Journal-fed regions keep their existing behaviour.
  let res;
  try {
    res = await fetch('/journal/data');
  } catch (e) {
    console.error('Journal refresh error:', e);
    _jnRenderFailure('Journal unavailable — the request could not be made.');
    return;
  }
  if (!res.ok) {
    _jnRenderFailure('Journal unavailable — server responded ' + res.status + '.');
    return;
  }
  let data;
  try {
    data = await res.json();
  } catch (e) {
    console.error('Journal refresh error:', e);
    _jnRenderFailure('Journal unavailable — the response could not be read.');
    return;
  }
  try { renderJournal(data); } catch(e) { console.error('renderJournal failed:', e); }
  try { renderOverviewAccountSummary(data); } catch(e) { console.error('renderOverviewAccountSummary failed:', e); }
  try { renderOverviewRecentActivity(data); } catch(e) { console.error('renderOverviewRecentActivity failed:', e); }

  // Keep an untouched form date current across midnight, while preserving a
  // date the user deliberately changed for a historical backfill.
  const dateEl = document.getElementById('jDate');
  if (dateEl) {
    const today = todayDateStr();
    if (!dateEl.value || dateEl.value === dateEl.dataset.autoDate) dateEl.value = today;
    dateEl.dataset.autoDate = today;
  }
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
  const account      = (document.getElementById('jAccount').value || '').trim();
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
  const trade_mode   = _jTradeMode;
  const entry_time   = document.getElementById('jEntryTime').value || '';
  const exit_time    = document.getElementById('jExitTime').value || '';
  const commission   = document.getElementById('jCommission').value !== '' ? parseFloat(document.getElementById('jCommission').value) : 0;
  const performance_rating = document.getElementById('jPerformanceRating').value !== '' ? parseFloat(document.getElementById('jPerformanceRating').value) : null;
  const protocol     = (document.getElementById('jProtocol').value || '').trim();
  const premarket_plan_id = document.getElementById('jPremarketPlan').value || '';
  const confluences  = (document.getElementById('jConfluences').value || '').split(',').map(x => x.trim()).filter(Boolean);
  const trade_management = (document.getElementById('jTradeManagement').value || '').trim();

  const msgEl = document.getElementById('jFormMsg');
  function showMsg(text, color) { msgEl.style.display='block'; msgEl.style.color=color; msgEl.textContent=text; }

  if (!ticker) { showMsg('Ticker is required.', 'var(--red)'); return; }
  if (realized_pnl === null && (entry_price === null || exit_price === null)) {
    showMsg('Enter Realized P&L or both Entry and Exit.', 'var(--red)'); return;
  }

  const btn = document.getElementById('jSubmitBtn');
  btn.disabled = true; btn.textContent = _jEditingIndex === null ? 'LOGGING...' : 'SAVING...';
  msgEl.style.display = 'none';

  try {
    const emotional_state  = document.getElementById('jEmotionalState').value;
    const behavioral_flags = ['jFlagEarlyExit','jFlagLateEntry','jFlagHesitation','jFlagOversized','jFlagFomo','jFlagRevenge']
      .filter(id => document.getElementById(id).checked)
      .map(id => document.getElementById(id).value);
    const reflection = (document.getElementById('jReflection').value || '').trim();
    const risk_checklist = ['jRiskSize','jRiskTrades','jRiskLosses','jRiskSession'].filter(id => document.getElementById(id).checked).map(id => document.getElementById(id).value);
    const trade_checklist = ['jPrimePosition','jPrimeLevel','jPrimeInteraction','jPrimeConfirmation','jPrimeExecution'].filter(id => document.getElementById(id).checked).map(id => document.getElementById(id).value);

    const payload = {account, ticker, direction, outcome, size, setup_type, session, notes, trade_date, trade_mode, entry_time, exit_time, commission, performance_rating, protocol, premarket_plan_id, confluences, trade_management, risk_checklist, trade_checklist};
    if (realized_pnl !== null) payload.realized_pnl = realized_pnl;
    if (entry_price  !== null) payload.entry_price   = entry_price;
    if (exit_price   !== null) payload.exit_price    = exit_price;
    if (stop !== null) payload.stop = stop;
    if (tp1  !== null) payload.tp1  = tp1;
    if (emotional_state)         payload.emotional_state  = emotional_state;
    if (behavioral_flags.length) payload.behavioral_flags = behavioral_flags;
    if (reflection)              payload.reflection        = reflection;
    const screenshotInput = document.getElementById('jScreenshot');
    const screenshotFile = screenshotInput && screenshotInput.files ? screenshotInput.files[0] : null;
    if (_jEditingIndex !== null) payload.index = _jEditingIndex;
    const res  = await fetch(_jEditingIndex === null ? '/journal/add' : '/journal/trade/update', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const data = await res.json();
    if (data.status === 'ok') {
      let screenshotError = '';
      if (screenshotFile) {
        try { await _jnUploadFile(data.index, screenshotFile); }
        catch (e) { screenshotError = e.message || 'Screenshot upload failed.'; }
      }
      ['jTicker','jRealizedPnl','jEntry','jExit','jSize','jStop','jTp1','jSetup','jNotes','jReflection','jEntryTime','jExitTime','jCommission','jPerformanceRating','jProtocol','jPremarketPlan','jConfluences','jTradeManagement'].forEach(id => { const el = document.getElementById(id); if(el) el.value=''; });
      if (screenshotInput) screenshotInput.value = '';
      const screenshotName = document.getElementById('jScreenshotName');
      if (screenshotName) screenshotName.textContent = 'PNG, JPEG, or WebP · up to 8 MB';
      document.getElementById('jDate').value = todayDateStr();
      document.getElementById('jDate').dataset.autoDate = todayDateStr();
      document.getElementById('jSession').value = '';
      document.getElementById('jEmotionalState').value = '';
      ['jFlagEarlyExit','jFlagLateEntry','jFlagHesitation','jFlagOversized','jFlagFomo','jFlagRevenge'].forEach(id => { const el = document.getElementById(id); if(el) el.checked = false; });
      ['jRiskSize','jRiskTrades','jRiskLosses','jRiskSession','jPrimePosition','jPrimeLevel','jPrimeInteraction','jPrimeConfirmation','jPrimeExecution'].forEach(id => { const el = document.getElementById(id); if(el) el.checked = false; });
      setDir('LONG'); setOutcome('WIN'); setTradeMode('LIVE');
      const wasEditing = _jEditingIndex !== null;
      _jEditingIndex = null; setText('jModalTitle','LOG TRADE');
      showMsg(screenshotError ? `Trade saved, but ${screenshotError}` : (wasEditing ? 'Trade updated.' : (screenshotFile ? 'Trade and screenshot logged.' : 'Trade logged.')), screenshotError ? 'var(--gold)' : 'var(--green)');
      setTimeout(() => { msgEl.style.display='none'; closeJModal(); }, screenshotError ? 2600 : 1200);
      refreshJournal();
    } else {
      showMsg('Error: ' + (data.detail || 'Unknown'), 'var(--red)');
    }
  } catch(e) { showMsg('Connection error.', 'var(--red)'); }
  btn.disabled = false; btn.textContent = _jEditingIndex === null ? 'LOG TRADE' : 'SAVE CHANGES';
});

const _jnNewShotInput = document.getElementById('jScreenshot');
if (_jnNewShotInput) _jnNewShotInput.addEventListener('change', () => {
  const label = document.getElementById('jScreenshotName');
  const file = _jnNewShotInput.files && _jnNewShotInput.files[0];
  if (label) label.textContent = file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB` : 'PNG, JPEG, or WebP · up to 8 MB';
});

['jTicker','jRealizedPnl','jEntry','jExit','jSize','jStop','jTp1','jSetup','jNotes'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('jSubmitBtn').click(); });
});


// ═════════════════════════ MARKETS ═════════════════════════════════════════

function _mkEsc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
// Symbols arrive spelled differently by route -- /futures-macro-pulse says
// US10Y, /major-indexes says "US 10Y". Without this they de-duplicate to two
// instruments instead of one.
function _mkNorm(sym) {
  const s = String(sym || '').trim().toUpperCase();
  if (s === 'US 10Y' || s === 'US10Y') return 'US10Y';
  if (s === 'SPX') return 'S&P 500';
  return s;
}
function _mkPctNum(v) {
  const n = parseFloat(String(v == null ? '' : v).replace(/[%+,]/g, ''));
  return isFinite(n) ? n : null;
}
function _mkDir(pct) {
  const n = _mkPctNum(pct);
  if (n === null) return '';
  return n > 0 ? 'up' : (n < 0 ? 'dn' : 'flat');
}
function _mkAge(iso) {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!isFinite(t)) return null;
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 60) return s + 's';
  if (s < 3600) return Math.round(s / 60) + 'm';
  if (s < 86400) return Math.round(s / 3600) + 'h';
  return Math.round(s / 86400) + 'd';
}
function _mkFmt(v, dp) {
  const n = typeof v === 'number' ? v : parseFloat(String(v).replace(/,/g, ''));
  if (!isFinite(n)) return String(v == null ? '—' : v);
  return n.toLocaleString('en-US', {minimumFractionDigits: dp, maximumFractionDigits: dp});
}
function _mkSigned(v, dp) {
  const n = typeof v === 'number' ? v : parseFloat(String(v).replace(/[,+]/g, ''));
  if (!isFinite(n)) return '—';
  return (n > 0 ? '+' : '') + _mkFmt(n, dp);
}

// Merge the supported quote routes into one de-duplicated instrument list.
// /btc-vix legitimately returns {"BTC":{},"VIX":{}} -- an empty object is not a
// price, so BTC is simply absent rather than estimated or carried forward.
function _mkMergeQuotes(pulseRows, indexRows, btcVix) {
  const out = [];
  const seen = {};
  const push = (row) => {
    const sym = _mkNorm(row.symbol);
    if (!sym || seen[sym]) return;
    const pct = row.pct;
    if (row.last == null || row.last === '' || row.last === '—') return;
    seen[sym] = true;
    out.push({
      symbol: sym,
      group: _MK_GROUPS[sym] || 'Other',
      last: row.last,
      chg: row.chg,
      pct: pct,
      dir: row.dir || _mkDir(pct),
    });
  };
  (pulseRows || []).forEach(push);
  (indexRows || []).forEach(push);
  const btc = (btcVix || {}).BTC || {};
  if (btc.last != null && btc.last !== '') {
    push({symbol: 'BTC', last: btc.last, chg: btc.chg, pct: btc.pct});
  }
  return out;
}

function _mkQuoteState() {
  if (_mkQuotesFailed && !_mkQuotes) return 'error';
  if (!_mkQuotes) return 'loading';
  if (!_mkQuotes.length) return 'empty';
  if (_mkQuotesFailed) return 'stale';
  return 'live';
}

function _mkSetFresh() {
  const el = document.getElementById('mkFresh');
  if (!el) return;
  const st = _mkQuoteState();
  const age = _mkAge(_mkQuotesAt);
  const map = {
    live: ['live', age ? 'Live · updated ' + age + ' ago' : 'Live'],
    stale: ['stale', age ? 'Cached · ' + age + ' old' : 'Cached'],
    loading: ['loading', 'Loading…'],
    empty: ['live', age ? 'Live · updated ' + age + ' ago' : 'Live'],
    error: ['down', 'Unavailable'],
  };
  const [cls, text] = map[st] || map.loading;
  el.className = 'mk-fresh ' + cls;
  el.textContent = text;
}

function _mkRenderRail(risk, session) {
  const set = (id, html) => { const e = document.getElementById(id); if (e) e.innerHTML = html; };
  const badge = (v) => {
    const t = String(v == null ? '' : v).trim();
    if (!t) return '<span class="mk-badge none">Not available</span>';
    const k = t.toLowerCase();
    const cls = (k === 'low' || k === 'high' || k === 'medium') ? k : 'none';
    return '<span class="mk-badge ' + cls + '">' + _mkEsc(t) + '</span>';
  };
  const sess = document.getElementById('mkSession');
  if (sess) {
    const s = session || '—';
    sess.innerHTML = _mkEsc(s) + '<small id="mkSessionSub">' +
      (risk && risk.session_note ? _mkEsc(risk.session_note) : '') + '</small>';
  }
  set('mkMacroRisk', badge((risk || {}).macro_risk));
  set('mkHeadlineRisk', badge((risk || {}).headline_risk));
  set('mkMarketRisk', badge((risk || {}).market_news_risk));
  const ep = document.getElementById('mkEventPhase');
  if (ep) {
    const phase = (risk || {}).event_phase || '—';
    const nxt = (risk || {}).next_event || '';
    ep.innerHTML = _mkEsc(phase) + '<small id="mkNextEvent">' + _mkEsc(nxt) + '</small>';
  }
}

function _mkRenderPulse() {
  const body = document.getElementById('mkPulseBody');
  const meta = document.getElementById('mkPulseMeta');
  const foot = document.getElementById('mkPulseFoot');
  if (!body) return;
  const st = _mkQuoteState();
  const rows = _mkQuotes || [];

  if (foot) {
    foot.innerHTML = 'Merged from <code>/futures-macro-pulse</code> and <code>/major-indexes</code>, ' +
      'de-duplicated on symbol. <code>/btc-vix</code> supplies BTC only when it returns a price.';
  }
  if (meta) {
    meta.textContent = st === 'loading' ? 'loading'
      : st === 'error' ? 'unavailable'
      : st === 'empty' ? '0 instruments'
      : rows.length + ' instrument' + (rows.length === 1 ? '' : 's') +
        (st === 'stale' ? ' · cached' : ' · live');
  }
  if (st === 'loading') {
    body.innerHTML = '<div class="mk-skel-rows"><i></i><i></i><i></i><i></i><i></i></div>';
    return;
  }
  if (st === 'error') {
    body.innerHTML = '<div class="mk-note err"><b>Cross-asset pulse unavailable</b>' +
      'The quote service did not respond. No prices are shown rather than showing the last ' +
      'known values as if they were current.</div>';
    return;
  }
  if (st === 'empty') {
    body.innerHTML = '<div class="mk-note"><b>No instruments returned</b>' +
      'The quote service responded and returned no rows. Nothing is charted rather than ' +
      'filling the table with placeholders.</div>';
    return;
  }

  const mags = rows.map(r => Math.abs(_mkPctNum(r.pct) || 0));
  const max = Math.max.apply(null, mags.concat([0.01]));
  const muted = st === 'stale' ? ' mk-muted' : '';
  const html = ['<table class="mk-xa"><thead><tr>' +
    '<th scope="col">Instrument</th><th scope="col">Group</th>' +
    '<th scope="col" class="n">Last</th><th scope="col" class="n">Chg</th>' +
    '<th scope="col" class="n">%</th><th scope="col" class="mvc">Move</th>' +
    '</tr></thead><tbody>'];
  rows.forEach((r, i) => {
    const d = r.dir || _mkDir(r.pct);
    const w = Math.min(100, Math.abs(_mkPctNum(r.pct) || 0) / max * 100);
    const sel = (_mkNorm(r.symbol) === _mkSym) ? ' is-sel' : '';
    const lab = r.symbol + ', ' + r.group + ', last ' + (r.last == null ? 'not available' : r.last) +
      ', change ' + (r.pct || 'not available');
    html.push('<tr tabindex="0" class="mk-row' + sel + muted + '" data-mk-row="' + _mkEsc(r.symbol) + '"' +
      ' aria-label="' + _mkEsc(lab) + '">' +
      '<td class="mk-sym">' + _mkEsc(r.symbol) + '</td>' +
      '<td class="mk-grp">' + _mkEsc(r.group) + '</td>' +
      '<td class="n mk-last">' + _mkEsc(typeof r.last === 'number' ? _mkFmt(r.last, 2) : r.last) + '</td>' +
      '<td class="n mk-last ' + d + '">' + (r.chg == null ? '—' : _mkEsc(_mkSigned(r.chg, 2))) + '</td>' +
      '<td class="n mk-pct ' + d + '">' + _mkEsc(r.pct == null ? '—' : r.pct) + '</td>' +
      '<td class="mvc"><span class="mk-mv"><i class="' + d + '" style="width:' + w.toFixed(1) + '%"></i></span></td>' +
      '</tr>');
  });
  html.push('</tbody></table>');
  if (st === 'stale') {
    const age = _mkAge(_mkQuotesAt) || 'some time';
    html.push('<div class="mk-note"><b>These are cached prices, ' + age + ' old</b>' +
      'The quote service has not returned since. Values are shown in muted type and must not ' +
      'be read as the current market.</div>');
  }
  body.innerHTML = html.join('');
}

function _mkRenderVol() {
  const body = document.getElementById('mkVolBody');
  const meta = document.getElementById('mkVolMeta');
  if (!body) return;
  const st = _mkQuoteState();
  if (meta) meta.textContent = st === 'loading' ? 'loading' : st === 'error' ? 'unavailable' : st;
  if (st === 'loading') { body.innerHTML = '<div class="mk-skel-rows"><i></i><i></i><i></i></div>'; return; }
  if (st === 'error') {
    body.innerHTML = '<div class="mk-note err"><b>Unavailable</b>' +
      'Volatility and index direction both derive from the quote service, which did not respond.</div>';
    return;
  }
  if (st === 'empty') {
    body.innerHTML = '<div class="mk-note"><b>Nothing to derive</b>' +
      'Volatility and direction are computed from the instrument table, which returned no rows.</div>';
    return;
  }
  const rows = _mkQuotes || [];
  const find = (sym) => rows.filter(r => _mkNorm(r.symbol) === sym)[0] || null;
  const vix = find('VIX');
  const btc = find('BTC');
  const row = (k, v, cls) =>
    '<div class="mk-vrow"><span class="mk-vk">' + k + '</span>' +
    '<span class="mk-vv ' + (cls || '') + '">' + v + '</span></div>';

  let html = '';
  html += row('VIX', vix
    ? _mkEsc(typeof vix.last === 'number' ? _mkFmt(vix.last, 2) : vix.last) +
      ' <span class="mk-vsub">' + _mkEsc(vix.pct || '') + '</span>'
    : '<span class="mk-na">Not available</span>', vix ? _mkDir(vix.pct) : '');
  if (vix) {
    const lv = parseFloat(String(vix.last).replace(/,/g, ''));
    const regime = !isFinite(lv) ? 'Not available'
      : lv < 20 ? 'Below 20 · calm'
      : lv < 30 ? '20–30 · elevated' : 'Above 30 · stressed';
    html += row('VIX regime', '<span class="mk-vsub">' + regime + '</span>');
  }
  // /btc-vix returning {} is a real state: absent, never invented.
  html += row('BTC · risk proxy', btc
    ? _mkEsc(btc.pct || '—') : '<span class="mk-na">Not available</span>', btc ? _mkDir(btc.pct) : '');

  const eq = (_mkIndexRows || []).filter(r => _MK_EQUITY.indexOf(_mkNorm(r.symbol)) !== -1);
  if (eq.length) {
    const up = eq.filter(r => (r.dir || _mkDir(r.pct)) === 'up').length;
    html += '<div class="mk-vrow mk-vrow-block">' +
      '<div class="mk-vhead"><span class="mk-vk">Index direction</span>' +
      '<span class="mk-vv"><span class="up">' + up + '</span> ' +
      '<span class="mk-vsub">of ' + eq.length + ' advancing</span></span></div>' +
      '<div class="mk-breadth" aria-hidden="true">' +
        eq.map(r => '<i class="' + ((r.dir || _mkDir(r.pct)) === 'up' ? 'up' : 'dn') + '"></i>').join('') +
      '</div>' +
      '<div class="mk-vnote">' + eq.map(r => _mkEsc(r.symbol)).join(', ') +
      ' — the equity indexes <code>/major-indexes</code> returns. Not an exchange breadth feed.</div>' +
      '</div>';
  } else {
    html += row('Index direction', '<span class="mk-na">Not available</span>');
  }
  body.innerHTML = html;
}

function _mkRenderNews(dash) {
  const body = document.getElementById('mkNewsBody');
  const meta = document.getElementById('mkNewsMeta');
  const wire = document.getElementById('mkBreakingWire');
  if (!body) return;
  if (!dash) {
    body.innerHTML = '<div class="mk-skel-rows"><i></i><i></i><i></i></div>';
    if (meta) meta.textContent = 'loading';
    return;
  }
  const news = dash.news || [];
  const events = ((dash.calendar || {}).events) || [];
  const riskDate = String(((dash.risk || {}).donna_time_ny) || '').slice(0, 10);
  const todayEt = riskDate || (() => {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(new Date()).reduce((out, p) => { out[p.type] = p.value; return out; }, {});
    return parts.year + '-' + parts.month + '-' + parts.day;
  })();
  const byEventTime = (a, b) => String(a.date || '').localeCompare(String(b.date || '')) ||
    String(a.time_et || '').localeCompare(String(b.time_et || ''));
  const currentEvents = events.filter(e => String(e.date || '') >= todayEt).sort(byEventTime);
  const recentEvents = events.filter(e => String(e.date || '') < todayEt).sort(byEventTime).reverse();
  const displayedEvents = currentEvents.concat(recentEvents).slice(0, 6);
  const severityWeight = {high: 3, medium: 2, low: 1};
  const ranked = news.slice().sort((a, b) => {
    const score = (n) => {
      const age = n.published_at ? Math.max(0, Date.now() / 1000 - Number(n.published_at)) : Infinity;
      const sev = String(n.severity || '').toLowerCase();
      const liveBoost = sev === 'high' && age <= 7200 ? 100 : age <= 21600 ? 25 : 0;
      return liveBoost + Number(n.market_score || 0) * 10 + (severityWeight[sev] || 0);
    };
    return score(b) - score(a) || Number(b.published_at || 0) - Number(a.published_at || 0);
  });
  const safeUrl = (n) => /^https?:[/][/]/i.test(String((n || {}).url || '')) ? String(n.url) : '';
  const stamp = (n, includeDate) => {
    const raw = Number((n || {}).published_at || 0);
    if (!raw) return 'Time unavailable';
    const d = new Date(raw * 1000);
    if (isNaN(d.getTime())) return 'Time unavailable';
    try {
      return d.toLocaleString('en-US', {
        timeZone: 'America/New_York', month: includeDate ? 'short' : undefined,
        day: includeDate ? 'numeric' : undefined, year: includeDate ? 'numeric' : undefined,
        hour: 'numeric', minute: '2-digit',
        hour12: true,
      }).replace(',', '') + ' ET';
    } catch (e) { return 'Time unavailable'; }
  };
  const linkedTitle = (n, cls) => {
    const title = _mkEsc(n.headline || 'Untitled headline');
    const url = safeUrl(n);
    return url ? '<a class="' + (cls || '') + '" href="' + _mkEsc(url) +
      '" target="_blank" rel="noopener noreferrer">' + title + '</a>' : title;
  };
  const row = (n) => {
    const sev = String(n.severity || 'low').toLowerCase();
    return '<div class="mk-news-row"><span class="mk-cat-t">' + _mkEsc(stamp(n, true)) + '</span>' +
      '<span class="mk-imp ' + _mkEsc(sev) + '" aria-hidden="true"></span>' +
      '<span>' + linkedTitle(n) + '<small>' + _mkEsc([n.category || 'Markets', n.source || 'Source unavailable'].join(' · ')) +
      '</small></span></div>';
  };

  if (meta) {
    const newest = ranked.reduce((v, n) => Math.max(v, Number(n.published_at || 0)), 0);
    meta.textContent = news.length + ' live headlines · ' + events.length + ' macro events' +
      (newest ? ' · latest ' + stamp({published_at: newest}, false) : '');
  }

  if (wire) {
    if (ranked.length) {
      const top = ranked[0];
      wire.innerHTML = '<span>Breaking</span><strong>' + linkedTitle(top) +
        '<small>' + _mkEsc(stamp(top, true)) + '</small></strong>';
    } else {
      wire.innerHTML = '<span>Live wire</span><strong>No verified headline is available right now.</strong>';
    }
  }

  let html = '';
  if (ranked.length) {
    const lead = ranked[0];
    const ageSec = lead.published_at ? Math.max(0, Date.now() / 1000 - Number(lead.published_at)) : Infinity;
    const sev = String(lead.severity || 'low').toLowerCase();
    const breaking = sev === 'high' && ageSec <= 7200;
    html += '<div class="mk-news-desk"><article class="mk-news-lead">' +
      '<div class="mk-news-lead-meta"><span class="mk-breaking' + (breaking ? '' : ' medium') + '">' +
      (breaking ? 'Breaking' : 'Top market driver') + '</span><span class="mk-news-stamp">' +
      _mkEsc([lead.category || 'Markets', stamp(lead, true), lead.source || 'Source unavailable'].join(' · ')) +
      '</span></div><h3>' + linkedTitle(lead) + '</h3>' +
      (lead.summary ? '<p class="mk-news-summary">' + _mkEsc(String(lead.summary).slice(0, 420)) + '</p>' : '') +
      (safeUrl(lead) ? '<a class="mk-news-open" href="' + _mkEsc(safeUrl(lead)) +
        '" target="_blank" rel="noopener noreferrer">Open full article ↗</a>' : '') +
      '</article><section class="mk-news-rapid"><div class="mk-news-label">Latest market-moving updates</div>' +
      ranked.slice(1, 6).map(row).join('') + '</section></div>';
  } else {
    html += '<div class="mk-note"><b>No headlines in the feed</b>The news service returned zero live articles. ' +
      'Nothing is repeated as if it had just broken.</div>';
  }

  html += '<div class="mk-news-lower"><section class="mk-news-section"><div class="mk-news-label">Why NQ is moving</div>';
  const nq = (_mkQuotes || []).filter(r => _mkNorm(r.symbol) === 'NQ')[0] || null;
  const es = (_mkQuotes || []).filter(r => _mkNorm(r.symbol) === 'ES')[0] || null;
  const nqTerms = /\b(nq|nasdaq|tech|semiconductor|nvidia|fed|rate|yield|inflation|cpi|ppi|jobs|payroll|oil|iran|war|tariff|treasury)\b/i;
  const drivers = ranked.filter(n => String(n.severity || '').toLowerCase() !== 'low' &&
    nqTerms.test([n.headline, n.summary, n.category].filter(Boolean).join(' '))).slice(0, 3);
  const renderIndexDriver = (quote, symbol, related) => {
    if (!quote) return '<div class="mk-note"><b>' + symbol + ' move unavailable</b>The quote service has not returned a current ' + symbol + ' move.</div>';
    const dir = _mkDir(quote.chg);
    const move = quote.chg == null ? (quote.pct || '—') : _mkSigned(quote.chg, 2) + ' pts (' + (quote.pct || '—') + ')';
    return '<div class="mk-driver-box"><div class="mk-driver-move ' + dir + '">' + symbol + ' ' + _mkEsc(move) + '</div>' +
      '<div class="mk-driver-note">Potential live drivers for the current move. These headlines are correlated context, not verified causation.</div>' +
      (related.length ? '<ul class="mk-driver-list">' + related.map(n => '<li>' + linkedTitle(n) + '</li>').join('') + '</ul>' :
        '<div class="mk-driver-note" style="margin-top:10px">No high-confidence headline catalyst is present. NOVA will not invent a reason for the move.</div>') + '</div>';
  };
  html += renderIndexDriver(nq, 'NQ', drivers);
  const esTerms = /\b(es|s&p|s&p 500|sp500|stocks|equities|fed|rate|yield|inflation|cpi|ppi|jobs|payroll|oil|iran|war|tariff|treasury)\b/i;
  const esDrivers = ranked.filter(n => String(n.severity || '').toLowerCase() !== 'low' &&
    esTerms.test([n.headline, n.summary, n.category].filter(Boolean).join(' '))).slice(0, 2);
  html += '<div class="mk-driver-subhead">Why ES is moving</div>' + renderIndexDriver(es, 'ES', esDrivers);
  html += '</section><section class="mk-news-section"><div class="mk-news-label">Upcoming macro · date &amp; time ET</div>';
  displayedEvents.forEach(e => {
    const imp = String(e.importance || 'low').toLowerCase();
    html += '<div class="mk-cat"><span class="mk-cat-t">' + _mkEsc((e.date ? e.date + ' · ' : '') + (e.time_et || '—') + ' ET') + '</span>' +
      '<span class="mk-imp ' + _mkEsc(imp) + '" aria-hidden="true"></span>' +
      '<span class="mk-cat-b"><span class="mk-cat-h">' + _mkEsc(e.title || 'Untitled event') + '</span>' +
      '<span class="mk-cat-m">' + _mkEsc([imp.toUpperCase() + ' IMPACT', e.currency, e.note, e.source].filter(Boolean).join(' · ')) +
      '</span></span></div>';
  });
  if (!events.length) html += '<div class="mk-note"><b>No scheduled events loaded</b>The calendar source returned no events. NOVA will not invent an economic release.</div>';
  html += '</section><section class="mk-news-section"><div class="mk-news-label">Full live coverage · war, macro, policy &amp; finance</div>' +
    '<div class="mk-all-news">' + (ranked.length ? ranked.map(row).join('') :
      '<div class="mk-note"><b>Coverage unavailable</b>No current articles were returned.</div>') + '</div></section></div>';
  if (!events.length && !news.length) {
    html += '<div class="mk-note"><b>Nothing live right now</b>Both collections are empty — quiet tape, not a failure.</div>';
  }
  body.innerHTML = html;
}

// Market Structure. Levels come from /market-structure, sweep status from
// /liquidity. If liquidity is missing the levels still draw, but every one is
// marked unclassified -- a guessed sweep state would be worse than none.
function _mkRenderStructure() {
  const body = document.getElementById('mkStructBody');
  const symEl = document.getElementById('mkStructSym');
  if (!body) return;
  if (symEl) symEl.textContent = _mkSym;
  document.querySelectorAll('.mk-switch [data-mk-sym]').forEach(b => {
    b.setAttribute('aria-pressed', String(b.dataset.mkSym === _mkSym));
  });

  const ms = _lastMarketStructure;
  const liq = _lastLiquidity;
  if (!ms) {
    body.innerHTML = _structureFetchFailed
      ? '<div class="mk-note err"><b>Structure unavailable</b><code>/market-structure</code> did not ' +
        'respond. No levels are drawn — a level ladder with no price reference would mislead.</div>'
      : '<div class="mk-skel-rows"><i></i><i></i><i></i></div>';
    return;
  }
  const key = _mkSym.toLowerCase();
  const d = ms[key] || {};
  const lq = (liq || {})[key] || {};
  // The last price lives on /liquidity. When that route is down the dashboard
  // payload's market_snapshot carries the same quote -- but only as DEGRADED
  // data: it is used solely when its own freshness can be established, and it
  // is never presented as the live price.
  const riskObj = (_lastDashData || {}).risk || {};
  const snap = riskObj.market_snapshot || {};
  const snapPx = (snap[_mkSym] || {}).last;
  const snapAt = riskObj.last_updated || null;
  let price = null, priceSrc = 'liquidity', priceAge = null;
  if (lq.price != null) {
    price = lq.price;
  } else if (snapPx != null && snapAt && _mkAge(snapAt)) {
    // A snapshot whose age cannot be established is not trustworthy enough to
    // anchor a level ladder, so it is refused rather than shown.
    price = snapPx;
    priceSrc = 'snapshot';
    priceAge = _mkAge(snapAt);
  }
  const levels = [];
  const add = (label, v) => { if (v != null && isFinite(v)) levels.push({label: label, price: +v}); };
  add('ONH', d.onh); add('ONL', d.onl); add('Daily open', d.daily_open);
  add('PDH', d.pdh); add('PDL', d.pdl); add('PWH', d.pwh); add('PWL', d.pwl);

  if (!levels.length || price == null || !isFinite(price)) {
    const noPrice = levels.length && price == null;
    body.innerHTML = noPrice
      ? '<div class="mk-note err"><b>Last price unavailable</b>' +
        '<code>/liquidity</code> did not respond and no snapshot with an establishable age is ' +
        'available, so the levels are not drawn against a price that cannot be trusted.</div>'
      : '<div class="mk-note"><b>No levels recorded yet</b>' +
        'The structure engine has not produced overnight or prior-session levels for ' +
        _mkEsc(_mkSym) + '. The ladder populates once a session completes.</div>';
    return;
  }

  const status = {};
  ((lq.levels) || []).forEach(l => { status[String(l.label).toUpperCase()] = String(l.status || '').toUpperCase(); });
  const haveStatus = Object.keys(status).length > 0;

  const all = levels.map(l => l.price).concat([price]);
  let hi = Math.max.apply(null, all), lo = Math.min.apply(null, all);
  const pad = Math.max((hi - lo) * 0.08, Math.abs(price) * 0.0005) || 1;
  hi += pad; lo -= pad;
  const span = (hi - lo) || 1;
  const pos = (v) => ((hi - v) / span * 100);

  const ticks = [0, 20, 40, 60, 80, 100].map(q => ({
    at: q, val: hi - (span * q / 100),
  }));
  const dp = Math.abs(price) < 100 ? 2 : 2;

  // Collision handling. A label is ~20px tall, and real level sets cluster --
  // ONH and the daily open can sit 4px apart. Each label takes the first lane
  // whose previous occupant is far enough away, so a run of three tight levels
  // spreads across three lanes instead of two of them landing on each other.
  const PLOT = 250, MIN = 22, LANES = 3;
  const drawn = levels.map(l => ({...l, at: pos(l.price)}))
    .sort((a, b) => a.at - b.at);
  const lastInLane = new Array(LANES).fill(-999);
  drawn.forEach(l => {
    const px = l.at / 100 * PLOT;
    let lane = 0;
    while (lane < LANES - 1 && (px - lastInLane[lane]) < MIN) lane++;
    l.lane = lane;
    lastInLane[lane] = px;
  });

  let html = '<div class="mk-lad">';
  html += '<div class="mk-lad-y">' + ticks.map(t =>
    '<span style="top:' + t.at + '%">' + _mkFmt(t.val, 0) + '</span>').join('') + '</div>';
  html += '<div class="mk-lad-plot">';
  html += ticks.map(t => '<i class="mk-gl" style="top:' + t.at + '%"></i>').join('');
  drawn.forEach(l => {
    const raw = status[l.label.toUpperCase()] || '';
    const cls = !haveStatus ? 'unknown' : (raw === 'SWEPT' ? 'swept' : 'untapped');
    const word = !haveStatus ? 'unclassified' : (raw === 'SWEPT' ? 'swept' : 'untapped');
    const dist = Math.round(l.price - price);
    // One pill per level. Placing a single element is what makes the lane
    // assignment sufficient; a separate right-anchored price would collide
    // again on its own axis.
    html += '<div class="mk-lvl ' + cls + '" style="top:' + l.at.toFixed(2) + '%;--lane:' + l.lane + '">' +
      '<i class="mk-lvl-bar"></i>' +
      '<span class="mk-lvl-tag">' + _mkEsc(l.label) +
      '<span class="mk-lvl-st"> · ' + word + '</span>' +
      '<span class="mk-lvl-px">' + _mkFmt(l.price, dp) +
      '<em>' + (dist >= 0 ? '+' : '−') + Math.abs(dist).toLocaleString('en-US') + ' pts</em></span>' +
      '</span></div>';
  });
  const fb = priceSrc === 'snapshot';
  html += '<div class="mk-lad-now' + (fb ? ' is-fallback' : '') + '" style="top:' + pos(price).toFixed(2) + '%">' +
    '<b>' + _mkFmt(price, dp) + (fb ? ' · Snapshot' : '') + '</b></div>';
  html += '</div></div>';
  html += '<div class="mk-lad-legend">' +
    '<span class="mk-lg ' + (fb ? 'f' : 'p') + '"><i></i>' +
      (fb ? 'Last price · snapshot, ' + priceAge + ' old' : 'Last price') + '</span>' +
    (haveStatus
      ? '<span class="mk-lg u"><i></i>Untapped level</span><span class="mk-lg s"><i></i>Swept level</span>'
      : '<span class="mk-lg n"><i></i>Level · sweep status unavailable</span>') +
    '</div>';

  const narrative = (liq && liq.narrative) || ms.narrative || '';
  if (narrative || !haveStatus || fb) {
    html += '<div class="mk-lad-note' + (fb ? ' degraded' : '') + '">' +
      (fb
        ? '<b>Degraded — last price is a snapshot, not live.</b> <code>/liquidity</code> did not respond, ' +
          'so the price shown comes from the dashboard <code>market_snapshot</code> taken ' +
          _mkEsc(priceAge) + ' ago, and sweep status is withdrawn: every level is drawn unclassified. '
        : (!haveStatus
          ? 'Levels rendered from <code>/market-structure</code>. Sweep status unavailable — ' +
            '<code>/liquidity</code> did not respond, so every level is drawn unclassified. '
          : '')) +
      _mkEsc(String(narrative).split('|')[0].trim()) + '</div>';
  }
  body.innerHTML = html;
}

function _mkRenderProv() {
  const el = document.getElementById('mkProv');
  if (!el) return;
  const q = _mkQuoteState();
  const qAge = _mkAge(_mkQuotesAt);
  const item = (k, v) => '<span>' + k + ' <b>' + _mkEsc(v) + '</b></span>';
  const msAge = _mkAge((_lastMarketStructure || {}).last_updated);
  const lqAge = _mkAge((_lastLiquidity || {}).last_updated);
  el.innerHTML =
    item('Quotes', q === 'live' ? 'live · ' + (qAge || 'now')
      : q === 'stale' ? 'cached · ' + (qAge || 'unknown age')
      : q === 'loading' ? 'loading' : q === 'error' ? 'unavailable' : 'live') +
    item('Structure', '/market-structure' + (msAge ? ' · ' + msAge + ' old' : '')) +
    item('Liquidity', '/liquidity' + (lqAge ? ' · ' + lqAge + ' old' : '')) +
    item('Calendar', ((_lastDashData || {}).calendar || {}).source || 'not available') +
    item('News', 'Finnhub') +
    item('Risk', 'News Guard');
}

function renderMarkets() {
  const clk = document.getElementById('mkClock');
  if (clk) {
    try {
      clk.textContent = 'NY ' + new Date().toLocaleTimeString('en-US',
        {timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false}) + ' ET';
    } catch (e) { clk.textContent = ''; }
  }
  const dash = _lastDashData;
  const risk = (dash || {}).risk || {};
  _mkSetFresh();
  // Session comes from the News Guard payload (risk.donna_session); the state
  // engine is the fallback. Neither is invented when both are absent.
  const sess = risk.donna_session || ((_dbStateEngine || {}).session) || '—';
  _mkRenderRail(risk, sess);
  _mkRenderPulse();
  _mkRenderVol();
  _mkRenderNews(dash);
  _mkRenderStructure();
  _mkRenderProv();
}

// NQ/ES switch and row selection. Selecting an instrument retargets the ladder
// when that instrument has structure; otherwise the selection is visual only.
document.addEventListener('click', (e) => {
  const t = e.target.closest ? e.target.closest('.mk-switch [data-mk-sym]') : null;
  if (t) { _mkSym = t.dataset.mkSym; _mkRenderStructure(); _mkRenderPulse(); return; }
  const row = e.target.closest ? e.target.closest('[data-mk-row]') : null;
  if (row) {
    const sym = _mkNorm(row.dataset.mkRow);
    if (sym === 'NQ' || sym === 'ES') { _mkSym = sym; _mkRenderStructure(); }
    document.querySelectorAll('[data-mk-row]').forEach(r => r.classList.remove('is-sel'));
    row.classList.add('is-sel');
  }
});
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const row = e.target.closest ? e.target.closest('[data-mk-row]') : null;
  if (!row) return;
  e.preventDefault();
  row.click();
});

// refresh signals when switching to signals tab. The approved Journal
// composition has no sub-tab bar, so this button may not exist -- an
// unguarded bind threw a TypeError at script load on every page view.
const _jSignalsTab = document.getElementById('jTab-signals');
if (_jSignalsTab) _jSignalsTab.addEventListener('click', () => refreshSignals());

// ════════ BOOT ════════
function todayDateStr() {
  return nyTodayDateStr();
}
document.getElementById('jDate').value = todayDateStr();
document.getElementById('jDate').dataset.autoDate = todayDateStr();

// First-load fade-in — applies once, removed after animation completes
document.body.classList.add('donna-first-load');
document.body.addEventListener('animationend', () => document.body.classList.remove('donna-first-load'), { once: true });

initTileEditors();
refresh();
setInterval(refresh, 30000);
refreshJournal();
setInterval(refreshJournal, 60000);
refreshJournalWorkspace();
refreshNewsFuturesStrip();
setInterval(refreshNewsFuturesStrip, 30000);
refreshTrendingMovers();
setInterval(refreshTrendingMovers, 5 * 60 * 1000);
refreshEconCalendar();
setInterval(refreshEconCalendar, 5 * 60 * 1000);
fetchStateEngine();
setInterval(fetchStateEngine, 15000);
dashClock();
setInterval(dashClock, 1000);
refreshMorningBrief();
// Session structure is fetched by refresh() (already called above) and on
// every subsequent 30s cycle -- no separate boot call, no extra timer.

'''
