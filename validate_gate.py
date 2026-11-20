#!/usr/bin/env python3
"""THE GATE — twin-pair parser equivalence. Task 001.

`Dataset/8209.003_Leistungsverzeichnis_leer.{D83,X83}` are the same bill of
quantities in two formats, 159 items each. Parse both, prove they agree.
Nothing else in this repo gets built until this exits 0.

    python3 validate_gate.py

Asserts all three of:
  - both parsers return exactly 159 items
  - the sets of normalized OZ keys are identical (report symmetric difference)
  - for every matched OZ, quantity (3dp) and unit are equal

Item text is reported but NOT asserted — the two formats store it differently.
Lump-sum status is likewise not asserted: GAEB 90's flag zone carries no signal
(every type-21 record is the identical literal `NNN`).

Do not loosen an assertion to make this pass. A real failure is useful; a gate
that passes by weakened comparison is worse than no gate.
"""

from __future__ import annotations

import sys
from typing import Dict, List

from core import parser_gaeb90, parser_x83
from core.models import NormalizedItem
from utils.text_cleaning import compare_key

D83 = "Dataset/8209.003_Leistungsverzeichnis_leer.D83"
X83 = "Dataset/8209.003_Leistungsverzeichnis_leer.X83"
EXPECTED_ITEMS = 159

MAX_REPORTED = 15


def by_key(items: List[NormalizedItem]) -> Dict[str, NormalizedItem]:
    return {i.key(): i for i in items}


def main() -> int:
    failures: List[str] = []

    d83 = parser_gaeb90.parse(D83)
    x83 = parser_x83.parse(X83)

    print(f"D83  {len(d83):>4} items  {D83}")
    print(f"X83  {len(x83):>4} items  {X83}")

    # --- 1. item counts ----------------------------------------------------
    for label, items in (("D83", d83), ("X83", x83)):
        if len(items) != EXPECTED_ITEMS:
            failures.append(
                f"{label}: expected {EXPECTED_ITEMS} items, got {len(items)}"
            )

    # --- 2. OZ key sets ----------------------------------------------------
    left, right = by_key(d83), by_key(x83)
    if len(left) != len(d83):
        failures.append(
            f"D83: {len(d83)} items collapse to {len(left)} distinct OZ keys "
            "— normalize_oz is losing information"
        )
    if len(right) != len(x83):
        failures.append(
            f"X83: {len(x83)} items collapse to {len(right)} distinct OZ keys "
            "— normalize_oz is losing information"
        )

    only_d83 = sorted(set(left) - set(right))
    only_x83 = sorted(set(right) - set(left))
    if only_d83 or only_x83:
        failures.append(
            f"OZ key sets differ: {len(only_d83)} only in D83, "
            f"{len(only_x83)} only in X83"
        )
        for key in only_d83[:MAX_REPORTED]:
            print(f"  only D83: {key!r}  (raw {left[key].oz!r})")
        for key in only_x83[:MAX_REPORTED]:
            print(f"  only X83: {key!r}  (raw {right[key].oz!r})")
    else:
        print(f"OZ   {len(left):>4} keys identical on both sides")

    # --- 3. quantity + unit on matched keys --------------------------------
    mismatches = []
    for key in sorted(set(left) & set(right)):
        a, b = left[key], right[key]
        if a.comparable() != b.comparable():
            mismatches.append((key, a, b))
    if mismatches:
        failures.append(f"{len(mismatches)} matched OZ differ on quantity or unit")
        for key, a, b in mismatches[:MAX_REPORTED]:
            print(
                f"  {key}: D83 qty={a.quantity:.3f} unit={a.unit!r}  "
                f"!=  X83 qty={b.quantity:.3f} unit={b.unit!r}"
            )
    else:
        print(f"QTY  {len(set(left) & set(right)):>4} matched items agree on quantity and unit")

    # --- informational: text + lump sum -----------------------------------
    shared = sorted(set(left) & set(right))
    text_diff = [k for k in shared
                 if compare_key(left[k].short_text) != compare_key(right[k].short_text)]
    print(f"TEXT {len(text_diff):>4} of {len(shared)} items differ on short text "
          "(informational, not asserted)")
    print(f"LUMP {sum(1 for i in x83 if i.is_lump_sum):>4} lump-sum items in X83 "
          "(D83 carries no such flag — not asserted)")

    if failures:
        print()
        print("GATE RED")
        for f in failures:
            print(f"  - {f}")
        return 1

    print()
    print("GATE GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
