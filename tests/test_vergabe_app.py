import os
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

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


if __name__ == "__main__":
    unittest.main()
