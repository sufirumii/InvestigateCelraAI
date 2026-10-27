#!/usr/bin/env python3
"""Prove that every configured source is live and returning real records.

Run this first, before you trust anything the desk shows you:

    PYTHONPATH=backend python scripts/verify_sources.py

For each source it performs a real request and prints the number of records
returned plus the newest headline, so you can see with your own eyes that the
content came from the publisher and not from this repository. There is no
offline mode and no fixture to fall back on: a source that cannot be reached
is reported as a failure and the exit code is non-zero.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from investigatecelra.ingest import clinicaltrials, pubmed, rss  # noqa: E402
from investigatecelra.ingest.base import source_registry  # noqa: E402
from investigatecelra.pipeline import tracked_sponsors  # noqa: E402
from investigatecelra import db  # noqa: E402


def line(char: str = "-") -> None:
    print(char * 78)


def show(name: str, docs: list[dict], errors: list[str]) -> bool:
    ok = bool(docs) and not errors
    flag = "  ok  " if ok else " FAIL "
    print(f"[{flag}] {name:<34} {len(docs):>4} records")
    if docs:
        newest = max(docs, key=lambda d: d.get("published_at") or "")
        title = (newest.get("title") or "").strip()
        print(f"          newest: {title[:72]}")
        print(f"          url:    {(newest.get('url') or '')[:72]}")
    for err in errors[:2]:
        print(f"          error:  {err[:72]}")
    return ok


def main() -> int:
    db.init()
    print("InvestigateCelra — live source verification")
    line("=")

    results: list[bool] = []

    print("\nRSS and Atom feeds")
    line()
    for source in [s for s in source_registry() if s.get("type") == "rss"]:
        result = rss.fetch(source)
        results.append(show(source["name"], result.documents, result.errors))

    sponsors = tracked_sponsors()
    print(f"\nClinicalTrials.gov v2  (sponsors queried: {len(sponsors)})")
    line()
    ct = clinicaltrials.fetch_for_sponsors(sponsors)
    results.append(show("ClinicalTrials.gov", ct.documents, ct.errors))
    print(f"          trials parsed: {len(ct.trials)}")

    print("\nPubMed E-utilities")
    line()
    pm = pubmed.fetch_query(f'"{sponsors[0]}"[Affiliation]' if sponsors else "clinical trial")
    results.append(show("PubMed", pm.documents, pm.errors))

    line("=")
    passed = sum(results)
    print(f"{passed}/{len(results)} sources returned live records")
    if passed == 0:
        print("\nNo source is reachable. The desk cannot build an edition, and by")
        print("design it will not invent one. Check outbound HTTPS access.")
        return 2
    if passed < len(results):
        print("\nSome sources failed. The desk will run on the remainder; failures")
        print("are recorded in the run history at /api/method.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
