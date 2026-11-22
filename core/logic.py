"""The logic engine — contradictions *between* positions.

The other detectors judge a position on its own: is this rate an outlier, is
this wording vague. This one judges positions against each other, which is
where the errors an engineer actually makes show up:

    300 m2 of floor heating over 50 m2 of floor slab
    a trench excavated but never backfilled
    2 chairs and 15 tables in the same classroom
    46 m2 where every comparable section has 460

None of these is detectable from a single line. A position is never
inconsistent with itself.

Everything here is **deterministic**. No model is asked whether something is
wrong — the rules are arithmetic over `core.objects.ObjectRow`, and a civil
engineer can read, argue with and extend `RELATIONS` without touching code.
That is the point: domain knowledge the model does not have gets *encoded*
rather than prompted for, and the same tender produces the same findings every
single run.

**Precision over recall, deliberately.** Three correct findings win an
estimator's trust; fifty findings with ten false ones destroy it permanently,
and he will never look at the fourth screen. Every rule here fires only with a
margin, and anything resting on an `unklar` tag is suppressed outright.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from core import constants
from core.domain import detect_lv_domains
from core.models import ClusterFlag, Finding, LogicResult, NormalizedItem
from core.objects import UNKNOWN_TAG, ObjectRow, build, tag_of
from utils.text_cleaning import clean_item_text, compare_key

# --- the rule table a civil engineer owns ---------------------------------
#
# (subject, relation, object, tolerance, plain-English reason)
#
#   "<="     subject quantity must not exceed object quantity, within tolerance
#   "needs"  if subject exists in a location, object must exist there too
#
# Tolerance is a fraction: 0.10 means "flag only if it exceeds by >10%", which
# absorbs the ordinary overlaps and offcuts of real construction.
RELATIONS: tuple[tuple[str, str, str, float, str], ...] = (
    ("Bodenheizung", "<=", "Bodenplatte", 0.10,
     "heated floor area cannot exceed the slab it sits on"),
    ("Dämmung", "<=", "Bodenplatte", 0.15,
     "insulation area cannot exceed the slab it covers"),
    ("Bettung", "<=", "Leitungsgraben", 0.20,
     "bedding cannot exceed the trench that contains it"),
    ("Verfüllung", "<=", "Bodenaushub", 0.20,
     "you cannot backfill more than you excavated"),
    # --- UNVERIFIED: companion rules below are domain judgements, not physical
    # necessities, and no civil engineer has confirmed them. Bedding and
    # backfill are frequently Nebenleistungen absorbed into the main position,
    # so their absence is often correct. Off by default; switch on only once
    # someone who writes tenders has signed them off.
    ("Leitungsgraben", "needs", "Verfüllung", 0.0,
     "a trench is excavated but never backfilled — the backfill is either "
     "missing from the tender or hidden in another position"),
    ("Rohrleitung", "needs", "Bettung", 0.0,
     "pipework with no bedding position — either unpriced scope or an "
     "incidental the contractor absorbs"),
)

# An order-of-magnitude check: the client described exactly this failure —
# "vielleicht hat er sich um die Null vertan, 46 statt 460".
MAGNITUDE_FACTOR = 20.0     # flag a position this many times off its peers
MIN_PEERS = 6               # below this there is no meaningful peer group
# A peer group that is itself wildly spread says nothing about any member.
# "50 St vs a median of 4 St" is not an error when the group lumps warning
# lamps in with site containers — it is a tagging artifact. Same lesson as the
# quartile fix in the price-outlier detector: test against the spread the
# comparables actually occupy, and stay silent when that spread is meaningless.
MAX_PEER_SPREAD = 10.0      # p75/p25 above this -> group too heterogeneous

DUPLICATE_MIN_VALUE = 500.0  # ignore trivial repeats


@dataclass(frozen=True)
class UnitBridge:
    """A permitted conversion corridor between two normalized units."""

    from_unit: str
    to_unit: str
    factor_min: float
    factor_max: float
    basis: str

    def corridor(self, qty: float) -> tuple[float, float]:
        """Return the lower and upper conversion corridor for a quantity."""
        return (self.factor_min * qty, self.factor_max * qty)


@dataclass(frozen=True)
class RuleSpec:
    """Editable definition of one cluster-level construction rule."""

    id: str
    kind: str
    subject: str
    object: str
    phase_subject: str
    scope: str
    bounds: tuple[float, float]
    bridge: UnitBridge | None
    tolerance: float
    min_exposure_eur: float
    suppress_if_inclusive: bool
    din_ref: str
    severity: str
    reason_de: str
    domains: tuple[str, ...] = ("COMMON",)


RULES_VERSION = "2"

# Civil engineers may maintain this catalogue. Bounds are factor corridors,
# bridges are explicit conversions, and every rule has an exposure threshold.
TRENCH_BRIDGE = UnitBridge(
    from_unit="m",
    to_unit="m3",
    factor_min=0.8,
    factor_max=1.2,
    basis="breite_m_x_tiefe_m",
)
RULES: tuple[RuleSpec, ...] = (
    RuleSpec(
        "TRENCH_VOLUME", "ratio", "Leitungsgraben", "Bodenaushub", "",
        "section", (0.8, 1.2), TRENCH_BRIDGE, 0.20, 5000.0, True, "",
        "high",
        "Leitungsgraben und Bodenaushub weichen vom plausiblen Tiefen-Breiten-Korridor ab.",
        ("TIEFBAU",),
    ),
    RuleSpec(
        "BEDDING_IN_TRENCH", "containment", "Bettung", "Bodenaushub", "",
        "section", (1.0, 1.0), None, 0.20, 2000.0, True, "",
        "high",
        "Bettungsmenge liegt oberhalb der enthaltenen Erd-/Grabenaushubmenge.",
        ("TIEFBAU",),
    ),
    RuleSpec(
        "BACKFILL_BALANCE", "containment", "Verfüllung", "Bodenaushub", "",
        "section", (1.0, 1.0), None, 0.20, 2000.0, True, "",
        "high",
        "Verfuellmenge liegt oberhalb der Bodenaushubmenge.",
        ("TIEFBAU",),
    ),
    RuleSpec(
        "DIN4124_VERBAU", "requires", "Grabenverbau", "Aboeschung", "",
        "section", (1.0, 1.0), None, 0.0, 2000.0, True, "DIN 4124",
        "high",
        "Tiefe ueber 1,25 m verlangt Grabenverbau oder Aboeschung.",
        ("TIEFBAU",),
    ),
    RuleSpec(
        "PRESSURE_TEST", "requires", "phase pruefung", "montage_trinkwasser_druckrohr", "",
        "system", (1.0, 1.0), None, 0.0, 2000.0, True, "DIN EN 805",
        "high",
        "Montiertes Trink-/Druckrohr aus PE, Guss oder Stahl benoetigt eine Pruefposition.",
        ("TIEFBAU", "TGA_SHK"),
    ),
    RuleSpec(
        "SURFACE_RESTORE", "requires", "phase wiederherstellung", "abbruch_oberflaeche", "",
        "section", (1.0, 1.0), None, 0.0, 2000.0, True, "",
        "high",
        "Abbruch von Asphalt, Pflaster oder Decke verlangt eine Wiederherstellung.",
        ("TIEFBAU",),
    ),
    RuleSpec(
        "SHAFT_COVER_CARD", "cardinality", "Schachtabdeckungen", "Schaechte", "",
        "section", (0.8, 1.2), None, 0.20, 1000.0, True, "",
        "medium",
        "Anzahl der Schachtabdeckungen und Schaechte liegt ausserhalb 0,8 bis 1,2.",
        ("TIEFBAU",),
    ),
    RuleSpec(
        "DN_STEP", "spec_consistency", "DN-Sprung", "reduzier|uebergang|adapter", "",
        "system", (2.0, 2.0), None, 0.0, 2000.0, True, "",
        "medium",
        "Im System liegt ein Sprung von mindestens zwei Normstufen ohne Ausgleichselement.",
        ("TIEFBAU", "TGA_SHK"),
    ),
    RuleSpec(
        "SITE_SETUP", "presence", "Baustelleneinrichtung", "", "",
        "frame", (1.0, 1.0), None, 0.0, 1000.0, True, "",
        "medium",
        "Im Projekt fehlt ein Frame-Cluster zur Baustelleneinrichtung.",
        ("COMMON",),
    ),
)


def _domain_rule(
    rule_id: str,
    domain: str,
    subject: str,
    object_terms: str,
    din_ref: str,
    reason: str,
) -> RuleSpec:
    return RuleSpec(
        rule_id, "requires", subject, object_terms, "",
        "section", (1.0, 1.0), None, 0.0, 0.0, True, din_ref,
        "medium", reason, (domain,),
    )


DOMAIN_RULES: tuple[RuleSpec, ...] = (
    _domain_rule(
        "DIN18331_MISSING_CONCRETE", "HOCHBAU_ROHBAU",
        "Schalung oder Bewehrung", "Beton|Betonage|Stahlbeton",
        "DIN 18331",
        "Mögliche Lücke: Schalung oder Bewehrung ist beschrieben, aber keine Betonleistung im Abschnitt erkennbar.",
    ),
    _domain_rule(
        "DIN18330_SCAFFOLD_MISSING", "HOCHBAU_ROHBAU",
        "Mauerwerk oder Fassade über 2,50 m", "Gerüst|Absturzsicherung|Seitenschutz",
        "DIN 18330",
        "Mögliche Lücke: Mauerwerks- oder Fassadenarbeiten über 2,50 m ohne erkennbare Gerüst-/Absturzsicherung.",
    ),
    _domain_rule(
        "DIN18533_PROTECTION_MISSING", "HOCHBAU_ROHBAU",
        "Erdberührte Abdichtung", "Schutzschicht|Schutzlage|Drainage",
        "DIN 18533",
        "Mögliche Lücke: Bei erdberührter Abdichtung ist keine Schutzschicht oder Drainage erkennbar.",
    ),
    _domain_rule(
        "DIN18340_DRYWALL_FIRE_SPEC", "AUSBAU",
        "Trockenbau mit Feuerwiderstand", "Systemaufbau|Spachtelgüte",
        "DIN 18340",
        "Mögliche Lücke: Bei F30/F90-Trockenbau fehlen Systemkomponenten oder eine Spachtelgüte Q1–Q4.",
    ),
    _domain_rule(
        "DIN18353_SCREED_COMPONENTS", "AUSBAU",
        "Estrich", "Randdämmstreifen|Trittschalldämmung|Aufheizprotokoll",
        "DIN 18353",
        "Mögliche Lücke: Zum Estrich fehlen Rand-/Trittschalldämmung oder bei beheiztem Estrich ein Aufheizprotokoll.",
    ),
    _domain_rule(
        "MLAR_FIRE_STOP_MISSING", "TGA_ELEKTRO",
        "Leitung durch Brandabschnitt", "Brandschott|Abschottung",
        "MLAR",
        "Mögliche Lücke: Leitungsführung durch Brandabschnitte ohne erkennbare Brandschottung.",
    ),
    _domain_rule(
        "DIN_VDE_0100_600_TEST", "TGA_ELEKTRO",
        "Verteilung oder Stromkreis", "Erstprüfung|Messprotokoll",
        "DIN VDE 0100-600",
        "Mögliche Lücke: Für Verteilungen/Stromkreise ist keine Erstprüfung oder Messdokumentation erkennbar.",
    ),
    _domain_rule(
        "ELECTRO_LIGHTING_CONNECTION", "TGA_ELEKTRO",
        "Leuchte oder Aktor", "Montage|Anschluss",
        "",
        "Mögliche Lücke: Leuchten/Aktoren sind beschrieben, aber Montage oder Anschluss ist nicht erkennbar.",
    ),
    _domain_rule(
        "GEG_PIPE_INSULATION", "TGA_SHK",
        "Heizungs- oder Warmwasserleitung", "Dämmung|Isolierung",
        "GEG",
        "Mögliche Lücke: Für Heizungs-/Warmwasserleitungen ist keine Dämmung erkennbar.",
    ),
    _domain_rule(
        "DIN18380_HYDRAULIC_BALANCE", "TGA_SHK",
        "Heiz- oder Kältenetz", "Hydraulischer Abgleich|Einregulierung",
        "DIN 18380",
        "Mögliche Lücke: Für das Heiz-/Kältenetz ist kein hydraulischer Abgleich erkennbar.",
    ),
    _domain_rule(
        "DIN_EN_806_POTABLE_WATER_TEST", "TGA_SHK",
        "Trinkwasserleitung", "Druckprobe|Spülung|Hygiene-Nachweis",
        "DIN EN 806 / VDI 6023",
        "Mögliche Lücke: Für Trinkwasser fehlen Druckprobe, Spülung oder Hygiene-Nachweis.",
    ),
)
RULES = RULES + DOMAIN_RULES
RULES_BY_DOMAIN: dict[str, tuple[RuleSpec, ...]] = {
    domain: tuple(rule for rule in RULES if domain in rule.domains)
    for domain in (
        "COMMON", "TIEFBAU", "HOCHBAU_ROHBAU", "AUSBAU",
        "TGA_ELEKTRO", "TGA_SHK",
    )
}


def _rule_by_id(rule_id: str) -> RuleSpec:
    for rule in RULES:
        if rule.id == rule_id:
            return rule
    raise KeyError(f"Unbekannte Regel {rule_id}")


def _item_text(item: NormalizedItem) -> str:
    return clean_item_text(f"{item.short_text} {item.long_text}".lower())


def _normalize_german_text(text: str) -> str:
    """Canonicalize umlaut and transliterated spellings for comparisons."""
    return (
        text.lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _subject_suppressed(
    rule: RuleSpec,
    subject_items: Sequence[NormalizedItem],
    facts: dict[str, object],
) -> bool:
    if not rule.suppress_if_inclusive:
        return False

    object_terms: tuple[str, ...]
    if rule.id == "DIN4124_VERBAU":
        object_terms = ("verbau", "aussteif", "aboeschung", "abschung")
    elif rule.id == "PRESSURE_TEST":
        object_terms = ("pruefung", "dichtheit", "druckpruefung")
    elif rule.id == "SURFACE_RESTORE":
        object_terms = ("wiederherstell", "instandsetz", "decke schliessen")
    elif rule.id == "BEDDING_IN_TRENCH":
        object_terms = ("bodenaushub", "aushub")
    elif rule.id == "BACKFILL_BALANCE":
        object_terms = ("bodenaushub", "aushub")
    elif rule.id == "TRENCH_VOLUME":
        object_terms = ("bodenaushub", "aushub")
    else:
        object_terms = tuple(
            term.strip().lower()
            for term in rule.object.replace("|", " ").split()
            if term.strip()
        )
        if rule.id == "SHAFT_COVER_CARD":
            object_terms = ("schachtabdeckung", "abdeckung", "deckel", "schacht")

    for item in subject_items:
        position_facts = facts.get(item.key())
        if position_facts is None:
            raise KeyError(f"PositionFacts fehlen fuer Position {item.key()}")
        for inclusive in position_facts.inclusive_terms:
            normalized_inclusive = _normalize_german_text(inclusive)
            if any(
                _normalize_german_text(term) in normalized_inclusive
                for term in object_terms
            ):
                return True
    return False


def suppressed_by_remarks(remarks: Sequence[str] | None, rule: RuleSpec | str) -> bool:
    """Project-wide remark suppression for a rule.

    A remark suppresses only when an object term and one of
    ``nebenleistung``, ``bauseits`` or ``gesondert`` occur near one another.
    """
    if not remarks:
        return False
    spec = _rule_by_id(rule) if isinstance(rule, str) else rule

    terms: tuple[str, ...]
    if spec.id == "DIN4124_VERBAU":
        terms = ("verbau", "aussteifung", "aboeschung", "abschung")
    elif spec.id == "PRESSURE_TEST":
        terms = ("pruefung", "dichtheit", "druckpruefung")
    elif spec.id == "SURFACE_RESTORE":
        terms = ("wiederherstellung", "instandsetzung")
    elif spec.id in ("BEDDING_IN_TRENCH", "BACKFILL_BALANCE", "TRENCH_VOLUME"):
        terms = ("bodenaushub", "aushub", "graben")
    elif spec.id == "SHAFT_COVER_CARD":
        terms = ("schachtabdeckung", "abdeckung", "schacht")
    elif spec.id == "DN_STEP":
        terms = ("reduzier", "uebergang", "adapter")
    elif spec.id == "SITE_SETUP":
        terms = ("baustelleneinrichtung",)
    else:
        terms = tuple(term for term in spec.object.lower().replace("|", " ").split() if term)

    markers = tuple(
        _normalize_german_text(marker)
        for marker in ("nebenleistung", "bauseits", "gesondert")
    )
    for remark in remarks:
        text = _normalize_german_text(clean_item_text(str(remark)))
        for term in terms:
            start = text.find(_normalize_german_text(term))
            if start < 0:
                continue
            window = text[max(0, start - 80):start + 120]
            if any(marker in window for marker in markers):
                return True
    return False


def _sum_tag_quantities(
    positions: Sequence[NormalizedItem],
    facts: dict[str, object],
    object_tag: str,
    allowed_units: set[str] | None = None,
) -> float:
    total = 0.0
    for item in positions:
        position_facts = facts.get(item.key())
        if position_facts is None:
            raise KeyError(f"PositionFacts fehlen fuer Position {item.key()}")
        if position_facts.object_tag != object_tag:
            continue
        unit = constants.normalize_unit(item.unit)
        if allowed_units is not None and unit not in allowed_units:
            continue
        total += item.quantity
    return total


def _sum_text_quantities(
    positions: Sequence[NormalizedItem],
    unit: str,
    terms: tuple[str, ...],
) -> float:
    normalized_unit = constants.normalize_unit(unit)
    total = 0.0
    for item in positions:
        if constants.normalize_unit(item.unit) != normalized_unit:
            continue
        text = _item_text(item)
        if any(term in text for term in terms):
            total += item.quantity
    return total


def _make_flag(
    rule: RuleSpec,
    cluster,
    reason: str,
    computed: dict,
    affected_positions: Sequence[str],
) -> ClusterFlag:
    return ClusterFlag(
        rule_id=rule.id,
        kind=rule.kind,
        cluster_id=cluster.cluster_id,
        cluster_title=cluster.title,
        severity=rule.severity,
        reason_de=reason,
        computed=computed,
        affected_positions=list(dict.fromkeys(affected_positions)),
    )


def _normalized_item_text(item: NormalizedItem) -> str:
    return _normalize_german_text(_item_text(item))


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(_normalize_german_text(term) in text for term in terms)


def _domain_rule_finding(
    rule: RuleSpec,
    positions: Sequence[NormalizedItem],
) -> tuple[list[NormalizedItem], dict, str] | None:
    texts = {item.key(): _normalized_item_text(item) for item in positions}
    section_text = " ".join(texts.values())

    def matching(predicate) -> list[NormalizedItem]:
        return [item for item in positions if predicate(texts[item.key()])]

    missing: list[str] = []
    subjects: list[NormalizedItem] = []

    if rule.id == "DIN18331_MISSING_CONCRETE":
        subjects = matching(lambda text: _contains_any(
            text, ("schalung", "bewehrung", "bewehrungsstahl"),
        ))
        if not subjects or _contains_any(
            section_text, ("beton", "betonage", "stahlbeton"),
        ):
            return None
        missing = ["Betonposition"]

    elif rule.id == "DIN18330_SCAFFOLD_MISSING":
        masonry = matching(lambda text: _contains_any(
            text, ("mauerwerk", "fassade", "aussenwand"),
        ))
        heights = []
        height_patterns = (
            r"\b(?:h|hoehe|wandhoehe|gebaeudehoehe)\s*"
            r"(?:bis|ueber|>\s*)?\s*(\d{1,2}(?:[,.]\d{1,2})?)\s*m\b",
            r"\b(?:bis|ueber|>)\s*(\d{1,2}(?:[,.]\d{1,2})?)\s*m\b",
            r"\b(\d{1,2}(?:[,.]\d{1,2})?)\s*m\s*(?:hoch|wandhoehe)\b",
        )
        for item in masonry:
            text = texts[item.key()]
            values = [
                float(value.replace(",", "."))
                for pattern in height_patterns
                for value in re.findall(pattern, text)
            ]
            if any(value > 2.5 for value in values):
                heights.append(item)
        if not heights or _contains_any(
            section_text,
            ("geruest", "absturzsicherung", "seitenschutz", "fanggeruest", "arbeitsbuehne"),
        ):
            return None
        subjects = heights
        missing = ["Gerüst-/Absturzsicherung"]

    elif rule.id == "DIN18533_PROTECTION_MISSING":
        subjects = matching(lambda text: (
            "abdichtung" in text
            and _contains_any(
                text,
                ("erdberuehrt", "erdreich", "kellerabdichtung",
                 "bauwerksabdichtung", "perimeter"),
            )
        ))
        if not subjects or _contains_any(
            section_text,
            ("schutzschicht", "schutzlage", "noppenbahn", "drainage",
             "drainmatte", "drainplatte", "perimeterdaemmung"),
        ):
            return None
        missing = ["Schutzschicht/Drainage"]

    elif rule.id == "DIN18340_DRYWALL_FIRE_SPEC":
        subjects = matching(lambda text: (
            _contains_any(text, ("trockenbau", "gipskarton", "gipsfaser"))
            and bool(re.search(r"\b(?:f|ei)\s*(?:30|90)\b", text))
        ))
        if not subjects:
            return None
        if not _contains_any(
            section_text,
            ("staenderwerk", "unterkonstruktion", "beplankung", "daemmstoff",
             "mineralwolle", "plattenstaerke", "systemaufbau", "zulassung",
             "bauartgenehmigung"),
        ):
            missing.append("Systemkomponenten")
        if not re.search(r"\bq\s*[1-4]\b", section_text):
            missing.append("Spachtelgüte Q1–Q4")
        if not missing:
            return None

    elif rule.id == "DIN18353_SCREED_COMPONENTS":
        subjects = matching(lambda text: "estrich" in text)
        if not subjects:
            return None
        if not _contains_any(
            section_text,
            ("randdaemmstreifen", "randdaemmung", "trittschall",
             "schalldaemmung", "schalldaemmstreifen"),
        ):
            missing.append("Randdämmstreifen/Trittschalldämmung")
        heated = _contains_any(
            section_text,
            ("fussbodenheizung", "heizkabel", "heizestrich", "heizkreis"),
        )
        if heated and not _contains_any(
            section_text,
            ("aufheizprotokoll", "funktionsheizen", "belegreifheizen",
             "heizprotokoll"),
        ):
            missing.append("Aufheizprotokoll")
        if not missing:
            return None

    elif rule.id == "MLAR_FIRE_STOP_MISSING":
        subjects = matching(lambda text: _contains_any(text, ("leitung", "kabel")))
        if (
            not subjects
            or not _contains_any(
                section_text, ("brandabschnitt", "brandschutzabschnitt"),
            )
            or _contains_any(
                section_text, ("brandschott", "abschottung", "feuerstop"),
            )
        ):
            return None
        missing = ["Brandschottung"]

    elif rule.id == "DIN_VDE_0100_600_TEST":
        subjects = matching(lambda text: _contains_any(
            text, ("stromkreis", "verteilung", "schaltanlage", "elektrische anlage"),
        ))
        if not subjects or _contains_any(
            section_text,
            ("erstpruefung", "messprotokoll", "pruefprotokoll",
             "vde 0100-600", "schutzmassnahmenpruefung"),
        ):
            return None
        missing = ["Erstprüfung/Messprotokoll"]

    elif rule.id == "ELECTRO_LIGHTING_CONNECTION":
        # A Warnleuchte / Blitzleuchte on a building site is battery-powered
        # traffic safety equipment with no electrical connection to install.
        # Matching bare "leuchte" made this rule fire on all three sections
        # that mention one, and on two of them the section contained no
        # lighting at all. Mains-connected luminaires only.
        TRAFFIC_LAMPS = ("warnleuchte", "blitzleuchte", "rundumleuchte",
                         "signalleuchte", "bakenleuchte", "taktleuchte")

        def _is_mains_luminaire(text: str) -> bool:
            stripped = text
            for lamp in TRAFFIC_LAMPS:
                stripped = stripped.replace(lamp, " ")
            return _contains_any(stripped, ("leuchte", "aktor"))

        subjects = matching(_is_mains_luminaire)
        if not subjects or _contains_any(
            section_text, ("montage", "anschluss", "anschliessen"),
        ):
            return None
        missing = ["Montage/Anschluss"]

    elif rule.id == "GEG_PIPE_INSULATION":
        subjects = matching(lambda text: (
            _contains_any(text, ("heizung", "warmwasser"))
            and _contains_any(text, ("leitung", "rohr"))
        ))
        if not subjects or _contains_any(
            section_text,
            ("daemmung", "daemmstaerke", "isolierung", "waermedaemmung", "geg"),
        ):
            return None
        missing = ["Dämmung"]

    elif rule.id == "DIN18380_HYDRAULIC_BALANCE":
        subjects = matching(lambda text: _contains_any(
            text,
            ("heizungsnetz", "kaeltenetz", "heizkreis", "kuehlnetz",
             "heizungsanlage", "kaelteanlage"),
        ))
        if not subjects or _contains_any(
            section_text,
            ("hydraulischer abgleich", "hydraulischeinregulierung",
             "einregulierung", "abgleich", "voreinstellung"),
        ):
            return None
        missing = ["Hydraulischer Abgleich"]

    elif rule.id == "DIN_EN_806_POTABLE_WATER_TEST":
        subjects = matching(lambda text: (
            "trinkwasser" in text
            and _contains_any(text, ("leitung", "rohr", "installation"))
        ))
        if not subjects:
            return None
        if not _contains_any(section_text, ("druckprobe", "druckpruefung")):
            missing.append("Druckprobe")
        if not _contains_any(section_text, ("spuelung", "spuelen", "spuelprotokoll")):
            missing.append("Spülung")
        if not _contains_any(
            section_text,
            ("hygiene", "vdi 6023", "desinfektion", "hygienenachweis"),
        ):
            missing.append("Hygiene-Nachweis")
        if not missing:
            return None

    else:
        return None

    return subjects, {"missing": missing}, f"Fehlende Signale: {', '.join(missing)}."


# Rules switched off because every finding they produced on the only tender we
# can check by hand was wrong. Each failed the same way: a keyword matched a
# German compound whose meaning is the opposite of what the rule assumes.
#
#   DN_STEP          read DN from a *bedding* position ("Einbettung Rohr
#                    DN300-400"), a protective conduit and a concrete manhole
#                    ring, then demanded a reducer between them. None of the
#                    three is part of a flow system.
#   SHAFT_COVER_CARD counted Strassenkappe and Hahnkasten — valve surface
#                    boxes — as manhole covers, giving 6 covers to 2 shafts
#                    where the tender has neither.
#   ELECTRO_LIGHTING "Schutz Mastleuchte Bestand" protects an existing lamp
#                    post during the works; the rule read it as a luminaire
#                    waiting to be wired up.
#
# They are kept rather than deleted because the rule shapes are sound — they
# need a classifier that understands the position, not more keyword patches.
# Re-enable one only together with a test case from a real tender that it gets
# right. Precision first: three correct findings earn trust, six wrong ones
# destroy it and the estimator never opens the fourth screen.
DISABLED_RULES: frozenset[str] = frozenset({
    "DN_STEP",
    "SHAFT_COVER_CARD",
    "ELECTRO_LIGHTING_CONNECTION",
})


def check_cluster_rules(
    clusters,
    items,
    facts,
    calculated=None,
    remarks=None,
    domains=None,
) -> list[ClusterFlag]:
    """Evaluate catalogue rules across section, system and frame clusters.

    Rules in `DISABLED_RULES` are skipped — see the note there.
    """
    clusters = list(clusters)
    items = list(items)
    active_domains = (
        set(domains)
        if domains is not None
        else detect_lv_domains(items, remarks)
    )
    active_rules = (
        rule for rule in RULES
        if rule.id not in DISABLED_RULES
        and ("COMMON" in rule.domains or active_domains.intersection(rule.domains))
    )
    item_by_key = {item.key(): item for item in items}
    by_cluster_positions: dict[str, list[NormalizedItem]] = {}
    for cluster in clusters:
        by_cluster_positions[cluster.cluster_id] = [
            item_by_key[key]
            for key in cluster.positions
            if key in item_by_key
        ]

    flags: list[ClusterFlag] = []

    def exposure_ok(cluster, rule: RuleSpec) -> bool:
        return cluster.euro_exposure >= rule.min_exposure_eur

    def remark_reason(rule: RuleSpec) -> str:
        return f"{rule.reason_de} Projektweit durch Vorbemerkung ausgeschlossen."

    for rule in active_rules:
        if suppressed_by_remarks(remarks, rule):
            # Projektweite Vorbemerkung: keine Regel- und keine False-Positive-Findung.
            continue

        if rule in DOMAIN_RULES:
            for cluster in (c for c in clusters if c.kind == "SECTION"):
                if not exposure_ok(cluster, rule):
                    continue
                positions = by_cluster_positions[cluster.cluster_id]
                finding = _domain_rule_finding(rule, positions)
                if finding is None:
                    continue
                subject_items, computed, detail = finding
                if _subject_suppressed(rule, subject_items, facts):
                    continue
                reason = f"{rule.reason_de} {detail}"
                if rule.din_ref:
                    reason += f" ({rule.din_ref})."
                flags.append(_make_flag(
                    rule, cluster, reason, computed,
                    [item.key() for item in subject_items],
                ))
            continue

        if rule.id == "TRENCH_VOLUME":
            for cluster in (c for c in clusters if c.kind == "SECTION"):
                if not exposure_ok(cluster, rule):
                    continue
                positions = by_cluster_positions[cluster.cluster_id]
                subject_items = [
                    item for item in positions
                    if facts[item.key()].object_tag == "Leitungsgraben"
                ]
                if not subject_items or _subject_suppressed(rule, subject_items, facts):
                    continue
                trench_m = _sum_tag_quantities(
                    positions, facts, "Leitungsgraben", {"m"},
                )
                excavation_m3 = _sum_tag_quantities(
                    positions, facts, "Leitungsgraben", {"m3"},
                )
                if excavation_m3 <= 0:
                    excavation_m3 = _sum_tag_quantities(
                        positions, facts, "Bodenaushub", {"m3"},
                    )
                if trench_m <= 0 or excavation_m3 <= 0:
                    continue

                depths: list[tuple[float, float]] = []
                for item in subject_items:
                    if constants.normalize_unit(item.unit) == "m":
                        depth = facts[item.key()].depth_m
                        depths.append((item.quantity, depth if depth is not None else 1.5))
                weighted_depth = (
                    sum(qty * depth for qty, depth in depths) / sum(qty for qty, _ in depths)
                    if depths and sum(qty for qty, _ in depths) > 0
                    else 1.5
                )
                low_raw = TRENCH_BRIDGE.factor_min * weighted_depth
                high_raw = TRENCH_BRIDGE.factor_max * weighted_depth
                low = low_raw * (1.0 - rule.tolerance)
                high = high_raw * (1.0 + rule.tolerance)
                actual = excavation_m3 / trench_m
                if low <= actual <= high:
                    continue
                computed = {
                    "aushub_m3": round(excavation_m3, 3),
                    "graben_m": round(trench_m, 3),
                    "je_m": round(actual, 3),
                    "korridor": [round(low, 3), round(high, 3)],
                }
                flags.append(_make_flag(
                    rule, cluster, rule.reason_de, computed,
                    [item.key() for item in subject_items],
                ))

        elif rule.id in ("BEDDING_IN_TRENCH", "BACKFILL_BALANCE"):
            subject_tag = "Bettung" if rule.id == "BEDDING_IN_TRENCH" else "Verfüllung"
            for cluster in (c for c in clusters if c.kind == "SECTION"):
                if not exposure_ok(cluster, rule):
                    continue
                positions = by_cluster_positions[cluster.cluster_id]
                subject_items = [
                    item for item in positions
                    if facts[item.key()].object_tag == subject_tag
                    or (
                        rule.id == "BACKFILL_BALANCE"
                        and any(
                            term in _item_text(item)
                            for term in ("verfuell", "verfüll", "hinterfuell", "hinterfüll", "auffuell", "auffüll")
                        )
                    )
                ]
                if not subject_items or _subject_suppressed(rule, subject_items, facts):
                    continue
                subject_units = {
                    constants.normalize_unit(item.unit) for item in subject_items
                }
                if len(subject_units) != 1:
                    continue
                unit = next(iter(subject_units))
                if unit != "m3":
                    continue
                subject_qty = sum(item.quantity for item in subject_items)
                object_qty = sum(
                    item.quantity for item in positions
                    if facts[item.key()].object_tag == rule.object
                    and constants.normalize_unit(item.unit) == unit
                )
                if object_qty <= 0:
                    continue
                if subject_qty <= object_qty * (1.0 + rule.tolerance):
                    continue
                ratio = subject_qty / object_qty
                computed = {
                    "subject_qty": round(subject_qty, 3),
                    "object_qty": round(object_qty, 3),
                    "unit": unit,
                    "ratio": round(ratio, 3),
                    "tolerance": rule.tolerance,
                }
                flags.append(_make_flag(
                    rule, cluster, rule.reason_de, computed,
                    [item.key() for item in subject_items],
                ))

        elif rule.id == "DIN4124_VERBAU":
            for cluster in (c for c in clusters if c.kind == "SECTION"):
                if not exposure_ok(cluster, rule):
                    continue
                positions = by_cluster_positions[cluster.cluster_id]
                subject_items = [
                    item for item in positions
                    if facts[item.key()].depth_m is not None
                    and facts[item.key()].depth_m > 1.25
                    and facts[item.key()].object_tag != "Grabenverbau"
                    and not any(
                        term in _item_text(item)
                        for term in ("verbau", "verbauen", "verbaut")
                    )
                ]
                if not subject_items:
                    continue
                has_object = any(
                    facts[item.key()].object_tag == "Grabenverbau"
                    or "aboeschung" in _item_text(item)
                    or "ab\u00f6schung" in _item_text(item)
                    for item in positions
                )
                if has_object:
                    continue
                if _subject_suppressed(rule, subject_items, facts):
                    continue
                computed = {
                    "depth_m_max": round(
                        max(
                            facts[item.key()].depth_m
                            for item in subject_items
                        ),
                        3,
                    ),
                    "schwelle_m": 1.25,
                    "objekt": "Grabenverbau oder Aboeschung",
                }
                reason = f"{rule.reason_de} ({rule.din_ref})."
                flags.append(_make_flag(
                    rule, cluster, reason, computed,
                    [item.key() for item in subject_items],
                ))

        elif rule.id == "PRESSURE_TEST":
            for cluster in (c for c in clusters if c.kind == "SYSTEM"):
                if not exposure_ok(cluster, rule):
                    continue
                positions = by_cluster_positions[cluster.cluster_id]
                subject_items = []
                for item in positions:
                    position_facts = facts[item.key()]
                    text = _item_text(item)
                    material = (position_facts.material or "").lower()
                    is_pressure_material = any(
                        term in material for term in ("pe", "guss", "ggg", "stahl")
                    )
                    if (
                        is_pressure_material
                        and position_facts.phase == "montage"
                        and ("trinkwasser" in text or "druckrohr" in text)
                    ):
                        subject_items.append(item)
                if not subject_items or _subject_suppressed(rule, subject_items, facts):
                    continue
                has_test = any(
                    facts[item.key()].phase == "pruefung"
                    for item in positions
                )
                if has_test:
                    continue
                computed = {
                    "subject_count": len(subject_items),
                    "material": sorted({
                        facts[item.key()].material
                        for item in subject_items
                        if facts[item.key()].material
                    }),
                }
                reason = f"{rule.reason_de} ({rule.din_ref})."
                flags.append(_make_flag(
                    rule, cluster, reason, computed,
                    [item.key() for item in subject_items],
                ))

        elif rule.id == "SURFACE_RESTORE":
            for cluster in (c for c in clusters if c.kind == "SECTION"):
                if not exposure_ok(cluster, rule):
                    continue
                positions = by_cluster_positions[cluster.cluster_id]
                subject_items = [
                    item for item in positions
                    if facts[item.key()].phase == "abbruch"
                    and any(term in _item_text(item) for term in ("asphalt", "pflaster", "decke"))
                ]
                if not subject_items or _subject_suppressed(rule, subject_items, facts):
                    continue
                has_restore = any(
                    facts[item.key()].phase == "wiederherstellung"
                    for item in positions
                )
                if has_restore:
                    continue
                computed = {
                    "abbruch_count": len(subject_items),
                    "oberflaechen": sorted({
                        term
                        for item in subject_items
                        for term in ("asphalt", "pflaster", "decke")
                        if term in _item_text(item)
                    }),
                }
                flags.append(_make_flag(
                    rule, cluster, rule.reason_de, computed,
                    [item.key() for item in subject_items],
                ))

        elif rule.id == "SHAFT_COVER_CARD":
            for cluster in (c for c in clusters if c.kind == "SECTION"):
                if not exposure_ok(cluster, rule):
                    continue
                positions = by_cluster_positions[cluster.cluster_id]
                shafts = _sum_text_quantities(
                    positions, "St", ("schacht",),
                )
                covers = _sum_text_quantities(
                    positions, "St", ("schachtabdeckung", "abdeckung", "deckel"),
                )
                if shafts <= 0 or covers <= 0:
                    continue
                low = rule.bounds[0] * (1.0 - rule.tolerance)
                high = rule.bounds[1] * (1.0 + rule.tolerance)
                if low <= covers / shafts <= high:
                    continue
                subject_items = [
                    item for item in positions
                    if "schacht" in _item_text(item)
                    or "abdeckung" in _item_text(item)
                    or "deckel" in _item_text(item)
                ]
                if _subject_suppressed(rule, subject_items, facts):
                    continue
                computed = {
                    "abdeckungen": round(covers, 3),
                    "schaechte": round(shafts, 3),
                    "ratio": round(covers / shafts, 3),
                    "korridor": [round(low, 3), round(high, 3)],
                }
                flags.append(_make_flag(
                    rule, cluster, rule.reason_de, computed,
                    [item.key() for item in subject_items],
                ))

        elif rule.id == "DN_STEP":
            dn_norms = (
                50, 63, 80, 100, 125, 150, 200, 250, 300, 400, 500,
            )
            for cluster in (c for c in clusters if c.kind == "SYSTEM"):
                if not exposure_ok(cluster, rule):
                    continue
                positions = by_cluster_positions[cluster.cluster_id]
                dns = [
                    facts[item.key()].dn
                    for item in positions
                    if facts[item.key()].dn is not None
                ]
                if len(dns) < 2:
                    continue
                indexes = [
                    dn_norms.index(dn) for dn in dns
                    if dn in dn_norms
                ]
                if len(indexes) < 2 or max(indexes) - min(indexes) < 2:
                    continue
                if any(
                    any(term in _item_text(item) for term in ("reduzier", "uebergang", "adapter"))
                    for item in positions
                ):
                    continue
                subject_items = [
                    item for item in positions
                    if facts[item.key()].dn is not None
                ]
                if _subject_suppressed(rule, subject_items, facts):
                    continue
                computed = {
                    "dn_min": min(dns),
                    "dn_max": max(dns),
                    "normstufen_sprung": max(indexes) - min(indexes),
                }
                flags.append(_make_flag(
                    rule, cluster, rule.reason_de, computed,
                    [item.key() for item in subject_items],
                ))

        elif rule.id == "SITE_SETUP":
            frame_present = False
            for cluster in clusters:
                if cluster.kind == "FRAME" and cluster.title == "Baustelleneinrichtung":
                    frame_present = len(cluster.positions) > 0
                    if frame_present:
                        break
            if not frame_present:
                site_subject = [
                    item for item in items
                    if "baustelleneinrichtung" in _item_text(item)
                ]
                if _subject_suppressed(rule, site_subject, facts):
                    continue
                affected = [item.key() for item in site_subject]
                dummy = next(
                    (c for c in clusters if c.kind == "SECTION"),
                    None,
                )
                if dummy is None:
                    continue
                if dummy.euro_exposure < rule.min_exposure_eur:
                    continue
                flags.append(_make_flag(
                    rule, dummy, rule.reason_de,
                    {"frame_present": False}, affected,
                ))

    return flags
@dataclass
class Relation:
    """One evaluated rule, kept so the UI can show the arithmetic."""

    subject: str
    relation: str
    obj: str
    location: str
    subject_qty: float
    object_qty: float
    unit: str
    reason: str


def _by_location(rows: Sequence[ObjectRow]) -> dict[str, dict[tuple[str, str], ObjectRow]]:
    out: dict[str, dict[tuple[str, str], ObjectRow]] = defaultdict(dict)
    for row in rows:
        if row.obj == UNKNOWN_TAG:
            continue
        out[row.location][(row.obj, row.unit)] = row
    return out


def _find(cell: dict, obj: str) -> ObjectRow | None:
    """The row for `obj` in this location, whichever unit it was measured in."""
    for (name, _unit), row in cell.items():
        if name == obj and row.quantity > 0:
            return row
    return None


def _item_for(row: ObjectRow, items: Sequence[NormalizedItem]) -> NormalizedItem:
    """A representative position, so a finding can point somewhere real."""
    index = {i.key(): i for i in items}
    for oz in row.positions:
        if oz in index:
            return index[oz]
    return NormalizedItem(oz=row.positions[0] if row.positions else "",
                          quantity=row.quantity, unit=row.unit,
                          short_text=row.label())


def check_relations(
    rows: Sequence[ObjectRow],
    items: Sequence[NormalizedItem],
    include_companions: bool = False,
) -> list[Finding]:
    """Apply `RELATIONS` within each location.

    `include_companions` enables the unverified "needs" rules. Default off:
    they produced 19 findings on the demo tender and not one was defensible.
    """
    findings: list[Finding] = []

    for location, cell in _by_location(rows).items():
        for subject, relation, obj, tolerance, reason in RELATIONS:
            left = _find(cell, subject)
            if left is None:
                continue
            right = _find(cell, obj)

            if relation == "needs":
                if not include_companions or right is not None:
                    continue
                findings.append(Finding(
                    item=_item_for(left, items),
                    detector="logic",
                    severity="medium",
                    rationale=(
                        f"{subject} appears in “{location}” but {obj} does not: "
                        f"{reason}. {len(left.positions)} positions affected."
                    ),
                    euro_leverage=left.value,
                    evidence={"location": location, "subject": subject,
                              "missing": obj, "positions": left.positions[:20]},
                ))
                continue

            # "<=" only compares like with like.
            if right is None or left.unit != right.unit or right.quantity <= 0:
                continue
            if left.quantity <= right.quantity * (1.0 + tolerance):
                continue

            ratio = left.quantity / right.quantity
            findings.append(Finding(
                item=_item_for(left, items),
                detector="logic",
                severity="high",
                rationale=(
                    f"“{location}”: {left.quantity:,.0f} {left.unit} of {subject} "
                    f"but only {right.quantity:,.0f} {right.unit} of {obj} "
                    f"({ratio:.1f}x) — {reason}. Either a quantity is wrong or "
                    "scope is missing; both change the price."
                ),
                euro_leverage=max(left.value, right.value),
                evidence={"location": location, "subject": subject, "object": obj,
                          "subject_qty": left.quantity, "object_qty": right.quantity,
                          "ratio": round(ratio, 2),
                          "positions": (left.positions + right.positions)[:20]},
            ))
    return findings


def _pre_unit_price(
    item: NormalizedItem,
    pre_prices: dict[str, float] | None,
) -> float:
    if pre_prices:
        price = pre_prices.get(item.key())
        if price is not None:
            return float(price)
    if item.unit_price is not None:
        return float(item.unit_price)
    if item.total_price is not None and item.quantity > 0:
        return float(item.total_price) / float(item.quantity)
    return 0.0


def check_magnitude(
    items: Sequence[NormalizedItem],
    pre_prices: dict[str, float] | None = None,
) -> list[Finding]:
    """Order-of-magnitude quantity outliers — the misplaced-zero check.

    Compares each position against its peers: the same object measured in the
    same unit elsewhere in the tender. Needs `MIN_PEERS` to say anything, and
    uses the median so one bad value cannot drag the baseline.
    """
    groups: dict[tuple[str, str], list[NormalizedItem]] = defaultdict(list)
    for item in items:
        tag = tag_of(item)
        if tag == UNKNOWN_TAG or item.quantity <= 0:
            continue
        groups[(tag, constants.normalize_unit(item.unit))].append(item)

    findings: list[Finding] = []
    for (tag, unit), peers in groups.items():
        if len(peers) < MIN_PEERS:
            continue
        quantities = sorted(i.quantity for i in peers)
        median = quantities[len(quantities) // 2]
        if median <= 0:
            continue
        p25 = quantities[len(quantities) // 4]
        p75 = quantities[(3 * len(quantities)) // 4]
        if p25 <= 0 or p75 / p25 > MAX_PEER_SPREAD:
            continue
        for item in peers:
            ratio = item.quantity / median
            if ratio < MAGNITUDE_FACTOR and ratio > 1 / MAGNITUDE_FACTOR:
                continue
            direction = "larger" if ratio > 1 else "smaller"
            findings.append(Finding(
                item=item,
                detector="logic",
                severity="medium",
                rationale=(
                    f"{item.quantity:,.0f} {unit} is {max(ratio, 1/ratio):.0f}x "
                    f"{direction} than the median of {len(peers)} comparable "
                    f"{tag} positions ({median:,.0f} {unit}). A misplaced "
                    "decimal or a genuinely unusual position — worth one look."
                ),
                euro_leverage=abs(item.quantity * _pre_unit_price(item, pre_prices)),
                evidence={"tag": tag, "unit": unit, "median": median,
                          "ratio": round(ratio, 2), "peers": len(peers)},
            ))
    return findings


def check_duplicates(
    items: Sequence[NormalizedItem],
    pre_prices: dict[str, float] | None = None,
) -> list[Finding]:
    """Positions repeating the same work — *"summary and duplicate is a good thing"*.

    Same wording, same unit, different OZ. Often legitimate (the same work in
    two sections), which is why this reports rather than accuses, and why the
    locations are named: identical work in the *same* location is the
    suspicious case.
    """
    groups: dict[tuple[str, str], list[NormalizedItem]] = defaultdict(list)
    for item in items:
        signature = compare_key(item.short_text)
        if signature:
            groups[(signature, constants.normalize_unit(item.unit))].append(item)

    findings: list[Finding] = []
    for (_sig, unit), group in groups.items():
        if len(group) < 2:
            continue
        exposure = sum(
            i.quantity * _pre_unit_price(i, pre_prices)
            if pre_prices or i.unit_price is not None or i.total_price is not None
            else 0.0
            for i in group
        )
        locations = {i.location() for i in group}
        same_place = len(locations) == 1
        if not same_place and exposure < DUPLICATE_MIN_VALUE:
            continue
        findings.append(Finding(
            item=group[0],
            detector="logic",
            severity="medium" if same_place else "low",
            rationale=(
                f"{len(group)} positions carry identical wording and unit "
                f"({', '.join(i.key() for i in group[:6])})"
                + (" — all in the same section, so this may be a genuine "
                   "duplication rather than the same work in two places."
                   if same_place else
                   f" across {len(locations)} sections, which is usually "
                   "legitimate. Worth confirming the quantities are not "
                   "double-counted.")
            ),
            euro_leverage=exposure,
            evidence={"positions": [i.key() for i in group],
                      "locations": sorted(locations), "same_location": same_place},
        ))
    return findings


def _text(item: NormalizedItem) -> str:
    return f"{clean_item_text(item.short_text)} {clean_item_text(item.long_text)}".lower()


def _severity_rank(severity: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(severity, 0)


def run_logic_engine(
    items: Sequence[NormalizedItem],
    rows: Sequence[ObjectRow] | None = None,
    pre_prices: dict[str, float] | None = None,
    clusters=None,
    facts=None,
    remarks=None,
    domains=None,
) -> dict[str, LogicResult]:
    """Run deterministic, per-position rules for a tender of any practical size."""

    if rows is None:
        rows = build(items, depth=2)

    results: dict[str, LogicResult] = {
        item.key(): LogicResult([], "low", [], [])
        for item in items
    }

    def add(item: NormalizedItem, flag: str, severity: str, detail: str) -> None:
        result = results[item.key()]
        if flag not in result.flags:
            result.flags.append(flag)
        if flag not in result.tags:
            result.tags.append(flag)
        if detail not in result.details:
            result.details.append(detail)
        if _severity_rank(severity) > _severity_rank(result.severity):
            result.severity = severity

    # Per-item textual and unit rules.
    for item in items:
        key = item.key()
        unit = constants.normalize_unit(item.unit)
        short_text = clean_item_text(item.short_text)
        long_text = clean_item_text(item.long_text)
        text = _text(item)

        if (unit == "psch" or item.is_lump_sum) and item.quantity not in (0.0, 1.0):
            add(item, "META_MISMATCH", "high",
                f"Pauschale Einheit {item.unit!r} hat Menge {item.quantity:g}, "
                "erwartet 0 oder 1.")

        if item.quantity <= 0 and not any(
            keyword in text for keyword in constants.EVENTUAL_KEYWORDS
        ):
            add(item, "ZERO_QTY", "high",
                f"Menge ist {item.quantity:g}; keine Eventualposition erkannt.")

        short_norm = compare_key(short_text)
        long_norm = compare_key(long_text)
        if any(keyword in short_norm for keyword in constants.BLACKBOX_KEYWORDS):
            if not long_norm or len(long_text) < 25 or long_norm == short_norm:
                add(item, "MISSING_SPEC", "medium",
                    "Komplexer/Black-Box-Text hat keine eigenständig ausreichende "
                    "Langbeschreibung.")

        if any(keyword in text for keyword in ("lieferung", "liefern")):
            montage_words = ("montage", "einbau", "verlegen", "versetzen", "anschließen")
            has_montage = any(word in text for word in montage_words)
            if not has_montage:
                own_tag = tag_of(item)
                location = item.location(depth=2)
                has_peer = own_tag != UNKNOWN_TAG and any(
                    peer.location(depth=2) == location
                    and tag_of(peer) == own_tag
                    and any(word in _text(peer) for word in montage_words)
                    for peer in items
                )
                if not has_peer:
                    add(item, "SCOPE_GAP", "medium",
                        "Lieferleistung genannt, aber Montage-/Einbauumfang nicht "
                        "sichtbar und keine passende Peer-Position in diesem Abschnitt.")

        # Unit and peer-magnitude outliers are separate signals combined here.
        qty_outlier_details: list[str] = []
        normalized_text = compare_key(f"{short_text} {long_text}")
        normalized_words = set(normalized_text.split())
        for keyword, expected_unit in constants.UNIT_EXPECTED_BY_KEYWORD.items():
            if keyword in normalized_words and unit != constants.normalize_unit(expected_unit):
                qty_outlier_details.append(
                    f"Einheit {item.unit!r} passt nicht zur erwarteten Einheit "
                    f"{expected_unit!r} für Schlüsselwort {keyword!r}."
                )
                break
        if qty_outlier_details:
            add(item, "QTY_OUTLIER", "medium", " | ".join(qty_outlier_details))

    # Attach peer-magnitude findings to the same per-key results.
    for finding in check_magnitude(items, pre_prices):
        key = finding.item.key()
        if key in results:
            add(finding.item, "QTY_OUTLIER", "medium", finding.rationale)

    # Relation findings identify category and quantity conflicts.
    relation_findings = check_relations(rows, items, include_companions=False)
    for finding in relation_findings:
        positions = finding.evidence.get("positions", [])
        if finding.item.key() in positions:
            positions = [finding.item.key()]
        for position_key in positions:
            if position_key not in results:
                continue
            representative = next(
                (item for item in items if item.key() == position_key),
                finding.item,
            )
            add(representative, "CATEGORY_MISMATCH", "high", finding.rationale)

    # Explicit companion-quantity gaps within the location.
    for item in items:
        location = item.location(depth=2)
        location_items = [peer for peer in items if peer.location(depth=2) == location]

        is_concrete = tag_of(item) == "Beton"
        has_concrete = is_concrete and item.quantity >= 10.0
        if has_concrete:
            concrete_qty = sum(
                peer.quantity for peer in location_items if tag_of(peer) == "Beton"
            )
            own_long = clean_item_text(item.long_text).lower()
            own_suppressed = any(
                marker in own_long for marker in ("inkl.", "einschl.", "schalung", "bewehr")
            )
            has_companion = any(
                "schalung" in _text(peer) or "bewehr" in _text(peer)
                for peer in location_items
            )
            if concrete_qty >= 10.0 and not has_companion and not own_suppressed:
                add(item, "MISSING_FOLLOW_UP", "medium",
                    f"Beton in Abschnitt {location!r}: mindestens "
                    f"{concrete_qty:g} m³, aber keine Schalungs-/Bewehrungsposition gefunden.")

        is_excavation = tag_of(item) == "Bodenaushub"
        if is_excavation:
            own_long = clean_item_text(item.long_text).lower()
            own_suppressed = any(
                marker in own_long for marker in ("inkl.", "einschl.", "schalung", "verfüll")
            )
            has_backfill = any(tag_of(peer) == "Verfüllung" for peer in location_items)
            if not has_backfill and not own_suppressed:
                add(item, "MISSING_FOLLOW_UP", "medium",
                    f"Bodenaushub in Abschnitt {location!r}, aber keine "
                    "Verfüllungsposition gefunden.")

    if clusters is not None and facts is not None:
        for cluster_flag in check_cluster_rules(
            clusters,
            items,
            facts,
            remarks=remarks,
            domains=domains,
        ):
            for position_key in cluster_flag.affected_positions:
                if position_key not in results:
                    continue
                detail = (
                    f"{cluster_flag.rule_id}: {cluster_flag.reason_de} "
                    f"Rechnung={cluster_flag.computed}"
                )
                add(
                    next(item for item in items if item.key() == position_key),
                    cluster_flag.rule_id,
                    cluster_flag.severity,
                    detail,
                )

    return results


def run_all(
    rows: Sequence[ObjectRow],
    items: Sequence[NormalizedItem],
    top_n: int | None = None,
    include_companions: bool = False,
    pre_prices: dict[str, float] | None = None,
) -> list[Finding]:
    """Every cross-position check, ranked by euro exposure."""
    findings = (
        check_relations(rows, items, include_companions)
        + check_magnitude(items, pre_prices)
        + check_duplicates(items, pre_prices)
    )
    findings.sort(key=lambda f: (-f.euro_leverage,
                                 constants.SEVERITY_ORDER.index(f.severity)))
    return findings[:top_n] if top_n else findings
