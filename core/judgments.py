"""Selective TypeSafe/Jev judgments for hybrid risk triage.

Jev supplies orthogonal atomic probabilities; application code turns them
into reasons and decisions. This module is cacheable and fails per item rather
than taking down the rest of the pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Sequence

from core import classify, constants
from core.models import AtomicLLMJudgments, HybridItemState, NormalizedItem


JUDGMENT_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "judgment_cache.json",
)


def judgment_fingerprint(
    item: NormalizedItem,
    state: HybridItemState,
) -> str:
    raw = (
        f"{item.short_text}"
        f"|{item.long_text[:600]}"
        f"|{constants.normalize_unit(item.unit)}"
        f"|{round(item.quantity, 3)}"
        f"|{round(state.pre_unit_price, 0)}"
    ).lower()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_judgment_cache() -> dict:
    if not os.path.exists(JUDGMENT_CACHE_PATH):
        return {}
    try:
        with open(JUDGMENT_CACHE_PATH, encoding="utf-8") as fh:
            cache = json.load(fh)
            return cache if isinstance(cache, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_judgment_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(JUDGMENT_CACHE_PATH), exist_ok=True)
    with open(JUDGMENT_CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=1, sort_keys=True)


def _judgment_from_cache(raw: dict) -> AtomicLLMJudgments:
    reasons = raw.get("reasons", {}) if isinstance(raw.get("reasons", {}), dict) else {}
    return AtomicLLMJudgments(
        unklar_beschrieben=float(raw.get("unklar_beschrieben", 0.0)),
        menge_unplausibel=float(raw.get("menge_unplausibel", 0.0)),
        preis_unplausibel=float(raw.get("preis_unplausibel", 0.0)),
        spezialgewerk=float(raw.get("spezialgewerk", 0.0)),
        nachtragspotenzial=float(raw.get("nachtragspotenzial", 0.0)),
        mindermengen_risiko=float(raw.get("mindermengen_risiko", 0.0)),
        reasons=dict(reasons),
    )


def _judgment_to_cache(judgments: AtomicLLMJudgments) -> dict:
    return {
        "unklar_beschrieben": judgments.unklar_beschrieben,
        "menge_unplausibel": judgments.menge_unplausibel,
        "preis_unplausibel": judgments.preis_unplausibel,
        "spezialgewerk": judgments.spezialgewerk,
        "nachtragspotenzial": judgments.nachtragspotenzial,
        "mindermengen_risiko": judgments.mindermengen_risiko,
        "reasons": dict(judgments.reasons),
    }


def _noul_answer(answers: dict, dimension: str) -> float:
    answer = answers.get(dimension, {}) or {}
    try:
        value = float(answer.get("noul", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, value))


def judge_item_jev(
    item: NormalizedItem,
    state: HybridItemState,
    timeout: float = 25.0,
) -> AtomicLLMJudgments:
    classify._load_env_once()
    key = os.getenv("JEV_KEY") or os.getenv("JEV_API_KEY")
    if not key:
        raise classify.JevError("JEV_KEY is not set")

    payload = {
        "model": classify.JEV_MODEL,
        "state": {
            "position": {
                "oz": item.oz,
                "kurztext": item.short_text,
                "langtext": (item.long_text or "")[:1000],
                "menge": item.quantity,
                "einheit": constants.normalize_unit(item.unit),
                "pauschal": bool(item.is_lump_sum),
            },
            "vorkalkulation": {
                "ep_vorl": state.pre_unit_price,
                "gesamt_exposure_eur": state.euro_exposure,
                "preis_quelle": state.price_source,
                "markt_spanne": state.benchmark_band,
                "regel_hinweise": list(state.logic_details),
            },
        },
        "questions": {
            "unklar_beschrieben": {
                "type": "noul",
                "instructions": (
                    "Ist der Leistungsumfang in `position` so mehrdeutig oder "
                    "unvollständig, dass zwei Kalkulatoren zu stark "
                    "unterschiedlichen Preisen kämen?"
                ),
                "criteria": {
                    "true": "Es fehlt eine wesentliche Dimension, Norm, Schnittstelle "
                            "oder Beschreibung, oder es liegt eine Black-Box-Leistung "
                            "mit undefiniertem Umfang vor.",
                    "false": "Der Leistungsumfang ist anhand der Position, der Menge "
                             "und der Abrechnungseinheit ausreichend bestimmbar.",
                },
            },
            "menge_unplausibel": {
                "type": "noul",
                "instructions": (
                    "Wirkt die ausgeschriebene Menge in `position` für die "
                    "beschriebene Bauleistung unplausibel?"
                ),
                "criteria": {
                    "true": "Ein Komma-/Zehnerpotenzfehler, eine unrealistische "
                            "Pauschale oder eine mengenmäßig technisch "
                            "unwahrscheinliche Angabe ist wahrscheinlich.",
                    "false": "Menge und Bauleistung sind mengenmäßig plausibel.",
                },
            },
            "preis_unplausibel": {
                "type": "noul",
                "instructions": (
                    "Weicht der vorkalkulierte EP in "
                    "`vorkalkulation.ep_vorl` unplausibel von der technischen "
                    "Komplexität in `position` oder der Marktspanne in "
                    "`vorkalkulation.markt_spanne` ab?"
                ),
                "criteria": {
                    "true": "Der Vorkalkulationspreis ist gegenüber Komplexität oder "
                            "Marktspanne auffällig zu niedrig oder zu hoch.",
                    "false": "Der Vorkalkulationspreis liegt technisch und gegenüber "
                             "der verfügbaren Marktspanne in einem plausiblen Bereich.",
                },
            },
            "spezialgewerk": {
                "type": "noul",
                "instructions": (
                    "Erfordert die Leistung in `position` ein Spezialgewerk oder "
                    "eine Nachunternehmervergabe?"
                ),
                "criteria": {
                    "true": "Beispiele sind Medientechnik, Spezialtiefbau, "
                            "Leitungsbau-Sonderarmaturen oder Mess-/Regeltechnik.",
                    "false": "Die Leistung ist als übliches Standardgewerk ohne "
                             "besondere Spezialfirma ausführbar.",
                },
            },
            "nachtragspotenzial": {
                "type": "noul",
                "instructions": (
                    "Besteht hohes Risiko, dass die ausgeschriebene Menge nach "
                    "Zuschlag deutlich überschritten wird oder zusätzliche "
                    "Nachträge entstehen?"
                ),
                "criteria": {
                    "true": "Unklare Schnittstellen, Bedarfs-/Eventualanteile oder "
                            "zu geringe Mengen deuten auf Mengenüberschreitung oder "
                            "zusätzliche Nachträge hin.",
                    "false": "Der Umfang ist fest abgegrenzt und ohne erkennbare "
                             "Zusatzleistung oder Mengensteigerung kalkulierbar.",
                },
            },
            "mindermengen_risiko": {
                "type": "noul",
                "instructions": (
                    "Handelt es sich in `position` um eine unwahrscheinliche, "
                    "optionale oder überhöhte Position, die voraussichtlich nicht "
                    "oder deutlich geringer abgerufen wird?"
                ),
                "criteria": {
                    "true": "Die Position ist bedarfs-, eventual-, wahl- oder "
                            "alternativartig oder mengenmäßig auffällig überhöht.",
                    "false": "Die Position ist verbindlich geplant und wahrscheinlich "
                             "vollständig oder weitgehend abzurufen.",
                },
            },
        },
    }

    request = urllib.request.Request(
        classify.JEV_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise classify.JevError(f"{type(exc).__name__}: {exc}") from exc

    answers = body.get("answers", {}) if isinstance(body, dict) else {}
    if not isinstance(answers, dict):
        answers = {}

    values = {
        "unklar_beschrieben": _noul_answer(answers, "unklar_beschrieben"),
        "menge_unplausibel": _noul_answer(answers, "menge_unplausibel"),
        "preis_unplausibel": _noul_answer(answers, "preis_unplausibel"),
        "spezialgewerk": _noul_answer(answers, "spezialgewerk"),
        "nachtragspotenzial": _noul_answer(answers, "nachtragspotenzial"),
        "mindermengen_risiko": _noul_answer(answers, "mindermengen_risiko"),
    }

    reasons: dict[str, str] = {}
    reason_text = {
        "unklar_beschrieben": (
            "Der Leistungsumfang ist zu offen oder unvollständig, sodass "
            "Maßnahmen, Schnittstellen oder Normen die Kalkulation verändern können."
        ),
        "menge_unplausibel": (
            "Die ausgeschriebene Menge wirkt für die beschriebene Bauleistung "
            "unplausibel und kann einen Komma- oder Zehnerpotenzfehler enthalten."
        ),
        "preis_unplausibel": (
            "Der vorkalkulierte Einheitspreis weicht gegenüber der technischen "
            "Komplexität oder der verfügbaren Marktspanne auffällig ab."
        ),
        "spezialgewerk": (
            "Die Position deutet auf ein Spezialgewerk oder eine "
            "Nachunternehmerleistung mit fachlich begrenztem Wettbewerb hin."
        ),
        "nachtragspotenzial": (
            "Der beschriebene Umfang birgt ein erhöhtes Risiko für Mengenmehrungen "
            "oder zusätzliche Nachträge nach VOB/B § 2 Abs. 3."
        ),
        "mindermengen_risiko": (
            "Die Position wirkt optional, bedarfsabhängig oder überhöht und könnte "
            "in deutlich geringerem Umfang abgerufen werden."
        ),
    }
    for dimension, probability in values.items():
        if probability > 0.50:
            reasons[dimension] = reason_text[dimension]

    return AtomicLLMJudgments(
        unklar_beschrieben=values["unklar_beschrieben"],
        menge_unplausibel=values["menge_unplausibel"],
        preis_unplausibel=values["preis_unplausibel"],
        spezialgewerk=values["spezialgewerk"],
        nachtragspotenzial=values["nachtragspotenzial"],
        mindermengen_risiko=values["mindermengen_risiko"],
        reasons=reasons,
    )


def judge_selected_items(
    items: Sequence[NormalizedItem],
    states: Sequence[HybridItemState],
    selected_keys: set[str],
    use_jev: bool | None = None,
    write_cache: bool = True,
    max_workers: int = 8,
) -> dict[str, AtomicLLMJudgments]:
    item_by_key = {item.key(): item for item in items}
    state_by_key = {state.key: state for state in states}
    cache = load_judgment_cache()

    if use_jev is None:
        use_jev = classify.jev_available()
    if not use_jev:
        return {}

    misses: list[tuple[NormalizedItem, HybridItemState, str]] = []
    output: dict[str, AtomicLLMJudgments] = {}

    for key in sorted(selected_keys):
        item = item_by_key.get(key)
        state = state_by_key.get(key)
        if item is None or state is None:
            continue

        fingerprint = judgment_fingerprint(item, state)
        cached = cache.get(fingerprint)
        if isinstance(cached, dict):
            output[key] = _judgment_from_cache(cached)
        else:
            misses.append((item, state, fingerprint))

    def resolve(
        entry: tuple[NormalizedItem, HybridItemState, str],
    ) -> tuple[str, AtomicLLMJudgments | None, str]:
        item, state, fingerprint = entry
        try:
            return item.key(), judge_item_jev(item, state), fingerprint
        except (classify.JevError, OSError, TimeoutError):
            return item.key(), None, fingerprint
        except Exception:
            return item.key(), None, fingerprint

    if misses:
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
            resolved = list(pool.map(resolve, misses))
        for key, judgments, fingerprint in resolved:
            if judgments is not None:
                output[key] = judgments
                cache[fingerprint] = _judgment_to_cache(judgments)

    if write_cache and misses:
        save_judgment_cache(cache)

    return output
