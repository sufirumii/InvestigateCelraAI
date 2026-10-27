# Architecture

## Shape

One Python process. FastAPI serves both the JSON API and the static frontend;
SQLite holds fetched documents. There is no build step, no `node_modules`, no
model weights, and no second service to deploy.

```
public sources ──► ingest ──► SQLite ──► pipeline ──► in-memory Store ──► API ──► browser
                                            │
                                            └─► momentum index, programme views
```

The pipeline runs on startup and on every refresh, producing an immutable
`Store` snapshot that the API reads. Requests never touch the analysis code,
so the desk stays responsive while a refresh is in flight.

## The eleven stages

| # | Stage | Module | What it does |
|---|---|---|---|
| 1 | Ingest | `ingest/` | Fetch RSS, ClinicalTrials.gov v2, PubMed |
| 2 | Normalise | `engine/normalize.py` | Strip HTML, split sentences, parse dates |
| 3 | Deduplicate | `engine/normalize.py` | SimHash, ≤7-bit Hamming distance |
| 4 | Recognise entities | `engine/entities.py` | Longest-match trie over the gazetteer |
| 5 | Classify event | `engine/classify.py` | Weighted regex vote across 15 classes |
| 6 | Extract limitations | `engine/classify.py` | Sentences carrying a caveat cue, quoted verbatim |
| 7 | Summarise | `engine/summarize.py` | Extractive sentence ranking |
| 8 | Assess relevance | `engine/relevance.py` | Rule table mapping events to Excelra capabilities |
| 9 | Score | `engine/score.py` | Six weighted components, 0–100 |
| 10 | Cluster | `pipeline.py` | Same company + event within 6 days |
| 11 | Index | `engine/index.py` | Momentum series per company |

Every stage is a pure function of its input. Running the pipeline twice over
the same stored documents produces byte-identical output — asserted by
`test_classification_is_deterministic`.

## Why no model

The users are competitive-intelligence analysts whose output goes into
portfolio decisions. They need to know *why* a story was ranked first, and they
need to be able to challenge it. A rule table can be read, argued with, and
edited by the analyst who disagrees. The reader panel shows the exact regular
expressions that produced each label and the arithmetic behind each score.

The trade-off is real: the classifier only knows the language written into
`lexicons.py`, and unusual phrasing falls through to a general bucket. That
failure is visible and fixable — add a pattern, re-run. A model's failures are
neither.

## Signal score

```
signal = 100 × (0.24·recency + 0.16·authority + 0.22·event
               + 0.16·impact + 0.12·corroboration + 0.10·portfolio)
```

Each component is bounded to [0, 1]. Recency is `0.5 ^ (age / half_life)` with a
nine-day half-life. Authority is the source tier. Event is the class weight
scaled by classifier confidence. Impact combines trial phase with how many
targets and indications are named. Corroboration counts distinct outlets
carrying the same development. Portfolio covers watchlist membership and
Excelra rule-match strength.

Bands: critical ≥ 72, high ≥ 58, moderate ≥ 42, routine below.

## Momentum index

Not a share price. A daily series computed from a company's own event flow:

```
indexₜ = indexₜ₋₁ · (1 + pressureₜ − 0.035·(indexₜ₋₁ − 100)/100)
pressureₜ = Σᵢ impactᵢ · e^(−Δᵢ/11) / Σ weights
```

Each story exerts influence over the following fortnight rather than on one
day, so the curve is continuous. The mean-reversion term returns a quiet
company to the 100 baseline, making the chart a reading of current momentum
rather than accumulated history.

