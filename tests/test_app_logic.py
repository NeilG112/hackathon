import os
import unittest
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from core import deep_logic, risk_engine


X83_FILES = (
    "Dataset/501-24-01_GAEB-XML_sas.x83",
    "Dataset/8209.003_Leistungsverzeichnis_leer.X83",
    "Dataset/[NUMMER_001]_leer.X83",
    "Dataset/GAEB-[PROJEKT_004].X83",
)


class AppLogicTests(unittest.TestCase):
    def _app_for_page(self, page):
        app = AppTest.from_file(
            os.path.abspath("app.py"),
            default_timeout=120,
        )
        app.session_state["source"] = (
            "disk",
            os.path.abspath("Dataset/[NUMMER_001]_leer.X83"),
        )
        app.session_state["active_page"] = page
        return app

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

    def test_severity_values_are_localized_in_ui_tables(self):
        labels = {"hoch", "mittel", "niedrig"}
        with patch.dict(os.environ, {
            "LOGIC_LLM_PROVIDER": "offline",
            "LOGIC_LLM_MODEL": "offline",
        }, clear=False):
            logic_app = self._app_for_page("Logik")
            logic_app.run()
            self.assertFalse(logic_app.exception)
            logic_tables = [
                element.value
                for element in logic_app.dataframe
                if "Schweregrad" in element.value.columns
            ]
            self.assertTrue(logic_tables)
            for table in logic_tables:
                self.assertTrue(set(table["Schweregrad"]).issubset(labels))

            risk_app = self._app_for_page("Heikle Positionen")
            risk_app.run()
            self.assertFalse(risk_app.exception)
            risk_tables = [
                element.value
                for element in risk_app.dataframe
                if "Risiko" in element.value.columns
            ]
            self.assertTrue(risk_tables)
            for table in risk_tables:
                self.assertTrue(set(table["Risiko"]).issubset(labels))

            risk_app.segmented_control[0].set_value("Hohes Risiko").run()
            self.assertFalse(risk_app.exception)
            risk_table = next(
                element.value
                for element in risk_app.dataframe
                if "Risiko" in element.value.columns
            )
            self.assertEqual(set(risk_table["Risiko"]), {"hoch"})

    def test_groups_page_exposes_all_analysis_tabs(self):
        app = self._app_for_page("Gruppen & Angebot")
        app.run()

        self.assertFalse(app.exception)
        self.assertEqual(
            [tab.label for tab in app.tabs],
            [
                "Gewerke & Positionen",
                "Positionskalkulation",
                "Benchmark-Quercheck",
                "Angebots-Reveal",
            ],
        )

    def test_logic_and_tricky_pages_have_separate_ai_controls(self):
        logic_app = self._app_for_page("Logik")
        logic_app.run()
        self.assertFalse(logic_app.exception)
        self.assertEqual(
            [checkbox.label for checkbox in logic_app.sidebar.checkbox],
            ["Cluster-Tiefenprüfung (Gemma 4)"],
        )
        self.assertIn(
            "Positionsregeln und mögliche Duplikate",
            [element.value for element in logic_app.subheader],
        )
        st.cache_data.clear()
        logic_app.session_state["use_deep_logic"] = True
        with (
            patch.object(risk_engine, "analyze_tender_hybrid", return_value=([], []))
            as analyze,
            patch.object(deep_logic, "evaluate_clusters", return_value={})
            as evaluate,
        ):
            logic_app.run()
        self.assertFalse(logic_app.exception)
        evaluate.assert_called_once()
        self.assertFalse(analyze.call_args.kwargs["use_jev"])

        tricky_app = self._app_for_page("Heikle Positionen")
        tricky_app.session_state["use_jev"] = True
        st.cache_data.clear()
        with patch.object(
            risk_engine,
            "analyze_tender_hybrid",
            return_value=([], []),
        ) as analyze:
            tricky_app.run()
        self.assertFalse(tricky_app.exception)
        self.assertTrue(analyze.call_args.kwargs["use_jev"])
        tricky_app.run()
        self.assertFalse(tricky_app.exception)
        self.assertEqual(
            [checkbox.label for checkbox in tricky_app.sidebar.checkbox],
            ["Jev-Risikotriage (Top 60 Positionen)"],
        )

    def test_cluster_questions_export_without_position_findings(self):
        st.cache_data.clear()
        app = self._app_for_page("Heikle Positionen")
        app.session_state["rfi_cluster_questions"] = [{
            "cluster_id": "cluster-test",
            "category": "DN_STEP",
            "title": "Leitungsstrang",
            "analysis": "Nennweitenwechsel klaeren.",
            "affected_ozs": ["01.01"],
            "euro_exposure_estimate": 100.0,
        }]
        with patch.object(risk_engine, "analyze_tender_hybrid", return_value=([], [])):
            app.run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.get("download_button")), 1)
        app.get("download_button")[0].click().run()
        self.assertFalse(app.exception)

    def test_logic_cluster_finding_can_be_added_to_export(self):
        st.cache_data.clear()
        app = self._app_for_page("Logik")
        with patch.dict(os.environ, {
            "LOGIC_LLM_PROVIDER": "offline",
            "LOGIC_LLM_MODEL": "offline",
        }, clear=False):
            app.run()
            question_buttons = [
                button for button in app.button
                if button.label == "Als Bieterfrage uebernehmen"
            ]
            self.assertTrue(question_buttons)
            question_buttons[0].click().run()

        self.assertFalse(app.exception)
        questions = app.session_state["rfi_cluster_questions"]
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["category"], "DN_STEP")
        self.assertTrue(questions[0]["affected_ozs"])

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
