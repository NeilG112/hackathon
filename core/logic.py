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
from core.models import Finding, LogicResult, NormalizedItem
from core.objects import UNKNOWN_TAG, ObjectRow, build, tag_of
from utils.text_cleaning import clean_item_text, compare_key

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


def _pre_unit_price(
    item: NormalizedItem,
    pre_prices: dict[str, float] | None,
) -> float:
    if pre_prices:
        price = pre_prices.get(item.key())
        if price is not None:
            return float(price)
    if item.unit_price is not None:
        return float(item.unit_price)
    if item.total_price is not None and item.quantity > 0:
        return float(item.total_price) / float(item.quantity)
    return 0.0


def check_magnitude(
    items: Sequence[NormalizedItem],
    pre_prices: dict[str, float] | None = None,
) -> list[Finding]:
    """Order-of-magnitude quantity outliers — the misplaced-zero check.

    Compares each position against its peers: the same object measured in the
    same unit elsewhere in the tender. Needs `MIN_PEERS` to say anything, and
    uses the median so one bad value cannot drag the baseline.
    """
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
                euro_leverage=abs(item.quantity * _pre_unit_price(item, pre_prices)),
                evidence={"tag": tag, "unit": unit, "median": median,
                          "ratio": round(ratio, 2), "peers": len(peers)},
            ))
    return findings


def check_duplicates(
    items: Sequence[NormalizedItem],
    pre_prices: dict[str, float] | None = None,
) -> list[Finding]:
    """Positions repeating the same work — *"summary and duplicate is a good thing"*.

    Same wording, same unit, different OZ. Often legitimate (the same work in
    two sections), which is why this reports rather than accuses, and why the
    locations are named: identical work in the *same* location is the
    suspicious case.
    """
    groups: dict[tuple[str, str], list[NormalizedItem]] = defaultdict(list)
    for item in items:
        signature = compare_key(item.short_text)
        if signature:
            groups[(signature, constants.normalize_unit(item.unit))].append(item)

    findings: list[Finding] = []
    for (_sig, unit), group in groups.items():
        if len(group) < 2:
            continue
        exposure = sum(
            i.quantity * _pre_unit_price(i, pre_prices)
            if pre_prices or i.unit_price is not None or i.total_price is not None
            else 0.0
            for i in group
        )
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


def _text(item: NormalizedItem) -> str:
    return f"{clean_item_text(item.short_text)} {clean_item_text(item.long_text)}".lower()


