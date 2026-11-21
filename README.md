# Bid & Risk Assistant

> It reads a construction tender file, finds the line items that will cost the contractor
> money, and writes the clarification letter he'd otherwise spend four hours on.

Lead with that sentence. No German, no file extensions, no vocabulary lesson — German
belongs in the *artifact* (the Bieterfragen-Katalog, in correct VOB phrasing), plain
English in the *narration*.

Full reasoning, verified data facts and the demo script live in [PLAN.md](PLAN.md).
**Read it before writing code.** Everything in this repo exists because of a fact checked
directly against `Dataset/`.

---

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`core/` and `utils/` are **standard library only** — no pandas, no lxml. The parsers must
run anywhere, because `validate_gate.py` is the gate. Dependencies are for the UI and the
.docx export only.

## Commands

```bash
python3 validate_gate.py                        # THE GATE — must be green first
python3 scripts/build_reference_prices.py       # data/reference_prices.json from real bids
python3 scripts/dump_golden.py                  # data/golden/ — the on-stage fallback
python3 validate.py                             # comparable-price engine vs. a real bid
streamlit run app.py                            # the demo
```

`Dataset/` is **read-only**. Never write to it.

## Layout

```
app.py                      Streamlit — the demo surface
validate_gate.py            twin-pair parser equivalence (run before every push)
validate.py                 comparable-price engine vs. a real bid (dev instrument)
export_rfi.py               Bieterfragen-Katalog -> .docx
core/
  models.py                 NormalizedItem — the shared contract
  parser_x83.py             GAEB XML; namespace-agnostic, OZ + section from the tree
  parser_gaeb90.py          GAEB 90 fixed-width; per-file calibrated column slices
  stammdaten.py             the rate tables (Database/) + cost-base presets
  classify.py               position -> Leistung code; Jev, cache, keyword fallback
  kalkulation.py            Aufschlagskalkulation — the bid, as a price range
  objects.py                the object table: (section, object, unit) + roll-up
  logic.py                  cross-position contradictions, deterministic
  detectors.py              price / scope / quantity risk findings
  pricer.py                 comparable-price engine — cross-check only
  constants.py              tunables, inline
utils/text_cleaning.py      strip the HTML wrapper out of item text
views/reveal.py             the comparison against a real submitted bid
Database/                   rate tables + labelled test data (synthetic)
data/reference_prices.json  720 real unit prices from three submitted bids
data/classification_cache.json   pre-computed Jev answers — the demo runs offline
data/golden/                pre-parsed fixtures (fallback if a live parse dies)
```

## Where it stands

Every number below is measured, and reproducible with the commands above.

| Stage | What it does | State |
|---|---|---|
| Read | 4 GAEB formats, two formats byte-identical | **gate green** |
| Classify | position -> Leistung, via Jev | **90 %** of the real tender |
| Calculate | hours x wage + machine + material + markup | **84.7 %** coverage |
| Check | risk / logic / comparable cross-check | 59 findings / quiet / labelled |
| Hand back | Bieterfragen letter | done; **GAEB X84 bid file missing** |

```
classifier   94 % correct on 2,496 labelled positions
calculation  5.3 % median error against 2,459 real prices in Database/
real tender  248 positions -> EUR 477,304 – 557,063 – 636,732
             a contractor actually bid EUR 897,305 for this BoQ
```

**The 38 % gap is not a calculation error.** The engine reproduces the database's own
prices to 5.3 %. The synthetic rates simply sit below market — `Database/` says so
itself ("Preise plausibel Stand 2026, keine Marktabfrage"). Reaching the real bid would
need a factor of 1.61 on everything. Either calibrate and say you calibrated, or show
the range and name the reason. Do not quote the midpoint as a bid.

### Two engines, deliberately

The **calculation** (`core/kalkulation.py`) is the bid: bottom-up from the rate tables,
works on a position nobody has ever quoted, auditable line by line.

The **comparable-price engine** (`core/pricer.py`) is an independent second opinion from
720 real prices. On its own it is -50 % with 91 % median per-position error, because two
unrelated reference projects cannot carry a third. It stays as a cross-check — where the
two agree, confidence is higher — and it is never the headline.

## Rules that are not negotiable

- **Never hardcode an XML namespace URI.** Two namespaces appear in the dataset; match on
  `local-name()`. A 3.2-keyed XPath silently returns zero nodes on the 296-item file.
- **Join on OZ, never on list index** — and use `NormalizedItem.padded_key((2,2,4))`, not
  `key()`. The blank BoQ stores hierarchy levels unpadded (`1,1,1`) while the priced files
  pad them (`01,01,0001`), so a naive key join matches **zero** of 248 items and looks like
  a pricing failure. Padded, it matches 247. (PLAN.md's stated join is wrong on this file.)
- **No comparable → print `kein Vergleichswert`.** An honest blank beats an invented euro.
  20 of the 248 demo positions are rental/time units (`Wo`, `mWo`, `m2d`) with no
  comparable anywhere in the benchmark. The contractor charged €10,336 for them. Say so;
  don't fill the hole.
- **Never measure against a bid that is in the benchmark.** Use
  `pricer.without_source(ref, answer_key)`. Worth €6.2k here today, €251k before the
  pricer improved — the magnitude is not the point, the circularity is.
- **No live LLM in the demo path.** Pre-generate, cache to disk, ship the JSON.
- **Changed the rate catalogue? Delete `data/classification_cache.json`.** The cache is
  keyed on position text only, not on the catalogue version. Leaving it in place after an
  extension keeps the old assignments and the new Leistungen are never found — coverage
  stays flat and it looks like the extension did nothing. (It cost us exactly that once.)
- **Don't loosen the gate to make it pass.** A real failure is useful; a gate that passes
  by weakened comparison is worse than no gate.
