import unittest

from core.models import NormalizedItem
from core.pricer import nearest_comparables


class PricerDimensionTests(unittest.TestCase):
    def test_dimensions_prevent_large_dn_and_section_mismatches(self):
        item = NormalizedItem(
            oz="01",
            quantity=1.0,
            unit="m",
            short_text="Druckrohr Trinkwasser PE100 DN300 PN16 D20cm",
        )
        reference = {
            "items": [
                {
                    "text": "Druckrohr Trinkwasser PE100 DN50 PN6 D2cm",
                    "unit": "m",
                    "ep": 12.0,
                },
                {
                    "text": "Druckrohr Trinkwasser PE100 DN300 PN16 D20cm",
                    "unit": "m",
                    "ep": 300.0,
                },
            ],
        }

        matches = nearest_comparables(item, reference, "m")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][1], 300.0)
        self.assertEqual(matches[0][2], reference["items"][1]["text"])


if __name__ == "__main__":
    unittest.main()
