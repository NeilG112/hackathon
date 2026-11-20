"""Shared data contract.

Everything in the system speaks `NormalizedItem`. Both parsers produce it, the
pricer and detectors consume it. If you need another field, add it here rather
than passing dicts around — this module is the one place all five workstreams
touch, so keep it boring and dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


def normalize_oz(raw: str) -> str:
    """Canonical form of a GAEB item number (Ordnungszahl).

    The join between the two input formats and the priced reference data runs
    through this function, so there is exactly one canonical form:

        digits only, internal padding removed, hierarchy levels concatenated.

    D83 fixed-width gives `'0101   1'`; X83 gives the parts `('01', '01', '1')`.
    Both must collapse to the same key. Whitespace is dropped, not zero-padded —
    see PLAN.md "The three OZ layouts" for why per-file field widths make
    zero-padding unsafe as a global rule.
    """
    return "".join(ch for ch in raw if ch.isdigit())


@dataclass
class NormalizedItem:
    """One priceable line of a bill of quantities (Leistungsverzeichnis)."""

    oz: str
    quantity: float
    unit: str
    short_text: str = ""
    long_text: str = ""
    is_lump_sum: bool = False

    # Only present on priced files (.D84/.D86). None on a blank tender.
    unit_price: Optional[float] = None
    total_price: Optional[float] = None

    # Provenance: which file and which record/element this came from. Keep this
    # populated — the validation report cites it when a position disagrees.
    source_file: str = ""
    source_ref: str = ""

    def key(self) -> str:
        """Join key. Use this, never the list index (the 248/249 gap)."""
        return normalize_oz(self.oz)

    def comparable(self) -> tuple:
        """The tuple the twin-pair gate asserts on. Text is deliberately out."""
        return (self.key(), round(self.quantity, 3), self.unit.strip().lower())


@dataclass
class Finding:
    """One detector hit, as rendered in the UI and the RFI export."""

    item: NormalizedItem
    detector: str          # "unit_price_outlier" | "vague_scope" | "qty_sanity"
    severity: str          # "high" | "medium" | "low"
    rationale: str         # plain-English why, shown next to the row
    euro_leverage: float = 0.0   # quantity x price exposure; the ranking value
    evidence: dict = field(default_factory=dict)
