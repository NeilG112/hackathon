#!/usr/bin/env python3
"""Synthetische Test-Datenbank für den Bid & Risk Assistant — Angebotshistorie EINES Unternehmens.

    python3 scripts/generate_testdata.py           # aus dem Repo-Root
    python3 scripts/generate_testdata.py --csv     # zusätzlich CSV zum Anschauen

Schreibt, relativ zum Repo-Root:

    data/testdb/testdatenbank.sqlite   alle Tabellen — für Tests und Auswertung
    data/arbeitszeitrichtwerte.json    Leistungen mit h/Einheit, Material, Gerät — Laufzeit
    data/materialien.json              Materialpreise — Laufzeit
    data/geraete.json                  Gerätekosten je h — Laufzeit

Bewusst unabhängig von den LVs in Dataset/: kein Text, keine Menge, kein Preis
wird von dort übernommen. Alles entsteht aus einem Kalkulationsmodell:

    EP = (Stunden × Mittellohn + Material + Gerät) × (1 + Zuschlag) × Streuung

Die Stunden je Einheit stehen in `arbeitszeitrichtwerte` — eigene, plausible
Schätzwerte in der Größenordnung üblicher Arbeitszeit-Richtwerte (ARH) für
Tiefbau/Leitungsbau. **Keine Originalwerte aus den ARH-Tabellen** (die liegen
nicht vor); vor Verwendung als Referenz gegen das Tabellenwerk prüfen.

Ein Unternehmen (fiktiv), 140 Ausschreibungen 2022–2026, je ein eigenes Angebot.
Mittellohn, Zuschlag und Materialindex ändern sich über die Zeit.

Die Mengen folgen aus der Geometrie jedes Projekts (Trassenlänge, Tiefe,
Breite), damit sie untereinander stimmig sind. Fehler werden gezielt
eingebaut und in `testfall_erwartungen` als Soll-Ergebnis dokumentiert.

Nur Standardbibliothek, fester Seed: jeder Lauf erzeugt dieselben Daten.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sqlite3

SEED = 2026
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_REL = os.path.join("data", "testdb", "testdatenbank.sqlite")
CSV_REL = os.path.join("data", "testdb", "csv")
HERKUNFT = "synthetisch, Größenordnung angelehnt an ARH Tiefbau — nicht aus dem Tabellenwerk"

# --- Stammdaten -------------------------------------------------------------

GERAETE = {
    "BAG14": ("Mobilbagger 14 t", 68.0),
    "BAG25": ("Kettenbagger 25 t", 98.0),
    "RLD": ("Radlader 2 m³", 58.0),
    "LKW": ("LKW 3-Achs-Kipper", 72.0),
    "RUE": ("Rüttelplatte 400 kg", 9.5),
    "WAL": ("Tandemwalze 3 t", 31.0),
    "FER": ("Asphaltfertiger", 185.0),
    "VBG": ("Grabenverbaugerät (Vorhaltung)", 14.0),
    "KLG": ("Kleingerät / Handwerkzeug", 4.0),
    "SAEG": ("Fugenschneider", 12.0),
}

MATERIALIEN = {
    "SAND": ("Sand 0/2", "t", 21.50),
    "FSS": ("Frostschutzmaterial 0/45", "t", 19.80),
    "BET": ("Beton C20/25", "m3", 152.00),
    "MAG": ("Magerbeton C8/10", "m3", 118.00),
    "KG150": ("PVC-KG-Rohr DN 150", "m", 11.80),
    "KG200": ("PVC-KG-Rohr DN 200", "m", 19.90),
    "SB300": ("Stahlbetonrohr DN 300", "m", 46.00),
    "SB500": ("Stahlbetonrohr DN 500", "m", 92.00),
    "PE110": ("PE-HD-Rohr da 110 SDR 11", "m", 9.40),
    "PE160": ("PE-HD-Rohr da 160 SDR 11", "m", 19.60),
    "KSR": ("Kabelschutzrohr DN 110", "m", 2.70),
    "WARN": ("Trassenwarnband", "m", 0.16),
    "SCH1000": ("Schachtbauteile DN 1000 (Boden, Ringe, Konus)", "St", 1180.00),
    "ABD": ("Schachtabdeckung Klasse D 400", "St", 335.00),
    "ANSCH": ("Formteile / Anschlussmaterial", "St", 85.00),
    "PFL": ("Betonsteinpflaster 8 cm", "m2", 17.50),
    "BORD": ("Hochbordstein 15/30", "m", 13.20),
    "ACT": ("Asphalttragschicht AC 22 TS", "t", 71.00),
    "ACD": ("Asphaltdeckschicht AC 11 DS", "t", 86.00),
    "DEP": ("Deponiegebühr Boden Z 1.1", "t", 17.50),
    "BAKE": ("Absperrmaterial, Miete je Woche", "Wo", 38.00),
}

# code, gewerk, kurztext, einheit, h_mittel, materialien, geräte, langtext
LEISTUNGEN = [
    ("E01", "Erdbau", "Oberboden abtragen und seitlich lagern", "m2", 0.012, [],
     [("BAG14", 0.010)], "Oberboden d = 20 cm abtragen, im Baufeld lagern, gegen Vernässung schützen."),
    ("E02", "Erdbau", "Boden Homogenbereich B2 lösen, laden, abfahren", "m3", 0.060,
     [("DEP", 1.8)], [("BAG14", 0.050), ("LKW", 0.050)],
     "Grabenaushub maschinell, Boden laden, zur Deponie fahren, Gebühr nach Wiegeschein."),
    ("E03", "Erdbau", "Boden von Hand lösen im Bereich vorhandener Leitungen", "m3", 2.200,
     [("DEP", 1.8)], [("KLG", 2.0)], "Handschachtung im Kreuzungsbereich von Fremdleitungen."),
    ("E04", "Erdbau", "Graben mit Fremdmaterial verfüllen und lagenweise verdichten", "m3", 0.180,
     [("SAND", 1.9)], [("BAG14", 0.08), ("RUE", 0.15)], "Einbau in Lagen ≤ 30 cm, Dpr ≥ 97 %."),
    ("E05", "Erdbau", "Leitungszone mit Sand 0/2 herstellen", "m3", 0.450,
     [("SAND", 1.8)], [("RUE", 0.30)], "Bettung und Abdeckung 30 cm über Rohrscheitel."),
    ("E06", "Erdbau", "Planum herstellen und verdichten", "m2", 0.020, [],
     [("WAL", 0.010)], "Planum Ev2 ≥ 45 MN/m², Höhentoleranz ± 2 cm."),
    ("E07", "Oberbau", "Frostschutzschicht 0/45 einbauen, d = 30 cm", "m2", 0.050,
     [("FSS", 0.60)], [("RLD", 0.02), ("WAL", 0.02)], "Ev2 ≥ 120 MN/m² auf der Oberfläche."),
    ("V01", "Verbau", "Grabenverbau einbauen, vorhalten, rückbauen, Tiefe ≤ 3,0 m", "m2", 0.350, [],
     [("VBG", 0.60), ("BAG14", 0.08)], "Abrechnung nach verbauter Grabenwandfläche."),
    ("V02", "Verbau", "Zulage Grabenverbau für Tiefe > 3,0 bis 4,0 m", "m2", 0.120, [],
     [("VBG", 0.30)], "Zulage zur Position Grabenverbau."),
    ("K01", "Kanal", "PVC-KG-Rohr DN 150 verlegen", "m", 0.220,
     [("KG150", 1.02), ("ANSCH", 0.05)], [("KLG", 0.20)], "Einschl. Formstücke, Gefälle nach Plan."),
    ("K02", "Kanal", "PVC-KG-Rohr DN 200 verlegen", "m", 0.280,
     [("KG200", 1.02), ("ANSCH", 0.05)], [("KLG", 0.25)], "Einschl. Formstücke, Gefälle nach Plan."),
    ("K03", "Kanal", "Stahlbetonrohr DN 300 verlegen", "m", 0.550,
     [("SB300", 1.0)], [("BAG14", 0.25)], "Rohre mit Glockenmuffe, Dichtung nach DIN EN 1916."),
    ("K04", "Kanal", "Stahlbetonrohr DN 500 verlegen", "m", 0.850,
     [("SB500", 1.0)], [("BAG25", 0.35)], "Rohre mit Glockenmuffe, Dichtung nach DIN EN 1916."),
    ("K05", "Wasser", "PE-HD-Rohr da 110 verlegen, einschl. Schweißverbindungen", "m", 0.300,
     [("PE110", 1.02)], [("KLG", 0.30)], "Heizwendelschweißung, Druckprüfung gesondert."),
    ("K06", "Wasser", "PE-HD-Rohr da 160 verlegen, einschl. Schweißverbindungen", "m", 0.420,
     [("PE160", 1.02)], [("KLG", 0.35)], "Heizwendelschweißung, Druckprüfung gesondert."),
    ("K07", "Kabel", "Kabelschutzrohr DN 110 verlegen", "m", 0.060,
     [("KSR", 1.03)], [], "In vorbereiteten Graben, Muffen gesteckt."),
    ("K08", "Kabel", "Trassenwarnband verlegen", "m", 0.010,
     [("WARN", 1.05)], [], "30 cm über Leitung."),
    ("K09", "Kanal", "Dichtheitsprüfung je Haltung", "St", 3.000, [],
     [("KLG", 2.0)], "Prüfung mit Luft nach DIN EN 1610, Protokoll."),
    ("K10", "Kanal", "TV-Inspektion des neuen Kanals", "m", 0.040, [],
     [("KLG", 0.04)], "Befahrung, Video und Bericht."),
    ("K11", "Kanal", "Hausanschluss herstellen, einschl. Abzweig", "St", 6.500,
     [("ANSCH", 2.5), ("KG150", 3.0)], [("BAG14", 1.5)], "Anschluss bis Grundstücksgrenze."),
    ("S01", "Schacht", "Schacht DN 1000 aus Fertigteilen setzen, Tiefe bis 3,0 m", "St", 7.500,
     [("SCH1000", 1.0), ("MAG", 0.4)], [("BAG25", 2.5)], "Fertigteile nach DIN 4034-1."),
    ("S02", "Schacht", "Zulage Schachttiefe je angefangene 0,5 m über 3,0 m", "St", 1.600,
     [("SCH1000", 0.18)], [("BAG25", 0.40)], "Zulage zur Position Schacht."),
    ("S03", "Schacht", "Schachtabdeckung D 400 setzen und regulieren", "St", 2.200,
     [("ABD", 1.0), ("BET", 0.05)], [("KLG", 1.0)], "Auf Höhe der fertigen Oberfläche."),
    ("S04", "Schacht", "Gerinne herstellen", "St", 3.500,
     [("BET", 0.15)], [("KLG", 2.0)], "Gerinne in Beton, Berme mit Gefälle."),
    ("T01", "Straße", "Asphalt schneiden", "m", 0.050, [], [("SAEG", 0.05)], "Schnitttiefe bis 20 cm."),
    ("T02", "Straße", "Asphalt aufbrechen, laden, entsorgen", "m2", 0.060,
     [("DEP", 0.25)], [("BAG14", 0.04), ("LKW", 0.03)], "Dicke bis 15 cm, teerfrei lt. Gutachten."),
    ("T03", "Straße", "Asphalttragschicht AC 22 TS einbauen, d = 10 cm", "m2", 0.030,
     [("ACT", 0.245)], [("FER", 0.006), ("WAL", 0.010)], "Maschineller Einbau."),
    ("T04", "Straße", "Asphaltdeckschicht AC 11 DS einbauen, d = 4 cm", "m2", 0.025,
     [("ACD", 0.100)], [("FER", 0.005), ("WAL", 0.010)], "Maschineller Einbau."),
    ("T05", "Straße", "Betonsteinpflaster 8 cm verlegen, einschl. Bettung", "m2", 0.380,
     [("PFL", 1.02), ("SAND", 0.08)], [("RUE", 0.05)], "Läuferverband, Fugen mit Sand."),
    ("T06", "Straße", "Hochbordstein 15/30 in Beton setzen", "m", 0.280,
     [("BORD", 1.0), ("BET", 0.06)], [("KLG", 0.30)], "Rückenstütze in Beton C20/25."),
    ("B01", "Baustelle", "Baustelleneinrichtung einrichten, vorhalten, räumen", "psch", 0.0, [],
     [], "Kalkuliert als Anteil der Einzelkosten aller übrigen Positionen."),
    ("B02", "Baustelle", "Verkehrssicherung vorhalten", "Wo", 1.000,
     [("BAKE", 1.0)], [], "Absperrung und Beschilderung nach RSA, je Woche."),
    ("B03", "Baustelle", "Stundenlohnarbeiten Facharbeiter", "h", 1.000, [], [],
     "Nur auf Anordnung der Bauleitung."),
    ("B04", "Baustelle", "Bestandsdokumentation und Aufmaß", "psch", 14.0, [], [],
     "Digitale Bestandspläne nach Vorgabe des Netzbetreibers."),
]
LEISTUNG = {row[0]: row for row in LEISTUNGEN}
SPREIZUNG = 0.25   # h_min / h_max = h_mittel × (1 ∓ 0,25)
BE_ANTEIL = 0.045  # Baustelleneinrichtung als Anteil der übrigen Einzelkosten

UNTERNEHMEN = {
    "id": 1, "firma": "Musterbau Tiefbau GmbH", "sitz": "Beispielstadt",
    "profil": "Mittelständischer Tief- und Leitungsbauer, ca. 60 gewerbliche Mitarbeiter",
}

# Kalkulationsparameter des Unternehmens, die sich über die Zeit ändern.
MITTELLOHN_2022 = 52.0          # €/h, steigt jährlich
LOHNSTEIGERUNG = 0.035          # je Jahr
MATERIALINDEX = {2022: 0.94, 2023: 0.98, 2024: 0.99, 2025: 1.00, 2026: 1.02}
ZUSCHLAG = (0.18, 0.27)         # BGK + AGK + W&G, je nach Auslastung
STREUUNG = 0.07                 # Rauschen je Position (Kalkulatoren-Handschrift)
LEISTUNGSFAKTOR = (0.92, 1.12)  # projektabhängige Erschwernis
ZUSCHLAGSQUOTE = 0.30           # Anteil beauftragter Angebote (Annahme, synthetisch)
ANZAHL_PROJEKTE = 140

# Wahrscheinlichkeiten je Projekt / Position für eingebaute Fehler
P_VAGE_JE_POSITION = 0.04
P_RUNDE_MENGE = 0.25
P_EINHEITENFEHLER = 0.20
P_MENGENRISIKO = 0.45           # nur bei beauftragten Projekten
P_KOMMAFEHLER_JE_POSITION = 0.008

PROJEKTTYPEN = {
    "Erschließung Baugebiet": dict(L=(300, 900), d=(2.0, 3.0), b=(1.0, 1.3),
                                   opt=lambda r: {"kanal": "K03", "wasser": "K05",
                                                  "strasse": "neu", "pflaster": True}),
    "Kanalauswechslung": dict(L=(150, 450), d=(2.8, 3.8), b=(1.2, 1.5),
                              opt=lambda r: {"kanal": r.choice(["K03", "K04"]), "strasse": "aufbruch"}),
    "Regenwasserkanal": dict(L=(250, 700), d=(2.2, 3.2), b=(1.1, 1.4),
                             opt=lambda r: {"kanal": r.choice(["K03", "K04"]),
                                            "kabel": r.random() < 0.4}),
    "Wasserleitungserneuerung": dict(L=(300, 1200), d=(1.4, 1.8), b=(0.8, 1.0),
                                     opt=lambda r: {"wasser": r.choice(["K05", "K06"]),
                                                    "strasse": "aufbruch", "kabel": r.random() < 0.5}),
    "Leerrohrtrasse": dict(L=(800, 2500), d=(0.8, 1.2), b=(0.4, 0.6),
                           opt=lambda r: {"kabel": True}),
    "Parkplatz und Zufahrt": dict(A=(800, 4000)),
}
ORTE = ["Beispielstadt", "Musterhausen", "Beispieldorf", "Musterau", "Testingen", "Demohausen",
        "Exempelberg", "Probstadt"]
LAGEN = ["Hauptstraße", "Bahnhofstraße", "Lindenweg", "Am Mühlbach", "Gartenstraße", "Schulstraße",
         "Gewerbegebiet Süd", "Gewerbegebiet Nord", "Kirchplatz", "Am Sportplatz", "Feldweg",
         "Kreisstraße K 12", "Ortsdurchfahrt", "Wiesengrund", "Schulzentrum", "Friedhof"]
AUFTRAGGEBER = ["Stadt {o}", "Stadtwerke {o}", "Abwasserzweckverband {o}",
                "Wasserversorgung {o}", "Gemeinde {o}"]

VAGE_FORMULIERUNGEN = [
    "Ausführung nach Wahl des Auftraggebers.",
    "Erforderlichenfalls ist ein zusätzlicher Bodenaustausch vorzunehmen.",
    "Leistungsumfang in Abstimmung mit der Bauleitung vor Ort.",
    "Fabrikat Typ X oder gleichwertig.",
    "Ggf. anfallende Mehrmengen sind einzurechnen.",
]

VORBEMERKUNGEN = [
    ("Es gelten die VOB/B sowie die einschlägigen ATV der VOB/C.", 0, ""),
    ("Arbeitszeiten werktags von 7:00 bis 18:00 Uhr.", 0, ""),
    ("Der AN hat sich vor Angebotsabgabe über die Boden- und Grundwasserverhältnisse zu "
     "informieren. Mehrkosten aus abweichenden Bodenverhältnissen werden nicht vergütet.", 1,
     "Baugrundrisiko wird auf den AN verlagert (nach VOB/B trägt es grundsätzlich der AG)."),
    ("Erschwernisse durch Grundwasser und Schichtenwasser sind in die Einheitspreise "
     "einzurechnen.", 1, "Wasserhaltung nicht als eigene Position — unkalkulierbares Wagnis."),
    ("Bei Überschreitung der Ausführungsfrist wird eine Vertragsstrafe von 0,3 % der "
     "Auftragssumme je Werktag fällig, höchstens 10 %.", 1,
     "Obergrenze 10 % liegt über den in der Rechtsprechung üblich gebilligten 5 %."),
    ("Leitungsauskünfte der Versorger liegen dem AG vor und werden auf Anforderung übergeben.",
     0, ""),
    ("Die Kosten der Baustelleneinrichtung sind in die Einheitspreise einzurechnen.", 1,
     "Widerspricht der eigenen BE-Position im LV — Gefahr von Doppel- oder Nichtvergütung."),
]


# --- Mengenermittlung -------------------------------------------------------

def graben_positionen(L: float, d: float, b: float, opt: dict) -> list[tuple]:
    """(titel, code, menge, positionsart) aus der Grabengeometrie."""
    schaechte = math.ceil(L / 45) if opt.get("kanal") else 0
    out = [("01", "B01", 1, "Normal"), ("01", "B02", math.ceil(L / 40) + 2, "Normal"),
           ("01", "B03", 40, "Eventual"), ("01", "B04", 1, "Normal")]
    if opt.get("strasse") == "aufbruch":
        out += [("02", "T01", 2 * L, "Normal"), ("02", "T02", L * (b + 0.6), "Normal")]
    out += [("02", "E02", L * b * d * 0.9, "Normal"), ("02", "E03", L * 0.08, "Eventual"),
            ("02", "E05", L * b * 0.5, "Normal"), ("02", "E04", L * b * max(d - 0.5, 0.3), "Normal")]
    if d > 1.75:
        out.append(("02", "V01", 2 * L * min(d, 3.0), "Normal"))
    if d > 3.0:
        out.append(("02", "V02", 2 * L * (d - 3.0), "Normal"))
    if opt.get("kanal"):
        out += kanal_positionen(L, d, opt["kanal"], schaechte)
    if opt.get("wasser"):
        out.append(("04", opt["wasser"], L * 1.05, "Normal"))
    if opt.get("kabel"):
        out += [("04", "K07", L * 1.02, "Normal"), ("04", "K08", L, "Normal")]
    if opt.get("strasse"):
        flaeche = L * (b + 0.6) if opt["strasse"] == "aufbruch" else L * 6.5
        out += [("05", c, flaeche, "Normal") for c in ("E06", "E07", "T03", "T04")]
    if opt.get("pflaster"):
        out += [("05", "T05", L * 2.5, "Normal"), ("05", "T06", L * 2, "Normal")]
    return out


def kanal_positionen(L: float, d: float, rohr: str, schaechte: int) -> list[tuple]:
    out = [("03", rohr, L, "Normal"), ("03", "K11", round(L / 12), "Normal"),
           ("03", "S01", schaechte, "Normal"), ("03", "S03", schaechte, "Normal"),
           ("03", "S04", schaechte, "Normal"), ("03", "K09", max(schaechte - 1, 1), "Normal"),
           ("03", "K10", L, "Normal")]
    tiefe_zulage = schaechte * max(0, math.ceil((d - 3.0) / 0.5))
    if tiefe_zulage:
        out.append(("03", "S02", tiefe_zulage, "Normal"))
    return out


def flaechen_positionen(A: float) -> list[tuple]:
    umfang = 4 * math.sqrt(A)
    return [("01", "B01", 1, "Normal"), ("01", "B02", max(4, round(A / 400)), "Normal"),
            ("01", "B03", 24, "Eventual"), ("02", "E01", A * 1.1, "Normal"),
            ("02", "E02", A * 0.45, "Normal"), ("02", "E06", A, "Normal"), ("02", "E07", A, "Normal"),
            ("03", "K01", round(A / 20), "Normal"), ("03", "S01", max(1, round(A / 1200)), "Normal"),
            ("03", "S03", max(1, round(A / 1200)), "Normal"), ("05", "T05", A * 0.7, "Normal"),
            ("05", "T03", A * 0.3, "Normal"), ("05", "T04", A * 0.3, "Normal"),
            ("05", "T06", umfang, "Normal")]


def menge_runden(menge: float, einheit: str) -> float:
    if einheit in ("St", "psch", "Wo", "h"):
        return float(max(1, round(menge)))
    return round(menge, 1 if menge >= 100 else 2)


# --- Projekte erzeugen ------------------------------------------------------

def projekt_spec(rng: random.Random, projekt_id: int) -> dict:
    """Ein zufälliges, in sich stimmiges Projekt des Unternehmens."""
    typ = rng.choice(list(PROJEKTTYPEN))
    cfg = PROJEKTTYPEN[typ]
    ort = rng.choice(ORTE)
    jahr = rng.choice(list(MATERIALINDEX))
    spec = {"id": projekt_id, "typ": typ, "ort": ort, "jahr": jahr,
            "bezeichnung": f"{typ} {rng.choice(LAGEN)}",
            "auftraggeber": rng.choice(AUFTRAGGEBER).format(o=ort),
            "submission": f"{jahr}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "L": 0.0, "d": 0.0, "b": 0.0, "A": None, "opt": {}}
    if "A" in cfg:
        spec["A"] = round(rng.uniform(*cfg["A"]), -1)
    else:
        spec.update(L=round(rng.uniform(*cfg["L"]), -1), d=round(rng.uniform(*cfg["d"]), 1),
                    b=round(rng.uniform(*cfg["b"]), 1), opt=cfg["opt"](rng))
    return spec


def kalkulationsparameter(rng: random.Random, jahr: int) -> dict:
    return {"mittellohn": round(MITTELLOHN_2022 * (1 + LOHNSTEIGERUNG) ** (jahr - 2022) * 2) / 2,
            "zuschlag": round(rng.uniform(*ZUSCHLAG), 3),
            "materialindex": MATERIALINDEX[jahr],
            "leistungsfaktor": round(rng.uniform(*LEISTUNGSFAKTOR), 3)}


# --- Kalkulation ------------------------------------------------------------

def einzelkosten(code: str, p: dict) -> tuple[float, float, float]:
    """(Lohn, Material, Gerät) je Einheit, ohne Zuschlag."""
    row = LEISTUNG[code]
    lohn = row[4] * p["leistungsfaktor"] * p["mittellohn"]
    mat = sum(q * MATERIALIEN[m][2] for m, q in row[5]) * p["materialindex"]
    ger = sum(h * GERAETE[g][1] for g, h in row[6]) * p["leistungsfaktor"]
    return lohn, mat, ger


def kalkuliere(positionen: list[dict], p: dict, rng: random.Random) -> list[dict]:
    zeilen, summe_ek = [], 0.0
    for pos in positionen:
        if pos["leistung_code"] == "B01":
            continue
        lohn, mat, ger = einzelkosten(pos["leistung_code"], p)
        faktor = (1 + p["zuschlag"]) * math.exp(rng.gauss(0, STREUUNG))
        summe_ek += (lohn + mat + ger) * pos["menge"]
        zeilen.append((pos, lohn * faktor, mat * faktor, ger * faktor))
    be = next((x for x in positionen if x["leistung_code"] == "B01"), None)
    if be:
        kosten = summe_ek * BE_ANTEIL * (1 + p["zuschlag"]) * math.exp(rng.gauss(0, STREUUNG))
        zeilen.append((be, kosten * 0.5, 0.0, kosten * 0.5))
    return [angebotszeile(pos, lohn, mat, ger) for pos, lohn, mat, ger in zeilen]


def angebotszeile(pos: dict, lohn: float, mat: float, ger: float) -> dict:
    ep = round(lohn + mat + ger, 2)
    return {"position_id": pos["id"], "ep_eur": ep, "gp_eur": round(ep * pos["menge"], 2),
            "lohnanteil_eur": round(lohn, 2), "materialanteil_eur": round(mat, 2),
            "geraeteanteil_eur": round(ger, 2)}


# --- Testfälle --------------------------------------------------------------

def erwartung(projekt_id: int, pos: dict | None, kategorie: str, begruendung: str,
              angebot_id: int | None = None) -> dict:
    return {"projekt_id": projekt_id, "position_id": pos["id"] if pos else None,
            "angebot_id": angebot_id, "kategorie": kategorie, "begruendung": begruendung}


def lv_fehler(positionen: list[dict], projekt_id: int, rng: random.Random) -> list[dict]:
    """Fehler im LV des Auftraggebers: vage Texte, runde Mengen, falsche Einheiten."""
    out = []
    normale = [p for p in positionen if p["positionsart"] == "Normal" and p["einheit"] != "psch"]
    for pos in normale:
        if rng.random() < P_VAGE_JE_POSITION:
            satz = rng.choice(VAGE_FORMULIERUNGEN)
            pos["langtext"] += " " + satz
            out.append(erwartung(projekt_id, pos, "vage_leistungsbeschreibung",
                                 f"Langtext enthält: „{satz}“"))
    flaechig = [p for p in normale if p["einheit"] in ("m", "m2", "m3")]
    if flaechig and rng.random() < P_RUNDE_MENGE:
        pos = rng.choice(flaechig)
        pos["menge"] = 1000.0
        out.append(erwartung(projekt_id, pos, "mengenplausibilitaet",
                             "Auffällig runde Menge (1.000) — vermutlich geschätzt, nicht ermittelt."))
    rohre = [p for p in normale if p["leistung_code"].startswith("K") and p["einheit"] == "m"]
    if rohre and rng.random() < P_EINHEITENFEHLER:
        pos = rng.choice(rohre)
        pos["einheit"] = "m3"
        out.append(erwartung(projekt_id, pos, "einheitenfehler",
                             "Rohrverlegung in m³ ausgeschrieben, üblich ist m."))
    return out


def abrechnung(positionen: list[dict], projekt_id: int, rng: random.Random) -> list[dict]:
    """Nur bei beauftragten Projekten kennt das Unternehmen die Abrechnungsmenge."""
    for pos in positionen:
        pos["abrechnungsmenge"] = menge_runden(pos["menge"] * math.exp(rng.gauss(0, 0.06)),
                                               pos["einheit"])
    if rng.random() >= P_MENGENRISIKO:
        return []
    kandidaten = [p for p in positionen if p["positionsart"] == "Normal"
                  and p["einheit"] != "psch" and p["menge"] != 1000.0]
    pos = max(kandidaten, key=lambda p: p["menge"])
    pos["abrechnungsmenge"] = round(pos["menge"] * 1.6, 1)
    return [erwartung(projekt_id, pos, "mengenrisiko",
                      "Abrechnungsmenge liegt 60 % über der Ausschreibungsmenge.")]


def kommafehler(zeilen: list[dict], projekt_id: int, angebot_id: int,
                rng: random.Random) -> list[dict]:
    """Eigene Kalkulationsfehler: Einheitspreis um eine Kommastelle verrutscht."""
    out = []
    for z in zeilen:
        if rng.random() >= P_KOMMAFEHLER_JE_POSITION:
            continue
        faktor = rng.choice([10.0, 0.1])
        for key in ("ep_eur", "lohnanteil_eur", "materialanteil_eur", "geraeteanteil_eur"):
            z[key] = round(z[key] * faktor, 2)
        z["gp_eur"] = round(z["gp_eur"] * faktor, 2)
        richtung = "zehnfach zu hoch" if faktor > 1 else "ein Zehntel zu niedrig"
        out.append({"projekt_id": projekt_id, "position_id": z["position_id"],
                    "angebot_id": angebot_id, "kategorie": "kalkulationsfehler",
                    "begruendung": f"Einheitspreis {richtung} (Kommafehler)."})
    return out


# --- Aufbau -----------------------------------------------------------------

SCHEMA = """
CREATE TABLE arbeitszeitrichtwerte (leistung_code TEXT PRIMARY KEY, gewerk TEXT, taetigkeit TEXT,
  einheit TEXT, h_min REAL, h_mittel REAL, h_max REAL, bemerkung TEXT, herkunft TEXT);
