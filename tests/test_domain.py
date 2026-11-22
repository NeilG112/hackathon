import unittest

from core.clusters import build_clusters
from core.domain import detect_lv_domains
from core.facts import extract_facts
from core.logic import check_cluster_rules
from core.models import NormalizedItem


def item(oz: str, text: str, section: str = "Gewerk") -> NormalizedItem:
    return NormalizedItem(
        oz=oz,
        quantity=1,
        unit="m",
        section_path=(section, "Bereich"),
        short_text=text,
    )


def clusters_for(items, domains=None):
    facts = {position.key(): extract_facts(position) for position in items}
    clusters = build_clusters(items, facts, domains=domains)
    for cluster in clusters:
        if cluster.kind == "SECTION":
            cluster.euro_exposure = 10000.0
    return facts, clusters


class DomainDetectionTests(unittest.TestCase):
    def test_detects_domains_from_positions_and_preambles(self):
        examples = (
            (item("01", "Leitungsgraben ausheben"), set(), {"TIEFBAU"}),
            (item("02", "Schalung und Bewehrung"), set(), {"HOCHBAU_ROHBAU"}),
            (item("03", "Trockenbauwand F90"), set(), {"AUSBAU"}),
            (item("04", "Kabel 5x2,5 400V"), set(), {"TGA_ELEKTRO"}),
            (item("05", "Heizungsleitung dämmen"), set(), {"TGA_SHK"}),
            (item("06", "Allgemeine Leistung"), ["Gewerk: Elektroinstallation"], {"TGA_ELEKTRO"}),
        )
        for position, preambles, expected in examples:
            with self.subTest(text=position.short_text, preambles=preambles):
                self.assertEqual(detect_lv_domains([position], preambles), expected)

    def test_unknown_lv_has_no_guessed_domain(self):
        position = item("01", "Allgemeine Leistung ohne Fachsignal")
        self.assertEqual(detect_lv_domains([position], []), set())

    def test_domain_frames_are_gated_but_universal_frames_remain(self):
        items = [
            item("01", "Bauzaun aufstellen"),
            item("02", "Wasserhaltung betreiben"),
            item("03", "Gerüststellung"),
            item("04", "Brandschottung herstellen"),
            item("05", "Inbetriebnahme durchführen"),
            item("06", "Bestandsplan erstellen"),
        ]
        facts, unknown_clusters = clusters_for(items, domains=set())
        unknown_frames = {
            cluster.title for cluster in unknown_clusters if cluster.kind == "FRAME"
        }
        self.assertIn("Baustelleneinrichtung", unknown_frames)
        self.assertIn("Dokumentation & Revision", unknown_frames)
        self.assertNotIn("Wasserhaltung", unknown_frames)
        self.assertNotIn("Gerüstbau & Absturzsicherung", unknown_frames)
        self.assertNotIn("Brandschutzabschottung & Bauendreinigung", unknown_frames)
        self.assertNotIn("Prüfung & Inbetriebnahme", unknown_frames)

        _, trade_clusters = clusters_for(
            items,
            domains={
                "TIEFBAU", "HOCHBAU_ROHBAU", "TGA_ELEKTRO",
            },
        )
        trade_frames = {
            cluster.title for cluster in trade_clusters if cluster.kind == "FRAME"
        }
        self.assertIn("Wasserhaltung", trade_frames)
        self.assertIn("Gerüstbau & Absturzsicherung", trade_frames)
        self.assertIn("Brandschutzabschottung & Bauendreinigung", trade_frames)
        self.assertIn("Prüfung & Inbetriebnahme", trade_frames)


