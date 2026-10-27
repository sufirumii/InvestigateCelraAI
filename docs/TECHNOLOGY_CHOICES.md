# Technology choices

The brief permits two to three technologies from the approved list. Two are
used: **Python with FastAPI** and **SQL (SQLite)**.

A third, Knowledge Graphs, was built and then removed. That decision is
recorded at the end of this document rather than quietly erased.

## 1. Python with FastAPI

**What it does here.** Runs the entire analysis pipeline and serves both the
JSON API and the static frontend from one process.

**Why.** The work is text processing and arithmetic: regex classification,
SimHash deduplication, TF-IDF keywords, PageRank. Python's standard library
covers all of it — `re`, `hashlib`, `xml.etree`, `urllib`, `math`, `sqlite3` —
so the dependency list is two entries and neither is a framework for machine
learning.

FastAPI specifically, over Flask or Django: type-hinted handlers give request
validation and an OpenAPI schema at `/docs` with no extra code, which matters
when the deliverable must be *technically demonstrable*. Its ability to mount
static files means the frontend needs no second service and no build step.

**Rejected alternative.** The original prototype was Next.js. It required
Node, a build step, `node_modules`, and a separate API surface, for a product
whose frontend is entirely read-only. Serving hand-written ES modules from
FastAPI removed a whole runtime.

## 2. SQL (SQLite)

**What it does here.** Persists fetched documents and trials, deduplicates on
primary key, and records ingestion run history.

**Why.** The desk needs durability across restarts and a corroboration count
across sources — both natural in SQL. SQLite in WAL mode handles this with
zero administration, and the "server" is a file, so Render's free tier needs no
managed database and the reviewer needs no `docker compose` to run it.

The schema is ordinary SQL. Repointing `DATABASE_PATH` at PostgreSQL is a
connection-string change and a handful of type adjustments, not a rewrite.

**Rejected alternatives.** MongoDB — the data is uniform and relational, so a
document store buys nothing and loses joins. PySpark and Databricks — the
corpus is thousands of documents, not billions; distributed compute would add
a cluster to manage and make the project harder to run from an IDE, which the
brief requires.

## What was deliberately not used

**No LLM, no Claude API, no MCP, no agents.** The brief's approved list
includes them; this system rejects them on purpose. Its users must be able to
defend a ranking to a client. Every decision here is a rule they can read and
change — the reader panel shows the exact regexes that produced each label and
the arithmetic behind each score. A model would make the output better-written
and unauditable, which is the wrong trade for competitive intelligence.

**No AWS, no N8N.** One `pip install` and one process. Adding orchestration or
managed services would increase the operational surface without changing what
the product does.

## The technology that was removed

An in-process property graph shipped in an earlier build: typed nodes for
companies, assets, targets, indications and trials, BFS path-finding, PageRank
centrality, and a Cypher export for Neo4j. It worked, and it was removed
anyway.

The reason is that it never earned its place in the workflow. The question it
answered well — *if this target fails here, what else is exposed?* — is a real
analyst question, but on a corpus of public news the co-occurrence edges behind
it were thin evidence: two entities named in the same press release is a weak
basis for asserting a relationship, and an analyst cannot act on a link they
would have to re-verify by hand. It looked impressive in a demo and was rarely
the thing anyone opened second.

What replaced it is narrower and better supported. The per-company **programme
view** now reads assets, targets, indications and modality straight off the
documents that mention them, and reports how many documents back each row, so
the evidence is countable and visible. Entity search does the same. Nothing
that was genuinely load-bearing was lost.

Two technologies still satisfies the brief, and a capability that is removed
when it stops paying for itself is a better answer than one kept because it
was already built.
