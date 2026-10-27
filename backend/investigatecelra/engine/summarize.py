"""Extractive summarisation.

Sentences are ranked by a transparent linear score and the best ones are
reproduced verbatim in their original order. Nothing is generated, so the
summary can never contain a claim the source did not make.
"""

from __future__ import annotations

import re
from math import log

from .lexicons import SALIENT_TERMS, STOPWORDS
from .normalize import content_tokens, sentences

_NUM_RE = re.compile(r"\d")
_QUOTE_RE = re.compile(r"^[\"'\u201c]")


def _term_frequencies(sents: list[str]) -> dict[str, int]:
    tf: dict[str, int] = {}
    for s in sents:
        for tok in content_tokens(s):
            tf[tok] = tf.get(tok, 0) + 1
    return tf


def score_sentences(text: str, boost_terms: set[str] | None = None) -> list[tuple[float, int, str]]:
    """Return (score, position, sentence) for every candidate sentence."""
    sents = sentences(text)
    if not sents:
        return []
    tf = _term_frequencies(sents)
    if not tf:
        return []
    peak = max(tf.values())
    boost = {b.lower() for b in (boost_terms or set())}
    total = len(sents)
    scored: list[tuple[float, int, str]] = []

    for idx, sent in enumerate(sents):
        toks = content_tokens(sent)
        if not toks:
            continue
        # 1. content density: normalised term frequency
        density = sum(tf[t] / peak for t in toks) / (len(toks) ** 0.65)
        # 2. lead bias: journalism puts the news first
        position = 1.0 / (1.0 + log(1 + idx)) if idx < total else 0.2
        # 3. commercially salient vocabulary
        salience = sum(1 for t in toks if t in SALIENT_TERMS) / max(4, len(toks)) * 3.0
        # 4. concrete numbers are what analysts quote
        numeric = 0.35 if _NUM_RE.search(sent) else 0.0
        # 5. topic boost (entity names, watchlist terms)
        topical = sum(1 for t in toks if t in boost) / max(4, len(toks)) * 2.0
        # 6. penalties: very short, very long, or a bare quotation
        penalty = 0.0
        words = len(sent.split())
        if words < 8:
            penalty += 0.5
        if words > 55:
            penalty += 0.35
        if _QUOTE_RE.match(sent.strip()):
            penalty += 0.30

        score = 1.10 * density + 0.85 * position + salience + numeric + topical - penalty
        scored.append((score, idx, sent))

    return scored


def summarise(text: str, max_sentences: int = 3, boost_terms: set[str] | None = None) -> str:
    scored = score_sentences(text, boost_terms)
    if not scored:
        return ""
    top = sorted(scored, key=lambda x: -x[0])[:max_sentences]
    top.sort(key=lambda x: x[1])
    return " ".join(s for _, _, s in top)


def headline_digest(text: str, boost_terms: set[str] | None = None) -> str:
    """One-sentence lede for compact cards."""
    scored = score_sentences(text, boost_terms)
    if not scored:
        return ""
    best = max(scored, key=lambda x: x[0])[2]
    if len(best) > 240:
        best = best[:237].rsplit(" ", 1)[0] + "…"
    return best


def corpus_document_frequencies(docs: list[str]) -> tuple[dict[str, int], int]:
    """Document frequency table used by the TF-IDF keyword extractor."""
    df: dict[str, int] = {}
    for doc in docs:
        seen = set()
        for tok in content_tokens(doc):
            if tok in STOPWORDS or len(tok) < 4:
                continue
            if tok in seen:
                continue
            seen.add(tok)
            df[tok] = df.get(tok, 0) + 1
    return df, len(docs)
