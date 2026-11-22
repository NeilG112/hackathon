"""Price-first triage and two-stage LLM refinement for hybrid risk.

Deterministic pre-calculation and candidate ranking happen here, before any
Jev call. Jev screens the bounded candidate set; Gemma refines only the
highest-scoring actionable positions. Item and calculation objects are not
modified.
"""

from __future__ import annotations

import math
from typing import Sequence

from core import constants
from core.kalkulation import CalculatedItem
from core.models import (
    AtomicLLMJudgments,
    Finding,
    HybridItemState,
    HybridRiskResult,
    LogicResult,
    NormalizedItem,
)
from core.pricer import PricedItem

_CLUSTER_RULE_FLAGS = frozenset({
    "TRENCH_VOLUME",
    "BEDDING_IN_TRENCH",
    "BACKFILL_BALANCE",
    "DIN4124_VERBAU",
    "PRESSURE_TEST",
    "SURFACE_RESTORE",
    "SHAFT_COVER_CARD",
    "DN_STEP",
    "SITE_SETUP",
})
_ITEM_RFI_SCORE_FIELDS = {
    "RFI": "unklar_beschrieben",
    "SPECULATE_UP": "nachtragspotenzial",
    "SPECULATE_DOWN": "mindermengen_risiko",
    "RFQ": "spezialgewerk",
}


def _text(item: NormalizedItem) -> str:
    return f"{item.short_text} {item.long_text}".lower()


def _format_benchmark_band(distribution: dict | None) -> str:
    if not distribution:
        return ""

    low = distribution.get("min")
    if low is None:
        low = distribution.get("p25")
    high = distribution.get("max")
    if high is None:
        high = distribution.get("p75")

    n = distribution.get("n")
    if low is not None and high is not None:
        band = f"{float(low):.2f} - {float(high):.2f} EUR"
    elif low is not None:
        band = f"{float(low):.2f} EUR"
    elif high is not None:
        band = f"{float(high):.2f} EUR"
    elif distribution.get("median") is not None:
        band = f"{float(distribution['median']):.2f} EUR"
    else:
        return ""

    if n is not None:
        band += f" (n={int(n)})"
    return band


def build_item_states(
    items: Sequence[NormalizedItem],
    calculated: Sequence[CalculatedItem],
    priced: Sequence[PricedItem],
    logic_results: dict[str, LogicResult],
) -> list[HybridItemState]:
    """Combine logic, bottom-up, and benchmark prices into triage states."""

    calculated_by_key = {entry.item.key(): entry for entry in calculated}
    priced_by_key = {entry.item.key(): entry for entry in priced}
    states: list[HybridItemState] = []

    for item in items:
        key = item.key()
        calculated_item = calculated_by_key.get(key)
        priced_item = priced_by_key.get(key)
        logic = logic_results.get(
            key,
            LogicResult(flags=[], severity="low", tags=[]),
        )

        ep_mid: float | None = None
        if (
            calculated_item is not None
            and calculated_item.priced
            and calculated_item.ep_mid is not None
        ):
            ep_mid = float(calculated_item.ep_mid)
            pre_unit_price = ep_mid
            price_source = "kalkulation"
        elif priced_item is not None and priced_item.unit_price is not None:
            pre_unit_price = float(priced_item.unit_price)
            price_source = priced_item.source
        else:
            pre_unit_price = 0.0
            price_source = "none"

        engine_divergence = 0.0
        if (
            price_source == "kalkulation"
            and ep_mid is not None
            and priced_item is not None
            and priced_item.source == "benchmark_match"
            and priced_item.similarity_score
            >= constants.HYBRID_MIN_BENCHMARK_SIMILARITY
            and priced_item.unit_price is not None
            and ep_mid > 0.0
            and float(priced_item.unit_price) > 0.0
        ):
            engine_divergence = abs(
                ep_mid - float(priced_item.unit_price)
            ) / float(priced_item.unit_price)

        text = _text(item)
        specialist_hits = [
            keyword
            for keyword in constants.SPECIALIST_KEYWORDS
            if keyword in text
        ]
        is_specialist = bool(specialist_hits or item.is_lump_sum)

        distribution = (
            priced_item.distribution
            if priced_item is not None
            else None
        )
        benchmark_band = _format_benchmark_band(distribution)

        states.append(HybridItemState(
            key=key,
            oz=item.oz,
            qty=float(item.quantity),
            unit=item.unit,
            logic_flags=list(logic.flags),
            logic_severity=logic.severity,
            logic_details=list(logic.details),
            is_specialist=is_specialist,
            specialist_hits=specialist_hits,
            pre_unit_price=pre_unit_price,
            price_source=price_source,
            euro_exposure=abs(float(item.quantity) * pre_unit_price),
            engine_divergence=engine_divergence,
            benchmark_band=benchmark_band,
        ))

    return states


