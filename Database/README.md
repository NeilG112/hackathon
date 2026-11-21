# Setup-Paket: synthetische Testdaten

Ordnerstruktur wie im Repo. Zum Einbauen den Inhalt in den Repo-Root kopieren:

```
scripts/generate_testdata.py          Generator (nur Standardbibliothek, fester Seed 2026)
data/testdb/testdatenbank.sqlite      alle 12 Tabellen — für Tests und Auswertung (sqlite3)
data/arbeitszeitrichtwerte.json       34 Leistungen: h_min/h_mittel/h_max, Material, Gerät — Laufzeit
data/materialien.json                 21 Materialpreise — Laufzeit
data/geraete.json                     10 Gerätekosten je h — Laufzeit
```

Neu erzeugen (aus dem Repo-Root): `python3 scripts/generate_testdata.py` — gleicher Seed,
gleiche Daten. `--csv` legt zusätzlich CSV-Dateien zum Anschauen unter `data/testdb/csv/` ab.

**Format-Entscheidung:** SQLite für Tests, weil Projekte, Positionen, Angebote und
Soll-Ergebnisse verknüpft abgefragt werden. JSON für die Laufzeit, weil eine Engine dort nur
nachschlägt (Leistung → Stunden, Material → Preis) und JSON-Änderungen in Git lesbar sind.
Beides ohne zusätzliche Abhängigkeit.

**Synthetisch:** nichts aus den LVs übernommen. Arbeitszeitrichtwerte sind eigene Schätzungen in
ARH-Größenordnung, keine Originalwerte. Preise plausibel Stand 2026, keine Marktabfrage. Prüft
die Logik der Engines, nicht die Marktgenauigkeit.
