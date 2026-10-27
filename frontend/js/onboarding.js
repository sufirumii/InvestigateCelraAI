// Sign-in: who is reading, and what they want ranked first.
//
// Nothing here is a filter. The choices are sent to POST /api/preferences,
// which folds them into the portfolio component of the signal score, so the
// analyst's remit rises to the top of the edition without the rest of the
// sector disappearing. Every option offered is read from the live corpus —
// there is no fixed list of therapy areas or companies in this file.

import { api, frag, h, clear, titleCase } from './util.js';

const SPLASH_MINIMUM_MS = 4000;
const CONFIGURE_MS = 4000;

const ROLES = [
  ['Competitive intelligence', 'Tracking competitor pipelines and catching developments early'],
  ['Market & product intelligence', 'Sizing opportunities and watching for openings'],
  ['Medical information', 'Fielding questions on competitor safety and efficacy'],
  ['Business development', 'Partnership, licensing and M&A signals'],
];

// Event classes worth surfacing as headline priorities, matched against
// whatever the API reports so this never drifts out of step with the taxonomy.
const PRIORITY_HINTS = [
  'trial_failure', 'program_discontinuation', 'safety_event', 'regulatory_rejection',
  'regulatory_approval', 'readout_positive', 'partnership', 'ma_activity',
  'financing', 'platform_ai', 'repurposing', 'restructuring',
];

export function splashFloor(startedAt) {
  const elapsed = Date.now() - startedAt;
  return new Promise(r => setTimeout(r, Math.max(0, SPLASH_MINIMUM_MS - elapsed)));
}

export async function runOnboarding() {
  // Same reasoning as broadcast: these are full-screen overlays, so the desk
  // underneath must not contribute a scrollbar of its own.
  document.documentElement.classList.add('overlay-open');

  const { options, corpusReady } = await api('/api/preferences');

  const state = { analyst: '', role: '', sectors: [], eventTypes: [], companies: [] };
  const panel = document.getElementById('onboard');
  const body = document.getElementById('ob-body');
  const stepsEl = document.getElementById('ob-steps');
  const progress = document.getElementById('ob-progress');
  const back = document.getElementById('ob-back');
  const next = document.getElementById('ob-next');

  const orderedEvents = [
    ...PRIORITY_HINTS
      .map(id => options.eventTypes.find(t => t.id === id))
      .filter(Boolean),
    ...options.eventTypes.filter(t => !PRIORITY_HINTS.includes(t.id)),
  ];

  const steps = [
    {
      title: 'Who is reading this morning?',
      hint: 'Your name appears on exports and briefs so a shared deck is attributable.',
      valid: () => state.analyst.trim().length > 0,
      skipLabel: null,
      render: () => {
        const input = h('input', {
          class: 'inp big', type: 'text', placeholder: 'Your name',
          value: state.analyst, autocomplete: 'name', spellcheck: 'false',
        });
        input.addEventListener('input', e => { state.analyst = e.target.value; sync(); });
        input.addEventListener('keydown', e => { if (e.key === 'Enter' && state.analyst.trim()) go(1); });
        setTimeout(() => input.focus(), 120);
        return input;
      },
    },
    {
      title: 'What is your remit?',
      hint: 'This shapes which capability matches are surfaced alongside each story.',
      valid: () => true,
      render: () => h('div', { class: 'ob-role' },
        ...ROLES.map(([name, detail]) => h('button', {
          type: 'button', class: state.role === name ? 'on' : '',
          onclick: () => { state.role = state.role === name ? '' : name; draw(); },
        }, h('b', { text: name }), h('span', { text: detail })))),
    },
    {
      title: 'Which therapy areas matter to you?',
      hint: 'Chosen areas rise in the ranking. Leave everything unselected to weight the whole corpus equally.',
      valid: () => true,
      render: () => frag(
        h('div', { class: 'ob-grid' }, ...options.sectors.map(s => toggle(
          s.id, s.id, corpusReady ? s.count : null, state.sectors))),
        corpusReady ? null : note(
          'Counts appear once the first fetch completes. These are every area the desk can classify, so your choice applies to whatever arrives.'),
      ),
    },
    {
      title: 'Which developments should lead the edition?',
      hint: 'Event classes you pick are weighted toward the top. Setbacks are usually the ones that move a portfolio decision.',
      valid: () => true,
      render: () => h('div', { class: 'ob-grid' },
        ...orderedEvents.map(t => toggle(t.id, t.label, null, state.eventTypes))),
    },
    {
      title: 'Any companies you track closely?',
      hint: 'These join your watchlist and carry extra weight. Ranked by how active they are in the current corpus.',
      valid: () => true,
      render: () => frag(
        h('div', { class: 'ob-grid' }, ...options.companies.slice(0, 40).map(c => toggle(
          c.id, c.ticker ? `${c.name} · ${c.ticker}` : c.name, c.items || null, state.companies))),
        corpusReady ? null : note(
          'These are the companies the desk queries the registry and literature for on every refresh.'),
      ),
    },
  ];

  let at = 0;

  const note = text => h('p', {
    style: 'text-align:center;color:var(--ink-faint);font-size:var(--t-sm);max-width:44ch;margin:40px auto',
    text,
  });

  function toggle(id, label, count, bucket) {
    const on = bucket.includes(id);
    return h('button', {
      type: 'button', class: `ob-opt${on ? ' on' : ''}`,
      'aria-pressed': String(on),
      onclick: () => {
        const i = bucket.indexOf(id);
        if (i >= 0) bucket.splice(i, 1); else bucket.push(id);
        draw();
      },
    }, titleCase(label), count != null ? h('span', { class: 'n', text: String(count) }) : null);
  }

  function draw() {
    const step = steps[at];
    clear(stepsEl).append(...steps.map((_, i) => h('span', {
      class: i === at ? 'on' : i < at ? 'done' : '',
    })));
    clear(body).append(
      h('h2', { text: step.title }),
      h('p', { class: 'ob-hint', text: step.hint }),
      step.render(),
    );
    sync();
  }

  function sync() {
    const step = steps[at];
    back.classList.toggle('invisible', at === 0);
    next.disabled = !step.valid();
    next.textContent = at === steps.length - 1 ? 'Open the desk' : 'Continue';
    progress.textContent = `Step ${at + 1} of ${steps.length}`;
  }

  // `finish` is assigned by the promise below. Declared out here so that
  // `go()` — which is called from the buttons and from Enter on the name
  // field — can reach it; a function declared inside the executor would not
  // be in scope at this level.
  let finish = () => {};

  function go(delta) {
    const target = at + delta;
    if (target < 0) return;
    if (target >= steps.length) { finish(); return; }
    at = target;
    draw();
  }

  return new Promise(resolve => {
    finish = async () => {
      next.disabled = true;

      // Start the write and the playback in the same tick. The write does a
      // full re-rank and can take a few seconds; hiding the card first and
      // waiting for it left the analyst staring at a blank page. The playback
      // opens immediately with statements derived from what they just chose,
      // then reconciles with what the server reports it actually applied.
      const saving = api('/api/preferences', { method: 'POST', body: state });
      saving.catch(() => {});                     // handled below; avoids an unhandled rejection

      const playback = playConfiguration(state.analyst, localStatements(state, options), saving);
      panel.classList.add('hidden');

      let result;
      try {
        result = await saving;
      } catch (err) {
        playback.abort();
        panel.classList.remove('hidden');
        next.disabled = false;
        clear(body).append(
          h('h2', { text: 'That did not save' }),
          h('p', { class: 'ob-hint', text: String(err.message || err) }),
          h('p', { class: 'ob-hint', text: 'Press Open the desk to try again, or reload to continue with the default ranking.' }),
        );
        return;
      }

      await playback.done;
      document.documentElement.classList.remove('overlay-open');
      resolve(result.preferences);
    };

    back.onclick = () => go(-1);
    next.onclick = () => go(1);
    panel.classList.remove('hidden');
    draw();
  });
}

