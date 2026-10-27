// Reusable pieces of the desk UI.

import { api, h, frag, ago, dateShort, num, titleCase, clear, kindColour } from './util.js';
import { signalDial, componentBars } from './charts.js';

export const eventChip = c => h('span', {
  class: `chip event band-${bandOf(c)}`,
}, h('i', { class: 'pip' }), c.label);

const bandOf = c => (c.isSetback ? 'critical' : c.polarity > 0 ? 'moderate' : 'routine');

export function storyCard(item, onOpen) {
  return h('button', { class: `story band-${item.band}`, type: 'button',
    onclick: () => onOpen(item.id) },
    h('div', { class: 'lead-kicker' },
      eventChip(item.classification),
      item.classification.phase && h('span', { class: 'chip outline', text: titleCase(item.classification.phase) }),
    ),
    h('h3', { text: item.title }),
    item.lede && h('p', { class: 'dek', text: item.lede }),
    h('div', { class: 'foot' },
      h('span', { class: 'sig', text: num(item.signal.value, 0) }),
      h('span', { text: item.source.name }),
      h('span', { text: ago(item.publishedAt) }),
      item.excelra.assets.length > 0 && h('span', { class: 'chip violet', text: item.excelra.assets[0] }),
    ),
  );
}

export function briefRow(item, onOpen) {
  return h('button', { class: `brief band-${item.band}`, type: 'button',
    onclick: () => onOpen(item.id) },
    h('span', { class: 'when', text: ago(item.publishedAt) }),
    h('span', {},
      h('span', { class: 'headline', text: item.title }),
      h('span', { class: 'meta' },
        eventChip(item.classification),
        item.primaryCompany && h('span', { text: item.primaryCompany.name }),
        h('span', { text: item.sector }),
        item.limitationCount > 0 && h('span', { text: `${item.limitationCount} stated limitation${item.limitationCount > 1 ? 's' : ''}` }),
      ),
    ),
    h('span', { class: 'score', text: num(item.signal.value, 0) }),
  );
}

export function sectionHead(title, note) {
  return h('div', { class: 'sec-head' },
    h('h2', { text: title }),
    note && h('span', { class: 'note', text: note }),
  );
}

export function statStrip(entries) {
  return h('div', { class: 'stat-strip' },
    entries.map(([n, l]) => h('div', {},
      h('div', { class: 'n', text: n }),
      h('div', { class: 'l', text: l }))));
}

export function emptyState(title, detail) {
  return h('div', { class: 'empty' }, h('b', { text: title }), h('span', { text: detail }));
}

// ---------------------------------------------------------------- reader
const reader = () => document.getElementById('reader');
const scrim = () => document.getElementById('scrim');

export function closeReader() {
  reader().classList.remove('open');
  reader().setAttribute('aria-hidden', 'true');
  scrim().classList.remove('open');
}

export async function openStory(id, { onNavigate } = {}) {
  const panel = reader();
  const body = document.getElementById('reader-body');
  clear(body).append(h('div', { class: 'skeleton', style: 'height:200px' }));
  panel.classList.add('open');
  panel.setAttribute('aria-hidden', 'false');
  scrim().classList.add('open');

  const item = await api(`/api/items/${id}`);
  document.getElementById('reader-tag').textContent = item.classification.label;
  clear(body).append(renderStory(item, onNavigate));
  body.scrollTop = 0;
}

