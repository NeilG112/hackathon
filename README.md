# Bid & Risk Assistant

> It reads a construction tender, prices it from the contractor's own rate
> tables, and tells him which positions will cost him money.

German construction tenders (GAEB Leistungsverzeichnisse) arrive as a few
hundred — on a real job, a few thousand — line items that a contractor must
price. This reads the file, builds a bid bottom-up, and triages the positions
worth a human's attention.

Every number below is measured against the files in `Dataset/` and
reproducible with the commands given. Where something does not work, it says
so.

---

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

```bash
python3 validate_gate.py              # parser equivalence — must be green
python3 -m unittest discover tests    # 25 tests
python3 scripts/show_clusters.py      # the cluster view on the demo tender
```

`Dataset/` is read-only. Never write to it.

## What it does, in five stages

```
GAEB file ──► parse ──► classify ──► price ──► judge risk ──► hand back
```

**1 · Parse.** Four GAEB formats (X83 XML, D83/D84/D86 fixed-width). The same
tender in two different formats produces byte-identical output, asserted on
every run by `validate_gate.py`. Section labels and the item hierarchy come
out with it — the risk checks need them.

**2 · Classify.** Each position is matched to a work type in the rate
catalogue. TypeSafe **Jev** does this: a Choice over the catalogue paired with
a companion Noul asking whether the catalogue covers this work at all. Without
that Noul a Choice always returns *something*, and positions from trades the
catalogue doesn't contain get confidently mis-assigned.

**3 · Price.** Textbook Aufschlagskalkulation:

```
EKT = hours × Mittellohn + machine hours × rate + material
EP  = EKT × (1 + AGK×Bauzeit/12 + BGK + W&G)
```

It produces a **range**, not a point, because the rate table carries
fastest/typical/slowest times. AGK is prorated over the build time — a
ten-month job carries ten twelfths of the firm's annual overhead.

**4 · Judge risk.** Three layers, each doing what it is good at:

- *Arithmetic* — deterministic rules over clusters of positions: containment,
  cardinality, DIN 4124 trench depth, missing follow-up work.
- *Money* — only the top 10 % by euro exposure and the specialist-looking
  positions go further. 35 of 248 on the demo tender.
- *Judgement* — Jev answers five independent yes/no questions per selected
  position (ambiguous scope, implausible quantity, implausible price,
  specialist trade, likely to grow after award). **Code combines them**;
  the model never returns the risk class itself.

**5 · Hand back.** A Bieterfragen-Katalog as .docx. A GAEB X84 bid file is not
implemented.

## Measured results

On `Dataset/[NUMMER_001]_leer.X83`, 248 positions:

| | |
|---|---|
| Classified | **89.5 %** |
| Calculated (after unit check) | **86.3 %** |
| Cluster findings | **4**, all defensible |
| Bid | **€505,953 – 584,830 – 663,403** |
| A real contractor bid for this BoQ | **€897,305** |
| High risk | 32 positions = **75 % of the money in 13 % of the lines** |

Component accuracy, measured separately:

```
classifier    94 % correct on 2,496 labelled positions in Database/
calculation   5.3 % median error against 2,459 real prices in Database/
```

**The bid is low and the reason is known.** The engine reproduces the
database's own prices to 5.3 %, so the arithmetic is right; the rate tables
are synthetic and sit below market. `Database/` says so in its own metadata:
*"Preise plausibel Stand 2026, keine Marktabfrage."* Show the range and name
the reason — do not quote the midpoint as a bid.

## Speed

248 positions, everything from cache (the demo path, no network):

```
GAEB parsen               108 ms
Fakten extrahieren         63 ms
Klassifizierung (Cache)    15 ms
Kalkulation                 7 ms
Vergleichspreise          135 ms
Clustering                154 ms
Regel-Engine              264 ms
Risiko-Pipeline           761 ms
GESAMT                  1,507 ms      6.1 ms / position
```

Extrapolated to 9,000 positions: **~55 s**. A cold run adds the Jev calls —
248 positions classify in about 9 s at 8 parallel workers.

## Cost per tender

