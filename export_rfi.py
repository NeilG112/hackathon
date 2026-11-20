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

from typing import Sequence

from core.models import Finding

TEMPLATES_PATH = "data/rfi_templates.json"


def question_for(finding: Finding) -> str:
    """Render one Bieterfrage from a finding, in VOB-correct German.

    Template chosen by `finding.detector`; slots filled from the item (OZ,
    Kurztext, Menge, Einheit) and the finding's evidence.
    """
    raise NotImplementedError("task 006")


def build_catalog(findings: Sequence[Finding], project: dict) -> list[dict]:
    """Ordered, de-duplicated question list with OZ references."""
    raise NotImplementedError("task 006")


def to_docx(catalog: Sequence[dict], out_path: str, project: dict) -> str:
    """Write the .docx (python-docx). Returns the path written."""
    raise NotImplementedError("task 006")


def to_markdown(catalog: Sequence[dict], project: dict) -> str:
    """Fallback renderer. Must work with stdlib only, in case docx fails live."""
    raise NotImplementedError("task 006")
