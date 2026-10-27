"""PubMed connector (NCBI E-utilities).

Used sparingly: the desk needs the peer-reviewed layer under a company's
claims, not a literature dump. One esearch + one esummary per query.
"""

from __future__ import annotations

from ..engine.normalize import clean_text, fingerprint, iso, now_utc, parse_date, simhash
from .base import FetchError, IngestResult, http_json

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def fetch_query(term: str, retmax: int = 12, days: int = 120) -> IngestResult:
    result = IngestResult()
    try:
        search = http_json(
            f"{BASE}/esearch.fcgi",
            params={
                "db": "pubmed", "term": term, "retmode": "json",
                "retmax": retmax, "sort": "date", "reldate": days, "datetype": "pdat",
            },
        )
        ids = (search.get("esearchresult", {}) or {}).get("idlist", []) or []
        if not ids:
            return result
        summary = http_json(
            f"{BASE}/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
        )
    except FetchError as exc:
        result.errors.append(f"pubmed[{term}]: {exc}")
        return result

    payload = summary.get("result", {}) or {}
    for pmid in payload.get("uids", []) or []:
        rec = payload.get(pmid) or {}
        title = clean_text(rec.get("title", ""))
        if not title:
            continue
        journal = rec.get("fulljournalname") or rec.get("source") or "PubMed"
        authors = ", ".join(a.get("name", "") for a in (rec.get("authors") or [])[:4])
        body = f"{title} Published in {journal}. {('Authors: ' + authors + '.') if authors else ''}"
        published = parse_date(rec.get("pubdate")) or now_utc()
        result.documents.append(
            {
                "id": fingerprint("pubmed", pmid),
                "source_id": "pubmed",
                "source_name": f"PubMed — {journal}",
                "tier": "journal",
                "kind": "research",
                "title": title,
                "body": body,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "host": "pubmed.ncbi.nlm.nih.gov",
                "published_at": iso(published),
                "fetched_at": iso(now_utc()),
                "simhash": str(simhash(f"{title} {body}")),
                "extra": {"pmid": pmid, "journal": journal},
            }
        )
        result.fetched += 1
    return result
