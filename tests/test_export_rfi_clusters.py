import unittest

import export_rfi
from core.models import Finding, NormalizedItem


class ExportRfiClusterTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
