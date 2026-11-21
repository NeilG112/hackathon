# Was der Datenbank noch fehlt, um auf 100 % zu kommen

Stand: gemessen gegen das echte Ausschreibungs-LV `Dataset/[NUMMER_001]_leer.X83`
(248 Positionen) mit dem aktuellen Katalog (34 Leistungen).

```
248 Positionen
 93  kalkuliert          37,5 %   ← Status heute
 61  Einheiten-Konflikt  24,6 %   ← Leistung da, falsche Abrechnungseinheit
 94  ohne Zuordnung      37,9 %   ← Leistung fehlt im Katalog
```

**Der Engpass ist nicht mehr die Klassifizierung.** Jev ordnet 64 % der Positionen
korrekt zu, der Klassifikator liegt bei 94 % Trefferquote gegen die 2 496
gelabelten Positionen. Was fehlt, sind Einträge im Katalog, gegen die er zuordnen
kann. Jede Zeile, die unten dazukommt, erhöht die Abdeckung unmittelbar.

---

## Die zwei Ursachen

### Ursache A — Einheiten-Konflikt (61 Positionen, der schnellere Gewinn)

Die Leistung steht im Katalog, aber nur in **einer** Abrechnungseinheit. Das LV
rechnet dieselbe Arbeit anders ab. Ein Aufwandswert ist „Stunden **je Einheit der
Leistung**" — Menge × Stunden ist nur gültig, wenn beide Seiten dasselbe messen,
sonst entstehen Fantasiepreise. (Ohne diese Prüfung lag das Angebot bei 2,9 Mio €
statt rund 900 Tsd €, weil Positionen in mWo mit m²-Lohnsätzen multipliziert wurden.)

| Anz. | Leistung | vorhanden in | gebraucht wird |
|---:|---|---|---|
| 16 | B04 Bestandsdokumentation und Aufmaß | `psch` | `St` |
| 6 | B02 Verkehrssicherung vorhalten | `Wo` | `StWo` |
| 5 | B02 Verkehrssicherung vorhalten | `Wo` | `St` |
| 4 | E03 Boden von Hand lösen | `m³` | `St` |
| 4 | K05 PE-HD-Rohr da 110 verlegen | `m` | `St` |
| 3 | K09 Dichtheitsprüfung je Haltung | `St` | `m` |
| 2 | E01 Oberboden abtragen | `m²` | `m³` |
| 2 | V02 Zulage Grabenverbau Tiefe > 3,0 m | `m²` | `m²d` |
| 2 | E07 Frostschutzschicht einbauen | `m²` | `m³` |
| 2 | T02 Asphalt aufbrechen, laden, entsorgen | `m²` | `m³` |
| 2 | B03 Stundenlohnarbeiten Facharbeiter | `h` | `m` |
| 2 | B04 Bestandsdokumentation | `psch` | `m²` |

**Was zu tun ist:** Leistungen dürfen **mehrere Abrechnungseinheiten** haben. Entweder
eine zusätzliche Zeile je Einheit (eigener Code, z. B. `B04-ST`), oder ein
Umrechnungsfaktor je Leistung (`m² → m³` über die Schichtdicke, `Wo → StWo` über
die Stückzahl). Variante 1 ist einfacher und für das Hackathon ausreichend.

### Ursache B — Leistung fehlt ganz (94 Positionen)

| Anz. | Gruppe | benötigte Einheiten |
|---:|---|---|
| 22 | **Formteile und Armaturen** | `St` |
| 19 | **Baustellenausstattung** | `St`, `m`, `mWo`, `StWo`, `h` |
| 7 | Baustrom / Bauwasser | `St`, `m` |
| 6 | Landschaftsbau / Begrünung | `m²`, `St`, `kg` |
| 4 | Prüfungen und Untersuchungen | `St` |
| 3 | Schutzmaßnahmen am Bestand | `St`, `m` |
| 3 | Vorhalte-Varianten vorhandener Leistungen | `mWo` |
| 30 | Einzelfälle ohne Gruppe | gemischt |

---

## Die drei strukturellen Lücken

### 1. Der Lebenszyklus fehlt: herstellen → vorhalten → umsetzen

Das ist der wichtigste Punkt. Deutsche LVs zerlegen jede Baustellenausstattung in
**drei** Positionen mit **drei verschiedenen Einheiten**:

```
Bauzaun H 2 m aufstellen räumen      [m]      ← herstellen
Bauzaun H 2 m vorhalten              [mWo]    ← Standzeit, je Woche
Bauzaun H 2 m umsetzen               [m]      ← versetzen
```

Dasselbe Muster bei Laufsteg, Witterungsschutz-Zelt, Behelfsüberfahrt,
Verkehrszeichen, Warnleuchte, Schutzwand. Der Katalog kennt nur „vorhalten" bei
einer einzigen Leistung (B02) und keine `umsetzen`-Variante.

