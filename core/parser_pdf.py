"""PDF tender reader.

A GAEB file is structured data; a PDF is a picture of a table. Everything
here is recovery of structure that was thrown away at print time, so it is
best-effort by nature — and it says so rather than pretending otherwise.
`parse` reports how many positions it found and `confidence` tells the UI
whether to trust the result.

The layout these files use, recovered with `pdftotext -layout`:

    Ordnungszahl   Leistungsbeschreibung        Menge ME   Einheitspreis ...
    2.1.50.        Wiesen- und Ackerflächen herrichten (Baufeldbreite 12 m
                   bis 14 m)
                   Bei Trassenverlauf in Wiesen wird der Humus nur im ...
                                       6.800,000 m³   ..........  ..........

So: an OZ at the left margin opens a position, its short text follows on the
same line, indented lines are the long text, and a right-aligned
number-plus-unit line carries the quantity. German decimals throughout —
`6.800,000` is six thousand eight hundred, not six point eight.

**Prices in the PDF are deliberately ignored.** A priced PDF is somebody's
submitted bid; reading its numbers into our own calculation is how the
leakage happened the first time. Only quantities and text are taken.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import List

from core.models import NormalizedItem
from utils.text_cleaning import collapse_whitespace

# An Ordnungszahl at the left margin: "2.1.50." / "01.02.0030" / "1.10"
OZ_LINE = re.compile(r"^(\d{1,3}(?:\.\d{1,4}){1,4}\.?)\s{2,}(\S.*)$")
# A right-aligned quantity: "6.800,000 m³" or "12,000 Stck"
QTY_LINE = re.compile(
    r"^\s{8,}([\d.]{1,12},\d{1,3}|\d{1,9})\s+"
    r"([A-Za-zÄÖÜäöüß²³%/]{1,6})(?:\s|$)"
)
# Page furniture that must never become text
NOISE = re.compile(
    r"^\s*(Ordnungszahl|Projekt:|LV:|Seite\b|Übertrag|Summe\b|Datum:|"
    r"Angebotssumme|Blatt\b|-\s*\d+\s*-\s*$)",
    re.IGNORECASE,
)


class PdfToolMissing(RuntimeError):
    """`pdftotext` is not installed. Say so; do not silently return nothing."""


def _german_number(raw: str) -> float:
    """`6.800,000` -> 6800.0. Thousands dot, decimal comma."""
    cleaned = raw.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def extract_text(path: str) -> str:
    """Lay the PDF out as text. Prefers pdfplumber, falls back to pdftotext."""
    try:
        import pdfplumber                                   # noqa: PLC0415
    except ImportError:
        pdfplumber = None

    if pdfplumber is not None:
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text(layout=True) or ""
                             for page in pdf.pages)

    if not shutil.which("pdftotext"):
        raise PdfToolMissing(
            "Weder pdfplumber noch pdftotext verfügbar — PDF kann nicht "
            "gelesen werden. Installiere poppler-utils oder pdfplumber."
        )
    result = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", path, "-"],
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise PdfToolMissing(
            f"pdftotext scheiterte: {result.stderr.decode('utf-8', 'replace')[:200]}"
        )
    return result.stdout.decode("utf-8", "replace")


def parse(path: str) -> List[NormalizedItem]:
    """Read a tender PDF into normalized items, in document order."""
    items, _stats = parse_with_stats(path)
    return items


def parse_with_stats(path: str) -> tuple[List[NormalizedItem], dict]:
    """Same as `parse`, plus what was seen and what was dropped."""
    text = extract_text(path)
    items: List[NormalizedItem] = []
    seen_oz = 0
    dropped: List[str] = []
    current: dict | None = None
    long_lines: List[str] = []

    def flush() -> None:
        # A heading ("1.1  Baustelleneinrichtung") carries an Ordnungszahl but
        # no quantity and no unit. It is a chapter title, not something anyone
        # prices. Keeping them inflates the position count and drags the
        # quantity share down, which made a good parse look like a bad one.
        if current is None:
            return
        if current["quantity"] <= 0 or not current["unit"]:
            dropped.append(current["oz"])
            return
        items.append(NormalizedItem(
            oz=current["oz"],
            quantity=current["quantity"],
            unit=current["unit"],
            short_text=collapse_whitespace(current["short"]),
            long_text=collapse_whitespace(" ".join(long_lines)),
            source_file=path,
            source_ref=f"pdf:{current['oz']}",
        ))

    for raw_line in text.splitlines():
        if NOISE.match(raw_line):
            continue

        opened = OZ_LINE.match(raw_line)
        if opened:
            seen_oz += 1
            flush()
            long_lines = []
            current = {
                "oz": opened.group(1).rstrip("."),
                "short": opened.group(2),
                "quantity": 0.0,
                "unit": "",
            }
            continue

        if current is None:
            continue

        quantity = QTY_LINE.match(raw_line)
        if quantity and not current["unit"]:
            current["quantity"] = _german_number(quantity.group(1))
            current["unit"] = quantity.group(2).strip()
            continue

        stripped = raw_line.strip()
        if stripped:
            long_lines.append(stripped)

    flush()
    stats = {
        "oz_lines_seen": seen_oz,
        "positions": len(items),
        "dropped_without_quantity": len(dropped),
        "dropped_examples": dropped[:5],
    }
    return items, stats


def confidence(items: List[NormalizedItem], stats: dict | None = None) -> dict:
    """How much of the document actually came through.

    The useful number is **yield**: of every line that looked like an
    Ordnungszahl, how many became a priceable position. Measuring "share of
    kept items that have a quantity" is tautological — items without one are
    dropped — and it reported a confident 100 % on a file where only 3 of 274
    positions were recovered.
    """
    total = len(items)
    with_long = sum(1 for i in items if len(i.long_text) > 40)
    seen = (stats or {}).get("oz_lines_seen", total)
    yield_pct = (100.0 * total / seen) if seen else 0.0
    return {
        "positions": total,
        "oz_lines_seen": seen,
        "dropped_without_quantity": (stats or {}).get(
            "dropped_without_quantity", 0),
        "with_long_text": with_long,
        "yield_pct": round(yield_pct, 1),
        # Headings legitimately account for a slice of every tender, so a
        # yield well under half means the quantity column was not recovered.
        "usable": total >= 5 and yield_pct >= 40.0,
    }
