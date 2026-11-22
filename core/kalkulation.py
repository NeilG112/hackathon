"""Aufschlagskalkulation — the bottom-up price build-up.

This is how every construction firm actually prices, and the client described
it exactly: *"Du hast Material-Einsatz, du hast einen Personeneinsatz, dann
hast du einen Zuschlagssatz für die Firma... So rechnet jedes Bauunternehmen.
Das ist immer nach Lehrbuch."*

    EKT  = labour hours x Mittellohn
         + machine hours x machine rate
         + material quantity x material price
    EP   = EKT x (1 + Zuschlag)

Two properties that matter more than the arithmetic:

**It needs no price database.** Given a work type and the company's own rates,
it produces a price for a position nobody has ever quoted before. That is the
whole reason to prefer it over matching against comparable bids, which only
works when a comparable exists — on this dataset it did not, and the honest
error was -50%.

**It produces a range, not a point.** The Aufwandswerte carry `h_min`,
`h_mittel` and `h_max`, so a low/mid/high price falls out for free. An
estimator reading "between EUR 41 and EUR 68" learns something true; reading
"EUR 52.37" he learns something false. Where the band is wide, that *is* the
finding — it is the same position the estimator calls tricky.

Every number is traceable: `CalculatedItem.breakdown` carries the hours, the
machine time and the material that produced it, so the estimator can argue
with the input instead of distrusting the output.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional

from core.models import NormalizedItem
from core.stammdaten import Company, Leistung, Stammdaten

_UNIT_SCALES = (
    {"mm": 0.001, "cm": 0.01, "dm": 0.1, "m": 1.0, "km": 1000.0},
    {"mm2": 1e-6, "cm2": 1e-4, "dm2": 0.01, "m2": 1.0},
    {
        "mm3": 1e-9,
        "cm3": 1e-6,
        "ml": 1e-6,
        "l": 1e-3,
        "dm3": 1e-3,
        "m3": 1.0,
    },
    {"g": 0.001, "kg": 1.0, "t": 1000.0},
    {"s": 1 / 3600, "min": 1 / 60, "h": 1.0, "d": 24.0},
)


@dataclass
class CostBreakdown:
    """What the money is made of, per unit. The audit trail."""

    labour_hours: float = 0.0
    labour_eur: float = 0.0
    machine_hours: float = 0.0
    machine_eur: float = 0.0
    material_eur: float = 0.0
    material_detail: list = field(default_factory=list)
    machine_detail: list = field(default_factory=list)

    @property
    def ekt(self) -> float:
        """Einzelkosten der Teilleistung — direct cost before any markup."""
        return self.labour_eur + self.machine_eur + self.material_eur


@dataclass
class CalculatedItem:
    """One position, priced bottom-up."""

    item: NormalizedItem
    leistung: Optional[Leistung]
    confidence: float = 0.0

    ep_low: Optional[float] = None
    ep_mid: Optional[float] = None
    ep_high: Optional[float] = None
    breakdown: CostBreakdown = field(default_factory=CostBreakdown)
    note: str = ""

    @property
    def priced(self) -> bool:
        return self.ep_mid is not None

    @property
    def total(self) -> Optional[float]:
        return None if self.ep_mid is None else self.ep_mid * self.item.quantity

    @property
    def total_low(self) -> Optional[float]:
        return None if self.ep_low is None else self.ep_low * self.item.quantity

    @property
    def total_high(self) -> Optional[float]:
        return None if self.ep_high is None else self.ep_high * self.item.quantity

    @property
    def band_width(self) -> float:
        """How uncertain this position is, as a fraction of the mid price.

        The estimator's "tricky position" signal, computed rather than
        guessed: a wide band means the standard times themselves disagree
        about how long this work takes.
        """
        if not self.ep_mid:
            return 0.0
        return (self.ep_high - self.ep_low) / self.ep_mid

    @property
    def euro_at_stake(self) -> float:
        """Spread x quantity — what getting this position wrong costs."""
        if self.ep_low is None or self.ep_high is None:
            return 0.0
        return (self.ep_high - self.ep_low) * self.item.quantity


def unit_costs(leistung: Leistung, company: Company, data: Stammdaten,
               hours: float) -> CostBreakdown:
    """Direct cost for one unit of `leistung` at `hours` labour hours."""
    breakdown = CostBreakdown()

    breakdown.labour_hours = hours * company.leistungsfaktor
    breakdown.labour_eur = breakdown.labour_hours * company.mittellohn_eur_h

    for entry in leistung.geraet:
        code = entry.get("code", "")
        machine_hours = float(entry.get("stunden_je_einheit", 0.0))
        rate = data.machine_rate(code)
        breakdown.machine_hours += machine_hours
        breakdown.machine_eur += machine_hours * rate
        breakdown.machine_detail.append(
            {"code": code, "hours": machine_hours, "rate": rate,
             "eur": round(machine_hours * rate, 2)}
        )

    for entry in leistung.material:
        code = entry.get("code", "")
        quantity = float(entry.get("menge_je_einheit", 0.0))
        price = data.material_price(code) * company.materialfaktor
        breakdown.material_eur += quantity * price
        breakdown.material_detail.append(
            {"code": code, "menge": quantity, "preis": round(price, 2),
             "eur": round(quantity * price, 2)}
        )

    return breakdown


def _unit_conversion_factor(
    source_unit: str,
    target_unit: str,
    quantity: float,
) -> float | None:
    """Cost multiplier from one catalogue unit to one position unit."""
    if source_unit == target_unit:
        return 1.0
    if {source_unit, target_unit} == {"st", "psch"} and math.isclose(
        quantity,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        return 1.0
    for scales in _UNIT_SCALES:
        source_scale = scales.get(source_unit)
        target_scale = scales.get(target_unit)
        if source_scale is not None and target_scale is not None:
            return target_scale / source_scale
    return None


def _scale_breakdown(breakdown: CostBreakdown, factor: float) -> CostBreakdown:
    if factor == 1.0:
        return breakdown
    return CostBreakdown(
        labour_hours=breakdown.labour_hours * factor,
        labour_eur=breakdown.labour_eur * factor,
        machine_hours=breakdown.machine_hours * factor,
        machine_eur=breakdown.machine_eur * factor,
        material_eur=breakdown.material_eur * factor,
        material_detail=[
            {
                **entry,
                "menge": entry["menge"] * factor,
                "eur": round(entry["eur"] * factor, 2),
            }
            for entry in breakdown.material_detail
        ],
        machine_detail=[
            {
                **entry,
                "hours": entry["hours"] * factor,
                "eur": round(entry["eur"] * factor, 2),
            }
            for entry in breakdown.machine_detail
        ],
    )


def calculate_item(
    item: NormalizedItem,
    leistung: Optional[Leistung],
    company: Company,
    data: Stammdaten,
    confidence: float = 0.0,
) -> CalculatedItem:
    """Price one position. Returns an unpriced result when unclassified.

    An unclassified position is reported as such rather than guessed. That
    blank is the honest answer, and it is also the "nobody can price this from
    what is written" signal the estimator asked for.
    """
    if leistung is None:
        return CalculatedItem(
            item=item, leistung=None, confidence=confidence,
            note=(
                "keine Leistung zugeordnet — kein Kalkulationsansatz; "
                "Fallback über pricer.py erforderlich"
            ),
        )

    # The Aufwandswert is hours *per unit of the Leistung*. Multiplying a
    # position's quantity by it only means anything when both sides measure
    # the same thing. The classifier picks semantically from the whole
    # catalogue — correctly, since the right work is often billed in another
    # unit — so the units must be checked here instead.
    #
    # Without this guard the demo tender priced at EUR 2.9M against a real bid
    # of EUR 897k, because positions measured in mWo (metre-weeks of standing
    # time) were multiplied by per-m2 labour rates.
    from core import constants
    position_unit = constants.normalize_unit(item.unit)
    leistung_unit = constants.normalize_unit(leistung.einheit)
    conversion_factor = _unit_conversion_factor(
        leistung_unit,
        position_unit,
        item.quantity,
    )
    if conversion_factor is None:
        return CalculatedItem(
            item=item, leistung=leistung, confidence=confidence,
            note=(f"{leistung.code} wird in {leistung.einheit} abgerechnet, "
                  f"die Position in {item.unit} — keine sichere "
                  "Einheitenbrücke; Fallback über pricer.py erforderlich"),
        )

    # AGK prorated over the build time, plus BGK and W&G. See
    # Company.markup_factor — a combined percentage hides which decision costs
    # what, and AGK is an annual figure a ten-month job should only carry ten
    # twelfths of.
    markup = company.markup_factor()
    mid = _scale_breakdown(
        unit_costs(leistung, company, data, leistung.h_mittel),
        conversion_factor,
    )
    low = unit_costs(leistung, company, data, leistung.h_min)
    high = unit_costs(leistung, company, data, leistung.h_max)
    if mid.ekt <= 0:
        reason = f" ({leistung.bemerkung})" if leistung.bemerkung else ""
        return CalculatedItem(
            item=item, leistung=leistung, confidence=confidence,
            note=(f"{leistung.code} hat keine Aufwandswerte für den "
                  f"Mittelwert — nicht kalkulierbar{reason}"),
        )
    unit_note = (
        f"; Einheitenbrücke {leistung.einheit} → {item.unit} "
        f"(Faktor {conversion_factor:g})"
        if conversion_factor != 1.0
        else ""
    )

    return CalculatedItem(
        item=item,
        leistung=leistung,
        confidence=confidence,
        ep_low=round(low.ekt * markup * conversion_factor, 2),
        ep_mid=round(mid.ekt * markup, 2),
        ep_high=round(high.ekt * markup * conversion_factor, 2),
        breakdown=mid,
        note=(
            f"{leistung.code}: {mid.labour_hours:.3f} h x "
            f"{company.mittellohn_eur_h:,.2f} €/h"
            + (f" + {mid.machine_eur:,.2f} € Gerät" if mid.machine_eur else "")
            + (f" + {mid.material_eur:,.2f} € Material" if mid.material_eur else "")
            + f", +{company.total_markup_pct:.1f}% Zuschlag"
            + unit_note
        ),
    )


def calculate(
    items: Iterable[NormalizedItem],
    assignments: dict,
    company: Company,
    data: Stammdaten,
) -> list[CalculatedItem]:
    """Price a whole tender.

    `assignments` maps a position's OZ key to `(leistung_code, confidence)` —
    produced by `core.classify`. Keeping classification out of here means the
    calculation is pure arithmetic and can be tested on its own.
    """
    out = []
    for item in items:
        code, confidence = assignments.get(item.key(), (None, 0.0))
        out.append(calculate_item(item, data.leistung(code) if code else None,
                                  company, data, confidence))
    return out


def summarize(calculated: Iterable[CalculatedItem]) -> dict:
    """Totals, coverage and the uncertainty band on the bid as a whole."""
    rows = list(calculated)
    priced = [c for c in rows if c.priced]
    return {
        "positions": len(rows),
        "priced": len(priced),
        "unpriced": len(rows) - len(priced),
        "coverage_pct": round(100.0 * len(priced) / len(rows), 1) if rows else 0.0,
        "total_low": round(sum(c.total_low or 0.0 for c in priced), 2),
        "total_mid": round(sum(c.total or 0.0 for c in priced), 2),
        "total_high": round(sum(c.total_high or 0.0 for c in priced), 2),
        "labour_eur": round(sum((c.breakdown.labour_eur) * c.item.quantity
                                for c in priced), 2),
        "machine_eur": round(sum((c.breakdown.machine_eur) * c.item.quantity
                                 for c in priced), 2),
        "material_eur": round(sum((c.breakdown.material_eur) * c.item.quantity
                                  for c in priced), 2),
    }
