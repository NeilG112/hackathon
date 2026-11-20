"""Three detectors. Not five.

STATUS: stub — owned by task 004.

Each detector is a pure function `(priced_items, context) -> list[Finding]`.
No I/O, no Streamlit, no printing — they are driven from a script first and the
UI later. Findings are ranked by euro leverage (quantity x price exposure) and
the top ~20 are shown.
"""

from __future__ import annotations

from typing import Sequence

from core.models import Finding, NormalizedItem
from core.pricer import PricedItem


def unit_price_outlier(priced: Sequence[PricedItem]) -> list[Finding]:
    """Detector 1 — the speculative-price detector.

    Compares each observed/estimated unit price against the reference
    distribution for its (unit, bucket). Defensible because it runs against
    ~720 real same-trade items. Skip items with fewer than
    `constants.MIN_COMPARABLES` comparables rather than guessing.
    """
    raise NotImplementedError("task 004")


def vague_scope(
    priced: Sequence[PricedItem],
    remarks: Sequence[str] = (),
) -> list[Finding]:
    """Detector 2 — trigger words over item text *and* `<Remark>` text.

    The 46 Remark blocks (Vorbemerkungen) are where contract risk actually
    hides; they are not items, so the parsers exclude them and they arrive here
    separately. Terms live in `constants.VAGUE_SCOPE_TERMS`, mapped to the
    plain-English reason shown to the estimator.
    """
    raise NotImplementedError("task 004")


def quantity_sanity(priced: Sequence[PricedItem]) -> list[Finding]:
    """Detector 3 — unit mismatches, suspicious round numbers, provisional share.

    Three sub-checks, see `constants.UNIT_EXPECTED_BY_KEYWORD`,
    `SUSPICIOUS_ROUND_QUANTITIES`, `PROVISIONAL_SHARE_WARN_PCT`.
    """
    raise NotImplementedError("task 004")


def euro_leverage(item: NormalizedItem, unit_price: float | None) -> float:
    """Quantity x price exposure. The single ranking number."""
    raise NotImplementedError("task 004")


def run_all(
    priced: Sequence[PricedItem],
    remarks: Sequence[str] = (),
    top_n: int | None = None,
) -> list[Finding]:
    """Run the three detectors, dedupe per item, rank by euro leverage."""
    raise NotImplementedError("task 004")
