"""Company profiles, the markets board and the watchlist."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import db, pipeline
from ..engine.normalize import iso, now_utc

router = APIRouter(prefix="/api", tags=["companies"])

RANGE_DAYS = {"1W": 7, "1M": 30, "3M": 90, "6M": 182, "1Y": 365, "ALL": 3650}


class WatchRequest(BaseModel):
    entityId: str = Field(min_length=2)
    focus: str = ""


def _card(company: dict) -> dict:
    return {
        "id": company["id"],
        "name": company["name"],
        "ticker": company["ticker"],
        "sector": company["sector"],
        "subtype": company["subtype"],
        "last": company["index"]["last"],
        "change": company["index"]["change"],
        "changePct": company["index"]["changePct"],
        "windows": company["index"]["windows"],
        "high": company["index"]["high"],
        "low": company["index"]["low"],
        "volatility": company["index"]["volatility"],
        "sparkline": company["sparkline"],
        "itemCount": company["itemCount"],
        "setbackCount": company["setbackCount"],
        "trialCount": company["trialCount"],
        "activeTrials": company["activeTrials"],
        "lastActivity": company["lastActivity"],
        "topSignal": company["topSignal"],
    }


@router.get("/companies")
def list_companies(sector: str | None = None, sort: str = "signal") -> dict:
    store = pipeline.store()
    watch = {w["entity_id"] for w in db.get_watchlist()}
    rows = [c for c in store.companies.values() if not sector or c["sector"] == sector]

    keys = {
        "signal": lambda c: -c["topSignal"],
        "activity": lambda c: -c["itemCount"],
        "momentum": lambda c: -c["index"]["windows"]["1M"]["changePct"],
        "setbacks": lambda c: -c["setbackCount"],
        "name": lambda c: c["name"],
    }
    rows.sort(key=keys.get(sort, keys["signal"]))

    return {
        "total": len(rows),
        "companies": [{**_card(c), "onWatchlist": c["id"] in watch} for c in rows],
    }


@router.get("/companies/{company_id}")
def company_detail(company_id: str, range: str = Query("6M")) -> dict:
    store = pipeline.store()
    company = store.companies.get(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="company not tracked in the current corpus")

    days = RANGE_DAYS.get(range.upper(), 182)
    series = company["series"][-days:] if days < len(company["series"]) else company["series"]

    items = [i for i in store.items if (i.get("primaryCompany") or {}).get("id") == company_id]
    trials = [t for t in store.trials if t.get("sponsorEntityId") == company_id]

    # Programme view, read straight off the documents: an asset named in a
    # story about this company, together with the targets, indications and
    # modality named in those same stories. Co-occurrence within one document
    # is the evidence, and `evidence` is how many documents support it.
    programmes: dict[str, dict] = {}
    for item in items:
        entities = item.get("entities", [])
        assets = [e for e in entities if e["kind"] == "asset"]
        if not assets:
            continue
        context = {
            kind: [e["name"] for e in entities if e["kind"] == kind]
            for kind in ("target", "indication", "modality")
        }
        for asset in assets:
            row = programmes.setdefault(
                asset["id"],
                {
                    "id": asset["id"], "name": asset["name"],
                    "modality": "", "evidence": 0,
                    "targets": [], "indications": [],
                },
            )
            row["evidence"] += 1
            for name in context["target"]:
                if name not in row["targets"]:
                    row["targets"].append(name)
            for name in context["indication"]:
                if name not in row["indications"]:
                    row["indications"].append(name)
            if not row["modality"] and context["modality"]:
                row["modality"] = context["modality"][0]

    programmes = sorted(programmes.values(), key=lambda p: (-p["evidence"], p["name"]))
    for row in programmes:
        row["targets"] = row["targets"][:3]
        row["indications"] = row["indications"][:3]

    from .edition import _compact

    return {
        "company": _card(company),
        "range": range.upper(),
        "series": series,
        "programmes": programmes,
        "items": [_compact(i) for i in items[:30]],
        "setbacks": [_compact(i) for i in items if i["classification"]["isSetback"]][:10],
        "trials": [
            {
                "id": t["id"], "nctId": t.get("nct_id"), "title": t["title"],
                "status": t["status"], "phase": t["phase"], "conditions": t.get("conditions"),
                "enrollment": t.get("enrollment"), "whyStopped": t.get("why_stopped"),
                "isSetback": t.get("isSetback"), "url": t.get("url"),
            }
            for t in trials
        ],
        "excelra": _excelra_rollup(items),
    }


def _excelra_rollup(items: list[dict]) -> list[dict]:
    """Which Excelra capabilities this company's news flow keeps pointing at."""
    tally: dict[str, dict] = {}
    for item in items:
        for match in item["excelra"]["matches"]:
            row = tally.setdefault(
                match["assetId"],
                {"assetId": match["assetId"], "name": match["name"], "hits": 0,
                 "strength": 0.0, "contribution": match["contribution"], "value": match["value"]},
            )
            row["hits"] += 1
            row["strength"] += match["strength"]
    out = list(tally.values())
    for row in out:
        row["strength"] = round(row["strength"] / max(1, row["hits"]), 3)
    out.sort(key=lambda r: (-r["hits"], -r["strength"]))
    return out


