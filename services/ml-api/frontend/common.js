// ── Config ──────────────────────────────────────────────────
let API = '';         // same origin; ml-api serves frontend
let VISION_API = '';  // ml-vision base URL — injected via window.__ML_URLS__
let EDA_API    = '';  // ml-eda base URL — injected via window.__ML_URLS__

// ── Analytics tracking ───────────────────────────────────────
const _TRACK_URL = 'https://ml-portfolio-rho.vercel.app/api/track';
function _getSession() {
  let id = localStorage.getItem('_ml_session');
  if (!id) { id = crypto.randomUUID(); localStorage.setItem('_ml_session', id); }
  return id;
}
function _track(type, meta) {
  try {
    fetch(_TRACK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, path: (typeof APP_MODE !== 'undefined' && APP_MODE === 'eda' ? '/eda' : typeof APP_MODE !== 'undefined' && APP_MODE === 'vision' ? '/vision' : '/'), session_id: _getSession(), referrer: document.referrer, meta: meta || {} }),
    }).catch(() => {});
  } catch(_) {}
}

// ── Service URL injection ────────────────────────────────────
// Priority 1: window.__ML_URLS__ is set by an inline <script> that app.py
//             string-replaces before serving — so common.js (a static file)
//             stays untouched on disk.
async function initServiceUrls() {
  if (window.__ML_URLS__) {
    if (window.__ML_URLS__.vision && window.__ML_URLS__.vision !== '__VISION_URL__') {
      VISION_API = window.__ML_URLS__.vision.replace(/\/$/, '');
    }
    if (window.__ML_URLS__.eda && window.__ML_URLS__.eda !== '__EDA_URL__') {
      EDA_API = window.__ML_URLS__.eda.replace(/\/$/, '');
    }
    return;
  }
  // Priority 2: /app-config endpoint (dev / direct static-file access)
  try {
    const r = await fetch('/app-config');
    if (r.ok) {
      const cfg = await r.json();
      if (cfg.vision_url) VISION_API = cfg.vision_url.replace(/\/$/, '');
      if (cfg.eda_url)    EDA_API    = cfg.eda_url.replace(/\/$/, '');
    }
  } catch (_) {}
}
initServiceUrls();

// ── App mode ─────────────────────────────────────────────────
// ── App mode: read ?mode=ml | ?mode=vision | (none = all) ─────
const APP_MODE = new URLSearchParams(window.location.search).get('mode') || 'ml';
// Reflect mode in nav title immediately
(function applyNavMode() {
  const titleEl = document.getElementById('nav-title-el');
  const subEl   = document.getElementById('nav-sub-el');
  if (APP_MODE === 'vision') {
    if (titleEl) titleEl.textContent = 'ML Vision';
    if (subEl)   subEl.textContent   = 'Computer Vision Platform';
    document.title = 'ML Vision — Computer Vision Platform';
  } else if (APP_MODE === 'ml') {
    if (titleEl) titleEl.textContent = 'ML Unified';
    if (subEl)   subEl.textContent   = 'Multi-Model Predictor';
    document.title = 'ML Unified — Multi-Model Predictor';
  } else if (APP_MODE === 'eda') {
    if (titleEl) titleEl.textContent = 'EDA Explorer';
    if (subEl)   subEl.textContent   = 'Exploratory Data Analysis';
    document.title = 'EDA Explorer — Dataset Inspector';
  }
})();

// ── Theme system ──────────────────────────────────────────────
const THEMES = {
  dark:     { label: 'Dark',     gradient: 'linear-gradient(135deg,#818cf8,#34d399)' },
  light:    { label: 'Light',    gradient: 'linear-gradient(135deg,#6366f1,#10b981)' },
  midnight: { label: 'Midnight', gradient: 'linear-gradient(135deg,#a855f7,#f43f5e)' },
  ocean:    { label: 'Ocean',    gradient: 'linear-gradient(135deg,#0ea5e9,#64ffda)'  },
  sunset:   { label: 'Sunset',   gradient: 'linear-gradient(135deg,#f97316,#fbbf24)'  },
  forest:   { label: 'Forest',   gradient: 'linear-gradient(135deg,#22c55e,#06b6d4)'  },
};
function setThemeChoice(t) {
  if (!THEMES[t]) t = 'dark';
  document.documentElement.setAttribute('data-theme', t);
  // Update picker button label + swatch
  const lbl    = document.getElementById('themePickerLabel');
  const swatch = document.getElementById('themePickerSwatch');
  if (lbl)    lbl.textContent = THEMES[t].label;
  if (swatch) swatch.style.background = THEMES[t].gradient;
  // Mark active option
  document.querySelectorAll('.theme-option[data-theme-opt]').forEach(el => {
    el.classList.toggle('active', el.dataset.themeOpt === t);
  });
  // Close dropdown
  const dd = document.getElementById('themePickerDropdown');
  if (dd) dd.classList.remove('open');
  try { localStorage.setItem('theme', t); } catch(e) {}
}
function toggleThemePicker() {
  const dd = document.getElementById('themePickerDropdown');
  if (dd) dd.classList.toggle('open');
}
// Close picker on outside click
document.addEventListener('click', e => {
  const wrap = document.getElementById('themePickerWrap');
  if (wrap && !wrap.contains(e.target)) {
    const dd = document.getElementById('themePickerDropdown');
    if (dd) dd.classList.remove('open');
  }
});
// Legacy compat
function setTheme(t) { setThemeChoice(t); }
function toggleTheme() {
  const cur  = document.documentElement.getAttribute('data-theme') || 'dark';
  const keys = Object.keys(THEMES);
  setThemeChoice(keys[(keys.indexOf(cur) + 1) % keys.length]);
}
(function () {
  const params   = new URLSearchParams(window.location.search);
  const urlTheme = params.get('theme');
  if (urlTheme && THEMES[urlTheme]) {
    setThemeChoice(urlTheme);
    params.delete('theme');
    history.replaceState(null, '', window.location.pathname + (params.toString() ? '?' + params : ''));
  } else {
    try {
      const saved = localStorage.getItem('theme');
      setThemeChoice(saved && THEMES[saved] ? saved : 'dark');
    } catch(e) { setThemeChoice('dark'); }
  }
})();

