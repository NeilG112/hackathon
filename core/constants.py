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

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    "m²": "m2", "cm²": "cm2", "mm²": "mm2", "dm²": "dm2",
    "qm": "m2", "m³": "m3", "cm³": "cm3", "mm³": "mm3",
    "dm³": "dm3", "cbm": "m3",
    "stck": "st", "stk": "st", "stück": "st",
    "std": "h", "to": "t", "pausch": "psch",
    # Mixed-encoding repair. These files are cp850 (the umlauts decode
    # correctly) but whatever wrote them emitted the superscripts as latin-1:
    # byte 0xB2 is '²' in latin-1 and '▓' in cp850, 0xB3 is '³' vs '│'. So 50
    # of the 720 priced items arrive as "m▓"/"m│" and would otherwise form
    # their own bogus unit buckets, splitting every area/volume benchmark.
    "m▓": "m2", "m│": "m3",
}

# Units that measure *time-on-site* rather than work done (vorhalten / hire).
# Their unit prices are per-week or per-day and are not comparable with the
# same nominal unit used for installation work.
TIME_RENTAL_UNITS = {"wo", "stwo", "mwo", "m2d", "md", "d", "mt", "jahr"}


def normalize_unit(raw: str) -> str:
    """Canonical unit key: trimmed, lowercased, aliases and encoding repaired."""
    unit = (raw or "").strip().lower()
    return UNIT_ALIASES.get(unit, unit)


# --- Keyword buckets ------------------------------------------------------
# The join dimension for benchmarking, alongside unit. Crude and legible on
# purpose — this gets read out loud in the demo. First match wins, so order
# matters: more specific terms before generic ones. Derived from the actual
# vocabulary of the 720 priced items, not invented.
BUCKET_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("armatur",      ("absperrschieber", "schieber", "kugelhahn", "flansch",
                      "blindflansch", "hydrant", "armatur")),
    ("formteil",     ("bogen", "muffe", "abgang", "reduzierung", "übergang",
                      "formteil", "anschweiss")),
    ("rohr",         ("rohr", "leitung", "ltg", "dn/od", "verlegen")),
    ("schacht",      ("schacht", "sohle", "sohlen", "abdeckung")),
    ("verbau",       ("verbau", "grabenverbau", "spundwand", "aussteifung")),
    ("erdarbeiten",  ("graben", "boden", "aushub", "verfüllen", "verdichten",
                      "erde", "fördern", "lösen", "planum")),
    ("strasse",      ("asphalt", "pflaster", "fahrbahn", "bordstein", "decke",
                      "tragschicht", "strasse", "straße")),
    ("absicherung",  ("bauzaun", "warnleuchte", "schutzwand", "laufsteg",
                      "absperrung", "sichern", "beschilderung", "absicherung")),
    ("baustelle",    ("baustelleneinrichtung", "standplatz", "vorhalten",
                      "umsetzen", "aufbauen", "abbauen", "räumen")),
    ("dokumentation", ("dokumentation", "foto", "bestandsplan", "aufmass",
                       "aufmaß", "nachweis")),
    ("stundenlohn",  ("stundenlohn", "facharbeiter", "helfer", "vorarbeiter")),
)
BUCKET_FALLBACK = "sonstiges"


def bucket_for_text(text: str) -> str:
    """First matching keyword bucket. Order in BUCKET_KEYWORDS decides ties.

    Lives here, not in the builder script, because the benchmark builder and
    the pricer MUST bucket identically — if they drift, every lookup misses and
    the pricer silently falls through to its fallback rates.
    """
    low = (text or "").lower()
    for bucket, keywords in BUCKET_KEYWORDS:
        if any(k in low for k in keywords):
            return bucket
    return BUCKET_FALLBACK


# --- Company -> price model ------------------------------------------------
# How the sliders move an observed market price. A benchmark median already
# embeds *that* contractor's wage, overhead and margin, so the sliders express
# a ratio against DEFAULT_COMPANY, not an absolute build-up. At
# DEFAULT_COMPANY the multiplier is exactly 1.0 — the baseline estimate is the
# raw benchmark, which is what makes the reveal's error number meaningful.
PRICING_MODEL = {
    "labour_share": 0.35,   # share of a typical Tiefbau rate that is wage
    "risk_span": 0.10,      # +/- swing from the pricing-aggression slider
}

# --- Detector 1: unit-price outlier ----------------------------------------
# Two modes, because the input decides what is detectable:
#
#   priced file (a bid)   -> observed EP vs. the market -> speculative pricing
#   blank tender          -> no EP exists to test. Comparing our own estimate
#                            against the distribution it was drawn from is
#                            circular: 228 of the demo file's 248 estimates
#                            ARE their benchmark median. So on a blank tender
#                            the detectable risk is market *dispersion* — the
#                            positions where comparable contractors disagree
#                            wildly, so our single number is least trustworthy.
OUTLIER_HIGH_FACTOR = 1.6   # observed EP above median x this -> flag
OUTLIER_LOW_FACTOR = 0.6
DISPERSION_WARN_RATIO = 1.0   # (p75-p25)/median above this = wide market spread

