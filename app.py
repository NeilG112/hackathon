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

from core import (classify, constants, detectors, kalkulation, logic, objects,
                  parser_gaeb90, parser_x83, pricer, stammdaten)
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

def sidebar_kalkulation() -> stammdaten.Company:
    """The cost base the bottom-up calculation uses.

    These are the parameters the client said a contractor must bring himself:
    *"Maschinenstundensätze hast du aus der Firma gegeben"*. Presets come from
    the bidder profiles in the test database.
    """
    st.sidebar.header("Kalkulationsgrundlage")
    presets = stammdaten.companies()
    names = [c.name for c in presets]
    chosen = presets[names.index(st.sidebar.selectbox("Profil", names))]

    wage = st.sidebar.slider("Mittellohn (€/h)", 35.0, 95.0,
                             float(chosen.mittellohn_eur_h), 0.5)
    markup = st.sidebar.slider("Zuschlag AGK+BGK+W&G (%)", 0.0, 45.0,
                               float(chosen.zuschlag_pct), 0.5)
    perf = st.sidebar.slider("Leistungsfaktor", 0.6, 1.6,
                             float(chosen.leistungsfaktor), 0.05,
                             help=">1 = slower than the standard times")
    mat = st.sidebar.slider("Materialfaktor", 0.6, 1.6,
                            float(chosen.materialfaktor), 0.05)
    if chosen.profil:
        st.sidebar.caption(chosen.profil)
    return stammdaten.Company(chosen.name, wage, markup, perf, mat, chosen.profil)


def sidebar_company() -> dict:
    """Legacy comparable-pricing sliders (cross-check engine only)."""
    st.sidebar.header("Vergleichspreise (Quercheck)")
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


def section_objects(items, priced):
    """The object table and the project roll-up. Returns the table rows."""
    st.subheader("3 · What the project is made of")
    rows = objects.build(items, priced)
    cov = objects.coverage(rows)

    st.caption(
        f"{cov['positions']} positions grouped into {cov['rows']} "
        f"(section × object × unit) cells. **{cov['tagged_pct']}% of positions "
        f"were classified**; {cov['unknown']} are “unklar” and are excluded "
        "from every cross-position check — a wrong tag would produce a "
        "confident false finding, which is worse than no finding."
    )

    left, right = st.columns(2)
    with left:
        st.markdown("**Project roll-up** — the manual-summing job")
        st.dataframe(pd.DataFrame([{
            "Objekt": r.obj, "Menge": round(r.quantity, 1), "Einheit": r.unit,
            "Positionen": len(r.positions),
        } for r in objects.rollup(rows) if r.obj != objects.UNKNOWN_TAG][:14]),
            width="stretch", hide_index=True, height=300)
    with right:
        st.markdown("**By section** — the key the logic checks use")
        st.dataframe(pd.DataFrame([{
            "Abschnitt": r.location[:38], "Objekt": r.obj,
            "Menge": round(r.quantity, 1), "Einheit": r.unit,
            "Pos.": len(r.positions),
        } for r in rows if r.obj != objects.UNKNOWN_TAG][:14]),
            width="stretch", hide_index=True, height=300)
    return rows


def section_logic(rows, items):
    """Cross-position contradictions."""
    st.subheader("4 · Does the tender contradict itself?")
    st.caption(
        "Checks that only exist between positions: containment (heated floor "
        "area cannot exceed the slab), order-of-magnitude quantity outliers "
        "(the misplaced zero), and repeated positions. All deterministic — "
        "same tender, same findings, every run."
    )
    found = logic.run_all(rows, items)
    if not found:
        st.success(
            "No cross-position contradictions found. That is a real result, "
            "not a placeholder — on this tender the containment rules have no "
            "matching pairs to test."
        )
        return []
    st.dataframe(pd.DataFrame([{
        "OZ": f.item.key(), "Schwere": f.severity,
        "€ exposure": round(f.euro_leverage, 2), "Befund": f.rationale,
    } for f in found]), width="stretch", hide_index=True)
    return found