// Statements describing the choices, built on the client so the playback can
// open the instant the analyst clicks — no waiting on the network. The server
// returns its own account of what it applied and that supersedes these as soon
// as it arrives, so the two can never quietly disagree.
function localStatements(state, options) {
  const named = ids => options.sectors
    .filter(s => ids.includes(s.id))
    .map(s => s.id)
    .join(', ');

  return [
    state.sectors.length
      ? `Prioritising ${state.sectors.length} therapy area${state.sectors.length > 1 ? 's' : ''}: ${named(state.sectors)}`
      : 'Covering every therapy area in the corpus',
    state.eventTypes.length
      ? `Weighting ${state.eventTypes.length} event class${state.eventTypes.length > 1 ? 'es' : ''} toward the top of the edition`
      : 'Weighting all event classes equally',
    state.companies.length
      ? `Tracking ${state.companies.length} compan${state.companies.length > 1 ? 'ies' : 'y'} on the watchlist`
      : 'Tracking the full core coverage set',
  ];
}

// Opens immediately and runs for a fixed four seconds. `saving` is the
// in-flight write: when it lands, the lines are replaced with the server's
// account and the closing line gains the real story count. If the write is
// still running when the four seconds are up, the playback waits for it rather
// than dropping the analyst onto a half-built desk.
function playConfiguration(name, initialLines, saving) {
  const panel = document.getElementById('configuring');
  const list = document.getElementById('cfg-lines');
  const first = (name || '').trim().split(/\s+/)[0] || 'there';
  let cancelled = false;
  let timers = [];

  document.getElementById('cfg-greet').textContent = `Good ${partOfDay()}, ${first}.`;
  panel.classList.remove('hidden');

  const closing = 'Re-ranking the corpus against your priorities';

  function paint(lines) {
    clear(list).append(...lines.map((text, i) => h('li', {
      style: `animation-delay:${i * 220}ms`,
    }, h('i', {}), h('span', { text }))));

    timers.forEach(clearTimeout);
    const tickEvery = CONFIGURE_MS / (lines.length + 1);
    timers = lines.map((_, i) => setTimeout(
      () => list.children[i]?.classList.add('done'),
      tickEvery * (i + 1),
    ));
  }

  paint([...initialLines, closing]);

  saving.then(result => {
    if (cancelled) return;
    const lines = [
      ...(result.statements?.length ? result.statements : initialLines),
      `Re-ranking ${result.stats?.analysed ?? 0} stories against your priorities`,
    ];
    // Keep whatever has already been ticked off ticked off.
    const ticked = [...list.children].filter(li => li.classList.contains('done')).length;
    paint(lines);
    for (let i = 0; i < Math.min(ticked, lines.length); i++) {
      list.children[i]?.classList.add('done');
    }
  }).catch(() => {});

  const floor = new Promise(r => setTimeout(r, CONFIGURE_MS));
  const done = Promise.allSettled([floor, saving]).then(() => {
    if (cancelled) return;
    timers.forEach(clearTimeout);
    [...list.children].forEach(li => li.classList.add('done'));
    panel.classList.add('hidden');
  });

  return {
    done,
    abort() {
      cancelled = true;
      timers.forEach(clearTimeout);
      panel.classList.add('hidden');
    },
  };
}

const partOfDay = () => {
  const hour = new Date().getHours();
  if (hour < 12) return 'morning';
  if (hour < 18) return 'afternoon';
  return 'evening';
};
