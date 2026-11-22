import os
import unittest
from unittest.mock import patch

from core.deep_logic import (
    OfflineAdapter,
    cache_fingerprint,
    evaluate_clusters,
    get_adapter,
)
from core.models import Cluster


class DeepLogicTests(unittest.TestCase):
    def test_fingerprint_includes_rules_version_and_model(self):
        one = cache_fingerprint("payload", "1", "model-a")
        two = cache_fingerprint("payload", "2", "model-a")
        three = cache_fingerprint("payload", "1", "model-b")

        self.assertEqual(len(one), 40)
        self.assertNotEqual(one, two)
        self.assertNotEqual(one, three)

    def test_missing_key_returns_offline_adapter(self):
        with patch("core.deep_logic._load_env_once"):
            with patch.dict(os.environ, {
                "LOGIC_LLM_PROVIDER": "openai",
                "LOGIC_LLM_MODEL": "test-model",
            }, clear=False):
                os.environ.pop("LOGIC_LLM_KEY", None)
                adapter = get_adapter()
                self.assertIsInstance(adapter, OfflineAdapter)

    def test_offline_evaluation_is_marked_and_capped(self):
        clusters = [
            Cluster("sec:1", "SECTION", "One", ["01"]),
            Cluster("sec:2", "SECTION", "Two", ["02"]),
        ]
        payloads = {
            "sec:1": "payload one",
            "sec:2": "payload two",
        }
        with patch("core.deep_logic.load_deep_cache", return_value={}):
            with patch("core.deep_logic.save_deep_cache"):
                output = evaluate_clusters(
                    clusters,
                    payloads,
                    use_llm=False,
                    max_clusters=1,
                    write_cache=False,
                )

        self.assertEqual(set(output), {"sec:1"})
        self.assertTrue(output["sec:1"].offline)
        self.assertEqual(output["sec:1"].contradiction_category, "NONE")


if __name__ == "__main__":
    unittest.main()
