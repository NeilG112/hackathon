"""Three detectors. Not five.

Each detector is a pure function `(priced_items, context) -> list[Finding]`.
No I/O, no Streamlit, no printing. Findings are ranked by euro leverage
(quantity x price exposure) and the top ~20 are shown.

**What "outlier" means depends on the input, and this is the one thing to
understand before changing detector 1.** A priced file (a submitted bid) has
observed unit prices, so a rate far from the market is a real finding — the
classic speculative-price check. A *blank tender* has no prices at all: the
only number available is our own estimate, and that estimate was drawn from
the benchmark distribution, so testing it against that distribution is
circular. On the demo file 228 of 248 estimates are exactly their benchmark
median; a naive implementation returns zero findings and looks like it works.

So on a blank tender detector 1 reports **dispersion**: the positions where
real contractors disagree most about the rate. Those are where a single number
is least trustworthy and where the money moves.
"""

from __future__ import annotations

import re
from typing import Optional, Sequence

from core import constants
from core.models import Finding, NormalizedItem
from core.pricer import PricedItem

# A contract clause has no attributable euro value but can outweigh every line
# item in the tender, so remark findings cannot compete on leverage and would
# otherwise never surface. They get reserved slots instead.
REMARK_SLOTS = 3


def severity_for(euro: float) -> str:
    if euro >= constants.SEVERITY_HIGH_EUR:
        return "high"
    if euro >= constants.SEVERITY_MEDIUM_EUR:
        return "medium"
    return "low"


def euro_leverage(item: NormalizedItem, unit_price: Optional[float]) -> float:
    """Quantity x price exposure. The single ranking number."""
    if unit_price is None:
        return 0.0
    return abs(item.quantity * unit_price)


def _synthetic_item(oz: str, text: str) -> NormalizedItem:
    """A stand-in position for findings that belong to no single line.

    Contract preamble and whole-BoQ observations still have to render in a
    table keyed on positions, so they get a labelled pseudo-position rather
    than a `None` the UI would have to special-case.
    """
    return NormalizedItem(oz=oz, quantity=0.0, unit="", short_text=text)


# --- Detector 1 -------------------------------------------------------------

def unit_price_outlier(priced: Sequence[PricedItem]) -> list[Finding]:
    """Speculative prices where prices exist; market dispersion where they don't."""
    findings: list[Finding] = []

    for p in priced:
        dist = p.distribution
        if not dist or dist.get("n", 0) < constants.MIN_COMPARABLES:
            continue
        median = dist.get("median") or 0.0
        if median <= 0:
            continue

        observed = p.item.unit_price

        if observed is not None:
            # The file carries a real submitted rate: test it against the market.
            #
            # Tested against the *quartiles*, not a ratio to the median. Some
            # comparable groups are enormously wide — the catch-all "St" group
            # spans 0.50 to 39,186 EUR — and against a median alone a perfectly
            # ordinary rate in a wide group reads as "0.1x the market". Using
            # the band the comparables actually occupy makes the test as strict
            # as the evidence allows and no stricter.
            low = dist.get("p25", median) * constants.OUTLIER_LOW_FACTOR
            high = dist.get("p75", median) * constants.OUTLIER_HIGH_FACTOR
            if low <= observed <= high:
                continue

            reference_point = dist.get("p25", median) if observed < low else dist.get("p75", median)
            at_stake = abs(observed - reference_point) * p.item.quantity
            direction = "below" if observed < low else "above"
            findings.append(Finding(
                item=p.item,
                detector="unit_price_outlier",
                severity=severity_for(at_stake),
                rationale=(
                    f"Priced at {observed:,.2f} €/{p.item.unit or '—'}, "
                    f"{direction} the {dist.get('p25', 0):,.2f}–"
                    f"{dist.get('p75', 0):,.2f} € band that {dist['n']} "
                    f"comparable items occupy. {at_stake:,.0f} € turns on this "
                    "rate — the kind of gap that is either a mistake or a "
                    "deliberate bet on the quantity changing."
                ),
                euro_leverage=at_stake,
                evidence={"observed": observed, "median": median,
                          "p25": dist.get("p25"), "p75": dist.get("p75"),
                          "comparables": dist["n"]},
            ))
            continue

        # Blank tender: no rate to test. Report where the market disagrees.
        spread = (dist.get("p75", 0.0) - dist.get("p25", 0.0))
        if spread <= 0:
            continue
        dispersion = spread / median
        if dispersion < constants.DISPERSION_WARN_RATIO:
            continue

        at_stake = spread * p.item.quantity
        findings.append(Finding(
            item=p.item,
            detector="unit_price_outlier",
            severity=severity_for(at_stake),
            rationale=(
                f"Comparable contractors disagree widely on this rate: "
                f"{dist['p25']:,.2f}–{dist['p75']:,.2f} €/{p.item.unit or '—'} "
                f"across {dist['n']} items. At {p.item.quantity:,.0f} "
                f"{p.item.unit or 'units'} that spread is worth {at_stake:,.0f} €, "
                "so the estimate here is a guess with a wide band."
            ),
            euro_leverage=at_stake,
            evidence={"p25": dist["p25"], "p75": dist["p75"], "median": median,
                      "dispersion": round(dispersion, 2), "comparables": dist["n"]},
        ))

    return findings


