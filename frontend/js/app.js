// Application shell: boot, routing, navigation, command palette.

import { api, h, clear, debounce, dateShort, toast } from './util.js';
import { openStory, closeReader } from './components.js';
import { runOnboarding, splashFloor } from './onboarding.js';
import { frontPage } from './views/frontpage.js';
import { signals } from './views/signals.js';
import { markets } from './views/markets.js';
import { setbacks } from './views/setbacks.js';
import { company } from './views/company.js';
import { value, method } from './views/pages.js';

const ICONS = {
  front: 'M3 4h18M3 9h11M3 14h11M3 19h18M17 9h4v10h-4z',
  signals: 'M3 17l5-6 4 4 5-8 4 5',
  markets: 'M4 19V9M9 19V5M14 19v-7M19 19v-4',
  setbacks: 'M12 3l9 16H3zM12 9v5M12 17h.01',
  value: 'M12 3l2.6 5.9 6.4.6-4.8 4.3 1.4 6.2L12 16.8 6.4 20l1.4-6.2L3 9.5l6.4-.6z',
  method: 'M9 3h6l.6 3 2.6 1.5 2.8-1 3 5.2-2.3 2v3l2.3 2-3 5.2-2.8-1L15.6 21 15 24H9',
};

const NAV = [
  { id: 'front', hash: '#/', label: 'Front page', icon: ICONS.front },
  { id: 'signals', hash: '#/signals', label: 'Signals', icon: ICONS.signals, tally: m => m.stats.analysed },
  { id: 'markets', hash: '#/markets', label: 'Momentum', icon: ICONS.markets, tally: m => m.stats.companies },
  { id: 'setbacks', hash: '#/setbacks', label: 'Setbacks', icon: ICONS.setbacks, tally: m => m.stats.setbacks },
  { id: 'value', hash: '#/value', label: 'Why Excelra', icon: ICONS.value },
  { id: 'method', hash: '#/method', label: 'Method', icon: ICONS.method },
];

const state = { meta: null };

// ---------------------------------------------------------------- boot
async function boot() {
  const splashStart = Date.now();
  try {
    state.meta = await api('/api/meta');
  } catch {
    document.getElementById('splash').innerHTML =
      '<div class="empty"><b>The desk is not responding</b><span>Start the backend with <code>uvicorn investigatecelra.main:app</code> and reload.</span></div>';
    return;
  }

  if (state.meta.gateEnabled && !(await unlocked())) { showGate(); return; }

  // The splash is a floor, not a fixed delay: if the API was slow it has
  // already elapsed and we continue immediately.
  await splashFloor(splashStart);

  if (!state.meta.preferences?.configured) {
    document.getElementById('splash').classList.add('done');
    await runOnboarding();
    state.meta = await api('/api/meta');
    start({ instant: true });
    return;
  }
  start();
}

async function unlocked() {
  try { await api('/api/health'); await api('/api/edition'); return true; } catch { return false; }
}

function showGate() {
  document.getElementById('splash').classList.add('done');
  const gate = document.getElementById('gate');
  gate.classList.remove('hidden');
  document.getElementById('gate-form').addEventListener('submit', async e => {
    e.preventDefault();
    const err = document.getElementById('gate-err');
    err.textContent = '';
    try {
      await api('/api/session', { method: 'POST', body: { code: document.getElementById('gate-input').value } });
      gate.classList.add('hidden');
      start();
    } catch {
      err.textContent = 'That code was not accepted. Check with your desk administrator.';
    }
  });
}

function start({ instant = false } = {}) {
  document.getElementById('shell').classList.remove('hidden');
  buildNav();
  paintStatus();
  wireChrome();
  window.addEventListener('hashchange', route);
  route();
  if (instant) document.getElementById('splash').classList.add('done');
  else setTimeout(() => document.getElementById('splash').classList.add('done'), 320);
}

