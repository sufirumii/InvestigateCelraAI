import { api, h, frag, clear, num, pct, dir, dateLong, ago } from '../util.js';
import { sparkline, signalDial, componentBars } from '../charts.js';
import { storyCard, briefRow, sectionHead, eventChip } from '../components.js';
import { openBroadcast } from '../broadcast.js';

export async function frontPage(ctx) {
  const data = await api('/api/edition');
  if (!data.lead) {
    // No bundled corpus exists, so an empty edition means the first fetch is
    // either running or has failed. Poll rather than leaving a dead page.
    const host = h('div', { class: 'booting' },
      h('h2', { text: 'Building the first edition' }),
      h('p', { text: 'The desk is reading the regulator feeds, the trade press, the trial registry and PubMed. Nothing is stored in this repository — every story you are about to see is being fetched now.' }),
      h('div', { class: 'bar' }, h('i', {})));
    let tries = 0;
    const poll = setInterval(async () => {
      tries += 1;
      const again = await api('/api/edition');
      if (again.lead) { clearInterval(poll); ctx.reload(); return; }
      if (tries > 40) {
        clearInterval(poll);
        clear(host).append(
          h('b', { text: 'The sources could not be reached' }),
          h('span', { text: 'Check outbound network access, then press Refresh sources. The desk will not substitute placeholder content.' }));
        host.className = 'empty';
      }
    }, 3000);
    return host;
  }

  const lead = data.lead;
  const detail = await api(`/api/items/${lead.id}`);

  const masthead = h('header', { class: 'masthead' },
    h('h1', { text: 'The Intelligence Edition' }),
    h('div', { class: 'edition-meta' },
      h('div', { text: dateLong(data.generatedAt) }),
      h('div', {}, h('b', { text: String(data.stats.analysed) }), ' stories · ',
        h('b', { text: String(data.stats.setbacks) }), ' setbacks · ',
        h('b', { text: String(data.stats.companies) }), ' companies'),
      h('button', {
        class: 'btn broadcast', type: 'button',
        onclick: () => openBroadcast(data, { onOpen: ctx.open }),
      }, h('i', {}), 'Initiate slideshow'),
    ));

  // Continuous tape. The track holds the full company list twice; the CSS
  // translates it by exactly -50% and loops, so the seam is invisible and the
  // speed is proportional to the number of entries rather than fixed.
  const tape = data.movers;
  const tick = m => h('button', {
    class: 'tick', type: 'button', tabindex: '-1',
    onclick: () => ctx.go(`#/company/${encodeURIComponent(m.id)}`),
  },
    h('div', {},
      h('div', { class: 'sym', text: m.ticker || m.name }),
      h('div', { class: 'val' }, num(m.last, 2), '  ',
        h('span', { class: `chg ${dir(m.changePct)}`, text: pct(m.changePct) })),
    ),
    sparkline(m.sparkline, { width: 64, height: 26 }),
  );

  const ticker = tape.length
    ? h('div', { class: 'ticker', role: 'marquee',
        'aria-label': `Momentum for ${tape.length} companies` },
        h('div', {
          class: 'tape',
          style: `--tape-duration:${Math.max(28, tape.length * 4.2)}s`,
        },
          h('div', { class: 'tape-run' }, ...tape.map(tick)),
          h('div', { class: 'tape-run', 'aria-hidden': 'true' }, ...tape.map(tick)),
        ))
    : null;

  const leadBlock = h('section', { class: `lead band-${lead.band}` },
    h('div', {},
      h('div', { class: 'lead-kicker' },
        eventChip(lead.classification),
        h('span', { class: 'chip outline', text: lead.sector }),
        lead.primaryCompany && h('span', { class: 'chip outline', text: lead.primaryCompany.name }),
      ),
      h('h2', { text: lead.title }),
      h('p', { class: 'standfirst', text: lead.summary || lead.lede }),
      h('div', { class: 'byline' },
        `${lead.source.name} · ${ago(lead.publishedAt)} ago · corroborated by ${lead.corroboration} source${lead.corroboration > 1 ? 's' : ''}`),
      h('div', { style: 'margin-top:20px;display:flex;gap:10px;flex-wrap:wrap' },
        h('button', { class: 'btn', type: 'button', onclick: () => ctx.open(lead.id), text: 'Read the analysis' }),
        lead.primaryCompany && h('button', { class: 'btn ghost', type: 'button',
          onclick: () => ctx.go(`#/company/${encodeURIComponent(lead.primaryCompany.id)}`),
          text: `${lead.primaryCompany.name} profile` }),
      ),
    ),
    h('aside', { class: 'lead-aside' },
      signalDial(lead.signal.value, lead.band),
      componentBars(detail.signal.components),
      detail.limitations.length ? h('div', { class: 'quote-lim', text: detail.limitations[0].statement }) : null,
      lead.excelraDetail?.length ? h('div', { class: 'asset-block' },
        h('div', { class: 'an', text: lead.excelraDetail[0].name }),
        h('div', { class: 'ac', text: lead.excelraDetail[0].contribution })) : null,
    ));

  const features = h('section', { class: 'grid-features' },
    data.features.map(i => storyCard(i, ctx.open)));

  const setbacks = data.setbacks.length ? frag(
    sectionHead('Where programmes are going wrong', 'Failures, holds, terminations and restructuring'),
    h('div', { class: 'briefs' }, data.setbacks.map(i => briefRow(i, ctx.open))),
  ) : null;

  const rails = frag(
    sectionHead('By therapy area', 'Ranked within each area by signal'),
    data.sectors.slice(0, 6).map(rail => h('div', { class: 'rail-row' },
      h('header', {},
        h('h3', { text: rail.sector }),
        h('span', { class: 'c', text: `${rail.count} stories · ${rail.setbacks} setbacks` }),
        h('button', { class: 'btn ghost small', style: 'margin-left:auto', type: 'button',
          onclick: () => ctx.go(`#/signals?sector=${encodeURIComponent(rail.sector)}`), text: 'See all' }),
      ),
      h('div', { class: 'rail-scroll' }, rail.items.map(i => storyCard(i, ctx.open))),
    )));

  const briefs = data.briefs.length ? frag(
    sectionHead('In brief', `${data.briefs.length} further developments`),
    h('div', { class: 'briefs' }, data.briefs.map(i => briefRow(i, ctx.open))),
  ) : null;

  return frag(masthead, ticker, leadBlock, features, setbacks, rails, briefs);
}
