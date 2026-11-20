#!/usr/bin/env python3
"""The credibility layer — measured error against a real human bid. Task 005.

PLAN.md calls this the whole pitch. Price the blank BoQ `[NUMMER_001]_leer.X83`
(248 items) and compare against `StBALV23040.D86` (249 priced items, bid total
EUR 897,305.45 — actually submitted by a contractor for the same bill of
quantities).

    python3 validate.py

It reports three numbers, deliberately separated, because conflating them is
how an estimator stops believing the tool:

  1. **Headline gap** — our total vs. the real bid total. Includes the effect
     of positions we refuse to price, so it flatters nothing.
  2. **Like-for-like error** — only the positions we actually priced AND the
     real bid also priced. This is the honest measure of the pricing engine.
  3. **Coverage gap** — what the contractor charged for the positions we
     declined to price. The difference between (1) and (2), explained.

Then the worst-deviating positions, ranked by euro impact rather than by
percentage, because a 400% error on a EUR 12 line is noise and a 25% error on
a EUR 90,000 line is the conversation.

**Joins on `padded_key`, never on list index.** See `NormalizedItem.padded_key`
— a naive key join matches zero of 248 here.
"""

from __future__ import annotations

import sys
from typing import Dict, List

from core import constants, parser_gaeb90, parser_x83, pricer
from core.models import NormalizedItem

BLANK = constants.REVEAL["blank_boq"]
ANSWER_KEY = constants.REVEAL["answer_key"]
ACTUAL_TOTAL = constants.REVEAL["actual_bid_total_eur"]
THRESHOLD = constants.REVEAL["disagreement_threshold_pct"]

# Level widths of the priced file's OZ, to re-pad the blank's unpadded levels.
JOIN_WIDTHS = (2, 2, 4)
MIN_JOIN_RATE = 0.90      # below this the join is broken, not the pricing
TOP_DEVIATIONS = 12


def euro(value: float) -> str:
    return f"{value:>14,.2f}"


def pct(value: float) -> str:
    return f"{value:+.1f}%"


