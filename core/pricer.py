"""Price a blank bill of quantities. Task 003.

**The one inversion that matters (PLAN.md):** look up a real observed price
*first*, from `data/reference_prices.json` built out of the 720 genuinely priced
items in the dataset. Fall back to `constants.FALLBACK_RATES_BY_UNIT` only where
no comparable exists — and return *which source was used* so the UI can label
it. Where there is no comparable at all, return `None` and let the UI print
`kein Vergleichswert`. An honest blank beats an invented euro.

Lookup order, most specific first:

    nearest priced lines by item text, same unit     -> "benchmark_match"
    bucket x unit  ("rohr|m",  n>=MIN_COMPARABLES)   -> "benchmark"
    unit only      ("m",       n>=MIN_COMPARABLES)   -> "benchmark_unit"
    hand-authored fallback rate for the unit         -> "fallback_rate"
    nothing                                          -> "none"

The text-match tier carries the accuracy. Measured against the real EUR 897k
bid with that bid held out of the benchmark (`python3 validate.py`):

    bucket medians only      -50% total error, 91% median position error
    + nearest-text matching   +6% total error,  7% median position error

The reason is that a keyword bucket cannot separate "Rohrleitung markieren"
(EUR 0.27/m) from "Leitungsbehelfsbrücke" (EUR 6,000/m) — same bucket, same
unit, four orders of magnitude apart. The words of the item do separate them.

Everything here is pure: no file I/O except `load_reference_prices`, no
printing. `price_boq` is re-run on every slider change, so it stays cheap.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional

from core import constants
from core.facts import PositionFacts, extract_facts
from core.models import NormalizedItem

PriceSource = Literal[
    "benchmark_match", "benchmark", "benchmark_unit", "fallback_rate", "none"
]

BENCHMARK_SOURCES = ("benchmark_match", "benchmark", "benchmark_unit")


@dataclass
class PricedItem:
    item: NormalizedItem
    unit_price: Optional[float]
    total: Optional[float]
    source: PriceSource
    comparables: int = 0      # how many reference items backed this
    spread: Optional[float] = None   # p75 - p25 of comparables
    bucket: str = ""
    distribution: Optional[dict] = field(default=None, repr=False)
    note: str = ""
    similarity_score: float = 0.0

    @property
    def is_benchmarked(self) -> bool:
        return self.source in BENCHMARK_SOURCES

    @property
    def euro_exposure(self) -> float:
        """What this line is worth getting wrong. Used for ranking."""
        return abs(self.total or 0.0)


def load_reference_prices(path: str | None = None) -> dict:
    """Load the benchmark distributions. Never raises if the file is missing.

    A missing benchmark degrades the whole app to labeled fallback rates, which
    is survivable and visible. A crash on stage is not.
    """
    target = path or constants.REFERENCE_PRICES
    if not os.path.exists(target):
        return {"by_unit": {}, "by_bucket": {}, "items": [], "meta": {"missing": target}}
    with open(target, encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("by_unit", {})
    data.setdefault("by_bucket", {})
    return data


def percentile(ordered: list[float], q: float) -> float:
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def summarize_prices(values: list[float]) -> dict:
    """The shape every distribution in `reference_prices.json` takes."""
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "median": round(_median(ordered), 2),
        "p25": round(percentile(ordered, 0.25), 2),
        "p75": round(percentile(ordered, 0.75), 2),
        "min": round(ordered[0], 2),
        "max": round(ordered[-1], 2),
    }


def _median(ordered: list[float]) -> float:
    import statistics
    return statistics.median(ordered)


def build_distributions(
    items: Iterable[dict],
    exclude_sources: Iterable[str] = (),
) -> dict:
    """Group raw benchmark rows into `by_unit` / `by_bucket` distributions.

    Shared by `scripts/build_reference_prices.py` (which writes the file) and
    by `validate.py`, which needs to rebuild them **with the answer key held
    out**. Without that leave-one-out, the reveal prices a bill of quantities
    using the same contractor's bid for that very bill of quantities, and the
    measured error is circular.

    Rental/time-on-site units and provisional (quantity-less) positions are
    excluded: a per-week vorhalten price is not comparable with an installation
    rate even when the nominal unit matches, and a unit-less provisional price
    has no rate at all.
    """
    drop = {os.path.basename(s) for s in exclude_sources}
    by_unit: dict[str, list[float]] = {}
    by_bucket: dict[str, list[float]] = {}

    for row in items:
        if row.get("rental") or row.get("provisional"):
            continue
        if os.path.basename(row.get("src", "")) in drop:
            continue
        by_unit.setdefault(row["unit"], []).append(row["ep"])
        by_bucket.setdefault(f"{row['bucket']}|{row['unit']}", []).append(row["ep"])

    return {
        "by_unit": {k: summarize_prices(v) for k, v in sorted(by_unit.items())},
        "by_bucket": {k: summarize_prices(v) for k, v in sorted(by_bucket.items())},
    }


def without_source(reference: dict, source: str) -> dict:
    """`reference` with one bid held out — distributions **and** item list.

    Both must be filtered. The distributions feed the bucket/unit tiers, but
    `nearest_comparables` reads `items` directly and prices the large majority
    of positions, so filtering only the distributions leaves the tier that does
    nearly all the work still looking at the answer. That bug silently returned
    a perfect text match to the held-out bid's own line for the same position.
    """
    dropped = os.path.basename(source)
    kept = [r for r in reference.get("items", [])
            if os.path.basename(r.get("src", "")) != dropped]

    rebuilt = build_distributions(kept)
    meta = dict(reference.get("meta", {}))
    meta["held_out"] = dropped
    meta["priced_items"] = len(kept)
    return {**rebuilt, "items": kept, "meta": meta}


def bucket_for(item: NormalizedItem) -> str:
    """Keyword bucket an item falls into (rohr / schacht / armatur / ...)."""
    return constants.bucket_for_text(item.short_text or item.long_text)


def company_multiplier(company: dict | None = None) -> float:
    """How far this company's cost base sits from the benchmark's.

    The benchmark median is a real submitted price, so it already contains some
    other contractor's wage, overhead and margin. The sliders therefore express
    a *ratio* against `DEFAULT_COMPANY`, where this returns exactly 1.0 and the
    estimate is the untouched benchmark. That is what makes the reveal's error
    figure a measurement rather than an artifact of slider defaults.

    Wage moves only the labour share of a rate; overhead and margin move the
    whole thing; pricing aggression swings +/- `risk_span` around neutral 0.5.
    """
    base = constants.DEFAULT_COMPANY
    c = {**base, **(company or {})}

    labour = constants.PRICING_MODEL["labour_share"]
    wage_ratio = c["mittellohn_eur_h"] / base["mittellohn_eur_h"]
    wage = 1.0 + labour * (wage_ratio - 1.0)

    overhead = (1.0 + c["overhead_pct"] / 100.0) / (1.0 + base["overhead_pct"] / 100.0)
    profit = (1.0 + c["profit_pct"] / 100.0) / (1.0 + base["profit_pct"] / 100.0)

    span = constants.PRICING_MODEL["risk_span"]
    risk = 1.0 - (c["risk_appetite"] - base["risk_appetite"]) * 2.0 * span

    return wage * overhead * profit * risk


def tokens(text: str) -> frozenset[str]:
    """Content tokens of an item description, for nearest-comparable matching.

    Anonymisation placeholders (`[PERSON_000...083]`, `PER029`, `TELEFON_084`)
    are stripped: they appear in both the tender and the reference set, carry no
    trade meaning, and otherwise dominate the overlap score. Short tokens go
    too — German compounds carry the signal here ("grabenverbaugerät",
    "abschrumpfmuffe"), not "mit"/"und"/"der".
    """
    low = re.sub(r"\[?\b(?:person|firma|ort|projekt|nummer|telefon|per)[_0-9]*\]?",
                 " ", (text or "").lower())
    return frozenset(t for t in re.findall(r"[a-zäöüß]{4,}", low)
                     if t not in _STOPWORDS)


_STOPWORDS = frozenset("""
oder sowie nach ohne über unter gemäß einschl incl inkl bzw ggf etwa ca
liefern lieferung stück wird werden wie des der die das den dem für mit auf
vorh vorhanden ausf ausführung
""".split())


def _reference_index(
    reference: dict,
) -> list[tuple[frozenset[str], str, float, str, PositionFacts]]:
    """Tokenized reference items, cached on the reference dict itself.

    `price_boq` re-runs on every slider change, so this is built once per
    benchmark and reused. Cached under a private key rather than a module
    global so two benchmarks (full and leave-one-out) cannot share a cache.
    """
    cached = reference.get("_index")
    if cached is not None:
        return cached

    index = []
    for row in reference.get("items", []):
        if row.get("rental") or row.get("provisional"):
            continue
        text = row.get("text", "")
        toks = tokens(text)
        if toks:
            reference_item = NormalizedItem(
                oz=f"REF-{len(index)}",
                quantity=1.0,
                unit=row["unit"],
                short_text=text,
            )
            index.append((
                toks,
                row["unit"],
                row["ep"],
                text,
                extract_facts(reference_item),
            ))
    reference["_index"] = index
    return index


def _dimension_adjusted_similarity(
    similarity: float,
    item_facts: PositionFacts,
    reference_facts: PositionFacts,
) -> float:
    """Reward matching technical dimensions and strongly penalize mismatches."""
    adjusted = similarity
    for name in ("dn", "pn", "thickness_cm", "depth_m"):
        item_value = getattr(item_facts, name)
        reference_value = getattr(reference_facts, name)
        if item_value is None or reference_value is None:
            continue
        if math.isclose(
            float(item_value),
            float(reference_value),
            rel_tol=0.05,
            abs_tol=0.01,
        ):
            adjusted += 0.12
            continue
        smaller = min(abs(float(item_value)), abs(float(reference_value)))
        larger = max(abs(float(item_value)), abs(float(reference_value)))
        ratio = larger / smaller if smaller > 0 else float("inf")
        penalty = min(0.9, 0.25 + 0.25 * math.log2(ratio))
        adjusted -= penalty
    return round(max(0.0, min(1.0, adjusted)), 3)


def nearest_comparables(
    item: NormalizedItem,
    reference: dict,
    unit: str,
    limit: int = 5,
) -> list[tuple[float, float, str]]:
    """Reference items whose description overlaps this one's, best first.

    Jaccard overlap on content tokens, restricted to the same unit — an item
    priced per metre tells you nothing about one priced per piece. Returns
    `(score, unit_price, text)`.

    This is the tier that makes the estimate defensible position by position. A
    median per keyword bucket cannot separate "Rohrleitung markieren" (EUR 0.27
    per metre) from "Leitungsbehelfsbrücke" (EUR 6,000 per metre) — both are
    pipework priced per metre, and both land in the same bucket. Matching on
    the words of the item does separate them, and it also gives the UI
    something to show: *the real priced line we think yours resembles.*
    """
    item_tokens = tokens(item.short_text or item.long_text)
    if not item_tokens:
        return []

    item_facts = extract_facts(item)
    scored = []
    for ref_tokens, ref_unit, ep, text, ref_facts in _reference_index(reference):
        if ref_unit != unit:
            continue
        overlap = len(item_tokens & ref_tokens)
        if not overlap:
            continue
        score = _dimension_adjusted_similarity(
            overlap / len(item_tokens | ref_tokens),
            item_facts,
            ref_facts,
        )
        if score >= constants.MIN_TEXT_SIMILARITY:
            scored.append((round(score, 3), ep, text))

    scored.sort(key=lambda s: (-s[0], s[1]))
    return scored[:limit]


def _distribution(reference: dict, bucket: str, unit: str) -> tuple[Optional[dict], PriceSource]:
    """Most specific distribution with enough comparables to be worth using."""
    by_bucket = reference.get("by_bucket", {})
    by_unit = reference.get("by_unit", {})

    specific = by_bucket.get(f"{bucket}|{unit}")
    if specific and specific.get("n", 0) >= constants.MIN_COMPARABLES:
        return specific, "benchmark"

    generic = by_unit.get(unit)
    if generic and generic.get("n", 0) >= constants.MIN_COMPARABLES:
        return generic, "benchmark_unit"

    return None, "none"


def price_item(
    item: NormalizedItem,
    reference: dict,
    company: dict | None = None,
) -> PricedItem:
    """Price one item. Benchmark first, labeled fallback second, else None."""
    unit = constants.normalize_unit(item.unit)
    bucket = bucket_for(item)
    multiplier = company_multiplier(company)

    # Tier 1: the most similar real priced lines, by item description.
    matches = nearest_comparables(item, reference, unit)
    if len(matches) >= constants.MIN_TEXT_MATCHES:
        eps = sorted(ep for _, ep, _ in matches)
        unit_price = _median(eps) * multiplier
        best_score, _, best_text = matches[0]
        return PricedItem(
            item=item,
            unit_price=round(unit_price, 2),
            total=round(unit_price * item.quantity, 2),
            source="benchmark_match",
            comparables=len(matches),
            spread=round(eps[-1] - eps[0], 2),
            bucket=bucket,
            distribution={"median": round(_median(eps), 2),
                          "p25": round(percentile(eps, 0.25), 2),
                          "p75": round(percentile(eps, 0.75), 2),
                          "n": len(eps)},
            note=(f"matched {len(matches)} similar priced lines "
                  f"({best_score:.0%} similarity), closest: {best_text[:60]}"),
            similarity_score=best_score,
        )

    dist, source = _distribution(reference, bucket, unit)

    if dist is not None:
        unit_price = dist["median"] * multiplier
        note = (f"median of {dist['n']} comparable {bucket} items in {unit}"
                if source == "benchmark"
                else f"median of {dist['n']} items priced in {unit} (no {bucket} comparables)")
        return PricedItem(
            item=item,
            unit_price=round(unit_price, 2),
            total=round(unit_price * item.quantity, 2),
            source=source,
            comparables=dist["n"],
            spread=round(dist["p75"] - dist["p25"], 2),
            bucket=bucket,
            distribution=dist,
            note=note,
        )

    fallback = constants.FALLBACK_RATES_BY_UNIT.get(unit)
    if fallback is not None:
        unit_price = fallback * multiplier
        return PricedItem(
            item=item,
            unit_price=round(unit_price, 2),
            total=round(unit_price * item.quantity, 2),
            source="fallback_rate",
            comparables=0,
            bucket=bucket,
            note=f"no comparable — hand-authored fallback rate for {unit}",
        )

    return PricedItem(
        item=item,
        unit_price=None,
        total=None,
        source="none",
        comparables=0,
        bucket=bucket,
        note=constants.NO_COMPARABLE_LABEL,
    )


def price_boq(
    items: Iterable[NormalizedItem],
    reference: dict | None = None,
    company: dict | None = None,
) -> list[PricedItem]:
    """Price a whole BoQ. `company` defaults to `constants.DEFAULT_COMPANY`."""
    ref = reference if reference is not None else load_reference_prices()
    return [price_item(i, ref, company) for i in items]


def implied_cost_base(priced: Iterable[PricedItem], target_total: float) -> dict:
    """The single scalar that makes our estimate match `target_total`.

    This is demo step 5's engine, and the honest answer to "why is the absolute
    total off". A benchmark built from other projects captures the *shape* of a
    price list well and its *level* badly — site conditions, haulage distance,
    competitive pressure and programme all move every rate at once. One scalar
    absorbs that, and what remains is genuine position-by-position disagreement.

    Inverting the wage term of `company_multiplier` turns the scalar into the
    wage it implies, which is the sentence the demo wants: *"drag Mittellohn to
    EUR 104/h and we match their bid — that is this competitor's implied cost
    base."*
    """
    ours = sum(p.total or 0.0 for p in priced)
    if not ours:
        return {"multiplier": None, "implied_mittellohn_eur_h": None, "ours": 0.0}

    multiplier = target_total / ours
    labour = constants.PRICING_MODEL["labour_share"]
    base_wage = constants.DEFAULT_COMPANY["mittellohn_eur_h"]
    return {
        "multiplier": round(multiplier, 4),
        "implied_mittellohn_eur_h": round(
            base_wage * (1.0 + (multiplier - 1.0) / labour), 2
        ),
        "ours": round(ours, 2),
    }


def summarize(priced: Iterable[PricedItem]) -> dict:
    """Totals and coverage. The UI headline and `validate.py` both read this."""
    rows = list(priced)
    by_source: dict[str, int] = {}
    for p in rows:
        by_source[p.source] = by_source.get(p.source, 0) + 1

    benchmarked = [p for p in rows if p.is_benchmarked]
    return {
        "items": len(rows),
        "total": round(sum(p.total or 0.0 for p in rows), 2),
        "priced": sum(1 for p in rows if p.total is not None),
        "no_comparable": sum(1 for p in rows if p.source == "none"),
        "benchmark_share_pct": round(100.0 * len(benchmarked) / len(rows), 1) if rows else 0.0,
        "by_source": by_source,
        # Value sitting on hand-authored rates rather than observed prices —
        # the honest caveat to put next to any headline total.
        "fallback_value": round(
            sum(p.total or 0.0 for p in rows if p.source == "fallback_rate"), 2
        ),
    }
