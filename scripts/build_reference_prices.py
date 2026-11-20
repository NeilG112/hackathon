#!/usr/bin/env python3
"""Build data/reference_prices.json from the real priced files. Task 002.

    python3 scripts/build_reference_prices.py

720 priced items, all the same trade (Tiefbau / Rohrleitung / Schacht /
Straßenbau) as the blank BoQs. PLAN.md: this is the strongest layer in the
system, and the pricer's primary source.

Sources (verified item counts, and their real bid totals):
    Angebot AN24-0305.D84   274 items   EUR 988,913.89
    StBALV23040.D86         249 items   EUR 897,305.45   <- the reveal's answer key
    [ORT_024] LV24069.D86   197 items   EUR 536,991.65
    StBALV23040.D84         249 prices, 0 quantities — the same bid as the .D86
                            above, so it is NOT a fourth source. Skipped to
                            avoid double-weighting that contractor's prices.

`EP x qty = GB` is checked on every row before it is accepted, so a bad column
slice cannot quietly poison the benchmark. Output shape:

    {
      "meta":      {...sources, counts, rejects...},
      "by_unit":   {"m": {"n": 104, "median": 20.0, "p25":..., "p75":...}, ...},
      "by_bucket": {"rohr|m": {...}, "armatur|st": {...}, ...},
      "items":     [{"oz","unit","ep","bucket","src","text"}]
    }

Do NOT modify anything in Dataset/. Read-only, always.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from typing import Dict, Iterable, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import constants, parser_gaeb90, pricer
from core.models import NormalizedItem

# StBALV23040.D84 is deliberately absent: it is the same bid as its .D86
# sibling (identical 897,305.45 total), and including both would double-weight
# one contractor's price list.
SOURCES = [
    "Dataset/Angebot AN24-0305.D84",
    "Dataset/StBALV23040.D86",
    "Dataset/[ORT_024] LV24069.D86",
]
OUT = constants.REFERENCE_PRICES

MIN_SENSIBLE_EP = 0.01   # below this the item is a rounding artifact, not a price


# Shared with the pricer on purpose — see constants.bucket_for_text.
bucket_for_text = constants.bucket_for_text


# Grouping and percentiles live in core.pricer: validate.py has to rebuild
# these distributions with the answer key held out, and two implementations
# would drift.
summarize = pricer.summarize_prices


def collect(paths: Iterable[str]) -> tuple[List[dict], dict]:
    """Read every priced item from `paths`, rejecting anything inconsistent."""
    rows: List[dict] = []
    rejects = defaultdict(int)
    per_source = {}

    for path in paths:
        items: List[NormalizedItem] = parser_gaeb90.parse(path)
        price_rows = {p.key(): p for p in parser_gaeb90.parse_prices(path)}
        kept = 0

        for item in items:
            price = price_rows.get(item.key())
            if price is None or item.unit_price is None:
                rejects["no price record"] += 1
                continue
            if not price.consistent():
                # EP x qty != GB — the slice is wrong, do not trust the number.
                rejects["EPxqty != GB"] += 1
                continue
            if item.unit_price < MIN_SENSIBLE_EP:
                rejects["EP below 0.01"] += 1
                continue
            # Quantity-less, unit-less but priced = Bedarfs-/Eventualposition
            # (e.g. "Mehrkosten Armaturen für Ausführung VAG"). 38 of these in
            # [ORT_024] LV24069.D86. They are real prices for optional work, so
            # they are kept and flagged — detector 3's provisional-share check
            # wants them — but they are excluded from the rate distributions,
            # where a unit-less price has nothing to be compared against.
            unit = constants.normalize_unit(item.unit)
            provisional = not unit or item.quantity == 0

            rows.append({
                "oz": item.key(),
                "unit": unit,
                "ep": round(item.unit_price, 2),
                "qty": round(item.quantity, 3),
                "total": round(item.total_price or 0.0, 2),
                "bucket": bucket_for_text(item.short_text or item.long_text),
                "rental": unit in constants.TIME_RENTAL_UNITS,
                "provisional": provisional,
                "src": os.path.basename(path),
                "text": (item.short_text or "")[:140],
            })
            kept += 1

        per_source[os.path.basename(path)] = {
            "items": len(items),
            "kept": kept,
            "bid_total": round(sum(i.total_price or 0.0 for i in items), 2),
        }

    return rows, {"per_source": per_source, "rejects": dict(rejects)}


build = pricer.build_distributions


def main() -> int:
    missing = [p for p in SOURCES if not os.path.exists(p)]
    if missing:
        print("missing source files:")
        for p in missing:
            print(f"  {p}")
        return 1

    rows, report = collect(SOURCES)
    if not rows:
        print("no priced items collected — refusing to write an empty benchmark")
        return 1

    grouped = build(rows)
    payload = {
        "meta": {
            "sources": SOURCES,
            "priced_items": len(rows),
            "note": (
                "Observed unit prices from real submitted bids. Rental/"
                "time-on-site units are excluded from the distributions."
            ),
            **report,
        },
        **grouped,
        "items": rows,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"{len(rows)} priced items -> {OUT}")
    for name, info in report["per_source"].items():
        print(f"  {name:<26} {info['kept']:>4}/{info['items']:<4} kept   "
              f"bid total {info['bid_total']:>14,.2f}")
    if report["rejects"]:
        print("  rejected:", report["rejects"])
    print(f"  {len(grouped['by_unit'])} unit distributions, "
          f"{len(grouped['by_bucket'])} bucket x unit distributions")

    usable = {k: v for k, v in grouped["by_bucket"].items()
              if v["n"] >= constants.MIN_COMPARABLES}
    print(f"  {len(usable)} bucket distributions have >= "
          f"{constants.MIN_COMPARABLES} comparables (usable by the detector)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
