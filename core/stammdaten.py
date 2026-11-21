"""Company master data — the rate tables the calculation reads.

The client was explicit: *"Ihr bekommt von uns gar nichts. Ihr bekommt nur die
Beschreibung."* No prices come with a tender. Labour and machine rates are the
contractor's own, and the client's suggested approach was to generate a
plausible Stammdatensatz and make it a parameter the company can adjust.

That is what this is. `Database/data/` holds:

    arbeitszeitrichtwerte.json   34 Leistungen: h_min / h_mittel / h_max per
                                 unit, plus the material and machine each one
                                 consumes. These are the Aufwandswerte.
    materialien.json             21 material prices
    geraete.json                 10 machine rates per hour
    testdb/testdatenbank.sqlite  the same data plus labelled test cases

**The data is synthetic and says so.** Its own metadata reads *"Synthetisch.
Keine ARH-Originalwerte, keine Marktpreisabfrage."* That is fine and it is the
honest position: the deliverable is the *method* — a transparent build-up a
contractor can audit line by line — with the rate table as a parameter he
swaps for his own. Never present these numbers as market data.

JSON is the runtime source because a lookup is all the engine needs and diffs
stay readable in git. The SQLite carries the relational extras (projects,
bids, expected test results) and is used by `evaluate.py`, not at runtime.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "Database", "data")
SQLITE = os.path.join(ROOT, "testdb", "testdatenbank.sqlite")


@dataclass
class Leistung:
    """One work type: how long it takes and what it consumes, per unit."""

    code: str
    gewerk: str
    taetigkeit: str
    einheit: str
    h_min: float
    h_mittel: float
    h_max: float
    material: list = field(default_factory=list)   # [{code, menge_je_einheit}]
    geraet: list = field(default_factory=list)     # [{code, stunden_je_einheit}]
    bemerkung: str = ""

    def label(self) -> str:
        return f"{self.code} · {self.taetigkeit}"


@dataclass
class Company:
    """The cost base. Mirrors the `bieter` table so profiles can be loaded."""

    name: str = "Eigene Kalkulation"
    mittellohn_eur_h: float = 58.0
    zuschlag_pct: float = 22.0      # AGK + BGK + Wagnis & Gewinn, combined
    leistungsfaktor: float = 1.0    # >1 = slower than the standard times
    materialfaktor: float = 1.0     # >1 = buys material dearer
    profil: str = ""


class Stammdaten:
    """Loaded rate tables. Construct once, pass around; it is read-only."""

    def __init__(self, leistungen: dict, materialien: dict, geraete: dict,
                 meta: Optional[dict] = None):
        self.leistungen = leistungen
        self.materialien = materialien
        self.geraete = geraete
        self.meta = meta or {}

    # --- lookups ----------------------------------------------------------

    def leistung(self, code: str) -> Optional[Leistung]:
        return self.leistungen.get(code)

    def material_price(self, code: str) -> float:
        return float(self.materialien.get(code, {}).get("preis_eur", 0.0))

    def machine_rate(self, code: str) -> float:
        return float(self.geraete.get(code, {}).get("kosten_eur_h", 0.0))

    def by_unit(self, unit: str) -> list[Leistung]:
        """Candidate work types measured in this unit — the classifier's shortlist."""
        unit = (unit or "").strip().lower()
        return [l for l in self.leistungen.values() if l.einheit.lower() == unit]

    def codes(self) -> list[str]:
        return sorted(self.leistungen)

    @property
    def is_synthetic(self) -> bool:
        return "synthet" in json.dumps(self.meta, ensure_ascii=False).lower()

    def describe(self) -> str:
        return (f"{len(self.leistungen)} Leistungen, {len(self.materialien)} "
                f"Materialien, {len(self.geraete)} Geräte")


def _read(name: str, key: str) -> tuple[dict, dict]:
    path = os.path.join(ROOT, f"{name}.json")
    if not os.path.exists(path):
        return {}, {}
    with open(path, encoding="utf-8") as fh:
        blob = json.load(fh)
    return blob.get(key, {}), blob.get("meta", {})


@lru_cache(maxsize=1)
def load() -> Stammdaten:
    """Load the rate tables. Returns an empty set rather than raising.

    A missing database must degrade visibly in the UI, not crash on stage.
    """
    raw_l, meta = _read("arbeitszeitrichtwerte", "leistungen")
    materialien, _ = _read("materialien", "materialien")
    geraete, _ = _read("geraete", "geraete")

    leistungen = {
        code: Leistung(
            code=code,
            gewerk=v.get("gewerk", ""),
            taetigkeit=v.get("taetigkeit", ""),
            einheit=v.get("einheit", ""),
            h_min=float(v.get("h_min", 0.0)),
            h_mittel=float(v.get("h_mittel", 0.0)),
            h_max=float(v.get("h_max", 0.0)),
            material=v.get("material", []) or [],
            geraet=v.get("geraet", []) or [],
            bemerkung=v.get("bemerkung", ""),
        )
        for code, v in raw_l.items()
    }
    return Stammdaten(leistungen, materialien, geraete, meta)


def companies() -> list[Company]:
    """Cost-base presets from the test database, for the UI's picker.

    The schema moved: parameters used to live on a `bieter` table and now sit
    on each `angebote` row (with `materialfaktor` renamed `materialindex`).
    Both layouts are tried, newest first, and a missing or unknown schema
    falls back to one neutral profile rather than raising — a changed test
    database must not take the app down.
    """
    if not os.path.exists(SQLITE):
        return [Company()]

    queries = (
        # current: parameters per offer, company name via unternehmen
        """SELECT u.firma, a.mittellohn_eur_h, a.zuschlag_pct, a.leistungsfaktor,
                  a.materialindex, p.projekttyp
           FROM angebote a
           LEFT JOIN unternehmen u ON u.id = a.unternehmen_id
           LEFT JOIN projekte p ON p.id = a.projekt_id
           GROUP BY a.mittellohn_eur_h, a.zuschlag_pct
           ORDER BY a.mittellohn_eur_h LIMIT 8""",
        # previous: a dedicated bidder table
        """SELECT firma, mittellohn_eur_h, zuschlag_pct, leistungsfaktor,
                  materialfaktor, profil FROM bieter ORDER BY id""",
    )
    for sql in queries:
        try:
            con = sqlite3.connect(SQLITE)
            rows = con.execute(sql).fetchall()
            con.close()
        except sqlite3.Error:
            continue
        built = [
            Company(
                name=row[0] or "Angebotsprofil",
                mittellohn_eur_h=float(row[1] or 58.0),
                zuschlag_pct=float(row[2] or 22.0),
                leistungsfaktor=float(row[3] or 1.0),
                materialfaktor=float(row[4] or 1.0),
                profil=row[5] or "",
            )
            for row in rows
        ]
        if built:
            return built
    return [Company()]
