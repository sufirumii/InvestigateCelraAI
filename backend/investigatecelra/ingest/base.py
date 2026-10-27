"""Shared ingestion helpers.

urllib from the standard library is enough: every source is an unauthenticated
GET returning XML, JSON or CSV. Fewer dependencies means fewer things that can
break a deployment.
"""

from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from ..config import DATA_DIR, settings


class FetchError(RuntimeError):
    pass


@dataclass
class IngestResult:
    documents: list[dict] = field(default_factory=list)
    trials: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    fetched: int = 0

    def merge(self, other: "IngestResult") -> None:
        self.documents.extend(other.documents)
        self.trials.extend(other.trials)
        self.errors.extend(other.errors)
        self.fetched += other.fetched


def http_get(url: str, *, params: dict | None = None, accept: str = "*/*") -> bytes:
    if not settings.allow_network:
        raise FetchError("network access disabled (ALLOW_NETWORK=0)")
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": settings.http_user_agent,
            "Accept": accept,
            "Accept-Encoding": "gzip",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.http_timeout) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return raw
    except urllib.error.HTTPError as exc:  # pragma: no cover - network dependent
        raise FetchError(f"HTTP {exc.code} for {url}") from exc
    except Exception as exc:  # pragma: no cover - network dependent
        raise FetchError(f"{type(exc).__name__}: {exc} for {url}") from exc


def http_json(url: str, *, params: dict | None = None) -> dict:
    return json.loads(http_get(url, params=params, accept="application/json").decode("utf-8", "replace"))


def load_sources() -> dict:
    return json.loads((DATA_DIR / "sources.json").read_text(encoding="utf-8"))


def source_registry() -> list[dict]:
    cfg = load_sources()
    return [*cfg.get("feeds", []), *cfg.get("apis", [])]


