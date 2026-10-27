import { api, h, frag, num, titleCase, dateShort } from '../util.js';
import { sectionHead, statStrip } from '../components.js';

// --------------------------------------------------------------- Why Excelra
export async function value(ctx) {
  const data = await api('/api/excelra');

  const impact = statStrip([
    [String(data.impact.storiesTriaged), 'Stories triaged automatically'],
    [String(data.impact.setbacksSurfaced), 'Competitor setbacks surfaced'],
    [String(data.impact.limitationsExtracted), 'Limitations quoted with a source'],
    [String(data.impact.trialsTracked), 'Registry trials tracked'],
  ]);

  const users = h('div', { class: 'two-col' },
    data.users.map(u => h('div', { class: 'value-card' },
      h('h3', { text: u.role }),
      h('p', { class: 'lead-line', style: 'margin:0', text: u.need }),
      h('p', { style: 'margin:0;font-size:var(--t-sm)', text: u.served }))));

  const coverage = data.coverage.length ? h('table', { class: 'data' },
    h('thead', {}, h('tr', {},
      h('th', { text: 'Capability' }), h('th', { text: 'Stories matched' }),
      h('th', { text: 'Share of corpus' }), h('th', { text: 'Where it lands' }),
      h('th', { text: 'What it is worth' }))),
    h('tbody', {}, data.coverage.map(a => h('tr', {},
      h('td', {}, h('b', { text: a.name }),
        h('div', { style: 'color:var(--ink-faint);font-size:var(--t-xs);margin-top:3px', text: a.fullName })),
      h('td', { class: 'num', text: String(a.hits) }),
      h('td', { class: 'num', text: `${a.share}%` }),
      h('td', { text: Object.keys(a.sectors).slice(0, 3).join(', ') }),
      h('td', { text: a.value }),
    )))) : null;

  const catalogue = h('div', { class: 'two-col' },
    data.catalogue.map(a => h('div', { class: 'value-card' },
      h('h3', { text: a.name }),
      h('p', { class: 'lead-line', style: 'margin:0', text: a.summary }),
      h('p', { style: 'margin:0;font-size:var(--t-sm);color:var(--ink-faint)', text: a.supports }))));

  return frag(
    h('div', { class: 'page-head' },
      h('h1', { text: 'Why Excelra' }),
      h('p', { text: 'Competitive intelligence in life sciences fails on volume, not on insight. The desk triages the volume so analysts spend their time on the judgement calls — and every story arrives already mapped to the Excelra capability that would answer it.' })),
    impact,
    sectionHead('Who this is for'),
    users,
    sectionHead('Capability coverage in the current corpus', 'Counted from live rule matches, not asserted'),
    coverage,
    sectionHead('The capabilities the rules map onto'),
    catalogue,
    sectionHead('The inefficiency this removes'),
    h('div', { class: 'two-col' },
      h('div', { class: 'value-card' },
        h('h3', { text: 'Today' }),
        h('p', { style: 'margin:0;font-size:var(--t-sm)',
          text: 'Analysts read the same trade press, registry updates and filings by hand, keep parallel spreadsheets, and rediscover the same competitor limitation three times in three teams. Nothing is ranked, so urgency is whatever landed in the inbox last.' })),
      h('div', { class: 'value-card' },
        h('h3', { text: 'With the desk' }),
        h('p', { style: 'margin:0;font-size:var(--t-sm)',
          text: 'One ranked edition per day with an auditable reason for every placement, setbacks separated from progress, source-quoted limitations, and registry records set beside the trade coverage of the same programme. Commercial and medical teams work from the same evidence on the same morning.' })),
    ),
  );
}

