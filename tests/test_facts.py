import unittest

from core.facts import extract_facts
from core.models import NormalizedItem


def item(text: str) -> NormalizedItem:
    return NormalizedItem(
        oz="01.02",
        quantity=1,
        unit="m",
        short_text=text,
    )


class PositionFactsTests(unittest.TestCase):
    def test_extract_pipe_facts(self):
        facts = extract_facts(item(
            "Druckrohr PE100 TW DN/OD63 SDR11 Graben verbaut T 1,25-1,75m"
        ))

        self.assertEqual(facts.dn, 63)
        self.assertEqual(facts.material, "PE100")
        self.assertEqual(facts.depth_m, 1.5)
        self.assertEqual(facts.phase, "montage")
        self.assertEqual(facts.confidence, 1.0)
        self.assertEqual(facts.source, "regex")

    def test_extract_shoring_depth(self):
        facts = extract_facts(item(
            "Grabenverbaugeraet H 3-3,5m Sohlen-/Stirnverbau"
        ))

        self.assertEqual(facts.depth_m, 3.25)
        self.assertEqual(facts.phase, "vorbereitung")

    def test_extract_bedding_facts(self):
        facts = extract_facts(item(
            "Kies-Sand-Gemisch Einbettung Rohr DN300-400 einbauen verdichten D 15-20cm"
        ))

        self.assertEqual(facts.dn, 300)
        self.assertEqual(facts.thickness_cm, 15.0)
        self.assertEqual(facts.phase, "vorbereitung")

    def test_pn_depth_and_inclusive_terms(self):
        facts = extract_facts(item(
            "PE-HD Leitung PN16 Tiefe bis 2,50 m, einschl. Muffen und Formteile"
        ))

        self.assertEqual(facts.pn, 16.0)
        self.assertEqual(facts.depth_m, 2.5)
        self.assertEqual(facts.material, "PE-HD")
        self.assertTrue(facts.inclusive_terms)
        self.assertTrue(facts.inclusive_terms[0].startswith("muffen"))

    def test_h_height_is_not_graben_depth_on_bridge(self):
        facts = extract_facts(item(
            "Leitungsbehelfsbruecke L 10-15m H 4,5-5m"
        ))
        self.assertIsNone(facts.depth_m)

    def test_h_height_is_graben_depth_for_shoring(self):
        facts = extract_facts(item(
            "Grabenverbaugeraet H 3-3,5m Sohlen-/Stirnverbau"
        ))
        self.assertEqual(facts.depth_m, 3.25)

    def test_facts_serialization_round_trip(self):
        facts = extract_facts(item("Betonfundament einschliesslich Bewehrung"))
        restored = type(facts).from_dict(facts.as_dict())

        self.assertEqual(restored, facts)
        self.assertEqual(
            restored.as_dict()["inclusive_terms"],
            list(facts.inclusive_terms),
        )


if __name__ == "__main__":
    unittest.main()
