"""Keyword-based detection of construction domains present in a tender."""

from __future__ import annotations

import re
from collections.abc import Iterable

from core.models import NormalizedItem
from utils.text_cleaning import clean_item_text

DOMAIN_PATTERNS: dict[str, tuple[str, ...]] = {
    "TIEFBAU": (
        r"\btiefbau\b",
        r"\berdarbeiten\b",
        r"\bkanalbau\b",
        r"\bgraben(?:bau|arbeiten|verbau|aushub)?\b",
        r"\bleitungsgraben\w*\b",
        r"\bgrabenverbau\w*\b",
        r"\bgrabentiefe\b",
        r"\b(?:boden|erd|baugruben|graben)aushub\b",
        r"\baushub\b",
        r"\b(?:kanal)?schacht(?:abdeckung|bauwerk|entwaesserung|grube)\w*\b",
        r"\bwasserhaltung\b",
        r"\bverkehrssicherung\b",
        r"\bspundwand\b",
        r"\bverbau\b",
        r"\basphalt(?:bau)?\b",
        r"\boberboden\b",
    ),
    "HOCHBAU_ROHBAU": (
        r"\brohbau\b",
        r"\bmauerwerk\w*\b",
        r"\bstahlbeton\w*\b",
        r"\bschalung\w*\b",
        r"\bbewehrung\w*\b",
        r"\bbetonstahl\b",
        r"\bkalksandstein\w*\b",
        r"\bziegelmauerwerk\b",
        r"\bortbeton\b",
        r"\bbodenplatte\b",
        r"\bfundament\w*\b",
        r"\b(?:beton)?stuetze\w*\b",
        r"\berdberuehrt\w*\b",
        r"\bkellerabdichtung\b",
        r"\bperimeterdaemmung\b",
    ),
    "AUSBAU": (
        r"\bausbau\b",
        r"\btrockenbau\w*\b",
        r"\bgipskarton\w*\b",
        r"\bgipsfaser\w*\b",
        r"\bestrich\w*\b",
        r"\bbodenbelag\w*\b",
        r"\bfliesen\w*\b",
        r"\bmaler(?:arbeiten)?\b",
        r"\bspachtel(?:arbeiten)?\b",
        r"\btapeten?\b",
        r"\bparkett\w*\b",
        r"\binnenputz\w*\b",
        r"\binnentueren?\b",
    ),
    "TGA_ELEKTRO": (
        r"\belektro(?:technik|installation|arbeiten|anlage|anlagen)\b",
        r"\bkabel(?:verlegung|trasse|rinne)?\b",
        r"\bstromkreis\w*\b",
        r"\bunterverteilung\w*\b",
        r"\bverteilungen?\b",
        r"\bschaltschrank\w*\b",
        r"\bsicherungskasten\w*\b",
        r"\b(?:beleuchtung|leuchten?|steckdosen?|schalter)\b",
        r"\bvde\s*0100\b",
        r"\b400\s*v\b",
        r"\bknx\b",
        r"\bpotentialausgleich\b",
        r"\bbrandmeldeanlage\b",
        r"\berdung\b",
    ),
    "TGA_SHK": (
        r"\bshk\b",
        r"\bsanitaer\w*\b",
        r"\bheizungs?\w*\b",
        r"\bheizkreis\w*\b",
        r"\btrinkwasser\w*\b",
        r"\bwarmwasser\w*\b",
        r"\bkaltwasser\w*\b",
        r"\bkaelte\w*\b",
        r"\blueftung\w*\b",
        r"\blufttechnik\w*\b",
        r"\bwaermepumpe\w*\b",
        r"\bsprinkler\w*\b",
        r"\bvd[iI]\s*6023\b",
    ),
}


def _normalize(text: str) -> str:
    return (
        clean_item_text(text).lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def detect_lv_domains(
    items: Iterable[NormalizedItem],
    preambles: Iterable[str] | str | None,
) -> set[str]:
    """Detect domains from LV section titles, preambles, and position texts.

    An empty result means no domain had a clear signal; callers should still
    run rules marked ``COMMON``.
    """
    item_list = list(items)
    corpus = [
        _normalize(f"{item.short_text} {item.long_text}")
        for item in item_list
    ]
    corpus.extend(
        _normalize(" ".join(item.section_path))
        for item in item_list
        if item.section_path
    )
    if isinstance(preambles, str):
        preambles = (preambles,)
    corpus.extend(_normalize(str(preamble)) for preamble in preambles or ())
    lv_text = "\n".join(corpus)

    return {
        domain
        for domain, patterns in DOMAIN_PATTERNS.items()
        if any(re.search(pattern, lv_text) for pattern in patterns)
    }
