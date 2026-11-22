from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

from core import session_store
from core.vergabe import GewerkEntscheidung, Modus


def test_session_store_roundtrip_upload_and_vergabe():
    with tempfile.TemporaryDirectory() as directory:
        with patch.object(
            session_store,
            "SESSION_FILE",
            os.path.join(directory, "session.json"),
        ):
            _assert_session_store_roundtrip()


def _assert_session_store_roundtrip():
    state = {
        "source": ("upload", "lv.x83", b"\x00\x01data"),
        "active_page": "Vergabe",
        "manual_prices": {"114": {"ep": 12.5, "gp": 12.5}},
        "vergabe_entscheidungen": {
            "lv.x83": {
                "Kanal": GewerkEntscheidung(
                    "Kanal",
                    Modus.FREMD_ANGEBOT,
                    einkauf_eur=2500.0,
                    aufschlag_pct=12.0,
                )
            }
        },
    }

    class State(dict):
        def keys(self):
            return super().keys()

    session_store.persist(State(state))

    restored = State()
    assert session_store.restore(restored)
    assert restored["source"] == ("upload", "lv.x83", b"\x00\x01data")
    assert restored["active_page"] == "Vergabe"
    assert restored["manual_prices"]["114"]["gp"] == 12.5
    decision = restored["vergabe_entscheidungen"]["lv.x83"]["Kanal"]
    assert decision.modus is Modus.FREMD_ANGEBOT
    assert decision.einkauf_eur == 2500.0
    assert decision.aufschlag_pct == 12.0
