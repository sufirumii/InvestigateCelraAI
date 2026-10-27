"""The analysis pipeline.

Raw document → normalise → deduplicate → recognise entities → classify event →
extract limitations and figures → assess Excelra relevance → score → cluster →
cluster → index. Every stage is deterministic; running it twice over the same
corpus produces byte-identical output.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from . import db
from .config import settings
from .engine import classify as clf
from .engine import index as idx
from .engine import relevance, score, summarize
from .engine.entities import Gazetteer, Mention, default_gazetteer, keywords, primary_company
from .engine.preferences import Preferences
from .engine.normalize import (
    age_days,
    hamming,
    iso,
    key_figures,
    normalize_title,
    now_utc,
    parse_date,
)
from .ingest import clinicaltrials, pubmed, rss
from .ingest.base import IngestResult, source_registry

log = logging.getLogger("investigatecelra.pipeline")

NEAR_DUPLICATE_BITS = 7
CLUSTER_WINDOW_DAYS = 6
SPONSOR_QUERY_LIMIT = 24   # registry queries per refresh
PUBMED_QUERY_LIMIT = 8     # literature queries per refresh

SECTOR_RULES: list[tuple[str, set[str]]] = [
    ("Oncology", {"cancer", "tumour", "tumor", "oncology", "carcinoma", "lymphoma", "myeloma", "leukaemia", "leukemia", "metastatic", "melanoma"}),
    ("Cardiometabolic", {"obesity", "diabetes", "cardiovascular", "kidney", "renal", "mash", "nash", "cholesterol", "heart", "metabolic", "weight"}),
    ("Immunology", {"colitis", "crohn", "arthritis", "psoriasis", "dermatitis", "lupus", "immunology", "inflammatory", "autoimmune"}),
    ("Neuroscience", {"alzheimer", "parkinson", "neurology", "neuro", "cognitive", "tau", "amyloid", "epilepsy", "depression", "sclerosis"}),
    ("Respiratory", {"copd", "asthma", "pulmonary", "respiratory", "fibrosis", "bronchiectasis", "lung function"}),
    ("Rare Disease", {"rare disease", "orphan", "duchenne", "muscular dystrophy", "haemophilia", "hemophilia", "cystic fibrosis", "spinal muscular"}),
    ("Platform & Data", {"knowledge graph", "multiomics", "multi-omics", "data", "artificial intelligence", "machine learning", "platform", "genomics", "proteomics", "diagnostic", "biomarker panel"}),
]


@dataclass
class Store:
    """Everything the API serves, rebuilt in one pass."""

    items: list[dict] = field(default_factory=list)
    by_id: dict[str, dict] = field(default_factory=dict)
    trials: list[dict] = field(default_factory=list)
    companies: dict[str, dict] = field(default_factory=dict)
    sectors: list[str] = field(default_factory=list)
    built_at: str = ""
    mode: str = "live"
    ready: bool = False
    preferences: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)


_STORE = Store()
_STORE_LOCK = threading.RLock()
_GAZETTEER: Gazetteer | None = None


def gazetteer() -> Gazetteer:
    global _GAZETTEER
    if _GAZETTEER is None:
        _GAZETTEER = default_gazetteer()
    return _GAZETTEER


def store() -> Store:
    return _STORE


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------
def detect_sector(text: str, mentions: list[Mention], hint: str = "") -> str:
    if hint:
        pretty = {
            "oncology": "Oncology", "cardiometabolic": "Cardiometabolic",
            "immunology": "Immunology", "neuroscience": "Neuroscience",
            "rare": "Rare Disease", "respiratory": "Respiratory",
            "platform": "Platform & Data",
        }
        if hint in pretty:
            return pretty[hint]
    lowered = text.lower()
    best, best_hits = "General", 0
    for label, terms in SECTOR_RULES:
        hits = sum(1 for t in terms if t in lowered)
        if hits > best_hits:
            best, best_hits = label, hits
    if best_hits == 0:
        for m in mentions:
            if m.entity.kind == "indication" and m.entity.subtype:
                return {
                    "oncology": "Oncology", "cardiometabolic": "Cardiometabolic",
                    "immunology": "Immunology", "neuroscience": "Neuroscience",
                    "rare": "Rare Disease", "respiratory": "Respiratory",
                    "ophthalmology": "Ophthalmology",
                }.get(m.entity.subtype, "General")
    return best


def deduplicate(docs: list[dict]) -> tuple[list[dict], dict[str, list[str]]]:
    """SimHash near-duplicate collapse. Survivors keep a list of echoing sources."""
    kept: list[dict] = []
    hashes: list[tuple[int, dict]] = []
    echoes: dict[str, list[str]] = defaultdict(list)

    for doc in sorted(docs, key=lambda d: (d.get("tier") != "registry", d.get("published_at", "")), reverse=False):
        try:
            h = int(doc.get("simhash") or 0)
        except ValueError:
            h = 0
        duplicate_of = None
        if h:
            for other_h, other in hashes:
                if hamming(h, other_h) <= NEAR_DUPLICATE_BITS:
                    duplicate_of = other
                    break
        if duplicate_of is not None:
            echoes[duplicate_of["id"]].append(doc.get("source_name", ""))
            continue
        hashes.append((h, doc))
        kept.append(doc)
    return kept, echoes


def analyse_document(
    doc: dict,
    *,
    corpus_df: dict[str, int],
    corpus_size: int,
    watch_ids: set[str],
    prefs: Preferences,
    echoes: dict[str, list[str]],
    reference: datetime,
) -> dict:
    g = gazetteer()
    # Registries publish backronym titles ("cancEr iNduced by DenOsUmab").
    # Repair the casing for display; classification below is case-insensitive
    # anyway, and no word is altered — only its case.
    title = normalize_title(doc["title"], keep=g.cased_tokens())
    body = doc.get("body") or ""
    full = f"{title}. {body}"

    mentions = g.extract(title, body)
    classification = clf.classify(title, body)
    entity_kinds: dict[str, int] = defaultdict(int)
    for m in mentions:
        entity_kinds[m.entity.kind] += 1
    modalities = {m.entity.name for m in mentions if m.entity.kind == "modality"}
    modalities |= {m.entity.subtype for m in mentions if m.entity.kind == "asset" and m.entity.subtype}

    matches, relevance_strength = relevance.assess(
        event_type=classification.event_type,
        entity_kinds=set(entity_kinds),
        modalities=modalities,
        text=full,
    )

    company = primary_company(mentions)
    on_watchlist = bool(company and company.id in watch_ids)
    extra = doc.get("extra")
    if not isinstance(extra, dict):
        # A malformed `extra` blob must not take the whole rebuild down with it.
        extra = {}
    sector = detect_sector(full, mentions, extra.get("sector", ""))
    published = parse_date(doc.get("published_at")) or reference
    echo_sources = echoes.get(doc["id"], [])
    distinct_sources = 1 + len({e for e in echo_sources if e})

    signal = score.compute(
        age_days=age_days(published, reference),
        half_life=settings.recency_half_life_days,
        tier=doc.get("tier", "unknown"),
        event_weight=clf.event_meta(classification.event_type)["weight"],
        classification_confidence=classification.confidence,
        phase_weight=classification.phase_weight,
        entity_kinds=dict(entity_kinds),
        distinct_sources=distinct_sources,
        on_watchlist=on_watchlist,
        preference_fit=prefs.fit(
            sector=sector,
            event_type=classification.event_type,
            company_id=company.id if company else None,
        ),
        relevance_strength=relevance_strength,
    )

    boost = {m.entity.name.lower() for m in mentions[:6]}

    return {
        "id": doc["id"],
        "title": title,
        "url": doc.get("url", ""),
        "source": {
            "id": doc.get("source_id", ""),
            "name": doc.get("source_name", ""),
            "tier": doc.get("tier", "unknown"),
            "host": doc.get("host", ""),
        },
        "kind": doc.get("kind", "news"),
        "publishedAt": iso(published),
        "ageDays": round(age_days(published, reference), 2),
        "sector": sector,
        "summary": summarize.summarise(body or title, max_sentences=3, boost_terms=boost),
        "lede": summarize.headline_digest(body or title, boost_terms=boost),
        "keywords": keywords(full, corpus_df, corpus_size, limit=7),
        "figures": key_figures(full),
        "entities": [m.as_dict() for m in mentions[:14]],
        "primaryCompany": company.as_dict() if company else None,
        "classification": classification.as_dict(),
        "limitations": clf.extract_limitations(body or title),
        "excelra": {
            "strength": round(relevance_strength, 3),
            "matches": [m.as_dict() for m in matches],
        },
        "signal": signal.as_dict(),
        "band": score.band(signal.value),
        "corroboration": {"distinctSources": distinct_sources, "echoes": echo_sources[:6]},
        "onWatchlist": on_watchlist,
    }


def cluster(items: list[dict]) -> list[dict]:
    """Group stories that describe the same development."""
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in items:
        company = (item.get("primaryCompany") or {}).get("id", "unassigned")
        buckets[(company, item["classification"]["eventType"])].append(item)

    for group in buckets.values():
        group.sort(key=lambda i: i["publishedAt"], reverse=True)
        chain: list[dict] = []
        for item in group:
            dt = parse_date(item["publishedAt"])
            if chain:
                head = parse_date(chain[0]["publishedAt"])
                if head and dt and abs((head - dt).days) > CLUSTER_WINDOW_DAYS:
                    _seal(chain)
                    chain = []
            chain.append(item)
        _seal(chain)
    return items


def _seal(chain: list[dict]) -> None:
    if len(chain) < 2:
        if chain:
            chain[0]["related"] = []
        return
    lead = max(chain, key=lambda i: i["signal"]["value"])
    for item in chain:
        item["related"] = [
            {"id": o["id"], "title": o["title"], "source": o["source"]["name"]}
            for o in chain if o["id"] != item["id"]
        ][:4]
        item["isLead"] = item is lead


def link_trials(trials: list[dict]) -> list[dict]:
    g = gazetteer()
    out = []
    for trial in trials:
        text = " ".join(
            str(trial.get(k) or "") for k in ("title", "conditions", "interventions", "why_stopped")
        )
        mentions = g.extract(trial.get("title", ""), text)
        sponsor_id = None
        for eid, _surface in g.scan(trial.get("sponsor", "")):
            if g.entities[eid].kind == "company":
                sponsor_id = eid
                break
        linked = [
            (m.entity.id, m.entity.name, m.entity.kind)
            for m in mentions
            if m.entity.kind in {"indication", "target", "modality", "asset"}
        ][:6]
        record = dict(trial)
        record["sponsorEntityId"] = sponsor_id
        record["linkedEntities"] = linked
        record["isSetback"] = (trial.get("status", "").lower() in {"terminated", "suspended", "withdrawn"})
        out.append(record)
    return out


def build_companies(items: list[dict], trials: list[dict]) -> dict[str, dict]:
    meta = gazetteer_metadata()
    by_company: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        pc = item.get("primaryCompany")
        if pc:
            by_company[pc["id"]].append(item)

    trials_by_company: dict[str, list[dict]] = defaultdict(list)
    for trial in trials:
        if trial.get("sponsorEntityId"):
            trials_by_company[trial["sponsorEntityId"]].append(trial)

    out: dict[str, dict] = {}
    for cid, citems in by_company.items():
        citems.sort(key=lambda i: i["publishedAt"], reverse=True)
        series = idx.series_for(citems, days=365)
        summary = idx.summarise_series(series)
        setbacks = [i for i in citems if i["classification"]["isSetback"]]
        entity = gazetteer().entities.get(cid)
        info = meta.get(cid, {})
        sectors = defaultdict(int)
        for i in citems:
            sectors[i["sector"]] += 1
        out[cid] = {
            "id": cid,
            "name": entity.name if entity else cid,
            "subtype": entity.subtype if entity else "",
            "ticker": info.get("ticker", ""),
            "sector": max(sectors.items(), key=lambda kv: kv[1])[0] if sectors else "General",
            "itemCount": len(citems),
            "setbackCount": len(setbacks),
            "topSignal": round(max(i["signal"]["value"] for i in citems), 1),
            "lastActivity": citems[0]["publishedAt"],
            "index": summary,
            "sparkline": idx.sparkline(series),
            "series": series,
            "trialCount": len(trials_by_company.get(cid, [])),
            "activeTrials": sum(
                1 for t in trials_by_company.get(cid, [])
                if t.get("status", "").lower().startswith(("recruiting", "active", "enrolling"))
            ),
        }
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def rebuild() -> Store:
    """Re-run analysis over everything currently in the database."""
    docs = db.all_documents()
    raw_trials = db.all_trials()
    watch_ids = {w["entity_id"] for w in db.get_watchlist()}
    prefs = load_preferences()
    reference = now_utc()

    kept, echoes = deduplicate(docs)
    corpus_df, corpus_size = summarize.corpus_document_frequencies(
        [f"{d['title']} {d.get('body','')}" for d in kept]
    )

    items = [
        analyse_document(
            d, corpus_df=corpus_df, corpus_size=corpus_size,
            watch_ids=watch_ids, prefs=prefs, echoes=echoes, reference=reference,
        )
        for d in kept
    ]
    items = cluster(items)
    items.sort(key=lambda i: (-i["signal"]["value"], i["publishedAt"]))

    trials = link_trials(raw_trials)
    companies = build_companies(items, trials)
    sectors = sorted({i["sector"] for i in items})

    setbacks = sum(1 for i in items if i["classification"]["isSetback"])
    new_store = Store(
        items=items,
        by_id={i["id"]: i for i in items},
        trials=trials,
        companies=companies,
        sectors=sectors,
        built_at=iso(reference),
        mode=db.get_meta("data_mode", "live"),
        ready=bool(items),
        preferences=prefs.as_dict(),
        stats={
            "documents": len(docs),
            "analysed": len(items),
            "duplicatesCollapsed": len(docs) - len(kept),
            "setbacks": setbacks,
            "trials": len(trials),
            "companies": len(companies),
            "sources": len({i["source"]["name"] for i in items}),
        },
    )

    global _STORE
    with _STORE_LOCK:
        _STORE = new_store
    return new_store


def refresh(live: bool | None = None) -> dict:
    """Fetch from the public sources, persist, and re-analyse.

    There is no offline fallback. If the network is unavailable the run
    records the failure and the desk keeps whatever it fetched last time.
    Nothing is ever substituted or generated.
    """
    started = now_utc()
    if not settings.allow_network:
        raise RuntimeError(
            "ALLOW_NETWORK is off. InvestigateCelra has no bundled corpus; "
            "it cannot produce an edition without reaching its sources."
        )
    run_id = db.start_run(iso(started), "live")

    result = IngestResult()
    per_source: dict[str, int] = {}

    for feed in [s for s in source_registry() if s.get("type") == "rss"]:
        r = rss.fetch(feed)
        per_source[feed["id"]] = len(r.documents)
        result.merge(r)

    sponsors = tracked_sponsors()
    if sponsors:
        r = clinicaltrials.fetch_for_sponsors(sponsors)
        per_source["clinicaltrials"] = len(r.documents)
        result.merge(r)

    for term in sponsors[:PUBMED_QUERY_LIMIT]:
        pr = pubmed.fetch_query(f'"{term}"[Affiliation]')
        per_source["pubmed"] = per_source.get("pubmed", 0) + len(pr.documents)
        result.merge(pr)

    mode = "live"
    new, dupes = db.upsert_documents(result.documents)
    db.upsert_trials(result.trials)
    db.set_meta("data_mode", mode)
    db.set_meta("last_refresh", iso(now_utc()))

    rebuild()

    finished = now_utc()
    detail = {"perSource": per_source, "mode": mode}
    db.finish_run(run_id, iso(finished), result.fetched, new, dupes, result.errors[:12], detail)

    return {
        "mode": mode,
        "fetched": result.fetched,
        "new": new,
        "duplicates": dupes,
        "errors": result.errors[:12],
        "perSource": per_source,
        "durationMs": int((finished - started).total_seconds() * 1000),
        "stats": _STORE.stats,
    }


def tracked_sponsors() -> list[str]:
    """Sponsor names to query the trial registry and literature for.

    The watchlist wins if the analyst has set one; otherwise the desk covers
    the largest R&D spenders in the sector, read from the gazetteer. These are
    company names used as *search terms* — no facts about them are assumed.
    """
    watch = [w["name"] for w in db.get_watchlist()]
    if watch:
        return watch[:SPONSOR_QUERY_LIMIT]
    covered = [
        e.name for e in gazetteer().entities.values()
        if e.kind == "company" and e.meta.get("coverage") == "core"
    ]
    return sorted(covered)[:SPONSOR_QUERY_LIMIT]


def gazetteer_metadata() -> dict:
    """Ticker/sector reference for known companies, from the gazetteer file."""
    return {
        e.id: {k: v for k, v in e.meta.items() if k in {"ticker", "sector", "hq", "coverage"}}
        for e in gazetteer().entities.values()
        if e.kind == "company"
    }


def bootstrap() -> None:
    """Called once at application startup.

    Re-analyses whatever is already stored so the desk comes up instantly,
    then fetches in the background if the store is empty or stale.
    """
    db.init()
    rebuild()
    if db.document_count() == 0 and settings.allow_network:
        threading.Thread(target=_safe_refresh, name="first-fetch", daemon=True).start()


def _safe_refresh() -> None:
    try:
        refresh()
    except Exception as exc:  # noqa: BLE001 - startup must never crash the app
        log.warning("initial fetch failed: %s", exc)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------
PREFERENCES_KEY = "preferences"


def sector_vocabulary() -> list[str]:
    """Every therapy area the pipeline can assign, in taxonomy order.

    Used by the sign-in screen, which may run before the first fetch has
    finished. Offering the taxonomy is honest — these are the only labels
    `detect_sector` can ever produce — whereas offering nothing forces the
    analyst to configure the desk blind.
    """
    return [name for name, _ in SECTOR_RULES] + ["General"]


def load_preferences() -> Preferences:
    raw = db.get_meta(PREFERENCES_KEY)
    if not raw:
        return Preferences()
    try:
        return Preferences.from_dict(json.loads(raw))
    except (ValueError, TypeError):
        log.warning("stored preferences were unreadable; falling back to defaults")
        return Preferences()


def save_preferences(payload: dict) -> Preferences:
    """Persist the sign-in choices, mirror companies onto the watchlist, and
    re-rank the corpus so the next request reflects them."""
    prefs = Preferences.from_dict({**payload, "configured": True})
    db.set_meta(PREFERENCES_KEY, json.dumps(prefs.as_dict()))

    # The watchlist and the preferences are two views of the same intent, so
    # keep them in step rather than letting them drift apart.
    existing = {w["entity_id"] for w in db.get_watchlist()}
    wanted = set(prefs.companies)
    g = gazetteer()
    for entity_id in wanted - existing:
        entity = g.entities.get(entity_id)
        if entity:
            db.add_watch(entity.id, entity.name, entity.meta.get("sector", ""), iso(now_utc()))
    for entity_id in existing - wanted:
        db.remove_watch(entity_id)

    rebuild()
    return prefs
