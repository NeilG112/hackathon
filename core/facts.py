"""Deterministische technische Faktextraktion fuer LV-Positionen."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from core.models import NormalizedItem
from core.objects import tag_of

Phase = Literal[
    "abbruch",
    "aushub",
    "vorbereitung",
    "rohbau",
    "montage",
    "verfuellung",
    "wiederherstellung",
    "pruefung",
    "vorhalten",
    "sonstiges",
]

# Deutsche Fachbegriffe gehoeren hierhin, damit sie ohne Kenntnis der
# Extraktionslogik erweitert werden koennen.
PHASE_TERMS: tuple[tuple[Phase, tuple[str, ...]], ...] = (
    ("pruefung", (
        "pruefung", "dichtheit", "druckpruefung", "spuelen",
        "desinfekt", "inbetriebnahme",
    )),
    ("vorhalten", ("vorhalten", "umsetzen", "miete")),
    ("abbruch", ("abbruch", "aufbrechen", "rueckbau", "demontage")),
    ("aushub", (
        "aushub", "ausheben", "loesen", "baggern", "graben herstellen",
    )),
    ("vorbereitung", ("bettung", "planum", "verbau", "schalung", "grundierung")),
    ("verfuellung", ("verfuell", "hinterfuell", "auffuell", "verdicht")),
    ("wiederherstellung", ("wiederherstell", "instandsetz", "decke schliessen")),
    ("montage", (
        "verlegen", "montieren", "einbauen", "setzen", "anschliessen",
        "verbaut", "verbauen",
    )),
    ("rohbau", ("beton", "mauerwerk", "bewehrung")),
)

MATERIAL_TERMS: tuple[str, ...] = (
    "PE100",
    "PE-HD",
    "PVC",
    "Guss",
    "GGG",
    "Stahl",
    "Beton",
    "Steinzeug",
    r"C\d{2}/\d{2}",
)

INCLUSIVE_MARKERS: tuple[str, ...] = (
    r"inkl\.",
    r"einschl\.",
    r"einschliesslich",
    r"eingerechnet",
    r"enthalten",
    r"nebenleistung",
)

DN_PATTERN = re.compile(r"DN[/\s]?(?:OD)?\s*(\d{2,4})", re.IGNORECASE)
PN_PATTERN = re.compile(r"PN\s*(\d{1,3})", re.IGNORECASE)
BAR_PATTERN = re.compile(r"(\d{1,3})\s*bar", re.IGNORECASE)
DEPTH_RANGE_PATTERN = re.compile(
    r"T\s*(\d+[,\.]\d+)\s*-\s*(\d+[,\.]\d+)\s*m",
    re.IGNORECASE,
)
DEPTH_SINGLE_PATTERN = re.compile(
    r"Tiefe\s*(?:bis\s*)?(\d+[,\.]\d+)\s*m",
    re.IGNORECASE,
)
DEPTH_H_PATTERN = re.compile(
    r"H\s*(\d+(?:[,\.]\d+)?)-(\d+(?:[,\.]\d+)?)m",
    re.IGNORECASE,
)
THICKNESS_PATTERN = re.compile(
    r"[Dd]\s*=?\s*(\d{1,3})\s*-?\s*(\d{1,3})?\s*cm",
    re.IGNORECASE,
)
MATERIAL_PATTERN = re.compile(
    "|".join(f"(?:{term})" for term in MATERIAL_TERMS),
    re.IGNORECASE,
)
INCLUSIVE_PATTERN = re.compile(
    "|".join(INCLUSIVE_MARKERS),
    re.IGNORECASE,
)


@dataclass
class PositionFacts:
    """Technische, deterministisch extrahierte Merkmale einer Position."""

    key: str
    object_tag: str
    phase: Phase
    dn: int | None
    pn: float | None
    depth_m: float | None
    thickness_cm: float | None
    material: str | None
    inclusive_terms: tuple[str, ...]
    confidence: float
    source: Literal["regex", "llm", "fallback"]

    def as_dict(self) -> dict:
        """JSON-safe Form der extrahierten Fakten."""
        return {
            "key": self.key,
            "object_tag": self.object_tag,
            "phase": self.phase,
            "dn": self.dn,
            "pn": self.pn,
            "depth_m": self.depth_m,
            "thickness_cm": self.thickness_cm,
            "material": self.material,
            "inclusive_terms": list(self.inclusive_terms),
            "confidence": self.confidence,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "PositionFacts":
        data = dict(raw)
        data["inclusive_terms"] = tuple(data.get("inclusive_terms") or ())
        return cls(**data)


def _decimal(raw: str) -> float:
    return float(raw.replace(",", "."))


def _extract_phase(text: str) -> Phase:
    low = (
        text.lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    for phase, terms in PHASE_TERMS:
        for term in terms:
            normalized_term = (
                term.replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace("ß", "ss")
            )
            pattern = normalized_term.replace(" ", r"\s+")
            if normalized_term == "verbau":
                if re.search(rf"{pattern}(?!t|en)", low):
                    return phase
            elif re.search(rf"{pattern}", low):
                return phase
    return "sonstiges"


def _extract_inclusive_terms(text: str) -> tuple[str, ...]:
    terms: list[str] = []
    for match in INCLUSIVE_PATTERN.finditer(text):
        segment = text[match.end():match.end() + 60]
        segment = segment.lstrip(" \t\r\n:;,-")
        segment = re.sub(r"\s+", " ", segment).strip(" \t\r\n.,;:")
        if segment:
            normalized = segment.lower()
            if normalized not in terms:
                terms.append(normalized)
    return tuple(terms)


def extract_facts(item: NormalizedItem) -> PositionFacts:
    """Extrahiert technische Merkmale aus Kurz- und Langtext."""
    text = f"{item.short_text} {item.long_text}".strip()

    dn: int | None = None
    dn_match = DN_PATTERN.search(text)
    if dn_match:
        dn = int(dn_match.group(1))

    pn: float | None = None
    pn_match = PN_PATTERN.search(text)
    if pn_match:
        pn = float(pn_match.group(1))
    else:
        bar_match = BAR_PATTERN.search(text)
        if bar_match:
            pn = float(bar_match.group(1))

    depth_m: float | None = None
    depth_match = DEPTH_RANGE_PATTERN.search(text)
    if depth_match:
        first = _decimal(depth_match.group(1))
        second = _decimal(depth_match.group(2))
        depth_m = (first + second) / 2.0
    else:
        depth_match = DEPTH_SINGLE_PATTERN.search(text)
        if depth_match:
            depth_m = _decimal(depth_match.group(1))
        else:
            depth_match = DEPTH_H_PATTERN.search(text)
            if depth_match:
                low = text.lower()
                bridge_context = any(
                    term in low
                    for term in ("bruecke", "brücke", "lichte höhe", "lichte hoehe")
                )
                trench_context = any(
                    term in low
                    for term in ("graben", "baugrube", "verbau")
                )
                if not bridge_context or trench_context:
                    first = _decimal(depth_match.group(1))
                    second = _decimal(depth_match.group(2))
                    depth_m = (first + second) / 2.0

    thickness_cm: float | None = None
    thickness_match = THICKNESS_PATTERN.search(text)
    if thickness_match:
        thickness_cm = float(thickness_match.group(1))

    material: str | None = None
    material_match = MATERIAL_PATTERN.search(text)
    if material_match:
        material = material_match.group(0)

    inclusive_terms = _extract_inclusive_terms(text)
    technical_found = any(
        value is not None
        for value in (dn, pn, depth_m, thickness_cm, material)
    )

    return PositionFacts(
        key=item.key(),
        object_tag=tag_of(item),
        phase=_extract_phase(text),
        dn=dn,
        pn=pn,
        depth_m=depth_m,
        thickness_cm=thickness_cm,
        material=material,
        inclusive_terms=inclusive_terms,
        confidence=1.0 if technical_found else 0.5,
        source="regex",
    )
