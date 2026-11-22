import unittest
from unittest.mock import patch

from core.kalkulation import CalculatedItem
from core import constants
from core.models import (
    AtomicLLMJudgments,
    HybridItemState,
    HybridRiskResult,
    NormalizedItem,
)
from core.pricer import PricedItem
from core.risk_engine import (
    analyze_tender_hybrid,
    build_item_states,
    select_top_item_rfi_results,
    select_top_llm_keys,
)


def _state(
    key: str,
    exposure: float,
    logic_flags: list[str] | None = None,
    logic_severity: str = "low",
) -> HybridItemState:
    return HybridItemState(
        key=key,
        oz=key,
        qty=1.0,
        unit="m",
        logic_flags=logic_flags or [],
        logic_severity=logic_severity,
        logic_details=[],
        is_specialist=False,
        specialist_hits=[],
        pre_unit_price=exposure,
        price_source="test",
        euro_exposure=exposure,
    )


class HybridRiskEngineTests(unittest.TestCase):
    def test_cluster_rule_reaches_hybrid_result_offline(self):
        item = NormalizedItem(
            oz="01",
            quantity=100.0,
            unit="m",
            short_text="Leitungsgraben Tiefe bis 1,50 m",
        )
        calculated = [CalculatedItem(item=item, leistung=None, ep_mid=30.0)]

        with patch("core.classify.jev_available", return_value=False):
            results, _findings = analyze_tender_hybrid(
                [item],
                [],
                calculated,
                [],
            )

        result = next(result for result in results if result.key == item.key())
        self.assertTrue(any("DIN4124_VERBAU" in reason for reason in result.reasons))
        self.assertEqual(result.risk_level, "high")

    def test_cluster_findings_are_prioritized_for_jev_triage(self):
        states = [_state(f"position-{index:02d}", 1000.0) for index in range(61)]
        states.append(_state(
            "cluster-position",
            1.0,
            logic_flags=["DN_STEP"],
            logic_severity="medium",
        ))

        selected, _threshold = select_top_llm_keys(states, max_llm_items=60)

        self.assertIn("cluster-position", selected)
        self.assertEqual(len(selected), 60)

    def test_item_rfi_selection_ranks_jev_scores_and_caps_at_twelve(self):
        results = [
            HybridRiskResult(
                key=f"item-{index:02d}",
                risk_level="medium",
                euro_exposure=100.0,
                pre_unit_price=100.0,
                reasons=[],
                strategy="",
                action_type="RFI",
                speculation_candidate=False,
                judgments=AtomicLLMJudgments(
                    unklar_beschrieben=0.95 - index * 0.02,
                    menge_unplausibel=0.0,
                    preis_unplausibel=0.0,
                    spezialgewerk=0.0,
                    nachtragspotenzial=0.0,
                ),
            )
            for index in range(14)
        ]
        results.append(HybridRiskResult(
            key="not-jev-scored",
            risk_level="high",
            euro_exposure=10000.0,
            pre_unit_price=10000.0,
            reasons=[],
            strategy="",
            action_type="RFQ",
            speculation_candidate=False,
        ))

        selected = select_top_item_rfi_results(results)

        self.assertEqual(len(selected), 12)
        self.assertEqual(selected[0].key, "item-00")
        self.assertNotIn("item-12", {result.key for result in selected})
        self.assertNotIn("not-jev-scored", {result.key for result in selected})

    def test_item_rfi_score_uses_the_action_specific_jev_dimension(self):
        primary_scores = (
            ("RFI", "unklar_beschrieben", 0.51),
            ("SPECULATE_UP", "nachtragspotenzial", 0.95),
            ("SPECULATE_DOWN", "mindermengen_risiko", 0.70),
            ("RFQ", "spezialgewerk", 0.80),
        )
        results = []
        for index, (action, dimension, score) in enumerate(primary_scores):
            scores = {
                "unklar_beschrieben": 0.99,
                "menge_unplausibel": 0.0,
                "preis_unplausibel": 0.0,
                "spezialgewerk": 0.0,
                "nachtragspotenzial": 0.0,
                "mindermengen_risiko": 0.0,
            }
            scores[dimension] = score
            results.append(HybridRiskResult(
                key=f"item-{index}",
                risk_level="high",
                euro_exposure=100.0,
                pre_unit_price=100.0,
                reasons=[],
                strategy="",
                action_type=action,
                speculation_candidate=False,
                judgments=AtomicLLMJudgments(**scores),
            ))

        selected = select_top_item_rfi_results(results, max_items=4)

        self.assertEqual(
            [result.action_type for result in selected],
            ["SPECULATE_UP", "RFQ", "SPECULATE_DOWN", "RFI"],
        )

    def test_gemma_reason_replaces_jev_template_and_question_reaches_export(self):
        item = NormalizedItem(
            oz="04",
            quantity=10.0,
            unit="m",
            short_text="Leitung herstellen",
            long_text="Anschluss an Bestand nach Vorgabe.",
        )
        judgment = AtomicLLMJudgments(
            unklar_beschrieben=0.8,
            menge_unplausibel=0.0,
            preis_unplausibel=0.0,
            spezialgewerk=0.0,
            nachtragspotenzial=0.0,
            reasons={"unklar_beschrieben": "Statischer Jev-Text."},
        )
        generated = {
            "commercial_reason_de": (
                "Der Bestandsanschluss ist kaufmännisch nicht abgegrenzt."
            ),
            "bidder_question_de": (
                "Bitte benennen Sie die einzurechnende Anschlussstelle."
            ),
        }
        priced = [PricedItem(
            item=item,
            unit_price=100.0,
            total=1000.0,
            source="fallback_rate",
        )]
        with patch(
            "core.judgments.judge_selected_items",
            return_value={item.key(): judgment},
        ):
            with patch(
                "core.deep_logic.evaluate_item_rfis",
                return_value={item.key(): generated},
            ) as refine:
                results, findings = analyze_tender_hybrid(
                    [item],
                    ["Bestandsanschluss ist durch den Auftraggeber festzulegen."],
                    [],
                    priced,
                    use_jev=True,
                )

        result = next(result for result in results if result.key == item.key())
        self.assertEqual(result.action_type, "RFI")
        self.assertIn(generated["commercial_reason_de"], result.reasons)
        self.assertNotIn("Statischer Jev-Text.", result.reasons)
        self.assertEqual(result.judgments.reasons, {})
        finding = next(
            finding for finding in findings
            if finding.item.key() == item.key()
            and finding.detector == "hybrid_risk"
        )
        self.assertEqual(
            finding.evidence["bidder_question_de"],
            generated["bidder_question_de"],
        )
        refine.assert_called_once()
        payload = refine.call_args.args[0][item.key()]
        self.assertEqual(payload["oz"], item.oz)
        self.assertEqual(payload["short_text"], item.short_text)
        self.assertEqual(payload["long_text"], item.long_text)
        self.assertEqual(payload["quantity"], item.quantity)
        self.assertEqual(payload["unit"], item.unit)
        self.assertEqual(
            payload["remarks"],
            ["Bestandsanschluss ist durch den Auftraggeber festzulegen."],
        )
        self.assertTrue(any(
            trigger["type"] == "jev_score"
            for trigger in payload["risk_triggers"]
        ))

    def test_rfi_position_is_not_duplicated_by_vague_scope_detector(self):
        item = NormalizedItem(
            oz="02",
            quantity=10.0,
            unit="m",
            short_text="Rohr nach Bedarf liefern",
        )
        priced = [
            PricedItem(
                item=item,
                unit_price=100.0,
                total=1000.0,
                source="fallback_rate",
            )
        ]
        remarks = ["Leistung nach Bedarf des Auftraggebers."]

        with patch("core.classify.jev_available", return_value=False):
            results, findings = analyze_tender_hybrid(
                [item],
                remarks,
                [],
                priced,
            )

        result = next(result for result in results if result.key == item.key())
        self.assertEqual(result.action_type, "RFI")
        item_findings = [
            finding for finding in findings
            if finding.item.key() == item.key()
        ]
        self.assertEqual(len(item_findings), 1)
        self.assertEqual(item_findings[0].detector, "hybrid_risk")
        self.assertTrue(any(
            finding.detector == "vague_scope"
            and finding.item.key() != item.key()
            for finding in findings
        ))

    def test_engine_divergence_requires_high_similarity_tier_one_match(self):
        item = NormalizedItem(
            oz="03",
            quantity=1.0,
            unit="m",
            short_text="Rohrleitung Trinkwasser DN100",
        )
        calculated = [CalculatedItem(item=item, leistung=None, ep_mid=100.0)]

        def divergence(source, similarity_score):
            priced = [PricedItem(
                item=item,
                unit_price=200.0,
                total=200.0,
                source=source,
                similarity_score=similarity_score,
            )]
            return build_item_states(
                [item],
                calculated,
                priced,
                {},
            )[0].engine_divergence

        self.assertEqual(constants.HYBRID_DIVERGENCE_THRESH, 0.40)
        self.assertAlmostEqual(divergence("benchmark_match", 0.8), 0.5)
        self.assertEqual(divergence("benchmark_match", 0.5), 0.0)
        self.assertEqual(divergence("benchmark_unit", 1.0), 0.0)


if __name__ == "__main__":
    unittest.main()
