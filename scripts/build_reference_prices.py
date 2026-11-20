#!/usr/bin/env python3
"""Build data/reference_prices.json from the real priced files. Task 002.

    python3 scripts/build_reference_prices.py

~720 priced items, all the same trade (Tiefbau / Rohrleitung / Schacht /
Straßenbau) as the blank BoQs. PLAN.md: this is the strongest layer in the
system, and the pricer's primary source.

Sources (verified item counts):
    Angebot AN24-0305.D84   274 qty + 274 price   usable as-is
    StBALV23040.D86         249 qty + 249 price   usable as-is
    [ORT_024] LV24069.D86   197 qty + 197 price   usable as-is
    StBALV23040.D84           0 qty + 249 price   prices only — join to .D86 on OZ

Output shape (medians per unit and per keyword bucket), plus enough to let the
outlier detector work:

    {
      "by_unit":   {"m": {"n": 310, "median": 41.2, "p25": ..., "p75": ...}, ...},
      "by_bucket": {"rohr|m": {...}, "schacht|st": {...}, ...},
      "items":     [{"oz": ..., "unit": ..., "ep": ..., "bucket": ..., "src": ...}]
    }

Do NOT modify anything in Dataset/. Read-only, always.
"""

from __future__ import annotations

import sys

SOURCES = [
    "Dataset/Angebot AN24-0305.D84",
    "Dataset/StBALV23040.D86",
    "Dataset/[ORT_024] LV24069.D86",
    "Dataset/StBALV23040.D84",   # prices only; join to its .D86 sibling on OZ
]
OUT = "data/reference_prices.json"


def main() -> int:
    raise NotImplementedError("task 002")


if __name__ == "__main__":
    sys.exit(main())
