import unittest
from types import SimpleNamespace

from core.clusters import build_clusters, cluster_index
from core.facts import extract_facts
from core.models import Cluster, NormalizedItem


def item(oz: str, text: str, section: str = "Haupttrasse") -> NormalizedItem:
    return NormalizedItem(
        oz=oz,
        quantity=1,
        unit="m",
        section_path=(section, "Bereich A"),
        short_text=text,
    )


class ClusterTests(unittest.TestCase):
    def test_section_system_frame_and_index(self):
        items = [
            item("0101", "Druckrohr PE100 DN63"),
            item("0102", "Druckrohr PE100 DN80"),
            item("0103", "Druckrohr PE100 DN100"),
            item("0104", "Baustelleneinrichtung umsetzen"),
        ]
        facts = {position.key(): extract_facts(position) for position in items}

        calculated = [
            SimpleNamespace(item=items[0], total=100.0),
            SimpleNamespace(item=items[1], total=200.0),
            SimpleNamespace(item=items[2], total=300.0),
        ]
        clusters = build_clusters(items, facts, calculated)

        sections = [cluster for cluster in clusters if cluster.kind == "SECTION"]
        systems = [cluster for cluster in clusters if cluster.kind == "SYSTEM"]
        frames = [cluster for cluster in clusters if cluster.kind == "FRAME"]

        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].title, "Haupttrasse > Bereich A")
        self.assertEqual(sections[0].euro_exposure, 600.0)
        self.assertEqual(len(systems), 1)
        self.assertEqual(systems[0].title, "System PE100 DN63-100")
        self.assertEqual(len(systems[0].positions), 3)
        self.assertTrue(any(cluster.title == "Baustelleneinrichtung" for cluster in frames))

        index = cluster_index(clusters)
        self.assertGreaterEqual(len(index["0101"]), 2)
        self.assertIn(systems[0].cluster_id, index["0101"])

    def test_no_system_below_three_positions(self):
        items = [
            item("0201", "Rohr DN63"),
            item("0202", "Rohr DN80"),
        ]
        facts = {position.key(): extract_facts(position) for position in items}

        systems = [
            cluster
            for cluster in build_clusters(items, facts)
            if cluster.kind == "SYSTEM"
        ]
        self.assertEqual(systems, [])

    def test_material_free_strand_keeps_large_dn_step_in_one_system(self):
        items = [
            item("0301", "Trinkwasserleitung DN50 verlegen"),
            item("0302", "Trinkwasserleitung DN80 verlegen"),
            item("0303", "Trinkwasserleitung DN200 verlegen"),
        ]
        facts = {position.key(): extract_facts(position) for position in items}

        systems = [
            cluster
            for cluster in build_clusters(items, facts)
            if cluster.kind == "SYSTEM"
        ]

        self.assertEqual(len(systems), 1)
        self.assertEqual(set(systems[0].positions), {position.key() for position in items})

    def test_two_position_material_free_large_dn_step_forms_system(self):
        items = [
            item("0351", "Trinkwasserleitung DN50 verlegen"),
            item("0352", "Trinkwasserleitung DN200 verlegen"),
        ]
        facts = {position.key(): extract_facts(position) for position in items}

        systems = [
            cluster
            for cluster in build_clusters(items, facts)
            if cluster.kind == "SYSTEM"
        ]

        self.assertEqual(len(systems), 1)
        self.assertEqual(set(systems[0].positions), {position.key() for position in items})

    def test_generic_material_cluster_does_not_absorb_entire_section(self):
        items = [
            item(f"05{index:02}", "Rohr PE100 DN50")
            for index in range(1, 13)
        ]
        facts = {position.key(): extract_facts(position) for position in items}

        systems = [
            cluster
            for cluster in build_clusters(items, facts)
            if cluster.kind == "SYSTEM"
        ]

        self.assertGreaterEqual(len(systems), 2)
        self.assertLessEqual(max(len(cluster.positions) for cluster in systems), 8)

    def test_high_building_and_tga_features_create_system_clusters(self):
        groups = (
            ("Beton", "Stahlbetonstütze C25/30 XC4", "Stahlbetonstütze C25/30 XC4 einbauen"),
            ("Brandschutz", "Trockenbauwand F90 EI90", "Trockenbauwand F90 EI90 montieren"),
            ("Elektro", "NYM-Kabel 5x2,5 400V", "NYM-Kabel 5x2,5 400V anschließen"),
            ("Dämmung", "Wärmedämmung 100 mm WLG 035", "Wärmedämmung 100 mm WLG 035 montieren"),
        )
        items = []
        expected = {}
        for index, (name, first, second) in enumerate(groups):
            section = f"System {name}"
            first_item = item(f"06{index}1", first, section)
            second_item = item(f"06{index}2", second, section)
            items.extend((first_item, second_item))
            expected[name] = {first_item.key(), second_item.key()}
        facts = {position.key(): extract_facts(position) for position in items}

        systems = [
            cluster
            for cluster in build_clusters(items, facts)
            if cluster.kind == "SYSTEM"
        ]
        by_title = {cluster.title: set(cluster.positions) for cluster in systems}

        for feature, positions in expected.items():
            with self.subTest(feature=feature):
                matched = [
                    title
                    for title, cluster_positions in by_title.items()
                    if feature.lower() in title.lower()
                    and cluster_positions == positions
                ]
                self.assertTrue(matched)
        titles = " ".join(by_title)
        for marker in ("C25/30", "XC4", "F90", "EI90", "5x2.5", "400V", "100mm", "035"):
            with self.subTest(marker=marker):
                self.assertIn(marker.lower(), titles.lower())

    def test_material_does_not_merge_unrelated_strands(self):
        items = [
            item("0401", "Trinkwasser Druckrohr PE100 DN50"),
            item("0402", "Trinkwasser Druckrohr PE100 DN80"),
            item("0403", "Trinkwasser Druckrohr PE100 DN100"),
            item("0411", "Schmutzwasser Druckrohr PE100 DN50"),
            item("0412", "Schmutzwasser Druckrohr PE100 DN80"),
            item("0413", "Schmutzwasser Druckrohr PE100 DN100"),
        ]
        facts = {position.key(): extract_facts(position) for position in items}

        systems = [
            cluster
            for cluster in build_clusters(items, facts)
            if cluster.kind == "SYSTEM"
        ]

        self.assertEqual(len(systems), 2)
        self.assertEqual(
            {frozenset(cluster.positions) for cluster in systems},
            {
                frozenset(position.key() for position in items[:3]),
                frozenset(position.key() for position in items[3:]),
            },
        )

    def test_cluster_serialization_round_trip(self):
        cluster = Cluster(
            cluster_id="sec:12345678",
            kind="SECTION",
            title="Test",
            positions=["0101"],
            euro_exposure=12.5,
            unknown_share=0.25,
        )
        restored = Cluster.from_dict(cluster.as_dict())
        self.assertEqual(restored, cluster)


if __name__ == "__main__":
    unittest.main()