// ── Legacy palette (URL ?palette= still works) ────────────────
const VALID_PALETTES = ['cosmic', 'sunset', 'aurora', 'ocean'];
function setPalette(p) {
  if (p && p !== 'cosmic') {
    document.documentElement.setAttribute('data-palette', p);
  } else {
    document.documentElement.removeAttribute('data-palette');
  }
}
(function () {
  const params = new URLSearchParams(window.location.search);
  const urlPalette = params.get('palette');
  if (urlPalette && VALID_PALETTES.includes(urlPalette)) {
    setPalette(urlPalette);
    try { localStorage.setItem('palette', urlPalette); } catch(e) {}
    params.delete('palette');
    const qs = params.toString();
    history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
  } else {
    try { const saved = localStorage.getItem('palette'); if (saved && VALID_PALETTES.includes(saved)) setPalette(saved); } catch(e) {}
  }
})();

// ── Boot retry helper ────────────────────────────────────────
async function fetchWithRetry(url, maxRetries = 4, delayMs = 12000) {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(url);
      return res;
    } catch(e) {
      if (attempt === maxRetries) throw e;
      const msg = document.getElementById('loadingMsg');
      const remaining = (maxRetries - attempt);
      if (msg) msg.textContent = `Server waking up — retrying in ${delayMs/1000}s… (${remaining} attempt${remaining !== 1 ? 's' : ''} left)`;
      await new Promise(r => setTimeout(r, delayMs));
    }
  }
}

// ── Ambient color helpers ─────────────────────────────────────
function hexToRgba(hex, alpha) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
function setAmbientTheme(c1, c2) {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const dim = rgba => rgba.replace(/([\d.]+)\)$/, (_, a) => (parseFloat(a) * 0.45).toFixed(3) + ')');
  const b1 = document.querySelector('.bg-blob-1');
  const b2 = document.querySelector('.bg-blob-2');
  if (b1) b1.style.background = isLight ? dim(c1) : c1;
  if (b2) b2.style.background = isLight ? dim(c2) : c2;
}
function setAmbientFromAccent(hex) {
  setAmbientTheme(hexToRgba(hex, 0.14), hexToRgba(hex, 0.09));
}
const AMBIENT_DEFAULT = ['rgba(99,102,241,0.14)', 'rgba(56,189,248,0.11)'];

// ── Animation helpers ─────────────────────────────────────────

function animateSidebarIn() {
  const items = document.querySelectorAll('#sidebar .model-btn, #sidebar .sidebar-label');
  items.forEach((el, i) => {
    el.classList.add('sb-anim');
    setTimeout(() => el.classList.add('sb-visible'), i * 55 + 30);
  });
}

function animateMainOut() {
  const main = document.getElementById('main');
  if (!main) return Promise.resolve();
  return new Promise(resolve => {
    main.style.transition = 'opacity 0.14s ease, transform 0.14s ease';
    main.style.opacity    = '0';
    main.style.transform  = 'translateY(-6px)';
    setTimeout(resolve, 140);
  });
}

function animateMainIn() {
  const main = document.getElementById('main');
  if (!main) return;
  main.style.transition = 'none';
  main.style.opacity    = '0';
  main.style.transform  = 'translateY(16px)';
  void main.offsetWidth;
  main.style.transition = 'opacity 0.38s cubic-bezier(0.22,1,0.36,1), transform 0.38s cubic-bezier(0.22,1,0.36,1)';
  main.style.opacity    = '1';
  main.style.transform  = 'translateY(0)';
}

