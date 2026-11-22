"""Small file-backed session persistence for the Streamlit UI.

Streamlit session state survives reruns but not a browser refresh/reopen.
This module stores the few UI values that should survive that boundary.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Iterable

SESSION_FILE = os.environ.get(
    "BID_RISK_SESSION_FILE",
    os.path.join("data", "persisted_session.json"),
)

PERSISTED_KEYS = {
}


def _is_persisted_key(key: str) -> bool:
    return (
        key in PERSISTED_KEYS
        or key.endswith("_slider")
        or key.endswith("_number")
    )


def _encode_vergabe(store: dict[str, Any]) -> dict[str, Any]:
    encoded: dict[str, Any] = {}
    for scope, decisions in store.items():
        encoded_scope: dict[str, Any] = {}
        for gewerk, decision in decisions.items():
            if hasattr(decision, "modus"):
                encoded_scope[gewerk] = {
                    "gewerk": decision.gewerk,
                    "modus": getattr(decision.modus, "value", str(decision.modus)),
                    "einkauf_eur": decision.einkauf_eur,
                    "aufschlag_pct": decision.aufschlag_pct,
                }
            elif isinstance(decision, dict):
                encoded_scope[gewerk] = decision
        encoded[scope] = encoded_scope
    return encoded


def _decode_vergabe(store: dict[str, Any]) -> dict[str, Any]:
    from core.vergabe import GewerkEntscheidung, Modus

    decoded: dict[str, Any] = {}
    for scope, decisions in store.items():
        decoded_scope: dict[str, Any] = {}
        for gewerk, raw in decisions.items():
            if isinstance(raw, dict):
                decoded_scope[gewerk] = GewerkEntscheidung(
                    gewerk=raw.get("gewerk", gewerk),
                    modus=Modus(raw["modus"]),
                    einkauf_eur=raw.get("einkauf_eur"),
                    aufschlag_pct=float(raw.get("aufschlag_pct", 10.0)),
                )
        decoded[scope] = decoded_scope
    return decoded


def _encode_source(source: Any) -> Any:
    if not isinstance(source, tuple) or not source:
        return source
    if source[0] == "upload" and len(source) >= 3:
        payload = source[2]
        if isinstance(payload, bytes):
            payload = base64.b64encode(payload).decode("ascii")
        return [source[0], source[1], {"base64": payload}]
    return list(source)


def _decode_source(source: Any) -> Any:
    if not isinstance(source, list) or not source:
        return source
    if source[0] == "upload" and len(source) >= 3:
        payload = source[2]
        if isinstance(payload, dict) and "base64" in payload:
            payload = base64.b64decode(payload["base64"])
        return (source[0], source[1], payload)
    return tuple(source)


def snapshot(session_state: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in list(session_state.keys()):
        if not isinstance(key, str) or not _is_persisted_key(key):
            continue
        value = session_state.get(key)
        if key == "source":
            result[key] = _encode_source(value)
        elif key == "vergabe_entscheidungen":
            result[key] = _encode_vergabe(value or {})
        else:
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                continue
            result[key] = value
    return result


def persist(session_state: Any) -> None:
    state = snapshot(session_state)
    parent = os.path.dirname(os.path.abspath(SESSION_FILE))
    os.makedirs(parent, exist_ok=True)
    temporary = f"{SESSION_FILE}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, SESSION_FILE)


def restore(session_state: Any) -> bool:
    if not os.path.isfile(SESSION_FILE):
        return False
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False

    for key, value in state.items():
        if key in session_state:
            continue
        if key == "source":
            value = _decode_source(value)
        elif key == "vergabe_entscheidungen":
            value = _decode_vergabe(value)
        session_state[key] = value
    return True
