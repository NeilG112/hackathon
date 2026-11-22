import unittest

from core.kalkulation import calculate_item
from core.models import NormalizedItem
from core.stammdaten import Company, Leistung, Stammdaten


class CalculationUnitBridgeTests(unittest.TestCase):
    def setUp(self):
        self.company = Company(mittellohn_eur_h=10.0, zuschlag_pct=0.0)
        self.data = Stammdaten({}, {}, {})
        self.leistung = Leistung(
            code="L1",
            gewerk="Tiefbau",
            taetigkeit="Leitung verlegen",
            einheit="m",
            h_min=1.0,
            h_mittel=1.0,
            h_max=1.0,
        )

    def test_compatible_length_units_convert_rate_and_breakdown(self):
        item = NormalizedItem(
            oz="01",
            quantity=100.0,
            unit="cm",
            short_text="Leitung verlegen",
        )

        calculated = calculate_item(
            item,
            self.leistung,
            self.company,
            self.data,
        )

        self.assertTrue(calculated.priced)
        self.assertAlmostEqual(calculated.ep_mid, 0.1)
        self.assertAlmostEqual(calculated.total, 10.0)
        self.assertAlmostEqual(calculated.breakdown.labour_hours, 0.01)
        self.assertIn("Einheitenbrücke m → cm", calculated.note)

    def test_piece_and_lump_sum_bridge_only_at_quantity_one(self):
        item = NormalizedItem(
            oz="02",
            quantity=1.0,
            unit="St",
            short_text="Leitung verlegen",
        )
        lump_sum = Leistung(
            code="L2",
            gewerk="Tiefbau",
            taetigkeit="Leistung komplett",
            einheit="psch",
            h_min=1.0,
            h_mittel=1.0,
            h_max=1.0,
        )

        calculated = calculate_item(item, lump_sum, self.company, self.data)

        self.assertTrue(calculated.priced)
        self.assertEqual(calculated.ep_mid, 10.0)

        item.quantity = 2.0
        fallback = calculate_item(item, lump_sum, self.company, self.data)
        self.assertFalse(fallback.priced)
        self.assertIn("Fallback über pricer.py erforderlich", fallback.note)

    def test_incompatible_units_are_marked_for_pricer_fallback(self):
        item = NormalizedItem(
            oz="03",
            quantity=2.0,
            unit="St",
            short_text="Leitung verlegen",
        )

        calculated = calculate_item(
            item,
            self.leistung,
            self.company,
            self.data,
        )

        self.assertFalse(calculated.priced)
        self.assertIn("Fallback über pricer.py erforderlich", calculated.note)


if __name__ == "__main__":
    unittest.main()
