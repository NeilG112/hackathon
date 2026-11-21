"""Marktpreise 2025 je Katalogleistung — recherchiert, mit Quelle und Vertrauensstufe.

Alle Preise netto, Einheitspreis inkl. Lohn, Gerät, Material und Zuschlägen
(so wie sie in Leistungsverzeichnissen stehen). Nur Quellen mit Stand 2025.

Vertrauen:
  A  direkt aus Kostenberechnung Biblis, 04.06.2025 (Planerschätzung, kein Angebot)
  B  aus A abgeleitet (Summe zweier Positionen oder Umrechnung über eine im
     Katalog genannte Schichtdicke) — Rechenweg in `herleitung`
  C  Spannen aus Ratgeber-/Forenquellen 2025 — nur grob

Quelle A: https://rim.ekom21.de/biblis/sdnetrim/UGhVM0hpd2NXNFdFcExjZQba-SMTEnOwrwjEtjDi1S-Nc_rmeRcMj4XcKvvKxdX_/Kostenberechnung.pdf
Lohn 2025: https://www.bauprofessor.de/ecklohn-im-baugewerbe/ (TL LG4 West ab 01.04.2025: 23,68 €/h)
"""

BIBLIS = "Kostenberechnung Biblis 04.06.2025"

# code: (einheit, min, mittel, max, vertrauen, quelle/herleitung)
MARKT_2025 = {
    # --- Erdbau ---
    "E02": ("m3", 54.0, 69.0, 74.0, "B", f"{BIBLIS}: Leitungsgraben ausheben, laden 30–35 €/m³ (6.2.11, 5.2.11) "
            "+ Boden entsorgen BM-0 34 €/m³ (3.12)"),
    "E11": ("m3", 35.0, 40.0, 45.0, "B", f"{BIBLIS}: ausheben, laden 30–35 €/m³ + Zulage Zwischenlagerung 5 €/m³ (3.10)"),
    "E03": ("m3", 60.0, 75.0, 109.0, "A", f"{BIBLIS}: Handaushub an Bebauung 75 €/m³ (5.2.13); Zulage Handaushub 60 €/m³ (4.1.16)"),
    "E04": ("m3", 45.0, 55.0, 64.0, "A", f"{BIBLIS}: Bodenaustausch Schotter 58, Kiessand 64, gelagert 45; Verfüllung Vorsiebmaterial 48 €/m³"),
    "E05": ("m3", 64.0, 67.0, 70.0, "A", f"{BIBLIS}: Leitungszone/Rohrauflager 64 €/m³ (4.1.26), Sand 70 €/m³ (6.2.18)"),
    "E09": ("m3", 35.0, 40.0, 45.0, "A", f"{BIBLIS}: Hauptverfüllung mit Aushubmaterial 35 €/m³ (5.2.20); mit gelagertem Material 45 €/m³ (4.1.28)"),
    "E10": ("m3", 60.0, 70.0, 100.0, "B", f"{BIBLIS}: ausheben 35 + Hauptverfüllung Aushub 35 €/m³; Suchgraben ausheben+verfüllen 100 €/m³ (1.23)"),
    "E01-M3": ("m3", 14.0, 16.0, 18.0, "A", f"{BIBLIS}: Oberboden abtragen, fördern, lagern 16 €/m³ (4.1.11)"),
    "E01": ("m2", 2.8, 3.2, 3.6, "B", "E01-M3 × 0,20 m (Abtragsdicke laut Katalogtext E01)"),
    "E08": ("m3", 14.0, 16.0, 32.0, "A", f"{BIBLIS}: Oberboden gelagert andecken 16 €/m³; geliefert 32 €/m³ (4.1.12/13)"),
    "E06": ("m2", 1.8, 2.0, 2.2, "A", f"{BIBLIS}: Planum herstellen, Ev2 45 MN/m² 2 €/m² (4.1.32)"),
    "E07-M3": ("m3", 52.0, 58.0, 64.0, "A", f"{BIBLIS}: Schottertragschicht herstellen 58 €/m³ (4.3.10–12)"),
    "E07": ("m2", 15.6, 17.4, 19.2, "B", "E07-M3 × 0,30 m (Schichtdicke laut Katalogtext E07)"),
    "T07": ("m3", 52.0, 58.0, 64.0, "A", f"{BIBLIS}: Schottertragschicht herstellen 58 €/m³"),
    "E12": ("m3", 95.0, 130.0, 180.0, "C", "Tiefbau-Anbieter Wien, schwierige Böden 95–180 €/m³ (Datum unklar)"),
    # --- Straße ---
    "T01": ("m", 6.0, 7.0, 8.0, "A", f"{BIBLIS}: Asphaltbefestigung trennen 5–15 cm 7 €/m (4.4.10)"),
    "T02": ("m2", 15.0, 20.0, 30.0, "C", f"{BIBLIS}: aufreißen/fräsen Kleinflächen 30 €/m² (4.4.11) — für Großflächen niedriger angesetzt"),
    "T03": ("m2", 25.0, 27.5, 30.0, "B", f"{BIBLIS}: Asphalttragschicht AC 32 TN 12 cm 30 €/m² (4.4.13) → 10 cm"),
    "T04": ("m2", 20.0, 22.0, 24.0, "A", f"{BIBLIS}: Asphaltdeckschicht AC 8 DN 20 €/m² + Emulsion 2 €/m² (4.4.17/18)"),
    "T05": ("m2", 70.0, 78.0, 86.0, "A", f"{BIBLIS}: Betonpflaster liefern und verlegen 8 cm 78 €/m² (4.5.21)"),
    "T11": ("m2", 35.0, 35.0, 45.0, "A", f"{BIBLIS}: Pflaster gelagert verlegen 35 €/m² (4.5.25/27), Naturstein 45 €/m²"),
    "T09": ("m2", 25.0, 25.0, 30.0, "A", f"{BIBLIS}: Pflaster ausbauen, säubern, seitlich lagern 25 €/m² (4.5.24/26)"),
    "T06": ("m", 38.0, 50.0, 60.0, "B", f"{BIBLIS}: Tiefbord 8/25 38 €/m, 10/30 40 €/m, Rundbord 15/22 60 €/m — Hochbord 15/30 dazwischen"),
    "T10": ("m", 20.0, 20.0, 30.0, "A", f"{BIBLIS}: Bordsteine aufnehmen und entsorgen 20 €/m (4.5.10)"),
    # --- Kanal / Wasser / Kabel ---
    "K01": ("m", 35.0, 40.0, 45.0, "A", f"{BIBLIS}: PVC-U-Rohre DN/OD 160 40 €/m (4.2.10, 5.3.10)"),
    "K05": ("m", 10.0, 15.0, 31.0, "C", f"{BIBLIS}: PE DA 40 10 €/m (6.3.11); Tarif Freiberg 2025 Hausanschluss bis DN 50 30,91 €/m"),
    "K07": ("m", 6.5, 15.0, 15.0, "A", f"{BIBLIS}: Kabelschutzrohr DN 110 15 €/m (6.3.13), DA 63 6,50 €/m"),
    "K08": ("m", 1.0, 1.0, 1.2, "A", f"{BIBLIS}: Trassenwarnband 1 €/m (6.3.16, 4.6.13)"),
    "K09": ("St", 150.0, 150.0, 200.0, "A", f"{BIBLIS}: Dichtheitsprüfung Revisionsschächte 150 €/St (5.5.22)"),
    "K09-M": ("m", 2.0, 3.0, 4.0, "A", f"{BIBLIS}: Muffendruckprüfung 2–4 €/m (5.5.20/21)"),
    "K10": ("m", 4.0, 9.0, 9.0, "A", f"{BIBLIS}: TV-Untersuchung 4–9 €/m (5.5.15/16)"),
    "S01": ("St", 2000.0, 2750.0, 3000.0, "A", f"{BIBLIS}: Schacht DN 1000 2.750 €/St (5.4.14), DN 800 2.000 €/St"),
    "S03": ("St", 400.0, 550.0, 550.0, "A", f"{BIBLIS}: Schachtabdeckung Kl. D 400 550 €/St (5.4.19)"),
    "F01": ("St", 25.0, 25.0, 40.0, "A", f"{BIBLIS}: Formstücke DA 40 25 €/St (6.3.12); PVC-Bögen DN 160 40 €/St"),
    "F03": ("St", 25.0, 25.0, 40.0, "A", f"{BIBLIS}: Formstücke/Klemmfittings DA 40 25 €/St (6.3.12)"),
    "F04": ("St", 25.0, 25.0, 30.0, "A", f"{BIBLIS}: Endkappen 25 €/St (6.3.14)"),
    "F19": ("St", 250.0, 250.0, 300.0, "A", f"{BIBLIS}: Anschluss an bestehende Leitung 250 €/St (6.3.15)"),
    "F23": ("St", 250.0, 250.0, 300.0, "A", f"{BIBLIS}: Einbindung herstellen inkl. Material 250 €/St (6.3.10)"),
    "F28": ("St", 200.0, 200.0, 250.0, "A", f"{BIBLIS}: Schieber/Kappen auf Höhe setzen 200 €/St (5.2.21)"),
    "P05": ("m", 2.0, 3.0, 3.5, "A", f"{BIBLIS}: Desinfektion Wasserleitung 3 €/m (6.3.17)"),
    # --- Baustelle / Ausstattung / Prüfung / Grün ---
    "B04": ("psch", 750.0, 1100.0, 1500.0, "A", f"{BIBLIS}: Bestandsaufnahme 750 €, Zustandserfassung+Doku 1.500 € psch (1.12, 1.17–1.19)"),
    "P01": ("St", 150.0, 180.0, 200.0, "A", f"{BIBLIS}: Lastplattendruckversuch 180 €/St (1.13)"),
    "P02": ("St", 600.0, 600.0, 600.0, "A", f"{BIBLIS}: Beprobung Boden/Aufbruch bzw. Asphalt 600 €/St (3.11, 3.15)"),
    "A01-H": ("m", 8.0, 12.0, 12.0, "A", f"{BIBLIS}: Bauzaun aufstellen und entfernen 2,0 m 12 €/m (1.14)"),
    "A06-H": ("St", 40.0, 40.0, 100.0, "A", f"{BIBLIS}: Verkehrszeichen aufstellen 40 €/St (2.11), Größe 2 100 €/St"),
    "A07-H": ("St", 40.0, 40.0, 40.0, "A", f"{BIBLIS}: Absperr-/Warneinrichtung aufstellen 40 €/St (2.12)"),
    "A04-H": ("St", 150.0, 150.0, 300.0, "A", f"{BIBLIS}: Notbrücke PKW/LKW herstellen 150 €/St (2.13)"),
    "L01": ("m2", 2.0, 2.0, 2.5, "A", f"{BIBLIS}: Oberboden ansäen RSM Regio 2 €/m² (4.1.14)"),
}

MITTELLOHN_2025 = {
    "tariflohn_lg4_west_ab_2025_04": 23.68,
    "gesamttariflohn_inkl_bauzuschlag_5_9pct": 25.08,
    "quelle": "https://www.bauprofessor.de/ecklohn-im-baugewerbe/",
}
