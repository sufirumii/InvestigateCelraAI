import { api, h, frag, clear, num, pct, dir, dateShort } from '../util.js';
import { sparkline, stockChart, rangeSelector } from '../charts.js';
import { statStrip } from '../components.js';

const RANGES = ['1W', '1M', '3M', '6M', '1Y'];

export async function markets(ctx) {
  const board = await api('/api/markets');
  if (!board.companies.length) {
    return h('div', { class: 'empty' }, h('b', { text: 'No companies tracked yet' }),
      h('span', { text: 'Refresh the sources to populate the board.' }));
  }

  let selected = ctx.query.get('id') || board.companies[0].id;
  let range = '3M';

  const detailHost = h('div', {});
  const listHost = h('div', { class: 'quote-list' });

  async function paintDetail() {
    clear(detailHost).append(h('div', { class: 'skeleton', style: 'height:340px' }));
    const data = await api(`/api/companies/${encodeURIComponent(selected)}?range=${range}`);
    const c = data.company;
    const w = c.windows[range] || { changePct: c.changePct };

    const priceBig = h('div', { class: 'big', text: num(c.last, 2) });
    const delta = h('div', { class: `delta ${dir(w.changePct)}`,
      text: `${pct(w.changePct)} · ${range}` });

    const chart = stockChart(data.series, {
      height: 268,
      label: `${c.name} momentum`,
      onScrub: point => {
        if (point) {
          priceBig.textContent = num(point.value, 2);
          delta.textContent = point.events
            ? `${point.events} event${point.events > 1 ? 's' : ''} · ${dateShort(point.date)}`
            : dateShort(point.date);
          delta.className = 'delta';
        } else {
          priceBig.textContent = num(c.last, 2);
          delta.textContent = `${pct(w.changePct)} · ${range}`;
          delta.className = `delta ${dir(w.changePct)}`;
        }
      },
    });

    clear(detailHost).append(
      h('div', { class: 'quote-head' },
        h('div', {},
          h('div', { class: 'quote-name', text: c.name }),
          h('div', { class: 'quote-sub',
            text: `${c.ticker ? c.ticker + ' · ' : ''}${c.sector} · ${c.itemCount} stories · ${c.activeTrials} active trials` })),
        h('div', { class: 'quote-price' }, priceBig, delta)),
      chart,
      rangeSelector(RANGES, range, r => { range = r; paintDetail(); }),
      h('div', { style: 'margin-top:22px' },
        statStrip([
          [num(c.high, 1), '12-month high'],
          [num(c.low, 1), '12-month low'],
          [String(c.setbackCount), 'Setbacks recorded'],
          [num(c.volatility, 2), 'Daily volatility'],
        ])),
      h('div', { style: 'margin-top:20px;display:flex;gap:10px;flex-wrap:wrap' },
        h('button', { class: 'btn', type: 'button',
          onclick: () => ctx.go(`#/company/${encodeURIComponent(c.id)}`), text: 'Open full profile' }),
        h('button', { class: `btn ghost`, type: 'button',
          onclick: () => toggleWatch(c), text: c.onWatchlist ? 'Remove from watchlist' : 'Add to watchlist' })),
    );
  }

  async function toggleWatch(c) {
    if (c.onWatchlist) await api(`/api/watchlist/${encodeURIComponent(c.id)}`, { method: 'DELETE' });
    else await api('/api/watchlist', { method: 'POST', body: { entityId: c.id, focus: c.sector } });
    ctx.reload();
  }

  function paintList() {
    clear(listHost);
    board.companies.forEach(c => {
      const change = c.windows['1M'].changePct;
      listHost.append(h('button', {
        class: `quote-row${c.id === selected ? ' on' : ''}`, type: 'button',
        onclick: () => { selected = c.id; paintList(); paintDetail(); },
      },
        h('div', {},
          h('div', { class: 'nm', text: c.name }),
          h('div', { class: 'sb', text: `${c.ticker || c.sector} · ${c.itemCount} stories${c.setbackCount ? ` · ${c.setbackCount} setbacks` : ''}` })),
        h('div', { class: 'spark' }, sparkline(c.sparkline, { width: 78, height: 28 })),
        h('div', { class: `pc ${dir(change)}`, text: pct(change) }),
      ));
    });
  }

  paintList();
  await paintDetail();

  return frag(
    h('div', { class: 'page-head' },
      h('h1', { text: 'Momentum' }),
      h('p', { text: board.basis })),
    h('div', { class: 'market-top' },
      detailHost,
      h('div', {},
        statStrip([
          [String(board.breadth.advancing), 'Advancing'],
          [String(board.breadth.declining), 'Declining'],
        ]),
        h('div', { style: 'margin-top:18px' },
          h('h3', { style: 'font-size:var(--t-sm);font-weight:650;margin-bottom:10px', text: 'Largest one-month moves' }),
          ...board.gainers.slice(0, 3).map(g => row(g, ctx)),
          ...board.losers.slice(0, 3).map(g => row(g, ctx))),
      )),
    h('div', { class: 'sec-head' },
      h('h2', { text: 'All tracked companies' }),
      h('span', { class: 'note', text: 'One-month change in the momentum index' })),
    listHost,
  );
}

const row = (c, ctx) => h('button', {
  class: 'hub-row', type: 'button',
  onclick: () => ctx.go(`#/company/${encodeURIComponent(c.id)}`),
},
  h('div', {}, h('div', { class: 'hn', text: c.name }), h('div', { class: 'hk', text: c.sector })),
  h('div', { class: `hv ${dir(c.windows['1M'].changePct)}`,
    style: 'font-weight:650', text: pct(c.windows['1M'].changePct) }));