**Das ist kein Randfall.** Vorhalte- und Umsetz-Positionen sind der Grund, warum
20 Positionen auch im Vergleichspreis-Modul als „kein Vergleichswert" enden.
Jede Ausstattungs-Leistung braucht alle drei Varianten.

### 2. Rohrleitungsbau ohne Formteile

Der Katalog rechnet Rohr nach Metern ab (K01, K05 …), enthält aber **kein
einziges Formteil**. Ein echtes LV hat davon Dutzende, alle nach Stück:

> Bogen 45–90°, T-Stück, Verbindungsmuffe, Abschlussmuffe, Abschrumpfmuffe,
> Verschlussmuffe, Absperrarmatur, Segmentschnitt, Übergangsstück

**22 Positionen** allein in diesem LV. Das ist die größte Einzelgruppe.

### 3. Fehlende Gewerke

Vorhanden: Erdbau, Verbau, Kanal, Wasser, Kabel, Schacht, Straße, Oberbau, Baustelle.

Es fehlen: **Landschaftsbau** (Rasen ansäen, Düngen, Wurzelbehandlung, Stammschutz),
**Prüfungen** (Verformungsmodul/Lastplattendruckversuch, Abfalldeklaration,
Dichtheitsprüfung als eigene Leistung), **Schutz des Bestands** (Schutzrohr sichern,
Mastleuchte schützen, Ummantelung), **Wasserhaltung** (Pumpe aufstellen/betreiben).

---

## Konkrete Vorschlagsliste

Ungefähr **45–55 neue Zeilen** bringen die Abdeckung über 80 %. Priorität von oben.

| Prio | Neue Leistungen | ca. Anzahl | Einheiten | deckt ab |
|---:|---|---:|---|---:|
| 1 | Formteile/Armaturen (Bogen, T-Stück, Muffen, Schieber, Übergang) | 10 | `St` | 22 |
| 2 | Ausstattung × 3 Varianten (Bauzaun, Laufsteg, Zelt, Überfahrt, Verkehrszeichen, Warnleuchte) | 18 | `m`/`St` + `mWo`/`StWo` | 19 |
| 3 | Einheiten-Varianten bestehender Leistungen (Tabelle Ursache A) | 12 | s. o. | 61 |
| 4 | Baustrom / Bauwasser (herstellen + vorhalten) | 4 | `St`, `m`, `mWo` | 7 |
| 5 | Landschaftsbau (Rasen, Düngen, Wurzel, Stammschutz) | 5 | `m²`, `kg`, `St` | 6 |
| 6 | Prüfungen (Lastplatte, Deklaration, Dichtheit) | 3 | `St` | 4 |
| 7 | Schutz des Bestands (Schutzrohr, Mastleuchte, Ummantelung) | 3 | `St`, `m` | 3 |

Wichtig bei jeder neuen Zeile: `h_min` / `h_mittel` / `h_max` **unterschiedlich**
ansetzen. Die Spanne ist kein Beiwerk — sie erzeugt die Preisspanne und damit das
Signal „diese Position ist schwer kalkulierbar". Bei `h_min == h_max` ist die
Spanne null und das Signal weg.

---

## Zwei Dinge außerhalb des Katalogs

**Schema-Änderung dokumentieren.** `bieter` ist weggefallen, die Parameter
(`mittellohn_eur_h`, `zuschlag_pct`, `leistungsfaktor`) liegen jetzt auf
`angebote`, und `materialfaktor` heißt dort `materialindex`. Der Code hat das
still abgefangen und mit Default-Werten weitergerechnet — beim nächsten Umbau
bitte kurz Bescheid geben, sonst rechnet das Angebot mit falschem Mittellohn.

**Klassifizierungs-Cache invalidieren.** `data/classification_cache.json` wird nur
über den Positionstext geschlüsselt, nicht über die Katalog-Version. Nach jeder
Katalog-Erweiterung muss die Datei gelöscht werden, sonst bleiben die alten
Zuordnungen stehen und die neuen Leistungen werden nie gefunden.

---

## Abnahmekriterium

So wird gemessen, ob wir da sind:

```bash
python3 -c "
from core import stammdaten, classify, kalkulation, parser_x83
d=stammdaten.load(); b=parser_x83.parse('Dataset/[NUMMER_001]_leer.X83')
c=kalkulation.calculate(b, classify.classify(b,d), stammdaten.companies()[0], d)
print(kalkulation.summarize(c))"
```

| Ziel | Wert |
|---|---|
| Abdeckung | **> 80 %** (heute 37,5 %) |
| Angebotssumme | plausibel gegen die realen **897.305 €** für dieses LV |
| Einheiten-Konflikte | **0** |

Erst ab ~80 % Abdeckung ist die Angebotssumme überhaupt mit dem echten Angebot
vergleichbar — darunter deckt sie nur einen Teil des LV ab und die Zahlen sagen
nichts über die Qualität der Kalkulation aus.
