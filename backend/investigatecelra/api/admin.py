"""System metadata, methodology transparency, Excelra value view and exports."""

from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse

from .. import db, pipeline
from ..config import settings
from ..engine.classify import ALL_EVENT_TYPES
from ..engine.lexicons import EVENT_TYPES, SOURCE_TIERS
from ..engine.relevance import asset_catalogue, load_assets
from ..engine.score import COMPONENT_LABELS, WEIGHTS
from ..ingest.base import source_registry

log = logging.getLogger("investigatecelra.api")

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/meta")
def meta() -> dict:
    store = pipeline.store()
    return {
        "app": settings.app_name,
        "tagline": settings.tagline,
        "classification": settings.classification,
        "generatedAt": store.built_at,
        "dataMode": store.mode,
        "ready": store.ready,
        "gateEnabled": settings.gate_enabled,
        "lastRefresh": db.get_meta("last_refresh"),
        "stats": store.stats,
        "sectors": store.sectors,
        "eventTypes": ALL_EVENT_TYPES,
        "preferences": store.preferences,
        "bands": ["critical", "high", "moderate", "routine"],
        "sources": [
            {"id": s["id"], "name": s["name"], "tier": s.get("tier", "unknown"), "type": s.get("type")}
            for s in source_registry()
        ],
    }


@router.get("/preferences")
def get_preferences() -> dict:
    """What the analyst chose at sign-in, plus the vocabularies to choose from.

    Options are derived from the live corpus and the gazetteer, so the sign-in
    screen never offers a therapy area or a company that does not exist in the
    data currently loaded.
    """
    store = pipeline.store()
    g = pipeline.gazetteer()
    counts: dict[str, int] = {}
    for item in store.items:
        counts[item["sector"]] = counts.get(item["sector"], 0) + 1

    companies = sorted(
        (
            {
                "id": c["id"],
                "name": c["name"],
                "sector": c.get("sector", ""),
                "ticker": c.get("ticker", ""),
                "items": c.get("itemCount", 0),
            }
            for c in store.companies.values()
        ),
        key=lambda c: (-c["items"], c["name"]),
    )
    if not companies:
        companies = sorted(
            (
                {"id": e.id, "name": e.name, "sector": "", "ticker": e.meta.get("ticker", ""), "items": 0}
                for e in g.entities.values()
                if e.meta.get("coverage") == "core"
            ),
            key=lambda c: c["name"],
        )

    # The taxonomy first, then anything the corpus produced that is not in it,
    # so the list is complete on a cold start and still reflects reality once
    # stories are in. Counts are live and may legitimately be zero.
    observed = list(store.sectors)
    ordered = [s for s in pipeline.sector_vocabulary() if s in observed or not observed]
    ordered += [s for s in observed if s not in ordered]

    return {
        "preferences": store.preferences,
        "corpusReady": bool(store.items),
        "options": {
            "sectors": [{"id": s, "count": counts.get(s, 0)} for s in ordered],
            "eventTypes": ALL_EVENT_TYPES,
            "companies": companies,
        },
    }


@router.post("/preferences")
def set_preferences(payload: dict) -> dict:
    try:
        prefs = pipeline.save_preferences(payload)
    except Exception as exc:  # noqa: BLE001 - the analyst needs the reason
        log.exception("failed to save preferences")
        raise HTTPException(
            status_code=500,
            detail=f"Preferences could not be saved: {exc}",
        ) from exc
    store = pipeline.store()
    return {
        "preferences": prefs.as_dict(),
        "statements": prefs.describe(),
        "stats": store.stats,
    }


@router.get("/health")
def health() -> dict:
    store = pipeline.store()
    return {"status": "ok" if store.items else "empty", "items": len(store.items), "builtAt": store.built_at}