def main() -> int:
    blank: List[NormalizedItem] = parser_x83.parse(BLANK)
    actual: List[NormalizedItem] = parser_gaeb90.parse(ANSWER_KEY)
    reference = pricer.load_reference_prices()

    if reference.get("meta", {}).get("missing"):
        print("no benchmark found — run scripts/build_reference_prices.py first")
        return 1

    # LEAVE-ONE-OUT. The answer key is itself one of the three bids in the
    # benchmark, so pricing this BoQ against the full benchmark means pricing
    # it partly with the very bid we then claim to be measured against. Every
    # number below therefore holds StBALV23040.D86 out. The leaky figure is
    # printed too, once, so the size of the effect is on the record — but the
    # honest number is the one to put on a slide.
    honest = pricer.without_source(reference, ANSWER_KEY)

    priced = pricer.price_boq(blank, honest)
    stats = pricer.summarize(priced)
    leaky = pricer.summarize(pricer.price_boq(blank, reference))

    print(f"tender      {len(blank):>4} positions  {BLANK}")
    print(f"real bid    {len(actual):>4} positions  {ANSWER_KEY}")
    print(f"benchmark   {honest['meta'].get('priced_items', 0):>4} observed prices, "
          f"answer key held out ({len(reference['meta'].get('sources', [])) - 1} "
          "independent bids)")
    print(f"            leave-one-out total {leaky['total'] - stats['total']:+,.2f} "
          "vs. the leaky benchmark")
    print()

    # --- the join ----------------------------------------------------------
    by_key: Dict[str, NormalizedItem] = {i.key(): i for i in actual}
    matched = []
    unmatched = []
    for p in priced:
        key = p.item.padded_key(JOIN_WIDTHS)
        if key in by_key:
            matched.append((key, p, by_key[key]))
        else:
            unmatched.append(key)

    join_rate = len(matched) / len(priced) if priced else 0.0
    print(f"joined      {len(matched):>4}/{len(priced)} positions "
          f"({join_rate:.0%}) on padded OZ")
    if join_rate < MIN_JOIN_RATE:
        print()
        print(f"JOIN BROKEN — only {join_rate:.0%} of positions matched.")
        print("Check NormalizedItem.padded_key and JOIN_WIDTHS before reading")
        print("anything below as a pricing result.")
        return 1

    only_tender = sorted(unmatched)
    only_bid = sorted(set(by_key) - {k for k, _, _ in matched})
    if only_tender:
        print(f"  in tender, not in bid : {', '.join(only_tender)}")
    if only_bid:
        print(f"  in bid, not in tender : {', '.join(only_bid)}  "
              "<- positions added after the tender went out")
    print()

    # --- 1. headline -------------------------------------------------------
    ours_all = stats["total"]
    print("1. HEADLINE")
    print(f"   our estimate, all {len(priced)} positions   {euro(ours_all)}")
    print(f"   real submitted bid                   {euro(ACTUAL_TOTAL)}")
    print(f"   gap                                  {euro(ours_all - ACTUAL_TOTAL)}"
          f"   {pct(100 * (ours_all - ACTUAL_TOTAL) / ACTUAL_TOTAL)}")
    print()

    # --- 2. like-for-like --------------------------------------------------
    comparable = [(k, p, a) for k, p, a in matched
                  if p.total is not None and a.total_price is not None]
    ours_ll = sum(p.total for _, p, _ in comparable)
    theirs_ll = sum(a.total_price for _, _, a in comparable)
    print(f"2. LIKE-FOR-LIKE  ({len(comparable)} positions both sides priced)")
    print(f"   ours                                 {euro(ours_ll)}")
    print(f"   theirs                               {euro(theirs_ll)}")
    if theirs_ll:
        print(f"   error                                {euro(ours_ll - theirs_ll)}"
              f"   {pct(100 * (ours_ll - theirs_ll) / theirs_ll)}")
    print()

    # --- 3. coverage gap ---------------------------------------------------
    declined = [(k, p, a) for k, p, a in matched if p.total is None]
    declined_value = sum(a.total_price or 0.0 for _, _, a in declined)
    print(f"3. COVERAGE GAP  ({len(declined)} positions we declined to price)")
    print(f"   the contractor charged               {euro(declined_value)}")
    if declined:
        units = sorted({constants.normalize_unit(a.unit) for _, _, a in declined})
        print(f"   their units: {', '.join(u or '(none)' for u in units)}")
        print(f"   -> {constants.NO_COMPARABLE_LABEL}: no same-unit comparables exist "
              "in the benchmark")
    print()

    # --- 4. level-calibrated -----------------------------------------------
    # A benchmark from other projects gets the *shape* of a price list right
    # and its *level* wrong: site conditions, haulage, competitive pressure and
    # programme move every rate at once. Fitting one scalar separates "we are
    # cheaper than this contractor across the board" from "we disagree about
    # this position", and only the second is a finding worth exporting.
    calib = pricer.implied_cost_base(
        [p for _, p, _ in comparable], theirs_ll
    )
    multiplier = calib["multiplier"] or 1.0
    print("4. LEVEL-CALIBRATED  (one scalar fitted to their price level)")
    print(f"   implied multiplier                   {multiplier:>14,.2f}x")
    print(f"   implied Mittellohn                   "
          f"{calib['implied_mittellohn_eur_h']:>14,.2f} EUR/h   "
          f"(ours: {constants.DEFAULT_COMPANY['mittellohn_eur_h']:,.2f})")

    residuals = []
    for key, p, a in comparable:
        if not a.unit_price:
            continue
        scaled = p.unit_price * multiplier
        delta_pct = 100.0 * (scaled - a.unit_price) / a.unit_price
        impact = abs(scaled * a.quantity - (a.total_price or 0.0))
        residuals.append((impact, delta_pct, key, p, a, scaled))
    residuals.sort(reverse=True)

    within = [r for r in residuals if abs(r[1]) <= THRESHOLD]
    median_abs = sorted(abs(r[1]) for r in residuals)
    print(f"   within +/-{THRESHOLD:.0f}% after calibration     "
          f"{len(within):>4}/{len(residuals)} positions "
          f"({100 * len(within) / len(residuals):.0f}%)")
    if median_abs:
        print(f"   median absolute error                "
              f"{median_abs[len(median_abs) // 2]:>13,.0f}%")
    print()

    # --- worst deviations, after calibration -------------------------------
    print(f"{len(residuals) - len(within)} positions still disagree by more than "
          f"{THRESHOLD:.0f}% once the price level is matched.")
    print(f"these are the findings worth arguing about — worst "
          f"{min(TOP_DEVIATIONS, len(residuals))} by euro impact:")
    print(f"   {'OZ':<10} {'qty':>9} {'unit':<5} {'ours*':>10} {'theirs':>10} "
          f"{'delta':>8} {'impact':>12}  item")
    for impact, delta_pct, key, p, a, scaled in residuals[:TOP_DEVIATIONS]:
        text = (a.short_text or p.item.short_text or "")[:34]
        print(f"   {key:<10} {a.quantity:>9,.2f} "
              f"{constants.normalize_unit(a.unit):<5} "
              f"{scaled:>10,.2f} {a.unit_price:>10,.2f} "
              f"{delta_pct:>7.0f}% {impact:>12,.2f}  {text}")
    print("   (* ours, level-calibrated)")
    print()

    # --- coverage ----------------------------------------------------------
    print(f"coverage    {stats['benchmark_share_pct']:.0f}% of positions priced from "
          f"observed bids, {stats['no_comparable']} declined, "
          f"{euro(stats['fallback_value']).strip()} on fallback rates")

    if median_abs and median_abs[len(median_abs) // 2] > 60.0:
        print()
        print("median calibrated error above 60% — the benchmark buckets are not "
              "discriminating. Tune core/constants.py BUCKET_KEYWORDS now, "
              "before the UI exists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
