"""Intelligence Momentum Index.

Each tracked company gets a daily index series computed from its own news flow.
It is not a stock price and it is not a forecast: it is an accounting identity
over observed events, so the same corpus always yields the same curve.

    indexₜ = indexₜ₋₁ · (1 + pressureₜ − decay·(indexₜ₋₁ − 100)/100)

    pressureₜ = Σᵢ impactᵢ · w(t − dateᵢ) / Σ w      for dateᵢ ≤ t

where impactᵢ = polarity · eventWeight · (signal/100) · phaseWeight · k and
w(Δ) = exp(−Δ/τ) is a decay kernel. A story therefore exerts its influence
over the fortnight that follows it rather than on its publication day alone,
which is both a fairer reading of how news is absorbed and the reason the
curve is continuous instead of a row of spikes.

The mean-reversion term pulls an un-newsworthy company back toward the 100
baseline so the chart reflects *current* momentum rather than accumulated history.
"""

from __future__ import annotations

from collections import defaultdict
from math import exp
from datetime import datetime, timedelta, timezone

from .lexicons import EVENT_TYPES
from .normalize import day_key, parse_date

BASELINE = 100.0
IMPACT_SCALE = 0.075          # a maximal single event moves the index ~7.5%
REVERSION = 0.035             # daily pull back to baseline
MAX_DAILY_MOVE = 0.14
DIFFUSION_TAU = 11.0          # days; decay constant of the influence kernel
DIFFUSION_SPAN = 34           # days; kernel truncated beyond this


def _impact(item: dict) -> float:
    cls = item.get("classification", {})
    polarity = cls.get("polarity", 0)
    if polarity == 0:
        # Structural news still creates volatility; direction taken from tone of
        # the event weight only, magnitude halved.
        polarity = 0.35 if not cls.get("isSetback") else -0.5
    cfg = EVENT_TYPES.get(cls.get("eventType", ""), {})
    weight = cfg.get("weight", 0.5)
    signal = float(item.get("signal", {}).get("value", 40.0)) / 100.0
    phase = float(cls.get("phaseWeight") or 0.4)
    confidence = float(cls.get("confidence", 0.5))
    return polarity * weight * signal * (0.55 + 0.45 * phase) * confidence * IMPACT_SCALE


def series_for(
    items: list[dict],
    *,
    days: int = 365,
    end: datetime | None = None,
) -> list[dict]:
    """Build the daily index series for one company's items."""
    end = (end or datetime.now(timezone.utc)).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)

    by_day: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        dt = parse_date(item.get("publishedAt"))
        if not dt:
            continue
        by_day[day_key(dt)].append(item)

    # Pre-compute the normalised decay kernel once.
    kernel = [exp(-d / DIFFUSION_TAU) for d in range(DIFFUSION_SPAN + 1)]
    kernel_sum = sum(kernel)
    kernel = [k / kernel_sum for k in kernel]

    # Impact per calendar day, before diffusion.
    raw: dict[str, float] = {k: sum(_impact(i) for i in v) for k, v in by_day.items()}

    out: list[dict] = []
    level = BASELINE
    cur = start
    while cur <= end:
        key = day_key(cur)
        todays = by_day.get(key, [])
        # Today's pressure is every recent event, weighted by how long ago it
        # broke. Δ = 0 is today; the loop walks backwards through the kernel.
        move = 0.0
        for delta, weight in enumerate(kernel):
            contribution = raw.get(day_key(cur - timedelta(days=delta)))
            if contribution:
                move += contribution * weight
        move = max(-MAX_DAILY_MOVE, min(MAX_DAILY_MOVE, move))
        reversion = REVERSION * (level - BASELINE) / BASELINE
        level = level * (1.0 + move - reversion)
        level = max(20.0, min(400.0, level))
        out.append(
            {
                "date": key,
                "value": round(level, 2),
                "events": len(todays),
                "move": round(move * 100, 3),
            }
        )
        cur += timedelta(days=1)
    return out


def summarise_series(series: list[dict]) -> dict:
    """Headline number plus the change windows an Apple Stocks card shows."""
    if not series:
        return {
            "last": BASELINE, "change": 0.0, "changePct": 0.0,
            "windows": {}, "high": BASELINE, "low": BASELINE, "volatility": 0.0,
        }
    last = series[-1]["value"]
    values = [p["value"] for p in series]

    def window(n: int) -> dict:
        if len(series) <= 1:
            return {"change": 0.0, "changePct": 0.0}
        base = series[max(0, len(series) - 1 - n)]["value"]
        delta = last - base
        return {"change": round(delta, 2), "changePct": round(100 * delta / base, 2) if base else 0.0}

    moves = [p["move"] for p in series[-90:] if p["move"]]
    vol = (sum(m * m for m in moves) / len(moves)) ** 0.5 if moves else 0.0

    prev = series[-2]["value"] if len(series) > 1 else last
    return {
        "last": round(last, 2),
        "change": round(last - prev, 2),
        "changePct": round(100 * (last - prev) / prev, 2) if prev else 0.0,
        "windows": {"1W": window(7), "1M": window(30), "3M": window(90), "6M": window(182), "1Y": window(365)},
        "high": round(max(values), 2),
        "low": round(min(values), 2),
        "volatility": round(vol, 3),
    }


def sparkline(series: list[dict], points: int = 60) -> list[float]:
    """Downsample for the compact card chart."""
    if not series:
        return []
    if len(series) <= points:
        return [p["value"] for p in series]
    step = len(series) / points
    return [round(series[int(i * step)]["value"], 2) for i in range(points)]
