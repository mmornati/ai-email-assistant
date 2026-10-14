import base64
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import runner
import schedule
import triage


class TriageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.patches = [
            patch.object(triage, key, self.state / filename)
            for key, filename in {
                "PENDING": "pending.json", "PLAN_FILE": "plan.json", "META_CACHE": "meta.json",
                "JOURNAL": "journal.jsonl",
            }.items()
        ] + [
            patch.object(triage, "STATE", self.state),
            patch.object(triage, "REPORT", triage.Report()),
            patch.object(triage, "PLAN", []),
            patch.object(triage, "_meta_cache", {}),
            patch.object(runner, "CACHE", self.state / "cache.json"),
            patch.object(runner, "SUMMARY", self.state / "summary.json"),
            patch.object(runner, "USAGE", self.state / "usage.jsonl"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.rules = triage.load_rules(triage.ROOT / "rules.example.json")
        self.cfg = runner.load_config(triage.ROOT / "classifier.json")
        self.messages = [
            {"id": "a1", "thread": "t1", "subject": "Synthetic informational update", "snippet": "No action needed."},
            {"id": "a2", "thread": "t1", "subject": "Synthetic request", "snippet": "Please approve the proposal."},
        ]
        self.pending = {
            "batch_id": "batch", "created": time.time(), "rules_version": triage.rules_version(self.rules),
            "messages": self.messages,
        }
        self.args = SimpleNamespace(
            rules=str(triage.ROOT / "rules.example.json"), apply=False, window=None, limit=500,
            no_model=False, retry_review=False,
        )

    def envelope(self, decisions=None):
        return {"batch_id": "batch", "decisions": decisions if decisions is not None else {"a1": "FYI"}}

    def prediction(self, messages, confidence=0.99, needs_context=False):
        return {m["id"]: {"tag": "FYI", "task": None, "confidence": confidence,
                          "needs_context": needs_context} for m in messages}

    def test_current_envelope_and_subset(self):
        self.assertEqual(triage.validate_decisions(self.envelope(), self.pending, self.rules),
                         {"a1": {"tag": "FYI"}})

    def test_stale_batch_and_legacy_rejected(self):
        for raw in ({"a1": "FYI"}, {**self.envelope(), "batch_id": "old"}):
            with self.assertRaises(ValueError):
                triage.validate_decisions(raw, self.pending, self.rules)

    def test_foreign_id_rejected(self):
        with self.assertRaises(ValueError):
            triage.validate_decisions(self.envelope({"foreign": "FYI"}), self.pending, self.rules)

    def test_expired_future_and_changed_rules_rejected(self):
        for pending in (
            {**self.pending, "created": time.time() - 86401},
            {**self.pending, "created": time.time() + 1000},
            {**self.pending, "rules_version": "old"},
        ):
            with self.assertRaises(ValueError):
                triage.validate_decisions(self.envelope(), pending, self.rules)

    def test_invalid_tags_tasks_dates_and_overrides(self):
        invalid = [
            {"tag": "unknown"}, {"tag": "FYI", "archive": True},
            {"tag": "Newsletter", "task": {"title": "Do something"}},
            {"tag": "Action", "task": {"title": ""}},
            {"tag": "Action", "task": {"title": "x" * 251}},
            {"tag": "Action", "task": {"title": "Approve", "due": "2026-02-30"}},
            {"tag": "Action", "task": {"title": "Approve", "due": "20261008"}},
            {"tag": "Action", "task": {"title": "Approve", "notes": []}},
            {"tag": "Action", "task": {"title": "Approve", "on_done": ["trash"]}},
            {"tag": "Action", "task": {"title": "Approve", "on_done": ["star"]}},
            {"tag": "Action", "task": []},
        ]
        for decision in invalid:
            with self.subTest(decision=decision), self.assertRaises(ValueError):
                triage.validate_decisions(self.envelope({"a1": decision}), self.pending, self.rules)

    def test_valid_task_and_restricted_override(self):
        action = next(tag for tag in self.rules["tags"] if tag["name"] == "Action")
        action["on_task_done"] = ["mark_read", "archive"]
        self.pending["rules_version"] = triage.rules_version(self.rules)
        decision = {"tag": "Action", "task": {"title": "Approve proposal", "due": "2026-10-08",
                                              "on_done": ["archive"]}}
        self.assertEqual(triage.validate_decisions(self.envelope({"a1": decision}), self.pending, self.rules),
                         {"a1": decision})

    def test_model_shape_confidence_and_ids(self):
        invalid = [
            {}, {"foreign": self.prediction(self.messages)["a1"]},
            self.prediction(self.messages, confidence=float("nan")),
            self.prediction(self.messages, confidence=True),
            self.prediction(self.messages, needs_context="yes"),
            {**self.prediction(self.messages), "a1": {"tag": "FYI"}},
        ]
        for output in invalid:
            with self.subTest(output=output), self.assertRaises(ValueError):
                runner.validate_prediction(output, self.messages, self.pending, self.rules)

    def test_model_cannot_override_actions(self):
        output = self.prediction(self.messages)
        output["a1"].update(tag="Action", task={"title": "Approve", "on_done": ["archive"]})
        with self.assertRaises(ValueError):
            runner.validate_prediction(output, self.messages, self.pending, self.rules)

    def test_empty_pending_uses_no_model(self):
        with patch.object(runner, "call_model") as model:
            envelope, deferred, cached = runner.classify({**self.pending, "messages": []}, self.rules, self.cfg)
        model.assert_not_called()
        self.assertEqual((envelope["decisions"], deferred, cached), ({}, [], 0))

    def test_no_model_mode(self):
        with patch.object(runner, "call_model") as model:
            envelope, deferred, _ = runner.classify(self.pending, self.rules, self.cfg, no_model=True)
        model.assert_not_called()
        self.assertEqual(envelope["decisions"], {})
        self.assertEqual(deferred, self.messages)

    def test_batched_small_model_and_cache_hit(self):
        with patch.object(runner, "call_model", return_value=self.prediction(self.messages)) as model:
            envelope, deferred, cached = runner.classify(self.pending, self.rules, self.cfg)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(model.call_args.args[-1], self.cfg["cheap_model"])
        self.assertEqual((len(envelope["decisions"]), deferred, cached), (2, [], 0))
        with patch.object(runner, "call_model") as model:
            envelope, deferred, cached = runner.classify(self.pending, self.rules, self.cfg)
        model.assert_not_called()
        self.assertEqual(cached, 2)

    def test_escalation_fetches_context_only_for_ambiguous(self):
        cheap = self.prediction(self.messages)
        cheap["a2"]["needs_context"] = True
        strong = self.prediction(self.messages[1:])
        with patch.object(runner, "call_model", side_effect=[cheap, strong]) as model, \
                patch.object(triage, "fetch_context", return_value="Synthetic full text") as context:
            envelope, deferred, _ = runner.classify(self.pending, self.rules, self.cfg)
        context.assert_called_once_with("a2", self.cfg["context_chars"])
        self.assertEqual(model.call_args.args[-1], self.cfg["escalation_model"])
        self.assertEqual(model.call_args.args[0][0]["body"], "Synthetic full text")
        self.assertEqual(len(envelope["decisions"]), 2)
        self.assertEqual(deferred, [])

    def test_unresolved_mail_held_without_repeated_calls(self):
        with patch.object(runner, "call_model", side_effect=[
            self.prediction(self.messages, needs_context=True),
            self.prediction(self.messages, needs_context=True),
        ]), patch.object(triage, "fetch_context", return_value=""):
            envelope, deferred, _ = runner.classify(self.pending, self.rules, self.cfg)
        self.assertEqual(envelope["decisions"], {})
        self.assertEqual(deferred, self.messages)
        with patch.object(runner, "call_model") as model:
            runner.classify(self.pending, self.rules, self.cfg)
        model.assert_not_called()
        with patch.object(runner, "call_model", return_value=self.prediction(self.messages)) as model:
            envelope, deferred, _ = runner.classify(self.pending, self.rules, self.cfg, retry_review=True)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(deferred, [])

    def test_batch_and_escalation_caps(self):
        cfg = {**self.cfg, "batch_size": 1, "max_batches": 1, "max_escalations": 0}
        with patch.object(runner, "call_model", return_value=self.prediction(self.messages[:1], needs_context=True)) as model, \
                patch.object(triage, "fetch_context") as context:
            envelope, deferred, _ = runner.classify(self.pending, self.rules, cfg)
        self.assertEqual(model.call_count, 1)
        context.assert_not_called()
        self.assertEqual(len(deferred), 2)
        self.assertEqual(envelope["decisions"], {})

    def test_acceptance_threshold_boundaries(self):
        with patch.object(runner, "call_model", return_value=self.prediction(
            self.messages, confidence=self.cfg["confidence_threshold"]
        )) as model:
            envelope, deferred, _ = runner.classify(self.pending, self.rules, self.cfg)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(len(envelope["decisions"]), 2)
        self.assertEqual(deferred, [])
        runner.CACHE.unlink()
        with patch.object(runner, "call_model", side_effect=[
            self.prediction(self.messages, confidence=self.cfg["confidence_threshold"] - 0.01),
            self.prediction(self.messages, confidence=self.cfg["escalation_threshold"]),
        ]) as model, patch.object(triage, "fetch_context", return_value="text"):
            envelope, deferred, _ = runner.classify(self.pending, self.rules, self.cfg)
        self.assertEqual(model.call_count, 2)
        self.assertEqual(len(envelope["decisions"]), 2)
        self.assertEqual(deferred, [])

    def test_cache_invalidation_on_content_rules_and_model(self):
        key = runner.cache_key(self.messages[0], self.rules, self.cfg)
        self.assertNotEqual(key, runner.cache_key({**self.messages[0], "snippet": "Changed"}, self.rules, self.cfg))
        self.assertNotEqual(key, runner.cache_key(self.messages[0], {**self.rules, "label_prefix": "Other"}, self.cfg))
        self.assertNotEqual(key, runner.cache_key(self.messages[0], self.rules, {**self.cfg, "version": 2}))
        with patch.object(runner.dt, "date") as date:
            date.today.return_value.isoformat.return_value = "2099-01-01"
            self.assertNotEqual(key, runner.cache_key(self.messages[0], self.rules, self.cfg))

    def test_invalid_model_json_and_failure_are_explicit(self):
        for result in (
            SimpleNamespace(returncode=0, stdout="```json\n{}\n```"),
            SimpleNamespace(returncode=1, stdout="sensitive content"),
        ):
            with patch.object(runner.subprocess, "run", return_value=result):
                with self.assertRaises((ValueError, RuntimeError)) as error:
                    runner.call_model(self.messages, self.rules, self.cfg, self.cfg["cheap_model"])
                self.assertNotIn("sensitive", str(error.exception))
                usage = json.loads(runner.USAGE.read_text().splitlines()[-1])
                self.assertEqual(usage["status"], "cli_error" if result.returncode else "invalid_json")

    def test_timeout_and_custom_provider_fail_closed(self):
        with patch.object(runner.subprocess, "run", side_effect=subprocess.TimeoutExpired("copilot", 1)):
            with self.assertRaises(RuntimeError):
                runner.call_model(self.messages, self.rules, self.cfg, self.cfg["cheap_model"])
        with patch.dict(os.environ, {"COPILOT_PROVIDER_BASE_URL": "https://unapproved.invalid"}), \
                patch.object(runner.subprocess, "run") as process:
            with self.assertRaises(ValueError):
                runner.call_model(self.messages, self.rules, self.cfg, self.cfg["cheap_model"])
        process.assert_not_called()

    def test_cli_restrictions_stdin_and_isolation(self):
        output = json.dumps(self.prediction(self.messages))
        event = json.dumps({"type": "assistant.message", "data": {"phase": "final_answer", "content": output}})
        with patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=event)) as process:
            runner.call_model(self.messages, self.rules, self.cfg, self.cfg["cheap_model"])
        command = process.call_args.args[0]
        self.assertEqual(command[command.index("--output-format") + 1], "json")
        self.assertIn("--available-tools=", command)
        self.assertIn("--no-custom-instructions", command)
        self.assertIn("--no-remote-export", command)
        self.assertNotIn("--allow-all-tools", command)
        self.assertNotIn("-p", command)
        self.assertIn("Synthetic", process.call_args.kwargs["input"])
        self.assertNotEqual(process.call_args.kwargs["cwd"], str(triage.ROOT))

    def test_jsonl_preserves_long_strings_and_ignores_other_events(self):
        text = "A long synthetic string " * 20
        events = [
            {"type": "session.tools_updated", "data": {}},
            {"type": "assistant.message", "data": {
                "phase": "final_answer", "content": json.dumps({"long": text}), "toolRequests": [],
            }},
            {"type": "result", "exitCode": 0},
        ]
        self.assertEqual(runner.parse_cli_response("\n".join(json.dumps(e) for e in events)), {"long": text})

    def test_jsonl_rejects_missing_multiple_or_tool_using_final(self):
        final = {"type": "assistant.message", "data": {"phase": "final_answer", "content": "{}"}}
        for events in (
            [], [final, final], [{"type": "session.error"}],
            [{"type": "assistant.message", "data": {**final["data"], "toolRequests": [{}]}}],
            [1],
        ):
            with self.assertRaises(ValueError):
                runner.parse_cli_response("\n".join(json.dumps(e) for e in events))

    def test_usage_log_excludes_mail_and_unknown_fields(self):
        runner.record_usage("test", 1, 10, 20, 1.0, {
            "totalNanoAiu": 100, "secret": "private",
            "tokenDetails": {"input": {"tokenCount": 5}, "other": {"tokenCount": 3}},
        }, "ok")
        text = runner.USAGE.read_text()
        self.assertNotIn("private", text)
        self.assertEqual(json.loads(text)["cli_usage"]["tokens"], {"input": 5})
        with contextlib.redirect_stdout(io.StringIO()) as output:
            runner.usage_report()
        self.assertEqual(json.loads(output.getvalue())["test"]["tokens"]["input"], 5)

    def test_report_has_deterministic_task_details(self):
        triage.REPORT.task("a1", "CREATE due 2026-10-08: Approve proposal",
                           title="Approve proposal", due="2026-10-08", thread="t1")
        detail = triage.REPORT.rows["a1"]["task_detail"]
        self.assertEqual(detail["due"], "2026-10-08")
        self.assertEqual(detail["link"], "https://mail.google.com/mail/u/0/#all/t1")

    def test_rule_candidates_require_repeated_bulk_sender(self):
        messages = [
            {"id": f"b{i}", "from": "Synthetic List <news@example.invalid>", "bulk": True}
            for i in range(3)
        ]
        decisions = {m["id"]: {"tag": "Newsletter"} for m in messages}
        self.assertEqual(runner.rule_candidates(messages, decisions), [{
            "sender": "news@example.invalid", "count": 3, "query": "from:news@example.invalid",
            "classified_tags": ["Newsletter"], "requires_approval": True,
        }])
        self.assertEqual(runner.rule_candidates(messages[:2], decisions), [])
        self.assertEqual(runner.rule_candidates([{**m, "bulk": False} for m in messages], decisions), [])

    def test_rule_task_failure_does_not_apply_labels(self):
        args = SimpleNamespace(window="", limit=500, apply=False)
        with patch.object(triage, "search", return_value=["a1"]), \
                patch.object(triage, "ensure_tasks", side_effect=RuntimeError("task failed")), \
                patch.object(triage, "act") as act, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                triage.cmd_tag(self.rules, args, SimpleNamespace())
        act.assert_not_called()

    def test_missing_rules_produces_error_summary(self):
        self.args.rules = str(self.state / "missing-rules.json")
        with self.assertRaises(OSError):
            runner.run(self.args, self.cfg)
        self.assertEqual(json.loads(runner.SUMMARY.read_text())["status"], "error")

    def test_mailbox_state_preflight_before_actions(self):
        triage.write_json(triage.PENDING, self.pending)
        path = self.state / "decisions.json"
        triage.write_json(path, self.envelope())
        for labels in ([], ["INBOX", "label-fyi"]):
            with patch.object(triage, "gws", return_value={"labelIds": labels}), \
                    patch.object(triage, "ensure_tasks") as tasks, patch.object(triage, "act") as act:
                with self.assertRaises(ValueError):
                    triage.cmd_decide(self.rules, SimpleNamespace(apply=True, file=path),
                                      SimpleNamespace(by_name={"AI/FYI": "label-fyi"}))
            tasks.assert_not_called()
            act.assert_not_called()

    def test_task_failure_leaves_labels_untouched(self):
        triage.write_json(triage.PENDING, self.pending)
        path = self.state / "decisions.json"
        triage.write_json(path, self.envelope())
        with patch.object(triage, "ensure_tasks", side_effect=RuntimeError("failure")), \
                patch.object(triage, "act") as act, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                triage.cmd_decide(self.rules, SimpleNamespace(apply=False, file=path),
                                  SimpleNamespace(by_name={}))
        act.assert_not_called()

    def test_plain_context_no_attachments(self):
        encoded = lambda s: base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")
        payload = {"mimeType": "multipart/mixed", "parts": [
            {"mimeType": "text/plain", "body": {"data": encoded("synthetic body")}},
            {"mimeType": "text/plain", "filename": "attachment.txt", "body": {"data": encoded("secret attachment")}},
        ]}
        with patch.object(triage, "gws", return_value={"payload": payload}):
            self.assertEqual(triage.fetch_context("a1", 9), "synthetic")

    def test_shared_lock_rejects_second_process(self):
        with triage.run_lock():
            code = (
                "import triage; from pathlib import Path; "
                f"triage.STATE=Path({str(self.state)!r}); triage.main()"
            )
            result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another triage process", result.stderr)

    def test_private_atomic_json(self):
        path = self.state / "private.json"
        triage.write_json(path, {"test": True})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(path.with_suffix(".json.tmp").exists())

    def mock_scan(self):
        def pending(*args, **kwargs):
            triage.write_json(triage.PENDING, self.pending)
        patches = [
            patch.object(triage, "ROOT", self.state),
            patch.object(triage, "Labels", return_value=SimpleNamespace(by_name={})),
            patch.object(triage, "cmd_sync"), patch.object(triage, "cmd_tag", return_value=set()),
            patch.object(triage, "cmd_sweep"), patch.object(triage, "cmd_pending", side_effect=pending),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_end_to_end_dry_run_and_apply(self):
        for apply in (False, True):
            self.mock_scan()
            self.args.apply = apply
            with patch.object(runner, "call_model", return_value=self.prediction(self.messages)), \
                    patch.object(triage, "cmd_decide") as decide, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.run(self.args, self.cfg), 0)
            decide.assert_called_once()
            summary = json.loads(runner.SUMMARY.read_text())
            self.assertEqual((summary["status"], summary["classified"]), ("ok", 2))
            remaining = json.loads(triage.PENDING.read_text())["messages"]
            self.assertEqual(len(remaining), 0 if apply else 2)
            if not apply:
                self.assertTrue(triage.PLAN_FILE.exists())

    def test_end_to_end_empty_run_never_calls_model_or_decide(self):
        self.pending["messages"] = []
        self.mock_scan()
        with patch.object(runner, "call_model") as model, patch.object(triage, "cmd_decide") as decide, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.run(self.args, self.cfg), 0)
        model.assert_not_called()
        decide.assert_not_called()

    def test_end_to_end_unresolved_and_failure_status(self):
        self.mock_scan()
        self.args.no_model = True
        with patch.object(triage, "cmd_decide") as decide, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.run(self.args, self.cfg), 2)
        decide.assert_not_called()
        self.assertEqual(json.loads(runner.SUMMARY.read_text())["status"], "needs_review")
        self.args.no_model = False
        with patch.object(runner, "call_model", return_value={}), patch.object(triage, "cmd_decide") as decide:
            with self.assertRaises(ValueError):
                runner.run(self.args, self.cfg)
        decide.assert_not_called()
        self.assertEqual(json.loads(runner.SUMMARY.read_text())["status"], "error")

    def test_config_rejects_invalid_values(self):
        for key, value in (("batch_size", 0), ("max_escalations", -1), ("cheap_model", ""),
                           ("confidence_threshold", float("nan")), ("disabled_mcp_servers", "all")):
            path = self.state / "cfg.json"
            triage.write_json(path, {**self.cfg, key: value})
            with self.assertRaises(ValueError):
                runner.load_config(path)

    def test_schedule_calendar_and_no_immediate_execution(self):
        job = schedule.definition(sys.executable)
        self.assertEqual(len(job["StartCalendarInterval"]), 60)
        self.assertEqual({e["Weekday"] for e in job["StartCalendarInterval"]}, {1, 2, 3, 4, 5})
        self.assertEqual({e["Hour"] for e in job["StartCalendarInterval"]}, set(range(8, 20)))
        self.assertFalse(job["RunAtLoad"])
        self.assertIn("--apply", job["ProgramArguments"])
        self.assertNotIn("--apply", schedule.definition(sys.executable, dry_run=True)["ProgramArguments"])
        self.assertIn("--no-model", schedule.definition(sys.executable, no_model=True)["ProgramArguments"])


if __name__ == "__main__":
    unittest.main()