class DomainRuleTests(unittest.TestCase):
    def _rule_ids(self, texts, section):
        positions = [item(f"{index:02}", text, section) for index, text in enumerate(texts, 1)]
        facts, clusters = clusters_for(positions)
        return {
            flag.rule_id
            for flag in check_cluster_rules(clusters, positions, facts)
        }

    def test_domain_completeness_rules_flag_clear_missing_signals(self):
        cases = (
            ("DIN18331_MISSING_CONCRETE", ["Schalung für Decke herstellen"], "Rohbau"),
            ("DIN18330_SCAFFOLD_MISSING", ["Mauerwerk bis 3,00 m Höhe herstellen"], "Mauerwerk"),
            ("DIN18533_PROTECTION_MISSING", ["Erdberührte Abdichtung Kellerwand"], "Abdichtung"),
            ("DIN18340_DRYWALL_FIRE_SPEC", ["F90 Trockenbauwand herstellen"], "Trockenbau"),
            ("DIN18353_SCREED_COMPONENTS", ["Estrich auf Fußbodenheizung herstellen"], "Estrich"),
            ("MLAR_FIRE_STOP_MISSING", ["Kabel durch Brandabschnitt verlegen"], "Elektro"),
            ("DIN_VDE_0100_600_TEST", ["Stromkreis in Unterverteilung herstellen"], "Verteilung"),
            ("ELECTRO_LIGHTING_CONNECTION", ["LED-Leuchte liefern"], "Leuchten"),
            ("GEG_PIPE_INSULATION", ["Heizungsleitung verlegen"], "Heizung"),
            ("DIN18380_HYDRAULIC_BALANCE", ["Heizungsnetz herstellen"], "Heizungsnetz"),
            ("DIN_EN_806_POTABLE_WATER_TEST", ["Trinkwasserleitung verlegen"], "Trinkwasser"),
        )
        for rule_id, texts, section in cases:
            with self.subTest(rule=rule_id):
                self.assertIn(rule_id, self._rule_ids(texts, section))

    def test_domain_rules_accept_explicit_companion_signals(self):
        cases = (
            ("DIN18331_MISSING_CONCRETE", ["Schalung für Decke", "Ortbeton Decke"], "Rohbau"),
            ("DIN18330_SCAFFOLD_MISSING", ["Mauerwerk bis 3,00 m Höhe", "Arbeitsgerüst"], "Mauerwerk"),
            ("DIN18533_PROTECTION_MISSING", ["Erdberührte Abdichtung Kellerwand", "Schutzlage mit Drainage"], "Abdichtung"),
            ("DIN18340_DRYWALL_FIRE_SPEC", ["F90 Trockenbauwand", "Systemaufbau mit Ständerwerk, Spachtelgüte Q3"], "Trockenbau"),
            ("DIN18353_SCREED_COMPONENTS", ["Estrich auf Fußbodenheizung", "Randdämmstreifen, Trittschalldämmung, Aufheizprotokoll"], "Estrich"),
            ("MLAR_FIRE_STOP_MISSING", ["Kabel durch Brandabschnitt", "Brandschott herstellen"], "Elektro"),
            ("DIN_VDE_0100_600_TEST", ["Stromkreis in Unterverteilung", "Erstprüfung und Messprotokoll nach VDE 0100-600"], "Verteilung"),
            ("ELECTRO_LIGHTING_CONNECTION", ["LED-Leuchte liefern", "Montage und Anschluss der Leuchte"], "Leuchten"),
            ("GEG_PIPE_INSULATION", ["Heizungsleitung verlegen", "Wärmedämmung der Leitungen nach GEG"], "Heizung"),
            ("DIN18380_HYDRAULIC_BALANCE", ["Heizungsnetz herstellen", "Hydraulischer Abgleich durchführen"], "Heizungsnetz"),
            ("DIN_EN_806_POTABLE_WATER_TEST", ["Trinkwasserleitung verlegen", "Druckprobe, Spülung und Hygiene-Nachweis"], "Trinkwasser"),
        )
        for rule_id, texts, section in cases:
            with self.subTest(rule=rule_id):
                self.assertNotIn(rule_id, self._rule_ids(texts, section))

    def test_unknown_domain_still_runs_common_rules(self):
        positions = [item("01", "Allgemeine Leistung ohne Fachsignal")]
        facts, clusters = clusters_for(positions, domains=set())
        rule_ids = {
            flag.rule_id
            for flag in check_cluster_rules(clusters, positions, facts, domains=set())
        }
        self.assertIn("SITE_SETUP", rule_ids)
        self.assertFalse(any(rule_id in rule_ids for rule_id in (
            "DIN18331_MISSING_CONCRETE", "DIN18330_SCAFFOLD_MISSING",
            "DIN18340_DRYWALL_FIRE_SPEC", "MLAR_FIRE_STOP_MISSING",
        )))


if __name__ == "__main__":
    unittest.main()
