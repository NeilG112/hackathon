import unittest

import export_rfi
from core.models import Finding, NormalizedItem


class ExportRfiClusterTests(unittest.TestCase):
    def test_position_export_prefers_generated_bidder_question(self):
        item = NormalizedItem(
            oz="10003",
            oz_parts=("1", "0003"),
            quantity=1,
            unit="St",
            short_text="Spezialposition",
        )
        finding = Finding(
            item=item,
            detector="hybrid_risk",
            severity="high",
            rationale="Statische Begründung",
            evidence={
                "bidder_question_de": (
                    "Bitte konkretisieren Sie den Leistungsumfang der Position."
                ),
            },
        )

        catalog = export_rfi.build_catalog([finding], {"title": "Test"})

        self.assertEqual(catalog[0]["oz"], "1.0003")
        self.assertEqual(
            catalog[0]["frage"],
            "Bitte konkretisieren Sie den Leistungsumfang der Position.",
        )

    def test_cluster_questions_precede_position_questions(self):
        item = NormalizedItem(
            oz="0101",
            quantity=10,
            unit="m",
            short_text="Rohr verlegen",
        )
        finding = Finding(
            item=item,
            detector="qty_sanity",
            severity="medium",
            rationale="Menge pruefen",
            euro_leverage=500.0,
        )
        evaluations = {
            "sec:12345678": {
                "contradiction_category": "QUANTITY_CONFLICT",
                "severity": "high",
                "reason_de": "Mengen widersprechen sich.",
                "affected_positions": ["0101"],
                "offline": False,
                "cluster_title": "Haupttrasse",
                "euro_exposure_estimate": 9000.0,
                "din_ref": "DIN 4124",
            }
        }

        catalog = export_rfi.build_catalog(
            [finding],
            {"title": "Test"},
            cluster_evaluations=evaluations,
        )

        self.assertEqual(catalog[0]["group"], "cluster")
        self.assertEqual(catalog[0]["cluster_title"], "Haupttrasse")
        self.assertEqual(catalog[0]["affected_ozs"], ["0101"])

        markdown = export_rfi.to_markdown(catalog, {"title": "Test"})
        self.assertIn("Fragen zu Bauabschnitten", markdown)
        self.assertIn("Fragen zu Einzelpositionen", markdown)

    def test_markdown_export_renders_nu_requests_separately(self):
        markdown = export_rfi.to_markdown([{
            "nr": 1,
            "oz": "1.0003",
            "kurztext": "Schacht setzen",
            "menge": "1",
            "einheit": "St",
            "frage": "Bitte bieten Sie das Setzen des Schachts an.",
            "group": "rfq",
        }], {"title": "Export"})

        self.assertIn("## Nachunternehmer-Anfragen", markdown)
        self.assertIn("Anfrage an Nachunternehmer", markdown)
        self.assertIn("Bitte bieten Sie das Setzen des Schachts an.", markdown)


if __name__ == "__main__":
    unittest.main()
