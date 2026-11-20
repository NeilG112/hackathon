# What needs to be done

Four people, three open workstreams, no shared files. Pick one, claim it in the group
chat, and don't edit anyone else's file.

Read [README.md](README.md) first (setup + architecture), then [PLAN.md](PLAN.md) if you
want the reasoning. This file is just the work.

---

## Where the project is right now

Working end to end, on real data, verified:

```bash
python3 validate_gate.py     # both parsers agree: 159/159 items. Must stay green.
python3 validate.py          # our estimate vs. a real €897,305.45 bid: +6.3%
streamlit run app.py         # upload → table → sliders → totals → the reveal
```

| Layer | State |
|---|---|
| GAEB XML + GAEB 90 parsers | done — 9 files, 4 formats, all parse |
| Price benchmark, 720 real priced items | done — `data/reference_prices.json` |
| Pricer (benchmark-first, labelled fallback) | done — `core/pricer.py` |
| Measured error vs. a real bid | done — +6.3%, median 7% per position |
| UI spine | done — parses, prices, compares |
| Detectors | done — 59 findings on the demo tender |
| **RFI export** | **open — task 006** |
| **Findings panel + polish** | **open — task 007b** |
| **Reveal view** | **working draft — task 007c** |

Everything open is independent. Nothing below is blocked by anything else below.

---

## Task 004 — The three detectors — **DONE**

`core/detectors.py` is implemented. 59 findings on the demo tender (31 price, 17 scope,
11 quantity), rendering in `app.py` with no UI changes — the guard did its job.

Two design decisions worth knowing if you touch it:

**Detector 1 has two modes, because the input decides what is detectable.** A priced file
(a submitted bid) has observed rates, so a rate outside the comparable band is a real
speculative-price finding. A *blank tender* has no rates at all — the only number is our
own estimate, which was drawn from the benchmark, so testing it against that benchmark is
circular. On the demo file **228 of 248 estimates are exactly their benchmark median**; a
naive implementation returns zero findings and looks like it works. So on a blank tender
detector 1 reports market **dispersion**: where real contractors disagree most, our single
number is least trustworthy.

**The outlier test uses quartiles, not a ratio to the median.** Some comparable groups are
enormously wide — the catch-all "St" group spans €0.50 to €39,186 — and against a median
alone an ordinary rate in a wide group reads as "0.1x the market". Testing against the
band the comparables actually occupy cut false positives from 24 findings to 15.

### Still open here

- `constants.VAGUE_SCOPE_TERMS` is 13 German phrases. It is the cheapest quality win in the
  repo: every term you add is a finding the tool can make. Needs a German speaker more than
  a programmer.
- The provisional-share check fires on `quantity == 0 or is_lump_sum`. Worth sanity-checking
  against what an estimator actually counts as an Eventualposition.

---

## Task 006 — The clarification letter

**File you own:** `export_rfi.py`, `data/rfi_templates.json`

This is the handover artifact — the thing the estimator actually keeps. It's also the
least code-heavy task on the list: **most of the work is German, not Python.**

Turn ranked findings into a formal Bieterfragen-Katalog in correct VOB phrasing, exported
as .docx. One template per detector type, with slots for OZ / Kurztext / Menge / Einheit.

### Rules

- **No live LLM in the demo path.** Pre-generate the phrasings, cache them to
  `data/rfi_templates.json`, commit the JSON. A network call on stage is a failed demo.
- **Plain English everywhere else, German only in the artifact.** That split is
  deliberate and it's in PLAN.md — don't give the judges a vocabulary lesson.
- Provide `to_markdown()` as well as `to_docx()`. If python-docx misbehaves live, we need
  a stdlib-only path that still produces something handover-shaped.

### The thing nobody has done

**No German construction professional has read a word of our output.** Wrong VOB register
is exactly what an industry judge spots in four seconds. Get the draft in front of someone
who writes these for a living before Sunday. This matters more than the code.

---

## Task 007b — Findings panel and polish

**File you own:** `app.py`

