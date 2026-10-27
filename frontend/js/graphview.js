// Knowledge graph renderer.
//
// Four layouts over the same data. Each is a pure function from the node list
// to positions — no stored coordinates, no hand-placed nodes, nothing tuned to
// a particular dataset. Geometry is derived from node count and degree, so the
// same code lays out twelve nodes or four hundred.
//
//   force   velocity Verlet: repulsion, springs, centring, plus a light
//           same-kind clustering term that stops the hairball
//   radial  concentric rings by node kind, ordered by degree
//   arc     one axis, grouped by kind, edges drawn as arcs above the line
//   grid    columns by kind, sorted by degree — the readable fallback
//
// Pan and zoom are applied to a single transform group so hit-testing and
// dragging stay correct at any scale.

import { svgEl, kindColour, titleCase } from './util.js';

export const LAYOUTS = [
  { id: 'force', label: 'Force', hint: 'Clusters emerge from the connections themselves' },
  { id: 'radial', label: 'Radial', hint: 'Concentric rings, one per entity type' },
  { id: 'arc', label: 'Arc', hint: 'Single axis grouped by type, edges as arcs' },
  { id: 'grid', label: 'Columns', hint: 'One column per type, ranked by connections' },
];

const MIN_ZOOM = 0.35;
const MAX_ZOOM = 4;

