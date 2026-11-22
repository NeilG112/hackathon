# Bid & Risk Assistant — Build Plan

> **Scope:** hackathon build, ~36h from Fri 20 Nov evening.
> **Product:** an estimator-perspective bid & risk assistant for German construction tenders (GAEB).

## The one sentence

> It reads a construction tender file, finds the line items that will cost the contractor money,
> and writes the clarification letter he'd otherwise spend four hours on.

No German, no file extensions. Lead with this every time. German belongs in the *artifact*
(the Bieterfragen-Katalog must use correct VOB phrasing), plain English in the *narration*.

---

## Deleted before any code is written

`build_corpus.py` · `parser_pdf.py` · `utils/semantic.py` · `corpus_rules.json` ·
`master_rates.json` · `rules.json` · the six-layer architecture slide · the hero total price ·
GAEB write-back · PDF as runtime input · detectors 4 and 5.

Rationale: the ~30 trade PDFs (Maler, Trockenbau, Fliesen, Estrich, Teppich, Schreiner) share
**zero trade overlap** with both the blank BoQs and the priced files, which are all
Tiefbau / Rohrleitung / Schacht / Straßenbau. A co-occurrence matrix over 30 heterogeneous
documents is noise, and it costs the entire build window. Cutting it buys back Saturday.

> **Current rule-engine scope:** `core/domain.py` now detects Tiefbau, Hochbau/Rohbau,
> Ausbau, TGA Elektro and TGA SHK from LV text, section labels and preambles. The
> deterministic domain checks are completeness heuristics and do not imply that the
> historical reference-price corpus covers those trades.

---

## Verified facts this plan rests on

All checked directly against the files in `Dataset/`, not assumed.

