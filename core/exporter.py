"""Hand the priced tender back: GAEB X84 and CSV.

The client's own words: *"Dieses LV wollen wir hochladen und am Ende das
Angebot rausbekommen."* A PDF of our screen is not that. An X84 is the file
his procurement system actually imports.

X84 is the bid-submission counterpart to the X83 tender: same document,
same Ordnungszahlen, with `UP` (Einheitspreis) and `IT` (Gesamtbetrag) filled
in. So the export does not build a document — it takes the X83 that was
uploaded, stamps `DP` to 84, and writes the prices into the positions that
are already there. Anything we did not price keeps its empty price field,
which is a legitimate state in a bid and better than a fabricated number.

**Positions are matched on the normalised OZ, never on list order.** A
sequential fallback looks like it works and silently puts the price of
position 7 onto position 8 as soon as one item is skipped. `export_x84`
returns the list of unmatched OZ so the caller can show it instead of
shipping a quietly wrong bid.
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from typing import Iterable, Sequence

from core import constants
from core.models import normalize_oz

X84_NAMESPACE = "http://www.gaeb.de/GAEB_DA_XML/DA84/3.2"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _child_text(element: ET.Element, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for child in element.iter():
        if child is element:
            continue
        if _local(child.tag).lower() in wanted:
            text = " ".join(child.itertext()).strip()
            if text:
                return text
    return ""


def _item_oz(element: ET.Element, parents: dict) -> str:
    """The OZ of a source `<Item>`, composed exactly as the parser does."""
    parts: list[str] = []
    cursor = element
    while cursor is not None:
        parent = parents.get(cursor)
        if parent is None:
            break
        if _local(parent.tag) == "BoQCtgy":
            rno = parent.attrib.get("RNoPart")
            if rno:
                parts.append(rno)
        cursor = parent
    parts.reverse()
    own = element.attrib.get("RNoPart") or _child_text(element, "RNoPart", "BoQNo")
    if own:
        parts.append(own)
    return normalize_oz("".join(parts))


def export_x84(source_path: str, calculated: Iterable) -> tuple[bytes, dict]:
    """Write the prices into a copy of the uploaded X83 and return it as X84.

    Returns `(xml_bytes, report)`. The report names every position that could
    not be matched or had no price — read it before sending the file.
    """
    tree = ET.parse(source_path)
    root = tree.getroot()

    # ElementTree elements reject arbitrary attributes in the C build, so the
    # parent links live in a dict — same approach as parser_x83._parent_map.
    parents = {child: parent for parent in root.iter() for child in parent}

    priced_by_oz = {}
    for entry in calculated:
        if entry.priced and entry.ep_mid is not None:
            priced_by_oz[entry.item.key()] = entry

    ET.register_namespace("", X84_NAMESPACE)
    prefix = f"{{{X84_NAMESPACE}}}"
    for element in root.iter():
        element.tag = prefix + _local(element.tag)

    # DP identifies the exchange phase: 83 is the tender, 84 the bid.
    for element in root.iter():
        if _local(element.tag).lower() == "dp":
            element.text = "84"

    written, unmatched, unpriced = 0, [], []
    for element in root.iter():
        if _local(element.tag) != "Item":
            continue
        oz = _item_oz(element, parents)
        entry = priced_by_oz.pop(oz, None)
        if entry is None:
            unmatched.append(oz or "(ohne OZ)")
            continue
        if entry.ep_mid is None:
            unpriced.append(oz)
            continue

        unit_price = element.find(f"{prefix}UP")
        if unit_price is None:
            unit_price = ET.SubElement(element, f"{prefix}UP")
        item_total = element.find(f"{prefix}IT")
        if item_total is None:
            item_total = ET.SubElement(element, f"{prefix}IT")
        unit_price.text = f"{entry.ep_mid:.2f}"
        item_total.text = f"{(entry.total or 0.0):.2f}"
        written += 1

    buffer = io.BytesIO()
    tree.write(buffer, encoding="utf-8", xml_declaration=True)
    report = {
        "written": written,
        "unmatched_in_file": len(unmatched),
        "unmatched_examples": unmatched[:8],
        "priced_but_not_in_file": sorted(priced_by_oz)[:8],
        "complete": not unmatched and not priced_by_oz,
    }
    return buffer.getvalue(), report


CSV_COLUMNS = (
    "OZ", "Kurztext", "Menge", "Einheit", "Leistung",
    "Lohn_EUR_je_Einheit", "Geraet_EUR_je_Einheit", "Material_EUR_je_Einheit",
    "EKT_EUR_je_Einheit", "EP_min", "EP_mittel", "EP_max", "GP_EUR",
)


def export_csv(calculated: Iterable, delimiter: str = ";") -> bytes:
    """The priced tender as CSV, in a shape Excel opens without a wizard.

    Semicolon-separated and comma-decimal, because that is what a German
    Excel expects; a comma-separated file with dots opens as one column per
    row and the estimator concludes the export is broken.
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)

    def number(value) -> str:
        if value is None:
            return ""
        return f"{value:.2f}".replace(".", ",")

    for entry in calculated:
        breakdown = entry.breakdown
        writer.writerow([
            getattr(entry.item, "display_oz", entry.item.oz),
            entry.item.short_text,
            f"{entry.item.quantity:.3f}".replace(".", ","),
            constants.normalize_unit(entry.item.unit),
            entry.leistung.code if entry.leistung else "",
            number(breakdown.labour_eur if entry.priced else None),
            number(breakdown.machine_eur if entry.priced else None),
            number(breakdown.material_eur if entry.priced else None),
            number(breakdown.ekt if entry.priced else None),
            number(entry.ep_low), number(entry.ep_mid), number(entry.ep_high),
            number(entry.total),
        ])
    # BOM so Excel detects UTF-8 and the umlauts survive.
    return output.getvalue().encode("utf-8-sig")


def summarize(calculated: Sequence) -> dict:
    priced = [c for c in calculated if c.priced]
    return {
        "positions": len(calculated),
        "priced": len(priced),
        "total": round(sum(c.total or 0.0 for c in priced), 2),
    }
