"""Bid & Risk Assistant — Streamlit UI. Task 007.

    streamlit run app.py

> It reads a construction tender file, finds the line items that will cost the
> contractor money, and writes the clarification letter he'd otherwise spend
> four hours on.

Lead with that sentence. No vocabulary lesson, no file extensions.

Wired: upload -> parse -> item table -> company sliders -> priced totals ->
the reveal. Still stubbed, and owned by other people:

  * the findings panel lights up when `core/detectors.py` (task 004) lands
  * the export button lights up when `export_rfi.py` (task 006) lands

Both are guarded, so an unfinished module shows a note instead of a traceback.

Fallbacks, in order: live parse -> `data/golden/` fixture -> an honest
"format not supported" with the sample loaded on a button. Degrade visibly
rather than fabricating output.
"""

from __future__ import annotations

import os
import tempfile
import traceback

import pandas as pd
import streamlit as st

from core import constants, detectors, parser_gaeb90, parser_x83, pricer
from views import reveal

ONE_SENTENCE = (
    "It reads a construction tender file, finds the line items that will cost "
    "the contractor money, and writes the clarification letter he'd otherwise "
    "spend four hours on."
)

SAMPLE = constants.REVEAL["blank_boq"]
ANSWER_KEY = constants.REVEAL["answer_key"]

XML_SUFFIXES = (".x83", ".x81", ".x84", ".x86")
GAEB90_SUFFIXES = (".d83", ".d81", ".d84", ".d86")

st.set_page_config(page_title="Bid & Risk Assistant", layout="wide")


# --- parsing ---------------------------------------------------------------

def parse_path(path: str):
    """Parse by format. Returns (items, remarks). Raises on unknown format."""
    suffix = os.path.splitext(path)[1].lower()
    if suffix in XML_SUFFIXES:
        return parser_x83.parse(path), parser_x83.parse_remarks(path)
    if suffix in GAEB90_SUFFIXES:
        return parser_gaeb90.parse(path), []
    raise ValueError(f"unsupported format: {suffix or path}")


@st.cache_data(show_spinner=False)
def load_from_disk(path: str):
    items, remarks = parse_path(path)
    return [i.as_dict() for i in items], remarks


@st.cache_data(show_spinner=False)
def load_from_upload(name: str, payload: bytes):
    """Parse uploaded bytes. Cached on content, so sliders don't re-parse."""
    suffix = os.path.splitext(name)[1] or ".x83"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(payload)
        temp = handle.name
    try:
        items, remarks = parse_path(temp)
        return [i.as_dict() for i in items], remarks
    finally:
        os.unlink(temp)


@st.cache_data(show_spinner=False)
def load_reference():
    return pricer.load_reference_prices()


def rehydrate(dicts: list[dict]):
    from core.models import NormalizedItem
    return [NormalizedItem.from_dict(d) for d in dicts]


# --- sections --------------------------------------------------------------

def sidebar_company() -> dict:
    """Company cost base sliders. Returns the dict the pricer consumes."""
    st.sidebar.header("Your cost base")
    labels = {
        "mittellohn_eur_h": "Average loaded wage (€/h)",
        "overhead_pct": "Site overhead (%)",
        "profit_pct": "Risk & profit (%)",
        "risk_appetite": "Pricing aggression",
    }
    company = {}
    for field, default in constants.DEFAULT_COMPANY.items():
        lo, hi, step = constants.SLIDER_RANGES[field]
        company[field] = st.sidebar.slider(
            labels.get(field, field), float(lo), float(hi), float(default), float(step)
        )
    multiplier = pricer.company_multiplier(company)
    st.sidebar.metric("Effect on every rate", f"{multiplier:.3f}×")
    st.sidebar.caption(
        "At the defaults this is exactly 1.000× — the estimate is then the raw "
        "benchmark of real observed prices, with nothing added by us."
    )
    return company