// ---------------------------------------------------------------- nav
function buildNav() {
  const nav = clear(document.getElementById('nav'));
  NAV.forEach(entry => {
    const tally = entry.tally?.(state.meta);
    nav.append(h('a', { href: entry.hash, dataset: { id: entry.id } },
      h('span', { html: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="${entry.icon}"/></svg>` }),
      entry.label,
      tally ? h('span', { class: 'tally', text: String(tally) }) : null,
    ));
  });
}

function paintStatus() {
  const m = state.meta;
  const el = document.getElementById('rail-status');
  const prefs = m.preferences || {};
  clear(el).append(
    h('div', {}, h('b', { text: `${m.stats.sources || 0} sources` })),
    h('div', { text: `Updated ${dateShort(m.generatedAt)}` }),
    prefs.configured
      ? h('button', {
          class: 'link-quiet', type: 'button',
          onclick: async () => { await runOnboarding(); state.meta = await api('/api/meta'); paintStatus(); buildNav(); route(true); },
          text: 'Adjust priorities',
        })
      : null,
  );
}

function wireChrome() {
  document.getElementById('reader-close').addEventListener('click', closeReader);
  document.getElementById('scrim').addEventListener('click', closeReader);

  document.getElementById('refresh-btn').addEventListener('click', async e => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = 'Refreshing…';
    try {
      const res = await api('/api/refresh', { method: 'POST' });
      state.meta = await api('/api/meta');
      paintStatus();
      buildNav();
      toast(res.new > 0
        ? `${res.new} new stories from ${Object.keys(res.perSource).length} sources`
        : 'Sources checked — nothing new since the last run');
      route(true);
    } catch {
      toast('Refresh failed. The desk kept the last good edition.');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Refresh sources';
    }
  });

  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); }
    if (e.key === 'Escape') { closePalette(); closeReader(); }
  });
}

// ---------------------------------------------------------------- router
const ctx = {
  get meta() { return state.meta; },
  query: new URLSearchParams(),
  go: hash => { window.location.hash = hash; },
  open: id => openStory(id, { onNavigate: hash => { closeReader(); window.location.hash = hash; } }),
  reload: () => route(true),
};

async function route(force = false) {
  const raw = window.location.hash.slice(1) || '/';
  const [path, search] = raw.split('?');
  ctx.query = new URLSearchParams(search || '');
  const parts = path.split('/').filter(Boolean);
  const head = parts[0] || 'front';

  document.querySelectorAll('#nav a').forEach(a => {
    const id = a.dataset.id;
    a.classList.toggle('on', id === head || (head === 'front' && id === 'front') ||
      (head === 'company' && id === 'markets'));
  });

  const host = document.getElementById('view');
  clear(host).append(
    h('div', { class: 'classbar' },
      state.meta.preferences?.analyst
        ? h('span', { class: 'whose', text: `${state.meta.preferences.analyst}'s desk` })
        : null,
      h('span', { class: 'spacer' }),
      h('button', { class: 'searchbox', type: 'button', onclick: openPalette },
        h('span', { html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>' }),
        'Search the desk',
        h('kbd', { text: navigator.platform.includes('Mac') ? '⌘K' : 'Ctrl K' })),
    ),
    h('div', { class: 'skeleton', style: 'height:220px;margin-bottom:24px' }),
    h('div', { class: 'skeleton', style: 'height:120px' }),
  );

  let node;
  try {
    if (head === 'front') node = await frontPage(ctx);
    else if (head === 'signals') node = await signals(ctx);
    else if (head === 'markets') node = await markets(ctx);
    else if (head === 'setbacks') node = await setbacks(ctx);
    else if (head === 'value') node = await value(ctx);
    else if (head === 'method') node = await method(ctx);
    else if (head === 'company') node = await company(ctx, decodeURIComponent(parts.slice(1).join('/')));
    else node = h('div', { class: 'empty' }, h('b', { text: 'No such section' }),
      h('span', { text: 'Use the navigation on the left to get back to the edition.' }));
  } catch (err) {
    node = h('div', { class: 'empty' },
      h('b', { text: 'That view could not be built' }),
      h('span', { text: String(err.message || err) }));
  }

  const bar = host.firstChild;
  clear(host).append(bar, node);
  host.scrollTop = 0;
  window.scrollTo({ top: 0, behavior: force ? 'auto' : 'auto' });
}

// ---------------------------------------------------------------- palette
const palette = () => document.getElementById('palette');

function openPalette() {
  palette().classList.add('open');
  const input = document.getElementById('pal-input');
  input.value = '';
  input.focus();
  clear(document.getElementById('pal-results')).append(
    h('div', { class: 'pal-empty', text: 'Type a company, target, indication or headline.' }));
}

function closePalette() { palette().classList.remove('open'); }

palette().addEventListener('click', e => { if (e.target === palette()) closePalette(); });

document.getElementById('pal-input').addEventListener('input', debounce(async e => {
  const q = e.target.value.trim();
  const box = clear(document.getElementById('pal-results'));
  if (q.length < 2) {
    box.append(h('div', { class: 'pal-empty', text: 'Keep typing…' }));
    return;
  }
  const res = await api(`/api/search?q=${encodeURIComponent(q)}`);
  const rows = [
    ...res.companies.map(c => ({
      t: c.name, s: `Company · ${c.sector}`, go: () => { closePalette(); window.location.hash = `#/company/${encodeURIComponent(c.id)}`; },
    })),
    ...res.entities.slice(0, 5).map(en => ({
      t: en.name, s: `${en.kind} · named in ${en.mentions} stor${en.mentions === 1 ? 'y' : 'ies'}`,
      go: () => { closePalette(); window.location.hash = `#/signals?q=${encodeURIComponent(en.name)}`; },
    })),
    ...res.items.slice(0, 10).map(i => ({
      t: i.title, s: `${i.classification.label} · ${i.source.name}`,
      go: () => { closePalette(); ctx.open(i.id); },
    })),
  ];
  if (!rows.length) {
    box.append(h('div', { class: 'pal-empty', text: `Nothing in the corpus matches “${q}”.` }));
    return;
  }
  rows.forEach(r => box.append(h('button', { class: 'pal-item', type: 'button', onclick: r.go },
    h('span', { class: 't', text: r.t }), h('span', { class: 's', text: r.s }))));
}, 160));

window.addEventListener('ic:gate', () => window.location.reload());

boot();
