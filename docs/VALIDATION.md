# Validation

The brief requires the project to be validated before submission. This is what
was checked and what it found.

## Automated tests

`make test` — 63 tests, all passing.

| File | Covers |
|---|---|
| `test_classify.py` | Event labels, negation guard, title weighting, phase detection, verbatim limitation extraction, determinism |
| `test_entities.py` | Acronym case-sensitivity, longest-match, aliases, primary-company selection, coverage metadata |
| `test_normalize.py` | SimHash near-duplicate detection and separation, HTML stripping, sentence splitting, figure extraction |
| `test_score.py` | Score bounds and bands, weight sum, component reconstruction, half-life decay |
| `test_api.py` | All 16 endpoints, empty-corpus behaviour, refusal to fabricate offline, 404 handling |
| `test_titles_and_preferences.py` | Backronym casing repair and its invariants, preference fit bounds and neutrality |

## Defects the tests found

Three real bugs, all fixed:

**Present-tense verbs were unmatched.** `\bdiscontinu(?:e|ed|ing|ation)\b`
does not match "discontinues". Trade-press headlines are usually present tense
("Pfizer discontinues…", "FDA approves…"), so a large share of real stories
were falling through to the general bucket and losing their event weight in the
score. Affected discontinuation, termination, approval and rejection patterns.

**`recency_component` was not a half-life.** It computed `e^(−age/half_life)`,
which returns 0.368 at one half-life, not 0.5 — the setting did not do what its
name said. Now `0.5 ^ (age/half_life)`, pinned by a test.

**Short acronyms matched common words.** The target `MET` matched the verb
"met" in "met its primary endpoint", making MET the highest-centrality node in
the graph. Fixed with a strict exact-case rule for tokens matching
`^[A-Z0-9][A-Z0-9\-/.]{0,5}$`, pinned by a regression test.

**A 64-bit SimHash overflows SQLite.** `sqlite3` refuses to bind an integer
above 2^63−1 regardless of the column type, and a 64-bit SimHash exceeds that
roughly half the time — one oversized row aborts the entire `executemany`, so
a whole ingestion batch could fail. The three ingest modules already stored it
as text, so the live path was safe, but nothing enforced that and a fourth
source added later would have broken refresh runs silently. Coercion now
happens in the store.

**Registry backronym titles read as typos.** ClinicalTrials.gov holds titles
like "Survival imProvement in Lung cancEr iNduced by DenOsUmab theRapy", where
the capitals spell the study nickname. Three conservative per-token rules now
restore ordinary casing. The repair is lossless — a test lowercases the input
and the output and asserts they are identical, so only case can ever change —
and idempotent. Real names survive via an adjacent-capital guard plus a
keep-set built from every surface form in the gazetteer, so AstraZeneca,
BioNTech, mRNA-1273, HER2, F/TAF, pCR and eGFR pass through untouched.

## Manual checks

**Pipeline determinism.** Two runs over identical stored documents produce
identical output, asserted in `test_classification_is_deterministic`.

**Rendering.** Every view was rendered in headless Chromium at 1440×1000 and
inspected. Three defects were found this way and fixed: the momentum chart
clipped its final point at the right edge; the graph hub list rendered as
`[object HTMLButtonElement]` (an array passed to `.append`); and the momentum
curve was a flat line with vertical spikes, because each event moved the index
on a single day. The last was fixed by diffusing each event's impact through an
exponential kernel over the following fortnight.

**Sign-in, end to end, with selections made.** Two defects reached the running
system because the first click-through skipped past the optional steps without
choosing anything:

- `db.add_watch` takes four arguments and was called with three. The TypeError
  surfaced as a bare 500 on the final step — but only once a company had been
  selected, since an empty selection never entered the loop.
- Therapy areas were offered only from sectors observed in the corpus, so on a
  cold start, which is exactly when sign-in runs, the step was empty. Options
  now come from the classifier's own sector taxonomy, unioned with what the
  corpus has produced, with live counts that may legitimately read zero.

The lesson recorded here: walking a flow without exercising its optional
branches is not a test of that flow. The rerun selects on every step, asserts
no `/api/*` response is 4xx or 5xx, and confirms the desk opens.

