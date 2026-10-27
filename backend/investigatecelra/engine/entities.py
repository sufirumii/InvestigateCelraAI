"""Dictionary-based entity recognition.

Instead of a named-entity model we compile the gazetteer into a trie and run a
longest-match scan. This is O(n) in the length of the text, exact, and every
match can be traced back to a specific line in gazetteer.json.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..config import DATA_DIR
from .normalize import tokens

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-'&/\.]*")
MAX_PHRASE_TOKENS = 6


@dataclass
class Entity:
    id: str
    name: str
    kind: str
    subtype: str
    aliases: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "subtype": self.subtype}


@dataclass
class Mention:
    entity: Entity
    surface: str
    count: int
    in_title: bool

    def as_dict(self) -> dict:
        d = self.entity.as_dict()
        d.update({"surface": self.surface, "count": self.count, "inTitle": self.in_title})
        return d


def _norm_key(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^a-z0-9\-'&/\. ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_ACRONYM_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-/\.]{0,5}$")


def _is_acronym(surface: str) -> bool:
    """Short all-caps tokens (MET, RET, AI, HR) collide with ordinary English.

    They are only accepted when the source text also capitalises them.
    """
    return bool(_ACRONYM_RE.match(surface.strip()))


class Gazetteer:
    """Compiled phrase index. Built once, reused for every document."""

    def __init__(self, entities: list[Entity]):
        self.entities: dict[str, Entity] = {e.id: e for e in entities}
        self.phrases: dict[str, str] = {}
        self.strict: dict[str, str] = {}
        for e in entities:
            for surface in [e.name, *e.aliases]:
                key = _norm_key(surface)
                if len(key) < 2:
                    continue
                if _is_acronym(surface):
                    self.strict.setdefault(surface.strip(), e.id)
                    continue
                # Longer/earlier definitions win; do not let a short alias of one
                # entity shadow the full name of another.
                if key not in self.phrases or len(surface) > len(self.phrases[key]):
                    self.phrases[key] = e.id
        lens = [len(k.split()) for k in self.phrases] or [1]
        self.max_len = min(max(lens), MAX_PHRASE_TOKENS)

    @classmethod
    def load(cls, path: Path | None = None) -> "Gazetteer":
        path = path or (DATA_DIR / "gazetteer.json")
        raw = json.loads(path.read_text(encoding="utf-8"))
        ents = [
            Entity(
                id=e["id"], name=e["name"], kind=e["kind"],
                subtype=e.get("subtype", ""), aliases=e.get("aliases", []),
                meta=e.get("meta", {}),
            )
            for e in raw["entities"]
        ]
        return cls(ents)

    @lru_cache(maxsize=1)
    def cased_tokens(self) -> frozenset[str]:
        """Every individually-cased word appearing in a known name.

        Used by the title normaliser so that a recognised proper noun is never
        reshaped by its capitalisation heuristics.
        """
        out: set[str] = set()
        for e in self.entities.values():
            for surface in [e.name, *e.aliases]:
                for token in surface.replace("/", " ").split():
                    token = token.strip("(),.")
                    if token:
                        out.add(token)
        return frozenset(out)

    def add(self, entity: Entity) -> None:
        """Register an entity discovered at runtime (e.g. a new trial sponsor)."""
        if entity.id in self.entities:
            return
        self.entities[entity.id] = entity
        for surface in [entity.name, *entity.aliases]:
            if _is_acronym(surface):
                self.strict.setdefault(surface.strip(), entity.id)
                continue
            key = _norm_key(surface)
            if len(key) >= 2:
                self.phrases.setdefault(key, entity.id)
        self.max_len = min(max(self.max_len, len(_norm_key(entity.name).split())), MAX_PHRASE_TOKENS)

    # -- matching ---------------------------------------------------------
    def scan(self, text: str) -> list[tuple[str, str]]:
        """Return (entity_id, surface) for every longest match in `text`."""
        if not text:
            return []
        words = [(m.group(0), m.start(), m.end()) for m in _WORD_RE.finditer(text)]
        out: list[tuple[str, str]] = []
        i = 0
        n = len(words)
        while i < n:
            matched = False
            upper = min(self.max_len, n - i)
            for span in range(upper, 0, -1):
                chunk = text[words[i][1]:words[i + span - 1][2]]
                eid = self.strict.get(chunk.strip()) or self.phrases.get(_norm_key(chunk))
                if eid:
                    out.append((eid, chunk))
                    i += span
                    matched = True
                    break
            if not matched:
                i += 1
        return out

    def extract(self, title: str, body: str) -> list[Mention]:
        """Aggregate mentions across a document, title-weighted."""
        counts: dict[str, int] = {}
        surfaces: dict[str, str] = {}
        in_title: set[str] = set()

        for eid, surface in self.scan(title or ""):
            counts[eid] = counts.get(eid, 0) + 1
            surfaces.setdefault(eid, surface)
            in_title.add(eid)
        for eid, surface in self.scan(body or ""):
            counts[eid] = counts.get(eid, 0) + 1
            surfaces.setdefault(eid, surface)

        mentions = [
            Mention(
                entity=self.entities[eid],
                surface=surfaces.get(eid, self.entities[eid].name),
                count=c,
                in_title=eid in in_title,
            )
            for eid, c in counts.items()
            if eid in self.entities
        ]
        mentions.sort(key=lambda m: (m.in_title, m.count, len(m.entity.name)), reverse=True)
        return mentions


@lru_cache(maxsize=1)
def default_gazetteer() -> Gazetteer:
    return Gazetteer.load()


def primary_company(mentions: list[Mention]) -> Entity | None:
    """The company a story is 'about': title mention first, then frequency."""
    companies = [m for m in mentions if m.entity.kind == "company" and m.entity.subtype != "internal"]
    if not companies:
        return None
    companies.sort(key=lambda m: (m.in_title, m.count), reverse=True)
    return companies[0].entity


def keywords(text: str, corpus_df: dict[str, int], corpus_size: int, limit: int = 8) -> list[str]:
    """TF-IDF keyword extraction — arithmetic only, no vectors stored."""
    from math import log

    from .lexicons import STOPWORDS

    tf: dict[str, int] = {}
    for tok in tokens(text):
        if tok in STOPWORDS or len(tok) < 4 or tok.isdigit():
            continue
        tf[tok] = tf.get(tok, 0) + 1
    if not tf:
        return []
    scored = []
    for term, freq in tf.items():
        df = corpus_df.get(term, 0) + 1
        idf = log((corpus_size + 1) / df)
        scored.append((freq * idf, term))
    scored.sort(reverse=True)
    return [t for _, t in scored[:limit]]
