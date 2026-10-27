"""Analyst preferences and the fit score derived from them.

Captured once at sign-in and stored in the `meta` table. Nothing here is a
filter: a preference shifts a story's portfolio component, so the analyst sees
their remit first without the rest of the sector disappearing. Everything the
preferences refer to — sector names, event classes, company ids — is drawn
from the live corpus and the gazetteer, never from a fixed list in this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Weight given to each signal of fit. They sum to 1.0 so `fit` is bounded.
SECTOR_WEIGHT = 0.40
EVENT_WEIGHT = 0.35
COMPANY_WEIGHT = 0.25


@dataclass
class Preferences:
    analyst: str = ""
    role: str = ""
    sectors: list[str] = field(default_factory=list)
    event_types: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    configured: bool = False

    @classmethod
    def from_dict(cls, raw: dict | None) -> "Preferences":
        raw = raw or {}
        return cls(
            analyst=str(raw.get("analyst", ""))[:80].strip(),
            role=str(raw.get("role", ""))[:80].strip(),
            sectors=[str(x) for x in raw.get("sectors", [])][:12],
            event_types=[str(x) for x in raw.get("eventTypes", [])][:16],
            companies=[str(x) for x in raw.get("companies", [])][:40],
            configured=bool(raw.get("configured", False)),
        )

    def as_dict(self) -> dict:
        return {
            "analyst": self.analyst,
            "role": self.role,
            "sectors": self.sectors,
            "eventTypes": self.event_types,
            "companies": self.companies,
            "configured": self.configured,
        }

    def fit(self, *, sector: str, event_type: str, company_id: str | None) -> float:
        """0.0–1.0. Neutral (0.5) when the analyst expressed no preference.

        A neutral default matters: an unconfigured desk must rank exactly as it
        did before this feature existed, so the baseline ordering is unchanged
        and any movement is attributable to a stated choice.
        """
        if not self.configured:
            return 0.5

        parts: list[tuple[float, float]] = []
        if self.sectors:
            parts.append((SECTOR_WEIGHT, 1.0 if sector in self.sectors else 0.0))
        if self.event_types:
            parts.append((EVENT_WEIGHT, 1.0 if event_type in self.event_types else 0.0))
        if self.companies:
            parts.append((COMPANY_WEIGHT, 1.0 if company_id in self.companies else 0.0))

        if not parts:
            return 0.5
        total = sum(w for w, _ in parts)
        return sum(w * v for w, v in parts) / total

    def describe(self) -> list[str]:
        """Human-readable statements, used by the configuration screen."""
        lines: list[str] = []
        if self.sectors:
            lines.append(f"Prioritising {len(self.sectors)} therapy areas: {', '.join(self.sectors)}")
        else:
            lines.append("Covering every therapy area in the corpus")
        if self.event_types:
            lines.append(f"Weighting {len(self.event_types)} event classes toward the top of the edition")
        else:
            lines.append("Weighting all event classes equally")
        if self.companies:
            lines.append(f"Tracking {len(self.companies)} companies on the watchlist")
        else:
            lines.append("Tracking the full core coverage set")
        return lines