Jev is $0.084 per million input tokens. The catalogue is sent with every
classification call, which dominates everything else:

| | 248 positions | 9,000 positions |
|---|---|---|
| before | $1.16 | $42.47 |
| **now** (slim criteria, 180-option shortlist) | **$0.18** | **$6.70** |
| possible: 10 positions per call | $0.02 | $0.67 |

The catalogue carried a 170-character `bemerkung` for all 939 Leistungen on
every call — 84 % of the tokens, for prose that never helped tell two
Leistungen apart. Batching several positions into one call is the remaining
factor of ten and has not been done.

Risk judgements are negligible — capped at 60 calls, about $0.002 per tender.

## Known problems

**Three cluster rules are switched off.** `DN_STEP`, `SHAFT_COVER_CARD` and
`ELECTRO_LIGHTING_CONNECTION` produced six findings on the demo tender and
every one was wrong — keyword matches inside German compounds whose meaning
is the opposite of the assumption (`Suchschachtung` is not a shaft,
`Strassenkappe` is not a manhole cover, `Schutz Mastleuchte Bestand` protects
an existing lamp rather than installing one). See `logic.DISABLED_RULES`. The
rule shapes are sound; they need a classifier that understands the position,
not more keyword patches.

The four that remain all hold up: a 1.75 m trench with no shoring (DIN 4124),
two drinking-water lines with no pressure test or hygiene certificate
(DIN EN 806), and demolished paving with no restoration position.

**`TRENCH_VOLUME` never fires.** The rule compares `Leitungsgraben[m]` against
`Bodenaushub[m³]`, but in this tender the m³ excavation quantities are tagged
`Leitungsgraben` and `Bodenaushub` has exactly one position, in `St`. The rule
and the tag vocabulary disagree.

**Comparing the two pricing engines is switched off.** See
`HYBRID_DIVERGENCE_THRESH` in `core/constants.py` — the comparable-price engine
is −50 % with 91 % median per-position error, so disagreement with it was
noise, and it was consuming 57 of 60 LLM slots.

## Layout

```
app.py                     Streamlit UI, page-based
validate_gate.py           parser equivalence — run before every push
export_rfi.py              Bieterfragen-Katalog → .docx
core/
  parser_x83 / parser_gaeb90   GAEB readers, namespace-agnostic
  facts.py                 DN, PN, depth, material, inkl-exclusions
  clusters.py              section / system / frame clusters
  logic.py                 declarative RuleSpec catalogue
  classify.py              position → Leistung, Jev + cache + keyword fallback
  kalkulation.py           Aufschlagskalkulation, price ranges
  stammdaten.py            rate tables + cost-base presets
  risk_engine.py           deterministic + LLM hybrid risk
  judgments.py             the five atomic Jev questions
  deep_logic.py            provider-agnostic cluster evaluation
  pricer.py                comparable-price engine — cross-check only
Database/                  rate tables + 2,496 labelled test positions
data/*.json                caches: classification, judgments, deep logic
```

## Rules that are not negotiable

- **Run `python3 validate_gate.py` before every push.** Red means something
  upstream broke and nothing downstream is trustworthy. Never loosen the
  assertion to make it pass.
- **Changed the rate catalogue? Delete `data/classification_cache.json`.** It
  is keyed on position text only, not on the catalogue version. A stale cache
  silently swallows a catalogue extension — this already cost us one round.
- **Never hardcode an XML namespace.** Two appear in the dataset; match on
  `local-name()`. A wrong-namespace XPath returns zero nodes *silently*.
- **Check units before multiplying.** An Aufwandswert is hours per unit *of the
  Leistung*. Without that guard the tender priced at €2.9M against a real
  €897k, because metre-week positions were costed at per-m² labour rates.
- **Never measure against a bid that is in your benchmark.** That once showed
  "+6.3 % accurate" where the honest figure was −50 %.
- **No live API call on the prepared demo path.** Pre-generate, cache to disk,
  commit the JSON. Uploaded files do call out — that is deliberate, the
  alternative is 3 % coverage and a broken-looking demo.
