from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

from core import session_store


def test_session_store_does_not_roundtrip_tender_data():
    with tempfile.TemporaryDirectory() as directory:
        with patch.object(
            session_store,
            "SESSION_FILE",
            os.path.join(directory, "session.json"),
        ):
            _assert_tender_data_not_persisted()


def _assert_tender_data_not_persisted():
    state = {
        "source": ("upload", "lv.x83", b"\x00\x01data"),
        "active_page": "Vergabe",
        "manual_prices": {"114": {"ep": 12.5, "gp": 12.5}},
        "vergabe_entscheidungen": {"lv.x83": {}},
        "mittellohn_slider": 67.5,
    }

    class State(dict):
        def keys(self):
            return super().keys()

    session_store.persist(State(state))

    restored = State()
    session_store.restore(restored)
    assert "source" not in restored
    assert "active_page" not in restored
    assert "manual_prices" not in restored
    assert "vergabe_entscheidungen" not in restored
    assert restored["mittellohn_slider"] == 67.5
