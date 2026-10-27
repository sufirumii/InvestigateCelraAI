"""Rule-based event classification.

The classifier is a scored keyword/regex vote. Every decision returns the exact
rules that fired, so the UI can show *why* a story was labelled a trial failure
rather than asking the reader to trust a black box.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from .lexicons import (
    EVENT_TYPES,
    LIMITATION_CUES,
    PHASE_PATTERNS,
    PHASE_WEIGHTS,
    SETBACK_TYPES,
)
from .normalize import sentences

# Compile once.
_COMPILED: dict[str, list[tuple[re.Pattern[str], int]]] = {
    etype: [(re.compile(p, re.I), pts) for p, pts in cfg["patterns"]]
    for etype, cfg in EVENT_TYPES.items()
}
_PHASE_COMPILED = [(re.compile(p, re.I), label) for p, label in PHASE_PATTERNS]
_NEGATION = re.compile(
    r"\b(?:no|not|never|without|denies|denied|rules? out|ruled out)\b[^.,;]{0,32}$", re.I
)


@dataclass
class Classification:
    event_type: str
    label: str
    polarity: int
    confidence: float
    is_setback: bool
    phase: str | None
    phase_weight: float
    matched_rules: list[dict] = field(default_factory=list)
    secondary: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "eventType": self.event_type,
            "label": self.label,
            "polarity": self.polarity,
            "confidence": round(self.confidence, 3),
            "isSetback": self.is_setback,
            "phase": self.phase,
            "phaseWeight": self.phase_weight,
            "matchedRules": self.matched_rules,
            "secondary": self.secondary,
        }


def _is_negated(text: str, start: int) -> bool:
    window = text[max(0, start - 40):start]
    return bool(_NEGATION.search(window))


def classify(title: str, body: str) -> Classification:
    """Score every event type; the highest total wins."""
    # The title carries triple weight — headlines state the event.
    haystacks = [(title or "", 3), (body or "", 1)]
    totals: dict[str, int] = {k: 0 for k in EVENT_TYPES}
    fired: dict[str, list[dict]] = {k: [] for k in EVENT_TYPES}

    for etype, rules in _COMPILED.items():
        for pattern, points in rules:
            for text, mult in haystacks:
                if not text:
                    continue
                for m in pattern.finditer(text):
                    if _is_negated(text, m.start()):
                        continue
                    totals[etype] += points * mult
                    fired[etype].append(
                        {
                            "rule": pattern.pattern,
                            "match": m.group(0)[:60],
                            "points": points * mult,
                            "where": "title" if mult == 3 else "body",
                        }
                    )
                    break  # one hit per rule per field keeps scores bounded

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]

    if best_score == 0:
        return Classification(
            event_type="general",
            label="Market Note",
            polarity=0,
            confidence=0.25,
            is_setback=False,
            phase=detect_phase(f"{title} {body}"),
            phase_weight=PHASE_WEIGHTS.get(detect_phase(f"{title} {body}") or "", 0.4),
            matched_rules=[],
        )

    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    # Confidence = how decisively the winner beat the field, bounded to [0.3, 0.98]
    margin = (best_score - runner_up) / best_score
    saturation = min(1.0, best_score / 18.0)
    confidence = max(0.30, min(0.98, 0.45 + 0.35 * margin + 0.25 * saturation))

    cfg = EVENT_TYPES[best]
    phase = detect_phase(f"{title} {body}")
    secondary = [k for k, v in ranked[1:4] if v >= max(3, best_score * 0.45)]

    return Classification(
        event_type=best,
        label=cfg["label"],
        polarity=cfg["polarity"],
        confidence=confidence,
        is_setback=best in SETBACK_TYPES,
        phase=phase,
        phase_weight=PHASE_WEIGHTS.get(phase or "", 0.4),
        matched_rules=sorted(fired[best], key=lambda r: -r["points"])[:5],
        secondary=secondary,
    )


def detect_phase(text: str) -> str | None:
    for pattern, label in _PHASE_COMPILED:
        if pattern.search(text or ""):
            return label
    return None


@lru_cache(maxsize=512)
def _cue_re() -> re.Pattern[str]:
    return re.compile("|".join(re.escape(c) for c in LIMITATION_CUES), re.I)


def extract_limitations(text: str, limit: int = 3) -> list[dict]:
    """Pull out sentences that state a constraint, caveat or risk.

    These are quoted verbatim from the source — the system never paraphrases a
    limitation into something it did not say.
    """
    out: list[dict] = []
    cue = _cue_re()
    for sent in sentences(text):
        m = cue.search(sent)
        if not m:
            continue
        if len(sent) > 320:
            sent = sent[:317].rsplit(" ", 1)[0] + "…"
        out.append({"cue": m.group(0).lower(), "statement": sent})
        if len(out) >= limit:
            break
    return out


def event_meta(event_type: str) -> dict:
    cfg = EVENT_TYPES.get(event_type)
    if not cfg:
        return {"label": "Market Note", "polarity": 0, "weight": 0.4, "isSetback": False}
    return {
        "label": cfg["label"],
        "polarity": cfg["polarity"],
        "weight": cfg["weight"],
        "isSetback": event_type in SETBACK_TYPES,
    }


ALL_EVENT_TYPES = [
    {"id": k, "label": v["label"], "polarity": v["polarity"], "isSetback": k in SETBACK_TYPES}
    for k, v in sorted(EVENT_TYPES.items(), key=lambda kv: -kv[1]["weight"])
]
