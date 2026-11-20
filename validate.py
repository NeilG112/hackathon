#!/usr/bin/env python3
"""The credibility layer — measured error against a real human bid. Task 005.

PLAN.md calls this the whole pitch. Price the blank BoQ
`[NUMMER_001]_leer.X83` (248 items) and compare against
`StBALV23040.D86` (249 priced items, bid total EUR 897,305.45 — actually
submitted by a contractor for the same bill of quantities).

    python3 validate.py

Prints:
  - our estimated total vs. the actual 897,305.45, and the % error
  - the worst-deviating positions, ranked
  - how many positions disagree by more than 30%

**Join on composed OZ, never on list index** — that is what absorbs the
248/249 discrepancy. The one extra position is itself a finding worth looking
at (PLAN.md open threads).

Build this BEFORE the UI. If the error is wild there is still time to tune
`core/constants.py`; after the UI exists there isn't.
"""

from __future__ import annotations

import sys

from core import constants

BLANK = constants.REVEAL["blank_boq"]
ANSWER_KEY = constants.REVEAL["answer_key"]
ACTUAL_TOTAL = constants.REVEAL["actual_bid_total_eur"]


def main() -> int:
    raise NotImplementedError("task 005")


if __name__ == "__main__":
    sys.exit(main())
