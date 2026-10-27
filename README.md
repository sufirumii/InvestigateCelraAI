# InvestigateCelra

**A life-sciences commercial intelligence desk that reads like a newspaper.**

Every morning it reads the regulator feeds, the trial registry, the literature
and the trade press for 30 of the largest R&D companies in the sector, ranks
what it finds, separates the setbacks from the progress, and quotes the
limitations competitors state about their own work.

There is no model anywhere in it. Every decision is a rule you can read.

---

## Two things to know before you run it

**1. This repository contains no life-sciences content.** Not one headline,
company result, trial record or figure ships in the source tree. Everything you
see in the product is fetched at runtime from public sources and stored in a
git-ignored SQLite file. With no network, the desk shows an empty edition and
says so — it never substitutes placeholder content. See
[docs/DATA_PROVENANCE.md](docs/DATA_PROVENANCE.md), which also shows you how to
verify that claim yourself.

**2. Run `make verify` first.** It makes a real request to every configured
source and prints the record count, newest headline and publisher URL for each.
Fifteen seconds, and you know the pipeline works end to end before you show it
to anyone.

---

## Quick start

```bash
pip install -r requirements-dev.txt
cp .env.example .env        # set HTTP_USER_AGENT to a real contact address
make verify                 # prove the sources are reachable
make run                    # http://127.0.0.1:8000
```

Or open the project in PyCharm or VS Code and press Run on `run.py` —
step-by-step IDE setup is in [docs/PYCHARM.md](docs/PYCHARM.md). Python 3.11+
and outbound HTTPS are the only requirements — no Node, no database server, no
model download.

The first load shows "Building the first edition" while the initial fetch runs,
then the page loads itself. Deployment instructions, including the Render
blueprint, are in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## What it does

**Sign-in.** On first open the desk asks who is reading and what they want
ranked first — therapy areas, event classes, companies — then plays back what
it applied. Every option offered is read from the live corpus, and the choices
shift the ranking rather than filtering it: a chosen area rises, the others do
not disappear. Details in [docs/PERSONALISATION.md](docs/PERSONALISATION.md).

**Broadcast mode.** *Initiate slideshow* turns the edition into a full-screen,
auto-advancing news display for a wall screen or the front of a room — lower
third, live clock, momentum tape, signal score, and the next four stories
queued in the rail. The running order is the signal ranking; nothing is curated
for it. See [docs/BROADCAST.md](docs/BROADCAST.md).

**Front page.** A ranked edition: lead story with its full score breakdown, a
ticker of momentum movers, feature cards, therapy-area rails, and the day's
briefs. Placement is never arbitrary — open any story and the reader panel
shows the exact regular expressions that produced its label and the arithmetic
behind its score.

**Setbacks.** The view the product exists for. Failures, discontinuations,
safety holds, regulatory rejections and restructuring, separated out and
grouped by class, alongside registry records of stopped trials with the
sponsor's own stated reason. Underneath, every sentence in the corpus that
carries a caveat cue — *"the open-label design limits interpretation"* — quoted
verbatim and never paraphrased.

**Momentum.** An Apple Stocks-style board. The Intelligence Momentum Index is
not a share price; it is a daily series computed from a company's own event
flow, with each story's influence diffused across the following fortnight and a
mean-reversion pull back to a 100 baseline. Scrub the chart to read any day.

**Why Excelra.** Capability coverage counted from live rule matches against the
current corpus — GOSTAR, GOBIOM, data curation, bioinformatics and commercial
analytics — not asserted.

**Method.** The eleven pipeline stages, the scoring formula with per-component
weights, the full event taxonomy, and the ingestion run history including
failures.

---

## How it works

```
public sources ──► ingest ──► SQLite ──► pipeline ──► Store ──► API ──► browser
                                            │
                                            └─► momentum index, programme views
```

One Python process. FastAPI serves both the JSON API and the static frontend;
there is no build step and no `node_modules`. The pipeline runs on startup and
on refresh, producing an immutable snapshot the API reads, so the desk stays
responsive while a refresh is in flight.

