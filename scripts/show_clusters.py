#!/usr/bin/env python3
"""Show clusters for the demo tender."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.clusters import build_clusters
from core.facts import extract_facts
from core.parser_x83 import parse


def main() -> int:
    path = "Dataset/[NUMMER_001]_leer.X83"
    items = parse(path)
    facts = {item.key(): extract_facts(item) for item in items}
    clusters = build_clusters(items, facts)

    for cluster in sorted(
        clusters,
        key=lambda value: (-value.euro_exposure, value.kind, value.title),
    ):
        print(
            f"{cluster.kind}, {cluster.title}, "
            f"{len(cluster.positions)} Positionen, "
            f"{cluster.euro_exposure:.2f} EUR, "
            f"{cluster.unknown_share:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
