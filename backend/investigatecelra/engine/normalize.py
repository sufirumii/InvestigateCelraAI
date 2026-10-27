"""Deterministic text normalisation utilities.

Pure standard library. Same input always produces the same output, which is
what makes the whole pipeline reproducible and auditable.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from .lexicons import STOPWORDS

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_WS_RE = re.compile(r"[ \t\u00a0]+")
_MULTINL_RE = re.compile(r"\n{3,}")
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-'/]*")

# Abbreviations that must not terminate a sentence.
_ABBREV = {
    "dr", "mr", "mrs", "ms", "prof", "inc", "ltd", "llc", "plc", "corp", "co",
    "vs", "etc", "e.g", "i.e", "no", "fig", "approx", "st", "jr", "sr", "u.s",
    "phase", "ph", "n", "p", "al",
}
_SENT_END_RE = re.compile(r"(?<=[.!?])[\"')\]]?\s+(?=[A-Z(\"'\u2018\u201c])")


def strip_html(raw: str) -> str:
    """Remove markup and decode entities without any external parser."""
    if not raw:
        return ""
    text = _SCRIPT_RE.sub(" ", raw)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.I)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    text = _WS_RE.sub(" ", text)
    text = _MULTINL_RE.sub("\n\n", text)
    return text.strip()


def clean_text(raw: str) -> str:
    text = strip_html(raw)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2014", " — ")
    return text.strip()


def sentences(text: str, min_len: int = 25, max_count: int = 80) -> list[str]:
    """Split into sentences with a small abbreviation guard."""
    if not text:
        return []
    flat = re.sub(r"\s+", " ", text).strip()
    raw_parts = _SENT_END_RE.split(flat)
    out: list[str] = []
    buffer = ""
    for part in raw_parts:
        candidate = (buffer + " " + part).strip() if buffer else part.strip()
        last_word = candidate.rsplit(" ", 1)[-1].rstrip(".").lower()
        if last_word in _ABBREV and len(candidate) < 400:
            buffer = candidate
            continue
        buffer = ""
        if len(candidate) >= min_len:
            out.append(candidate)
        if len(out) >= max_count:
            break
    if buffer and len(buffer) >= min_len and len(out) < max_count:
        out.append(buffer)
    return out


def tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and len(t) > 2]


def fingerprint(*parts: str) -> str:
    """Stable id for a record."""
    joined = "\u0001".join(p.strip().lower() for p in parts if p)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def simhash(text: str, bits: int = 64) -> int:
    """64-bit SimHash over content tokens, used for near-duplicate detection."""
    vector = [0] * bits
    toks = content_tokens(text)
    if not toks:
        return 0
    for tok in toks:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        for i in range(bits):
            vector[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(bits):
        if vector[i] > 0:
            out |= 1 << i
    return out


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
_DATE_FORMATS = (
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%a, %d %b %Y %H:%M:%S",
    "%d %b %Y %H:%M:%S %z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d %B %Y",
    "%B %d, %Y",
)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    raw = re.sub(r"\s+", " ", raw)
    raw = raw.replace("GMT", "+0000").replace("UTC", "+0000")
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    return None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def age_days(dt: datetime, reference: datetime | None = None) -> float:
    ref = reference or now_utc()
    return max(0.0, (ref - dt).total_seconds() / 86400.0)


def day_key(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def days_between(start: datetime, end: datetime) -> list[str]:
    out = []
    cur = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while cur <= end:
        out.append(day_key(cur))
        cur += timedelta(days=1)
    return out


def host_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    if not m:
        return ""
    return m.group(1).lower().removeprefix("www.")


# ---------------------------------------------------------------------------
# Numeric fact extraction — "key figures" shown on each story card.
# ---------------------------------------------------------------------------
_FIGURE_PATTERNS: list[tuple[str, str]] = [
    (r"\$\s?\d[\d,.]*\s?(?:billion|million|bn|m\b|B\b)?", "value"),
    (r"\b\d{1,3}(?:\.\d+)?\s?%", "percentage"),
    (r"\bn\s?=\s?\d[\d,]*", "cohort"),
    (r"\bp\s?[=<>]\s?0?\.\d+", "p-value"),
    (r"\bHR\s?[=:]?\s?0?\.\d+", "hazard ratio"),
    (r"\b\d[\d,]{2,}\s+patients?\b", "patients"),
    (r"\bPhase\s?(?:1|2|3|4|I{1,3}|IV)(?:/(?:1|2|3|I{1,3}))?\b", "phase"),
]


def key_figures(text: str, limit: int = 6) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for pattern, kind in _FIGURE_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.I):
            val = re.sub(r"\s+", " ", m.group(0)).strip()
            key = val.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"value": val, "kind": kind})
            if len(out) >= limit:
                return out
    return out


# ---------------------------------------------------------------------------
# Title casing
# ---------------------------------------------------------------------------
# Trial registries are full of backronym titles: the sponsor capitalises
# whichever letters spell out the study's nickname, giving strings like
# "Survival imProvement in Lung cancEr iNduced by DenOsUmab theRapy" (SIRENA).
# That is genuinely what the registry holds, but it reads as a typo in a
# headline. We restore ordinary casing without touching the words themselves.
#
# Three rules, applied per token, each deliberately conservative:
#   A. lowercase first letter + any later uppercase  -> lowercase the token
#      ("imProvement", "cancEr", "iNduced", "theRapy")
#   B. uppercase first letter + two or more later uppercase -> capitalise only
#      ("DenOsUmab" -> "Denosumab"; "AstraZeneca" has one internal capital and
#      is therefore left alone, as are "McDonald" and "BioNTech")
#   C. everything else is preserved verbatim
#
# Tokens containing a digit (HER2, HIV-1, F/TAF), all-capital tokens (FDA,
# NSCLC, mRNA is handled by rule A giving "mrna"... so mRNA-style tokens are
# whitelisted), and roman-numeral phase markers are never touched.

_ROMAN = {"I", "II", "III", "IV", "V", "VI", "IIIB", "IIB", "IIA", "IIIA"}

# Lowercase-then-capital tokens that are real and must survive rule A.
_LOWER_CAP_KEEP = {
    "mRNA", "miRNA", "siRNA", "sgRNA", "gRNA", "tRNA", "rRNA", "cfDNA", "ctDNA",
    "dsDNA", "ssDNA", "pH", "iPSC", "iPSCs", "nAb", "nAbs", "eGFR", "iNKT",
    "pCR", "mAb", "mAbs", "bsAb", "scFv", "kDa", "nM", "pM", "µM",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


def _fix_token(token: str, keep: frozenset[str] = frozenset()) -> str:
    core = token.strip("-'\u2019")
    if core in _LOWER_CAP_KEEP or core in keep or core.upper() in _ROMAN:
        return token
    if any(ch.isdigit() for ch in token):
        return token
    letters = [c for c in core if c.isalpha()]
    if not letters or len(letters) < 3:
        return token
    if all(c.isupper() for c in letters):
        return token                                    # FDA, NSCLC, EMA

    later_caps = sum(1 for c in letters[1:] if c.isupper())
    # Adjacent capitals are how real names are built (BioNTech, McKesson,
    # DNAse); backronyms scatter isolated capitals through the word.
    adjacent = any(a.isupper() and b.isupper() for a, b in zip(letters, letters[1:]))
    if letters[0].islower() and later_caps and not adjacent:
        return token.lower()                            # rule A
    if letters[0].isupper() and later_caps >= 2 and not adjacent:
        return token[0] + token[1:].lower()             # rule B
    return token                                        # rule C


def normalize_title(title: str, keep: frozenset[str] | set[str] | None = None) -> str:
    """Repair backronym capitalisation without altering any word.

    Purely presentational and lossless in content: the letters and their order
    are untouched, only their case changes. Idempotent.

    `keep` is a set of tokens to leave exactly as written — the caller passes
    every surface form in the gazetteer, so recognised company, target and
    modality names are never reshaped by the heuristics above.
    """
    if not title:
        return title
    kept = frozenset(keep or ())
    return _WORD_RE.sub(lambda m: _fix_token(m.group(0), kept), title)
