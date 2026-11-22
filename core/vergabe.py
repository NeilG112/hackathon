"""Vergabe — which trades the company builds itself and which it buys in.

One decision per trade, not per position: a 248-position tender has ~15
trades, and that is the level at which an estimator decides make-or-buy.

The rules this module exists to enforce:

**A subcontractor quote replaces the own calculation, it is never added.**
Otherwise the trade sits in the bid twice. `FREMD_ANGEBOT` therefore takes the
trade's own calculated total out and puts `einkauf x (1 + aufschlag)` in.

**No quote, no number.** A trade marked for subcontracting without a quote
(`FREMD_OFFEN`) contributes nothing to the bid and is listed in `offen`, so the
gap is visible instead of being filled with an invented figure.

**The default changes nothing.** `default_modus` only marks trades as
`FREMD_OFFEN` that carry no calculated value anyway, so loading the page never
moves the bid. Only a user decision does.

Pure functions, no Streamlit, no mutation: every call returns new objects.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable, Mapping, Optional, Sequence

from core import constants
from core.models import NormalizedItem
from core.objects import trade_of
from core.stammdaten import Company

UNASSIGNED_TRADE = "nicht zugeordnet"
DEFAULT_AUFSCHLAG_PCT = 10.0


class Modus(str, Enum):
    SELBST = "selbst"
    FREMD_OFFEN = "fremd_offen"        # will be subcontracted, no quote yet
    FREMD_ANGEBOT = "fremd_angebot"    # subcontractor quote is in


MODUS_LABEL = {
    Modus.SELBST: "selbst",
    Modus.FREMD_OFFEN: "fremd, Angebot fehlt",
    Modus.FREMD_ANGEBOT: "fremd, Angebot liegt vor",
}


@dataclass(frozen=True)
class GewerkEntscheidung:
    gewerk: str
    modus: Modus
    einkauf_eur: Optional[float] = None
    aufschlag_pct: float = DEFAULT_AUFSCHLAG_PCT

    @property
    def hat_angebot(self) -> bool:
        return (self.modus is Modus.FREMD_ANGEBOT
                and self.einkauf_eur is not None and self.einkauf_eur > 0)


@dataclass(frozen=True)
class GewerkZeile:
    """One row on the Vergabe screen."""

    gewerk: str
    positionen: tuple[str, ...]
    eigen_eur: float            # own calculation (mid), priced positions only
    eigen_gewinn_eur: float     # W&G share of that
    unkalkuliert: int           # positions without an own price
    entscheidung: GewerkEntscheidung
    angebot_eur: Optional[float]    # what this trade puts into the bid
    gewinn_eur: Optional[float]     # profit this trade contributes
    oft_vergeben: bool = False      # hint only, never changes the default

    @property
    def offen(self) -> bool:
        return self.entscheidung.modus is not Modus.SELBST \
            and not self.entscheidung.hat_angebot


@dataclass(frozen=True)
class VergabeErgebnis:
    zeilen: tuple[GewerkZeile, ...]
    angebotssumme: float
    gewinn_eigen: float
    gewinn_vergabe: float
    offen: tuple[str, ...]
    fremd_gesamt: int           # trades not built in-house
    fremd_mit_angebot: int

    @property
    def gewinn_gesamt(self) -> float:
        return self.gewinn_eigen + self.gewinn_vergabe


@dataclass(frozen=True)
class _Gruppe:
    gewerk: str
    positionen: tuple[str, ...]
    eigen_eur: float
    eigen_gewinn_eur: float
    kalkuliert: int


def default_modus(gewerk: str, kalkuliert: int) -> Modus:
    """Pre-select without moving the bid.

    A trade with no own price at all (unclassified, or every row lacking
    Aufwandswerte) cannot be built from the company's own figures, so it starts
    as "fremd, Angebot fehlt". Everything else starts as "selbst".
    """
    if gewerk == UNASSIGNED_TRADE or kalkuliert == 0:
        return Modus.FREMD_OFFEN
    return Modus.SELBST


def default_entscheidung(gewerk: str, kalkuliert: int) -> GewerkEntscheidung:
    return GewerkEntscheidung(gewerk=gewerk, modus=default_modus(gewerk, kalkuliert))


def _gruppieren(
    items: Iterable[NormalizedItem],
    assignments: Mapping,
    data,
    calculated: Sequence,
    company: Company,
) -> list[_Gruppe]:
    by_key = {c.item.key(): c for c in calculated}
    wg_share = company.wg_pct / 100.0
    acc: dict[str, dict] = {}
    for item in items:
        gewerk = trade_of(item, assignments, data)
        row = acc.setdefault(gewerk, {"pos": [], "eur": 0.0, "wg": 0.0, "n": 0})
        row["pos"].append(item.key())
        calc = by_key.get(item.key())
        if calc is not None and calc.priced:
            row["eur"] += calc.total or 0.0
            row["wg"] += calc.breakdown.ekt * item.quantity * wg_share
            row["n"] += 1
    return [
        _Gruppe(g, tuple(r["pos"]), r["eur"], r["wg"], r["n"])
        for g, r in acc.items()
    ]


def _zeile(gruppe: _Gruppe, entscheidung: GewerkEntscheidung) -> GewerkZeile:
    if entscheidung.modus is Modus.SELBST:
        angebot, gewinn = gruppe.eigen_eur, gruppe.eigen_gewinn_eur
    elif entscheidung.hat_angebot:
        einkauf = float(entscheidung.einkauf_eur)
        aufschlag = einkauf * entscheidung.aufschlag_pct / 100.0
        angebot, gewinn = einkauf + aufschlag, aufschlag
    else:
        angebot, gewinn = None, None
    return GewerkZeile(
        gewerk=gruppe.gewerk,
        positionen=gruppe.positionen,
        eigen_eur=gruppe.eigen_eur,
        eigen_gewinn_eur=gruppe.eigen_gewinn_eur,
        unkalkuliert=len(gruppe.positionen) - gruppe.kalkuliert,
        entscheidung=entscheidung,
        angebot_eur=angebot,
        gewinn_eur=gewinn,
        oft_vergeben=gruppe.gewerk in constants.NU_TYPISCHE_GEWERKE,
    )


def auswerten(
    items: Sequence[NormalizedItem],
    assignments: Mapping,
    data,
    calculated: Sequence,
    company: Company,
    entscheidungen: Optional[Mapping[str, GewerkEntscheidung]] = None,
) -> VergabeErgebnis:
    """Apply the make-or-buy decisions to a calculated tender.

    Trades without an explicit decision get `default_entscheidung`. Rows are
    sorted own-built first, then by volume, so the trades that still need
    attention sit together at the bottom.
    """
    entscheidungen = entscheidungen or {}
    zeilen = []
    for gruppe in _gruppieren(items, assignments, data, calculated, company):
        e = entscheidungen.get(gruppe.gewerk) or default_entscheidung(
            gruppe.gewerk, gruppe.kalkuliert)
        zeilen.append(_zeile(gruppe, e))

    zeilen.sort(key=lambda z: (z.entscheidung.modus is not Modus.SELBST,
                               -(z.angebot_eur or z.eigen_eur), z.gewerk))
    fremd = [z for z in zeilen if z.entscheidung.modus is not Modus.SELBST]
    return VergabeErgebnis(
        zeilen=tuple(zeilen),
        angebotssumme=round(sum(z.angebot_eur or 0.0 for z in zeilen), 2),
        gewinn_eigen=round(sum(z.gewinn_eur or 0.0 for z in zeilen
                               if z.entscheidung.modus is Modus.SELBST), 2),
        gewinn_vergabe=round(sum(z.gewinn_eur or 0.0 for z in fremd), 2),
        offen=tuple(z.gewerk for z in fremd if z.offen),
        fremd_gesamt=len(fremd),
        fremd_mit_angebot=sum(1 for z in fremd if not z.offen),
    )


def mit_entscheidung(
    entscheidungen: Mapping[str, GewerkEntscheidung],
    neu: GewerkEntscheidung,
) -> dict[str, GewerkEntscheidung]:
    """Return a new decision map with `neu` applied. Never mutates the input."""
    return {**entscheidungen, neu.gewerk: neu}


def setze_modus(e: GewerkEntscheidung, modus: Modus) -> GewerkEntscheidung:
    return replace(e, modus=modus)
