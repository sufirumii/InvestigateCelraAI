# Why Excelra

The brief asks six questions. Answered in order.

## 1. Who could use this?

**Primary: competitive intelligence analysts** in Commercial Analytics. They
track competitor pipelines and are measured on catching a development before it
reaches a client's slide deck.

**Primary: market and product intelligence analysts.** They size opportunities
and need to know when a competitor's programme weakens, because that is when a
window opens.

**Secondary: Medical Information teams.** They field questions on competitor
safety and efficacy and need the source-quoted position, not a summary.

**Secondary: business development.** Partnership and M&A activity, and the
setbacks that precede it, are the leading indicator of a company coming to
market.

## 2. What work does it support?

Daily competitive monitoring, pipeline tracking, competitor setback analysis,
opportunity identification, and the evidence-gathering step of a client
deliverable. The Markdown brief and CSV exports exist so the output goes
straight into that deliverable rather than being retyped.

## 3. What data does it use?

Public regulatory feeds (FDA, EMA), the NIH newsroom, ClinicalTrials.gov API
v2, PubMed E-utilities, trade press, and journal feeds. All keyless, all
fetched at runtime. Full list and verification procedure in
[DATA_PROVENANCE.md](DATA_PROVENANCE.md).

## 4. What inefficiency or opportunity does it address?

The inefficiency is triage, not analysis. An analyst covering thirty companies
reads several hundred items a week to find the ten that matter. That reading is
undifferentiated: nothing is ranked, so urgency is decided by what arrived most
recently. Three teams rediscover the same competitor limitation independently
because none of them knows the others found it.

Two things are lost in that process:

**Setbacks are systematically under-recorded.** Approvals get written up;
quiet discontinuations do not. But a competitor's Phase 3 miss is the most
commercially actionable event there is, and it is usually one paragraph in a
trade newsletter.

**Stated limitations are discarded.** When a sponsor writes "the open-label
design limits interpretation", that sentence is the honest boundary of their
own claim. It is exactly what a Medical Information team needs and exactly what
a summary removes. The desk extracts these verbatim and never paraphrases them.

## 5. How does Excelra contribute?

The desk performs triage. It does not perform analysis, and it is not trying
to. Its output is a ranked, deduplicated, source-linked queue — the input to
Excelra's actual work.

The connection is made explicit by a rule table
(`data/excelra_assets.json`) that maps event patterns onto specific
capabilities:

| Trigger | Capability | Why |
|---|---|---|
| Target or SAR-related event | **GOSTAR** | 10.6M+ curated structure–activity records to place the compound in its chemical series |
| Biomarker or stratification event | **GOBIOM** | Curated biomarker evidence from 200k+ sources to explain why a readout landed where it did |
| Multi-source, conflicting reports | **Data curation & FAIRification** | The reconciliation the desk deliberately does not attempt |
| Multiomics or genomics signal | **Bioinformatics services** | Interpretation the desk cannot do from text |
| Commercial or portfolio event | **Commercial analytics** | Sizing and positioning |

Every match on the "Why Excelra" page is counted from live rule hits against
the current corpus. Nothing there is asserted.

## 6. What value is created?

- **Triage time.** Several hundred items a week reduced to a ranked edition,
  with the reason for each placement visible.
- **Setback visibility.** A dedicated view for failures, holds, terminations,
  rejections and restructuring — the category most likely to be missed and
  most likely to be commercially useful.
- **Defensible sourcing.** Every claim links to its publisher; every
  limitation is a verbatim quote. An analyst can defend the brief in a client
  meeting.
- **Programme visibility.** A company profile lists the assets named in its
  coverage with the targets, indications and modality named alongside them, and
  how many documents support each row.
- **Shared evidence base.** Commercial and Medical teams work from the same
  ranked record on the same morning.

## Honest limits

The desk reads English-language public sources. It cannot see subscription
databases, conference abstracts, or anything behind a paywall — which is where
a good deal of competitive signal lives. The classifier only recognises
language present in its lexicon. The momentum index is a reading of news flow,
not a market instrument, and should never be presented as one.

These are the boundaries of a triage tool. It is designed to make the first
hour of an analyst's day useful, not to replace their judgement.
