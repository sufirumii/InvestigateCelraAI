import { api, h, frag, clear, svgEl, kindColour, titleCase, num, toast } from '../util.js';
import { createGraph, LAYOUTS } from '../graphview.js';
import { briefRow } from '../components.js';

export async function graphView(ctx) {
  let focus = ctx.query.get('focus') || null;
  let depth = Number(ctx.query.get('depth')) || 2;
  let limit = Number(ctx.query.get('limit')) || 130;
  const hidden = new Set();

  const svg = svgEl('svg', { role: 'application', 'aria-label': 'Knowledge graph' });
  const stage = h('div', { class: 'graph-stage' }, svg);
  const detailPanel = h('div', { class: 'panel' });
  const legendPanel = h('div', { class: 'panel' });
  const hubsPanel = h('div', { class: 'panel' });
  const pathPanel = h('div', { class: 'panel' });
  const layoutRow = h('div', { class: 'seg' });
  const scaleNote = h('span', { class: 'note' });

  const graph = createGraph(svg, {
    onSelect: n => select(n.id),
    onExpand: n => { focus = n.id; depth = Math.min(4, depth + 1); load(); },
  });

  let data = { nodes: [], edges: [], legend: [], stats: {} };

  function params() {
    const p = new URLSearchParams({ limit: String(limit), depth: String(depth) });
    if (focus) p.set('focus', focus);
    return p;
  }

  async function load({ keepView = false } = {}) {
    data = await api(`/api/graph?${params()}`);
    graph.setFocus(focus);
    graph.setData(data, { keepView });
    paintLegend();
    paintScale();
    paintPath();
  }

  function paintScale() {
    scaleNote.textContent =
      `${data.stats.nodes} of ${data.stats.total ?? data.stats.nodes} entities · ${data.stats.edges} links · depth ${depth}`;
  }

  function paintLegend() {
    clear(legendPanel).append(
      h('h3', { text: 'Entity types' }),
      h('div', { class: 'legend' },
        ...data.legend.map(kind => h('button', {
          class: hidden.has(kind) ? 'off' : '', type: 'button',
          'aria-pressed': String(!hidden.has(kind)),
          onclick: () => {
            hidden.has(kind) ? hidden.delete(kind) : hidden.add(kind);
            graph.setHidden(hidden);
            paintLegend();
          },
        }, h('i', { style: `background:${kindColour(kind)}` }), titleCase(kind)))),
      h('p', { class: 'panel-note',
        text: 'Disc size is how many stories the entity appears in. Hover to isolate its neighbourhood, drag to reposition, double-click to widen the view around it.' }),
      h('div', { class: 'panel-actions' },
        h('button', { class: 'btn ghost small', type: 'button',
          onclick: () => window.open('/api/graph/export.cypher', '_blank'),
          text: 'Export Cypher' }),
        h('button', { class: 'btn ghost small', type: 'button',
          onclick: () => window.open(popoutUrl(), '_blank', 'noopener'),
          text: 'Open in new tab' })),
    );
  }

  function popoutUrl() {
    const p = params();
    p.set('layout', graph.getLayout());
    if (hidden.size) p.set('hide', [...hidden].join(','));
    return `/graph.html?${p}`;
  }

  async function select(nodeId) {
    focus = nodeId;
    clear(detailPanel).append(h('div', { class: 'skeleton', style: 'height:130px' }));
    const node = await api(`/api/graph/node/${encodeURIComponent(nodeId)}`);
    data = await api(`/api/graph?${params()}`);
    graph.setFocus(focus);
    graph.setData(data);
    paintScale();
    paintPath();

    clear(detailPanel).append(
      h('h3', { text: node.node.label }),
      h('div', { class: 'tag-row', style: 'margin-bottom:12px' },
        h('span', { class: 'chip',
          style: `background:${kindColour(node.node.kind)}18;color:${kindColour(node.node.kind)}`,
          text: titleCase(node.node.kind) }),
        node.node.subtype && h('span', { class: 'chip outline', text: titleCase(node.node.subtype) }),
        h('span', { class: 'chip outline', text: `${node.node.degree} links` }),
        node.node.setbacks > 0 && h('span', { class: 'chip setback', text: `${node.node.setbacks} setbacks` }),
      ),
      node.neighbours.length ? frag(
        h('h3', { style: 'margin-top:6px', text: 'Connected to' }),
        h('div', { class: 'tag-row' },
          ...node.neighbours.slice(0, 16).map(n => h('button', {
            class: 'chip outline', type: 'button',
            style: `color:${kindColour(n.kind)};border-color:${kindColour(n.kind)}35`,
            onclick: () => select(n.id),
          }, n.label)))) : null,
      node.items.length ? frag(
        h('h3', { style: 'margin-top:16px', text: 'Evidence' }),
        h('div', { class: 'briefs' },
          ...node.items.slice(0, 6).map(i => briefRow(i, ctx.open)))) : null,
      node.node.kind === 'company' ? h('button', {
        class: 'btn ghost small', style: 'margin-top:12px', type: 'button',
        onclick: () => ctx.go(`#/company/${encodeURIComponent(node.node.id)}`),
        text: 'Open company profile',
      }) : null,
    );
  }

  async function paintHubs() {
    const { hubs } = await api('/api/graph/hubs?limit=10');
    clear(hubsPanel).append(
      h('h3', { text: 'Most connected entities' }),
      ...hubs.map(hub => h('button', { class: 'hub-row', type: 'button', onclick: () => select(hub.id) },
        h('div', {}, h('div', { class: 'hn', text: hub.label }),
          h('div', { class: 'hk', text: `${titleCase(hub.kind)} · ${hub.degree} links` })),
        h('div', { class: 'hv', text: num(hub.centrality, 1) }))),
      h('p', { class: 'panel-note', text: 'Ranked by PageRank over the undirected graph.' }),
    );
  }

  function paintPath() {
    const options = data.nodes
      .slice()
      .sort((a, b) => a.label.localeCompare(b.label))
      .map(n => h('option', { value: n.id, text: `${n.label} · ${titleCase(n.kind)}` }));
    if (!options.length) { clear(pathPanel); return; }
    const from = h('select', { class: 'inp' }, ...options.map(o => o.cloneNode(true)));
    const to = h('select', { class: 'inp' }, ...options.map(o => o.cloneNode(true)));
    if (to.options.length > 1) to.selectedIndex = Math.min(4, to.options.length - 1);
    const out = h('div', { class: 'path-out' });

    clear(pathPanel).append(
      h('h3', { text: 'Trace a connection' }),
      h('div', { class: 'path-form' }, from, to,
        h('button', { class: 'btn small', type: 'button', text: 'Find shortest path',
          onclick: async () => {
            const res = await api(`/api/graph/path?source=${encodeURIComponent(from.value)}&target=${encodeURIComponent(to.value)}`);
            clear(out);
            if (!res.found) {
              out.append(h('div', { class: 'panel-note', text: 'No path within six hops.' }));
              return;
            }
            res.path.forEach(step => out.append(h('div', { class: 'path-step' },
              step.rel && h('span', { class: 'rel', text: step.rel }),
              h('button', { class: 'chip outline', type: 'button',
                style: `color:${kindColour(step.node.kind)};border-color:${kindColour(step.node.kind)}35`,
                onclick: () => select(step.node.id) }, step.node.label))));
            toast(`${res.length} hop${res.length === 1 ? '' : 's'} between the two entities`);
          } })),
      out,
    );
  }

  function paintLayoutRow() {
    clear(layoutRow).append(...LAYOUTS.map(l => h('button', {
      class: graph.getLayout() === l.id ? 'on' : '', type: 'button', title: l.hint,
      onclick: () => { graph.setLayout(l.id); paintLayoutRow(); },
      text: l.label,
    })));
  }

  const controls = h('div', { class: 'graph-toolbar' },
    layoutRow,
    h('div', { class: 'seg' },
      h('button', { type: 'button', title: 'Zoom out', onclick: () => graph.zoomOut(), text: '−' }),
      h('button', { type: 'button', title: 'Reset view', onclick: () => graph.reset(), text: 'Reset' }),
      h('button', { type: 'button', title: 'Zoom in', onclick: () => graph.zoomIn(), text: '+' })),
    h('div', { class: 'seg' },
      h('button', { type: 'button', title: 'Narrow the neighbourhood',
        onclick: () => { depth = Math.max(1, depth - 1); load(); }, text: 'Contract' }),
      h('button', { type: 'button', title: 'Widen the neighbourhood',
        onclick: () => { depth = Math.min(5, depth + 1); load(); }, text: 'Expand' }),
      h('button', { type: 'button', title: 'Clear the focus and show the whole graph',
        onclick: () => { focus = null; depth = 2; limit = 200; load(); }, text: 'Whole graph' })),
    scaleNote,
  );

  paintLayoutRow();
  paintHubs();
  await load();
  if (focus) await select(focus);
  else clear(detailPanel).append(
    h('h3', { text: 'Select an entity' }),
    h('p', { class: 'panel-note',
      text: 'Every node was extracted from a source document by dictionary match, and every edge carries the stories that produced it.' }));

  return frag(
    h('div', { class: 'page-head' },
      h('h1', { text: 'Knowledge graph' }),
      h('p', { text: 'Companies, assets, targets, indications and trials, connected by the evidence that links them.' })),
    controls,
    h('div', { class: 'graph-layout' },
      stage,
      h('div', { class: 'graph-side' }, detailPanel, legendPanel, pathPanel, hubsPanel)),
  );
}
