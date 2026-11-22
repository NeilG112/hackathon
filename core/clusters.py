"""Clusteransichten fuer LV-Positionen.

Eine Position darf bewusst in mehreren Clustern liegen: Abschnitt, System und
projektweites Frame sind komplementaere Sichtachsen. Der Stand muss daher
niemals spaeter durch Deduplication nach Position oder OZ verkleinert werden.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from core import objects
from core.facts import PositionFacts
from core.models import Cluster, NormalizedItem

DN_SERIES = (50, 63, 80, 100, 125, 150, 200, 250, 300, 400, 500)

FRAME_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Wasserhaltung", (
        "wasserhaltung", "grundwasserabsenkung", "grundwasserbrunnen",
    )),
    ("Verkehrssicherung", (
        "verkehrssicherung", "verkehrssicherungsdienst", "bauliche verkehrssicherung",
    )),
    ("Entsorgung", (
        "entsorgung", "abfuhr", "entsorgen", "deponie",
    )),
    ("Dokumentation", (
        "dokumentation", "bestandsplan", "aufmass", "aufma\u00df", "fotodokumentation",
    )),
)


@dataclass
class _UnionFind:
    parent: dict[int, int]

    @classmethod
    def for_range(cls, size: int) -> "_UnionFind":
        return cls({i: i for i in range(size)})

    def find(self, value: int) -> int:
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _cluster_id(kind: str, title: str) -> str:
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]
    return f"{kind}:{digest}"


def _dn_related(left: int | None, right: int | None) -> bool:
    if left is None or right is None:
        return False
    if left == right:
        return True
    if left not in DN_SERIES or right not in DN_SERIES:
        return False
    return abs(DN_SERIES.index(left) - DN_SERIES.index(right)) <= 1


def _material_key(material: str | None) -> str:
    return (material or "").strip().lower()


def _facts_for(items: Iterable[NormalizedItem], facts: dict[str, PositionFacts]) -> dict[str, PositionFacts]:
    out: dict[str, PositionFacts] = {}
    for item in items:
        key = item.key()
        if key not in facts:
            raise KeyError(f"PositionFacts fehlen fuer Position {key}")
        out[key] = facts[key]
    return out


def _exposure(
    positions: Sequence[str],
    value_by_oz: dict[str, float],
) -> float:
    return sum(value_by_oz.get(key, 0.0) for key in positions)


def _metrics(
    cluster_id: str,
    kind: str,
    title: str,
    positions: Sequence[NormalizedItem],
    facts_by_key: dict[str, PositionFacts],
    value_by_oz: dict[str, float],
) -> Cluster:
    ozs = [item.key() for item in positions]
    unknown_count = sum(
        1
        for item in positions
        if facts_by_key[item.key()].object_tag == objects.UNKNOWN_TAG
    )
    return Cluster(
        cluster_id=cluster_id,
        kind=kind,
        title=title,
        positions=ozs,
        euro_exposure=_exposure(ozs, value_by_oz),
        unknown_share=unknown_count / len(ozs) if ozs else 0.0,
    )


def build_clusters(
    items,
    facts: dict[str, PositionFacts],
    calculated=None,
) -> list[Cluster]:
    """Build section, system, and project frame clusters."""
    item_list = list(items)
    facts_by_key = _facts_for(item_list, facts)

    value_by_oz: dict[str, float] = {}
    if calculated:
        for result in calculated:
            key = result.item.key()
            value_by_oz[key] = value_by_oz.get(key, 0.0) + (result.total or 0.0)

    clusters: list[Cluster] = []

    # Section clusters.
    by_section: dict[str, list[NormalizedItem]] = defaultdict(list)
    for item in item_list:
        by_section[item.location(depth=2)].append(item)
    for location, positions in by_section.items():
        clusters.append(_metrics(
            f"sec:{hashlib.sha1(location.encode('utf-8')).hexdigest()[:8]}",
            "SECTION",
            location,
            positions,
            facts_by_key,
            value_by_oz,
        ))

    # System clusters. A functional edge is DN-adjacent/same or material-same.
    by_top_section: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(item_list):
        position_facts = facts_by_key[item.key()]
        if position_facts.dn is not None or position_facts.material is not None:
            by_top_section[item.location(depth=1)].append(index)

    for top_section, indexes in by_top_section.items():
        union = _UnionFind.for_range(len(item_list))
        for left_pos, left_index in enumerate(indexes):
            left_facts = facts_by_key[item_list[left_index].key()]
            for right_index in indexes[left_pos + 1:]:
                right_facts = facts_by_key[item_list[right_index].key()]
                shares_material = (
                    _material_key(left_facts.material) != ""
                    and _material_key(left_facts.material)
                    == _material_key(right_facts.material)
                )
                if _dn_related(left_facts.dn, right_facts.dn) or shares_material:
                    union.union(left_index, right_index)

        components: dict[int, list[NormalizedItem]] = defaultdict(list)
        for index in indexes:
            components[union.find(index)].append(item_list[index])

        for positions in components.values():
            if len(positions) < 3:
                continue

            dns = [
                facts_by_key[item.key()].dn
                for item in positions
                if facts_by_key[item.key()].dn is not None
            ]
            materials = [
                facts_by_key[item.key()].material
                for item in positions
                if facts_by_key[item.key()].material is not None
            ]
            distinct_materials = list(dict.fromkeys(
                material for material in materials
            ))
            material = (
                distinct_materials[0]
                if len(distinct_materials) == 1
                else None
            )
            dn_text = (
                f"DN{min(dns)}-{max(dns)}"
                if dns
                else "DNunbenannt"
            )
            title = f"System {material or 'unbenannt'} {dn_text}"
            cluster_seed = top_section + "|" + title + "|" + ",".join(sorted(
                item.key() for item in positions
            ))
            clusters.append(_metrics(
                _cluster_id("sys", cluster_seed),
                "SYSTEM",
                title,
                positions,
                facts_by_key,
                value_by_oz,
            ))

    # Project-wide fixed frame catalog.
    for title in (
        "Baustelleneinrichtung",
        "Wasserhaltung",
        "Verkehrssicherung",
        "Entsorgung",
        "Dokumentation",
    ):
        positions: list[NormalizedItem] = []
        for item in item_list:
            position_facts = facts_by_key[item.key()]
            text = f"{item.short_text} {item.long_text}".lower()
            matched = False
            if title == "Baustelleneinrichtung":
                matched = (
                    position_facts.object_tag == "Baustelle"
                    or position_facts.phase == "vorhalten"
                )
            elif title == "Dokumentation":
                matched = position_facts.object_tag == "Dokumentation"
                if not matched:
                    matched = any(term in text for term in dict(FRAME_RULES)[title])
            else:
                matched = any(term in text for term in dict(FRAME_RULES)[title])
            if matched:
                positions.append(item)
        if positions:
            clusters.append(_metrics(
                _cluster_id("frame", title),
                "FRAME",
                title,
                positions,
                facts_by_key,
                value_by_oz,
            ))

    return clusters


def cluster_index(clusters: Iterable[Cluster]) -> dict[str, list[str]]:
    """Map each OZ to all cluster IDs that contain its position."""
    index: dict[str, list[str]] = {}
    for cluster in clusters:
        for oz in cluster.positions:
            index.setdefault(oz, [])
            if cluster.cluster_id not in index[oz]:
                index[oz].append(cluster.cluster_id)
    return index