function renderStory(item, onNavigate) {
  const cls = item.classification;

  const head = h('div', {},
    h('div', { class: 'lead-kicker' },
      eventChip(cls),
      h('span', { class: 'chip outline', text: item.sector }),
      cls.phase && h('span', { class: 'chip outline', text: titleCase(cls.phase) }),
    ),
    h('h2', { text: item.title }),
    h('div', { class: 'attribution' },
      `${item.source.name} · ${dateShort(item.publishedAt)}`,
      item.url ? frag(' · ', h('a', { href: item.url, target: '_blank',
        rel: 'noopener', style: 'color:var(--violet-deep);text-decoration:underline', text: 'Open source' })) : null,
    ),
  );

  const extract = item.summary
    ? h('div', { class: 'extract', text: item.summary })
    : null;

  const figures = item.figures.length
    ? h('div', { class: 'reader-sec' },
        h('h4', { text: 'Figures found in the text' }),
        h('div', { class: 'tag-row' },
          item.figures.map(f => h('span', { class: 'chip outline' },
            h('b', { text: f.value }), h('span', { style: 'font-weight:400;opacity:.7', text: f.kind })))))
    : null;

  const limitations = item.limitations.length
    ? h('div', { class: 'reader-sec' },
        h('h4', { text: 'Stated limitations, quoted from the source' }),
        item.limitations.map(l => h('div', { class: 'quote-lim', text: l.statement })))
    : null;

  const excelra = item.excelra.matches.length
    ? h('div', { class: 'reader-sec' },
        h('h4', { text: 'Why this reaches Excelra' }),
        item.excelra.matches.map(m => h('div', { class: 'asset-block' },
          h('div', { class: 'an', text: m.name }),
          h('div', { class: 'ac', text: m.contribution }),
          h('div', { class: 'ar', text: `Matched on ${m.reasons.join('; ')}` }))))
    : null;

  const entities = item.entities.length
    ? h('div', { class: 'reader-sec' },
        h('h4', { text: 'Entities recognised' }),
        h('div', { class: 'tag-row' },
          item.entities.map(e => h('span', {
            class: 'chip outline',
            style: `border-color:${kindColour(e.kind)}40;color:${kindColour(e.kind)}`,
            title: titleCase(e.kind),
          }, e.name))))
    : null;

  const scoring = h('div', { class: 'reader-sec' },
    h('h4', { text: 'How this story was ranked' }),
    signalDial(item.signal.value, item.band),
    h('div', { style: 'margin-top:16px' }, componentBars(item.signal.components)),
  );

  const rules = cls.matchedRules.length
    ? h('div', { class: 'reader-sec' },
        h('h4', { text: `Rules that produced the "${cls.label}" label` }),
        h('div', { class: 'rule-list' },
          cls.matchedRules.map(r => h('div', {},
            h('code', { text: r.match }),
            h('span', { style: 'color:var(--ink-faint)', text: ` matched in ${r.where}, +${r.points}` })))),
        h('p', { style: 'font-size:var(--t-xs);color:var(--ink-faint);margin-top:10px',
          text: `Classifier confidence ${(cls.confidence * 100).toFixed(0)}%. No model was involved — these regular expressions are the entire decision.` }))
    : null;

  const facts = h('div', { class: 'reader-sec' },
    h('h4', { text: 'Record' }),
    h('dl', { class: 'kv' },
      ...kv('Company', item.primaryCompany?.name || '—'),
      ...kv('Sector', item.sector),
      ...kv('Source tier', titleCase(item.source.tier)),
      ...kv('Corroborating outlets', String(item.corroboration.distinctSources)),
      ...kv('Age', `${item.ageDays.toFixed(1)} days`),
      ...kv('Keywords', item.keywords.join(', ') || '—'),
    ));

  const related = item.related?.length
    ? h('div', { class: 'reader-sec' },
        h('h4', { text: 'Same development, other sources' }),
        item.related.map(r => h('button', { class: 'brief', type: 'button',
          style: 'grid-template-columns:1fr', onclick: () => openStory(r.id, { onNavigate }) },
          h('span', {}, h('span', { class: 'headline', text: r.title }),
            h('span', { class: 'meta' }, h('span', { text: r.source }))))))
    : null;

  const company = item.primaryCompany
    ? h('div', { class: 'reader-sec' },
        h('button', { class: 'btn ghost', type: 'button',
          onclick: () => { closeReader(); onNavigate?.(`#/company/${encodeURIComponent(item.primaryCompany.id)}`); },
          text: `Open ${item.primaryCompany.name} profile` }))
    : null;

  return frag(head, extract, figures, limitations, excelra, scoring, rules, entities, facts, related, company);
}

const kv = (k, v) => [h('dt', { text: k }), h('dd', { text: v })];
