# Was noch zu tun ist

Architektur und Messwerte stehen in [README.md](README.md). Hier steht nur die offene
Arbeit. Alles mit einer Zahl dahinter ist gemessen, nicht geschätzt.

```bash
python3 validate_gate.py     # muss grün sein, vor jedem Push
streamlit run app.py         # der Demo-Pfad
```

## Fertig

| | Stand |
|---|---|
| Parser, 4 GAEB-Formate | Gate grün, zwei Formate byte-identisch |
| Klassifizierung (Jev) | 90 % auf dem echten LV, 94 % gegen 2.496 Labels |
| Kalkulation (Aufschlag) | 84,7 % Abdeckung, 5,3 % Medianfehler gegen 2.459 Preise |
| Objekttabelle + Mengengerüst | 248 Positionen → (Abschnitt, Objekt, Einheit) |
| Risiko-Detektoren | 59 Befunde |
| Vergleichspreis-Quercheck | läuft, ehrlich als −50 % gekennzeichnet |
| Bieterfragen-Katalog (.docx) | fertig |

---

## Offen

### 1 · GAEB-X84-Export — das fehlende Produktversprechen

Der Kunde sagte wörtlich: *„Dieses LV wollen wir hochladen und am Ende das Angebot
rausbekommen."* Wir geben den Brief zurück, aber keine Angebotsdatei.

Der Code existiert im Repo deines Kollegen (236 Zeilen `exporter.py`, GAEB X84 + Excel).
`codebase_bundle.md` wurde gelöscht, ist aber über die Git-History erreichbar:

```bash
git show 3f63002:codebase_bundle.md | less   # Abschnitt "## `exporter.py`"
```

**Wichtig beim Portieren:** Sein Parser verliert die echte OZ und ersetzt sie durch einen
laufenden Zähler (1, 2, 3 …). Für einen X84-Export ist das fatal — der Auftraggeber
joint auf der OZ. Unsere Parser machen das korrekt; nimm `NormalizedItem.key()`.

### 2 · „Heikle Positionen" zeigt 176 von 248

Unbrauchbar. Die Schwelle (Spanne > 35 %) stammt aus der Zeit mit 34 Leistungen; mit 124
Einträgen und breiteren min/max-Werten feuert sie fast überall. Ziel sind 20–30 Positionen,
die wirklich jemand ansehen muss. Reine Schwellenarbeit in `app.py`, keine neue Logik.

### 3 · Die restlichen 15 % Abdeckung

26 Positionen ohne Zuordnung, 12 mit Einheiten-Konflikt. Die häufigsten:

```
4x  S10 gibt es in 'm'    — gebraucht wird 'St'
2x  B04-ST gibt es in 'St' — gebraucht wird 'psch'
```

Einzelne Katalogzeilen, ein Nachmittag für ~95 %.

### 4 · Logik-Engine braucht einen Bauingenieur

Läuft, findet auf diesem LV nichts Belastbares. Von den vier Regeln in `core/logic.py`
sind zwei physikalisch zwingend (man kann nicht mehr verfüllen als man ausgehoben hat),
der Rest ist meine Vermutung. Die „needs"-Regeln sind bewusst abgeschaltet — sie
produzierten 19 Befunde, von denen keiner haltbar war.

### 5 · Niemand hat von Hand einen echten Widerspruch gesucht

Eine Stunde, ein Mensch, das LV lesen. Das Ergebnis ist Testmenge, Präzisionsnenner und
Demo-Skript in einem. Ohne das ist die Logik-Engine unbewiesen.

### 6 · Die Orga-Fragen sind weiter offen

Was wird bewertet? Wie lang ist der Demo-Slot? Zehn Minuten mit einem Organisator.

---

## Hausregeln

- `Dataset/` ist **read-only**.
- `core/` und `utils/` sind **nur Standardbibliothek** — damit `validate_gate.py` überall läuft.
- **Vor jedem Push `python3 validate_gate.py`.** Rot heißt: stromaufwärts ist etwas
  kaputt, flussabwärts ist nichts mehr vertrauenswürdig. Niemals die Assertion aufweichen.
- **Katalog geändert → `data/classification_cache.json` löschen.** Der Cache kennt nur den
  Positionstext, nicht die Katalogversion. Hat uns schon einmal eine Erweiterung
  verschluckt, die aussah, als hätte sie nichts gebracht.
- **Kein Live-API-Call im Demo-Pfad.** Vorab berechnen, cachen, die JSON mitliefern.

## Fünf Fakten, die Zeit gekostet haben

1. **Auf `padded_key((2,2,4))` joinen, nie auf `key()` oder den Listenindex.** Das leere LV
   speichert Hierarchie-Ebenen ungepolstert (`1,1,1`), die bepreisten Dateien gepolstert
   (`01,01,0001`) — ein naiver Join trifft **null** von 248 Positionen.
2. **Nie einen XML-Namespace hartkodieren.** Zwei Namespaces im Datensatz; auf
   `local-name()` matchen. Ein falsch gekeytes XPath liefert **lautlos** null Knoten.
3. **Einheiten prüfen, bevor multipliziert wird.** Ein Aufwandswert ist „Stunden je Einheit
   *der Leistung*". Ohne die Prüfung kam ein Angebot von 2,9 Mio € statt ~900 Tsd € heraus.
4. **Nie gegen ein Angebot messen, das im Benchmark steckt.** Hat uns einmal eine
   Genauigkeit von „+6,3 %" vorgegaukelt; ehrlich waren es −50 %.
5. **Einheiten-Strings sind kaputt.** 50 von 720 Positionen kommen als `m▓`/`m│` an —
   cp850 für Buchstaben, latin-1 für Hochzahlen. Immer `constants.normalize_unit()`.