The spine works: upload, parse, item table, sliders, priced totals, reveal. What's left is
everything that makes it not look like a prototype.

- The findings panel is stubbed and **guarded** — it catches `NotImplementedError` and
  shows a note. When 004 lands it fills in with no work from you; your job is making it
  readable (severity colours, grouping, the rationale next to each row).
- Layout, spacing, the item tables (248 rows is a lot to look at).
- The upload path: try a file that isn't GAEB and make sure the failure is graceful.

### Rules

- **Never price with a benchmark that contains the answer.** `app.py` already holds the
  answer key out before pricing. An earlier version priced with the full benchmark and
  printed a caption claiming otherwise — €6.2k of silent self-flattery on this file. If
  you refactor `main()`, keep the hold-out *before* `price_boq`.
- **`kein Vergleichswert` stays visible.** 20 positions have no comparable. Don't let a
  tidier layout hide them — the honesty is the feature.

---

## Task 007c — The reveal view

**File you own:** `views/reveal.py`

A working draft exists. **Extend it, don't rewrite it.** The seam with `app.py` is one
function in one direction:

```python
from views.reveal import render
render(priced, answer_items, source_label)
```

You never open `app.py`; 007b never opens your file.

This is PLAN.md's demo step 4 and **it is the whole pitch**: an undefendable absolute
number replaced by a measured error against a real human bid. Make it land.

- The maths lives in `core/pricer.py` on purpose, so the screen and `validate.py` cannot
  disagree. Change it there, not here.
- The headline currently shows €885,986 (the like-for-like subtotal over the 227 positions
  priced on both sides), with the full €897,305.45 in the caption. Decide which way round
  you want that — there's an honest argument for either, but you need to be able to defend
  it when asked.
- The fitted scalar (0.93×) **is** the competitor's implied cost base. That's the sentence
  for the slider demo: *"drag the wage to €41/h and we land on their bid — that's their
  cost base."*

---

## Not a coding task, and nobody owns it

PLAN.md lists three assumptions that are still unverified, and all three can invalidate a
day of work:

1. What does the hackathon actually **score**?
2. How long is the demo slot?
3. Are hand-authored / AI-generated rates permitted at all? (Our fallback rates in
   `constants.py` depend on this. The benchmark doesn't — it's real observed prices.)

Ten minutes with an organiser. Whoever is least deep in code should just go and ask.

---

## House rules

- `Dataset/` is **read-only**. Never write to it.
- `core/` and `utils/` are **stdlib only**. Dependencies belong in the UI and export layer,
  so `validate_gate.py` runs anywhere.
- **Run `python3 validate_gate.py` before every push.** If it's red, something upstream
  broke and nothing downstream can be trusted. Don't loosen the assertion to make it pass.
- One owner per file. Need a change in someone else's file? Ask them.
- `core/constants.py` is the one shared file — own your section, never reformat another.

## Five facts that cost real time to establish

Worth knowing before you hit them yourself:

1. **Join on `padded_key((2,2,4))`, never `key()`, never list index.** The blank BoQ stores
   hierarchy levels unpadded (`1,1,1`), priced files pad them (`01,01,0001`). Naive join
   matches **zero** of 248 positions and looks exactly like a pricing failure.
2. **Never hardcode an XML namespace.** Two namespaces appear in the dataset; match on
   `local-name()`. A wrong-namespace XPath returns zero nodes *silently*.
3. **Keyword buckets alone are useless for pricing** (−50% total, 91% median error). They
   can't separate `Rohrleitung markieren` (€0.27/m) from `Leitungsbehelfsbrücke`
   (€6,000/m). Matching on item *text* gets it to 7%.
4. **The answer key is inside the benchmark.** Always `pricer.without_source()` before
   measuring against it.
5. **Unit strings are encoding-damaged.** 50 of 720 items read `m▓` / `m│` — those files
   are cp850 for letters but latin-1 for superscripts. Use `constants.normalize_unit()`,
   never compare raw unit strings.