function countUpMetricPill() {
  const el = document.querySelector('.metric-val');
  if (!el) return;
  const raw = el.textContent.trim();
  const num = parseFloat(raw.replace(/[^0-9.]/g, ''));
  if (isNaN(num)) return;
  const prefix = raw.match(/^[^0-9]*/)?.[0] || '';
  const suffix = raw.match(/[^0-9.]+$/)?.[0] || '';
  const dec    = (raw.replace(/[^0-9.]/g,'').split('.')[1] || '').length;
  const start  = performance.now();
  const dur    = 600;
  (function tick(now) {
    const t = Math.min((now - start) / dur, 1);
    const ease = 1 - Math.pow(1 - t, 3);
    el.textContent = prefix + (num * ease).toFixed(dec) + suffix;
    if (t < 1) requestAnimationFrame(tick);
  })(performance.now());
}

function countUp(el, endVal, prefix, duration) {
  const dec = endVal % 1 === 0 ? 0 : 0;
  const start = performance.now();
  (function tick(now) {
    const t    = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - t, 3);
    const cur  = endVal * ease;
    el.textContent = prefix + cur.toLocaleString('en-IN', { maximumFractionDigits: 0 });
    if (t < 1) requestAnimationFrame(tick);
  })(performance.now());
}

// ── Particle background ────────────────────────────────────────
(function initParticles() {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, pts;
  const N = 65, CONN = 130, REPEL = 110;
  const mouse = { x: -999, y: -999 };

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function spawn() {
    pts = Array.from({ length: N }, () => {
      const x = Math.random() * W, y = Math.random() * H;
      return { x, y, ox: x, oy: y, vx: 0, vy: 0, r: Math.random() * 1.2 + 0.5 };
    });
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    const dark = document.documentElement.getAttribute('data-theme') !== 'light';
    const dotColor  = dark ? '129,140,248' : '99,102,241';
    const lineColor = dark ? '129,140,248' : '99,102,241';

    pts.forEach(p => {
      const dx = p.x - mouse.x, dy = p.y - mouse.y;
      const d  = Math.sqrt(dx * dx + dy * dy);
      if (d < REPEL && d > 0) {
        const f = ((REPEL - d) / REPEL) * 1.2;
        p.vx += (dx / d) * f;
        p.vy += (dy / d) * f;
      }
      p.vx += (p.ox - p.x) * 0.018;
      p.vy += (p.oy - p.y) * 0.018;
      p.vx *= 0.82; p.vy *= 0.82;
      p.x  += p.vx;  p.y  += p.vy;
    });

    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const dx = pts[i].x - pts[j].x, dy = pts[i].y - pts[j].y;
        const d  = Math.sqrt(dx * dx + dy * dy);
        if (d < CONN) {
          ctx.globalAlpha = (1 - d / CONN) * (dark ? 0.35 : 0.28);
          ctx.strokeStyle = `rgba(${lineColor},1)`;
          ctx.lineWidth   = 0.8;
          ctx.beginPath();
          ctx.moveTo(pts[i].x, pts[i].y);
          ctx.lineTo(pts[j].x, pts[j].y);
          ctx.stroke();
        }
      }
    }

    pts.forEach(p => {
      ctx.globalAlpha = dark ? 0.65 : 0.55;
      ctx.fillStyle   = `rgba(${dotColor},1)`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
    requestAnimationFrame(draw);
  }

  window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
  window.addEventListener('resize',    () => { resize(); spawn(); });
  resize(); spawn(); draw();
})();

// ── SSE streaming helpers ─────────────────────────────────────────────────────
async function* _sseStream(response) {
  const reader  = response.body.getReader();
  const decoder = new TextDecoder();
  let   buffer  = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { yield JSON.parse(line.slice(6)); } catch {}
      }
    }
  }
  if (buffer.startsWith('data: ')) {
    try { yield JSON.parse(buffer.slice(6)); } catch {}
  }
}

function _progressBarHTML(fillId, msgId, pctId) {
  return `<div class="sse-progress">
    <div class="sse-progress-track"><div class="sse-progress-fill" id="${fillId}" style="width:4%"></div></div>
    <div class="sse-progress-row">
      <span class="sse-progress-msg" id="${msgId}">Starting…</span>
      <span class="sse-progress-pct" id="${pctId}">0%</span>
    </div>
  </div>`;
}

function _updateProgressBar(fillId, msgId, pctId, pct, msg) {
  const fill  = document.getElementById(fillId);
  const msgEl = document.getElementById(msgId);
  const pctEl = document.getElementById(pctId);
  if (fill)  fill.style.width  = Math.max(4, pct) + '%';
  if (msgEl) msgEl.textContent = msg || '';
  if (pctEl) pctEl.textContent = pct + '%';
}

