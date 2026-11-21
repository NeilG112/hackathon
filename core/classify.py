"""Position text -> Leistung code. The one job a model is actually good at.

The pricing engine needs to know *what kind of work* a position describes; the
rate table then supplies the hours and the money. Splitting it this way is
deliberate and it is what makes the system defensible:

    classify (hard, fuzzy, language)   -> a model
    price    (easy, exact, arithmetic) -> a lookup

A model asked "how many hours does this take?" produces a plausible number
nobody can check. A model asked "is this Oberboden abtragen or Rohrgraben
aushaeben?" produces an answer that is right or wrong, measurably, against the
106 labelled positions in `Database/`. And because the price then comes from a
table, the same tender always yields the same bid.

Three backends behind one interface:

    cache    on-disk, keyed by text+unit. Checked first, always.
    jev      TypeSafe's classifier: structured label + confidence, cheap.
    keyword  deterministic token overlap. No network, no key, no cost.

`classify()` walks them in that order, so a cold run with no key still works
and a warm run costs nothing. **Pre-generate the cache and commit it** — a
live API call during a demo is a failure mode with no upside.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from core.models import NormalizedItem
from core.stammdaten import Leistung, Stammdaten

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "classification_cache.json",
)

MIN_KEYWORD_SCORE = 0.12     # below this the keyword match is noise
MIN_JEV_CONFIDENCE = 0.35    # below this we would rather say nothing

_STOP = frozenset("""
und oder mit ohne nach vor bis je der die das den dem des ein eine einer
liefern lieferung einbauen herstellen inkl incl einschl gemaess gemäß
""".split())


@dataclass
class Assignment:
    code: Optional[str]
    confidence: float
    source: str          # "cache" | "jev" | "keyword" | "none"
    alternatives: list = None

    def as_tuple(self) -> tuple[Optional[str], float]:
        return (self.code, self.confidence)


# --- shared helpers --------------------------------------------------------

def tokens(text: str) -> frozenset[str]:
    low = re.sub(r"\[?\b(?:person|firma|ort|projekt|nummer|telefon|per)[_0-9]*\]?",
                 " ", (text or "").lower())
    return frozenset(t for t in re.findall(r"[a-zäöüß]{4,}", low) if t not in _STOP)


def fingerprint(item: NormalizedItem, unit: str) -> str:
    """Cache key: the text and unit decide the class, nothing else does."""
    raw = f"{item.short_text}|{item.long_text[:400]}|{unit}".lower()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def candidates(unit: str, data: Stammdaten) -> list[Leistung]:
    """Work types measured in this unit — everything else is impossible.

    The unit is the single strongest signal in a bill of quantities and it is
    free. Restricting to it before any fuzzy matching removes most of the ways
    a classifier can be confidently wrong.
    """
    shortlist = data.by_unit(unit)
    return shortlist or list(data.leistungen.values())


# --- backend: keyword ------------------------------------------------------

def classify_keyword(item: NormalizedItem, data: Stammdaten, unit: str) -> Assignment:
    """Token overlap against each candidate's Taetigkeit and Bemerkung.

    The deterministic floor. It has no domain knowledge and will never beat a
    real classifier, but it costs nothing, runs offline, and makes the whole
    system work with no API key at all.
    """
    item_tokens = tokens(f"{item.short_text} {item.long_text[:400]}")
    if not item_tokens:
        return Assignment(None, 0.0, "none")

    scored = []
    for leistung in candidates(unit, data):
        ref = tokens(f"{leistung.taetigkeit} {leistung.bemerkung} {leistung.gewerk}")
        if not ref:
            continue
        overlap = len(item_tokens & ref)
        if not overlap:
            continue
        scored.append((overlap / len(item_tokens | ref), leistung.code))

    if not scored:
        return Assignment(None, 0.0, "none")
    scored.sort(reverse=True)
    best_score, best_code = scored[0]
    if best_score < MIN_KEYWORD_SCORE:
        return Assignment(None, round(best_score, 3), "none",
                          [c for _, c in scored[:3]])
    return Assignment(best_code, round(best_score, 3), "keyword",
                      [c for _, c in scored[:3]])


# --- backend: Jev ----------------------------------------------------------

def jev_available() -> bool:
    return bool(os.getenv("JEV_KEY") or os.getenv("JEV_API_KEY"))


def classify_jev(
    item: NormalizedItem,
    data: Stammdaten,
    unit: str,
    timeout: float = 20.0,
) -> Assignment:
    """Ask Jev to pick a Leistung code from the shortlist.

    Jev returns a structured value plus a confidence, which is exactly the
    shape this problem wants: a label we can join to the rate table, and a
    number telling us when not to trust it. Any failure returns an empty
    assignment so the caller falls through to the keyword backend — a
    classifier outage must never take the estimate down.
    """
    import urllib.error
    import urllib.request

    key = os.getenv("JEV_KEY") or os.getenv("JEV_API_KEY")
    if not key:
        return Assignment(None, 0.0, "none")

    shortlist = candidates(unit, data)
    menu = "\n".join(f"{l.code}: {l.taetigkeit} [{l.einheit}]" for l in shortlist)
    payload = {
        "input": (
            "Ordne die folgende Position aus einem deutschen Leistungsverzeichnis "
            "genau einer Leistung zu. Antworte nur mit dem Code.\n\n"
            f"POSITION ({unit}): {item.short_text}\n{item.long_text[:400]}\n\n"
            f"MÖGLICHE LEISTUNGEN:\n{menu}"
        ),
        "schema": {"leistung_code": "string", "score": "number"},
    }
    request = urllib.request.Request(
        os.getenv("JEV_URL", "https://api.jevai.net/v1/decide"),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception:                                       # noqa: BLE001
        return Assignment(None, 0.0, "none")

    code = str(body.get("leistung_code") or "").strip().upper()
    confidence = float(body.get("confidence") or body.get("score") or 0.0)
    if code not in data.leistungen or confidence < MIN_JEV_CONFIDENCE:
        return Assignment(None, confidence, "none")
    return Assignment(code, round(confidence, 3), "jev")


# --- cache -----------------------------------------------------------------

def load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=1, sort_keys=True)


# --- the interface ---------------------------------------------------------

def classify(
    items: Iterable[NormalizedItem],
    data: Stammdaten,
    use_jev: bool = False,
    write_cache: bool = True,
) -> dict[str, tuple]:
    """Assign a Leistung code to every position. `{oz_key: (code, confidence)}`.

    `use_jev` is opt-in on purpose: the demo path should run from the cache.
    """
    from core import constants

    cache = load_cache()
    out: dict[str, tuple] = {}
    dirty = False

    for item in items:
        unit = constants.normalize_unit(item.unit)
        key = fingerprint(item, unit)

        hit = cache.get(key)
        if hit:
            out[item.key()] = (hit.get("code"), float(hit.get("confidence", 0.0)))
            continue

        assignment = Assignment(None, 0.0, "none")
        if use_jev and jev_available():
            assignment = classify_jev(item, data, unit)
        if assignment.code is None:
            assignment = classify_keyword(item, data, unit)

        out[item.key()] = assignment.as_tuple()
        cache[key] = {"code": assignment.code,
                      "confidence": assignment.confidence,
                      "source": assignment.source,
                      "text": item.short_text[:90]}
        dirty = True

    if dirty and write_cache:
        save_cache(cache)
    return out


def coverage(assignments: dict) -> dict:
    total = len(assignments)
    hit = sum(1 for code, _ in assignments.values() if code)
    return {"positions": total, "classified": hit,
            "unclassified": total - hit,
            "pct": round(100.0 * hit / total, 1) if total else 0.0}
