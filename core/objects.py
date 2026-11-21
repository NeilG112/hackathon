"""The object table — the document compressed to what can be reasoned over.

A tender is 248 positions here and 9,000 on a real job. Neither a human nor a
model reasons well over that; at 9,000 the full text is ~1.3M tokens, past any
context window. But almost every cross-position question ("is there more floor
heating than floor slab?", "how much concrete does this project need?") is a
question about **aggregates**, not about individual lines.

So: tag each position with the physical object it acts on, then aggregate.
248 positions collapse to a few dozen rows. 9,000 would collapse to a few
hundred. That fits anywhere, and the estimator who sums thousands of rows by
hand to find out how much concrete he needs gets that answer for free.

Three rules this module exists to enforce:

**1. The key is (location, object, unit) — never object alone.** "300 m2 of
floor heating over 50 m2 of slab" is only a contradiction *within one section*.
Summed across a whole site, heating spread over twelve floors looks perfectly
fine and the finding vanishes. Aggregating globally does not make the signal
weaker, it deletes it.

**2. Units are part of the key, so nothing incommensurable is ever summed.**
You cannot add m2 to m3 to Stk to psch. Keying on the unit makes that a
structural impossibility rather than a bug waiting to happen.

**3. Every row keeps back-pointers to its positions.** A row the estimator
cannot drill into is a number he has no reason to believe. `ObjectRow.positions`
holds the OZ of every line that fed it.

The weak link is the tagger, and it is deliberately visible. `tag_of` is
keyword matching, which is measurably poor on this vocabulary (the rule
`rohr -> metres` holds 38% of the time on 720 real priced items). Positions
that do not match cleanly become `UNKNOWN_TAG` rather than being forced into a
bucket — a wrong tag does not produce a missing finding, it produces a
*confident false* one, which is far worse. This function is the seam where a
real classifier replaces the keywords.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from core import constants
from core.models import NormalizedItem

UNKNOWN_TAG = "unklar"

# Physical objects, not trades. Ordered most-specific first: a position
# mentioning both "Rohrgraben" and "Rohr" is about the trench, not the pipe.
# Each entry is (tag, required terms, disqualifying terms).
OBJECT_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("Leitungsgraben",  ("rohrgraben", "leitungsgraben", "kanalgraben", "graben"), ()),
    ("Grabenverbau",    ("verbau", "spundwand", "aussteifung"), ()),
    ("Bettung",         ("einbettung", "bettung", "kies-sand", "sandbett"), ()),
    ("Verfüllung",      ("verfüll", "wiederverfüll", "hinterfüll"), ()),
    ("Bodenaushub",     ("aushub", "boden lösen", "bodenaushub", "erdaushub"), ()),
    ("Rohrleitung",     ("rohr", "leitung", "ltg", "druckrohr"),
                        ("graben", "verbau", "bettung", "verfüll")),
    ("Schacht",         ("schacht", "schachtbauwerk"), ()),
    ("Armatur",         ("schieber", "kugelhahn", "hydrant", "armatur", "flansch"), ()),
    ("Asphalt",         ("asphalt", "tragschicht", "deckschicht"), ()),
    ("Pflaster",        ("pflaster", "bordstein", "randstein"), ()),
    ("Beton",           ("beton", "stahlbeton", "fundament"), ()),
    ("Bodenplatte",     ("bodenplatte", "sohlplatte"), ()),
    ("Bodenheizung",    ("bodenheizung", "fußbodenheizung", "heizestrich"), ()),
    ("Dämmung",         ("dämmung", "wärmedämmung", "isolierung"), ()),
    ("Baustelle",       ("baustelleneinrichtung", "bauzaun", "container",
                         "standplatz", "warnleuchte", "verkehrssicherung"), ()),
    ("Dokumentation",   ("dokumentation", "foto", "bestandsplan", "aufmaß"), ()),
    ("Stundenlohn",     ("stundenlohn", "facharbeiter", "bauwerker", "helfer"), ()),
)


@dataclass
class ObjectRow:
    """One (location, object, unit) cell of the aggregated tender."""

    location: str
    obj: str
    unit: str
    quantity: float = 0.0
    value: float = 0.0                       # euro exposure, if priced
    positions: list[str] = field(default_factory=list)   # OZ back-pointers

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.location, self.obj, self.unit)

    def label(self) -> str:
        return f"{self.obj} [{self.unit or '—'}] in {self.location}"


def tag_of(item: NormalizedItem) -> str:
    """Which physical object this position acts on.

    Keyword matching with disqualifiers, most-specific rule first. Returns
    `UNKNOWN_TAG` rather than guessing — see the module docstring on why a
    wrong tag is worse than no tag.

    **This is the swap point for a real classifier.** Replace the body, keep
    the signature, and everything downstream improves at once.
    """
    text = f"{item.short_text} {item.long_text}".lower()
    for tag, terms, blockers in OBJECT_RULES:
        if any(t in text for t in terms) and not any(b in text for b in blockers):
            return tag
    return UNKNOWN_TAG


def build(
    items: Iterable[NormalizedItem],
    priced: Sequence | None = None,
    depth: int = 2,
) -> list[ObjectRow]:
    """Aggregate positions into the object table.

    `priced` is an optional parallel sequence of `PricedItem` used only to
    attach euro exposure, so the table can be ranked by money. The table is
    built from quantities and is meaningful with no pricing at all.
    """
    totals: dict[tuple[str, str, str], ObjectRow] = {}
    value_by_oz = {}
    if priced:
        value_by_oz = {p.item.key(): (p.total or 0.0) for p in priced}

    for item in items:
        unit = constants.normalize_unit(item.unit)
        row_key = (item.location(depth), tag_of(item), unit)
        row = totals.get(row_key)
        if row is None:
            row = ObjectRow(location=row_key[0], obj=row_key[1], unit=row_key[2])
            totals[row_key] = row
        row.quantity += item.quantity
        row.value += value_by_oz.get(item.key(), 0.0)
        row.positions.append(item.key())

    return sorted(totals.values(), key=lambda r: (-r.value, -len(r.positions)))


def rollup(rows: Iterable[ObjectRow]) -> list[ObjectRow]:
    """Collapse the location dimension: project totals per (object, unit).

    This is the estimator's manual job — *"to figure out how much concrete I
    need, I sum up all 9,000 of them by hand"*. Location is dropped on purpose
    here, which is safe because this view answers "how much in total", not
    "is this internally consistent".
    """
    totals: dict[tuple[str, str], ObjectRow] = {}
    for row in rows:
        key = (row.obj, row.unit)
        merged = totals.get(key)
        if merged is None:
            merged = ObjectRow(location="(Gesamtprojekt)", obj=row.obj, unit=row.unit)
            totals[key] = merged
        merged.quantity += row.quantity
        merged.value += row.value
        merged.positions.extend(row.positions)
    return sorted(totals.values(), key=lambda r: (-r.value, -r.quantity))


def coverage(rows: Sequence[ObjectRow]) -> dict:
    """How much of the tender the tagger actually understood.

    Report this next to the table. A table built from 60% `unklar` rows is not
    evidence of anything, and hiding that is how a plausible-looking screen
    produces a wrong finding.
    """
    total = sum(len(r.positions) for r in rows)
    unknown = sum(len(r.positions) for r in rows if r.obj == UNKNOWN_TAG)
    return {
        "positions": total,
        "rows": len(rows),
        "tagged": total - unknown,
        "unknown": unknown,
        "tagged_pct": round(100.0 * (total - unknown) / total, 1) if total else 0.0,
    }
