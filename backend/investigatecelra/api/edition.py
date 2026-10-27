"""Front page, story list, setbacks board and search."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query

from .. import pipeline
from ..config import settings
from ..engine.normalize import content_tokens

router = APIRouter(prefix="/api", tags=["edition"])


def _compact(item: dict) -> dict:
    """Card-sized projection — the list views never ship the full analysis."""
    return {
        "id": item["id"],
        "title": item["title"],
        "lede": item["lede"],
        "url": item["url"],
        "source": item["source"],
        "publishedAt": item["publishedAt"],
        "ageDays": item["ageDays"],
        "sector": item["sector"],
        "kind": item["kind"],
        "signal": {"value": item["signal"]["value"]},
        "band": item["band"],
        "classification": {
            "eventType": item["classification"]["eventType"],
            "label": item["classification"]["label"],
            "polarity": item["classification"]["polarity"],
            "isSetback": item["classification"]["isSetback"],
            "phase": item["classification"]["phase"],
            "confidence": item["classification"]["confidence"],
        },
        "primaryCompany": item["primaryCompany"],
        "figures": item["figures"][:3],
        "excelra": {
            "strength": item["excelra"]["strength"],
            "assets": [m["name"] for m in item["excelra"]["matches"]],
        },
        "limitationCount": len(item["limitations"]),
        "corroboration": item["corroboration"]["distinctSources"],
    }


def _filtered(
    sector: str | None, event: str | None, company: str | None,
    band: str | None, setbacks: bool, query: str | None,
) -> list[dict]:
    items = pipeline.store().items
    out = []
    q_tokens = set(content_tokens(query)) if query else set()
    for item in items:
        if sector and item["sector"] != sector:
            continue
        if event and item["classification"]["eventType"] != event:
            continue
        if company and (item.get("primaryCompany") or {}).get("id") != company:
            continue
        if band and item["band"] != band:
            continue
        if setbacks and not item["classification"]["isSetback"]:
            continue
        if q_tokens:
            haystack = set(content_tokens(f"{item['title']} {item['summary']} " +
                                          " ".join(e['name'] for e in item['entities'])))
            if not q_tokens & haystack:
                continue
        out.append(item)
    return out


@router.get("/edition")
def edition() -> dict:
    """The front page: one lead, features, briefs and sector rails."""
    store = pipeline.store()
    items = store.items
    if not items:
        return {"lead": None, "features": [], "briefs": [], "sectors": [], "setbacks": [], "stats": store.stats}

    lead = items[0]
    features = items[1:5]
    briefs = items[5: settings.edition_size]

    by_sector: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_sector[item["sector"]].append(item)
    sector_rails = [
        {
            "sector": sector,
            "count": len(group),
            "setbacks": sum(1 for i in group if i["classification"]["isSetback"]),
            "topSignal": round(max(i["signal"]["value"] for i in group), 1),
            "items": [_compact(i) for i in group[:5]],
        }
        for sector, group in sorted(by_sector.items(), key=lambda kv: -len(kv[1]))
    ]

    setbacks = [i for i in items if i["classification"]["isSetback"]][:6]

    # The tape is a continuous loop, so it wants the whole board rather than a
    # top-six. Ordered by absolute one-month move so the most eventful names
    # come round first; every company the corpus knows about appears.
    movers = sorted(
        store.companies.values(),
        key=lambda c: -abs(c["index"]["windows"]["1M"]["changePct"]),
    )

    return {
        "generatedAt": store.built_at,
        "mode": store.mode,
        "ready": store.ready,
        "lead": {**_compact(lead), "summary": lead["summary"], "excelraDetail": lead["excelra"]["matches"][:2]},
        "features": [_compact(i) for i in features],
        "briefs": [_compact(i) for i in briefs],
        "sectors": sector_rails,
        "setbacks": [_compact(i) for i in setbacks],
        "movers": [
            {
                "id": c["id"], "name": c["name"], "ticker": c["ticker"],
                "last": c["index"]["last"], "changePct": c["index"]["windows"]["1M"]["changePct"],
                "sparkline": c["sparkline"], "sector": c["sector"],
            }
            for c in movers
        ],
        "stats": store.stats,
    }


@router.get("/items")
def items(
    sector: str | None = None,
    event: str | None = None,
    company: str | None = None,
    band: str | None = None,
    setbacks: bool = False,
    q: str | None = None,
    limit: int = Query(40, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    found = _filtered(sector, event, company, band, setbacks, q)
    return {
        "total": len(found),
        "offset": offset,
        "limit": limit,
        "items": [_compact(i) for i in found[offset: offset + limit]],
    }


@router.get("/items/{item_id}")
def item_detail(item_id: str) -> dict:
    item = pipeline.store().by_id.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="story not found")
    return item


@router.get("/setbacks")
def setbacks_board() -> dict:
    """Failures, holds, terminations and stated limitations in one place."""
    store = pipeline.store()
    items = [i for i in store.items if i["classification"]["isSetback"]]

    by_type: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_type[item["classification"]["label"]].append(_compact(item))

    limitations = []
    for item in store.items:
        for lim in item["limitations"]:
            limitations.append(
                {
                    "statement": lim["statement"],
                    "cue": lim["cue"],
                    "itemId": item["id"],
                    "title": item["title"],
                    "company": (item.get("primaryCompany") or {}).get("name"),
                    "sector": item["sector"],
                    "source": item["source"]["name"],
                    "publishedAt": item["publishedAt"],
                }
            )
    limitations.sort(key=lambda l: l["publishedAt"], reverse=True)

    stopped_trials = [
        {
            "id": t["id"], "nctId": t.get("nct_id"), "title": t["title"],
            "sponsor": t["sponsor"], "status": t["status"], "phase": t["phase"],
            "whyStopped": t.get("why_stopped", ""), "conditions": t.get("conditions", ""),
            "enrollment": t.get("enrollment"), "updatedAt": t.get("updated_at"),
        }
        for t in store.trials if t.get("isSetback")
    ]

    return {
        "total": len(items),
        "byType": [{"label": k, "count": len(v), "items": v} for k, v in
                   sorted(by_type.items(), key=lambda kv: -len(kv[1]))],
        "limitations": limitations[:40],
        "stoppedTrials": stopped_trials,
    }


@router.get("/search")
def search(q: str = Query(..., min_length=2), limit: int = 25) -> dict:
    store = pipeline.store()
    q_tokens = set(content_tokens(q))
    lowered = q.lower()
    scored: list[tuple[float, dict]] = []
    for item in store.items:
        title_tokens = set(content_tokens(item["title"]))
        body_tokens = set(content_tokens(item["summary"]))
        entity_names = " ".join(e["name"] for e in item["entities"]).lower()
        hit = 0.0
        hit += 3.0 * len(q_tokens & title_tokens)
        hit += 1.0 * len(q_tokens & body_tokens)
        if lowered in entity_names:
            hit += 2.5
        if hit <= 0:
            continue
        scored.append((hit + item["signal"]["value"] / 100.0, item))
    scored.sort(key=lambda s: -s[0])

    # Entity matches, counted from the documents that mention them.
    seen: dict[str, dict] = {}
    for item in store.items:
        for entity in item.get("entities", []):
            if lowered not in entity["name"].lower():
                continue
            row = seen.setdefault(entity["id"], {**entity, "mentions": 0})
            row["mentions"] += 1
    entities = sorted(seen.values(), key=lambda e: (-e["mentions"], e["name"]))[:8]

    return {
        "query": q,
        "items": [_compact(i) for _, i in scored[:limit]],
        "entities": entities,
        "companies": [
            {"id": c["id"], "name": c["name"], "ticker": c["ticker"], "sector": c["sector"]}
            for c in store.companies.values() if lowered in c["name"].lower()
        ][:8],
    }


@router.get("/trials")
def trials(sponsor: str | None = None, status: str | None = None) -> dict:
    store = pipeline.store()
    rows = store.trials
    if sponsor:
        rows = [t for t in rows if t.get("sponsorEntityId") == sponsor or sponsor.lower() in t["sponsor"].lower()]
    if status:
        rows = [t for t in rows if t.get("status", "").lower() == status.lower()]
    return {
        "total": len(rows),
        "trials": [
            {
                "id": t["id"], "nctId": t.get("nct_id"), "title": t["title"],
                "sponsor": t["sponsor"], "status": t["status"], "phase": t["phase"],
                "conditions": t.get("conditions"), "interventions": t.get("interventions"),
                "enrollment": t.get("enrollment"), "startDate": t.get("start_date"),
                "updatedAt": t.get("updated_at"), "whyStopped": t.get("why_stopped"),
                "url": t.get("url"), "isSetback": t.get("isSetback"),
                "linkedEntities": [
                    {"id": e[0], "name": e[1], "kind": e[2]} for e in t.get("linkedEntities", [])
                ],
            }
            for t in rows
        ],
    }