# Severity bands, in euro at stake. Shared by all three detectors so "high"
# means the same thing everywhere in the UI.
SEVERITY_HIGH_EUR = 10_000.0
SEVERITY_MEDIUM_EUR = 2_000.0
MIN_COMPARABLES = 3         # below this, print kein Vergleichswert instead

# Nearest-comparable matching (pricer tier 1). Jaccard overlap on item-text
# content tokens. Measured against validate.py's leave-one-out error, not
# guessed. Swept 0.20-0.50: median absolute error stays 7-9% and 70-78% of
# positions land within 30% across the whole range, so this is a plateau rather
# than a tuned point. Requiring 2+ matches is much worse (median error 25-38%)
# because it pushes items back onto the coarse keyword buckets.
MIN_TEXT_SIMILARITY = 0.30
MIN_TEXT_MATCHES = 1        # how many similar lines before we trust the match
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
# Only rules the data actually supports. Each was measured against the 720
# real priced items: the share is how often that keyword really is measured in
# that unit. A rule below ~70% fires on correctly-priced work more often than
# on errors, which is worse than having no rule.
#
# Kept (measured):      excavation terms are volume; verfüllen 100% of 3
# Dropped (measured):   generic "boden" (82% of 17) is too broad for
#                       Bodenbelag, Bodenplatte, Oberboden and Fußboden.
#                       rohr 38% of 42; leitung 31% of 26; asphalt 33% of 3
#                       schacht, pflaster and aushub have insufficient samples.
#
# `rohr -> m` is the instructive one. It looks obvious and it is wrong: in
# "Kies-Sand-Gemisch Einbettung Rohr DN300-400 verdichten" the pipe is what the
# gravel surrounds, and m3 is the correct basis. The keyword names the subject
# of the position, not how it is measured — only the verb would tell you that.
UNIT_EXPECTED_BY_KEYWORD = {
    "bodenaushub": "m3",
    "erdaushub": "m3",
    "baugrubenaushub": "m3",
    "grabenaushub": "m3",
    "verfüllen": "m3",
}
UNIT_RULE_MIN_SUPPORT = 0.70   # the bar a rule must clear to be worth keeping

# --- Ranking / display ----------------------------------------------------
TOP_N_FINDINGS = 20         # PLAN.md: top 15-25 by euro leverage
SEVERITY_ORDER = ("high", "medium", "low")

# --- Hybrid risk and logic pipeline ---------------------------------------
HYBRID_MAX_LLM_ITEMS = 60
HYBRID_EXPOSURE_PERCENTILE = 0.90
HYBRID_HIGH_SCORE_THRESH = 0.70
HYBRID_MED_SCORE_THRESH = 0.50

# Divergence is meaningful only when the benchmark engine found a high-
# similarity tier-1 comparable and the bottom-up calculation also succeeded.
HYBRID_DIVERGENCE_THRESH = 0.40
HYBRID_MIN_BENCHMARK_SIMILARITY = 0.60

SPECIALIST_KEYWORDS: tuple[str, ...] = (
    "bauseits",
    "nach vorgabe",
    "komplettanlage",
    "komplett",
    "raumsystem",
    "pauschal",
    "nach aufwand",
    "o.ä.",
    "o. ä.",
    "ggf.",
    "wie angeordnet",
    "audio",
    "medientechnik",
    "sonderkonstruktion",
    "nach beigefügter zeichnung",
    "nach wahl des auftraggebers",
)

EVENTUAL_KEYWORDS: tuple[str, ...] = (
    "eventual",
    "bedarfsposition",
    "alternativ",
    "wahlposition",
    "nur auf anordnung",
)

BLACKBOX_KEYWORDS: tuple[str, ...] = (
    "anlage",
    "system",
    "komplett",
    "sonder",
    "bauwerk",
    "schacht",
    "steuerung",
    "technik",
)

# --- Validation comparison data -------------------------------------------
REVEAL = {
    "blank_boq": "Dataset/[NUMMER_001]_leer.X83",
    "answer_key": "Dataset/StBALV23040.D86",
    "actual_bid_total_eur": 897_305.45,
    "disagreement_threshold_pct": 30.0,
}

GOLDEN_DIR = os.path.join(PROJECT_ROOT, "data", "golden")
REFERENCE_PRICES = os.path.join(PROJECT_ROOT, "data", "reference_prices.json")

# --- Vergabe (make-or-buy) ----------------------------------------------------
NU_TYPISCHE_GEWERKE = frozenset({"Prüfung", "Landschaftsbau"})
