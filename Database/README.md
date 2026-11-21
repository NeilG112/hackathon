# Setup-Paket: synthetische Testdaten — Angebotshistorie eines Unternehmens

Ordnerstruktur wie im Repo. Zum Einbauen den Inhalt in den Repo-Root kopieren:

```
scripts/generate_testdata.py          Generator (nur Standardbibliothek, fester Seed 2026)
data/testdb/testdatenbank.sqlite      alle Tabellen — für Tests und Auswertung (sqlite3)
data/arbeitszeitrichtwerte.json       134 Leistungen: h_min/h_mittel/h_max, Material, Gerät — Laufzeit
data/materialien.json                 Materialpreise — Laufzeit
data/geraete.json                     Gerätekosten je h — Laufzeit
scripts/katalog_erweiterung.py        Einheiten-Varianten und Zusatzleistungen (siehe unten)
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

## Leistungskatalog (Laufzeit)

`arbeitszeitrichtwerte.json` = 34 Basisleistungen + 100 Zeilen aus
`scripts/katalog_erweiterung.py` (Stand 2026-11-21, zweiter Durchgang). Die
Testdatenbank-Projekte nutzen **alle 134** Leistungen (siehe unten).

Zusätzliche Felder je Leistung:

| Feld | Bedeutung |
|---|---|
| `stichworte` | LV-Vokabular für den Keyword-Klassifikator; `-wort` schließt die Leistung aus, wenn die Position das Wort enthält |
| `basis` | Einheiten-Variante einer anderen Leistung (z. B. `B04-ST` → `B04`). Die Klassifizierung lenkt eine Zuordnung in falscher Einheit auf die passende Variante um — **ohne Umrechnungsfaktor** |
| `status` | `abgeleitet` (aus einer Basisleistung gerechnet), `geschaetzt` (eigene Schätzung), `unsicher` (große reale Streuung) |
| `annahme` | wovon der Arbeitszeitwert abgeleitet ist |

Lebenszyklus der Baustellenausstattung: `-H` herstellen/aufstellen (`m`/`St`),
`-V` vorhalten (`mWo`/`StWo`, Bauzaun zusätzlich `md`), `-U` umsetzen. Zeitbezogene
Einheiten tragen kaum Lohn; der Preis kommt aus Miete bzw. Gerät je Zeiteinheit.

**Nach jeder Katalogänderung** `python3 Database/scripts/generate_testdata.py` ausführen.
Der Klassifizierungs-Cache (`data/classification_cache.json`) ist nach Katalogversion
geschlüsselt; alte Einträge werden danach nicht mehr verwendet (bleiben aber in der
Datei). Mit Jev-Schlüssel neu klassifizieren: `classify.classify(items, data, use_jev=True)`.

## Schema-Änderungen

| Datum | Änderung | Code angepasst |
|---|---|---|
| 2026-11-21 | Tabelle `bieter` entfällt. `mittellohn_eur_h`, `zuschlag_pct`, `leistungsfaktor` liegen auf `angebote`; `materialfaktor` heißt dort `materialindex`. | `stammdaten.Company.materialfaktor` → `materialindex`; `companies()` liest nur noch `angebote`, kein `bieter`-Fallback, keine stillen Defaults (NULL-Parameter → `SchemaError`; fehlende DB → Profil mit `is_fallback=True`, das die App anzeigt) |
| 2026-11-21 | `arbeitszeitrichtwerte` (SQLite): neue Spalten `basis`, `status`, `annahme`; 124 statt 34 Zeilen | Generator |

## Testdatenbank, Stand zweiter Durchgang (2026-11-21)

60 Projekte, 7 Projekttypen gleichmäßig verteilt (neu: Fernwärme-/Kältetrasse im
Kunststoffmantelrohr), **3.124 Positionen**, alle 134 Katalogleistungen kommen vor:
Lebenszyklus herstellen/vorhalten/umsetzen für 8 Ausstattungen (`m`/`St` + `mWo`/`StWo`/`md`),
alle Einheiten-Varianten aus `LUECKEN.md`, PE- und Mantelrohr-Formteile, Armaturen,
Baustrom/-wasser, Landschaftsbau, Prüfungen, Bestandsschutz, Wasserhaltung.
182 eingebaute Testfälle (5,8 % der Positionen). Zusatzleistungen je Projekt kommen aus
einem eigenen Zufallsstrom (`SEED * 1000 + projekt_id`), reproduzierbar.

Bekannte Eigenheit: ~41 % der Testpositionen sind Baustellen-Positionen (echtes LV ~15 %),
weil die synthetischen Projekte kleiner sind (Ø 52 statt 248 Positionen), die
Lebenszyklus-Positionen je Projekt aber ähnlich häufig anfallen.

**Bekannte Schwäche der Arbeitszeitwerte (gemessen, nicht korrigiert):** Gegen das reale
Angebot für `[NUMMER_001]_leer.X83` liegt die Kalkulation auf den gleich bepreisten
Positionen bei −45 %. Haupttreiber: Erdaushub mit Leitungsbehinderung (eine Position
−153 Tsd. €), Leitungsbehelfsbrücke (−76 Tsd. €), Container. Umgekehrt ist die
Verbau-Vorhaltung je m²·d deutlich zu hoch. Die Werte wurden bewusst **nicht** an das
Referenzangebot angepasst (zirkulär); sie brauchen echte Aufwandswerte (ARH bzw. eigene
Nachkalkulation).

## Marktkalibrierung 2025 (Stand 2026-11-21)

Die Arbeitszeitwerte sind auf **Marktpreise 2025 aus Internetquellen** kalibriert —
ausdrücklich **ohne** die echten Angebote im `Dataset/` (StBALV23040, AN24-0305, LV24069).
Quellen und Preise: `scripts/marktpreise_2025.py` (48 Leistungen; Hauptquelle
Kostenberechnung Biblis vom 04.06.2025, Planerschätzung; Tariflohn Bau West ab 04/2025).

| Gruppe | Anzahl | Verfahren |
|---|---|---|
| mit Marktpreis 2025 | 48 | Lohn- und Gerätestunden so angepasst, dass der EP beim Referenzprofil 2025 (57,50 €/h, 22,5 % Zuschlag, Materialindex 1,00) dem Markt-Mittel entspricht; Spreizung aus Markt-min/max. Materialmengen bleiben, außer das Material allein läge über dem Marktpreis |
| übrige, Gewerk hat Marktwerte | 69 | mit dem Median-Faktor Markt/Modell ihres Gewerks skaliert |
| übrige, Gewerk ohne Marktwerte | 16 | mit dem Median über alle kalibrierten Leistungen skaliert |
| B01 (0 h, Anteil an Einzelkosten) | 1 | unverändert |

Jede Zeile nennt in `annahme`, wie sie kalibriert wurde. Wirkung: Stunden im Median ×1,18;
Testdatenbank-Summe +11,7 %. Grenzen: Biblis ist eine Planerschätzung für ein kleines
innerstädtisches Projekt; `A04-H` (Notbrücke 150 €) ist fachlich nur grob vergleichbar.
Die Kalibrierung ändert keine Klassifizierung — der Cache bleibt gültig.