**Sign-in and graph rendering.** The full first-open flow was walked in
headless Chromium and screenshotted at every step. Four defects were found and
fixed this way: `finish()` was declared inside a Promise executor and called
from outside it, so the final button threw; `ago()` returned a calendar date
for anything over 30 days, producing "May 14 ago"; graph labels overlapped in
dense regions; and the radial layout put the largest entity group on the
smallest ring, crushing it. Labels are now placed greedily with collision
rejection, and each radial ring is sized to seat its own members.

**Removal is tested, not assumed.** `test_api.py` asserts every former graph
route now 404s and that no graph asset remains in the shipped frontend —
checking the files rather than the response code, because the SPA catch-all
serves `index.html` for any path and would otherwise make a deleted page look
alive.

**A headline that was black on black.** The base stylesheet carries
`h1, h2, h3, h4 { color: var(--ink) }` — correct on the paper-coloured desk and
invisible on the broadcast surface, which is the only inverted region in the
app. `.bc-headline` is an `h2` and never set its own colour, so it inherited
black and the headline was unreadable until the text happened to be selected.
Broadcast now resets heading colour for everything it contains, so a future
element added inside it cannot repeat the mistake.

Screenshots did not catch this: a dark headline on a dark background looks like
empty space, not like a defect. What caught it, once told, was a contrast audit
that walks every text node in the DOM, composites through translucent
ancestors to find the real backdrop, and reports any ratio below 2:1. It runs
across all seven routes plus broadcast and currently reports zero. The first
version of that audit produced twelve false positives by treating a 2%-alpha
overlay as opaque white — worth recording, because a checker that cries wolf is
worse than none.

**A kicker clipped by centring.** A flex item taller than its column overflows
equally at both ends, so on a 768px-tall display the event-class row was cut
off above the top of the story column. The story block now clips from the
bottom only, the headline and standfirst are bounded by viewport height as well
as width (`clamp(26px, min(2.9vw, 4.3vh), 48px)`), and both are clamped to
three lines. Verified at 950px and 768px heights.

**A scrollbar that belonged to another element.** The slideshow showed a
scrollbar down its right edge. The overlay itself was not overflowing — the
desk behind it was, several thousand pixels of it, still scrollable under a
`position: fixed` overlay. Headless Chromium uses overlay scrollbars, so
measuring scrollbar width returns zero and proves nothing; the check that
worked was `scrollHeight − clientHeight` on the scrolling element, which read
4172px with the overlay open and 0 after the fix. Verified at 1512×950,
1920×1080 and 1366×768, with every inner region also at zero overflow.

**Broadcast layout.** The tape track is `width: max-content` — several
thousand pixels. Grid tracks size to max-content by default, so the tape
silently stretched the entire broadcast grid to 5073px and pushed the right
rail off screen. The rail was rendering correctly the whole time; only a DOM
probe of the computed `grid-template-columns` revealed it, because the
screenshot just looked like empty black. Every ancestor of the tape is now
pinned to the viewport with `minmax(0, 1fr)` and `min-width: 0`.

**White screen after sign-in.** The save handler hid the sign-in card, then
awaited a `POST /api/preferences` that performs a full re-rank, and only then
showed the configuration playback — leaving a blank page for the duration of
the write. The playback now opens in the same tick as the request, using
statements derived client-side from what the analyst just chose, and reconciles
with the server's own account of what it applied when the response lands. A
Playwright assertion checks the playback is visible 250ms after the click.

**Empty-state behaviour.** Verified with an empty database and
`ALLOW_NETWORK=0`: all endpoints return valid empty responses, the front page
shows a first-run state, and `POST /api/refresh` returns 503 with an
explanatory message rather than substituting content.

## Not validated

**Live source behaviour was not observed during development.** The build
environment had no route to clinicaltrials.gov, fda.gov, ncbi.nlm.nih.gov or
any of the trade feeds — every request returned `403 host_not_allowed` from an
egress proxy. The ingestion code is written against the published API contracts
(ClinicalTrials.gov v2 `/studies`, NCBI E-utilities esearch/esummary, RSS 2.0
and Atom) and its parsers are unit-tested against those shapes, but the first
real fetch will happen on your machine, not this one.

`make verify` exists for exactly this reason. Run it before demonstrating the
system. It makes a real request to every source and prints the newest headline
and publisher URL it received, so you can confirm the pipeline end-to-end in
about fifteen seconds.

**Classifier precision has not been measured against a labelled set.** The unit
tests pin behaviour on hand-written cases; they are not an accuracy estimate.
Establishing precision and recall would require an analyst to label a few
hundred real stories, which is the natural next step and the reason the rules
were kept in one readable file.