def compute_priority_weight(
    state: HybridItemState,
    max_exposure: float,
) -> float:
    """Compute a deterministic ranking weight for one hybrid item state."""

    base_weight = {
        "high": 100.0,
        "medium": 35.0,
        "low": 0.0,
    }.get(state.logic_severity, 0.0)

    score = (
        base_weight
        + 15.0 * len(state.logic_flags)
        + 20.0 * len(state.specialist_hits)
    )
    if _CLUSTER_RULE_FLAGS.intersection(state.logic_flags):
        score += 1000.0

    if state.engine_divergence >= constants.HYBRID_DIVERGENCE_THRESH:
        score += 25.0

    if max_exposure > 0:
        score += 50.0 * (
            math.log1p(state.euro_exposure)
            / math.log1p(max_exposure)
        )

    return score


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])

    position = percentile * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return float(
        ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
    )


def select_top_llm_keys(
    states: Sequence[HybridItemState],
    max_llm_items: int = constants.HYBRID_MAX_LLM_ITEMS,
) -> tuple[set[str], float]:
    """Select the bounded, highest-priority candidates for an LLM pass."""

    positive_exposures = [
        state.euro_exposure
        for state in states
        if state.euro_exposure > 0
    ]
    if positive_exposures:
        top_threshold = _percentile(
            positive_exposures,
            constants.HYBRID_EXPOSURE_PERCENTILE,
        )
    else:
        top_threshold = constants.SEVERITY_HIGH_EUR

    candidates = [
        state
        for state in states
        if (
            state.logic_severity == "high"
            or bool(_CLUSTER_RULE_FLAGS.intersection(state.logic_flags))
            or state.is_specialist
            or state.engine_divergence >= constants.HYBRID_DIVERGENCE_THRESH
            or state.euro_exposure >= top_threshold
        )
    ]

    max_exposure = max(
        (state.euro_exposure for state in states),
        default=0.0,
    )
    ranked = sorted(
        candidates,
        key=lambda state: (
            -compute_priority_weight(state, max_exposure),
            -state.euro_exposure,
            state.key,
        ),
    )

    limit = max(0, int(max_llm_items))
    selected = {state.key for state in ranked[:limit]}
    return selected, top_threshold


def select_top_item_rfi_results(
    results: Sequence[HybridRiskResult],
    max_items: int = 12,
) -> list[HybridRiskResult]:
    """Rank Jev-scored actionable positions for the slower Gemma pass."""
    candidates = []
    for result in results:
        score_field = _ITEM_RFI_SCORE_FIELDS.get(result.action_type)
        if score_field is None or result.judgments is None:
            continue
        score = float(getattr(result.judgments, score_field, 0.0))
        candidates.append((result, score))

    candidates.sort(
        key=lambda entry: (
            -entry[1],
            -{"high": 2, "medium": 1}.get(entry[0].risk_level, 0),
            -entry[0].euro_exposure,
            entry[0].key,
        )
    )
    return [
        result
        for result, _score in candidates[:max(0, int(max_items))]
    ]


