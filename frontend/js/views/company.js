import { api, h, frag, clear, num, pct, dir } from '../util.js';
import { stockChart, rangeSelector } from '../charts.js';
import { briefRow, sectionHead, statStrip } from '../components.js';

const RANGES = ['1W', '1M', '3M', '6M', '1Y'];

export async function company(ctx, id) {
  let range = '6M';
  let data = await api(`/api/companies/${encodeURIComponent(id)}?range=${range}`);
  const c = data.company;

  const chartHost = h('div', {});

  async function paintChart() {
    data = await api(`/api/companies/${encodeURIComponent(id)}?range=${range}`);
    const w = data.company.windows[range] || {};
    const big = h('div', { class: 'big', text: num(data.company.last, 2) });
    const delta = h('div', { class: `delta ${dir(w.changePct)}`, text: `${pct(w.changePct || 0)} · ${range}` });
    clear(chartHost).append(
      h('div', { class: 'quote-head' },
        h('div', {}, h('div', { class: 'quote-sub', text: 'Intelligence momentum index' })),
        h('div', { class: 'quote-price' }, big, delta)),
      stockChart(data.series, {
        height: 240,
        onScrub: p => {
          big.textContent = p ? num(p.value, 2) : num(data.company.last, 2);
          delta.textContent = p
            ? (p.events ? `${p.events} event${p.events > 1 ? 's' : ''} on ${p.date}` : p.date)
            : `${pct(w.changePct || 0)} · ${range}`;
        },
      }),
      rangeSelector(RANGES, range, r => { range = r; paintChart(); }),
    );
  }
  await paintChart();

  const programmes = data.programmes.length ? frag(
    sectionHead('Programmes seen in the record', 'Assets named in stories about this company, with what those stories name alongside them'),
    h('table', { class: 'data' },
      h('thead', {}, h('tr', {},
        h('th', { text: 'Asset' }), h('th', { text: 'Modality' }),
        h('th', { text: 'Target' }), h('th', { text: 'Indication' }), h('th', { text: 'Evidence' }))),
      h('tbody', {}, data.programmes.map(p => h('tr', {},
        h('td', {}, h('b', { text: p.name })),
        h('td', { text: p.modality || '—' }),
        h('td', { text: p.targets.join(', ') || '—' }),
        h('td', { text: p.indications.join(', ') || '—' }),
        h('td', {}, h('span', { class: 'chip outline',
          text: `${p.evidence} stor${p.evidence === 1 ? 'y' : 'ies'}` })),
      )))),
  ) : null;

  const trials = data.trials.length ? frag(
    sectionHead('Registered studies'),
    h('table', { class: 'data' },
      h('thead', {}, h('tr', {},
        h('th', { text: 'Study' }), h('th', { text: 'Phase' }),
        h('th', { text: 'Status' }), h('th', { text: 'Enrolment' }), h('th', { text: 'Notes' }))),
      h('tbody', {}, data.trials.map(t => h('tr', {},
        h('td', {}, h('b', { text: t.title }),
          h('div', { style: 'color:var(--ink-faint);font-size:var(--t-xs);margin-top:3px', text: t.conditions || '' })),
        h('td', { text: t.phase || '—' }),
        h('td', {}, h('span', { class: t.isSetback ? 'chip setback' : 'chip', text: t.status })),
        h('td', { class: 'num', text: t.enrollment ? String(t.enrollment) : '—' }),
        h('td', { text: t.whyStopped || '—' }),
      )))),
  ) : null;

  const excelra = data.excelra.length ? frag(
    sectionHead('Where Excelra fits against this company', 'Aggregated from the rule matches across every story'),
    h('div', { class: 'two-col' },
      data.excelra.map(a => h('div', { class: 'value-card' },
        h('h3', { text: a.name }),
        h('div', { class: 'metric' }, h('b', { text: String(a.hits) }),
          h('span', { style: 'color:var(--ink-faint);font-size:var(--t-sm)', text: 'stories matched' })),
        h('p', { style: 'margin:0;font-size:var(--t-sm)', text: a.contribution }),
        h('p', { style: 'margin:0;font-size:var(--t-sm);color:var(--ink-faint)', text: a.value }),
      ))),
  ) : null;

  return frag(
    h('div', { class: 'page-head' },
      h('div', { class: 'lead-kicker' },
        h('span', { class: 'chip violet', text: c.sector }),
        c.ticker && h('span', { class: 'chip outline', text: c.ticker }),
        c.setbackCount > 0 && h('span', { class: 'chip setback', text: `${c.setbackCount} setbacks` })),
      h('h1', { text: c.name }),
      h('p', { text: `${c.itemCount} stories in the corpus · ${c.trialCount} registered studies · top signal ${num(c.topSignal, 0)}` })),
    h('div', { class: 'market-top' },
      chartHost,
      h('div', {},
        statStrip([
          [num(c.high, 1), 'High'],
          [num(c.low, 1), 'Low'],
          [String(c.activeTrials), 'Active trials'],
          [String(c.setbackCount), 'Setbacks'],
        ]),
        h('div', { style: 'margin-top:16px;display:grid;gap:8px' },
          h('button', {
            class: 'btn ghost', type: 'button',
            onclick: async () => {
              if (c.onWatchlist) await api(`/api/watchlist/${encodeURIComponent(c.id)}`, { method: 'DELETE' });
              else await api('/api/watchlist', { method: 'POST', body: { entityId: c.id, focus: c.sector } });
              ctx.reload();
            },
            text: c.onWatchlist ? 'Remove from watchlist' : 'Track this company',
          }),),
      )),
    data.setbacks.length ? frag(
      sectionHead('Setbacks'),
      h('div', { class: 'briefs' }, data.setbacks.map(i => briefRow(i, ctx.open)))) : null,
    programmes,
    sectionHead('Coverage', `${data.items.length} most recent stories`),
    h('div', { class: 'briefs' }, data.items.map(i => briefRow(i, ctx.open))),
    trials,
    excelra,
  );
}