def section_upload():
    """Upload -> parse. Writes (items, remarks, label) into session state."""
    st.subheader("1 · The tender")

    upload = st.file_uploader(
        "Drop a tender file",
        type=[s.lstrip(".") for s in XML_SUFFIXES + GAEB90_SUFFIXES],
    )
    if st.button("Use the sample tender", type="primary"):
        st.session_state["source"] = ("disk", SAMPLE)
    if upload is not None:
        st.session_state["source"] = ("upload", upload.name, upload.getvalue())

    source = st.session_state.get("source")
    if not source:
        st.info("Drop a tender file above, or load the sample to see it work.")
        return None

    try:
        if source[0] == "disk":
            raw, remarks = load_from_disk(source[1])
            label = os.path.basename(source[1])
        else:
            raw, remarks = load_from_upload(source[1], source[2])
            label = source[1]
    except ValueError as exc:
        # Known-unknown format. Say so plainly and offer the sample — do not
        # guess at a parse and present fabricated positions as real.
        st.error(f"{exc} — this build reads GAEB X83 and GAEB 90 D83/D84/D86.")
        st.session_state.pop("source", None)
        return None
    except Exception:                                      # noqa: BLE001
        st.error("That file did not parse. Falling back to the stored fixture.")
        with st.expander("What went wrong"):
            st.code(traceback.format_exc())
        try:
            from scripts.dump_golden import load as load_golden
            items, remarks = load_golden(source[1])
            st.success(f"Loaded {len(items)} positions from data/golden/.")
            return items, remarks, os.path.basename(source[1]) + " (fixture)"
        except Exception:                                  # noqa: BLE001
            st.session_state.pop("source", None)
            return None

    items = rehydrate(raw)
    if not items:
        # Spec-normal, not corruption: a .D84 bid submission can carry price
        # records and no quantity records, because it references the .D83/.D86
        # it was bid against. Say that, rather than showing an empty table.
        st.warning(
            f"**{label} carries prices but no quantities.** That is normal for a "
            "bid submission — it references the tender file it was bid against, "
            "and the two are joined on item number. Load that tender file "
            "instead and this bid becomes its answer key."
        )
        st.session_state.pop("source", None)
        return None

    priced_in_file = sum(1 for i in items if i.unit_price is not None)
    st.success(
        f"**{len(items)} positions** parsed from {label}"
        + (f" — {priced_in_file} of them already carry prices" if priced_in_file else "")
        + (f", plus {len(remarks)} contract preamble blocks" if remarks else "")
    )
    return items, remarks, label


def section_items(items):
    """The parsed bill of quantities."""
    st.subheader("2 · What's in it")
    frame = pd.DataFrame([{
        "OZ": i.key(),
        "Position": i.short_text,
        "Menge": i.quantity,
        "Einheit": constants.normalize_unit(i.unit),
        "Pauschal": "ja" if i.is_lump_sum else "",
    } for i in items])
    st.dataframe(frame, width="stretch", hide_index=True, height=320)


def section_pricing(items, company, reference):
    """Price every position and show the totals. Returns the priced list."""
    st.subheader("3 · What it should cost")
    priced = pricer.price_boq(items, reference, company)
    stats = pricer.summarize(priced)

    a, b, c, d = st.columns(4)
    a.metric("Estimated total", f"€{stats['total']:,.0f}")
    b.metric("Priced from real bids", f"{stats['benchmark_share_pct']:.0f}%")
    c.metric("No comparable", stats["no_comparable"],
             help="Positions we refuse to price rather than invent a number for.")
    d.metric("On fallback rates", f"€{stats['fallback_value']:,.0f}",
             help="Value resting on hand-authored rates, not observed prices.")

    frame = pd.DataFrame([{
        "OZ": p.item.key(),
        "Position": p.item.short_text[:60],
        "Menge": p.item.quantity,
        "Einheit": constants.normalize_unit(p.item.unit),
        "EP €": p.unit_price if p.unit_price is not None else None,
        "GP €": p.total if p.total is not None else None,
        "Quelle": {
            "benchmark_match": "matched comparable",
            "benchmark": "bucket median",
            "benchmark_unit": "unit median",
            "fallback_rate": "fallback rate",
            "none": constants.NO_COMPARABLE_LABEL,
        }[p.source],
        "Basis": p.note[:70],
    } for p in priced])
    st.dataframe(frame, width="stretch", hide_index=True, height=320)

    if stats["no_comparable"]:
        st.caption(
            f"{stats['no_comparable']} positions print "
            f"“{constants.NO_COMPARABLE_LABEL}”. These are mostly rental and "
            "time-on-site units with nothing comparable in the benchmark. "
            "An honest blank beats an invented euro."
        )
    return priced, stats


