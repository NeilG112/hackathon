import unittest
from types import SimpleNamespace

from core.clusters import build_clusters
from core.facts import extract_facts
from core.logic import (
    RULES,
    RULES_VERSION,
    UnitBridge,
    _subject_suppressed,
    check_cluster_rules,
    run_logic_engine,
    suppressed_by_remarks,
)
from core.models import NormalizedItem


def item(oz: str, text: str, section: str = "Trasse") -> NormalizedItem:
    return NormalizedItem(
        oz=oz,
        quantity=1,
        unit="m",
        section_path=(section, "Bereich"),
        short_text=text,
    )


def cluster_for(items, facts, extra=None):
    from core.clusters import build_clusters
    calculated = extra
    clusters = build_clusters(items, facts, calculated)
    for cluster in clusters:
        if cluster.kind == "SECTION" and cluster.euro_exposure == 0.0:
            cluster.euro_exposure = 10000.0
        if cluster.kind == "SYSTEM" and cluster.euro_exposure == 0.0:
            cluster.euro_exposure = 10000.0
    return clusters


class PositionRuleTests(unittest.TestCase):
    def test_volume_unit_rule_matches_specific_excavation_terms_only(self):
        area_positions = [
            item("01", "Bodenbelag", "Fläche"),
            item("02", "Oberboden", "Fläche"),
            item("03", "Bodenplatte", "Fläche"),
            item("04", "Fußboden", "Fläche"),
        ]
        for position in area_positions:
            position.unit = "m²"
            result = run_logic_engine([position])[position.key()]
            with self.subTest(text=position.short_text):
                self.assertNotIn("QTY_OUTLIER", result.flags)

        excavation_positions = [
            item("11", "Bodenaushub", "Erdbau"),
            item("12", "Erdaushub", "Erdbau"),
            item("13", "Baugrubenaushub", "Erdbau"),
            item("14", "Grabenaushub", "Erdbau"),
        ]
        for position in excavation_positions:
            position.unit = "m²"
            result = run_logic_engine([position])[position.key()]
            with self.subTest(text=position.short_text):
                self.assertIn("QTY_OUTLIER", result.flags)