CREATE TABLE geraete (code TEXT PRIMARY KEY, bezeichnung TEXT, kosten_eur_h REAL);
CREATE TABLE materialien (code TEXT PRIMARY KEY, bezeichnung TEXT, einheit TEXT,
  preis_eur REAL, preisstand TEXT);
CREATE TABLE leistung_material (leistung_code TEXT REFERENCES arbeitszeitrichtwerte,
  material_code TEXT REFERENCES materialien, menge_je_einheit REAL);
CREATE TABLE leistung_geraet (leistung_code TEXT REFERENCES arbeitszeitrichtwerte,
  geraet_code TEXT REFERENCES geraete, stunden_je_einheit REAL);
CREATE TABLE unternehmen (id INTEGER PRIMARY KEY, firma TEXT, sitz TEXT, profil TEXT);
CREATE TABLE projekte (id INTEGER PRIMARY KEY, bezeichnung TEXT, projekttyp TEXT, ort TEXT,
  auftraggeber TEXT, submission TEXT, trassenlaenge_m REAL, grabentiefe_m REAL,
  grabenbreite_m REAL, flaeche_m2 REAL);
CREATE TABLE lv_positionen (id INTEGER PRIMARY KEY, projekt_id INTEGER REFERENCES projekte,
  oz TEXT, titel TEXT, kurztext TEXT, langtext TEXT, einheit TEXT, menge REAL,
  positionsart TEXT, pauschal INTEGER, leistung_code TEXT REFERENCES arbeitszeitrichtwerte,
  abrechnungsmenge REAL);
