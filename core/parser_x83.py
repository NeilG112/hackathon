"""GAEB XML (.X83 / .x83) parser.

Verified facts this implementation rests on (checked against Dataset/):

- **Namespace-agnostic.** Two namespaces appear in Dataset/
  (`.../DA83/3.2` and `.../GAEB_DA_XML/200407`). Everything here matches on the
  tag after `}` only. A 3.2-keyed XPath silently returns zero nodes on the
  296-item file — that failure mode is silent, which is why there is no
  namespace URI anywhere in this module.
- **`RNoPart` is an attribute, not an element.** On both `<Item>` and
  `<BoQCtgy>`. (PLAN.md describes it as a nested element; that is wrong.) A
  naive `text.count("<Item>")` also returns 0 because of the attributes — use
  a real parser.
- **The OZ is composed, not stored flat.** Ancestor chain of an `<Item>` is
  `Itemlist <- BoQBody <- BoQCtgy <- BoQBody <- BoQCtgy <- BoQ <- Award <- GAEB`.
  Each `BoQCtgy` carries its own `RNoPart` (`'01'`). Compose outermost ->
  innermost, then append the item's own `RNoPart`: `'01'+'01'+'1'`, which must
  match the D83 OZ `'0101   1'` after `models.normalize_oz`.
- `<Remark>` blocks are **not** items (the 296-item file has 46 of them). They
  are excluded from `parse` and returned separately by `parse_remarks` — they
  are where contract risk hides, and the vague-scope detector wants them.
- Item text is HTML-wrapped (`<span>`, `<p>`, `<li>`, `<br>`) inside `<Text>`.
  In these files the wrapper is parsed as real child elements, so text is
  gathered with `itertext()` and then normalized by `utils.text_cleaning`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from core.models import NormalizedItem
from utils.text_cleaning import clean_item_text, short_text

ITEM_TAG = "Item"
CATEGORY_TAG = "BoQCtgy"
REMARK_TAG = "Remark"


def local_name(tag: str) -> str:
    """`'{http://...}Item'` -> `'Item'`. The only namespace handling we do."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _parent_map(root: ET.Element) -> Dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def _child(el: ET.Element, name: str) -> Optional[ET.Element]:
    for c in el:
        if local_name(c.tag) == name:
            return c
    return None


def _text_of(el: Optional[ET.Element]) -> str:
    """All descendant text of an element, HTML wrapper flattened."""
    if el is None:
        return ""
    return clean_item_text("".join(el.itertext()))


def _find_descendant(el: ET.Element, name: str) -> Optional[ET.Element]:
    for d in el.iter():
        if d is not el and local_name(d.tag) == name:
            return d
    return None


def oz_parts(item: ET.Element, parents: Dict[ET.Element, ET.Element]) -> tuple[str, ...]:
    """The OZ hierarchy levels, outermost -> innermost, exactly as stored.

    Kept separately from the composed string because the padding is *not*
    consistent across files: the 8209 twin pair stores `('01','01','1')` while
    `[NUMMER_001]_leer.X83` stores `('1','1','1')` for the same shape of BoQ.
    `NormalizedItem.padded_key` needs the levels to re-pad them for a join.
    """
    parts: List[str] = []
    cursor: Optional[ET.Element] = item
    while cursor in parents:
        cursor = parents[cursor]
        if local_name(cursor.tag) == CATEGORY_TAG:
            rno = cursor.attrib.get("RNoPart")
            if rno:
                parts.append(rno)
    parts.reverse()
    own = item.attrib.get("RNoPart")
    if own:
        parts.append(own)
    return tuple(parts)


def compose_oz(item: ET.Element, parents: Dict[ET.Element, ET.Element]) -> str:
    """Build the raw OZ by walking the `RNoPart` chain outermost -> innermost."""
    return "".join(oz_parts(item, parents))


LABEL_TAGS = ("LblTx", "OutlineText", "Label", "Description")
# A category's label lives in its own direct children; `BoQBody` holds the
# child categories and items. Searching the whole subtree picks up the first
# *position's* description instead and silently labels every section with the
# name of one of its line items.
BODY_TAGS = ("BoQBody", "Itemlist")


def section_path(item: ET.Element, parents: Dict[ET.Element, ET.Element]) -> tuple[str, ...]:
    """Labels of the `BoQCtgy` ancestors, outermost -> innermost.

    These carry the construction section — "Tiefbau Ost - Haupttrasse 2023",
    "BA 01 + BA 02", "[ORT_030]" — which is the location key the inconsistency
    engine groups on. Falls back to the category's RNoPart when a node has no
    readable label, so the path never silently collapses.
    """
    labels: List[str] = []
    cursor: Optional[ET.Element] = item
    while cursor in parents:
        cursor = parents[cursor]
        if local_name(cursor.tag) != CATEGORY_TAG:
            continue
        label_scope = [c for c in cursor if local_name(c.tag) not in BODY_TAGS]
        text = ""
        for tag in LABEL_TAGS:
            for child in label_scope:
                found = child if local_name(child.tag) == tag else _find_descendant(child, tag)
                text = _text_of(found)
                if text:
                    break
            if text:
                break
        labels.append(text[:70] or f"Abschnitt {cursor.attrib.get('RNoPart', '?')}")
    labels.reverse()
    return tuple(labels)


def _quantity(item: ET.Element) -> float:
    raw = (getattr(_child(item, "Qty"), "text", "") or "").strip()
    if not raw:
        return 0.0
    try:
        # Already decimal-formatted in this format ('1.000'), unlike GAEB 90.
        return float(raw.replace(",", "."))
    except ValueError:
        return 0.0


def parse(path: str) -> List[NormalizedItem]:
    """Parse a GAEB XML file into normalized items, in document order.

    Returns 159 items for `Dataset/8209.003_Leistungsverzeichnis_leer.X83`.
    """
    root = ET.parse(path).getroot()
    parents = _parent_map(root)

    items: List[NormalizedItem] = []
    for el in root.iter():
        if local_name(el.tag) != ITEM_TAG:
            continue

        description = _child(el, "Description")
        outline = (
            _find_descendant(description, "OutlineText")
            if description is not None
            else None
        )
        complete = (
            _find_descendant(description, "CompleteText")
            if description is not None
            else None
        )

        long = _text_of(complete)
        items.append(
            NormalizedItem(
                oz=compose_oz(el, parents),
                oz_parts=oz_parts(el, parents),
                section_path=section_path(el, parents),
                quantity=_quantity(el),
                unit=(getattr(_child(el, "QU"), "text", "") or "").strip(),
                short_text=_text_of(outline) or short_text(long),
                long_text=long,
                is_lump_sum=(getattr(_child(el, "LumpSumItem"), "text", "") or "")
                .strip()
                .lower() in ("yes", "ja", "true", "1"),
                source_file=path,
                source_ref=el.attrib.get("ID", ""),
            )
        )
    return items


def parse_remarks(path: str) -> List[str]:
    """The `<Remark>` texts — contract preamble, not priceable items.

    Kept out of `parse` deliberately (they are not items and would corrupt the
    item count), but handed to the vague-scope detector, which PLAN.md expects
    to find its highest-value hits in here.
    """
    root = ET.parse(path).getroot()
    out: List[str] = []
    for el in root.iter():
        if local_name(el.tag) == REMARK_TAG:
            text = _text_of(el)
            if text:
                out.append(text)
    return out