def classify_hybrid_risk(
    state: HybridItemState,
    judgments: AtomicLLMJudgments | None,
    top_10_pct_exposure_threshold: float,
    high_thresh: float = constants.HYBRID_HIGH_SCORE_THRESH,
    med_thresh: float = constants.HYBRID_MED_SCORE_THRESH,
) -> HybridRiskResult:
    """Combine deterministic hard signals with orthogonal atomic judgments."""

    hard_high = state.logic_severity == "high"
    exposure_high = (
        state.euro_exposure > 0
        and state.euro_exposure >= top_10_pct_exposure_threshold
    )

    scores: list[float] = []
    if judgments is not None:
        scores = [
            float(judgments.unklar_beschrieben),
            float(judgments.menge_unplausibel),
            float(judgments.preis_unplausibel),
            float(judgments.spezialgewerk),
            float(judgments.nachtragspotenzial),
            float(judgments.mindermengen_risiko),
        ]

    reasons: list[str] = []
    for detail in state.logic_details:
        if detail and detail not in reasons:
            reasons.append(detail)
    if judgments is not None:
        for dimension, reason in judgments.reasons.items():
            score = getattr(judgments, dimension, None)
            if (
                isinstance(score, (int, float))
                and float(score) > med_thresh
                and reason
                and reason not in reasons
            ):
                reasons.append(reason)

    if (
        hard_high
        or exposure_high
        or any(score > high_thresh for score in scores)
        or sum(1 for score in scores if score > med_thresh) >= 2
    ):
        risk_level = "high"
    elif (
        state.logic_severity == "medium"
        or state.is_specialist
        or state.engine_divergence >= constants.HYBRID_DIVERGENCE_THRESH
        or any(score > med_thresh for score in scores)
    ):
        risk_level = "medium"
    else:
        risk_level = "low"

    action_type: str
    strategy: str
    speculation_candidate = False

    if judgments is not None and judgments.nachtragspotenzial > high_thresh:
        action_type = "SPECULATE_UP"
        strategy = "EP erhöhen (VOB/B § 2 Abs. 3 Mehrmengen-Hebel >10 %)"
        speculation_candidate = True
    elif (
        judgments is not None
        and judgments.mindermengen_risiko > high_thresh
    ) or "ZERO_QTY" in state.logic_flags:
        action_type = "SPECULATE_DOWN"
        strategy = "EP senken (Unwahrscheinlicher Abruf / Wettbewerbshebel)"
        speculation_candidate = True
    elif judgments is not None and judgments.spezialgewerk > high_thresh:
        action_type = "RFQ"
        strategy = "Nachunternehmer-Anfrage (RFQ) vor Angebotsabgabe einholen"
    elif (
        judgments is not None
        and judgments.unklar_beschrieben > med_thresh
    ) or any(
        flag in state.logic_flags
        for flag in (
            "META_MISMATCH",
            "MISSING_SPEC",
            "SCOPE_GAP",
            "CATEGORY_MISMATCH",
        )
    ):
        action_type = "RFI"
        strategy = "Bieterfrage (RFI) an Auftraggeber/Planer stellen"
    else:
        action_type = "CHECK"
        strategy = "Kalkulationsansatz und Mengenansatz intern gegenprüfen"

    if not reasons:
        # A position can reach "high" on euro exposure alone, with no rule and
        # no judgment firing. Reporting "nothing found" there is misleading:
        # the finding IS the money. Name it, so the estimator knows why it is
        # on his list and can decide in one read.
        if exposure_high:
            reasons = [
                f"Gehört mit {state.euro_exposure:,.0f} € zu den wertvollsten "
                f"{(1 - constants.HYBRID_EXPOSURE_PERCENTILE) * 100:.0f} % der "
                "Positionen. Kein konkreter Mangel gefunden — aber hier kostet "
                "ein Fehler am meisten."
            ]
        else:
            reasons = ["Keine Auffälligkeit über den Grenzwerten."]

    return HybridRiskResult(
        key=state.key,
        risk_level=risk_level,
        euro_exposure=state.euro_exposure,
        pre_unit_price=state.pre_unit_price,
        reasons=reasons,
        strategy=strategy,
        action_type=action_type,
        speculation_candidate=speculation_candidate,
        judgments=judgments,
    )


