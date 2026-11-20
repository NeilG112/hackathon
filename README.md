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
python3 validate.py                             # our estimate vs. a real €897,305.45 bid
streamlit run app.py                            # the demo
```

`Dataset/` is **read-only**. Never write to it.

## Layout

```
app.py                      Streamlit — the demo surface
validate_gate.py            twin-pair parser equivalence (the gate)
validate.py                 measured error vs. a real human bid (the credibility layer)
export_rfi.py               Bieterfragen-Katalog -> .docx
core/
  models.py                 NormalizedItem + Finding — the shared contract
  parser_x83.py             GAEB XML; namespace-agnostic, OZ from RNoPart chain
  parser_gaeb90.py          GAEB 90 fixed-width; per-file calibrated column slices
  pricer.py                 benchmark first, labeled fallback rates second
  detectors.py              three detectors, pure functions
  constants.py              every tunable, inline — no JSON load path to fail on stage
utils/text_cleaning.py      strip the HTML wrapper out of item text
scripts/                    one-shot data builders
data/reference_prices.json  ~720 real priced items — the core of the system
data/golden/                pre-parsed fixtures (fallback if a live parse dies)
```

## Splitting the work

Tasks are numbered and dependency-ordered. Each module is stubbed with the facts it needs
in its docstring. Task briefs go in `.orch/tasks/NNN-*.md` — see `_TEMPLATE.md`.

| # | Task | Files | Depends on | Status |
|---|---|---|---|---|
| 001 | **The gate** — both parsers | `core/models.py`, `core/parser_x83.py`, `core/parser_gaeb90.py`, `utils/text_cleaning.py`, `validate_gate.py` | — | **done** — `GATE GREEN`, 159/159 |
| 002 | Reference prices + golden fixtures | `scripts/*` | 001 | **done** — 720 priced items, 9 fixtures |
| 003 | Pricer | `core/pricer.py` | 002 | **done** — +6.3% vs. the real bid |
| 004 | Three detectors | `core/detectors.py` | 003 | **open** — `run_all` returns findings ranked by € leverage |
| 005 | **The reveal** | `validate.py` | 003 | **done** — see numbers below |
| 006 | RFI export | `export_rfi.py` | 004 | **open** — .docx Bieterfragen-Katalog in VOB German, no live LLM |
| 007 | Streamlit UI | `app.py` | 004, 005 | **open** — upload → table → sliders → top 20 → reveal → export |

The critical path (001 → 002 → 003 → 005) is finished, so **004, 006 and 007 are now
independent** — three people can take one each without touching the same files.

### Where the reveal currently stands

`python3 validate.py`, with the answer key **held out** of the benchmark:

```
our estimate, 248 positions    954,062.31
real submitted bid             897,305.45      +6.3%
after fitting one scalar       78% of positions within +/-30%, median error 7%
50 positions still disagree by >30%  <- the actual findings
```

Two things to understand before you quote those numbers:

- **The benchmark holds the answer key out.** `StBALV23040.D86` is both one of the three
  bids in `reference_prices.json` *and* the bid we measure against. Pricing with it
  included is circular and worth €251k of flattery. `pricer.without_source()` exists for
  this; `validate.py` always uses it. **Never show a judge the leaky number.**
- **Absolute level vs. position accuracy are different claims.** A benchmark from other
  projects gets the *shape* of a price list right and its *level* roughly — site
  conditions and competitive pressure move every rate at once. That is why the demo's
  slider story works: the fitted scalar *is* the competitor's implied cost base
  (`pricer.implied_cost_base`).

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
  `pricer.without_source(ref, answer_key)`. Leakage was worth €251k here.
- **No live LLM in the demo path.** Pre-generate, cache to disk, ship the JSON.
- **Don't loosen the gate to make it pass.** A real failure is useful; a gate that passes
  by weakened comparison is worse than no gate.
