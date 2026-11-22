import os
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from core import session_store
from core.vergabe import Modus

DEMO = os.path.abspath("Dataset/[NUMMER_001]_leer.X83")
OFFLINE = {"LOGIC_LLM_PROVIDER": "offline", "LOGIC_LLM_MODEL": "offline"}


def _app() -> AppTest:
    app = AppTest.from_file(os.path.abspath("app.py"), default_timeout=180)
    app.session_state["source"] = ("disk", DEMO)
    app.session_state["active_page"] = "Vergabe"
    return app


def _metric(app: AppTest, label: str) -> str:
    return next(m.value for m in app.metric if m.label == label)


def _euro(text: str) -> int:
    """'514.443 €' and '€514,443' -> 514443. The two pages format differently."""
    return int("".join(ch for ch in text if ch.isdigit()))


class VergabePageTests(unittest.TestCase):
    def setUp(self):
        self._session_directory = tempfile.TemporaryDirectory()
        self._session_file_patch = patch.object(
            session_store,
            "SESSION_FILE",
            os.path.join(self._session_directory.name, "session.json"),
        )
        self._session_file_patch.start()

    def tearDown(self):
        self._session_file_patch.stop()
        self._session_directory.cleanup()

    def test_page_renders_and_quote_replaces_own_price(self):
        with patch.dict(os.environ, OFFLINE, clear=False):
            app = _app().run()
            self.assertFalse(app.exception, app.exception)
            before = _metric(app, "Angebotssumme")

            radio = next(r for r in app.radio
                         if r.key and r.key.endswith("::Prüfung::modus"))
            modus_key = radio.key
            radio.set_value(Modus.FREMD_ANGEBOT.value).run()
            app.number_input(key=modus_key.replace("::modus", "::einkauf")) \
                .set_value(9500.0).run()

            self.assertFalse(app.exception, app.exception)
            after = _metric(app, "Angebotssumme")
            self.assertNotEqual(before, after)
            self.assertEqual(_metric(app, "aus Vergabe"), "950 €")

            # Switch page and back: the decision must survive both trips, and
            # both pages must show the same bid.
            app.session_state["active_page"] = "Gruppen & Angebot"
            app.run()
            self.assertFalse(app.exception, app.exception)
            self.assertEqual(_euro(_metric(app, "Angebotssumme")), _euro(after))

            app.session_state["active_page"] = "Vergabe"
            app.run()
            self.assertFalse(app.exception, app.exception)
            self.assertEqual(_euro(_metric(app, "Angebotssumme")), _euro(after))
            self.assertEqual(app.number_input(
                key=modus_key.replace("::modus", "::einkauf")).value, 9500.0)

    def test_sidebar_price_can_be_entered_or_adjusted_by_slider(self):
        with patch.dict(os.environ, OFFLINE, clear=False):
            app = _app().run()
            app.number_input(key="mittellohn_number").set_value(66.0).run()
            self.assertFalse(app.exception, app.exception)
            self.assertEqual(app.slider(key="mittellohn_slider").value, 66.0)

            app.slider(key="mittellohn_slider").set_value(70.0).run()
            self.assertFalse(app.exception, app.exception)
            self.assertEqual(app.number_input(key="mittellohn_number").value, 70.0)

    def test_group_position_edit_updates_total_and_document_preview(self):
        with patch.dict(os.environ, OFFLINE, clear=False):
            app = AppTest.from_file(os.path.abspath("app.py"), default_timeout=180)
            app.session_state["source"] = ("disk", DEMO)
            app.session_state["active_page"] = "Gruppen & Angebot"
            app.run()
            self.assertFalse(app.exception, app.exception)

            app.button(key="open_group_0").click().run()
            app.session_state["group_positions"] = {
                "selection": {"rows": [0], "columns": [], "cells": []}
            }
            app.run()
            self.assertFalse(app.exception, app.exception)
            position_key = app.session_state["opened_position_key"]
            self.assertIn(f"dialog_ep_{position_key}", app.session_state)

            app.number_input(
                key=f"dialog_ep_{position_key}"
            ).set_value(123.45).run()
            self.assertFalse(app.exception, app.exception)
            edited = app.session_state["manual_prices"][position_key]
            row = next(
                table.value.iloc[0]
                for table in app.dataframe
                if "Bearbeitet" in table.value.columns
            )
            self.assertEqual(edited["ep"], 123.45)
            self.assertEqual(edited["gp"], round(123.45 * row["Menge"], 2))
            self.assertEqual(row["Bearbeitet"], "●")

            preview = app.get("iframe")[0].proto.srcdoc
            self.assertIn("€123.45", preview)
            self.assertIn("class=\"number changed\"", preview)

            app.number_input(
                key=f"dialog_gp_{position_key}"
            ).set_value(6000.0).run()
            self.assertFalse(app.exception, app.exception)
            edited = app.session_state["manual_prices"][position_key]
            self.assertEqual(edited["gp"], 6000.0)
            self.assertEqual(edited["ep"], round(6000.0 / row["Menge"], 2))
            self.assertIn("€6,000.00", app.get("iframe")[0].proto.srcdoc)


if __name__ == "__main__":
    unittest.main()
