#!/usr/bin/env python3
"""Pre-parse every GAEB file to data/golden/. Task 002.

    python3 scripts/dump_golden.py

This is the on-stage fallback: if a live parse dies, the app loads from
`data/golden/` instead. PLAN.md says wire it Saturday, not Sunday.

One JSON per input file, named after it, containing the serialized
`List[NormalizedItem]` plus the `<Remark>` texts the vague-scope detector needs.
"""

from __future__ import annotations

import sys

from core import constants

GAEB_FILES = [
    "Dataset/8209.003_Leistungsverzeichnis_leer.D83",
    "Dataset/8209.003_Leistungsverzeichnis_leer.X83",
    "Dataset/[NUMMER_001]_leer.X83",      # the demo upload
    "Dataset/501-24-01_GAEB-XML_sas.x83",
    "Dataset/GAEB-[PROJEKT_004].X83",
    "Dataset/Angebot AN24-0305.D84",
    "Dataset/StBALV23040.D84",
    "Dataset/StBALV23040.D86",
    "Dataset/[ORT_024] LV24069.D86",
]
OUT_DIR = constants.GOLDEN_DIR


def main() -> int:
    raise NotImplementedError("task 002")


if __name__ == "__main__":
    sys.exit(main())
