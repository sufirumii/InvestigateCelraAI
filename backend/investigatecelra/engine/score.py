"""Signal scoring — the editorial brain of the newspaper.

The score decides what runs on the front page. It is a weighted sum of six
components, each between 0 and 1, and the breakdown travels with the story so
an analyst can challenge any placement.

    signal = 100 * Σ (wᵢ · componentᵢ)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .lexicons import SOURCE_TIERS

WEIGHTS = {
    "recency": 0.24,
    "authority": 0.16,
    "event": 0.22,
    "impact": 0.16,
    "corroboration": 0.12,
    "portfolio": 0.10,
}

COMPONENT_LABELS = {
    "recency": "Recency",
    "authority": "Source authority",
    "event": "Event class",
    "impact": "Clinical impact",
    "corroboration": "Corroboration",
    "portfolio": "Portfolio fit",
}


@dataclass
class SignalScore:
    value: float
    components: dict[str, float]

    def as_dict(self) -> dict:
        return {
            "value": round(self.value, 1),
            "components": {
                k: {
                    "label": COMPONENT_LABELS[k],
                    "raw": round(v, 3),
                    "weight": WEIGHTS[k],
                    "contribution": round(v * WEIGHTS[k] * 100, 1),
                }
                for k, v in self.components.items()
            },
        }


def recency_component(age_days: float, half_life: float) -> float:
    """Exponential decay with a true half-life.

    At `age_days == half_life` this returns exactly 0.5, which is what the
    setting name promises. (An earlier version divided by the half-life
    without the ln 2 factor, so a story aged one "half-life" scored 0.368.)
    """
    return 0.5 ** (max(0.0, age_days) / max(0.5, half_life))


def authority_component(tier: str) -> float:
    return SOURCE_TIERS.get(tier, SOURCE_TIERS["unknown"])


def impact_component(phase_weight: float, entity_kinds: dict[str, int]) -> float:
    """Late-stage assets and named targets/indications carry more commercial weight."""
    breadth = min(1.0, (entity_kinds.get("target", 0) + entity_kinds.get("indication", 0)) / 3.0)
    modality = 0.15 if entity_kinds.get("modality") else 0.0
    return min(1.0, 0.60 * phase_weight + 0.25 * breadth + modality)


def corroboration_component(distinct_sources: int) -> float:
    """Diminishing returns: 1 source 0.35, 2 → 0.60, 3 → 0.75, 5+ → ~0.95."""
    if distinct_sources <= 0:
        return 0.0
    return min(1.0, 0.35 + 0.30 * math.log(distinct_sources, 2))


def portfolio_component(
    on_watchlist: bool,
    relevance_strength: float,
    preference_fit: float = 0.0,
) -> float:
    """How much this story belongs to *this* analyst's remit.

    Three inputs, all optional: an explicit watchlist company, the strength of
    the Excelra capability match, and how well the story fits the therapy
    areas and event priorities the analyst chose at sign-in. The last is the
    only part of the score that differs between two people looking at the same
    corpus, and it is bounded like everything else so it can shift ranking
    without ever dominating it.
    """
    return min(
        1.0,
        (0.45 if on_watchlist else 0.0)
        + 0.30 * relevance_strength
        + 0.35 * max(0.0, min(1.0, preference_fit)),
    )


def compute(
    *,
    age_days: float,
    half_life: float,
    tier: str,
    event_weight: float,
    classification_confidence: float,
    phase_weight: float,
    entity_kinds: dict[str, int],
    distinct_sources: int,
    on_watchlist: bool,
    relevance_strength: float,
    preference_fit: float = 0.0,
) -> SignalScore:
    components = {
        "recency": recency_component(age_days, half_life),
        "authority": authority_component(tier),
        "event": min(1.0, event_weight * (0.55 + 0.45 * classification_confidence)),
        "impact": impact_component(phase_weight, entity_kinds),
        "corroboration": corroboration_component(distinct_sources),
        "portfolio": portfolio_component(on_watchlist, relevance_strength, preference_fit),
    }
    value = 100.0 * sum(components[k] * WEIGHTS[k] for k in WEIGHTS)
    return SignalScore(value=value, components=components)


def band(value: float) -> str:
    if value >= 72:
        return "critical"
    if value >= 58:
        return "high"
    if value >= 42:
        return "moderate"
    return "routine"
