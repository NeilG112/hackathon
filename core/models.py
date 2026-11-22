"""Shared data contract.

Everything in the system speaks `NormalizedItem`. Both parsers produce it, the
pricer and detectors consume it. If you need another field, add it here rather
than passing dicts around — this module is the one place all five workstreams
touch, so keep it boring and dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


def normalize_oz(raw: str) -> str:
    """Canonical form of a GAEB item number (Ordnungszahl).

    The join between the two input formats and the priced reference data runs
    through this function, so there is exactly one canonical form:

        alphanumerics only, uppercased, padding and separators removed,
        hierarchy levels concatenated.

    D83 fixed-width gives `'0101   1'`; X83 gives the parts `('01', '01', '1')`.
    Both collapse to `'01011'`. Whitespace is dropped, not zero-padded — see
    PLAN.md "The three OZ layouts" for why per-file field widths make
    zero-padding unsafe as a global rule. Separators (`.`, `-`, `/`) are dropped
    for the same reason: only one of the two formats writes them.

    **Letters are kept.** `StBALV23040.D86` contains a real item with the OZ
    `TEL00009` (confirmed by its matching type-23 price record `23TEL00009`).
    A digits-only key silently turned that into `'00009'`, which both loses the
    prefix and risks colliding with a numeric OZ in the same file.
    """
    return "".join(ch for ch in raw.upper() if ch.isalnum())


@dataclass
class NormalizedItem:
    """One priceable line of a bill of quantities (Leistungsverzeichnis)."""

    oz: str
    quantity: float
    unit: str

    # The OZ hierarchy levels, outermost -> innermost, as stored. Populated by
    # the X83 parser (from the RNoPart chain); empty for GAEB 90, where the OZ
    # is one flat field with no recoverable level boundaries. Needed because
    # the two formats pad levels differently — see `padded_key`.
    oz_parts: tuple[str, ...] = ()

    # The hierarchy's *labels*, outermost -> innermost: "Tiefbau Ost -
    # Haupttrasse 2023" > "[ORT_030]". This is the location key, and the
    # inconsistency engine does not work without it: "300 m2 of floor heating
    # over 50 m2 of slab" is only a contradiction *within one section*. Summed
    # across a whole site, heating spread over twelve floors looks fine and the
    # finding disappears. See core/objects.py.
    section_path: tuple[str, ...] = ()

    short_text: str = ""
    long_text: str = ""
    is_lump_sum: bool = False

    # Only present on priced files (.D84/.D86). None on a blank tender.
    unit_price: Optional[float] = None
    total_price: Optional[float] = None

    # Provenance: which file and which record/element this came from. Keep this
    # populated — the validation report cites it when a position disagrees.
    source_file: str = ""
    source_ref: str = ""

    def key(self) -> str:
        """Join key. Use this, never the list index (the 248/249 gap)."""
        return normalize_oz(self.oz)

    @property
    def display_oz(self) -> str:
        """Return the human-readable hierarchy without changing the join key."""
        if self.oz_parts:
            return ".".join(self.oz_parts)
        parts = self.oz.split()
        return ".".join(parts) if len(parts) > 1 else self.oz.strip()

    def location(self, depth: int = 2) -> str:
        """The section this position sits in — the inconsistency engine's key.

        `depth` trades sensitivity against noise: too shallow and everything
        is one location (contradictions average away); too deep and every
        position is its own location (nothing to compare). Two levels matches
        the Bauabschnitt / Bereich split these tenders actually use.
        """
        if not self.section_path:
            return "(ohne Abschnitt)"
        return " > ".join(self.section_path[:depth])

    def padded_key(self, widths: tuple[int, ...]) -> str:
        """Join key with each OZ level zero-padded to `widths`.

        **Read this before writing the 248/249 join (task 005).** PLAN.md states
        the join is `'01'+'01'+'0001'` matching the D86 key `01010001`. That
        holds for the 8209 twin pair, but **not** for the demo file:

            [NUMMER_001]_leer.X83   RNoPart chain ('1','1','1')  -> '111'
            StBALV23040.D86         flat OZ field               -> '01010001'

        Same bill of quantities — the quantity and unit sequences agree item for
        item — but `key()` overlap between them is **zero**, because the blank
        stores levels unpadded and the priced file pads them to 2/2/4. A naive
        key join silently matches nothing and makes the reveal look like a
        pricing failure.

        So: pad to the level widths of whatever you are joining *to*.
        `padded_key((2, 2, 4))` turns `('1','1','1')` into `'01010001'`.

        Falls back to `key()` when levels are unknown (GAEB 90 side), which is
        correct — that side is already in padded form.
        """
        if not self.oz_parts:
            return self.key()
        out = []
        for i, part in enumerate(self.oz_parts):
            width = widths[i] if i < len(widths) else len(part)
            out.append(normalize_oz(part).rjust(width, "0"))
        return "".join(out)

    def comparable(self) -> tuple:
        """The tuple the twin-pair gate asserts on. Text is deliberately out."""
        return (self.key(), round(self.quantity, 3), self.unit.strip().lower())

    def as_dict(self) -> dict:
        """JSON-safe form, used for the `data/golden/` fallback fixtures."""
        return {
            "oz": self.oz,
            "oz_parts": list(self.oz_parts),
            "section_path": list(self.section_path),
            "quantity": self.quantity,
            "unit": self.unit,
            "short_text": self.short_text,
            "long_text": self.long_text,
            "is_lump_sum": self.is_lump_sum,
            "unit_price": self.unit_price,
            "total_price": self.total_price,
            "source_file": self.source_file,
            "source_ref": self.source_ref,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "NormalizedItem":
        data = dict(raw)
        data["oz_parts"] = tuple(data.get("oz_parts") or ())
        data["section_path"] = tuple(data.get("section_path") or ())
        return cls(**data)


@dataclass
class Cluster:
    """A cross-cutting or section-level set of tender positions."""

    cluster_id: str
    kind: str
    title: str
    positions: list[str] = field(default_factory=list)
    euro_exposure: float = 0.0
    unknown_share: float = 0.0

    def as_dict(self) -> dict:
        """JSON-safe form of the cluster and its OZ back-pointers."""
        return {
            "cluster_id": self.cluster_id,
            "kind": self.kind,
            "title": self.title,
            "positions": list(self.positions),
            "euro_exposure": self.euro_exposure,
            "unknown_share": self.unknown_share,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Cluster":
        data = dict(raw)
        data["positions"] = list(data.get("positions") or ())
        return cls(**data)


@dataclass
class ClusterFlag:
    """One rule finding attached to an overlapping cluster."""

    rule_id: str
    kind: str
    cluster_id: str
    cluster_title: str
    severity: str
    reason_de: str
    computed: dict = field(default_factory=dict)
    affected_positions: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.rule_id

    @property
    def title(self) -> str:
        return self.cluster_title


@dataclass
class Finding:
    """One detector hit, as rendered in the UI and the RFI export."""

    item: NormalizedItem
    detector: str          # "unit_price_outlier" | "vague_scope" | "qty_sanity"
    severity: str          # "high" | "medium" | "low"
    rationale: str         # plain-English why, shown next to the row
    euro_leverage: float = 0.0   # quantity x price exposure; the ranking value
    evidence: dict = field(default_factory=dict)


@dataclass
class LogicResult:
    """Deterministic logic findings for one tender position."""

    flags: list[str]
    severity: str
    tags: list[str]
    details: list[str] = field(default_factory=list)


@dataclass
class HybridItemState:
    """Combined deterministic state of one position for hybrid risk scoring."""

    key: str
    oz: str
    qty: float
    unit: str
    logic_flags: list[str]
    logic_severity: str
    logic_details: list[str]
    is_specialist: bool
    specialist_hits: list[str]
    pre_unit_price: float
    price_source: str
    euro_exposure: float
    engine_divergence: float = 0.0
    benchmark_band: str = ""


@dataclass
class AtomicLLMJudgments:
    """Atomic hybrid-pipeline judgments produced by the LLM specialist."""

    unklar_beschrieben: float
    menge_unplausibel: float
    preis_unplausibel: float
    spezialgewerk: float
    nachtragspotenzial: float
    mindermengen_risiko: float = 0.0
    reasons: dict[str, str] = field(default_factory=dict)


@dataclass
class HybridRiskResult:
    """Final hybrid risk result for one tender position."""

    key: str
    risk_level: str
    euro_exposure: float
    pre_unit_price: float
    reasons: list[str]
    strategy: str
    action_type: str
    speculation_candidate: bool
    judgments: Optional[AtomicLLMJudgments] = None

    def to_finding(self, item: NormalizedItem) -> Finding:
        evidence = {
            "key": self.key,
            "risk_level": self.risk_level,
            "pre_unit_price": self.pre_unit_price,
            "reasons": list(self.reasons),
            "strategy": self.strategy,
            "action_type": self.action_type,
            "speculation_candidate": self.speculation_candidate,
        }
        if self.judgments is not None:
            evidence["judgments"] = {
                "unklar_beschrieben": self.judgments.unklar_beschrieben,
                "menge_unplausibel": self.judgments.menge_unplausibel,
                "preis_unplausibel": self.judgments.preis_unplausibel,
                "spezialgewerk": self.judgments.spezialgewerk,
                "nachtragspotenzial": self.judgments.nachtragspotenzial,
                "mindermengen_risiko": self.judgments.mindermengen_risiko,
                "reasons": dict(self.judgments.reasons),
            }
        return Finding(
            item=item,
            detector="hybrid_risk",
            severity=self.risk_level,
            rationale=" | ".join(self.reasons),
            euro_leverage=self.euro_exposure,
            evidence=evidence,
        )
