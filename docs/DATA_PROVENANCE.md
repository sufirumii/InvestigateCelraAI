# Data provenance

**This repository contains no life-sciences content.** Not one headline, company
result, trial record, or figure ships in the source tree. Everything the desk
displays is fetched at runtime from the public sources listed below and stored
in a local SQLite file that is git-ignored.

## How to verify that for yourself

```bash
make verify
```

`scripts/verify_sources.py` performs a real request against every configured
source and prints, for each one, the record count, the newest headline, and the
publisher URL. Open the URL. It is the publisher's page.

Two further checks:

```bash
# 1. Nothing in the repo is a life-sciences document.
grep -ril "phase 3\|primary endpoint" backend/ | grep -v lexicons.py
#    -> only lexicons.py, which holds regular expressions, not content.

# 2. The database is not committed.
git check-ignore -v var/investigatecelra.db
```

If the network is unavailable, the desk shows an empty edition and says so. It
never substitutes placeholder or generated content. `POST /api/refresh` returns
HTTP 503 rather than degrading silently, and `tests/test_api.py` pins that
behaviour so it cannot regress.

## Sources

Configured in `backend/investigatecelra/data/sources.json`. All are public and
keyless.

| Source | Type | Tier | What it provides |
|---|---|---|---|
| FDA press releases | RSS | regulator | Approvals, rejections, safety communications |
| FDA drug approvals | RSS | regulator | New and supplemental approvals |
| EMA news | RSS | regulator | CHMP opinions, referrals, EU actions |
| NIH news releases | RSS | registry | Publicly funded research outcomes |
| ClinicalTrials.gov API v2 | JSON API | registry | Trial status, phase, enrolment, why-stopped |
| PubMed E-utilities | JSON API | registry | Peer-reviewed literature |
| Fierce Biotech / Fierce Pharma | RSS | trade | Deals, failures, restructuring |
| BioSpace, PharmaTimes | RSS | trade | Sector news |
| Nature Biotechnology | RSS | journal | Platform and modality developments |
| Nature Reviews Drug Discovery | RSS | journal | Pipeline analysis |
| bioRxiv | RSS | preprint | Early multiomics and discovery work |

Source tier feeds directly into the authority component of the signal score: a
registry or regulator outranks trade press, which outranks a preprint.

## Companies covered

30 companies are marked `coverage: core` in
`backend/investigatecelra/data/gazetteer.json` and are queried against the trial
registry and PubMed on every refresh. They are the largest R&D spenders in the
sector plus a set of high-activity biotechs: Johnson & Johnson, Eli Lilly,
AbbVie, Merck & Co, Novo Nordisk, AstraZeneca, Roche, Novartis, Pfizer, Sanofi,
Amgen, GSK, Bristol Myers Squibb, Gilead, Boehringer Ingelheim, Takeda, Bayer,
Vertex, Regeneron, Daiichi Sankyo, Astellas, Biogen, Moderna, BioNTech, Eisai,
BeiGene, Alnylam, argenx, Ionis, CRISPR Therapeutics.

A further 51 companies are recognised when they appear in a feed but are not
actively queried, giving 81 in total. Add more by editing `CORE_COVERAGE` in
`scripts/build_gazetteer.py` and re-running `make gazetteer`.

## What the gazetteer is, and why it is not "invented data"

The gazetteer is a controlled vocabulary — a dictionary of names the entity
recogniser looks for. It contains company names, drug targets, indications,
modalities and technologies. These are terms, not claims. The file asserts that
"KRAS" is a target and "AbbVie" is a company; it asserts nothing about what
either is doing. Every factual statement in the product comes from a fetched
document and carries a link to its publisher.

The same distinction applies to `lexicons.py` (regular expressions that
recognise event language) and `excelra_assets.json` (descriptions of Excelra's
own GOSTAR and GOBIOM products). These are the system's rules and reference
data. They are the substitute for a trained model, and keeping them as readable
files is what makes every decision auditable.
