#!/usr/bin/env python3
"""Bieterfragen-Katalog export -> .docx. Task 006.

Turns ranked findings into the formal clarification letter the estimator would
otherwise spend four hours writing. The German goes HERE, in the artifact, with
correct VOB phrasing. The narration elsewhere stays plain English.

**No live LLM in the demo path.** RFI texts are pre-written templates with
slots; pre-generate, cache to `data/rfi_templates.json`, ship the JSON. If you
want model-generated phrasings, generate them offline and commit the result.
"""

from __future__ import annotations

import json
import os
from typing import Sequence

from core.constants import normalize_unit
from core.models import Finding

TEMPLATES_PATH = os.path.join(
    os.path.dirname(__file__), "data", "rfi_templates.json"
)


def _load_templates() -> dict:
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _format_quantity(quantity: float) -> str:
    if quantity is None:
        return ""
    value = float(quantity)
    if value.is_integer():
        return f"{int(value):,}".replace(",", ".")
    return f"{value:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _item_text(item) -> str:
    text = item.short_text.strip() if item.short_text else ""
    return text or (item.long_text.strip() if item.long_text else "") or "Kurztext liegt nicht vor"


def question_for(finding: Finding) -> str:
    """Render one Bieterfrage from a finding, in VOB-correct German.

    Template chosen by `finding.detector`; slots filled from the item (OZ,
    Kurztext, Menge, Einheit) and the finding's evidence.
    """
    templates = _load_templates()
    template = templates.get(finding.detector, templates["qty_sanity"])
    values = {
        "oz": finding.item.key() or "ohne OZ",
        "kurztext": _item_text(finding.item),
        "menge": _format_quantity(finding.item.quantity),
        "einheit": normalize_unit(finding.item.unit) or "—",
    }
    return template["question"].format(**values)


def build_catalog(findings: Sequence[Finding], project: dict) -> list[dict]:
    """Ordered, de-duplicated question list with OZ references."""
    catalog = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        oz = finding.item.key() or "ohne OZ"
        key = (oz, finding.detector)
        if key in seen:
            continue
        seen.add(key)
        catalog.append({
            "nr": len(catalog) + 1,
            "oz": oz,
            "kurztext": _item_text(finding.item),
            "menge": _format_quantity(finding.item.quantity),
            "einheit": normalize_unit(finding.item.unit) or "—",
            "detector": finding.detector,
            "severity": finding.severity,
            "euro_leverage": round(finding.euro_leverage, 2),
            "frage": question_for(finding),
        })
    return catalog


def to_docx(catalog: Sequence[dict], out_path: str, project: dict) -> str:
    """Write the .docx (python-docx). Returns the path written."""
    try:
        from docx import Document
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Cm
    except ImportError as exc:
        raise RuntimeError("python-docx is not available") from exc

    title = project.get("title") or "Bieterfragen-Katalog"
    document = Document()
    heading = document.add_heading(title, level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph(
        "Im nachstehenden Bieterfragen-Katalog werden Rückfragen zu den "
        "ausgewiesenen Leistungspositionen zusammengestellt."
    )

    table = document.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths = (Cm(1.0), Cm(2.5), Cm(7.0), Cm(2.0), Cm(1.8), Cm(5.0))
    headers = ("Nr.", "OZ", "Kurztext", "Menge", "Einheit", "Bieterfrage")
    for cell, header, width in zip(table.rows[0].cells, headers, widths):
        cell.text = header
        cell.width = width

    for entry in catalog:
        cells = table.add_row().cells
        values = (
            str(entry["nr"]),
            entry["oz"],
            entry["kurztext"],
            entry["menge"],
            entry["einheit"],
            entry["frage"],
        )
        for cell, value, width in zip(cells, values, widths):
            cell.text = str(value)
            cell.width = width

    document.save(out_path)
    return out_path


def to_markdown(catalog: Sequence[dict], project: dict) -> str:
    """Fallback renderer. Must work with stdlib only, in case docx fails live."""
    title = project.get("title") or "Bieterfragen-Katalog"
    lines = [
        f"# {title}",
        "",
        "Im nachstehenden Bieterfragen-Katalog werden Rückfragen zu den "
        "ausgewiesenen Leistungspositionen zusammengestellt.",
        "",
        "| Nr. | OZ | Kurztext | Menge | Einheit | Bieterfrage |",
        "|---:|:---|:---|---:|:---|:---|",
    ]
    for entry in catalog:
        def clean(value) -> str:
            return str(value).replace("|", "\\|").replace("\n", " ")

        lines.append(
            "| {nr} | {oz} | {kurztext} | {menge} | {einheit} | {frage} |".format(
                nr=clean(entry["nr"]),
                oz=clean(entry["oz"]),
                kurztext=clean(entry["kurztext"]),
                menge=clean(entry["menge"]),
                einheit=clean(entry["einheit"]),
                frage=clean(entry["frage"]),
            )
        )
    return "\n".join(lines) + "\n"
