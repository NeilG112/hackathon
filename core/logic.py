"""The logic engine — contradictions *between* positions.

The other detectors judge a position on its own: is this rate an outlier, is
this wording vague. This one judges positions against each other, which is
where the errors an engineer actually makes show up:

    300 m2 of floor heating over 50 m2 of floor slab
    a trench excavated but never backfilled
    2 chairs and 15 tables in the same classroom
    46 m2 where every comparable section has 460

None of these is detectable from a single line. A position is never
inconsistent with itself.

Everything here is **deterministic**. No model is asked whether something is
wrong — the rules are arithmetic over `core.objects.ObjectRow`, and a civil
engineer can read, argue with and extend `RELATIONS` without touching code.
That is the point: domain knowledge the model does not have gets *encoded*
rather than prompted for, and the same tender produces the same findings every
single run.

**Precision over recall, deliberately.** Three correct findings win an
estimator's trust; fifty findings with ten false ones destroy it permanently,
and he will never look at the fourth screen. Every rule here fires only with a
margin, and anything resting on an `unklar` tag is suppressed outright.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from core import constants
from core.models import Finding, NormalizedItem
from core.objects import UNKNOWN_TAG, ObjectRow

# --- the rule table a civil engineer owns ---------------------------------
#
# (subject, relation, object, tolerance, plain-English reason)
#
#   "<="     subject quantity must not exceed object quantity, within tolerance
#   "needs"  if subject exists in a location, object must exist there too
#
# Tolerance is a fraction: 0.10 means "flag only if it exceeds by >10%", which
# absorbs the ordinary overlaps and offcuts of real construction.
RELATIONS: tuple[tuple[str, str, str, float, str], ...] = (
    ("Bodenheizung", "<=", "Bodenplatte", 0.10,
     "heated floor area cannot exceed the slab it sits on"),
    ("Dämmung", "<=", "Bodenplatte", 0.15,
     "insulation area cannot exceed the slab it covers"),
    ("Bettung", "<=", "Leitungsgraben", 0.20,
     "bedding cannot exceed the trench that contains it"),
    ("Verfüllung", "<=", "Bodenaushub", 0.20,
     "you cannot backfill more than you excavated"),
    # --- UNVERIFIED: companion rules below are domain judgements, not physical
    # necessities, and no civil engineer has confirmed them. Bedding and
    # backfill are frequently Nebenleistungen absorbed into the main position,
    # so their absence is often correct. Off by default; switch on only once
    # someone who writes tenders has signed them off.
    ("Leitungsgraben", "needs", "Verfüllung", 0.0,
     "a trench is excavated but never backfilled — the backfill is either "
     "missing from the tender or hidden in another position"),
    ("Rohrleitung", "needs", "Bettung", 0.0,
     "pipework with no bedding position — either unpriced scope or an "
     "incidental the contractor absorbs"),
)

# An order-of-magnitude check: the client described exactly this failure —
# "vielleicht hat er sich um die Null vertan, 46 statt 460".
MAGNITUDE_FACTOR = 20.0     # flag a position this many times off its peers
MIN_PEERS = 6               # below this there is no meaningful peer group
# A peer group that is itself wildly spread says nothing about any member.
# "50 St vs a median of 4 St" is not an error when the group lumps warning
# lamps in with site containers — it is a tagging artifact. Same lesson as the
# quartile fix in the price-outlier detector: test against the spread the
# comparables actually occupy, and stay silent when that spread is meaningless.
MAX_PEER_SPREAD = 10.0      # p75/p25 above this -> group too heterogeneous

DUPLICATE_MIN_VALUE = 500.0  # ignore trivial repeats


@dataclass
class Relation:
    """One evaluated rule, kept so the UI can show the arithmetic."""

    subject: str
    relation: str
    obj: str
    location: str
    subject_qty: float
    object_qty: float
    unit: str
    reason: str


def _by_location(rows: Sequence[ObjectRow]) -> dict[str, dict[tuple[str, str], ObjectRow]]:
    out: dict[str, dict[tuple[str, str], ObjectRow]] = defaultdict(dict)
    for row in rows:
        if row.obj == UNKNOWN_TAG:
            continue
        out[row.location][(row.obj, row.unit)] = row
    return out


def _find(cell: dict, obj: str) -> ObjectRow | None:
    """The row for `obj` in this location, whichever unit it was measured in."""
    for (name, _unit), row in cell.items():
        if name == obj and row.quantity > 0:
            return row
    return None


def _item_for(row: ObjectRow, items: Sequence[NormalizedItem]) -> NormalizedItem:
    """A representative position, so a finding can point somewhere real."""
    index = {i.key(): i for i in items}
    for oz in row.positions:
        if oz in index:
            return index[oz]
    return NormalizedItem(oz=row.positions[0] if row.positions else "",
                          quantity=row.quantity, unit=row.unit,
                          short_text=row.label())


def check_relations(
    rows: Sequence[ObjectRow],
    items: Sequence[NormalizedItem],
    include_companions: bool = False,
) -> list[Finding]:
    """Apply `RELATIONS` within each location.

    `include_companions` enables the unverified "needs" rules. Default off:
    they produced 19 findings on the demo tender and not one was defensible.
    """
    findings: list[Finding] = []

    for location, cell in _by_location(rows).items():
        for subject, relation, obj, tolerance, reason in RELATIONS:
            left = _find(cell, subject)
            if left is None:
                continue
            right = _find(cell, obj)

            if relation == "needs":
                if not include_companions or right is not None:
                    continue
                findings.append(Finding(
                    item=_item_for(left, items),
                    detector="logic",
                    severity="medium",
                    rationale=(
                        f"{subject} appears in “{location}” but {obj} does not: "
                        f"{reason}. {len(left.positions)} positions affected."
                    ),
                    euro_leverage=left.value,
                    evidence={"location": location, "subject": subject,
                              "missing": obj, "positions": left.positions[:20]},
                ))
                continue

            # "<=" only compares like with like.
            if right is None or left.unit != right.unit or right.quantity <= 0:
                continue
            if left.quantity <= right.quantity * (1.0 + tolerance):
                continue

            ratio = left.quantity / right.quantity
            findings.append(Finding(
                item=_item_for(left, items),
                detector="logic",
                severity="high",
                rationale=(
                    f"“{location}”: {left.quantity:,.0f} {left.unit} of {subject} "
                    f"but only {right.quantity:,.0f} {right.unit} of {obj} "
                    f"({ratio:.1f}x) — {reason}. Either a quantity is wrong or "
                    "scope is missing; both change the price."
                ),
                euro_leverage=max(left.value, right.value),
                evidence={"location": location, "subject": subject, "object": obj,
                          "subject_qty": left.quantity, "object_qty": right.quantity,
                          "ratio": round(ratio, 2),
                          "positions": (left.positions + right.positions)[:20]},
            ))
    return findings


def check_magnitude(items: Sequence[NormalizedItem]) -> list[Finding]:
    """Order-of-magnitude quantity outliers — the misplaced-zero check.

    Compares each position against its peers: the same object measured in the
    same unit elsewhere in the tender. Needs `MIN_PEERS` to say anything, and
    uses the median so one bad value cannot drag the baseline.
    """
    from core.objects import tag_of

    groups: dict[tuple[str, str], list[NormalizedItem]] = defaultdict(list)
    for item in items:
        tag = tag_of(item)
        if tag == UNKNOWN_TAG or item.quantity <= 0:
            continue
        groups[(tag, constants.normalize_unit(item.unit))].append(item)

    findings: list[Finding] = []
    for (tag, unit), peers in groups.items():
        if len(peers) < MIN_PEERS:
            continue
        quantities = sorted(i.quantity for i in peers)
        median = quantities[len(quantities) // 2]
        if median <= 0:
            continue
        p25 = quantities[len(quantities) // 4]
        p75 = quantities[(3 * len(quantities)) // 4]
        if p25 <= 0 or p75 / p25 > MAX_PEER_SPREAD:
            continue
        for item in peers:
            ratio = item.quantity / median
            if ratio < MAGNITUDE_FACTOR and ratio > 1 / MAGNITUDE_FACTOR:
                continue
            direction = "larger" if ratio > 1 else "smaller"
            findings.append(Finding(
                item=item,
                detector="logic",
                severity="medium",
                rationale=(
                    f"{item.quantity:,.0f} {unit} is {max(ratio, 1/ratio):.0f}x "
                    f"{direction} than the median of {len(peers)} comparable "
                    f"{tag} positions ({median:,.0f} {unit}). A misplaced "
                    "decimal or a genuinely unusual position — worth one look."
                ),
                euro_leverage=abs((item.total_price or 0.0)),
                evidence={"tag": tag, "unit": unit, "median": median,
                          "ratio": round(ratio, 2), "peers": len(peers)},
            ))
    return findings


def check_duplicates(items: Sequence[NormalizedItem]) -> list[Finding]:
    """Positions repeating the same work — *"summary and duplicate is a good thing"*.

    Same wording, same unit, different OZ. Often legitimate (the same work in
    two sections), which is why this reports rather than accuses, and why the
    locations are named: identical work in the *same* location is the
    suspicious case.
    """
    from utils.text_cleaning import compare_key

    groups: dict[tuple[str, str], list[NormalizedItem]] = defaultdict(list)
    for item in items:
        signature = compare_key(item.short_text)
        if signature:
            groups[(signature, constants.normalize_unit(item.unit))].append(item)

    findings: list[Finding] = []
    for (_sig, unit), group in groups.items():
        if len(group) < 2:
            continue
        exposure = sum(i.total_price or 0.0 for i in group)
        locations = {i.location() for i in group}
        same_place = len(locations) == 1
        if not same_place and exposure < DUPLICATE_MIN_VALUE:
            continue
        findings.append(Finding(
            item=group[0],
            detector="logic",
            severity="medium" if same_place else "low",
            rationale=(
                f"{len(group)} positions carry identical wording and unit "
                f"({', '.join(i.key() for i in group[:6])})"
                + (" — all in the same section, so this may be a genuine "
                   "duplication rather than the same work in two places."
                   if same_place else
                   f" across {len(locations)} sections, which is usually "
                   "legitimate. Worth confirming the quantities are not "
                   "double-counted.")
            ),
            euro_leverage=exposure,
            evidence={"positions": [i.key() for i in group],
                      "locations": sorted(locations), "same_location": same_place},
        ))
    return findings


def run_all(
    rows: Sequence[ObjectRow],
    items: Sequence[NormalizedItem],
    top_n: int | None = None,
    include_companions: bool = False,
) -> list[Finding]:
    """Every cross-position check, ranked by euro exposure."""
    findings = (
        check_relations(rows, items, include_companions)
        + check_magnitude(items)
        + check_duplicates(items)
    )
    findings.sort(key=lambda f: (-f.euro_leverage,
                                 constants.SEVERITY_ORDER.index(f.severity)))
    return findings[:top_n] if top_n else findings
