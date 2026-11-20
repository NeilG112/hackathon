"""Bid & Risk Assistant — Streamlit UI. Task 007.

    streamlit run app.py

> It reads a construction tender file, finds the line items that will cost the
> contractor money, and writes the clarification letter he'd otherwise spend
> four hours on.

Lead with that sentence. No vocabulary lesson, no file extensions.

The layout below is the demo script in order: upload -> item table -> company
sliders -> top 20 by euro leverage -> the reveal -> export. The sections are
wired as placeholders so the app always starts; each one lights up as its
module lands. Keep it that way — a UI that renders with holes is demoable, a
UI that crashes on import is not.

Fallback (wire this Saturday, not Sunday): if a live parse fails, load
pre-parsed fixtures from `data/golden/`. If a judge uploads an unsupported
file, say so honestly and offer the sample — degrade visibly rather than
fabricating output.
"""

from __future__ import annotations

import streamlit as st

from core import constants

ONE_SENTENCE = (
    "It reads a construction tender file, finds the line items that will cost "
    "the contractor money, and writes the clarification letter he'd otherwise "
    "spend four hours on."
)

st.set_page_config(page_title="Bid & Risk Assistant", layout="wide")


def sidebar_company() -> dict:
    """Company cost base sliders. Returns the dict the pricer consumes."""
    st.sidebar.header("Your cost base")
    company = {}
    labels = {
        "mittellohn_eur_h": "Average loaded wage (€/h)",
        "overhead_pct": "Site overhead (%)",
        "profit_pct": "Risk & profit (%)",
        "risk_appetite": "Pricing aggression",
    }
    for field, default in constants.DEFAULT_COMPANY.items():
        lo, hi, step = constants.SLIDER_RANGES[field]
        company[field] = st.sidebar.slider(
            labels.get(field, field), float(lo), float(hi), float(default), float(step)
        )
    return company


def section_upload():
    """Upload -> parse -> item count. TODO(task 007): wire the parsers."""
    st.subheader("1 · The tender")
    st.file_uploader(
        "Drop a tender file", type=["x83", "X83", "d83", "D83", "d84", "D84", "d86", "D86"]
    )
    st.button("Use the sample tender", help=constants.REVEAL["blank_boq"])
    st.info("Parsing not wired yet — task 001 (parsers) then task 007 (this view).")


def section_items():
    """The parsed bill of quantities, as a table. TODO(task 007)."""
    st.subheader("2 · What's in it")
    st.empty()


def section_findings(company: dict):
    """Top N findings by € leverage, each with a rationale. TODO(task 007)."""
    st.subheader(f"3 · Top {constants.TOP_N_FINDINGS} positions worth arguing about")
    st.caption(
        "Ranked by € leverage (quantity × price exposure). Where no comparable "
        f"exists we print “{constants.NO_COMPARABLE_LABEL}” rather than invent a number."
    )
    st.empty()


def section_reveal():
    """The reveal. PLAN.md step 4 — this is the whole pitch. TODO(task 007)."""
    st.subheader("4 · How wrong are we?")
    st.caption(
        "A real contractor submitted "
        f"€{constants.REVEAL['actual_bid_total_eur']:,.2f} for this exact bill of "
        "quantities. Our error against that bid, and the positions where we "
        f"disagree by more than {constants.REVEAL['disagreement_threshold_pct']:.0f}%."
    )
    st.empty()


def section_export():
    """Bieterfragen-Katalog download. TODO(task 007 + task 006)."""
    st.subheader("5 · The letter")
    st.button("Export clarification letter (.docx)", disabled=True)


def main():
    st.title("Bid & Risk Assistant")
    st.write(ONE_SENTENCE)
    company = sidebar_company()
    section_upload()
    section_items()
    section_findings(company)
    section_reveal()
    section_export()


main()
