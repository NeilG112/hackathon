# Setup-Paket: synthetische Testdaten — Angebotshistorie eines Unternehmens

Ordnerstruktur wie im Repo. Zum Einbauen den Inhalt in den Repo-Root kopieren:

```
scripts/generate_testdata.py          Generator (nur Standardbibliothek, fester Seed 2026)
data/testdb/testdatenbank.sqlite      alle Tabellen — für Tests und Auswertung (sqlite3)
data/arbeitszeitrichtwerte.json       34 Leistungen: h_min/h_mittel/h_max, Material, Gerät — Laufzeit
data/materialien.json                 21 Materialpreise — Laufzeit
data/geraete.json                     10 Gerätekosten je h — Laufzeit
```

Neu erzeugen (aus dem Repo-Root): `python3 scripts/generate_testdata.py` — gleicher Seed,
gleiche Daten. `--csv` legt zusätzlich CSV-Dateien unter `data/testdb/csv/` ab.

## Inhalt

Ein fiktives Unternehmen (Musterbau Tiefbau GmbH), 140 Ausschreibungen 2022–2026, je ein
eigenes Angebot — **2.496 kalkulierte Positionen**.

| Tabelle | Zeilen | Inhalt |
|---|---|---|
| `unternehmen` | 1 | das Unternehmen |
| `projekte` | 140 | 6 Projekttypen, Geometrie (Länge, Tiefe, Breite bzw. Fläche), Ort, AG, Datum |
| `lv_positionen` | 2.496 | OZ, Kurz-/Langtext, Menge, Einheit, Positionsart; Abrechnungsmenge nur bei beauftragten Projekten |
| `angebote` | 140 | Summe, Mittellohn, Zuschlag, Materialindex, Leistungsfaktor, Status |
| `angebotspositionen` | 2.496 | EP, GP, aufgeteilt in Lohn / Material / Gerät |
| `vorbemerkungen` | 700 | Vertragstexte, riskante markiert (`risiko = 1`) mit Begründung |
| `testfall_erwartungen` | 193 | Soll-Ergebnis: was eine Engine finden müsste, und warum |
| `arbeitszeitrichtwerte`, `materialien`, `geraete`, `leistung_material`, `leistung_geraet` | 34 / 21 / 10 / 31 / 35 | Stammdaten der Kalkulation |

Parameter über die Zeit: Mittellohn 52,0 €/h (2022) → 59,5 €/h (2026), +3,5 %/Jahr;
Zuschlag 18–27 % je Projekt; Materialindex 0,94 → 1,02; Leistungsfaktor 0,92–1,12 (Erschwernis).

## Eingebaute Testfälle (7,7 % der Positionen)

| Kategorie | Anzahl | Engine | Was |
|---|---|---|---|
| `vage_leistungsbeschreibung` | 85 | Risk | „nach Wahl des AG“, „ggf.“, „oder gleichwertig“ … |
| `einheitenfehler` | 37 | Fehlerkorrektur | Rohrverlegung in m³ statt m |
| `mengenplausibilitaet` | 36 | Fehlerkorrektur | auffällig runde Menge 1.000 |
| `kalkulationsfehler` | 22 | Fehlerkorrektur | eigener EP um eine Kommastelle verrutscht (×10 / ×0,1) |
| `mengenrisiko` | 13 | Risk | Abrechnungsmenge +60 % über Ausschreibung |

## Was diese Daten NICHT sind

- **Keine ARH-Originalwerte.** Stunden je Einheit sind eigene Schätzungen in der
  Größenordnung üblicher Arbeitszeit-Richtwerte — vor Verwendung als Referenz prüfen.
- Material- und Gerätepreise plausibel, keine Marktabfrage. Zuschlagsquote 30 % ist eine Annahme.
- Unternehmen, Orte, Auftraggeber sind erfunden.
- Prüft die Logik der Engines, nicht die Marktgenauigkeit.
