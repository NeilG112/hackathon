"""Tunables, inline. No JSON, no load path, no KeyError on stage.

PLAN.md is explicit about this: anything the demo depends on lives in Python
here, so a missing file cannot take the app down mid-presentation. The only
file-loaded data is `data/reference_prices.json` (built from real priced files),
and the pricer must degrade to `kein Vergleichswert` if it is absent.

Rates below are **fallback** values, used only where no real comparable exists,
and the UI must label them as such. PLAN.md flags as unverified whether
hand-authored rates are permitted at all — confirm before leaning on them.
"""

from __future__ import annotations

# --- Company cost base (the Streamlit sliders) -----------------------------

DEFAULT_COMPANY = {
    "mittellohn_eur_h": 52.0,   # loaded average wage
    "overhead_pct": 12.0,       # Baustellengemeinkosten
    "profit_pct": 5.0,          # Wagnis und Gewinn
    "risk_appetite": 0.5,       # 0 = defensive pricing, 1 = aggressive
}

SLIDER_RANGES = {
    "mittellohn_eur_h": (35.0, 80.0, 0.5),
    "overhead_pct": (0.0, 30.0, 0.5),
    "profit_pct": (0.0, 20.0, 0.5),
    "risk_appetite": (0.0, 1.0, 0.05),
}

# --- Pricing fallbacks ------------------------------------------------------
# Keyed by GAEB unit. Rough Tiefbau/Straßenbau order of magnitude. TODO(pricer
# owner): sanity-check these against the medians that come out of
# data/reference_prices.json and delete any that the real data covers.
FALLBACK_RATES_BY_UNIT: dict[str, float] = {
    "m": 45.0,
    "m2": 38.0,
    "m3": 55.0,
    "st": 120.0,
    "stk": 120.0,
    "psch": 1500.0,
    "h": 52.0,
    "t": 90.0,
    "kg": 3.5,
}

UNIT_ALIASES = {
    "m²": "m2", "qm": "m2", "m³": "m3", "cbm": "m3",
    "stck": "st", "stk": "st", "stück": "st",
    "std": "h", "to": "t", "pausch": "psch",
}

# --- Detector 1: unit-price outlier ----------------------------------------
OUTLIER_HIGH_FACTOR = 1.6   # observed EP above median x this -> flag
OUTLIER_LOW_FACTOR = 0.6
MIN_COMPARABLES = 3         # below this, print kein Vergleichswert instead
NO_COMPARABLE_LABEL = "kein Vergleichswert"

# --- Detector 2: vague scope ----------------------------------------------
# Run over <Remark> / Vorbemerkungen text as well as item text — PLAN.md calls
# the 46 Remark blocks the highest-value target for the least work.
VAGUE_SCOPE_TERMS: dict[str, str] = {
    "nach bedarf": "quantity left open to the client",
    "nach wahl des auftraggebers": "client picks the spec after award",
    "erforderlichenfalls": "scope conditional, unpriceable as written",
    "in abstimmung mit": "scope depends on a later agreement",
    "nebenleistung": "pushed into unpaid incidental work",
    "besondere leistung": "may or may not be separately paid",
    "o. ä.": "equivalent product left undefined",
    "oder gleichwertig": "equivalence judged by the client",
    "bauseits": "dependency on the client's own works",
    "evtl": "contingent scope",
    "ggf": "contingent scope",
    "pauschal": "lump sum absorbs quantity risk",
    "stundenlohnarbeiten": "day-work position, quantity unbounded",
}

# --- Detector 3: quantity / unit sanity -----------------------------------
SUSPICIOUS_ROUND_QUANTITIES = (100.0, 500.0, 1000.0, 5000.0, 10000.0)
PROVISIONAL_SHARE_WARN_PCT = 15.0   # Eventualpositionen share of total value
UNIT_EXPECTED_BY_KEYWORD = {
    "rohr": "m",
    "leitung": "m",
    "schacht": "st",
    "asphalt": "m2",
    "pflaster": "m2",
    "boden": "m3",
    "aushub": "m3",
    "verfüllen": "m3",
}

# --- Ranking / display ----------------------------------------------------
TOP_N_FINDINGS = 20         # PLAN.md: top 15-25 by euro leverage
SEVERITY_ORDER = ("high", "medium", "low")

# --- The reveal (PLAN.md step 4, the whole pitch) -------------------------
REVEAL = {
    "blank_boq": "Dataset/[NUMMER_001]_leer.X83",
    "answer_key": "Dataset/StBALV23040.D86",
    "actual_bid_total_eur": 897_305.45,
    "disagreement_threshold_pct": 30.0,
}

GOLDEN_DIR = "data/golden"
REFERENCE_PRICES = "data/reference_prices.json"
