import unittest

from core.models import NormalizedItem


class NormalizedItemDisplayTests(unittest.TestCase):
    def test_display_oz_preserves_hierarchy_without_changing_join_key(self):
        item = NormalizedItem(
            oz="10003",
            oz_parts=("1", "0003"),
            quantity=1,
            unit="St",
        )

        self.assertEqual(item.display_oz, "1.0003")
        self.assertEqual(item.key(), "10003")

    def test_display_oz_formats_whitespace_separated_gaeb_levels(self):
        item = NormalizedItem(
            oz="0101   1",
            quantity=1,
            unit="St",
        )

        self.assertEqual(item.display_oz, "0101.1")

    def test_display_oz_keeps_flat_oz_when_hierarchy_is_unavailable(self):
        item = NormalizedItem(
            oz="01010001",
            quantity=1,
            unit="St",
        )

        self.assertEqual(item.display_oz, "01010001")


if __name__ == "__main__":
    unittest.main()
