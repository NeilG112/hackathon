"""The reveal — our estimate measured against a real submitted bid.

PLAN.md step 4: *"We estimated EUR X. A real contractor actually submitted
EUR 897,305.45 for this exact bill of quantities. We're Z% off across 248
positions — and here are the positions where we disagree by more than 30%."*

Owned by person 4. The seam with `app.py` is one function, one direction:

    from views.reveal import render
    render(priced, answer_items, source_label)

`app.py` never reaches into this module's internals; this module never touches
`app.py`'s state. The numbers here are the console output of `validate.py`
rendered for a screen — if you change the maths, change it in `core/pricer.py`
so both agree.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import constants, pricer
from core.models import NormalizedItem

JOIN_WIDTHS = (2, 2, 4)
TOP_DEVIATIONS = 15


def join(priced: list, answer: list[NormalizedItem]) -> list[tuple]:
    """Match our priced positions to the real bid on **padded** OZ.

    Never on list index, and never on the raw key: the blank BoQ stores its
    hierarchy levels unpadded while the priced file pads them, so a naive join
    matches zero of 248. See `NormalizedItem.padded_key`.
    """
    by_key = {i.key(): i for i in answer}
    out = []
    for p in priced:
        actual = by_key.get(p.item.padded_key(JOIN_WIDTHS))
        if actual is not None:
            out.append((p, actual))
    return out


def render(priced: list, answer: list[NormalizedItem], source_label: str) -> None:
    """Draw the comparison. Assumes `answer` carries real unit prices."""
    pairs = join(priced, answer)
    if not pairs:
        st.warning(
            "Could not match these positions to the reference bid. "
            "That is a join problem, not a pricing result — check padded_key()."
        )
        return

    comparable = [(p, a) for p, a in pairs
                  if p.total is not None and a.total_price is not None]
    if not comparable:
        st.info("No position is priced on both sides, so there is nothing to compare.")
        return

    ours = sum(p.total for p, _ in comparable)
    theirs = sum(a.total_price for _, a in comparable)
    error_pct = 100.0 * (ours - theirs) / theirs if theirs else 0.0

    full_bid = sum(a.total_price or 0.0 for a in answer)

    left, middle, right = st.columns(3)
    left.metric("Our estimate", f"€{ours:,.0f}")
    middle.metric("Actually submitted", f"€{theirs:,.0f}", help=source_label)
    right.metric("Difference", f"{error_pct:+.1f}%", f"€{ours - theirs:,.0f}")

    st.caption(
        f"Compared over the **{len(comparable)} positions priced on both sides**, "
        f"out of {len(priced)} in the tender. The full submitted bid is "
        f"€{full_bid:,.2f} across {len(answer)} positions — the difference is the "
        "positions we decline to price, which are listed above rather than guessed. "
        "A real contractor submitted this: the comparison is against a human, not "
        "against our own output."
    )

    # One scalar absorbs the project-level price difference (site conditions,
    # haulage, competitive pressure move every rate at once). What survives it
    # is genuine position-by-position disagreement, which is the finding.
    calib = pricer.implied_cost_base([p for p, _ in comparable], theirs)
    multiplier = calib["multiplier"] or 1.0

    rows = []
    for p, a in comparable:
        if not a.unit_price:
            continue
        scaled = p.unit_price * multiplier
        rows.append({
            "OZ": a.key(),
            "Position": (a.short_text or p.item.short_text or "")[:60],
            "Menge": a.quantity,
            "Einheit": constants.normalize_unit(a.unit),
            "ours €": round(scaled, 2),
            "theirs €": round(a.unit_price, 2),
            "Δ%": round(100.0 * (scaled - a.unit_price) / a.unit_price, 0),
            "€ impact": round(abs(scaled * a.quantity - (a.total_price or 0.0)), 2),
        })

    frame = pd.DataFrame(rows).sort_values("€ impact", ascending=False)
    threshold = constants.REVEAL["disagreement_threshold_pct"]
    disputed = frame[frame["Δ%"].abs() > threshold]

    st.markdown(
        f"**{len(disputed)} of {len(frame)} positions still disagree by more than "
        f"{threshold:.0f}% once the price level is matched.** Those are the ones "
        "worth arguing about."
    )
    st.dataframe(frame.head(TOP_DEVIATIONS), width="stretch", hide_index=True)

    with st.expander("Why scale before comparing?"):
        st.markdown(
            f"""
A benchmark built from *other* projects gets the **shape** of a price list right and
its **level** only roughly — site conditions, haulage distance, programme and
competitive pressure move every rate at once.

Fitting one scalar separates *"we are cheaper than this contractor across the board"*
from *"we disagree about this position"*. Only the second is a finding.

For this bid the fitted scalar is **{multiplier:.2f}×**, which implies a cost base of
**€{calib['implied_mittellohn_eur_h']:,.0f}/h** against our
€{constants.DEFAULT_COMPANY['mittellohn_eur_h']:,.0f}/h.
That number *is* this competitor's implied cost base — drag the wage slider to it and
our total lands on theirs.
"""
        )