def section_kalkulation(items, company, data):
    """Bottom-up Aufschlagskalkulation — the bid. Returns calculated items."""
    st.subheader("5 · Das Angebot")

    assignments = classify.classify(items, data, use_jev=False)
    cov = classify.coverage(assignments)
    calculated = kalkulation.calculate(items, assignments, company, data)
    stats = kalkulation.summarize(calculated)

    a, b, c, d = st.columns(4)
    a.metric("Angebotssumme", f"€{stats['total_mid']:,.0f}",
             help="Mittelwert der Spanne")
    b.metric("Spanne", f"€{stats['total_low']:,.0f} – {stats['total_high']:,.0f}")
    c.metric("Kalkuliert", f"{stats['coverage_pct']:.0f}%",
             help=f"{stats['unpriced']} Positionen ohne zugeordnete Leistung")
    d.metric("davon Lohn", f"€{stats['labour_eur']:,.0f}")

    if cov["pct"] < 50:
        st.error(
            f"**Nur {cov['pct']}% der Positionen konnten einer Leistung "
            f"zugeordnet werden.** Der Katalog hat "
            f"{len(data.leistungen)} Einträge; dieses LV beschreibt Arbeiten, "
            "die darin nicht vorkommen. Die Summe oben deckt deshalb nur einen "
            "Teil des Leistungsverzeichnisses ab — sie ist kein vollständiges "
            "Angebot. Ein größerer Katalog oder ein semantischer Klassifikator "
            "behebt das; Stichwortabgleich reicht hier nicht."
        )
    if data.is_synthetic:
        st.caption(
            "⚠️ Die Stammdaten sind **synthetisch** (eigene Schätzungen in "
            "ARH-Größenordnung, keine Marktabfrage). Das Verfahren ist echt, "
            "die Zahlen sind Platzhalter, bis echte Firmenwerte hinterlegt sind."
        )

    st.dataframe(pd.DataFrame([{
        "OZ": c.item.key(),
        "Position": c.item.short_text[:52],
        "Menge": c.item.quantity,
        "Einheit": constants.normalize_unit(c.item.unit),
        "Leistung": c.leistung.code if c.leistung else "—",
        "EP min": c.ep_low, "EP mittel": c.ep_mid, "EP max": c.ep_high,
        "GP": c.total,
        "Grundlage": c.note[:60],
    } for c in calculated]), width="stretch", hide_index=True, height=320)
    return calculated


def section_tricky(calculated):
    """Positions nobody can price confidently from what is written."""
    st.subheader("6 · Heikle Positionen")
    st.caption(
        "The estimator's ask: *“who can tell how much this costs? Is it 50,000 "
        "or 200,000? If a system hints that this position is tricky, that is "
        "an advantage.”* Three signals: no Leistung could be assigned, the "
        "standard times themselves disagree widely, or the position is a lump "
        "sum with no measurable quantity."
    )
    rows = []
    for c in calculated:
        reasons = []
        if not c.priced:
            reasons.append("keine Leistung zuordenbar")
        elif c.band_width > 0.35:
            reasons.append(f"Spanne ±{100*c.band_width/2:.0f}%")
        if c.item.is_lump_sum:
            reasons.append("Pauschalposition")
        if reasons:
            rows.append({
                "OZ": c.item.key(), "Position": c.item.short_text[:58],
                "Menge": c.item.quantity,
                "Einheit": constants.normalize_unit(c.item.unit),
                "€ unsicher": round(c.euro_at_stake, 2),
                "Grund": ", ".join(reasons),
            })
    if not rows:
        st.success("Keine auffällig unsicheren Positionen.")
        return
    frame = pd.DataFrame(rows).sort_values("€ unsicher", ascending=False)
    st.markdown(f"**{len(frame)} Positionen** brauchen einen Menschen.")
    st.dataframe(frame.head(25), width="stretch", hide_index=True)


def section_pricing(items, company, reference):
    """Comparable-price cross-check. Secondary to the calculation above."""
    st.subheader("7 · Quercheck gegen echte Angebotspreise")
    st.caption(
        "A second, independent estimate from 720 unit prices in three real "
        "submitted bids. Where the two engines agree, confidence is higher; "
        "where they diverge, look. Measured on its own (answer key held out) "
        "this engine is −50% on the total, so it is a cross-check, not a bid."
    )
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
    st.subheader(f"8 · Top {constants.TOP_N_FINDINGS} positions worth arguing about")
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
    st.subheader("9 · How wrong are we?")

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
    st.subheader("10 · The letter")
    if not findings:
        st.button("Export clarification letter (.docx)", disabled=True)
        st.caption("No findings are available for export.")
        return

    import export_rfi
    project = {"title": "Bieterfragen-Katalog"}
    catalog = export_rfi.build_catalog(findings, project)
    if not catalog:
        st.button("Export clarification letter (.docx)", disabled=True)
        st.caption("No findings are available for export.")
        return

    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
            out_path = handle.name
        export_rfi.to_docx(catalog, out_path, project)
        with open(out_path, "rb") as handle:
            payload = handle.read()
        os.unlink(out_path)
        st.download_button(
            "Export clarification letter (.docx)",
            data=payload,
            file_name="Bieterfragen-Katalog.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as exc:
        fallback = export_rfi.to_markdown(catalog, project).encode("utf-8")
        st.warning("DOCX export is unavailable; the Markdown fallback is ready.")
        st.download_button(
            "Export clarification letter (.md)",
            data=fallback,
            file_name="Bieterfragen-Katalog.md",
            mime="text/markdown",
        )
        with st.expander("Export details"):
            st.code(str(exc))


def main():
    st.title("Bid & Risk Assistant")
    st.write(ONE_SENTENCE)

    kalk_company = sidebar_kalkulation()
    data = stammdaten.load()
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
    priced = pricer.price_boq(items, reference, company)
    rows = section_objects(items, priced)
    section_logic(rows, items)
    calculated = section_kalkulation(items, kalk_company, data)
    section_tricky(calculated)
    priced, _ = section_pricing(items, company, reference)
    findings = section_findings(priced, remarks)
    section_reveal(priced, answer, source_label)
    section_export(findings)


main()