def _severity_rank(severity: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(severity, 0)


def run_logic_engine(
    items: Sequence[NormalizedItem],
    rows: Sequence[ObjectRow] | None = None,
    pre_prices: dict[str, float] | None = None,
) -> dict[str, LogicResult]:
    """Run deterministic, per-position rules for a tender of any practical size."""

    if rows is None:
        rows = build(items, depth=2)

    results: dict[str, LogicResult] = {
        item.key(): LogicResult([], "low", [], [])
        for item in items
    }

    def add(item: NormalizedItem, flag: str, severity: str, detail: str) -> None:
        result = results[item.key()]
        if flag not in result.flags:
            result.flags.append(flag)
        if flag not in result.tags:
            result.tags.append(flag)
        if detail not in result.details:
            result.details.append(detail)
        if _severity_rank(severity) > _severity_rank(result.severity):
            result.severity = severity

    # Per-item textual and unit rules.
    for item in items:
        key = item.key()
        unit = constants.normalize_unit(item.unit)
        short_text = clean_item_text(item.short_text)
        long_text = clean_item_text(item.long_text)
        text = _text(item)

        if (unit == "psch" or item.is_lump_sum) and item.quantity not in (0.0, 1.0):
            add(item, "META_MISMATCH", "high",
                f"Pauschale Einheit {item.unit!r} hat Menge {item.quantity:g}, "
                "erwartet 0 oder 1.")

        if item.quantity <= 0 and not any(
            keyword in text for keyword in constants.EVENTUAL_KEYWORDS
        ):
            add(item, "ZERO_QTY", "high",
                f"Menge ist {item.quantity:g}; keine Eventualposition erkannt.")

        short_norm = compare_key(short_text)
        long_norm = compare_key(long_text)
        if any(keyword in short_norm for keyword in constants.BLACKBOX_KEYWORDS):
            if not long_norm or len(long_text) < 25 or long_norm == short_norm:
                add(item, "MISSING_SPEC", "medium",
                    "Komplexer/Black-Box-Text hat keine eigenständig ausreichende "
                    "Langbeschreibung.")

        if any(keyword in text for keyword in ("lieferung", "liefern")):
            montage_words = ("montage", "einbau", "verlegen", "versetzen", "anschließen")
            has_montage = any(word in text for word in montage_words)
            if not has_montage:
                own_tag = tag_of(item)
                location = item.location(depth=2)
                has_peer = own_tag != UNKNOWN_TAG and any(
                    peer.location(depth=2) == location
                    and tag_of(peer) == own_tag
                    and any(word in _text(peer) for word in montage_words)
                    for peer in items
                )
                if not has_peer:
                    add(item, "SCOPE_GAP", "medium",
                        "Lieferleistung genannt, aber Montage-/Einbauumfang nicht "
                        "sichtbar und keine passende Peer-Position in diesem Abschnitt.")

        # Unit and peer-magnitude outliers are separate signals combined here.
        qty_outlier_details: list[str] = []
        normalized_text = compare_key(f"{short_text} {long_text}")
        for keyword, expected_unit in constants.UNIT_EXPECTED_BY_KEYWORD.items():
            if keyword in normalized_text and unit != constants.normalize_unit(expected_unit):
                qty_outlier_details.append(
                    f"Einheit {item.unit!r} passt nicht zur erwarteten Einheit "
                    f"{expected_unit!r} für Schlüsselwort {keyword!r}."
                )
                break
        if qty_outlier_details:
            add(item, "QTY_OUTLIER", "medium", " | ".join(qty_outlier_details))

    # Attach peer-magnitude findings to the same per-key results.
    for finding in check_magnitude(items, pre_prices):
        key = finding.item.key()
        if key in results:
            add(finding.item, "QTY_OUTLIER", "medium", finding.rationale)

    # Relation findings identify category and quantity conflicts.
    relation_findings = check_relations(rows, items, include_companions=False)
    for finding in relation_findings:
        positions = finding.evidence.get("positions", [])
        if finding.item.key() in positions:
            positions = [finding.item.key()]
        for position_key in positions:
            if position_key not in results:
                continue
            representative = next(
                (item for item in items if item.key() == position_key),
                finding.item,
            )
            add(representative, "CATEGORY_MISMATCH", "high", finding.rationale)

    # Explicit companion-quantity gaps within the location.
    for item in items:
        location = item.location(depth=2)
        location_items = [peer for peer in items if peer.location(depth=2) == location]

        is_concrete = tag_of(item) == "Beton"
        has_concrete = is_concrete and item.quantity >= 10.0
        if has_concrete:
            concrete_qty = sum(
                peer.quantity for peer in location_items if tag_of(peer) == "Beton"
            )
            own_long = clean_item_text(item.long_text).lower()
            own_suppressed = any(
                marker in own_long for marker in ("inkl.", "einschl.", "schalung", "bewehr")
            )
            has_companion = any(
                "schalung" in _text(peer) or "bewehr" in _text(peer)
                for peer in location_items
            )
            if concrete_qty >= 10.0 and not has_companion and not own_suppressed:
                add(item, "MISSING_FOLLOW_UP", "medium",
                    f"Beton in Abschnitt {location!r}: mindestens "
                    f"{concrete_qty:g} m³, aber keine Schalungs-/Bewehrungsposition gefunden.")

        is_excavation = tag_of(item) == "Bodenaushub"
        if is_excavation:
            own_long = clean_item_text(item.long_text).lower()
            own_suppressed = any(
                marker in own_long for marker in ("inkl.", "einschl.", "schalung", "verfüll")
            )
            has_backfill = any(tag_of(peer) == "Verfüllung" for peer in location_items)
            if not has_backfill and not own_suppressed:
                add(item, "MISSING_FOLLOW_UP", "medium",
                    f"Bodenaushub in Abschnitt {location!r}, aber keine "
                    "Verfüllungsposition gefunden.")

    return results


def run_all(
    rows: Sequence[ObjectRow],
    items: Sequence[NormalizedItem],
    top_n: int | None = None,
    include_companions: bool = False,
    pre_prices: dict[str, float] | None = None,
) -> list[Finding]:
    """Every cross-position check, ranked by euro exposure."""
    findings = (
        check_relations(rows, items, include_companions)
        + check_magnitude(items, pre_prices)
        + check_duplicates(items, pre_prices)
    )
    findings.sort(key=lambda f: (-f.euro_leverage,
                                 constants.SEVERITY_ORDER.index(f.severity)))
    return findings[:top_n] if top_n else findings