@router.get("/markets")
def markets(sort: str = "momentum") -> dict:
    """The Apple-Stocks style board over the Intelligence Momentum Index."""
    store = pipeline.store()
    watch = {w["entity_id"] for w in db.get_watchlist()}
    rows = [{**_card(c), "onWatchlist": c["id"] in watch} for c in store.companies.values()]

    if sort == "momentum":
        rows.sort(key=lambda c: -c["windows"]["1M"]["changePct"])
    elif sort == "decliners":
        rows.sort(key=lambda c: c["windows"]["1M"]["changePct"])
    elif sort == "volatility":
        rows.sort(key=lambda c: -c["volatility"])
    else:
        rows.sort(key=lambda c: c["name"])

    gainers = sorted(rows, key=lambda c: -c["windows"]["1M"]["changePct"])[:3]
    losers = sorted(rows, key=lambda c: c["windows"]["1M"]["changePct"])[:3]
    avg = sum(c["windows"]["1M"]["changePct"] for c in rows) / len(rows) if rows else 0.0

    return {
        "asOf": store.built_at,
        "basis": "Intelligence Momentum Index — computed from observed event flow, not a market price.",
        "companies": rows,
        "gainers": gainers,
        "losers": losers,
        "breadth": {
            "advancing": sum(1 for c in rows if c["windows"]["1M"]["changePct"] > 0),
            "declining": sum(1 for c in rows if c["windows"]["1M"]["changePct"] < 0),
            "average1M": round(avg, 2),
        },
    }


@router.get("/watchlist")
def get_watchlist() -> dict:
    store = pipeline.store()
    rows = db.get_watchlist()
    return {
        "watchlist": [
            {
                **row,
                "card": _card(store.companies[row["entity_id"]])
                if row["entity_id"] in store.companies else None,
            }
            for row in rows
        ],
        "available": [
            {"id": c["id"], "name": c["name"], "sector": c["sector"], "ticker": c["ticker"]}
            for c in sorted(store.companies.values(), key=lambda c: c["name"])
        ],
    }


@router.post("/watchlist")
def add_watch(payload: WatchRequest) -> dict:
    store = pipeline.store()
    entity = pipeline.gazetteer().entities.get(payload.entityId)
    name = entity.name if entity else store.companies.get(payload.entityId, {}).get("name")
    if not name:
        raise HTTPException(status_code=404, detail="unknown entity")
    db.add_watch(payload.entityId, name, payload.focus, iso(now_utc()))
    pipeline.rebuild()
    return {"ok": True, "watchlist": db.get_watchlist()}


@router.delete("/watchlist/{entity_id}")
def delete_watch(entity_id: str) -> dict:
    db.remove_watch(entity_id)
    pipeline.rebuild()
    return {"ok": True, "watchlist": db.get_watchlist()}
