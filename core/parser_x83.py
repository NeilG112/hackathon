"""GAEB XML (.X83 / .x83) parser.

STATUS: stub — owned by task 001 (the gate).

Hard requirements, already verified against the dataset (PLAN.md):

- **Namespace-agnostic.** Two different namespaces appear in Dataset/
  (`DA83/3.2` and `GAEB_DA_XML/200407`). Match on the tag after `}` only.
  A 3.2-keyed XPath silently returns zero nodes on the 296-item file.
- **OZ is composed, not stored flat.** `RNoPart` is an *attribute* on both
  `<BoQCtgy>` and `<Item>`. Walk outermost -> innermost, append the item's own
  `RNoPart`, then pass through `models.normalize_oz`.
- `<Remark>` blocks are **not** items. 46 of them. Exclude from this list.
- Item text is HTML-wrapped inside `<Text>`; route it through
  `utils.text_cleaning.clean_item_text`.
"""

from __future__ import annotations

from typing import List

from core.models import NormalizedItem


def local_name(tag: str) -> str:
    """`'{http://...}Item'` -> `'Item'`. The only namespace handling we do."""
    return tag.rsplit("}", 1)[-1]


def parse(path: str) -> List[NormalizedItem]:
    """Parse a GAEB XML file into normalized items.

    Returns items in document order. Must return 159 items for
    `Dataset/8209.003_Leistungsverzeichnis_leer.X83`.
    """
    raise NotImplementedError("task 001")