Eleven deterministic stages: ingest → normalise → SimHash deduplicate →
recognise entities → classify event → extract limitations → summarise → assess
Excelra relevance → score → cluster → graph and index. Running it twice over
the same documents produces byte-identical output.

```
signal = 100 × (0.24·recency + 0.16·authority + 0.22·event
               + 0.16·impact + 0.12·corroboration + 0.10·portfolio)
```

Full detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Why no LLM

The users are competitive intelligence analysts whose output feeds portfolio
decisions. They need to know *why* a story ranked first, and to be able to
argue with it. A rule table can be read, challenged and edited by the analyst
who disagrees.

The trade-off is real and worth stating: the classifier only knows the language
written into `lexicons.py`, and unusual phrasing falls through to a general
bucket. That failure is visible and fixable — add a pattern, re-run. A model's
failures are neither.

---

## Technology

Two, within the two-to-three the brief allows. A third — Knowledge Graphs — was
built and then removed once it stopped earning its place; that decision is
recorded rather than erased. Both are justified at length in
[docs/TECHNOLOGY_CHOICES.md](docs/TECHNOLOGY_CHOICES.md).

| | Why |
|---|---|
| **Python + FastAPI** | The work is text processing and arithmetic; the standard library covers all of it. FastAPI gives request validation and an OpenAPI schema at `/docs` for free, and serves the frontend from the same process. |
| **SQL (SQLite)** | Durability, deduplication on primary key, and corroboration counts across sources. Zero administration, no managed database on Render, and the schema is ordinary SQL if it needs to become PostgreSQL. |

Deliberately unused: no LLM, no Claude API, no MCP, no agents, no AWS, no N8N.

---

## Layout

```
backend/investigatecelra/
  engine/       classify, entities, score, index, summarize, normalize,
                relevance, lexicons     — the analysis, no I/O
  ingest/       rss, clinicaltrials, pubmed, base
  api/          edition, companies, admin
  data/         gazetteer.json, excelra_assets.json, sources.json
  pipeline.py   the eleven stages
  db.py         SQLite schema and access
  main.py       app, routes, static mounts, access gate
frontend/
  index.html    styles/  js/  assets/
scripts/        build_gazetteer.py, verify_sources.py
tests/          52 tests
docs/           ARCHITECTURE, WHY_EXCELRA, TECHNOLOGY_CHOICES,
                DATA_PROVENANCE, VALIDATION, DEPLOYMENT, PYCHARM,
                PERSONALISATION, BROADCAST
```

---

## Validation

`make test` — 63 tests. Writing them found five real bugs, all fixed and now
pinned: present-tense verbs like "discontinues" were unmatched by the event
rules (trade headlines are almost always present tense, so this was dropping a
large share of real stories); `recency_component` implemented a 1/e decay while
claiming a half-life; the short-acronym target `MET` was matching the verb
"met", making it the highest-centrality node in the graph; and a 64-bit SimHash
exceeds SQLite's signed-integer range about half the time, so a single
oversized row could abort a whole ingestion batch; and `db.add_watch` was
called with three of its four arguments, which turned the last step of sign-in
into a 500 as soon as an analyst selected a company.

Three rendering defects were found by inspecting headless-Chromium screenshots
of every view and fixed: the momentum chart clipped its final point, the graph
hub list rendered as `[object HTMLButtonElement]`, and the momentum curve was a
flat line with vertical spikes before each event's impact was diffused across
the following fortnight.

**Not validated:** live source behaviour was never observed during development.
The build environment had no route to any of the sources — every request
returned `403 host_not_allowed` from an egress proxy. The ingestion code is
written against the published API contracts and its parsers are unit-tested,
but the first real fetch happens on your machine. This is what `make verify` is
for. Full account in [docs/VALIDATION.md](docs/VALIDATION.md).

---

## Limits

The desk reads English-language public sources. It cannot see subscription
databases, conference abstracts, or anything behind a paywall — where a good
deal of competitive signal lives. The classifier recognises only the language
in its lexicon. The momentum index is a reading of news flow, not a market
instrument, and should never be presented as one.

These are the boundaries of a triage tool. It is built to make the first hour
of an analyst's day useful, not to replace their judgement.

---

Logo assets in `frontend/assets/` are unmodified from the original project.
