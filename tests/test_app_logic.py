import os
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


X83_FILES = (
    "Dataset/501-24-01_GAEB-XML_sas.x83",
    "Dataset/8209.003_Leistungsverzeichnis_leer.X83",
    "Dataset/[NUMMER_001]_leer.X83",
    "Dataset/GAEB-[PROJEKT_004].X83",
)


class AppLogicTests(unittest.TestCase):
    def test_logic_tab_renders_for_all_x83_samples(self):
        for relative_path in X83_FILES:
            with self.subTest(file=relative_path):
                path = os.path.abspath(relative_path)
                with patch.dict(os.environ, {
                    "LOGIC_LLM_PROVIDER": "offline",
                    "LOGIC_LLM_MODEL": "offline",
                }, clear=False):
                    app = AppTest.from_file(
                        os.path.abspath("app.py"),
                        default_timeout=120,
                    )
                    app.session_state["source"] = ("disk", path)
                    app.session_state["active_page"] = "Logik"
                    app.run()

                    self.assertFalse(app.exception)
                    titles = [title.value for title in app.title]
                    self.assertIn("Logik", titles)
                    sidebar_buttons = [button.label for button in app.sidebar.button]
                    self.assertIn("Logik", sidebar_buttons)
                    self.assertFalse(app.selectbox)

    def test_blank_tender_labels_missing_prices_and_lump_sum_type(self):
        app = AppTest.from_file(
            os.path.abspath("app.py"),
            default_timeout=120,
        )
        app.session_state["source"] = (
            "disk",
            os.path.abspath("Dataset/[NUMMER_001]_leer.X83"),
        )
        app.session_state["active_page"] = "Tender"
        app.run()

        self.assertFalse(app.exception)
        captions = [element.value for element in app.caption]
        self.assertTrue(any("noch keine Positionspreise" in value for value in captions))
        self.assertTrue(any("keinen Preis" in value for value in captions))


if __name__ == "__main__":
    unittest.main()
