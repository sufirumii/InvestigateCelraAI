// Shared helpers: DOM building, formatting, API access.

// ---------------------------------------------------------------- DOM
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k === 'text') el.textContent = v;
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const child of children.flat(3)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}

export const frag = (...nodes) => {
  const f = document.createDocumentFragment();
  nodes.flat(3).filter(Boolean).forEach(n => f.append(n));
  return f;
};

export function svgEl(tag, attrs = {}) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined) continue;
    el.setAttribute(k, v);
  }
  return el;
}

export const clear = node => { while (node.firstChild) node.removeChild(node.firstChild); return node; };

// ---------------------------------------------------------------- API
export async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (res.status === 401) { window.dispatchEvent(new CustomEvent('ic:gate')); throw new Error('locked'); }
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  const type = res.headers.get('content-type') || '';
  return type.includes('json') ? res.json() : res.text();
}

// ---------------------------------------------------------------- format
export const num = (v, d = 2) =>
  Number(v ?? 0).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });

export const pct = v => `${v > 0 ? '+' : ''}${num(v, 2)}%`;

export const dir = v => (v > 0.005 ? 'up' : v < -0.005 ? 'down' : 'flat');

// Compact age, e.g. "3h", "12d", "4mo". Always relative, never a calendar
// date: callers append the word "ago", and "May 14 ago" is not a sentence.
export function ago(iso) {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const mins = Math.max(0, (Date.now() - then.getTime()) / 60000);
  if (mins < 60) return `${Math.round(mins)}m`;
  if (mins < 1440) return `${Math.round(mins / 60)}h`;
  const days = Math.round(mins / 1440);
  if (days < 31) return `${days}d`;
  const months = Math.round(days / 30.44);
  if (months < 12) return `${months}mo`;
  return `${(days / 365.25).toFixed(days < 730 ? 1 : 0)}y`;
}

export const dateLong = iso => new Date(iso).toLocaleDateString(undefined, {
  weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
});

export const dateShort = iso => new Date(iso).toLocaleDateString(undefined, {
  day: 'numeric', month: 'short', year: 'numeric',
});

export const titleCase = s => (s || '').replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

export function debounce(fn, ms = 180) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

export function toast(message) {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 2600);
}

// ---------------------------------------------------------------- palette
export const KIND_COLOUR = {
  company: '#6b4ee6',
  asset: '#0f7d55',
  target: '#bf2d47',
  indication: '#b4560d',
  modality: '#2b6cb0',
  technology: '#7a3fa8',
  trial: '#55545f',
};

export const kindColour = kind => KIND_COLOUR[kind] || '#8b8996';
