// Standalone full-window graph. Same renderer and the same API as the panel
// inside the desk — this page only supplies a bigger stage and reads its
// starting state from the query string it was opened with.

import { api, h, clear, kindColour, titleCase } from './util.js';
import { createGraph, LAYOUTS } from './graphview.js';

const q = new URLSearchParams(location.search);
let focus = q.get('focus') || null;
let depth = Number(q.get('depth')) || 2;
let limit = Number(q.get('limit')) || 160;
const hidden = new Set((q.get('hide') || '').split(',').filter(Boolean));

const svg = document.getElementById('pop-svg');
const detail = document.getElementById('pop-detail');
const scale = document.getElementById('pop-scale');
let data = { nodes: [], edges: [], legend: [], stats: {} };

const graph = createGraph(svg, {
  onSelect: id => select(id.id),
  onExpand: n => { focus = n.id; depth = Math.min(5, depth + 1); load(); },
});
graph.setLayout(q.get('layout') || 'force');
graph.setHidden(hidden);

async function load() {
  const p = new URLSearchParams({ limit: String(limit), depth: String(depth) });
  if (focus) p.set('focus', focus);
  data = await api(`/api/graph?${p}`);
  graph.setFocus(focus);
  graph.setData(data);
  scale.textContent = `${data.stats.nodes} entities · ${data.stats.edges} links · depth ${depth}`;
  paintLegend();
  document.title = focus
    ? `${data.nodes.find(n => n.id === focus)?.label || 'Graph'} — knowledge graph`
    : 'Knowledge graph — InvestigateCelra';
}

function paintLegend() {
  clear(document.getElementById('pop-legend')).append(
    ...data.legend.map(kind => h('button', {
      type: 'button', class: hidden.has(kind) ? 'off' : '',
      onclick: () => {
        hidden.has(kind) ? hidden.delete(kind) : hidden.add(kind);
        graph.setHidden(hidden); paintLegend();
      },
    }, h('i', { class: 'swatch', style: `background:${kindColour(kind)}` }), titleCase(kind))));
}

function paintLayouts() {
  clear(document.getElementById('pop-layouts')).append(
    ...LAYOUTS.map(l => h('button', {
      type: 'button', title: l.hint, class: graph.getLayout() === l.id ? 'on' : '',
      onclick: () => { graph.setLayout(l.id); paintLayouts(); },
      text: l.label,
    })));
}

async function select(id) {
  focus = id;
  const node = await api(`/api/graph/node/${encodeURIComponent(id)}`);
  await load();
  clear(detail).append(
    h('h2', { text: node.node.label }),
    h('div', { class: 'tag-row' },
      h('span', { class: 'chip',
        style: `background:${kindColour(node.node.kind)}18;color:${kindColour(node.node.kind)}`,
        text: titleCase(node.node.kind) }),
      h('span', { class: 'chip outline', text: `${node.node.degree} links` }),
      node.node.setbacks > 0 && h('span', { class: 'chip setback', text: `${node.node.setbacks} setbacks` })),
    node.neighbours.length ? h('h3', { text: 'Connected to' }) : null,
    h('div', { class: 'tag-row' },
      ...node.neighbours.slice(0, 24).map(n => h('button', {
        class: 'chip outline', type: 'button',
        style: `color:${kindColour(n.kind)};border-color:${kindColour(n.kind)}35`,
        onclick: () => select(n.id),
      }, n.label))),
    node.items.length ? h('h3', { text: 'Evidence' }) : null,
    ...node.items.slice(0, 8).map(i => h('a', {
      class: 'pop-item', href: `/#/signals?q=${encodeURIComponent(i.title.slice(0, 40))}`, target: '_blank',
    }, h('b', { text: i.title }), h('span', { text: `${i.source.name} · ${i.classification.label}` }))),
  );
}

document.getElementById('pop-in').onclick = () => graph.zoomIn();
document.getElementById('pop-out').onclick = () => graph.zoomOut();
document.getElementById('pop-reset').onclick = () => graph.reset();
document.getElementById('pop-expand').onclick = () => { depth = Math.min(5, depth + 1); load(); };
document.getElementById('pop-contract').onclick = () => { depth = Math.max(1, depth - 1); load(); };
document.getElementById('pop-all').onclick = () => { focus = null; depth = 2; limit = 260; load(); };

function paintPlaceholder() {
  clear(detail).append(
    h('h2', { text: 'Select an entity' }),
    h('p', { class: 'pop-hint',
      text: 'Every node was extracted from a source document by dictionary match, and every edge carries the stories that produced it.' }),
    h('p', { class: 'pop-hint',
      text: 'Drag to pan, scroll to zoom, hover to isolate a neighbourhood, double-click a node to widen the view around it.' }),
  );
}

paintLayouts();
paintPlaceholder();
load().then(() => { if (focus) select(focus); });