class ClusterRuleTests(unittest.TestCase):
    def test_unit_bridge_corridor(self):
        bridge = UnitBridge("m", "m3", 0.8, 1.2, "breite_m_x_tiefe_m")
        self.assertEqual(bridge.corridor(10.0), (8.0, 12.0))

    def test_rules_catalogue_and_version(self):
        ids = {rule.id for rule in RULES}
        self.assertIn("TRENCH_VOLUME", ids)
        self.assertIn("DIN4124_VERBAU", ids)
        self.assertEqual(RULES_VERSION, "2")

    def test_trench_positive_and_inclusive_negative(self):
        positive = [
            item("01", "Leitungsgraben DN63 T 1,25-1,75m", "Trasse"),
            item("02", "Bodenaushub", "Trasse"),
        ]
        positive[0].unit = "m"
        positive[0].quantity = 100
        positive[1].unit = "m3"
        positive[1].quantity = 500
        facts = {i.key(): extract_facts(i) for i in positive}
        clusters = cluster_for(positive, facts)
        flags = check_cluster_rules(clusters, positive, facts)
        self.assertTrue(any(flag.rule_id == "TRENCH_VOLUME" for flag in flags))

        negative = [
            item("11", "Leitungsgraben inkl. Bodenaushub T 1,25-1,75m", "Trasse"),
            item("12", "Bodenaushub", "Trasse"),
        ]
        negative[0].quantity = 100
        negative[0].unit = "m"
        negative[1].quantity = 500
        negative[1].unit = "m3"
        facts = {i.key(): extract_facts(i) for i in negative}
        clusters = cluster_for(negative, facts)
        flags = check_cluster_rules(clusters, negative, facts)
        self.assertFalse(any(flag.rule_id == "TRENCH_VOLUME" for flag in flags))

        same_tag = [
            item("13", "Leitungsgraben herstellen", "Trasse"),
            item("14", "Leitungsgraben ausheben", "Trasse"),
        ]
        same_tag[0].unit = "m"
        same_tag[0].quantity = 100
        same_tag[1].unit = "m3"
        same_tag[1].quantity = 500
        facts = {i.key(): extract_facts(i) for i in same_tag}
        clusters = cluster_for(same_tag, facts)
        flags = check_cluster_rules(clusters, same_tag, facts)
        self.assertTrue(any(flag.rule_id == "TRENCH_VOLUME" for flag in flags))

    def test_bedding_positive_and_negative(self):
        positive = [
            item("21", "Bettung", "A"), item("22", "Bodenaushub", "A")
        ]
        positive[0].unit = "m3"
        positive[0].quantity = 10
        positive[1].unit = "m3"
        positive[1].quantity = 5
        facts = {i.key(): extract_facts(i) for i in positive}
        flags = check_cluster_rules(cluster_for(positive, facts), positive, facts)
        self.assertTrue(any(f.rule_id == "BEDDING_IN_TRENCH" for f in flags))

        negative = [
            item("23", "Bettung einschliesslich Bodenaushub", "A"),
            item("24", "Bodenaushub", "A"),
        ]
        negative[0].unit = "m3"
        negative[0].quantity = 10
        negative[1].unit = "m3"
        negative[1].quantity = 5
        facts = {i.key(): extract_facts(i) for i in negative}
        flags = check_cluster_rules(cluster_for(negative, facts), negative, facts)
        self.assertFalse(any(f.rule_id == "BEDDING_IN_TRENCH" for f in flags))

    def test_backfill_positive_and_negative(self):
        positive = [
            item("31", "Verfüllung", "A"), item("32", "Bodenaushub", "A")
        ]
        positive[0].unit = "m3"
        positive[0].quantity = 10
        positive[1].unit = "m3"
        positive[1].quantity = 5
        facts = {i.key(): extract_facts(i) for i in positive}
        self.assertEqual(facts[positive[0].key()].object_tag, "Verfüllung")
        flags = check_cluster_rules(cluster_for(positive, facts), positive, facts)
        self.assertTrue(any(f.rule_id == "BACKFILL_BALANCE" for f in flags))

        negative = [
            item("33", "Verfuellung einschl. Bodenaushub", "A"),
            item("34", "Bodenaushub", "A"),
        ]
        negative[0].unit = "m3"
        negative[0].quantity = 10
        negative[1].unit = "m3"
        negative[1].quantity = 5
        facts = {i.key(): extract_facts(i) for i in negative}
        flags = check_cluster_rules(cluster_for(negative, facts), negative, facts)
        self.assertFalse(any(f.rule_id == "BACKFILL_BALANCE" for f in flags))

        piece_units = [
            item("35", "Verfuellung", "A"),
            item("36", "Bodenaushub", "A"),
        ]
        piece_units[0].unit = "St"
        piece_units[0].quantity = 10
        piece_units[1].unit = "St"
        piece_units[1].quantity = 1
        facts = {i.key(): extract_facts(i) for i in piece_units}
        flags = check_cluster_rules(cluster_for(piece_units, facts), piece_units, facts)
        self.assertFalse(any(f.rule_id == "BACKFILL_BALANCE" for f in flags))

    def test_din4124_positive_and_negative(self):
        positive = [item("41", "Leitungsgraben T 2,00-2,50m")]
        facts = {i.key(): extract_facts(i) for i in positive}
        flags = check_cluster_rules(cluster_for(positive, facts), positive, facts)
        self.assertTrue(any(f.rule_id == "DIN4124_VERBAU" for f in flags))

        negative = [item("42", "Leitungsgraben inkl. Verbau T 2,00-2,50m")]
        facts = {i.key(): extract_facts(i) for i in negative}
        flags = check_cluster_rules(cluster_for(negative, facts), negative, facts)
        self.assertFalse(any(f.rule_id == "DIN4124_VERBAU" for f in flags))

        verbau_position = [item("43", "Grabenverbaugeraet H 3-3,5m")]
        facts = {i.key(): extract_facts(i) for i in verbau_position}
        flags = check_cluster_rules(
            cluster_for(verbau_position, facts),
            verbau_position,
            facts,
        )
        self.assertFalse(any(f.rule_id == "DIN4124_VERBAU" for f in flags))

    def test_din4124_flags_are_attached_to_each_section(self):
        items = [
            item("44", "Leitungsgraben Tiefe bis 1,50 m", "Abschnitt A"),
            item("45", "Leitungsgraben Tiefe bis 2,00 m", "Abschnitt B"),
        ]
        facts = {position.key(): extract_facts(position) for position in items}
        sections = {
            cluster.title: cluster.cluster_id
            for cluster in cluster_for(items, facts)
            if cluster.kind == "SECTION"
        }

        flags = [
            flag for flag in check_cluster_rules(
                cluster_for(items, facts),
                items,
                facts,
            )
            if flag.rule_id == "DIN4124_VERBAU"
        ]

        self.assertEqual(len(flags), 2)
        self.assertEqual(
            {flag.cluster_id for flag in flags},
            set(sections.values()),
        )
        self.assertEqual(
            {tuple(flag.affected_positions) for flag in flags},
            {(items[0].key(),), (items[1].key(),)},
        )

    def test_pressure_positive_and_negative(self):
        positive = [
            item("51", "PE100 Trinkwasser Druckrohr DN63 verlegen"),
            item("52", "PE100 Trinkwasser Druckrohr DN80 verlegen"),
            item("53", "PE100 Trinkwasser Druckrohr DN100 verlegen"),
        ]
        facts = {i.key(): extract_facts(i) for i in positive}
        flags = check_cluster_rules(cluster_for(positive, facts), positive, facts)
        self.assertTrue(any(f.rule_id == "PRESSURE_TEST" for f in flags))

        negative = [
            item("52", "PE100 Trinkwasser Druckrohr DN63 verlegen einschl. Druckpruefung")
        ]
        facts = {i.key(): extract_facts(i) for i in negative}
        flags = check_cluster_rules(cluster_for(negative, facts), negative, facts)
        self.assertFalse(any(f.rule_id == "PRESSURE_TEST" for f in flags))

    def test_pressure_test_suppression_normalizes_umlauts(self):
        position = item(
            "54",
            "PE100 Trinkwasser Druckrohr DN63 verlegen inkl. Druckprüfung",
        )
        position_facts = extract_facts(position)
        rule = next(rule for rule in RULES if rule.id == "PRESSURE_TEST")

        self.assertIn("druckprüfung", position_facts.inclusive_terms)
        self.assertTrue(_subject_suppressed(
            rule,
            [position],
            {position.key(): position_facts},
        ))

    def test_surface_restore_positive_and_negative(self):
        positive = [item("61", "Asphalt abbruch")]
        facts = {i.key(): extract_facts(i) for i in positive}
        flags = check_cluster_rules(cluster_for(positive, facts), positive, facts)
        self.assertTrue(any(f.rule_id == "SURFACE_RESTORE" for f in flags))

        negative = [item("62", "Asphalt Abbruch einschl. Wiederherstellung")]
        facts = {i.key(): extract_facts(i) for i in negative}
        flags = check_cluster_rules(cluster_for(negative, facts), negative, facts)
        self.assertFalse(any(f.rule_id == "SURFACE_RESTORE" for f in flags))

    @unittest.skipIf(True, 'rule disabled: see logic.DISABLED_RULES')
    def test_shaft_cardinality_positive_and_negative(self):
        positive = [
            item("71", "Schacht", "A"),
            item("72", "Schachtabdeckung", "A"),
        ]
        positive[0].unit = "St"
        positive[0].quantity = 10
        positive[1].unit = "St"
        positive[1].quantity = 1
        facts = {i.key(): extract_facts(i) for i in positive}
        flags = check_cluster_rules(cluster_for(positive, facts), positive, facts)
        self.assertTrue(any(f.rule_id == "SHAFT_COVER_CARD" for f in flags))

        negative = [
            item("73", "Schacht", "A"),
            item("74", "Schachtabdeckung einschl. Schacht", "A"),
        ]
        negative[0].unit = "St"
        negative[0].quantity = 10
        negative[1].unit = "St"
        negative[1].quantity = 1
        facts = {i.key(): extract_facts(i) for i in negative}
        flags = check_cluster_rules(cluster_for(negative, facts), negative, facts)
        self.assertFalse(any(f.rule_id == "SHAFT_COVER_CARD" for f in flags))

    @unittest.skipIf(True, 'rule disabled: see logic.DISABLED_RULES')
    def test_dn_step_positive_and_negative(self):
        positive = [
            item("81", "Trinkwasser Druckrohr PE100 DN63"),
            item("82", "Trinkwasser Druckrohr PE100 DN100"),
            item("83", "Trinkwasser Druckrohr PE100 DN250"),
        ]
        facts = {i.key(): extract_facts(i) for i in positive}
        clusters = cluster_for(positive, facts)
        flags = check_cluster_rules(clusters, positive, facts)
        self.assertTrue(any(f.rule_id == "DN_STEP" for f in flags))

        negative = [
            item("84", "Trinkwasser Druckrohr PE100 DN63"),
            item("85", "Trinkwasser Druckrohr PE100 DN100"),
            item("86", "Trinkwasser Druckrohr PE100 DN250 mit Uebergang"),
        ]
        facts = {i.key(): extract_facts(i) for i in negative}
        flags = check_cluster_rules(cluster_for(negative, facts), negative, facts)
        self.assertFalse(any(f.rule_id == "DN_STEP" for f in flags))

    @unittest.skipIf(True, 'rule disabled: see logic.DISABLED_RULES')
    def test_dn_step_on_two_material_free_positions(self):
        positions = [
            item("87", "Trinkwasserleitung DN50 verlegen"),
            item("88", "Trinkwasserleitung DN200 verlegen"),
        ]
        facts = {position.key(): extract_facts(position) for position in positions}
        flags = check_cluster_rules(
            cluster_for(positions, facts),
            positions,
            facts,
        )
        self.assertTrue(any(flag.rule_id == "DN_STEP" for flag in flags))

    def test_site_setup_positive_and_negative(self):
        positive = [item("91", "Rohr DN63")]
        facts = {i.key(): extract_facts(i) for i in positive}
        flags = check_cluster_rules(cluster_for(positive, facts), positive, facts)
        self.assertTrue(any(f.rule_id == "SITE_SETUP" for f in flags))

        negative = [item("92", "Baustelleneinrichtung aufstellen")]
        facts = {i.key(): extract_facts(i) for i in negative}
        flags = check_cluster_rules(cluster_for(negative, facts), negative, facts)
        self.assertFalse(any(f.rule_id == "SITE_SETUP" for f in flags))

    def test_remark_suppression(self):
        rule = next(rule for rule in RULES if rule.id == "DIN4124_VERBAU")
        remarks = ["Grabenverbau ist bauseits als Nebenleistung einzubeziehen."]
        self.assertTrue(suppressed_by_remarks(remarks, rule))
        self.assertTrue(suppressed_by_remarks(
            ["Druckprüfung ist als Nebenleistung einzubeziehen."],
            "PRESSURE_TEST",
        ))


if __name__ == "__main__":
    unittest.main()


class DisabledRuleTests(unittest.TestCase):
    """The three rules switched off after every finding proved false.

    This test exists so the decision is visible in the suite rather than only
    in a comment: if someone re-enables one, they must also delete it here and
    add a real test case from a tender the rule gets right.
    """

    def test_disabled_rules_do_not_fire(self):
        from core import logic
        self.assertEqual(
            logic.DISABLED_RULES,
            frozenset({"DN_STEP", "SHAFT_COVER_CARD",
                       "ELECTRO_LIGHTING_CONNECTION"}),
        )
        active = {r.id for r in logic.RULES} - logic.DISABLED_RULES
        self.assertNotIn("DN_STEP", active)
