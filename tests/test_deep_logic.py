import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from core.deep_logic import (
    OpenAIAdapter,
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

    def test_clusters_are_ranked_before_limit_with_system_and_frame_tiebreak(self):
        clusters = [
            Cluster("section-low", "SECTION", "Low", ["01"], 100.0),
            Cluster("frame", "FRAME", "Frame", ["02"], 100.0),
            Cluster("section-high", "SECTION", "High", ["03"], 200.0),
            Cluster("system", "SYSTEM", "System", ["04"], 100.0),
        ]
        payloads = {cluster.cluster_id: cluster.cluster_id for cluster in clusters}

        class Adapter:
            name = "test"

            def evaluate(self, payload, schema):
                return {
                    "contradiction_category": "NONE",
                    "severity": "low",
                    "reason_de": payload,
                    "affected_positions": [],
                    "confidence": 0.0,
                }

        with patch("core.deep_logic.get_adapter", return_value=Adapter()):
            with patch("core.deep_logic.load_deep_cache", return_value={}):
                with patch("core.deep_logic.save_deep_cache"):
                    output = evaluate_clusters(
                        clusters,
                        payloads,
                        max_clusters=3,
                        write_cache=False,
                    )

        self.assertEqual(
            list(output),
            ["section-high", "system", "frame"],
        )

    def test_openai_adapter_retries_json_object_and_sanitizes_gemma_response(
        self,
    ):
        response_body = {
            "choices": [{
                "message": {
                    "content": (
                        "<|channel>thought\nReasoning before JSON.\n"
                        "```json\n"
                        '{"contradiction_category":"NONE","severity":"low",'
                        '"reason_de":"Keine belegbaren Widersprüche.",'
                        '"affected_positions":[],"confidence":0.0}\n'
                        "```"
                    ),
                },
            }],
        }

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(response_body).encode("utf-8")

        rejected = HTTPError(
            "https://example.test/v1/chat/completions",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(b"json_schema unsupported"),
        )
        adapter = OpenAIAdapter(
            model="google/gemma-4-31B-it",
            key="test-key",
            base_url="https://example.test/v1",
        )
        with patch(
            "core.deep_logic.urllib.request.urlopen",
            side_effect=[rejected, Response()],
        ) as urlopen:
            result = adapter.evaluate("payload", {"type": "object"})

        sent_bodies = [
            json.loads(call.args[0].data.decode("utf-8"))
            for call in urlopen.call_args_list
        ]
        self.assertEqual(result["contradiction_category"], "NONE")
        self.assertEqual(len(sent_bodies), 2)
        self.assertEqual(sent_bodies[0]["temperature"], 0.1)
        self.assertEqual(
            sent_bodies[0]["response_format"]["type"],
            "json_schema",
        )
        self.assertEqual(sent_bodies[1]["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
