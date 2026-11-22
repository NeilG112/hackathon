"""Clusteransichten fuer LV-Positionen.

Eine Position darf bewusst in mehreren Clustern liegen: Abschnitt, System und
projektweites Frame sind komplementaere Sichtachsen. Der Stand muss daher
niemals spaeter durch Deduplication nach Position oder OZ verkleinert werden.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from core import objects
from core.domain import detect_lv_domains
from core.facts import PositionFacts
from core.models import Cluster, NormalizedItem

DN_SERIES = (50, 63, 80, 100, 125, 150, 200, 250, 300, 400, 500)
MAX_WEAK_CONTEXT_DISTANCE = 3
MAX_WEAK_CONTEXT_CLUSTER_SIZE = 8
_CONCRETE_CLASS = re.compile(r"\bc\s*(\d{2})\s*/\s*(\d{2})\b")
_EXPOSURE_CLASS = re.compile(r"\b(xc|xd|xs|xf|xa)\s*([1-4])\b")
_FIRE_CLASS = re.compile(r"\b(f|ei)\s*(30|60|90|120)\b")
_CABLE_CROSS_SECTION = re.compile(
    r"(?<!\w)(\d{1,3})\s*[x×]\s*(\d+(?:[,.]\d+)?)"
    r"(?:\s*mm(?:2|²)?)?(?!\w)"
)
_VOLTAGE = re.compile(r"\b(\d+(?:[,.]\d+)?)\s*(kv|v)\b")
_INSULATION_THICKNESS = re.compile(
    r"\b(?:waermedaemm\w*|daemm\w*|isolier\w*)\D{0,20}(\d{1,3})\s*mm\b"
)
_WLG = re.compile(r"\bwlg\s*0?(\d{2,3})\b")
_SYSTEM_GENERIC_TERMS = {
    "aus", "bau", "druck", "einbau", "einbauen", "herstellen", "im",
    "anschliessen", "einsetzen", "liefern", "leitung", "leitungen",
    "montage", "montieren", "nach", "rohr", "rohre", "kabel",
    "verlegen", "verlegung", "von", "zu",
}
_SYSTEM_MATERIAL_TERMS = {
    "beton", "ggg", "guss", "pe", "pe100", "pehd", "pvc", "stahl",
    "steinzeug",
}

FRAME_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Baustelleneinrichtung", (
        "baustelleneinrichtung", "bauzaun", "container", "standplatz",
        "baustellenzufahrt",
    )),
    ("Entsorgung & Schadstoffe", (
        "entsorgung", "entsorgen", "abfall", "deponie", "schadstoff",
        "asbest", "kontaminiert", "dekontamination",
    )),
    ("Dokumentation & Revision", (
        "dokumentation", "bestandsplan", "aufmass", "revision",
        "revisionsunterlage", "fotodokumentation", "pruefprotokoll",
        "einmessung",
    )),
    ("Arbeitssicherheit & Schutzmaßnahmen", (
        "arbeitssicherheit", "arbeitsschutz", "schutzmassnahme", "psa",
        "absturzsicherung", "absperrung", "sicherheitseinrichtung",
    )),
    ("Wasserhaltung", (
        "wasserhaltung", "grundwasserabsenkung", "grundwasserbrunnen",
    )),
    ("Verkehrssicherung", (
        "verkehrssicherung", "verkehrssicherungsdienst",
        "bauliche verkehrssicherung",
    )),
    ("Gerüstbau & Absturzsicherung", (
        "geruest", "absturzsicherung", "seitenschutz", "fanggeruest",
        "arbeitsbuehne",
    )),
    ("Brandschutzabschottung & Bauendreinigung", (
        "brandschott", "abschottung", "brandschutz", "bauendreinigung",
        "schlussreinigung", "grundreinigung",
    )),
    ("Prüfung & Inbetriebnahme", (
        "pruefung", "erstpruefung", "messprotokoll", "inbetriebnahme",
        "funktionspruefung", "druckprobe", "spuelung",
    )),
)
FRAME_DOMAINS: dict[str, tuple[str, ...]] = {
    "Wasserhaltung": ("TIEFBAU",),
    "Verkehrssicherung": ("TIEFBAU",),
    "Gerüstbau & Absturzsicherung": ("HOCHBAU_ROHBAU", "AUSBAU"),
    "Brandschutzabschottung & Bauendreinigung": (
        "AUSBAU", "TGA_ELEKTRO", "TGA_SHK",
    ),
    "Prüfung & Inbetriebnahme": ("TGA_ELEKTRO", "TGA_SHK"),
}
_SYSTEM_FEATURE_GROUPS = {
    "BETON": "Beton",
    "BRANDSCHUTZ": "Brandschutz",
    "ELEKTRO": "Elektro",
    "DAEMMUNG": "Dämmung",
}


@dataclass
class _UnionFind:
    parent: dict[int, int]
    sizes: dict[int, int]

    @classmethod
    def for_range(cls, size: int) -> "_UnionFind":
        return cls({i: i for i in range(size)}, {i: 1 for i in range(size)})

    def find(self, value: int) -> int:
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]

    def component_size(self, value: int) -> int:
        return self.sizes[self.find(value)]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root
            self.sizes[left_root] += self.sizes[right_root]


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


def _normalized_item_text(item: NormalizedItem) -> str:
    return (
        f"{item.short_text} {item.long_text}".lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _system_features(item: NormalizedItem) -> set[str]:
    text = _normalized_item_text(item)
    features: set[str] = set()

    concrete_class = _CONCRETE_CLASS.search(text)
    exposure_class = _EXPOSURE_CLASS.search(text)
    if concrete_class or exposure_class:
        features.add("GROUP:BETON")
    if concrete_class:
        features.add(
            f"BETONGUETE:C{concrete_class.group(1)}/{concrete_class.group(2)}"
        )
    if exposure_class:
        features.add(
            f"EXPOSITION:{exposure_class.group(1).upper()}{exposure_class.group(2)}"
        )

    fire_classes = {
        f"{match.group(1).upper()}{match.group(2)}"
        for match in _FIRE_CLASS.finditer(text)
    }
    if fire_classes:
        features.add("GROUP:BRANDSCHUTZ")
        features.update(f"BRANDSCHUTZ:{value}" for value in fire_classes)

    cross_sections = {
        f"{match.group(1)}x{match.group(2).replace(',', '.')}"
        for match in _CABLE_CROSS_SECTION.finditer(text)
    }
    voltages = {
        f"{match.group(1).replace(',', '.')}{match.group(2).upper()}"
        for match in _VOLTAGE.finditer(text)
    }
    if cross_sections or voltages:
        features.add("GROUP:ELEKTRO")
        features.update(f"KABELQUERSCHNITT:{value}" for value in cross_sections)
        features.update(f"SPANNUNG:{value}" for value in voltages)

    thickness = _INSULATION_THICKNESS.search(text)
    wlg = _WLG.search(text)
    if thickness or wlg:
        features.add("GROUP:DAEMMUNG")
    if thickness:
        features.add(f"DAEMMSTAERKE:{thickness.group(1)}mm")
    if wlg:
        features.add(f"WLG:{wlg.group(1).zfill(3)}")

    return features


def _feature_title(features: set[str]) -> str:
    for group, label in _SYSTEM_FEATURE_GROUPS.items():
        if f"GROUP:{group}" in features:
            parts = [label]
            details = sorted(
                feature.split(":", 1)[1]
                for feature in features
                if ":" in feature
                and feature.split(":", 1)[0] != "GROUP"
            )
            parts.extend(details[:3])
            return " ".join(parts)
    return "unbenannt"


def _strand_context(item: NormalizedItem) -> set[str]:
    """Return trade/strand terms, excluding sizes, material and generic work words."""
    text = _normalized_item_text(item)
    has_pipe = bool(re.search(r"\b(?:rohr|leitung)\w*\b", text))
    has_cable = "kabel" in text
    text = re.sub(r"\bdn(?:/od)?\s*\d+\b", " ", text)
    for pattern in (
        _CONCRETE_CLASS,
        _EXPOSURE_CLASS,
        _FIRE_CLASS,
        _CABLE_CROSS_SECTION,
        _VOLTAGE,
        _INSULATION_THICKNESS,
        _WLG,
    ):
        text = pattern.sub(" ", text)
    text = re.sub(r"\b(?:pe\s*-?\s*hd|pe100|pvc|ggg|stahl|guss)\b", " ", text)
    terms: set[str] = set()
    for token in re.findall(r"[a-z]+", text):
        for suffix in ("rohrleitung", "leitungen", "leitung", "rohre", "rohr"):
            if token.endswith(suffix) and len(token) > len(suffix):
                token = token[:-len(suffix)]
                break
        if token not in _SYSTEM_GENERIC_TERMS | _SYSTEM_MATERIAL_TERMS:
            terms.add(token)
    if not terms:
        if has_pipe:
            terms.add("_generic_pipe")
        elif has_cable:
            terms.add("_generic_cable")
        else:
            feature_groups = {
                feature.removeprefix("GROUP:")
                for feature in _system_features(item)
                if feature.startswith("GROUP:")
            }
            if "BETON" in feature_groups:
                terms.add("_generic_concrete")
            elif "BRANDSCHUTZ" in feature_groups:
                terms.add("_generic_fire")
            elif "ELEKTRO" in feature_groups:
                terms.add("_generic_electro")
            elif "DAEMMUNG" in feature_groups:
                terms.add("_generic_insulation")
    return terms


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
    preambles=None,
    domains=None,
) -> list[Cluster]:
    """Build section, system, and project frame clusters."""
    item_list = list(items)
    facts_by_key = _facts_for(item_list, facts)
    active_domains = (
        set(domains)
        if domains is not None
        else detect_lv_domains(item_list, preambles)
    )

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

    # Adjacent DN positions can link unless their strand terms conflict.
    # Larger DN jumps and equal material additionally need shared context.
    by_top_section: dict[str, list[int]] = defaultdict(list)
    features_by_key = {
        item.key(): _system_features(item)
        for item in item_list
    }
    for index, item in enumerate(item_list):
        position_facts = facts_by_key[item.key()]
        if (
            position_facts.dn is not None
            or position_facts.material is not None
            or features_by_key[item.key()]
        ):
            by_top_section[item.location(depth=1)].append(index)

    for top_section, indexes in by_top_section.items():
        union = _UnionFind.for_range(len(item_list))
        contexts = {
            index: _strand_context(item_list[index])
            for index in indexes
        }
        for left_pos, left_index in enumerate(indexes):
            left_facts = facts_by_key[item_list[left_index].key()]
            for right_index in indexes[left_pos + 1:]:
                right_facts = facts_by_key[item_list[right_index].key()]
                left_context = contexts[left_index]
                right_context = contexts[right_index]
                same_strand = bool(left_context & right_context)
                if left_context and right_context and not same_strand:
                    continue
                weak_context = (
                    not left_context
                    or not right_context
                    or left_context <= {
                        "_generic_pipe", "_generic_cable", "_generic_concrete",
                        "_generic_fire", "_generic_electro",
                        "_generic_insulation",
                    }
                    or right_context <= {
                        "_generic_pipe", "_generic_cable", "_generic_concrete",
                        "_generic_fire", "_generic_electro",
                        "_generic_insulation",
                    }
                )
                if (
                    weak_context
                    and abs(left_index - right_index) > MAX_WEAK_CONTEXT_DISTANCE
                ):
                    continue
                shares_material = (
                    _material_key(left_facts.material) != ""
                    and _material_key(left_facts.material)
                    == _material_key(right_facts.material)
                )
                left_features = features_by_key[item_list[left_index].key()]
                right_features = features_by_key[item_list[right_index].key()]
                shares_feature_group = bool(
                    {
                        feature for feature in left_features
                        if feature.startswith("GROUP:")
                    }
                    & {
                        feature for feature in right_features
                        if feature.startswith("GROUP:")
                    }
                )
                dn_related = _dn_related(left_facts.dn, right_facts.dn)
                can_bridge_dn_step = (
                    same_strand
                    and (left_facts.material is None
                         or right_facts.material is None
                         or shares_material)
                )
                feature_related = shares_feature_group and same_strand
                if not (
                    dn_related
                    or can_bridge_dn_step
                    or feature_related
                ):
                    continue
                if weak_context:
                    left_size = union.component_size(left_index)
                    right_size = union.component_size(right_index)
                    if left_size + right_size > MAX_WEAK_CONTEXT_CLUSTER_SIZE:
                        continue
                if dn_related or can_bridge_dn_step or feature_related:
                    union.union(left_index, right_index)

        components: dict[int, list[NormalizedItem]] = defaultdict(list)
        for index in indexes:
            components[union.find(index)].append(item_list[index])

        for positions in components.values():
            component_features = set().union(*(
                features_by_key[item.key()] for item in positions
            ))
            if len(positions) < 2:
                continue
            if not component_features and len(positions) < 3:
                component_dns = [
                    facts_by_key[item.key()].dn
                    for item in positions
                    if facts_by_key[item.key()].dn in DN_SERIES
                ]
                if (
                    len(component_dns) < 2
                    or DN_SERIES.index(max(component_dns))
                    - DN_SERIES.index(min(component_dns)) < 2
                ):
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
            feature_label = _feature_title(component_features)
            if material:
                feature_details = [
                    part for part in feature_label.split()
                    if _material_key(part) != _material_key(material)
                    and part.lower() != "unbenannt"
                ]
                system_label = " ".join((material, *feature_details)).strip()
            else:
                system_label = feature_label
            dn_text = (
                f"DN{min(dns)}-{max(dns)}"
                if dns
                else "DNunbenannt"
            )
            title = f"System {system_label} {dn_text}"
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

    # Universal frames always remain available; trade frames are domain-gated.
    for title, terms in FRAME_RULES:
        required_domains = FRAME_DOMAINS.get(title, ())
        if required_domains and not active_domains.intersection(required_domains):
            continue
        positions: list[NormalizedItem] = []
        for item in item_list:
            position_facts = facts_by_key[item.key()]
            text = _normalized_item_text(item)
            if title == "Baustelleneinrichtung":
                matched = (
                    position_facts.object_tag == "Baustelle"
                    or position_facts.phase == "vorhalten"
                    or any(term in text for term in terms)
                )
            else:
                matched = (
                    (title == "Dokumentation & Revision"
                     and position_facts.object_tag == "Dokumentation")
                    or any(term in text for term in terms)
                )
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