export function createGraph(svg, { onSelect, onExpand } = {}) {
  // Hover card, positioned against the stage rather than the SVG so it is not
  // affected by pan or zoom. Created once and reused.
  const host = svg.parentElement;
  if (host && getComputedStyle(host).position === 'static') host.style.position = 'relative';
  const card = document.createElement('div');
  card.className = 'gcard';
  card.setAttribute('aria-hidden', 'true');
  host?.append(card);

  let data = { nodes: [], edges: [], legend: [] };
  let layout = 'force';
  let hidden = new Set();
  let focus = null;
  let view = { x: 0, y: 0, k: 1 };
  let W = 1000;
  let H = 680;

  let nodes = [];
  let edges = [];
  let nodeEls = [];
  let edgeEls = [];
  let root = null;
  let dragging = null;
  let panning = null;

  function measure() {
    const box = svg.getBoundingClientRect();
    W = Math.max(520, Math.round(box.width) || 1000);
    H = Math.max(420, Math.round(box.height) || 680);
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  }

  function setData(next, { keepView = false } = {}) {
    data = next || { nodes: [], edges: [], legend: [] };
    if (!keepView) view = { x: 0, y: 0, k: 1 };
    render();
  }

  function setLayout(next) { layout = next; render(); }
  function setHidden(next) { hidden = next; render(); }
  function setFocus(id) { focus = id; render(); }
  function getLayout() { return layout; }
  function reset() { view = { x: 0, y: 0, k: 1 }; render(); }

  function zoomBy(factor, cx = W / 2, cy = H / 2) {
    const k = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, view.k * factor));
    view.x = cx - ((cx - view.x) / view.k) * k;
    view.y = cy - ((cy - view.y) / view.k) * k;
    view.k = k;
    applyView();
  }

  function applyView() {
    root?.setAttribute('transform', `translate(${view.x},${view.y}) scale(${view.k})`);
    svg.style.setProperty('--label-scale', (1 / view.k).toFixed(3));
  }

  function render() {
    measure();
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const visible = data.nodes.filter(n => !hidden.has(n.kind));
    if (!visible.length) {
      const t = svgEl('text', {
        x: W / 2, y: H / 2, 'text-anchor': 'middle',
        fill: '#8b8996', 'font-size': 14,
      });
      t.textContent = data.nodes.length
        ? 'Every entity type is hidden. Re-enable one in the legend.'
        : 'No entities yet.';
      svg.append(t);
      return;
    }

    nodes = visible.map(n => ({ ...n, r: radius(n), vx: 0, vy: 0, x: 0, y: 0 }));
    const index = new Map(nodes.map(n => [n.id, n]));
    edges = data.edges
      .filter(e => index.has(e.source) && index.has(e.target))
      .map(e => ({ ...e, s: index.get(e.source), t: index.get(e.target) }));

    place(nodes, edges, layout, W, H);
    fitToStage(nodes, W, H);

    root = svgEl('g', { class: 'gviewport' });
    const edgeLayer = svgEl('g', { class: 'gedges' });
    const nodeLayer = svgEl('g', { class: 'gnodes' });
    root.append(edgeLayer, nodeLayer);
    svg.append(root);

    edgeEls = edges.map(e => {
      const el = svgEl(layout === 'arc' ? 'path' : 'line', {
        class: 'gedge',
        'stroke-width': Math.min(3.2, 0.7 + (e.weight || 1) * 0.45),
      });
      const title = svgEl('title');
      title.textContent = `${e.s.label} —${e.rel || 'RELATED'}→ ${e.t.label}`;
      el.append(title);
      edgeLayer.append(el);
      return { e, el };
    });

    // Greedy label placement, biggest nodes first: a label is drawn only if
    // its box clears every label already placed. Prevents the overlapping
    // text that makes a dense graph unreadable, without hiding labels
    // arbitrarily — the most connected entities always keep theirs.
    const placed = [];
    const labelled = new Set();
    [...nodes]
      .sort((a, b) => b.r - a.r || (b.degree || 0) - (a.degree || 0))
      .forEach(n => {
        const text = n.label.length > 24 ? `${n.label.slice(0, 23)}…` : n.label;
        const halfW = text.length * 3.05 + 4;
        const box = { x1: n.x - halfW, x2: n.x + halfW, y1: n.y + n.r + 5, y2: n.y + n.r + 18 };
        const clash = placed.some(b => !(box.x2 < b.x1 || box.x1 > b.x2 || box.y2 < b.y1 || box.y1 > b.y2));
        if (!clash || n.id === focus) { placed.push(box); labelled.add(n.id); }
      });

    nodeEls = nodes.map(n => {
      const g = svgEl('g', {
        class: `gnode${n.id === focus ? ' focused' : ''}`,
        tabindex: '0', role: 'button',
        'aria-label': `${n.label}, ${n.kind}, ${n.degree || 0} connections`,
      });
      const halo = svgEl('circle', { class: 'halo', r: n.r + 7, fill: kindColour(n.kind) });
      const circle = svgEl('circle', {
        class: 'disc', r: n.r, fill: kindColour(n.kind),
        stroke: n.id === focus ? '#000' : '#fff',
        'stroke-width': n.id === focus ? 2.6 : 1.6,
      });
      const title = svgEl('title');
      title.textContent = `${n.label} · ${titleCase(n.kind)} · ${n.degree || 0} connections`;
      g.append(halo, circle, title);

      if (labelled.has(n.id)) {
        const label = svgEl('text', { class: 'glabel', y: n.r + 14, 'text-anchor': 'middle' });
        label.textContent = n.label.length > 24 ? `${n.label.slice(0, 23)}…` : n.label;
        g.append(label);
      }

      g.addEventListener('click', ev => { ev.stopPropagation(); onSelect?.(n); });
      g.addEventListener('dblclick', ev => { ev.stopPropagation(); onExpand?.(n); });
      g.addEventListener('keydown', ev => {
        if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onSelect?.(n); }
      });
      g.addEventListener('pointerenter', ev => { highlight(n.id); showCard(n, ev); });
      g.addEventListener('pointermove', ev => moveCard(ev));
      g.addEventListener('pointerleave', () => { highlight(null); hideCard(); });
      g.addEventListener('focus', () => { highlight(n.id); showCard(n, null, g); });
      g.addEventListener('blur', () => { highlight(null); hideCard(); });
      nodeLayer.append(g);
      return { n, g };
    });

    paint();
    applyView();
  }

  function paint() {
    edgeEls.forEach(({ e, el }) => {
      if (layout === 'arc') {
        const mid = (e.s.x + e.t.x) / 2;
        const lift = Math.min(H * 0.42, Math.abs(e.t.x - e.s.x) * 0.55);
        el.setAttribute('d', `M ${e.s.x} ${e.s.y} Q ${mid} ${e.s.y - lift} ${e.t.x} ${e.t.y}`);
        el.setAttribute('fill', 'none');
      } else {
        el.setAttribute('x1', e.s.x); el.setAttribute('y1', e.s.y);
        el.setAttribute('x2', e.t.x); el.setAttribute('y2', e.t.y);
      }
    });
    nodeEls.forEach(({ n, g }) => g.setAttribute('transform', `translate(${n.x},${n.y})`));
  }

  function highlight(id) {
    if (!id) {
      svg.classList.remove('has-hover');
      nodeEls.forEach(({ g }) => g.classList.remove('near', 'dim'));
      edgeEls.forEach(({ el }) => el.classList.remove('hot', 'dim'));
      return;
    }
    const near = new Set([id]);
    edges.forEach(e => {
      if (e.source === id) near.add(e.target);
      if (e.target === id) near.add(e.source);
    });
    svg.classList.add('has-hover');
    nodeEls.forEach(({ n, g }) => {
      g.classList.toggle('near', near.has(n.id));
      g.classList.toggle('dim', !near.has(n.id));
    });
    edgeEls.forEach(({ e, el }) => {
      const on = e.source === id || e.target === id;
      el.classList.toggle('hot', on);
      el.classList.toggle('dim', !on);
    });
  }

  // ── hover card ─────────────────────────────────────────────────────────
  function showCard(n, ev, el) {
    const links = edges.filter(e => e.source === n.id || e.target === n.id);
    const byRel = new Map();
    links.forEach(e => {
      const rel = e.rel || 'RELATED';
      byRel.set(rel, (byRel.get(rel) || 0) + 1);
    });
    const peers = links
      .map(e => (e.source === n.id ? e.t : e.s))
      .filter((v, i, a) => a.findIndex(o => o.id === v.id) === i)
      .slice(0, 4);

    card.innerHTML = '';
    const head = document.createElement('div');
    head.className = 'gcard-head';
    const swatch = document.createElement('i');
    swatch.style.background = kindColour(n.kind);
    const name = document.createElement('b');
    name.textContent = n.label;
    head.append(swatch, name);

    const kind = document.createElement('div');
    kind.className = 'gcard-kind';
    kind.textContent = [titleCase(n.kind), n.subtype ? titleCase(n.subtype) : null]
      .filter(Boolean).join(' · ');

    const stats = document.createElement('div');
    stats.className = 'gcard-stats';
    stats.append(
      stat(String(links.length), links.length === 1 ? 'link' : 'links'),
      stat(String(n.events || 0), (n.events || 0) === 1 ? 'story' : 'stories'),
    );
    if (n.setbacks) stats.append(stat(String(n.setbacks), 'setbacks', 'bad'));

    card.append(head, kind, stats);

    if (byRel.size) {
      const rels = document.createElement('div');
      rels.className = 'gcard-rels';
      [...byRel.entries()].slice(0, 4).forEach(([rel, count]) => {
        const tag = document.createElement('span');
        tag.textContent = count > 1 ? `${rel} ×${count}` : rel;
        rels.append(tag);
      });
      card.append(rels);
    }

    if (peers.length) {
      const list = document.createElement('div');
      list.className = 'gcard-peers';
      list.textContent = peers.map(pn => pn.label).join(' · ')
        + (links.length > peers.length ? ` +${links.length - peers.length} more` : '');
      card.append(list);
    }

    const hint = document.createElement('div');
    hint.className = 'gcard-hint';
    hint.textContent = 'Click for evidence · double-click to widen';
    card.append(hint);

    card.classList.add('on');
    if (ev) moveCard(ev);
    else if (el) {
      const b = el.getBoundingClientRect();
      const h0 = host.getBoundingClientRect();
      place(b.left - h0.left + b.width / 2, b.top - h0.top);
    }
  }

  function stat(value, label, tone = '') {
    const wrap = document.createElement('span');
    wrap.className = tone;
    const strong = document.createElement('b');
    strong.textContent = value;
    wrap.append(strong, document.createTextNode(` ${label}`));
    return wrap;
  }

  function moveCard(ev) {
    const h0 = host.getBoundingClientRect();
    place(ev.clientX - h0.left, ev.clientY - h0.top);
  }

  // Keep the card inside the stage: flip to the other side of the cursor
  // rather than letting it run off the edge.
  function place(x, y) {
    const h0 = host.getBoundingClientRect();
    const w = card.offsetWidth || 250;
    const ht = card.offsetHeight || 130;
    const pad = 14;
    let left = x + 18;
    let top = y + 18;
    if (left + w + pad > h0.width) left = x - w - 18;
    if (top + ht + pad > h0.height) top = y - ht - 18;
    card.style.left = `${Math.max(pad, left)}px`;
    card.style.top = `${Math.max(pad, top)}px`;
  }

  function hideCard() { card.classList.remove('on'); }

  const toLocal = ev => {
    const box = svg.getBoundingClientRect();
    return {
      x: ((ev.clientX - box.left) / box.width) * W,
      y: ((ev.clientY - box.top) / box.height) * H,
    };
  };

  svg.addEventListener('pointerdown', ev => {
    hideCard();
    const hit = ev.target.closest('.gnode');
    const p = toLocal(ev);
    if (hit) {
      const found = nodeEls.find(x => x.g === hit);
      if (found) { dragging = found; svg.classList.add('dragging'); }
    } else {
      panning = { px: p.x, py: p.y, ox: view.x, oy: view.y };
      svg.classList.add('panning');
    }
    svg.setPointerCapture(ev.pointerId);
  });

  svg.addEventListener('pointermove', ev => {
    if (!dragging && !panning) return;
    const p = toLocal(ev);
    if (dragging) {
      dragging.n.x = (p.x - view.x) / view.k;
      dragging.n.y = (p.y - view.y) / view.k;
      paint();
    } else {
      view.x = panning.ox + (p.x - panning.px);
      view.y = panning.oy + (p.y - panning.py);
      applyView();
    }
  });

  const release = () => {
    dragging = null; panning = null;
    svg.classList.remove('dragging', 'panning');
  };
  svg.addEventListener('pointerup', release);
  svg.addEventListener('pointercancel', release);
  svg.addEventListener('pointerleave', release);

  svg.addEventListener('wheel', ev => {
    ev.preventDefault();
    const p = toLocal(ev);
    zoomBy(ev.deltaY < 0 ? 1.12 : 1 / 1.12, p.x, p.y);
  }, { passive: false });

  let resizeTimer;
  const onResize = () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 140); };
  window.addEventListener('resize', onResize);

  return {
    setData, setLayout, setHidden, setFocus, getLayout, render, reset,
    zoomIn: () => zoomBy(1.25),
    zoomOut: () => zoomBy(1 / 1.25),
    destroy: () => { window.removeEventListener('resize', onResize); card.remove(); },
  };
}

