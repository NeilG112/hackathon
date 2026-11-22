import json
import unittest
from unittest.mock import patch

from core.deep_logic import (
    ITEM_RFI_MODEL,
    OpenAIAdapter,
    OfflineAdapter,
    evaluate_item_rfis,
    item_rfi_fingerprint,
)


class ItemRfiTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "oz": "0101",
            "short_text": "Rohrleitung herstellen",
            "long_text": "Anschluss an Bestand unklar.",
            "quantity": 12.0,
            "unit": "m",
            "remarks": ["Bestand ist einzukalkulieren."],
            "risk_triggers": [
                {"type": "action", "value": "RFI"},
                {
                    "type": "jev_score",
                    "name": "unklar_beschrieben",
                    "probability": 0.8,
                },
            ],
        }

    def test_fingerprint_covers_item_text_and_trigger_signals(self):
        base = item_rfi_fingerprint(self.payload)
        changed_text = dict(self.payload, long_text="Anschluss eindeutig.")
        changed_triggers = dict(
            self.payload,
            risk_triggers=[{"type": "action", "value": "RFQ"}],
        )

        self.assertNotEqual(base, item_rfi_fingerprint(changed_text))
        self.assertNotEqual(base, item_rfi_fingerprint(changed_triggers))

    def test_no_openai_key_keeps_deterministic_fallback(self):
        with patch("core.deep_logic.get_adapter", return_value=OfflineAdapter()):
            with patch.object(OpenAIAdapter, "evaluate") as evaluate:
                result = evaluate_item_rfis({"0101": self.payload})

        self.assertEqual(result, {})
        evaluate.assert_not_called()

    def test_gemma_refinement_is_cached_and_uses_item_prompt(self):
        expected = {
            "commercial_reason_de": (
                "Der Bestandsanschluss ist nicht eindeutig abgegrenzt."
            ),
            "bidder_question_de": (
                "Bitte benennen Sie die einzurechnende Anschlussstelle."
            ),
        }
        adapter = OpenAIAdapter(
            model="configured-model",
            key="test-key",
            base_url="https://example.test/v1",
        )

        def fake_evaluate(
            openai_adapter,
            request_payload,
            schema,
            system_prompt=None,
        ):
            self.assertEqual(openai_adapter.model, ITEM_RFI_MODEL)
            self.assertEqual(
                json.loads(request_payload)["risk_triggers"],
                self.payload["risk_triggers"],
            )
            self.assertIn("VOB/A", system_prompt)
            self.assertEqual(
                set(schema["required"]),
                {"commercial_reason_de", "bidder_question_de"},
            )
            return expected

        with patch("core.deep_logic.get_adapter", return_value=adapter):
            with patch("core.deep_logic.load_item_rfi_cache", return_value={}):
                with patch("core.deep_logic.save_item_rfi_cache") as save_cache:
                    with patch.object(
                        OpenAIAdapter,
                        "evaluate",
                        autospec=True,
                        side_effect=fake_evaluate,
                    ):
                        result = evaluate_item_rfis({"0101": self.payload})

        self.assertEqual(result["0101"], expected)
        save_cache.assert_called_once()
        saved = save_cache.call_args.args[0]
        self.assertEqual(
            saved[item_rfi_fingerprint(self.payload, ITEM_RFI_MODEL)],
            expected,
        )

    def test_cache_hit_skips_gemma_call(self):
        expected = {
            "commercial_reason_de": "Kaufmännischer Befund.",
            "bidder_question_de": "Bitte bestätigen Sie den Umfang.",
        }
        adapter = OpenAIAdapter(model="configured", key="test-key")
        fingerprint = item_rfi_fingerprint(self.payload, ITEM_RFI_MODEL)
        with patch("core.deep_logic.get_adapter", return_value=adapter):
            with patch(
                "core.deep_logic.load_item_rfi_cache",
                return_value={fingerprint: expected},
            ):
                with patch.object(OpenAIAdapter, "evaluate") as evaluate:
                    result = evaluate_item_rfis({"0101": self.payload})

        self.assertEqual(result["0101"], expected)
        evaluate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
