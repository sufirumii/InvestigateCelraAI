"""RSS / Atom reader.

Handles both syndication dialects with one ElementTree pass. No feedparser
dependency, no network beyond a single GET per feed.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ..config import settings
from ..engine.normalize import clean_text, fingerprint, host_of, iso, now_utc, parse_date, simhash
from .base import FetchError, IngestResult, http_get

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return clean_text("".join(node.itertext()))


def _first(entry: ET.Element, paths: list[str]) -> ET.Element | None:
    for p in paths:
        found = entry.find(p, NS)
        if found is not None:
            return found
    return None


def _link(entry: ET.Element) -> str:
    node = entry.find("link")
    if node is not None and (node.text or "").strip():
        return node.text.strip()
    for alt in entry.findall("atom:link", NS):
        if alt.get("rel", "alternate") == "alternate" and alt.get("href"):
            return alt.get("href", "")
    node = entry.find("guid")
    if node is not None and (node.text or "").startswith("http"):
        return node.text.strip()
    return ""


def parse_feed(xml_bytes: bytes, source: dict) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    entries = root.findall(".//item") or root.findall(".//atom:entry", NS)
    fetched = iso(now_utc())
    out: list[dict] = []

    for entry in entries[: settings.max_items_per_source]:
        title = _text(_first(entry, ["title", "atom:title"]))
        if not title:
            continue
        body = _text(
            _first(entry, ["content:encoded", "description", "atom:content", "atom:summary", "summary"])
        )
        url = _link(entry)
        published = parse_date(
            _text(_first(entry, ["pubDate", "atom:published", "atom:updated", "dc:date", "updated"]))
        ) or now_utc()

        out.append(
            {
                "id": fingerprint(source["id"], url or title),
                "source_id": source["id"],
                "source_name": source["name"],
                "tier": source.get("tier", "trade"),
                "kind": "news",
                "title": title,
                "body": body or title,
                "url": url,
                "host": host_of(url) or source["id"],
                "published_at": iso(published),
                "fetched_at": fetched,
                "simhash": str(simhash(f"{title} {body}")),
                "extra": {},
            }
        )
    return out


def fetch(source: dict) -> IngestResult:
    result = IngestResult()
    try:
        raw = http_get(source["url"], accept="application/rss+xml, application/xml, text/xml")
        docs = parse_feed(raw, source)
        result.documents.extend(docs)
        result.fetched = len(docs)
    except (FetchError, ET.ParseError) as exc:
        result.errors.append(f"{source['id']}: {exc}")
    return result


def fetch_all(sources: list[dict]) -> IngestResult:
    combined = IngestResult()
    for source in sources:
        combined.merge(fetch(source))
    return combined
