"""GAEB 90 fixed-width parser (.D83 / .D84 / .D86).

STATUS: stub — owned by task 001 (the gate).

Hard requirements, already verified against the dataset (PLAN.md):

- Encoding **cp850**, CRLF line endings. Record type = first 2 chars.
- Type **21** records carry quantity + unit (these are the items).
  Type **23** records carry prices. Type 26 is long text.
- The last 6 chars of every line are a running sequence number, not data.
- **Three different column layouts** exist across the dataset, with differing
  field widths *and* offsets. So offsets are a calibrated `Layout`, never
  constants inside the slicing function. Detect the layout per file.
- Scaling: quantity / 1000, unit price / 100, total / 100.
  Verified: EP `0000000020` x qty `00000028000` = GB `000000000560`.
- A quantity-less `.D84` is spec-normal (it's a bid referencing its sibling
  `.D86`). Do not treat as corrupt; join on OZ.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from core.models import NormalizedItem

ENCODING = "cp850"
QTY_SCALE = 1000.0
PRICE_SCALE = 100.0


@dataclass
class Layout:
    """Per-file calibrated column slices for one record type.

    Half-open [start, end) character offsets into the decoded line.
    """

    oz: tuple[int, int]
    quantity: Optional[tuple[int, int]] = None
    unit: Optional[tuple[int, int]] = None
    unit_price: Optional[tuple[int, int]] = None
    total_price: Optional[tuple[int, int]] = None


def read_lines(path: str) -> List[str]:
    """Decode a GAEB 90 file to lines, stripping the trailing sequence number."""
    raise NotImplementedError("task 001")


def detect_layout(lines: List[str], record_type: str) -> Layout:
    """Infer column offsets for `record_type` from the file itself.

    See PLAN.md "The three OZ layouts" for the three known shapes. Prefer
    inference over a lookup table keyed on filename — the judge may upload a
    fourth shape, and degrading visibly beats fabricating output.
    """
    raise NotImplementedError("task 001")


def parse(path: str) -> List[NormalizedItem]:
    """Parse a GAEB 90 file into normalized items.

    Must return 159 items for `Dataset/8209.003_Leistungsverzeichnis_leer.D83`,
    matching `parser_x83.parse` of the .X83 twin on OZ, quantity and unit.
    """
    raise NotImplementedError("task 001")
