#!/usr/bin/env python3
"""Bieterfragen-Katalog export -> .docx. Task 006.

Turns ranked findings into the formal clarification letter the estimator would
otherwise spend four hours writing. The German goes HERE, in the artifact, with
correct VOB phrasing. The narration elsewhere stays plain English.

The exporter itself makes no LLM calls. Position questions use the templates
unless the risk pipeline supplies a cached, position-specific question.
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

    Prefer an upstream position-specific question; otherwise use the template
    chosen by `finding.detector` and fill it from the finding's item.
    """
    generated_question = finding.evidence.get("bidder_question_de")
    if isinstance(generated_question, str) and generated_question.strip():
        return generated_question.strip()

    templates = _load_templates()
    template = templates.get(finding.detector, templates["qty_sanity"])
    values = {
        "oz": finding.item.display_oz or "ohne OZ",
        "kurztext": _item_text(finding.item),
        "menge": _format_quantity(finding.item.quantity),
        "einheit": normalize_unit(finding.item.unit) or "—",
    }
    return template["question"].format(**values)


def questions_from_clusters(evaluations) -> list[dict]:
    """Convert cluster evaluations into RFI catalogue entries."""
    entries = evaluations.items() if hasattr(evaluations, "items") else ()
    if isinstance(evaluations, (list, tuple)):
        entries = enumerate(evaluations)

    catalog = []
    for key, evaluation in entries:
        if hasattr(evaluation, "as_dict"):
            raw = evaluation.as_dict()
        elif isinstance(evaluation, dict):
            raw = dict(evaluation)
        else:
            continue

        if raw.get("contradiction_category") in (None, "", "NONE"):
            continue
        if raw.get("offline") is True:
            continue

        cluster_id = str(key)
        cluster_title = str(
            raw.get("cluster_title")
            or raw.get("title")
            or cluster_id
        )
        affected = raw.get("affected_ozs")
        if affected is None:
            affected = raw.get("affected_positions")
        if affected is None:
            affected = raw.get("positions")
        affected = list(affected or [])
        oz_text = ", ".join(affected) if affected else "Cluster"
        category = str(raw.get("contradiction_category") or "CLUSTER")
        reason = str(
            raw.get("reason_de")
            or raw.get("engineering_analysis")
            or raw.get("rationale")
            or "Der Cluster-Widerspruch ist zu klaeren."
        )
        exposure = float(
            raw.get("euro_exposure_estimate")
            or raw.get("euro_exposure")
            or raw.get("euro_leverage")
            or 0.0
        )
        din_ref = str(raw.get("din_ref") or "")

        catalog.append({
            "nr": 0,
            "oz": oz_text,
            "kurztext": cluster_title,
            "menge": "",
            "einheit": "Cluster",
            "detector": f"cluster_{category.lower()}",
            "severity": str(raw.get("severity") or "high"),
            "euro_leverage": round(exposure, 2),
            "frage": reason,
            "cluster_title": cluster_title,
            "din_ref": din_ref,
            "affected_ozs": affected,
            "group": "cluster",
        })

    catalog.sort(key=lambda entry: (-entry["euro_leverage"], entry["cluster_title"]))
    for index, entry in enumerate(catalog, start=1):
        entry["nr"] = index
    return catalog


def build_catalog(
    findings: Sequence[Finding],
    project: dict,
    cluster_evaluations=None,
) -> list[dict]:
    """Ordered, de-duplicated question list with cluster questions first."""
    catalog = []
    if cluster_evaluations:
        cluster_catalog = questions_from_clusters(cluster_evaluations)
        catalog.extend(cluster_catalog)

    seen: set[tuple[str, str]] = set()
    for finding in findings:
        oz = finding.item.display_oz or "ohne OZ"
        key = (finding.item.key(), finding.detector)
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
            "cluster_title": "",
            "din_ref": "",
            "affected_ozs": [oz],
            "group": "position",
        })
    for index, entry in enumerate(catalog, start=1):
        entry["nr"] = index
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

    cluster_entries = [
        entry for entry in catalog
        if entry.get("group") == "cluster"
    ]
    position_entries = [
        entry for entry in catalog
        if entry.get("group") != "cluster"
    ]
    widths = (Cm(1.0), Cm(2.5), Cm(7.0), Cm(2.0), Cm(1.8), Cm(5.0))
    headers = ("Nr.", "OZ", "Kurztext", "Menge", "Einheit", "Bieterfrage")

    def render_group(group_title: str, entries: Sequence[dict]) -> None:
        if not entries:
            return
        document.add_heading(group_title, level=2)
        table = document.add_table(rows=1, cols=6)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for cell, header, width in zip(table.rows[0].cells, headers, widths):
            cell.text = header
            cell.width = width
        for entry in entries:
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

    render_group("Fragen zu Bauabschnitten", cluster_entries)
    render_group("Fragen zu Einzelpositionen", position_entries)

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
    ]
    cluster_entries = [
        entry for entry in catalog
        if entry.get("group") == "cluster"
    ]
    position_entries = [
        entry for entry in catalog
        if entry.get("group") != "cluster"
    ]

    def render_group(group_title: str, entries: Sequence[dict]) -> None:
        if not entries:
            return
        lines.extend([
            f"## {group_title}",
            "",
            "| Nr. | OZ | Kurztext | Menge | Einheit | Bieterfrage |",
            "|---:|:---|:---|---:|:---|:---|",
        ])
        for entry in entries:
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
        lines.append("")

    render_group("Fragen zu Bauabschnitten", cluster_entries)
    render_group("Fragen zu Einzelpositionen", position_entries)
    return "\n".join(lines) + "\n"
