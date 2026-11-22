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