def analyze_tender_hybrid(
    items: Sequence[NormalizedItem],
    remarks: Sequence[str],
    calculated: Sequence[CalculatedItem],
    priced: Sequence[PricedItem],
    use_jev: bool | None = None,
) -> tuple[list[HybridRiskResult], list[Finding]]:
    """Run the complete deterministic/LLM hybrid tender analysis."""

    from core import clusters as cluster_builder
    from core import deep_logic
    from core import facts as facts_module
    from core import judgments, logic, objects
    from core import detectors

    items = list(items)
    calculated = list(calculated)
    priced = list(priced)

    pre_prices: dict[str, float] = {}
    calculated_by_key = {entry.item.key(): entry for entry in calculated}
    priced_by_key = {entry.item.key(): entry for entry in priced}
    for item in items:
        key = item.key()
        calculated_item = calculated_by_key.get(key)
        if (
            calculated_item is not None
            and calculated_item.priced
            and calculated_item.ep_mid is not None
        ):
            pre_prices[key] = float(calculated_item.ep_mid)
        else:
            priced_item = priced_by_key.get(key)
            if priced_item is not None and priced_item.unit_price is not None:
                pre_prices[key] = float(priced_item.unit_price)

    rows = objects.build(items, depth=2)
    facts_by_key = {
        item.key(): facts_module.extract_facts(item)
        for item in items
    }
    clusters = cluster_builder.build_clusters(
        items,
        facts_by_key,
        calculated=calculated,
        preambles=remarks,
    )
    logic_results = logic.run_logic_engine(
        items,
        rows=rows,
        pre_prices=pre_prices,
        clusters=clusters,
        facts=facts_by_key,
        remarks=remarks,
    )
    states = build_item_states(
        items,
        calculated,
        priced,
        logic_results,
    )
    selected_keys, top_threshold = select_top_llm_keys(states)
    judgments_by_key = judgments.judge_selected_items(
        items,
        states,
        selected_keys,
        use_jev=use_jev,
    )

    item_by_key = {item.key(): item for item in items}
    hybrid_results: list[HybridRiskResult] = []

    for state in states:
        result = classify_hybrid_risk(
            state,
            judgments_by_key.get(state.key),
            top_threshold,
        )
        hybrid_results.append(result)

    state_by_key = {state.key: state for state in states}
    result_by_key = {result.key: result for result in hybrid_results}
    refinement_payloads: dict[str, dict] = {}
    refinement_candidates = select_top_item_rfi_results(hybrid_results)
    for result in refinement_candidates:
        item = item_by_key.get(result.key)
        state = state_by_key.get(result.key)
        if item is None or state is None or result.judgments is None:
            continue
        score_field = _ITEM_RFI_SCORE_FIELDS[result.action_type]
        risk_triggers = [
            {"type": "action", "value": result.action_type},
            {"type": "risk_level", "value": result.risk_level},
            *(
                {"type": "logic_rule", "value": flag}
                for flag in state.logic_flags
            ),
            *(
                {"type": "logic_detail", "value": detail}
                for detail in state.logic_details
            ),
        ]
        for dimension in (
            "unklar_beschrieben",
            "menge_unplausibel",
            "preis_unplausibel",
            "spezialgewerk",
            "nachtragspotenzial",
            "mindermengen_risiko",
        ):
            probability = float(getattr(result.judgments, dimension))
            if probability <= constants.HYBRID_MED_SCORE_THRESH:
                continue
            risk_triggers.append({
                "type": "jev_score",
                "name": dimension,
                "probability": probability,
                "reason": result.judgments.reasons.get(dimension, ""),
            })
        risk_triggers.append({
            "type": "primary_jev_score",
            "name": score_field,
            "probability": float(getattr(result.judgments, score_field)),
        })
        refinement_payloads[result.key] = {
            "oz": item.oz,
            "short_text": item.short_text,
            "long_text": item.long_text,
            "quantity": item.quantity,
            "unit": item.unit,
            "remarks": list(remarks),
            "risk_triggers": risk_triggers,
        }

    refinements = (
        deep_logic.evaluate_item_rfis(refinement_payloads)
        if refinement_payloads
        else {}
    )
    for key, refinement in refinements.items():
        result = result_by_key.get(key)
        if result is None:
            continue
        commercial_reason = refinement.get("commercial_reason_de", "").strip()
        bidder_question = refinement.get("bidder_question_de", "").strip()
        if not commercial_reason or not bidder_question:
            continue
        static_jev_reasons = (
            set(result.judgments.reasons.values())
            if result.judgments is not None
            else set()
        )
        result.reasons = [
            reason
            for reason in result.reasons
            if (
                reason not in static_jev_reasons
                and reason != "Keine Auffälligkeit über den Grenzwerten."
            )
        ]
        if commercial_reason not in result.reasons:
            result.reasons.append(commercial_reason)
        if result.judgments is not None:
            result.judgments.reasons = {}

    findings: list[Finding] = []
    for state in states:
        result = result_by_key[state.key]
        item = item_by_key.get(state.key)
        if item is None or not (
            result.risk_level in ("high", "medium")
            or state.key in refinements
        ):
            continue
        finding = result.to_finding(item)
        refinement = refinements.get(state.key)
        if refinement is not None:
            finding.evidence["commercial_reason_de"] = (
                refinement["commercial_reason_de"]
            )
            finding.evidence["bidder_question_de"] = (
                refinement["bidder_question_de"]
            )
        findings.append(finding)

    rfi_keys = {
        result.key
        for result in hybrid_results
        if result.action_type == "RFI"
    }
    findings.extend(
        finding
        for finding in detectors.vague_scope(priced, remarks)
        if finding.item.key() not in rfi_keys
    )
    severity_index = {
        severity: index
        for index, severity in enumerate(constants.SEVERITY_ORDER)
    }
    findings.sort(
        key=lambda finding: (
            severity_index.get(finding.severity, len(severity_index)),
            -finding.euro_leverage,
        )
    )
    return hybrid_results, findings
