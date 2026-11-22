"""Position text -> Leistung code. The one job a model is actually good at.

The pricing engine needs to know *what kind of work* a position describes; the
rate table then supplies the hours and the money. Splitting it this way is
deliberate and it is what makes the system defensible:

    classify (hard, fuzzy, language)   -> a model
    price    (easy, exact, arithmetic) -> a lookup

A model asked "how many hours does this take?" produces a plausible number
nobody can check. A model asked "is this Oberboden abtragen or Rohrgraben
aushaeben?" produces an answer that is right or wrong, measurably, against the
106 labelled positions in `Database/`. And because the price then comes from a
table, the same tender always yields the same bid.

Three backends behind one interface:

    cache    on-disk, keyed by text+unit. Checked first, always.
    jev      TypeSafe's classifier: structured label + confidence, cheap.
    keyword  deterministic token overlap. No network, no key, no cost.

`classify()` walks them in that order, so a cold run with no key still works
and a warm run costs nothing. **Pre-generate the cache and commit it** — a
live API call during a demo is a failure mode with no upside.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from core.models import NormalizedItem
from core.stammdaten import Leistung, Stammdaten


def constants_normalize(unit: str) -> str:
    from core import constants
    return constants.normalize_unit(unit)

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "classification_cache.json",
)

MIN_KEYWORD_SCORE = 0.12     # below this the keyword match is noise
MIN_JEV_CONFIDENCE = 0.35    # below this we would rather say nothing

_STOP = frozenset("""
und oder mit ohne nach vor bis je der die das den dem des ein eine einer
liefern lieferung einbauen herstellen inkl incl einschl gemaess gemäß
""".split())


@dataclass
class Assignment:
    code: Optional[str]
    confidence: float
    source: str          # "cache" | "jev" | "keyword" | "none"
    alternatives: list = None

    def as_tuple(self) -> tuple[Optional[str], float]:
        return (self.code, self.confidence)


# --- shared helpers --------------------------------------------------------

def tokens(text: str) -> frozenset[str]:
    low = re.sub(r"\[?\b(?:person|firma|ort|projekt|nummer|telefon|per)[_0-9]*\]?",
                 " ", (text or "").lower())
    return frozenset(t for t in re.findall(r"[a-zäöüß]{4,}", low) if t not in _STOP)


def fingerprint(item: NormalizedItem, unit: str) -> str:
    """Cache key: the text and unit decide the class, nothing else does."""
    raw = f"{item.short_text}|{item.long_text[:400]}|{unit}".lower()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def candidates(unit: str, data: Stammdaten) -> list[Leistung]:
    """Work types measured in this unit — everything else is impossible.

    The unit is the single strongest signal in a bill of quantities and it is
    free. Restricting to it before any fuzzy matching removes most of the ways
    a classifier can be confidently wrong.
    """
    shortlist = data.by_unit(unit)
    return shortlist or list(data.leistungen.values())


# --- backend: keyword ------------------------------------------------------

def classify_keyword(item: NormalizedItem, data: Stammdaten, unit: str) -> Assignment:
    """Token overlap against each candidate's Taetigkeit and Bemerkung.

    The deterministic floor. It has no domain knowledge and will never beat a
    real classifier, but it costs nothing, runs offline, and makes the whole
    system work with no API key at all.
    """
    item_tokens = tokens(f"{item.short_text} {item.long_text[:400]}")
    if not item_tokens:
        return Assignment(None, 0.0, "none")

    scored = []
    for leistung in candidates(unit, data):
        ref = tokens(f"{leistung.taetigkeit} {leistung.bemerkung} {leistung.gewerk}")
        if not ref:
            continue
        overlap = len(item_tokens & ref)
        if not overlap:
            continue
        scored.append((overlap / len(item_tokens | ref), leistung.code))

    if not scored:
        return Assignment(None, 0.0, "none")
    scored.sort(reverse=True)
    best_score, best_code = scored[0]
    if best_score < MIN_KEYWORD_SCORE:
        return Assignment(None, round(best_score, 3), "none",
                          [c for _, c in scored[:3]])
    return Assignment(best_code, round(best_score, 3), "keyword",
                      [c for _, c in scored[:3]])


# --- backend: Jev ----------------------------------------------------------

def _load_env_once() -> None:
    """Read `.env` into the environment if the key is not already set.

    Streamlit does not load `.env`, so without this the app silently has no
    API key, falls back to keyword matching and reports ~3% coverage on any
    file that is not already cached. Stdlib only — no python-dotenv.
    """
    if os.getenv("JEV_KEY") or os.getenv("JEV_API_KEY"):
        return
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip())
    except OSError:
        pass


def jev_available() -> bool:
    _load_env_once()
    return bool(os.getenv("JEV_KEY") or os.getenv("JEV_API_KEY"))


JEV_URL = os.getenv("JEV_URL", "https://api.typesafe.ai/v1/systemone")
JEV_MODEL = os.getenv("JEV_MODEL", "jev-latest")
# The decision rule, measured against representative and negative cases.
# Probed on real positions plus two deliberate negatives ("Teppichboden
# verlegen", "Dachabdichtung aufschweißen" — trades absent from this
# catalogue). Both negatives scored noul<=0.07 AND option probability <=0.35;
# genuine matches scored 0.62-0.99 on the option. So:
#
#     accept if  p >= 0.60                      (the option is clearly right)
#            or  p >= 0.45 and noul >= 0.60     (plausible and the catalogue
#                                                does contain this kind of work)
#
# `confidence` is deliberately unused: it measures how peaked the distribution
# is, not how likely the answer is to be correct.
# Jev rejects a Choice with too many options: 200 is accepted, 400 returns
# HTTP 422. The catalogue grew from 124 to 939 Leistungen, which silently
# broke every uncached classification — the demo tender only kept working
# because its answers were already on disk. Shortlist before sending.
MAX_JEV_OPTIONS = 180

STRONG_OPTION_PROB = 0.60
WEAK_OPTION_PROB = 0.45
MIN_MATCH_NOUL = 0.60


class JevError(RuntimeError):
    """A failed call is an error, never an answer.

    Treating an outage as "no match" would silently drop positions out of the
    bid and look like a clean result. The caller decides whether to fall back
    to the keyword backend; this layer does not decide for it.
    """


def _slug(text: str) -> str:
    """Descriptive option name. Jev sees these, so they carry meaning.

    Positional names (`option_1`) give the model nothing to reason about, and
    the Leistung codes (`E01`) are equally meaningless to it. The activity
    text is what a person would read.
    """
    base = re.sub(r"[^a-zäöüß0-9]+", "_", (text or "").lower()).strip("_")
    return base[:60] or "unbenannt"


def classify_jev(
    item: NormalizedItem,
    data: Stammdaten,
    unit: str,
    timeout: float = 30.0,
) -> Assignment:
    """Ask Jev which Leistung this position describes.

    Two questions in one request, sharing one state:

      `passt`     a Noul — does the catalogue contain this work at all?
      `leistung`  a Choice — which entry, given that it does

    The Noul is not optional. A Choice *always* returns an option, even when
    nothing fits, so without a companion Noul every unrelated position would
    be confidently assigned a wrong Leistung and silently mis-priced. The
    catalogue has 34 entries and a real tender contains work that is simply
    not in it, so "none of these" is the common case, not the edge case.

    Code, not the model, decides what to do with the two judgments.
    """
    import urllib.request

    key = os.getenv("JEV_KEY") or os.getenv("JEV_API_KEY")
    if not key:
        raise JevError("JEV_KEY is not set")

    # The whole catalogue, not the unit shortlist. Measured: restricting by
    # unit HIDES the right answer — "Sanitärcontainer aufstellen" is billed in
    # St but belongs to Baustelleneinrichtung (psch), so the unit shortlist
    # forced a wrong pick at p=0.71 while the full catalogue found it at 0.99.
    # Worse, a unit with one candidate makes the Choice degenerate: it must
    # return that option at p=1.00 regardless of the text.
    shortlist = list(data.leistungen.values())
    if not shortlist:
        return Assignment(None, 0.0, "none")

    if len(shortlist) > MAX_JEV_OPTIONS:
        # Pre-rank with the free keyword scorer and send only the plausible
        # candidates. Positions billed in the same unit are kept first — the
        # unit is the strongest signal and costs nothing — then the best
        # token-overlap matches fill the rest. This preserves recall far
        # better than a hard unit filter, which was measured to HIDE the
        # right answer ("Sanitaercontainer" is billed in St but belongs to
        # Baustelleneinrichtung, billed psch).
        item_tokens = tokens(f"{item.short_text} {item.long_text[:400]}")

        def _rank(leistung: Leistung) -> tuple[int, float]:
            same_unit = constants_normalize(leistung.einheit) == unit
            ref = tokens(f"{leistung.taetigkeit} {leistung.gewerk}")
            overlap = (len(item_tokens & ref) / len(item_tokens | ref)
                       if item_tokens and ref else 0.0)
            return (0 if same_unit else 1, -overlap)

        shortlist = sorted(shortlist, key=_rank)[:MAX_JEV_OPTIONS]

    criteria, back = {}, {}
    for leistung in shortlist:
        name = _slug(leistung.taetigkeit)
        while name in back:                       # keep option names unique
            name = f"{name}_{leistung.code.lower()}"
        back[name] = leistung.code
        # Taetigkeit and unit only. The `bemerkung` field averages ~170
        # characters and is sent for all 939 Leistungen on every single call:
        # 44,680 tokens per position, 33 USD on a 9,000-position tender, for
        # prose that describes execution detail the classifier does not need
        # to tell two Leistungen apart.
        criteria[name] = f"{leistung.taetigkeit} [{leistung.einheit}]"

    payload = {
        "model": JEV_MODEL,
        # The catalogue goes in the state because questions are answered
        # independently: the Noul cannot see the Choice's criteria, so without
        # this it has no idea what "the list" is and returned ~0.78 for
        # everything, including work from entirely different trades.
        "state": {
            "position": {
                "kurztext": item.short_text,
                "langtext": (item.long_text or "")[:1000],
                "einheit": unit,
                "menge": item.quantity,
            },
            # The Noul needs to know what "the catalogue" is — it cannot see
            # the Choice's criteria. Trades only, not the full list: naming
            # the 15 Gewerke costs ~60 tokens instead of 11,000 and answers
            # the same question ("is this kind of work in scope at all?").
            "katalog_gewerke": sorted({l.gewerk for l in shortlist if l.gewerk}),
        },
        "questions": {
            "passt": {
                "type": "noul",
                "instructions": (
                    "Lässt sich die Arbeit in `position` mit einer Zeile aus "
                    "`katalog` kalkulieren?"
                ),
                "criteria": {
                    "true": "Eine Katalogzeile beschreibt dieselbe Art von "
                            "Arbeit in derselben Abrechnungseinheit; Material, "
                            "Dimension oder Fabrikat dürfen abweichen.",
                    "false": "Der Katalog enthält keine Zeile für diese Art von "
                             "Arbeit, etwa weil sie zu einem anderen Gewerk "
                             "gehört.",
                },
            },
            "leistung": {
                "type": "choice",
                "instructions": "Welche Leistung beschreibt `position`?",
                "criteria": criteria,
            },
        },
    }

    request = urllib.request.Request(
        JEV_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:                                # noqa: BLE001
        raise JevError(f"{type(exc).__name__}: {exc}") from exc

    answers = body.get("answers", {})
    fits = float(answers.get("passt", {}).get("noul", 0.0))
    choice = answers.get("leistung", {}) or {}
    name = choice.get("choice")
    probabilities = choice.get("probabilities", {}) or {}
    probability = float(probabilities.get(name, 0.0))

    # Code holds the logic. The Noul decides whether anything fits at all; the
    # option's own probability decides whether we know which. `confidence` is
    # deliberately unused — it measures how peaked the distribution is, not
    # how likely the answer is to be right.
    if name not in back:
        return Assignment(None, round(probability, 3), "jev_unsure")
    strong = probability >= STRONG_OPTION_PROB
    plausible = probability >= WEAK_OPTION_PROB and fits >= MIN_MATCH_NOUL
    if not (strong or plausible):
        return Assignment(None, round(probability, 3),
                          "jev_nomatch" if fits < MIN_MATCH_NOUL else "jev_unsure")

    alternatives = sorted(probabilities.items(), key=lambda kv: -kv[1])[:3]
    return Assignment(
        back[name], round(probability, 3), "jev",
        [f"{back.get(n, n)}:{p:.2f}" for n, p in alternatives],
    )


# --- cache -----------------------------------------------------------------

def load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=1, sort_keys=True)


# --- the interface ---------------------------------------------------------

def classify(
    items: Iterable[NormalizedItem],
    data: Stammdaten,
    use_jev: bool | None = None,
    write_cache: bool = True,
    max_workers: int = 8,
) -> dict[str, tuple]:
    """Assign a Leistung code to every position. `{oz_key: (code, confidence)}`.

    `use_jev=None` (the default) means **call Jev for anything not cached, if a
    key is available**. The cache still answers instantly for the demo tender,
    so the prepared path makes no network call — but an arbitrary file a judge
    uploads is not in the cache, and the keyword fallback scores near zero on
    real tender wording. Refusing to call the API there does not make the demo
    safer, it just reports 3% coverage and looks broken.

    Pass `use_jev=False` to force the offline path.
    """
    from concurrent.futures import ThreadPoolExecutor
    from core import constants

    items = list(items)
    cache = load_cache()
    out: dict[str, tuple] = {}
    misses: list[NormalizedItem] = []

    for item in items:
        hit = cache.get(fingerprint(item, constants.normalize_unit(item.unit)))
        if hit:
            out[item.key()] = (hit.get("code"), float(hit.get("confidence", 0.0)))
        else:
            misses.append(item)

    if use_jev is None:
        use_jev = jev_available()

    def resolve(item: NormalizedItem) -> tuple:
        unit = constants.normalize_unit(item.unit)
        if use_jev:
            try:
                assignment = classify_jev(item, data, unit)
            except JevError:
                assignment = classify_keyword(item, data, unit)
            if assignment.code is not None:
                return item, assignment
        return item, classify_keyword(item, data, unit)

    if misses:
        # Parallel because a judge is watching: 248 positions take ~10s at 8
        # workers and over three minutes one at a time.
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            resolved = list(pool.map(resolve, misses))
        for item, assignment in resolved:
            out[item.key()] = assignment.as_tuple()
            cache[fingerprint(item, constants.normalize_unit(item.unit))] = {
                "code": assignment.code,
                "confidence": assignment.confidence,
                "source": assignment.source,
                "text": item.short_text[:90],
            }
        if write_cache:
            save_cache(cache)
    return out


def coverage(assignments: dict) -> dict:
    total = len(assignments)
    hit = sum(1 for code, _ in assignments.values() if code)
    return {"positions": total, "classified": hit,
            "unclassified": total - hit,
            "pct": round(100.0 * hit / total, 1) if total else 0.0}
