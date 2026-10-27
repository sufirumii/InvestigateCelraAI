// Broadcast mode — an editorial run through the edition for a wall display or
// the front of a room.
//
// Deliberately not a media player. There is no scrub bar and no transport
// glyphs; the model is a newsroom rundown. A segmented strip along the top
// shows every story in the edition and which one is on air, the body is a
// two-column editorial spread with a fixed structure, and the controls are
// named in words.
//
// Everything comes from the same /api/edition payload the front page uses. The
// running order is the signal ranking.

import { api, h, frag, clear, num, pct, dir, ago, titleCase, dateLong } from './util.js';

const DWELL_MS = 10000;
const TICK_MS = 100;

export function openBroadcast(edition, { onOpen } = {}) {
  const stories = [edition.lead, ...edition.features, ...edition.briefs]
    .filter(Boolean)
    .filter((s, i, all) => all.findIndex(o => o.id === s.id) === i);

  if (!stories.length) return;

  let at = 0;
  let paused = false;
  let elapsed = 0;
  let timer = null;
  let token = 0;

  const root = h('div', { class: 'bc', role: 'dialog', 'aria-modal': 'true',
    'aria-label': 'Broadcast mode' });

  // ── masthead ──────────────────────────────────────────────────────────
  const clock = h('span', { class: 'bc-clock' });
  const counter = h('span', { class: 'bc-counter' });

  const masthead = h('header', { class: 'bc-mast' },
    h('div', { class: 'bc-mast-l' },
      h('span', { class: 'bc-live' }, h('i', {}), 'On air'),
      h('span', { class: 'bc-mast-title', text: 'The Intelligence Edition' }),
      h('span', { class: 'bc-mast-date', text: dateLong(edition.generatedAt) }),
    ),
    h('div', { class: 'bc-mast-r' }, counter, clock),
  );

  // One segment per story: the rundown, and the only progress indicator.
  const rundown = h('div', { class: 'bc-rundown', role: 'tablist',
    'aria-label': 'Story rundown' });
  const segments = stories.map((s, i) => {
    const fill = h('i');
    const seg = h('button', {
      class: `bc-seg band-${s.band}`, type: 'button', role: 'tab',
      'aria-label': `Story ${i + 1}: ${s.title}`,
      title: s.title,
      onclick: () => jump(i),
    }, fill);
    rundown.append(seg);
    return { seg, fill };
  });

  const main = h('div', { class: 'bc-main' });
  const aside = h('aside', { class: 'bc-aside' });

  // ── controls ──────────────────────────────────────────────────────────
  const pauseBtn = h('button', { class: 'bc-btn', type: 'button', onclick: togglePause });

  const controls = h('div', { class: 'bc-controls' },
    h('button', { class: 'bc-btn', type: 'button', onclick: () => step(-1), text: 'Previous' }),
    pauseBtn,
    h('button', { class: 'bc-btn', type: 'button', onclick: () => step(1), text: 'Next' }),
    h('span', { class: 'bc-sep' }),
    h('button', { class: 'bc-btn quiet', type: 'button',
      onclick: () => { const s = stories[at]; close(); onOpen?.(s.id); },
      text: 'Open full story' }),
    h('button', { class: 'bc-btn quiet', type: 'button', onclick: toggleFullscreen,
      text: 'Full screen' }),
    h('span', { class: 'bc-keys', text: 'Space pause · ← → step · F full screen · Esc exit' }),
    h('button', { class: 'bc-btn exit', type: 'button', onclick: close, text: 'Exit' }),
  );

  const tape = edition.movers.length
    ? h('div', { class: 'bc-tape' },
        h('span', { class: 'bc-tape-label', text: 'Momentum' }),
        h('div', { class: 'bc-tape-win' },
          h('div', { class: 'bc-tape-run', style: `--n:${edition.movers.length}` },
            ...tapeItems(), ...tapeItems())))
    : null;

  root.append(masthead, rundown, h('div', { class: 'bc-spread' }, main, aside),
    h('footer', { class: 'bc-foot' }, controls, tape));

  function tapeItems() {
    return edition.movers.map(m => h('span', { class: 'bc-tick' },
      h('b', { text: m.ticker || m.name }),
      h('span', { text: num(m.last, 2) }),
      h('span', { class: `chg ${dir(m.changePct)}`, text: pct(m.changePct) })));
  }

  // ── slide ─────────────────────────────────────────────────────────────
  async function paint() {
    const s = stories[at];
    const mine = ++token;

    counter.textContent = `Story ${at + 1} of ${stories.length}`;
    segments.forEach(({ seg, fill }, i) => {
      seg.classList.toggle('on', i === at);
      seg.classList.toggle('done', i < at);
      fill.style.width = i < at ? '100%' : i === at ? '0%' : '0%';
    });

    clear(main).append(
      h('article', { class: 'bc-story' },
        h('div', { class: 'bc-kicker' },
          h('span', { class: `bc-band band-${s.band}`, text: s.classification.label }),
          s.primaryCompany && h('span', { class: 'bc-co', text: s.primaryCompany.name }),
          h('span', { class: 'bc-slug', text: s.sector }),
          s.classification.phase && h('span', { class: 'bc-slug', text: titleCase(s.classification.phase) }),
        ),
        h('h2', { class: 'bc-headline', text: s.title }),
        h('p', { class: 'bc-standfirst', text: s.summary || s.lede || '' }),
        h('div', { class: 'bc-byline' },
          h('span', { text: s.source.name }),
          h('span', { class: 'bc-dotsep' }),
          h('span', { text: `${ago(s.publishedAt)} ago` }),
          s.corroboration > 1 ? frag(
            h('span', { class: 'bc-dotsep' }),
            h('span', { text: `${s.corroboration} outlets` })) : null,
        ),
        h('div', { class: 'bc-figures' }),
      ),
    );

    clear(aside).append(
      h('div', { class: 'bc-panel bc-signal' },
        h('div', { class: 'bc-panel-h', text: 'Signal' }),
        h('div', { class: 'bc-signal-row' },
          h('span', { class: 'bc-signal-n', text: num(s.signal.value, 0) }),
          h('span', { class: `bc-signal-b band-${s.band}`, text: s.band })),
      ),
      h('div', { class: 'bc-panel bc-limit hidden' }),
      h('div', { class: 'bc-panel bc-fit hidden' }),
      h('div', { class: 'bc-panel' },
        h('div', { class: 'bc-panel-h', text: 'Next in the rundown' }),
        h('ol', { class: 'bc-queue' },
          ...stories.slice(at + 1, at + 4).map((n, i) => h('li', {},
            h('span', { class: 'bc-q-n', text: String(at + 2 + i).padStart(2, '0') }),
            h('span', { class: 'bc-q-t', text: n.title }))))),
    );

    // Detail arrives separately; a slide missing it must not stall the run.
    try {
      const full = await api(`/api/items/${s.id}`);
      if (mine !== token) return;

      if (full.figures.length) {
        main.querySelector('.bc-figures').append(...full.figures.slice(0, 4).map(f =>
          h('span', { class: 'bc-fig' }, h('b', { text: f.value }), h('span', { text: f.kind }))));
      }
      if (full.limitations.length) {
        const box = aside.querySelector('.bc-limit');
        box.classList.remove('hidden');
        box.append(
          h('div', { class: 'bc-panel-h', text: 'Stated limitation' }),
          h('blockquote', { text: full.limitations[0].statement }));
      }
      if (full.excelra.matches.length) {
        const box = aside.querySelector('.bc-fit');
        const m = full.excelra.matches[0];
        box.classList.remove('hidden');
        box.append(
          h('div', { class: 'bc-panel-h', text: 'Where Excelra fits' }),
          h('b', { class: 'bc-fit-n', text: m.name }),
          h('p', { text: m.contribution }));
      }
    } catch { /* keep broadcasting */ }
  }

  function jump(i) { at = i; elapsed = 0; paint(); }
  function step(d) { jump((at + d + stories.length) % stories.length); }

  function togglePause() {
    paused = !paused;
    root.classList.toggle('paused', paused);
    pauseBtn.textContent = paused ? 'Resume' : 'Pause';
    pauseBtn.classList.toggle('is-paused', paused);
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else root.requestFullscreen?.();
  }

  function tick() {
    clock.textContent = new Date().toLocaleTimeString(undefined,
      { hour: '2-digit', minute: '2-digit' });
    if (paused) return;
    elapsed += TICK_MS;
    segments[at].fill.style.width = `${Math.min(100, (elapsed / DWELL_MS) * 100)}%`;
    if (elapsed >= DWELL_MS) step(1);
  }

  function onKey(e) {
    if (e.key === 'Escape') return close();
    if (e.key === ' ') { e.preventDefault(); return togglePause(); }
    if (e.key === 'ArrowRight') return step(1);
    if (e.key === 'ArrowLeft') return step(-1);
    if (e.key.toLowerCase() === 'f') return toggleFullscreen();
    if (e.key === 'Enter') { const s = stories[at]; close(); onOpen?.(s.id); }
  }

  function close() {
    clearInterval(timer);
    document.documentElement.classList.remove('overlay-open');
    document.removeEventListener('keydown', onKey);
    if (document.fullscreenElement) document.exitFullscreen?.();
    root.classList.add('leaving');
    setTimeout(() => root.remove(), 220);
  }

  // The desk behind the overlay is several thousand pixels tall and stays
  // scrollable, which is what put a scrollbar down the right of the slideshow.
  // Broadcast is unattended, so lock the page under it and restore on exit.
  document.documentElement.classList.add('overlay-open');

  pauseBtn.textContent = 'Pause';
  document.body.append(root);
  document.addEventListener('keydown', onKey);
  paint();
  tick();
  timer = setInterval(tick, TICK_MS);
}
