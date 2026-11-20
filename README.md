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

| # | Task | Files | Depends on | Done when |
|---|---|---|---|---|
| 001 | **The gate** — both parsers | `core/models.py`, `core/parser_x83.py`, `core/parser_gaeb90.py`, `utils/text_cleaning.py`, `validate_gate.py` | — | `python3 validate_gate.py` prints `GATE GREEN`, 159 items both sides |
| 002 | Reference prices + golden fixtures | `scripts/*` | 001 | `data/reference_prices.json` has ~720 items; `data/golden/` has all 9 GAEB files |
| 003 | Pricer | `core/pricer.py` | 002 | prices a BoQ, labels benchmark vs. fallback, returns `None` where no comparable |
| 004 | Three detectors | `core/detectors.py` | 003 | `run_all` returns findings ranked by € leverage |
| 005 | **The reveal** | `validate.py` | 003 | prints our total, the real €897,305.45, the % error, worst positions |
| 006 | RFI export | `export_rfi.py` | 004 | a .docx Bieterfragen-Katalog in VOB German, no live LLM |
| 007 | Streamlit UI | `app.py` | 004, 005 | upload → table → sliders → top 20 → reveal → export |

**001 is a hard gate.** Nothing else is worth writing until it's green — it settles cp850
decoding, decimal scaling, the fixed-width slicer and `NormalizedItem` against
machine-checkable ground truth. 005 comes *before* the UI: if the pricing error is wild
there's still time to tune `constants.py`; after the UI exists there isn't.

Parallelism: 003/005 and 006 can run alongside 004 once 002 lands. 007 last.

## Rules that are not negotiable

- **Never hardcode an XML namespace URI.** Two namespaces appear in the dataset; match on
  `local-name()`. A 3.2-keyed XPath silently returns zero nodes on the 296-item file.
- **Join on composed OZ, never on list index.** That's what absorbs the 248/249 gap.
- **No comparable → print `kein Vergleichswert`.** An honest blank beats an invented euro.
- **No live LLM in the demo path.** Pre-generate, cache to disk, ship the JSON.
- **Don't loosen the gate to make it pass.** A real failure is useful; a gate that passes
  by weakened comparison is worse than no gate.
