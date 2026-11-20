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

Do not loosen an assertion to make this pass. A real failure is useful; a gate
that passes by weakened comparison is worse than no gate.
"""

from __future__ import annotations

import sys

from core import parser_gaeb90, parser_x83
from utils.text_cleaning import compare_key

D83 = "Dataset/8209.003_Leistungsverzeichnis_leer.D83"
X83 = "Dataset/8209.003_Leistungsverzeichnis_leer.X83"
EXPECTED_ITEMS = 159


def main() -> int:
    raise NotImplementedError("task 001")


if __name__ == "__main__":
    sys.exit(main())