// Scale and centre the finished layout so it uses the whole stage rather
// than whichever corner the simulation happened to settle in.
function fitToStage(nodes, W, H) {
  if (nodes.length < 2) {
    nodes.forEach(n => { n.x = W / 2; n.y = H / 2; });
    return;
  }
  const pad = 46;
  const xs = nodes.map(n => n.x);
  const ys = nodes.map(n => n.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  // Uniform scale keeps the geometry honest — no stretching one axis.
  const k = Math.min((W - pad * 2) / spanX, (H - pad * 2) / spanY);
  const offX = (W - spanX * k) / 2;
  const offY = (H - spanY * k) / 2;
  nodes.forEach(n => {
    n.x = offX + (n.x - minX) * k;
    n.y = offY + (n.y - minY) * k;
  });
}

const radius = n => Math.max(5, Math.min(22, 5 + Math.sqrt(n.events || 1) * 2.7 + (n.weight || 0) * 0.3));

function place(nodes, edges, layout, W, H) {
  const kinds = [...new Set(nodes.map(n => n.kind))].sort();
  if (layout === 'radial') return radial(nodes, kinds, W, H);
  if (layout === 'arc') return arc(nodes, kinds, W, H);
  if (layout === 'grid') return grid(nodes, kinds, W, H);
  return force(nodes, edges, W, H);
}

function radial(nodes, kinds, W, H) {
  const cx = W / 2;
  const cy = H / 2;

  // Smallest group innermost. Each ring is then given whatever radius it needs
  // to seat its own nodes at a comfortable arc spacing — a ring is never
  // asked to hold more entities than its circumference can take, which is
  // what made a naive equal-spacing version crush the largest group.
  const byKind = kinds
    .map(k => ({
      list: nodes.filter(n => n.kind === k).sort((a, b) => (b.degree || 0) - (a.degree || 0)),
    }))
    .sort((a, b) => a.list.length - b.list.length);

  let r = 0;
  byKind.forEach(({ list }, ring) => {
    const biggest = Math.max(...list.map(n => n.r));
    const spacing = biggest * 2 + 54;               // arc length wanted per node
    const needed = (list.length * spacing) / (Math.PI * 2);
    r = Math.max(r + biggest + 46, needed);
    const step = (Math.PI * 2) / list.length;
    const offset = ring * 0.6;                       // stagger so rings don't align
    list.forEach((n, i) => {
      const angle = list.length === 1 ? -Math.PI / 2 : i * step + offset;
      n.x = cx + Math.cos(angle) * r;
      n.y = cy + Math.sin(angle) * r;
    });
  });
}

function arc(nodes, kinds, W, H) {
  const y = H - 74;
  const ordered = kinds.flatMap(k =>
    nodes.filter(n => n.kind === k).sort((a, b) => (b.degree || 0) - (a.degree || 0)));
  const pad = 44;
  const span = W - pad * 2;
  ordered.forEach((n, i) => {
    n.x = pad + (ordered.length === 1 ? span / 2 : (i / (ordered.length - 1)) * span);
    n.y = y;
  });
}

function grid(nodes, kinds, W, H) {
  const colW = W / kinds.length;
  kinds.forEach((k, c) => {
    const list = nodes.filter(n => n.kind === k).sort((a, b) => (b.degree || 0) - (a.degree || 0));
    const usable = H - 96;
    list.forEach((n, i) => {
      n.x = colW * c + colW / 2 + ((i % 2) ? 26 : -26);
      n.y = 58 + (list.length === 1 ? usable / 2 : (i / (list.length - 1)) * usable);
    });
  });
}

function force(nodes, edges, W, H, ticks = 380) {
  const k = Math.sqrt((W * H) / Math.max(1, nodes.length)) * 0.70;

  // Deterministic start: a phyllotaxis spiral. Random seeding would make the
  // same graph land differently on every render, which is disorienting.
  const golden = Math.PI * (3 - Math.sqrt(5));
  nodes.forEach((n, i) => {
    const r = Math.sqrt(i / nodes.length) * Math.min(W, H) * 0.40;
    n.x = W / 2 + Math.cos(i * golden) * r;
    n.y = H / 2 + Math.sin(i * golden) * r;
    n.vx = 0; n.vy = 0;
  });

  const kinds = [...new Set(nodes.map(n => n.kind))];
  const anchors = new Map(kinds.map((kind, i) => {
    const a = (i / kinds.length) * Math.PI * 2;
    return [kind, { x: W / 2 + Math.cos(a) * W * 0.21, y: H / 2 + Math.sin(a) * H * 0.20 }];
  }));

  const cutoff = k * 3.4;

  for (let step = 0; step < ticks; step++) {
    const alpha = 1 - step / ticks;

    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let dist = Math.hypot(dx, dy);
        if (dist > cutoff) continue;
        if (dist < 0.01) { dx = (i % 2 ? 1 : -1) * 0.5; dy = 0.5; dist = 0.7; }
        // Hard minimum separation is what removes the congestion entirely.
        const minGap = a.r + b.r + 14;
        const push = ((k * k) / (dist * dist)) * 1.05 + (dist < minGap ? (minGap - dist) * 0.9 : 0);
        dx /= dist; dy /= dist;
        a.vx -= dx * push; a.vy -= dy * push;
        b.vx += dx * push; b.vy += dy * push;
      }
    }

    for (const e of edges) {
      let dx = e.t.x - e.s.x;
      let dy = e.t.y - e.s.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const rest = k * 0.95;
      const pull = ((dist - rest) / dist) * 0.052 * Math.min(2.2, 0.8 + (e.weight || 1) * 0.35);
      dx *= pull; dy *= pull;
      e.s.vx += dx; e.s.vy += dy;
      e.t.vx -= dx; e.t.vy -= dy;
    }

    for (const n of nodes) {
      const anchor = anchors.get(n.kind);
      n.vx += (anchor.x - n.x) * 0.0022;
      n.vy += (anchor.y - n.y) * 0.0022;
      n.vx += (W / 2 - n.x) * 0.0026;
      n.vy += (H / 2 - n.y) * 0.0032;
      const damp = 0.80 * alpha + 0.12;
      n.vx *= damp; n.vy *= damp;
      n.x = Math.max(n.r + 30, Math.min(W - n.r - 30, n.x + n.vx));
      n.y = Math.max(n.r + 26, Math.min(H - n.r - 30, n.y + n.vy));
    }
  }
}