// --------------------------------------------------------------- Method
export async function method(ctx) {
  const data = await api('/api/method');

  const stages = h('div', { class: 'flow' },
    data.stages.map((s, i) => h('div', { class: 'flow-step' },
      h('span', { class: 'n', text: String(i + 1).padStart(2, '0') }),
      h('div', {}, h('h4', { text: s.name }), h('p', { text: s.detail })))));

  const weights = h('table', { class: 'data' },
    h('thead', {}, h('tr', {}, h('th', { text: 'Component' }), h('th', { text: 'Weight' }), h('th', { text: 'What it measures' }))),
    h('tbody', {}, data.scoring.components.map(c => h('tr', {},
      h('td', {}, h('b', { text: c.label })),
      h('td', { class: 'num', text: c.weight.toFixed(2) }),
      h('td', { text: COMPONENT_NOTES[c.id] || '' }),
    ))));

  const taxonomy = h('table', { class: 'data' },
    h('thead', {}, h('tr', {},
      h('th', { text: 'Event class' }), h('th', { text: 'Direction' }),
      h('th', { text: 'Base weight' }), h('th', { text: 'Rules' }))),
    h('tbody', {}, data.taxonomy.map(t => h('tr', {},
      h('td', {}, h('b', { text: t.label })),
      h('td', {}, h('span', {
        class: t.polarity < 0 ? 'chip setback' : t.polarity > 0 ? 'chip positive' : 'chip',
        text: t.polarity < 0 ? 'Setback' : t.polarity > 0 ? 'Progress' : 'Structural' })),
      h('td', { class: 'num', text: t.weight.toFixed(2) }),
      h('td', { class: 'num', text: String(t.ruleCount) }),
    ))));

  const runs = data.runs.length ? h('table', { class: 'data' },
    h('thead', {}, h('tr', {},
      h('th', { text: 'Run' }), h('th', { text: 'Mode' }), h('th', { text: 'Fetched' }),
      h('th', { text: 'New' }), h('th', { text: 'Duplicates' }), h('th', { text: 'Errors' }))),
    h('tbody', {}, data.runs.map(r => h('tr', {},
      h('td', { text: dateShort(r.started_at) }),
      h('td', {}, h('span', { class: 'chip outline', text: titleCase(r.mode) })),
      h('td', { class: 'num', text: String(r.fetched) }),
      h('td', { class: 'num', text: String(r.accepted) }),
      h('td', { class: 'num', text: String(r.duplicates) }),
      h('td', { text: r.errors.length ? `${r.errors.length}` : '—' }),
    )))) : null;

  return frag(
    h('div', { class: 'page-head' },
      h('h1', { text: 'How the desk decides' }),
      h('p', { text: data.principle })),
    statStrip([
      [String(data.stats.analysed), 'Stories analysed'],
      [String(data.stats.duplicatesCollapsed), 'Duplicates collapsed'],
      [String(data.taxonomy.length), 'Event classes'],
      [String(data.stats.trials ?? 0), 'Registry trials'],
    ]),
    sectionHead('The pipeline', 'Eleven deterministic stages'),
    stages,
    sectionHead('The ranking formula', data.scoring.formula),
    weights,
    h('p', { style: 'font-size:var(--t-sm);color:var(--ink-soft);margin-top:14px',
      text: `Bands: critical ${data.scoring.bands.critical}, high ${data.scoring.bands.high}, moderate ${data.scoring.bands.moderate}, routine ${data.scoring.bands.routine}. Open any story to see its own breakdown.` }),
    sectionHead('The event taxonomy'),
    taxonomy,
    runs ? frag(sectionHead('Ingestion history'), runs) : null,
    sectionHead('Sources monitored'),
    h('div', { class: 'tag-row' },
      ctx.meta.sources.map(s => h('span', { class: 'chip outline' },
        s.name, h('span', { style: 'opacity:.6;font-weight:400', text: titleCase(s.tier) })))),
  );
}

const COMPONENT_NOTES = {
  recency: 'Exponential decay on publication age, nine-day half-life.',
  authority: 'Source tier: registry and regulator outrank trade press.',
  event: 'Base weight of the event class, scaled by classifier confidence.',
  impact: 'Trial phase plus how many targets and indications are named.',
  corroboration: 'Distinct outlets carrying the same development.',
  portfolio: 'Watchlist membership and strength of the Excelra rule match.',
};