@router.get("/method")
def method() -> dict:
    """Full transparency on how the newspaper is written. No model, no prompt."""
    return {
        "principle": (
            "Every ranking, label and relevance judgement in this system is produced by "
            "deterministic code over public data. There is no language model in the pipeline, "
            "so the same corpus always yields the same edition and any output can be traced to "
            "a rule."
        ),
        "stages": [
            {"id": "ingest", "name": "Ingest",
             "detail": "Keyless GETs against public feeds, ClinicalTrials.gov API v2 and PubMed E-utilities."},
            {"id": "normalise", "name": "Normalise",
             "detail": "Markup stripped, entities decoded, dates parsed to UTC, sentences segmented with an abbreviation guard."},
            {"id": "dedupe", "name": "Deduplicate",
             "detail": "64-bit SimHash over content tokens; documents within a 7-bit Hamming distance collapse into one story, and the echoing outlets become corroboration evidence."},
            {"id": "entities", "name": "Recognise entities",
             "detail": "Longest-match scan against a curated gazetteer of companies, assets, targets, indications, modalities and technologies."},
            {"id": "classify", "name": "Classify the event",
             "detail": "Weighted regex vote across a 14-class event taxonomy with negation guarding. Headline matches count triple."},
            {"id": "extract", "name": "Extract evidence",
             "detail": "Limitation sentences are quoted verbatim when they contain a caveat cue; numeric facts are pulled by pattern."},
            {"id": "summarise", "name": "Summarise",
             "detail": "Extractive only. Sentences are ranked on term density, lead position, salient vocabulary, numerals and topicality, then reproduced in original order."},
            {"id": "relevance", "name": "Assess Excelra relevance",
             "detail": "Rule table in excelra_assets.json maps event type, entity kinds, modality and vocabulary onto Excelra capabilities."},
            {"id": "score", "name": "Score the signal",
             "detail": "Weighted sum of six bounded components; the breakdown travels with every story."},
            {"id": "index", "name": "Compute momentum",
             "detail": "Daily index per company from signed event impact with mean reversion toward a 100 baseline."},
        ],
        "scoring": {
            "formula": "signal = 100 · Σ (weightᵢ × componentᵢ)",
            "components": [
                {"id": k, "label": COMPONENT_LABELS[k], "weight": v} for k, v in WEIGHTS.items()
            ],
            "bands": {"critical": "≥ 72", "high": "58 – 71", "moderate": "42 – 57", "routine": "< 42"},
        },
        "taxonomy": [
            {
                "id": k, "label": v["label"], "polarity": v["polarity"],
                "weight": v["weight"], "ruleCount": len(v["patterns"]),
            }
            for k, v in sorted(EVENT_TYPES.items(), key=lambda kv: -kv[1]["weight"])
        ],
        "sourceTiers": SOURCE_TIERS,
        "runs": db.recent_runs(8),
        "stats": pipeline.store().stats,
    }


@router.get("/excelra")
def excelra_view() -> dict:
    """The 'Why Excelra' answer, computed from the live corpus rather than asserted."""
    store = pipeline.store()
    tally: dict[str, dict] = {}
    for item in store.items:
        for match in item["excelra"]["matches"]:
            row = tally.setdefault(
                match["assetId"],
                {"assetId": match["assetId"], "name": match["name"], "hits": 0,
                 "sectors": defaultdict(int), "examples": []},
            )
            row["hits"] += 1
            row["sectors"][item["sector"]] += 1
            if len(row["examples"]) < 3:
                row["examples"].append(
                    {
                        "itemId": item["id"], "title": item["title"],
                        "reason": match["reasons"][0] if match["reasons"] else "",
                        "contribution": match["contribution"],
                    }
                )

    catalogue = {a["id"]: a for a in load_assets()}
    coverage = []
    for asset_id, row in sorted(tally.items(), key=lambda kv: -kv[1]["hits"]):
        base = catalogue.get(asset_id, {})
        coverage.append(
            {
                "assetId": asset_id,
                "name": row["name"],
                "fullName": base.get("full_name", ""),
                "summary": base.get("summary", ""),
                "supports": base.get("supports", ""),
                "value": base.get("value", ""),
                "hits": row["hits"],
                "share": round(100 * row["hits"] / max(1, len(store.items)), 1),
                "sectors": dict(sorted(row["sectors"].items(), key=lambda kv: -kv[1])),
                "examples": row["examples"],
            }
        )

    setbacks = sum(1 for i in store.items if i["classification"]["isSetback"])
    return {
        "catalogue": asset_catalogue(),
        "coverage": coverage,
        "users": [
            {"role": "Competitive intelligence analyst",
             "need": "Know within the day which competitor moves change the landscape, and why.",
             "served": "Signal-ranked edition with a scored, inspectable justification per story."},
            {"role": "Market & product intelligence analyst",
             "need": "Track where a therapy area is heading and where whitespace is opening.",
             "served": "Sector rails, the momentum index and per-company programme views."},
            {"role": "Commercial analytics team",
             "need": "Quantify the portfolio impact of competitor setbacks and approvals.",
             "served": "Setbacks board, momentum series and per-company programme view."},
            {"role": "Medical information team",
             "need": "Field questions about competitor data with the evidence and its stated limitations.",
             "served": "Verbatim limitation extraction with source attribution on every story."},
        ],
        "impact": {
            "storiesTriaged": len(store.items),
            "setbacksSurfaced": setbacks,
            "limitationsExtracted": sum(len(i["limitations"]) for i in store.items),
            "trialsTracked": store.stats.get("trials", 0),
            "sourcesMonitored": len(source_registry()),
        },
    }