| Fact | Consequence |
|---|---|
| `8209.003_Leistungsverzeichnis_leer` exists as both `.D83` and `.X83`, 159 items each, identical quantities/units | Free machine-checkable oracle for the hardest component |
| `[NUMMER_001]_leer.X83` (248 items) ≈ `StBALV23040.D86` (249 priced) — same BoQ, quantity sequence matches | Blank input **with a human-submitted answer key** |
| `StBALV23040.D86` bid total = **€897,305.45** | The reveal number |
| Scaling: qty ÷1000, EP ÷100, GB ÷100 | Verified: EP `0000000020` × qty `00000028000` = GB `000000000560` → 0.20 × 28 = 5.60 |
| Three distinct OZ layouts in type-23 records | Per-file calibration, not one hardcoded column slice |
| `501-24-01_GAEB-XML_sas.x83` is namespace `GAEB_DA_XML/200407`; the other three X83 are `DA83/3.2` | Match on `local-name()`, **never** a hardcoded namespace URI — 3.2-keyed XPath silently returns zero nodes on the 296-item file |
| No flat OZ field in X83 — compose from nested `RNoPart` | `01` + `01` + `0001` → matches D86 key `2101010001`. This is the join. |
| 46 `<Remark>` blocks are **not** items (248 `<Item>`, 32 `<BoQCtgy>`) | Must exclude from the item list — and they are where contract risk hides |
| Item text is HTML-wrapped `<span style=...>` inside `<Text>` | `text_cleaning.py` is required, not optional |
| A quantity-less `.D84` is spec-normal (it's a bid submission referencing the D83/D86) | Join `StBALV23040.D84` to its sibling `.D86`; don't treat as corrupt. The unusual file is `Angebot AN24-0305.D84` for *carrying* quantities. |

### The three OZ layouts

```
2301010001  0001600000  000001600000              StBALV23040.D84/.D86
23 1 1  10  00072000000 000007200000 00000001000  Angebot AN24-0305.D84
230101   1  0000570000  000000570000 00000001000  [ORT_024] LV24069.D86
```

Differing field widths *and* offsets. Detect the layout per file, then slice.

### Usable priced data

| File | type-21 (qty) | type-23 (price) | Usable |
|---|---|---|---|
| `Angebot AN24-0305.D84` | 274 | 274 | yes |
| `StBALV23040.D86` | 249 | 249 | yes |
| `[ORT_024] LV24069.D86` | 197 | 197 | yes |
| `StBALV23040.D84` | **0** | 249 | prices only — join to its `.D86` |

~720 priced items, all same-trade as the blank BoQs. This is the strongest layer in the system.

---

## Architecture

```
boq-assistant/
├── app.py                      # Streamlit
├── validate.py                 # twin-pair error report  <- credibility layer
├── core/
│   ├── models.py               # NormalizedItem
│   ├── parser_x83.py           # namespace-agnostic; OZ from RNoPart path
│   ├── parser_gaeb90.py        # tolerant slicer, per-file OZ calibration
│   ├── pricer.py               # benchmark-first, master rates as labeled fallback
│   ├── detectors.py            # 3 detectors
│   └── constants.py            # rates + rule words inline (no JSON, no load path, no KeyError on stage)
├── export_rfi.py               # Bieterfragen-Katalog -> .docx
├── data/
│   ├── reference_prices.json   # ~720 priced items — now the core of the system
│   └── golden/                 # pre-parsed fixtures for all 8 GAEB files
├── utils/text_cleaning.py      # strip <span> HTML out of <Text>
└── requirements.txt
```

**The one inversion that matters:** `pricer.py` looks up a real observed price **first** and falls
back to master rates only where no comparable exists — labeling which is which on screen.
The original plan had this backwards, with hand-written rates as the primary source.

**Three detectors, not five:**

1. **Unit-price outlier** vs. the reference distribution — the speculative-price detector.
   Defensible now, because it runs against ~720 real same-trade items.
2. **Vague scope** — trigger words, run over `<Remark>` text as well as item text.
3. **Quantity/unit sanity** — unit mismatches, suspicious round numbers, provisional-item share.

Findings are ranked by **€ leverage** (quantity × price exposure), top 15–25 shown.
Where no comparable exists, print `kein Vergleichswert` — an honest blank beats an invented euro.

---

## Build order

### Fri evening (~3h) — THE GATE

Parse `8209.003_Leistungsverzeichnis_leer.X83` and `...D83` into the same 159-row
`List[NormalizedItem]` and `assert` the two lists are equal.

**Nothing else gets written until this is green.** It builds both parsers, validates the
fixed-width slicer against machine-checkable ground truth with zero spec reading, settles
decimal scaling and cp850 decoding, and proves out `NormalizedItem` on both input formats.

### Sat morning (~3h)

`reference_prices.json` from the three usable priced files. Medians per unit + keyword bucket.
Dump `data/golden/` fixtures for all 8 GAEB files while here.

### Sat midday (~1h) — before the UI, not after

`validate.py`: price the blank `[NUMMER_001]_leer.X83`, compare against the €897,305.45 actual,
print the error and the worst-deviating positions. **Join on composed OZ, not list index** —
that absorbs the 248/249 discrepancy.

If the error is wild, there is still time to tune `constants.py`. After the UI exists, there isn't.

### Sat afternoon (~4h)

`pricer.py` + the 3 detectors as pure functions, driven from a script. No Streamlit yet.

### Sat evening (~4h)

Streamlit: upload → item table → company sliders → top-20 by € leverage.

### Sun morning

`export_rfi.py`. RFI texts as pre-written templates with slots.
**No live LLM in the demo path** — pre-generate, cache to disk, ship the JSON.

---

## The demo

1. The one sentence. No vocabulary lesson.
2. Upload the blank BoQ. 248 items parsed live.
3. Top 20 by € leverage, each with a rationale.
4. **The reveal:** "We estimated €X. A real contractor actually submitted €897,305.45 for this
   exact bill of quantities. We're Z% off across 248 items — and here are the eleven positions
   where we disagree by more than 30%. Those are the ones worth arguing about."
5. Drag the Mittellohn slider until the estimate matches the real bid →
   *"that's this competitor's implied cost base."*
6. Click export. Hand over a formal Bieterfragen-Katalog in correct VOB German.

**Step 4 is the whole pitch.** It replaces an undefendable absolute number with a measured error
against a real human bid. It is the only thing in this plan a judge cannot argue with, and it
converts the sliders from a credibility problem ("the headline moves when you drag it") into
the actual feature.

---

## Fallbacks

- **Live parse dies on stage** → app loads from `data/golden/`. Wire this Saturday, not Sunday.
- **Judge uploads their own file** → one tolerant parser, then an honest
  *"format not supported — try this sample"* with the twin pair pre-loaded as a button.
  Degrade visibly rather than fabricating output.
- **No comparable for an item** → `kein Vergleichswert`.

---

## Open threads worth ten minutes

- **The 248 vs 249 gap.** One position likely added between tender and bid. If so, that is itself
  exactly the kind of finding this tool should catch — worth checking, possibly worth demoing.
- **`<Remark>` blocks as the vague-scope target.** 46 of them, full of contract preamble
  (Vorbemerkungen) where risky clauses actually live. Probably the highest-value detector for
  the least work.
- **Unverified:** what the hackathon actually scores, how long the demo slot is, and whether
  hand-authored/AI-generated rates are permitted at all. Worth confirming before relying on
  `constants.py` defaults.
