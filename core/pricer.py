"""Price a blank bill of quantities.

STATUS: stub — owned by task 003.

**The one inversion that matters (PLAN.md):** look up a real observed price
*first*, from `data/reference_prices.json` built out of the ~720 genuinely
priced items in the dataset. Fall back to `constants.FALLBACK_RATES_BY_UNIT`
only where no comparable exists — and return *which source was used* so the UI
can label it. Where there is no comparable at all, return `None` and let the UI
print `kein Vergleichswert`. An honest blank beats an invented euro.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Optional

from core.models import NormalizedItem

PriceSource = Literal["benchmark", "fallback_rate", "none"]


@dataclass
class PricedItem:
    item: NormalizedItem
    unit_price: Optional[float]
    total: Optional[float]
    source: PriceSource
    comparables: int = 0      # how many reference items backed this
    spread: Optional[float] = None   # p25..p75 of comparables, for the detector
    note: str = ""


def load_reference_prices(path: str | None = None) -> dict:
    """Load the benchmark distribution. Must not raise if the file is missing.

    Built by `scripts/build_reference_prices.py` (task 002) from the three
    usable priced files. Shape is that script's contract — medians per
    (unit, keyword bucket).
    """
    raise NotImplementedError("task 003")


def bucket_for(item: NormalizedItem) -> str:
    """Keyword bucket an item falls into (rohr / schacht / asphalt / ...).

    Keep this crude and legible. It is the join dimension for benchmarking and
    it will be read out loud in the demo.
    """
    raise NotImplementedError("task 003")


def price_item(item: NormalizedItem, reference: dict, company: dict) -> PricedItem:
    """Price one item. Benchmark first, labeled fallback second, else None."""
    raise NotImplementedError("task 003")


def price_boq(
    items: Iterable[NormalizedItem],
    reference: dict | None = None,
    company: dict | None = None,
) -> list[PricedItem]:
    """Price a whole BoQ. `company` defaults to `constants.DEFAULT_COMPANY`.

    The company dict is what the Streamlit sliders drive, so this must be cheap
    enough to re-run on every slider change (PLAN.md demo step 5).
    """
    raise NotImplementedError("task 003")
