import os
import tempfile
import unittest
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

import export_rfi
from core import (
    classify,
    deep_logic,
    judgments,
    parser_x83,
    risk_engine,
    session_store,
)
from core.models import AtomicLLMJudgments


X83_FILES = (
    "Dataset/501-24-01_GAEB-XML_sas.x83",
    "Dataset/8209.003_Leistungsverzeichnis_leer.X83",
    "Dataset/[NUMMER_001]_leer.X83",
    "Dataset/GAEB-[PROJEKT_004].X83",
)


class AppLogicTests(unittest.TestCase):
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

    def test_app_starts_on_tender_without_restored_tender_data(self):
        app = AppTest.from_file(
            os.path.abspath("app.py"),
            default_timeout=120,
        )
        app.run()

        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["active_page"], "Tender")
        self.assertNotIn("source", app.session_state)
        self.assertEqual(app.session_state["manual_prices"], {})
        titles = [title.value for title in app.title]
        self.assertIn("Tender", titles)

    def test_subpage_navigation_without_toggle_makes_no_jev_calls(self):
        app = self._app_for_page("Tender")

        with (
            patch.object(classify, "classify_jev") as classify_call,
            patch.object(judgments, "judge_item_jev") as judgment_call,
            patch.object(classify, "save_cache"),
        ):
            app.run()
            for page in (
                "Gruppen & Angebot",
                "Vergabe",
                "Logik",
                "Heikle Positionen",
            ):
                app.session_state["active_page"] = page
                app.run()
                self.assertFalse(app.exception)

        classify_call.assert_not_called()
        judgment_call.assert_not_called()

    def test_lv_analysis_and_cluster_results_are_reused_across_subtabs(self):
        st.cache_data.clear()
        app = self._app_for_page("Heikle Positionen")
        app.session_state["use_jev"] = True

        with (
            patch.object(
                risk_engine,
                "analyze_tender_hybrid",
                wraps=risk_engine.analyze_tender_hybrid,
            ) as analyze,
            patch.object(judgments, "load_judgment_cache", return_value={}),
            patch.object(judgments, "save_judgment_cache"),
            patch.object(
                judgments,
                "judge_item_jev",
                return_value=AtomicLLMJudgments(0, 0, 0, 0, 0),
            ) as jev_call,
            patch.object(deep_logic, "evaluate_item_rfis", return_value={}),
            patch.object(
                parser_x83,
                "parse",
                wraps=parser_x83.parse,
            ) as parse_x83,
        ):
            app.run()
            jev_calls_after_first_run = jev_call.call_count
            self.assertGreater(jev_calls_after_first_run, 0)
            self.assertEqual(parse_x83.call_count, 1)
            app.session_state["active_page"] = "Logik"
            app.run()
            app.session_state["active_page"] = "Heikle Positionen"
            app.run()
            self.assertEqual(jev_call.call_count, jev_calls_after_first_run)
            self.assertEqual(parse_x83.call_count, 1)
            self.assertEqual(analyze.call_count, 1)

        st.cache_data.clear()
        app = self._app_for_page("Logik")
        app.session_state["use_deep_logic"] = True

        with patch.object(
            deep_logic,
            "evaluate_clusters",
            return_value={},
        ) as evaluate:
            app.run()
            app.session_state["active_page"] = "Vergabe"
            app.run()
            self.assertTrue(app.session_state["use_deep_logic"])
            app.session_state["active_page"] = "Logik"
            app.run()

            second_session = self._app_for_page("Logik")
            second_session.session_state["use_deep_logic"] = True
            second_session.run()

        self.assertEqual(evaluate.call_count, 2)
        self.assertTrue(app.session_state["use_deep_logic"])
        self.assertTrue(app.sidebar.toggle[0].value)

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

    def test_position_table_lives_on_tender_not_on_groups(self):
        """The per-position breakdown moved to Tender.

        "Gruppen & Angebot" answers where the money and the risk sit; a
        248-row table pushed that answer below the fold. The table itself is
        unchanged and still has to add up — asserted below on Tender.
        """
        groups = self._app_for_page("Gruppen & Angebot")
        groups.run()
        self.assertFalse(groups.exception)
        self.assertNotIn(
            "Positionskalkulation",
            [element.value for element in groups.subheader],
        )

        app = self._app_for_page("Tender")
        app.run()

        self.assertFalse(app.exception)
        self.assertFalse(app.tabs)
        expected_columns = {
            "Gewerk",
            "Menge",
            "Einheit",
            "Arbeitsstunden/Einh.",
            "Material €/Einh.",
            "EKT €/Einh.",
            "Zuschläge €/Einh.",
            "EP €/Einh.",
            "GP €",
        }
        calculation_tables = [
            element.value
            for element in app.dataframe
            if expected_columns.issubset(element.value.columns)
        ]
        self.assertTrue(calculation_tables)
        priced_row = calculation_tables[0].dropna(
            subset=["EKT €/Einh.", "EP €/Einh.", "GP €"],
        ).iloc[0]
        self.assertAlmostEqual(
            priced_row["EKT €/Einh."] + priced_row["Zuschläge €/Einh."],
            priced_row["EP €/Einh."],
            places=2,
        )
        self.assertAlmostEqual(
            priced_row["Menge"] * priced_row["EP €/Einh."],
            priced_row["GP €"],
            places=2,
        )
        self.assertAlmostEqual(
            priced_row["AGK €/Einh."]
            + priced_row["BGK €/Einh."]
            + priced_row["W&G €/Einh."],
            priced_row["Zuschläge €/Einh."],
            places=2,
        )
        self.assertIn(
            "Positionskalkulation",
            [element.value for element in app.subheader],
        )
        self.assertNotIn("Benchmark-Quercheck", [tab.label for tab in app.tabs])

        # The groups page keeps the summary metrics, just not the table.
        self.assertIn(
            "Angebotssumme",
            [element.value for element in groups.subheader],
        )

    def test_group_overview_has_clickable_section_subgroups(self):
        with patch.dict(os.environ, {
            "LOGIC_LLM_PROVIDER": "offline",
            "LOGIC_LLM_MODEL": "offline",
        }, clear=False):
            app = self._app_for_page("Gruppen & Angebot")
            app.run()
            self.assertFalse(app.exception, app.exception)

            app.button(key="open_group_0").click().run()
            self.assertFalse(app.exception, app.exception)
            subgroup_buttons = [
                button for button in app.button
                if button.key and button.key.startswith("open_subgroup_")
            ]
            self.assertTrue(subgroup_buttons)
            all_positions = app.dataframe(key="group_positions").value

            app.button(key=subgroup_buttons[0].key).click().run()
            self.assertFalse(app.exception, app.exception)
            self.assertIn("selected_group_subgroup_key", app.session_state)
            subgroup_positions = app.dataframe(key="group_positions").value
            self.assertLess(len(subgroup_positions), len(all_positions))

            app.button(key="show_all_group_positions").click().run()
            self.assertFalse(app.exception, app.exception)
            self.assertNotIn("selected_group_subgroup_key", app.session_state)

    def test_logic_and_tricky_pages_have_separate_ai_controls(self):
        logic_app = self._app_for_page("Logik")
        logic_app.run()
        self.assertFalse(logic_app.exception)
        # The Jev control lives on the page it affects ("Heikle Positionen"),
        # not in the sidebar: a global control that changes nothing on three
        # of five pages reads as broken. Logik keeps only its own.
        self.assertEqual(
            [toggle.label for toggle in logic_app.sidebar.toggle],
            ["Cluster-Tiefenprüfung (Gemma 4)"],
        )
        self.assertEqual([t.label for t in logic_app.toggle
                          if "KI-Tiefenprüfung" in t.label], [])
        self.assertEqual(
            [
                "Cluster- & Systemprüfungen",
                "Positionsbezogene Regelbefunde",
                "Mögliche Duplikate",
            ],
            [element.value for element in logic_app.subheader],
        )
        st.cache_data.clear()
        logic_app.session_state["use_jev"] = True
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
        self.assertTrue(analyze.call_args.kwargs["use_jev"])

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
            [toggle.label for toggle in tricky_app.toggle],
            ["KI-Tiefenprüfung (Top 60 Risiko-Positionen)"],
        )

    def test_jev_toggle_lives_on_the_risk_page_and_retains_state(self):
        app = self._app_for_page("Heikle Positionen")
        with (
            patch.dict(os.environ, {
                "LOGIC_LLM_PROVIDER": "offline",
                "LOGIC_LLM_MODEL": "offline",
            }, clear=False),
            patch.object(risk_engine, "analyze_tender_hybrid", return_value=([], [])),
        ):
            app.run()
            toggle = next(t for t in app.toggle
                          if "KI-Tiefenprüfung" in t.label)
            toggle.set_value(True).run()
            self.assertTrue(app.session_state["use_jev"])
            self.assertTrue(app.session_state["use_jev"])

            # The toggle is only rendered on the risk page, but the choice
            # must survive navigating away and back.
            for page in (
                "Tender",
                "Gruppen & Angebot",
                "Logik",
                "Heikle Positionen",
            ):
                app.session_state["active_page"] = page
                st.cache_data.clear()
                app.run()
                self.assertFalse(app.exception)
                self.assertTrue(app.session_state["use_jev"])
                visible = [t for t in app.toggle
                           if "KI-Tiefenprüfung" in t.label]
                if page == "Heikle Positionen":
                    self.assertEqual(len(visible), 1)
                    self.assertTrue(visible[0].value)
                else:
                    self.assertEqual(visible, [])

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
        downloads = app.get("download_button")
        self.assertEqual(
            {button.label for button in downloads},
            {"Export (.docx)", "Export (.md)"},
        )
        self.assertTrue(all(not button.proto.disabled for button in downloads))
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
                if button.label == "Als Bieterfrage übernehmen"
            ]
            self.assertTrue(question_buttons)
            question_buttons[0].click().run()

        self.assertFalse(app.exception)
        questions = app.session_state["rfi_cluster_questions"]
        self.assertEqual(len(questions), 1)
        self.assertTrue(questions[0]["category"])
        self.assertTrue(questions[0]["affected_ozs"])
        self.assertEqual(len(app.session_state["selected_rfis"]), 1)
        rfq_buttons = [
            button for button in app.button
            if button.label == "Als Nachunternehmen weiterleiten"
        ]
        self.assertTrue(rfq_buttons)
        rfq_buttons[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["selected_rfqs"]), 1)
        self.assertTrue(any(
            button.label == "✓ Als Bieterfrage übernommen" and button.disabled
            for button in app.button
        ))

    def test_selected_logik_actions_enable_both_exports_without_new_risk_findings(self):
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)
        app = self._app_for_page("Heikle Positionen")
        app.session_state["selected_rfis"] = [{
            "id": "RFI:position:001",
            "kind": "position",
            "action_type": "RFI",
            "oz": "1.0001",
            "short_text": "Rohrleitung verlegen",
            "quantity": 12,
            "unit": "m",
            "question": "Bitte bestätigen Sie den Leistungsumfang.",
        }] * 2
        app.session_state["selected_rfqs"] = [{
            "id": "RFQ:position:002",
            "kind": "position",
            "action_type": "RFQ",
            "oz": "1.0002",
            "short_text": "Schacht setzen",
            "quantity": 1,
            "unit": "St",
            "question": "Bitte bieten Sie das Setzen des Schachts an.",
        }]
        with (
            patch.object(risk_engine, "analyze_tender_hybrid", return_value=([], [])),
            patch.object(
                export_rfi,
                "to_markdown",
                wraps=export_rfi.to_markdown,
            ) as render_markdown,
        ):
            app.run()

        self.assertFalse(app.exception)
        downloads = app.get("download_button")
        self.assertEqual(
            {button.label for button in downloads},
            {"Export (.docx)", "Export (.md)"},
        )
        self.assertTrue(all(not button.proto.disabled for button in downloads))
        catalog = render_markdown.call_args.args[0]
        self.assertEqual(
            sum(entry["group"] == "position" for entry in catalog),
            1,
        )
        self.assertEqual(
            sum(entry["group"] == "rfq" for entry in catalog),
            1,
        )
        self.assertIn(
            "Bitte bestätigen Sie den Leistungsumfang.",
            [entry["frage"] for entry in catalog],
        )
        self.assertIn(
            "Bitte bieten Sie das Setzen des Schachts an.",
            [entry["frage"] for entry in catalog],
        )
        markdown_button = next(
            button for button in downloads if button.label == "Export (.md)"
        )
        markdown_button.click().run()
        self.assertFalse(app.exception)

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

    def test_tender_and_risky_row_selection_opens_position_details(self):
        for page, table_key in (
            ("Tender", "tender_items_table"),
            ("Heikle Positionen", "risky_items_table"),
        ):
            with self.subTest(page=page):
                st.cache_data.clear()
                app = self._app_for_page(page)
                app.session_state[table_key] = {
                    "selection": {"rows": [0]},
                }
                app.run()

                self.assertFalse(app.exception)
                self.assertTrue(app.session_state.get("opened_position_key"))
                self.assertEqual(len(app.get("iframe")), 1)
                if page == "Heikle Positionen":
                    self.assertIn("Heikle Positionen", [
                        title.value for title in app.title
                    ])
                    rfq_button = next(
                        button for button in app.button
                        if str(button.key).startswith("risky_position_rfq_")
                    )
                    rfq_button.click().run()
                    self.assertFalse(app.exception)
                    self.assertEqual(len(app.session_state["selected_rfqs"]), 1)

    def test_logic_rule_and_duplicate_tables_open_position_details(self):
        table_columns = {
            "logic_position_findings_table": {
                "OZ", "Kurztext", "Regelkategorie", "Schweregrad", "Begründung",
            },
            "logic_duplicate_pairs_table": {
                "OZ 1", "Kurztext 1", "OZ 2", "Kurztext 2",
                "Einheit", "Menge 1", "Menge 2", "Ähnlichkeit",
            },
        }
        for table_key, expected_columns in table_columns.items():
            with self.subTest(table=table_key):
                st.cache_data.clear()
                app = self._app_for_page("Logik")
                app.session_state[table_key] = {
                    "selection": {"rows": [0]},
                }
                app.run()

                self.assertFalse(app.exception)
                selected_table = next(
                    table for table in app.dataframe
                    if table.key == table_key
                )
                self.assertTrue(expected_columns.issubset(
                    set(selected_table.value.columns)
                ))
                self.assertTrue(app.session_state.get("opened_position_key"))
                self.assertEqual(len(app.get("iframe")), 1)
                if table_key == "logic_position_findings_table":
                    rfi_button = next(
                        button for button in app.button
                        if str(button.key).startswith("logic_position_rfi_")
                    )
                    rfi_button.click().run()
                    self.assertFalse(app.exception)
                    self.assertEqual(len(app.session_state["selected_rfis"]), 1)
                    self.assertTrue(any(
                        button.label == "✓ Als Bieterfrage übernommen"
                        and button.disabled
                        for button in app.button
                    ))


if __name__ == "__main__":
    unittest.main()
