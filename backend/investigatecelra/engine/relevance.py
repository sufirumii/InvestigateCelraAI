"""Excelra relevance engine.

Answers "why does this matter to us?" with a rule table rather than a
generated opinion. Each asset in excelra_assets.json declares trigger
conditions; a story matches when its event type, entity kinds, modality or
vocabulary hit those triggers. The matched conditions are returned so the
justification is inspectable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from ..config import DATA_DIR


@dataclass
class AssetMatch:
    asset_id: str
    name: str
    strength: float
    reasons: list[str]
    contribution: str
    value: str

    def as_dict(self) -> dict:
        return {
            "assetId": self.asset_id,
            "name": self.name,
            "strength": round(self.strength, 3),
            "reasons": self.reasons,
            "contribution": self.contribution,
            "value": self.value,
        }


@lru_cache(maxsize=1)
def load_assets() -> list[dict]:
    raw = json.loads((DATA_DIR / "excelra_assets.json").read_text(encoding="utf-8"))
    return raw["assets"]


def assess(
    *,
    event_type: str,
    entity_kinds: set[str],
    modalities: set[str],
    text: str,
) -> tuple[list[AssetMatch], float]:
    """Return matched Excelra assets and an overall relevance strength (0-1)."""
    lowered = text.lower()
    matches: list[AssetMatch] = []

    for asset in load_assets():
        trig = asset["triggers"]
        score = 0.0
        reasons: list[str] = []

        if event_type in trig.get("event_types", []):
            score += 0.40
            reasons.append(f"event type matches ({event_type.replace('_', ' ')})")

        overlap_kinds = entity_kinds & set(trig.get("entity_kinds", []))
        if overlap_kinds:
            score += 0.20
            reasons.append("entities present: " + ", ".join(sorted(overlap_kinds)))

        overlap_mod = {m.lower() for m in modalities} & {m.lower() for m in trig.get("modalities", [])}
        if overlap_mod:
            score += 0.20
            reasons.append("modality match: " + ", ".join(sorted(overlap_mod)))

        hits = [k for k in trig.get("keywords", []) if k in lowered]
        if hits:
            score += min(0.30, 0.10 * len(hits))
            reasons.append("vocabulary: " + ", ".join(hits[:4]))

        if score >= 0.35:
            matches.append(
                AssetMatch(
                    asset_id=asset["id"],
                    name=asset["name"],
                    strength=min(1.0, score),
                    reasons=reasons,
                    contribution=asset["contribution"],
                    value=asset["value"],
                )
            )

    matches.sort(key=lambda m: -m.strength)
    matches = matches[:3]
    overall = min(1.0, sum(m.strength for m in matches) / 2.0) if matches else 0.0
    return matches, overall


def asset_catalogue() -> list[dict]:
    return [
        {
            "id": a["id"],
            "name": a["name"],
            "fullName": a["full_name"],
            "summary": a["summary"],
            "supports": a["supports"],
        }
        for a in load_assets()
    ]
