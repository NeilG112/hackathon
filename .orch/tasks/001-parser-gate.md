# Task: build both GAEB parsers and make the twin-pair gate green

## Goal

`Dataset/8209.003_Leistungsverzeichnis_leer.D83` (GAEB 90 fixed-width) and
`Dataset/8209.003_Leistungsverzeichnis_leer.X83` (GAEB XML) are the **same bill of
quantities in two formats**, 159 items each. Parse both into the same
`List[NormalizedItem]` and prove the two lists agree. This is the project's gate: nothing
else gets built until it passes.

## Context

Read `PLAN.md` sections "Verified facts this plan rests on" and "Architecture" first.

### Facts already verified — rely on these, do not re-derive

D83 (GAEB 90, fixed-width):
- Encoding is **cp850**. Line endings CRLF. 4278 lines.
- Record type = first 2 chars. Counts: `26`×3857 (long text), `21`×159 (**the quantity
  records — these are your items**), `25`×159, `11`/`12`/`31`×28 each, `20`×13, plus
  single `00`,`01`,`02`,`03`,`08` header records.
- The last 6 characters of every line are a running sequence number, not data.
- A type-21 line looks like this (exact bytes from the file):
  ```
  210101   1 NNN         00000001000psch                                    000010
  ```
  Measured column slices for **this** file: OZ occupies roughly `[2:11]`
  (`'0101   1'`), quantity `[23:34]` = `'00000001000'`, unit `[34:38]` = `'psch'`.
- Quantity scaling: integer field **÷ 1000**. So `00000001000` → `1.0`.
- Column offsets differ between GAEB 90 files (PLAN.md documents three layouts). Write the
  slicer so the offsets are **parameters you calibrate per file**, not constants buried in
  the function. For this task, calibrate against the X83 side — that is the whole point of
  the twin pair.

X83 (GAEB XML):
- Namespace is `http://www.gaeb.de/GAEB_DA_XML/DA83/3.2` for this file, but another dataset
  file uses `.../200407`. **Match on `local-name()` / tag-after-`}` only. Never hardcode a
  namespace URI** — a 3.2-keyed XPath silently returns zero nodes on the other file.
- There are exactly 159 `<Item>` elements, 28 `<BoQCtgy>`, 29 `<BoQBody>`.
- **`<Item>` carries attributes** (`ID`, `RNoPart`), e.g. `<Item ID="id187" RNoPart="1">`.
  Note PLAN.md describes `RNoPart` as a nested *element* — that is wrong, it is an
  **attribute**. Also: a naive `text.count("<Item>")` returns 0 because of the attributes.
  Use a real XML parser (`xml.etree.ElementTree` is fine).
- `<Item>` children include `Qty` (`'1.000'`), `QU` (`'psch'`), `LumpSumItem` (`'Yes'`),
  `Description`.
- **The OZ (item number) is composed, not stored flat.** Ancestor chain of an `<Item>` is
  `Itemlist ← BoQBody ← BoQCtgy ← BoQBody ← BoQCtgy ← BoQ ← Award ← GAEB`. Each `BoQCtgy`
  carries its own `RNoPart` attribute (e.g. `'01'`). Compose outermost → innermost, then
  append the `Item`'s own `RNoPart`. First item: `'01'` + `'01'` + `'1'`, which must line up
  with the D83 OZ `'0101   1'` once you normalise padding.
- Item text is HTML-wrapped (`<span style=...>`, `<p>`, `<li>`, `<br>`) inside `<Text>`.

## Do

Build exactly these, per PLAN.md's Architecture section:

1. `core/models.py` — a `NormalizedItem` dataclass. Minimum fields: `oz` (normalised
   string key), `quantity` (float), `unit` (str), `short_text` (str), `is_lump_sum` (bool).
   Give it a `key()` or comparable form used for joining.
2. `utils/text_cleaning.py` — strip the HTML wrapper out of item text, collapse whitespace.
3. `core/parser_x83.py` — `parse(path) -> List[NormalizedItem]`, namespace-agnostic,
   OZ composed from the `RNoPart` attribute chain.
4. `core/parser_gaeb90.py` — `parse(path) -> List[NormalizedItem]`, cp850, tolerant
   slicer with per-file calibrated offsets.
5. `validate_gate.py` at the repo root — parses both files, compares, prints a report.

OZ normalisation is the crux: both sides must produce the **same** key (strip the internal
padding from the D83 form, zero-pad or join the X83 parts consistently). Pick one canonical
form, document it in a comment, and use it on both sides.

## Definition of done

```
python3 validate_gate.py
```

exits **0** and prints `GATE GREEN`, having asserted all three of:

- both parsers return exactly **159** items
- the two sets of normalised **OZ keys are identical** (compare as sets, and report any
  symmetric difference rather than just a count)
- for every matched OZ, **quantity and unit are equal** (quantity to 3 decimal places)

Item text is **not** part of the hard assertion — the two formats store it differently.
Compare it after normalisation and print the number of items whose text differs, as
information only. Do not fail the gate on text.

If the gate will not go green, **do not loosen the assertion to make it pass.** Report
`partial` or `blocked` with the actual mismatch output. A real failure is useful; a gate
that passes by weakened comparison is worse than no gate.

## Constraints

- **Standard library only.** No pip installs, no lxml, no pandas.
- **Do not modify anything in `Dataset/`.** Read-only, always.
- Do not touch `PLAN.md`, `.gitignore`, or anything in `.orch/`.
- Do not create top-level directories beyond `core/` and `utils/`. No Streamlit, no pricer,
  no detectors, no `data/` fixtures — those are later tasks. Stay in scope.
- Add `core/__init__.py` and `utils/__init__.py` so imports work.

## Report back

Call `finish` with:
- `verification`: paste the **actual stdout** of `python3 validate_gate.py`
- `files_changed`: every file created or edited
- `open_questions`: any offset you had to guess, any assumption about OZ normalisation, and
  anything you noticed in the data that looks like it will bite the next task
