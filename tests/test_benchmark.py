import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import triage
from tools import benchmark


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.rules = triage.load_rules(triage.ROOT / "rules.example.json")
        self.fixture = json.loads(benchmark.FIXTURES.read_text())

    def test_fixtures_are_complete_and_valid(self):
        messages = self.fixture["messages"]
        self.assertEqual({m["id"] for m in messages}, set(self.fixture["gold"]))
        self.assertEqual(len(messages), 16)
        self.assertEqual(sum(g["tag"] == "Action" for g in self.fixture["gold"].values()), 4)

    def test_gold_metrics_missing_output_counts_as_wrong(self):
        gold = {"a": {"tag": "Action", "has_task": True}, "b": {"tag": "FYI", "has_task": False}}
        metrics = benchmark.gold_metrics({"b": {"tag": "FYI", "has_task": False, "due": None}}, gold)
        self.assertEqual(metrics["tag_accuracy"], 0.5)
        self.assertEqual(metrics["action_fn"], 1)
        self.assertEqual(metrics["due_correct"], 1)

    def test_local_cannot_claim_date_extraction_accuracy(self):
        actual = {"a": {"tag": "Action", "has_task": True, "due": None}}
        gold = {"a": {"tag": "Action", "has_task": True, "due": "2026-10-09"}}
        self.assertIsNone(benchmark.gold_metrics(actual, gold, generation=False)["due_correct"])
        self.assertEqual(benchmark.gold_metrics(actual, gold)["due_correct"], 0)

    def test_paired_metrics_exclude_confidence_differences(self):
        left = {"a": {"tag": "FYI", "has_task": False, "confidence": 0.9}}
        right = {"a": {"tag": "FYI", "has_task": False, "confidence": 0.8}}
        metrics = benchmark.paired_metrics(left, right)
        self.assertEqual(metrics["tag_agreement"], 1)
        self.assertEqual(metrics["tag_disagreements"], [])
        self.assertEqual(metrics["task_presence_disagreements"], [])
        right["a"]["tag"] = "Action"
        self.assertEqual(benchmark.paired_metrics(left, right)["tag_disagreements"], ["a"])

    def test_summarization_drops_mail_task_text(self):
        summary = benchmark.summarize({
            "a": {"tag": "Action", "task": {"title": "confidential", "notes": "private"},
                  "confidence": 0.9, "needs_context": False},
        })
        text = json.dumps(summary)
        self.assertNotIn("confidential", text)
        self.assertNotIn("private", text)

    def test_billing_includes_cache_categories(self):
        cost = benchmark.billing_cost({"tokens": {"input": 3, "cache_write": 18088, "output": 816}},
                                      {"input": 0.1, "cache_read": 0.01, "cache_write": 0.125, "output": 0.5})
        self.assertAlmostEqual(cost, 0.0026693)
        self.assertIsNone(benchmark.billing_cost(None, {}))
        self.assertIsNone(benchmark.billing_cost({"tokens": {"input": 1}}, benchmark.MODEL_RATES.get("unknown")))

    def test_billing_prices_one_hour_cache_writes_separately(self):
        # Synthetic two-message Claude Haiku 5.5 probe: 1,635 cache-write tokens, all with a 1-hour TTL.
        usage = {"tokens": {"input": 2, "cache_read": 0, "cache_write": 1635, "cache_write_1h": 1635, "output": 696}}
        self.assertAlmostEqual(benchmark.billing_cost(usage, benchmark.MODEL_RATES["claude-haiku-5-5"]), 0.0006752)
        usage["tokens"]["cache_write_1h"] = 0
        self.assertAlmostEqual(benchmark.billing_cost(usage, benchmark.MODEL_RATES["claude-haiku-5-5"]), 0.000552575)
        self.assertEqual(set(benchmark.MODEL_RATES), {"gpt-6-luna", "gpt-6.1-sol", "claude-haiku-5-5",
                                                      "claude-sonnet-5-5"})

    def test_schemas_keep_all_allowed_tags(self):
        allowed = {t["name"] for t in self.rules["tags"]}
        for schema in ("baseline", "compact"):
            questions = benchmark.questions_for(self.rules, schema)
            self.assertEqual(set(questions["tag"]["criteria"]), allowed)
            self.assertEqual(questions["needs_task"]["type"], "noul")

    def test_local_adapter_preserves_probabilities_and_marks_truncation(self):
        router = Mock()
        router.predict_batch.return_value = [{
            "answers": {
                "tag": {"choice": "FYI", "answer_confidence": 0.8, "confidence": 0.3,
                        "probabilities": {"FYI": 0.8}},
                "needs_task": {"noul": 0.1},
            }, "usage": {"truncated": True}, "routing": {"model": "english"},
        }]
        output, metrics = benchmark.local_call([{"id": "a", "subject": "synthetic"}], self.rules, router)
        self.assertTrue(output["a"]["needs_context"])
        self.assertFalse(output["a"]["has_task"])
        self.assertEqual(output["a"]["confidence"], 0.8)
        self.assertEqual(output["a"]["entropy_confidence"], 0.3)
        self.assertFalse(metrics["text_generation_supported"])
        self.assertEqual(metrics["usd_reference"], 0)

    def test_local_failure_is_explicit_and_no_success_prediction(self):
        router = Mock()
        router.predict_batch.return_value = []
        with self.assertRaises(ValueError):
            benchmark.local_call([{"id": "a"}], self.rules, router)

    def test_local_rejects_invalid_probability(self):
        for probability in (float("nan"), True, 1.2, "0.9"):
            router = Mock()
            router.predict_batch.return_value = [{
                "answers": {"tag": {"choice": "FYI", "answer_confidence": probability},
                            "needs_task": {"noul": 0.1}},
            }]
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                benchmark.local_call([{"id": "a"}], self.rules, router)

    def test_prepare_never_reads_pending_or_calls_hosted_model(self):
        router = Mock()
        router.loaded_revisions = {"english": benchmark.LAYA_REVISION,
                                   "multilingual": benchmark.LAYA_REVISION}
        factory = Mock(return_value=router)
        optional = {
            "truststore": SimpleNamespace(inject_into_ssl=Mock()),
            "torch": SimpleNamespace(),
            "laya": SimpleNamespace(Router=factory),
        }
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(triage, "STATE", Path(directory)), \
                patch.dict(sys.modules, optional), \
                patch.object(sys, "argv", ["benchmark.py", "--prepare"]), \
                patch.object(triage, "run_lock") as lock, \
                patch.object(benchmark.runner, "call_model") as hosted, \
                patch("builtins.print"):
            benchmark.main()
            record = json.loads((Path(directory) / "laya-install.json").read_text())
        self.assertEqual(record["revision"], benchmark.LAYA_REVISION)
        factory.assert_called_once_with(device="mps", revision=benchmark.LAYA_REVISION,
                                        agent_kwargs={"backend": "eager"})
        router.preload.assert_called_once_with(["english", "multilingual"])
        lock.assert_not_called()
        hosted.assert_not_called()


if __name__ == "__main__":
    unittest.main()
