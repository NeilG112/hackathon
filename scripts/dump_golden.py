#!/usr/bin/env python3
"""Pre-parse every GAEB file to data/golden/. Task 002.

    python3 scripts/dump_golden.py

This is the on-stage fallback: if a live parse dies, the app loads from
`data/golden/` instead. PLAN.md says wire it Saturday, not Sunday.

One JSON per input file, containing the serialized `List[NormalizedItem]` plus
the `<Remark>` texts the vague-scope detector needs (X83 only — GAEB 90 has no
equivalent record).

Also writes `data/golden/index.json`, a manifest the UI reads to populate its
"use a sample tender" buttons without having to guess filenames.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import constants, parser_gaeb90, parser_x83

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


def slug(path: str) -> str:
    return os.path.basename(path).replace(" ", "_")


def is_xml(path: str) -> bool:
    return path.lower().endswith((".x83", ".x81", ".x84", ".x86"))


def dump_one(path: str) -> dict:
    """Parse one file and write its fixture. Returns a manifest entry."""
    if is_xml(path):
        items = parser_x83.parse(path)
        remarks = parser_x83.parse_remarks(path)
    else:
        items = parser_gaeb90.parse(path)
        remarks = []

    priced = [i for i in items if i.unit_price is not None]
    payload = {
        "source": path,
        "items": [i.as_dict() for i in items],
        "remarks": remarks,
        "stats": {
            "items": len(items),
            "priced": len(priced),
            "remarks": len(remarks),
            "bid_total": round(sum(i.total_price or 0.0 for i in items), 2),
        },
    }

    out = os.path.join(OUT_DIR, slug(path) + ".json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    return {"source": path, "fixture": out, **payload["stats"]}


def load(path_or_slug: str) -> tuple[list, list]:
    """Read a fixture back. The app's fallback path calls this.

    Accepts either the original Dataset path or the fixture filename.
    """
    from core.models import NormalizedItem

    name = slug(path_or_slug)
    if not name.endswith(".json"):
        name += ".json"
    with open(os.path.join(OUT_DIR, name), encoding="utf-8") as fh:
        payload = json.load(fh)
    return (
        [NormalizedItem.from_dict(d) for d in payload["items"]],
        payload.get("remarks", []),
    )


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = []
    failed = []

    for path in GAEB_FILES:
        if not os.path.exists(path):
            failed.append((path, "missing"))
            continue
        try:
            entry = dump_one(path)
        except Exception as exc:                      # noqa: BLE001
            # A file we cannot parse is a known-unknown, not a crash. Record it
            # and keep going — the fallback is more useful partial than absent.
            failed.append((path, f"{type(exc).__name__}: {exc}"))
            continue
        manifest.append(entry)
        print(f"  {os.path.basename(path):<40} items={entry['items']:>4} "
              f"priced={entry['priced']:>4} remarks={entry['remarks']:>3}"
              + (f"  total={entry['bid_total']:>13,.2f}" if entry["bid_total"] else ""))

    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"fixtures": manifest}, fh, ensure_ascii=False, indent=1)

    print(f"{len(manifest)} fixtures -> {OUT_DIR}/")
    if failed:
        print("could not dump:")
        for path, why in failed:
            print(f"  {os.path.basename(path):<40} {why}")
    return 0 if manifest else 1


if __name__ == "__main__":
    sys.exit(main())