# --- Detector 2 -------------------------------------------------------------

def _term_pattern(term: str) -> re.Pattern:
    """Word-boundary matcher. `ggf` must not fire inside another word."""
    return re.compile(r"(?<!\w)" + re.escape(term).replace(r"\ ", r"\s+") + r"(?!\w)",
                      re.IGNORECASE)


_TERM_PATTERNS = {term: _term_pattern(term) for term in constants.VAGUE_SCOPE_TERMS}


def _matched_terms(text: str) -> list[str]:
    if not text:
        return []
    return [term for term, pattern in _TERM_PATTERNS.items() if pattern.search(text)]


def vague_scope(
    priced: Sequence[PricedItem],
    remarks: Sequence[str] = (),
) -> list[Finding]:
    """Trigger words over item text *and* `<Remark>` text.

    The remarks are the Vorbemerkungen — contract preamble, 46 blocks in the
    demo file. They are not priceable positions, which is why the parsers keep
    them out of the item list, and they are where the risk-shifting clauses
    actually live. PLAN.md expects this to be the highest-value detector for
    the least work.
    """
    findings: list[Finding] = []

    for p in priced:
        text = f"{p.item.short_text} {p.item.long_text}"
        terms = _matched_terms(text)
        if not terms:
            continue
        exposure = p.total or 0.0
        reasons = "; ".join(constants.VAGUE_SCOPE_TERMS[t] for t in terms[:2])
        findings.append(Finding(
            item=p.item,
            detector="vague_scope",
            severity=severity_for(exposure),
            rationale=(
                f"Scope is open-ended (“{terms[0]}”): {reasons}. "
                f"{exposure:,.0f} € is priced against wording that can be "
                "read more than one way."
            ),
            euro_leverage=exposure,
            evidence={"terms": terms},
        ))

    for index, remark in enumerate(remarks, start=1):
        terms = _matched_terms(remark)
        if not terms:
            continue
        reasons = "; ".join(constants.VAGUE_SCOPE_TERMS[t] for t in terms[:2])
        excerpt = remark[:110].strip()
        findings.append(Finding(
            item=_synthetic_item(f"VORB-{index:02d}", excerpt),
            detector="vague_scope",
            severity="high",
            rationale=(
                f"Contract preamble, not a priced position (“{terms[0]}”): "
                f"{reasons}. A clause here applies across the whole tender, so "
                "it has no single euro value and will not rank by leverage — "
                "read it anyway."
            ),
            euro_leverage=0.0,
            evidence={"terms": terms, "remark_index": index, "text": remark[:400]},
        ))

    return findings


# --- Detector 3 -------------------------------------------------------------

