import { api, h, frag, clear } from '../util.js';
import { briefRow, emptyState } from '../components.js';

export async function signals(ctx) {
  const meta = ctx.meta;
  const state = {
    sector: ctx.query.get('sector') || '',
    event: ctx.query.get('event') || '',
    band: ctx.query.get('band') || '',
    setbacks: ctx.query.get('setbacks') === '1',
    q: ctx.query.get('q') || '',
  };

  const list = h('div', { class: 'briefs' });
  const count = h('span', { class: 'note' });

  const pill = (label, on, onClick, violet = false) =>
    h('button', { class: `pill${on ? ' on' : ''}${violet && on ? ' violet' : ''}`, type: 'button',
      onclick: onClick, text: label });

  function filterBar() {
    return h('div', { class: 'filters' },
      pill('All areas', !state.sector, () => set('sector', '')),
      ...meta.sectors.map(s => pill(s, state.sector === s, () => set('sector', s))),
      h('span', { class: 'sep' }),
      pill('Setbacks only', state.setbacks, () => set('setbacks', !state.setbacks), true),
      h('span', { class: 'sep' }),
      h('select', { class: 'inp', style: 'width:auto;min-width:170px',
        onchange: e => set('event', e.target.value) },
        h('option', { value: '', text: 'Every event class' }),
        ...meta.eventTypes.map(t => h('option', {
          value: t.id, text: t.label, selected: state.event === t.id ? 'selected' : null,
        }))),
      h('select', { class: 'inp', style: 'width:auto;min-width:140px',
        onchange: e => set('band', e.target.value) },
        h('option', { value: '', text: 'Any signal band' }),
        ...meta.bands.map(b => h('option', {
          value: b, text: `${b[0].toUpperCase()}${b.slice(1)}`, selected: state.band === b ? 'selected' : null,
        }))),
      h('button', { class: 'btn ghost small', style: 'margin-left:auto', type: 'button',
        onclick: download, text: 'Download CSV' }),
    );
  }

  function download() {
    const p = new URLSearchParams();
    if (state.sector) p.set('sector', state.sector);
    window.open(`/api/export/signals.csv?${p}`, '_blank');
  }

  async function load() {
    const p = new URLSearchParams({ limit: '120' });
    if (state.sector) p.set('sector', state.sector);
    if (state.event) p.set('event', state.event);
    if (state.band) p.set('band', state.band);
    if (state.setbacks) p.set('setbacks', 'true');
    if (state.q) p.set('q', state.q);
    const data = await api(`/api/items?${p}`);
    count.textContent = `${data.total} stories`;
    clear(list);
    if (!data.items.length) {
      list.append(emptyState('Nothing matches those filters',
        'Widen the therapy area or clear the event class to see more of the corpus.'));
      return;
    }
    data.items.forEach(i => list.append(briefRow(i, ctx.open)));
  }

  function set(key, value) {
    state[key] = value;
    clear(bar).append(...filterBar().childNodes);
    load();
  }

  const bar = h('div', {});
  bar.append(filterBar());
  await load();

  return frag(
    h('div', { class: 'page-head' },
      h('h1', { text: 'Signals' }),
      h('p', { text: 'Every analysed story, ranked by the same score used to build the front page.' })),
    bar,
    h('div', { class: 'sec-head' }, h('h2', { text: 'Results' }), count),
    list,
  );
}