@router.post("/refresh")
def refresh(live: bool | None = None) -> dict:
    try:
        return pipeline.refresh(live=live)
    except RuntimeError as exc:
        # The desk has no bundled corpus to fall back on, so an unreachable
        # network is a real, reportable failure rather than a silent downgrade.
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/export/brief.md", response_class=PlainTextResponse)
def export_brief(sector: str | None = None, limit: int = 15) -> str:
    """A markdown intelligence brief an analyst can paste into a deck or email."""
    store = pipeline.store()
    items = [i for i in store.items if not sector or i["sector"] == sector][:limit]
    lines = [
        f"# {settings.app_name} — Intelligence Brief",
        f"_{settings.classification} · generated {store.built_at}_",
        "",
        f"**Corpus:** {store.stats.get('analysed', 0)} stories · "
        f"{store.stats.get('setbacks', 0)} setbacks · "
        f"{store.stats.get('companies', 0)} companies tracked",
        "",
    ]
    lines += [f"> Sources: {store.stats.get('sources', 0)} public feeds and registries. "
              f"Every item below links to its original publisher.", ""]

    for n, item in enumerate(items, 1):
        company = (item.get("primaryCompany") or {}).get("name", "—")
        lines += [
            f"## {n}. {item['title']}",
            f"`{item['classification']['label']}` · **{company}** · {item['sector']} · "
            f"signal {item['signal']['value']} ({item['band']})",
            "",
            item["summary"] or item["lede"],
            "",
        ]
        if item["limitations"]:
            lines.append("**Stated limitations**")
            lines += [f"- {l['statement']}" for l in item["limitations"]]
            lines.append("")
        if item["excelra"]["matches"]:
            lines.append("**Excelra angle**")
            lines += [f"- _{m['name']}_ — {m['contribution']}" for m in item["excelra"]["matches"]]
            lines.append("")
        lines += [f"Source: {item['source']['name']} · {item['publishedAt']}", "", "---", ""]
    return "\n".join(lines)


@router.get("/export/signals.csv")
def export_csv(sector: str | None = None) -> Response:
    store = pipeline.store()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "published_at", "company", "sector", "event_type", "is_setback",
        "phase", "signal", "band", "confidence", "sources", "excelra_assets", "title", "url",
    ])
    for item in store.items:
        if sector and item["sector"] != sector:
            continue
        writer.writerow([
            item["id"], item["publishedAt"],
            (item.get("primaryCompany") or {}).get("name", ""),
            item["sector"], item["classification"]["eventType"],
            int(item["classification"]["isSetback"]), item["classification"]["phase"] or "",
            item["signal"]["value"], item["band"], item["classification"]["confidence"],
            item["corroboration"]["distinctSources"],
            "|".join(m["name"] for m in item["excelra"]["matches"]),
            item["title"], item["url"],
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="investigatecelra-signals.csv"'},
    )
