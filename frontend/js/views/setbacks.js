import { api, h, frag, dateShort } from '../util.js';
import { briefRow, sectionHead, statStrip, emptyState } from '../components.js';

export async function setbacks(ctx) {
  const data = await api('/api/setbacks');

  if (!data.total && !data.limitations.length) {
    return emptyState('No setbacks in the current corpus',
      'The desk flags failures, holds, terminations, rejections and restructuring as they appear.');
  }

  const strip = statStrip([
    [String(data.total), 'Setback events'],
    [String(data.stoppedTrials.length), 'Trials stopped or withdrawn'],
    [String(data.limitations.length), 'Limitations quoted from sources'],
    [String(data.byType.length), 'Distinct setback classes'],
  ]);

  const byType = data.byType.map(group => frag(
    sectionHead(group.label, `${group.count} record${group.count > 1 ? 's' : ''}`),
    h('div', { class: 'briefs' }, group.items.map(i => briefRow(i, ctx.open))),
  ));

  const trials = data.stoppedTrials.length ? frag(
    sectionHead('Registry records', 'Sponsor-stated reasons, taken verbatim from the trial registry'),
    h('table', { class: 'data' },
      h('thead', {}, h('tr', {},
        h('th', { text: 'Study' }), h('th', { text: 'Sponsor' }),
        h('th', { text: 'Phase' }), h('th', { text: 'Status' }),
        h('th', { text: 'Reason recorded' }))),
      h('tbody', {}, data.stoppedTrials.map(t => h('tr', {},
        h('td', {}, h('b', { text: t.title }),
          h('div', { style: 'color:var(--ink-faint);font-size:var(--t-xs);margin-top:3px',
            text: `${t.conditions || '—'}${t.enrollment ? ` · n=${t.enrollment}` : ''}` })),
        h('td', { text: t.sponsor }),
        h('td', { text: t.phase || '—' }),
        h('td', {}, h('span', { class: 'chip setback', text: t.status })),
        h('td', { text: t.whyStopped || 'No reason recorded' }),
      )))),
  ) : null;

  const limitations = data.limitations.length ? frag(
    sectionHead('Stated limitations', 'Sentences that contain a caveat cue, quoted without paraphrase'),
    h('div', {}, data.limitations.slice(0, 24).map(l =>
      h('button', {
        class: 'quote-lim', type: 'button',
        style: 'display:block;width:100%;text-align:left;cursor:pointer',
        onclick: () => ctx.open(l.itemId),
      },
        l.statement,
        h('div', { style: 'font-family:var(--sans);font-size:var(--t-xs);color:var(--ink-soft);margin-top:8px',
          text: `${l.company || l.sector} · ${l.source} · ${dateShort(l.publishedAt)}` }),
      ))),
  ) : null;

  return frag(
    h('div', { class: 'page-head' },
      h('h1', { text: 'Setbacks and limitations' }),
      h('p', { text: 'What is not working, and what competitors themselves say the constraints are. This is the part of the record that rarely makes it into a portfolio review.' })),
    strip,
    byType,
    trials,
    limitations,
  );
}