def quantity_sanity(priced: Sequence[PricedItem]) -> list[Finding]:
    """Unit mismatches, suspicious round numbers, provisional share."""
    findings: list[Finding] = []
    provisional_value = 0.0
    total_value = 0.0

    for p in priced:
        exposure = p.total or 0.0
        total_value += exposure
        unit = constants.normalize_unit(p.item.unit)
        text = (p.item.short_text or "").lower()

        # Unit vs. what the work described usually gets measured in. If any
        # matching keyword agrees with the unit used, the position is fine —
        # descriptions routinely mention several trades ("Boden ... Rohr"), and
        # firing on one while another explains the unit is a false positive.
        matched = {k: v for k, v in constants.UNIT_EXPECTED_BY_KEYWORD.items()
                   if k in text}
        if unit and matched and unit not in matched.values():
            keyword, expected = next(iter(matched.items()))
            findings.append(Finding(
                item=p.item,
                detector="qty_sanity",
                severity=severity_for(exposure),
                rationale=(
                    f"Described as “{keyword}” but measured in "
                    f"{p.item.unit} where {expected} is normal in comparable "
                    "priced work. Either the scope is not what the wording "
                    "suggests, or the quantity basis is wrong — both change "
                    "the price."
                ),
                euro_leverage=exposure,
                evidence={"keyword": keyword, "unit": unit, "expected": expected},
            ))

        # Suspiciously round quantities: an estimate dressed as a measurement.
        if p.item.quantity in constants.SUSPICIOUS_ROUND_QUANTITIES:
            findings.append(Finding(
                item=p.item,
                detector="qty_sanity",
                severity=severity_for(exposure),
                rationale=(
                    f"Quantity is exactly {p.item.quantity:,.0f} "
                    f"{p.item.unit}. Round numbers in a bill of quantities are "
                    "usually an allowance rather than a measurement, and the "
                    "risk of the difference sits with the contractor."
                ),
                euro_leverage=exposure,
                evidence={"quantity": p.item.quantity},
            ))

        # Provisional / quantity-less positions.
        if p.item.quantity == 0 or p.item.is_lump_sum:
            provisional_value += exposure

    if total_value > 0:
        share = 100.0 * provisional_value / total_value
        if share >= constants.PROVISIONAL_SHARE_WARN_PCT:
            findings.append(Finding(
                item=_synthetic_item("SUMME", "Provisional and lump-sum share"),
                detector="qty_sanity",
                severity="high",
                rationale=(
                    f"{share:.0f}% of the tender's value sits in lump-sum or "
                    "quantity-less positions. That share of the price is fixed "
                    "before the work is measured, so every overrun is absorbed "
                    "by the contractor."
                ),
                euro_leverage=provisional_value,
                evidence={"share_pct": round(share, 1),
                          "provisional_value": round(provisional_value, 2)},
            ))

    return findings


# --- Orchestration ----------------------------------------------------------

def run_all(
    priced: Sequence[PricedItem],
    remarks: Sequence[str] = (),
    top_n: int | None = None,
) -> list[Finding]:
    """Run the three detectors, dedupe per position, rank by euro leverage.

    One finding per position per detector: a position that trips the same
    detector twice says nothing more the second time, and duplicates in the
    top 20 waste the only screen the estimator looks at.

    Remark findings are appended rather than ranked. They carry no attributable
    euro value, so on leverage alone they would always lose to a line item and
    never be read — which would defeat the detector PLAN.md rates highest.
    """
    findings = (
        unit_price_outlier(priced)
        + vague_scope(priced, remarks)
        + quantity_sanity(priced)
    )

    seen: set[tuple[str, str]] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = (finding.item.key(), finding.detector)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)

    ranked = sorted(
        (f for f in unique if f.euro_leverage > 0),
        key=lambda f: f.euro_leverage,
        reverse=True,
    )
    # Reserved slots go to contract-preamble findings specifically. Zero-euro
    # *item* findings (vague wording on a position we could not price) are
    # real but would otherwise take the slots and bury the clauses.
    remark_findings = [f for f in unique if "remark_index" in f.evidence]
    other_zero = [f for f in unique
                  if f.euro_leverage <= 0 and "remark_index" not in f.evidence]

    if top_n is None:
        return ranked + remark_findings + other_zero
    return ranked[:top_n] + remark_findings[:REMARK_SLOTS]
