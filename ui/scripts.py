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
    if (btn.dataset.page === 'journal') { refreshJournal(); switchJTab('trades'); }
    if (btn.dataset.page === 'settings') { refreshSettings(); }
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
  ['sidebarStatus', 'ovIdentityStatus'].forEach(id => {
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
async function refreshSettings() {
  try {
    const [envRes, healthRes] = await Promise.all([fetch('/check-env'), fetch('/system-health')]);
    const env    = envRes.ok    ? await envRes.json()    : {};
    const health = healthRes.ok ? await healthRes.json() : {};


    const rows = [
      ['Anthropic (Claude)', env.anthropic_key_found],
      ['Telegram',           env.telegram_found],
      ['Finnhub',            env.finnhub_found],
      ['FMP',                env.fmp_found],
      ['Discord (Macro)',    env.macro_discord_available],
    ];
    setHtml('setIntegrations', rows.map(([label, ok]) => `
      <div class="exec-row">
        <span class="exec-row-label">${label}</span>
        <span class="exec-row-val" style="color:${ok ? 'var(--green)' : 'var(--muted2)'}">${ok ? 'CONNECTED' : '—'}</span>
      </div>`).join(''));

    setText('setChatModel',  env.chat_model || '—');
    setText('setFastModel',  env.fast_model || '—');
    setText('setServerTime', health.last_time_ny ? health.last_time_ny.substring(0,19).replace('T',' ') : '—');
  } catch(e) { console.error('refreshSettings:', e); }
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
    el.innerHTML = `<span class="role">NOVA</span>${text}<div><span class="msg-tag ${resolvedTag}">${resolvedTag}</span></div>`;
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
        const isAuto     = ['NOVA_AUTO','DONNA_AUTO','NOVA_AUTO_RECONSTRUCTED','DONNA_AUTO_RECONSTRUCTED'].includes(t.source);

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
  const loading = document.getElementById(\'novaMarketSummaryLoading\');
  const textEl  = document.getElementById(\'novaMarketSummaryText\');
  const errEl   = document.getElementById(\'novaMarketSummaryError\');
  if (errEl)  { errEl.style.display = \'none\'; errEl.textContent = \'\'; }
  if (textEl) { textEl.style.display = \'none\'; textEl.textContent = \'\'; }
  if (loading) loading.style.display = \'block\';
  if (btn) { btn.disabled = true; btn.textContent = \'GENERATING...\'; }
  try {
    const res  = await fetch(\'/market-summary\', {method: \'POST\'});
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.status === \'ok\') {
      if (textEl) { textEl.textContent = data.summary; textEl.style.display = \'block\'; }
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
  const stats  = data.stats  || {};
  const trades = data.trades || [];
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
  const trades = data.trades || [];
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

async function refreshJournal() {
  try {
    const res = await fetch('/journal/data');
    if (!res.ok) return;
    const data = await res.json();
    renderJournal(data);
    renderOverviewAccountSummary(data);
    renderOverviewRecentActivity(data);
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