def section_findings(priced, remarks):
    """Top findings by € leverage. Lights up when task 004 lands."""
    st.subheader(f"4 · Top {constants.TOP_N_FINDINGS} positions worth arguing about")
    st.caption(
        "Ranked by € leverage (quantity × price exposure). Where no comparable "
        f"exists we print “{constants.NO_COMPARABLE_LABEL}” rather than invent a number."
    )
    try:
        findings = detectors.run_all(priced, remarks, top_n=constants.TOP_N_FINDINGS)
    except NotImplementedError:
        st.info(
            "Detectors are task 004 — not built yet. The pricing above is live; "
            "this panel fills in once `core/detectors.py` is implemented."
        )
        return []

    if not findings:
        st.success("No findings above the detection thresholds.")
        return []

    st.dataframe(pd.DataFrame([{
        "OZ": f.item.key(),
        "Position": f.item.short_text[:60],
        "Detector": f.detector,
        "Severity": f.severity,
        "€ leverage": round(f.euro_leverage, 2),
        "Why": f.rationale,
    } for f in findings]), width="stretch", hide_index=True)
    return findings


def section_reveal(priced, answer, source_label):
    """The reveal. PLAN.md step 4 — this is the whole pitch."""
    st.subheader("5 · How wrong are we?")

    if answer is None:
        st.caption(
            "This tender has no submitted bid to check against. Load the sample "
            "tender to see the comparison that does."
        )
        return

    reveal.render(priced, answer, source_label)


def answer_key_for(label: str):
    """Find a real submitted bid to measure this tender against.

    Two cases exist. The demo blank has a known sibling bid for the same BoQ.
    A file the user uploads may itself be priced (.D84/.D86), in which case it
    is its own answer key — and must then be held out of the benchmark, or we
    would be checking our homework against our own source.
    """
    if label.startswith(os.path.basename(SAMPLE)):
        raw, _ = load_from_disk(ANSWER_KEY)
        return rehydrate(raw), os.path.basename(ANSWER_KEY), os.path.basename(ANSWER_KEY)

    for source in constants_sources():
        if label.startswith(os.path.basename(source)):
            raw, _ = load_from_disk(source)
            return rehydrate(raw), os.path.basename(source), os.path.basename(source)
    return None, "", ""


def constants_sources() -> list[str]:
    """The bids the benchmark was built from, per reference_prices.json."""
    return load_reference().get("meta", {}).get("sources", [])


def section_export(findings):
    """Bieterfragen-Katalog download. Lights up when task 006 lands."""
    st.subheader("6 · The letter")
    try:
        import export_rfi
        catalog = export_rfi.build_catalog(findings, {"title": "Bieterfragen"})
        st.download_button(
            "Export clarification letter (.docx)",
            data=export_rfi.to_markdown(catalog, {"title": "Bieterfragen"}),
            file_name="Bieterfragen-Katalog.docx",
        )
    except NotImplementedError:
        st.button("Export clarification letter (.docx)", disabled=True)
        st.caption("The RFI export is task 006 — not built yet.")


def main():
    st.title("Bid & Risk Assistant")
    st.write(ONE_SENTENCE)

    company = sidebar_company()
    reference = load_reference()
    if reference.get("meta", {}).get("missing"):
        st.warning(
            "No benchmark found — run `python3 scripts/build_reference_prices.py`. "
            "Until then every position falls back to a hand-authored rate."
        )

    loaded = section_upload()
    if not loaded:
        return
    items, remarks, label = loaded

    # Resolve the answer key BEFORE pricing. If this tender's bid is one of the
    # bids the benchmark was built from, it has to come out of the benchmark
    # for every number on the page — not just the comparison. Pricing with the
    # full benchmark and then claiming the answer was held out is the most
    # flattering thing this app could do, and it would be a lie worth €251k.
    answer, source_label, held_out = answer_key_for(label)
    if held_out:
        reference = pricer.without_source(reference, held_out)
        st.caption(
            f"**{held_out} is held out of the benchmark below.** It is one of "
            "the bids the benchmark is built from, so leaving it in would mean "
            "pricing this tender partly with its own answer."
        )

    section_items(items)
    priced, _ = section_pricing(items, company, reference)
    findings = section_findings(priced, remarks)
    section_reveal(priced, answer, source_label)
    section_export(findings)


main()