CREATE TABLE vorbemerkungen (id INTEGER PRIMARY KEY, projekt_id INTEGER REFERENCES projekte,
  nr INTEGER, text TEXT, risiko INTEGER, begruendung TEXT);
CREATE TABLE angebote (id INTEGER PRIMARY KEY, projekt_id INTEGER REFERENCES projekte,
  unternehmen_id INTEGER REFERENCES unternehmen, angebotssumme_netto REAL,
  mittellohn_eur_h REAL, zuschlag_pct REAL, materialindex REAL, leistungsfaktor REAL, status TEXT);
CREATE TABLE angebotspositionen (angebot_id INTEGER REFERENCES angebote,
  position_id INTEGER REFERENCES lv_positionen, ep_eur REAL, gp_eur REAL,
  lohnanteil_eur REAL, materialanteil_eur REAL, geraeteanteil_eur REAL);
CREATE TABLE testfall_erwartungen (id INTEGER PRIMARY KEY, projekt_id INTEGER, position_id INTEGER,
  angebot_id INTEGER, kategorie TEXT, begruendung TEXT);
"""

TITEL = {"01": "Baustelle und Verkehrssicherung", "02": "Erdarbeiten und Verbau",
         "03": "Kanal und Schächte", "04": "Leitungen", "05": "Oberbau"}


def projekt_positionen(spec: dict, next_id: int) -> list[dict]:
    roh = (flaechen_positionen(spec["A"]) if spec["A"]
           else graben_positionen(spec["L"], spec["d"], spec["b"], spec["opt"]))
    positionen, zaehler = [], {}
    for titel, code, menge, art in sorted(roh, key=lambda r: r[0]):
        row = LEISTUNG[code]
        zaehler[titel] = zaehler.get(titel, 0) + 10
        positionen.append({
            "id": next_id + len(positionen), "projekt_id": spec["id"],
            "oz": f"{titel}.{zaehler[titel]:04d}", "titel": TITEL[titel], "kurztext": row[2],
            "langtext": row[7], "einheit": row[3], "menge": menge_runden(menge, row[3]),
            "positionsart": art, "pauschal": int(row[3] == "psch"), "leistung_code": code,
            "abrechnungsmenge": None,
        })
    return positionen


def insert(con: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0])
    con.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    [tuple(r[c] for c in cols) for r in rows])


def stammdaten(con: sqlite3.Connection) -> None:
    insert(con, "arbeitszeitrichtwerte", [{
        "leistung_code": c, "gewerk": g, "taetigkeit": k, "einheit": e,
        "h_min": round(h * (1 - SPREIZUNG), 3), "h_mittel": h, "h_max": round(h * (1 + SPREIZUNG), 3),
        "bemerkung": lt, "herkunft": HERKUNFT} for c, g, k, e, h, _m, _g, lt in LEISTUNGEN])
    insert(con, "geraete", [{"code": c, "bezeichnung": n, "kosten_eur_h": k}
                            for c, (n, k) in GERAETE.items()])
    insert(con, "materialien", [{"code": c, "bezeichnung": n, "einheit": e, "preis_eur": p,
                                 "preisstand": "2025, synthetisch"} for c, (n, e, p) in MATERIALIEN.items()])
    insert(con, "leistung_material", [{"leistung_code": row[0], "material_code": m, "menge_je_einheit": q}
                                      for row in LEISTUNGEN for m, q in row[5]])
    insert(con, "leistung_geraet", [{"leistung_code": row[0], "geraet_code": g, "stunden_je_einheit": h}
                                    for row in LEISTUNGEN for g, h in row[6]])
    insert(con, "unternehmen", [UNTERNEHMEN])


def projekt_anlegen(con, rng, spec: dict, ids: dict) -> None:
    insert(con, "projekte", [{
        "id": spec["id"], "bezeichnung": spec["bezeichnung"], "projekttyp": spec["typ"],
        "ort": spec["ort"], "auftraggeber": spec["auftraggeber"], "submission": spec["submission"],
        "trassenlaenge_m": spec["L"] or None, "grabentiefe_m": spec["d"] or None,
        "grabenbreite_m": spec["b"] or None, "flaeche_m2": spec["A"]}])
    positionen = projekt_positionen(spec, ids["position"])
    ids["position"] += len(positionen)
    erwartungen = lv_fehler(positionen, spec["id"], rng)
    beauftragt = rng.random() < ZUSCHLAGSQUOTE
    if beauftragt:
        erwartungen += abrechnung(positionen, spec["id"], rng)
    insert(con, "lv_positionen", positionen)
    insert(con, "vorbemerkungen", [
        {"projekt_id": spec["id"], "nr": n, "text": t, "risiko": r, "begruendung": g}
        for n, (t, r, g) in enumerate(rng.sample(VORBEMERKUNGEN, k=5), start=1)])

    p = kalkulationsparameter(rng, spec["jahr"])
    angebot_id = ids["angebot"]
    ids["angebot"] += 1
    zeilen = kalkuliere(positionen, p, rng)
    erwartungen += kommafehler(zeilen, spec["id"], angebot_id, rng)
    for z in zeilen:
        z["angebot_id"] = angebot_id
    insert(con, "angebotspositionen", zeilen)
    insert(con, "angebote", [{
        "id": angebot_id, "projekt_id": spec["id"], "unternehmen_id": UNTERNEHMEN["id"],
        "angebotssumme_netto": round(sum(z["gp_eur"] for z in zeilen), 2),
        "mittellohn_eur_h": p["mittellohn"], "zuschlag_pct": round(p["zuschlag"] * 100, 1),
        "materialindex": p["materialindex"], "leistungsfaktor": p["leistungsfaktor"],
        "status": "beauftragt" if beauftragt else "nicht beauftragt"}])
    insert(con, "testfall_erwartungen", erwartungen)


def export_csv(con: sqlite3.Connection, csv_dir: str) -> None:
    os.makedirs(csv_dir, exist_ok=True)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for table in tables:
        cur = con.execute(f"SELECT * FROM {table}")
        with open(os.path.join(csv_dir, f"{table}.csv"), "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh, delimiter=";")
            writer.writerow([c[0] for c in cur.description])
            writer.writerows(cur.fetchall())


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)


def export_runtime_json(data_dir: str) -> None:
    """Die Nachschlage-Tabellen, die eine Engine zur Laufzeit braucht — ohne SQL."""
    meta = {"herkunft": HERKUNFT, "seed": SEED,
            "hinweis": "Synthetisch. Keine ARH-Originalwerte, keine Marktpreisabfrage."}
    write_json(os.path.join(data_dir, "arbeitszeitrichtwerte.json"), {"meta": meta, "leistungen": {
        c: {"gewerk": g, "taetigkeit": k, "einheit": e,
            "h_min": round(h * (1 - SPREIZUNG), 3), "h_mittel": h, "h_max": round(h * (1 + SPREIZUNG), 3),
            "material": [{"code": m, "menge_je_einheit": q} for m, q in mats],
            "geraet": [{"code": gc, "stunden_je_einheit": gh} for gc, gh in gers],
            "bemerkung": lt}
        for c, g, k, e, h, mats, gers, lt in LEISTUNGEN}})
    write_json(os.path.join(data_dir, "materialien.json"), {"meta": meta, "materialien": {
        c: {"bezeichnung": n, "einheit": e, "preis_eur": p} for c, (n, e, p) in MATERIALIEN.items()}})
    write_json(os.path.join(data_dir, "geraete.json"), {"meta": meta, "geraete": {
        c: {"bezeichnung": n, "kosten_eur_h": k} for c, (n, k) in GERAETE.items()}})


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetische Testdaten erzeugen.")
    parser.add_argument("--root", default=REPO_ROOT, help="Repo-Root (Standard: über scripts/)")
    parser.add_argument("--csv", action="store_true", help="zusätzlich CSV je Tabelle")
    args = parser.parse_args()

    db_path = os.path.join(args.root, DB_REL)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    rng = random.Random(SEED)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    stammdaten(con)
    ids = {"position": 1, "angebot": 1}
    for projekt_id in range(1, ANZAHL_PROJEKTE + 1):
        projekt_anlegen(con, rng, projekt_spec(rng, projekt_id), ids)
    con.commit()
    export_runtime_json(os.path.join(args.root, "data"))
    if args.csv:
        export_csv(con, os.path.join(args.root, CSV_REL))
    for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        print(f"{table:<24} {con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:>6} Zeilen")
    con.close()


if __name__ == "__main__":
    main()
