import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import runner
import triage


def claude_result(content, **overrides):
    return json.dumps({
        "type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
        "permission_denials": [], "result": content, "total_cost_usd": 0.0061,
        "usage": {"input_tokens": 2, "output_tokens": 9, "cache_read_input_tokens": 0,
                  "cache_creation_input_tokens": 739, "service_tier": "standard"},
        **overrides,
    })


class ClaudeBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        for p in (patch.object(triage, "STATE", self.state),
                  patch.object(runner, "USAGE", self.state / "usage.jsonl"),
                  patch.dict(os.environ)):
            p.start()
            self.addCleanup(p.stop)
        # A developer's shell (e.g. inside a Claude Code session) may set these; tests start clean.
        for name in runner.CLAUDE_PROVIDER_ENV:
            os.environ.pop(name, None)
        self.rules = triage.load_rules(triage.ROOT / "rules.example.json")
        self.cfg = runner.load_config(triage.ROOT / "classifier.json", cli="claude")
        self.messages = [
            {"id": "a1", "thread": "t1", "subject": "Synthetic request", "snippet": "Please approve the proposal."},
        ]
        self.output = {"a1": {"tag": "FYI", "task": None, "confidence": 0.9, "needs_context": False}}

    def call(self, stdout, returncode=0, cfg=None):
        result = SimpleNamespace(returncode=returncode, stdout=stdout)
        with patch.object(runner.subprocess, "run", return_value=result) as process:
            output = runner.call_model(self.messages, self.rules, cfg or self.cfg, self.cfg["cheap_model"])
        return output, process

    def last_usage(self):
        return json.loads(runner.USAGE.read_text().splitlines()[-1])

    def test_config_selects_claude_and_validates_its_block(self):
        self.assertEqual((self.cfg["cli"], self.cfg["binary"], self.cfg["auth"]), ("claude", "claude", "subscription"))
        raw = json.loads((triage.ROOT / "classifier.json").read_text())
        path = self.state / "cfg.json"
        for key, value in (("auth", "oauth"), ("max_budget_usd_per_call", 0),
                           ("max_budget_usd_per_call", "1"), ("escalation_model", ""), ("extra", 1)):
            bad = json.loads(json.dumps(raw))
            bad["providers"]["claude"][key] = value
            triage.write_json(path, bad)
            with self.assertRaises(ValueError, msg=key):
                runner.load_config(path)  # inactive blocks are validated too

    def test_cache_key_follows_selected_cli_only(self):
        message = self.messages[0]
        copilot = runner.load_config(triage.ROOT / "classifier.json")
        key = runner.cache_key(message, self.rules, self.cfg)
        self.assertNotEqual(key, runner.cache_key(message, self.rules, copilot))
        self.assertNotEqual(key, runner.cache_key(message, self.rules, {**self.cfg, "cheap_model": "other"}))
        raw = json.loads((triage.ROOT / "classifier.json").read_text())
        raw["providers"]["copilot"]["cheap_model"] = "changed"
        path = self.state / "cfg.json"
        triage.write_json(path, raw)
        self.assertEqual(key, runner.cache_key(message, self.rules, runner.load_config(path, cli="claude")))

    def test_command_is_isolated_and_mail_stays_on_stdin(self):
        output, process = self.call(claude_result(json.dumps(self.output)))
        self.assertEqual(output, self.output)
        command = process.call_args.args[0]
        self.assertEqual(command[:2], ["claude", "-p"])
        self.assertEqual(command[command.index("--tools") + 1], "")
        self.assertEqual(command[command.index("--output-format") + 1], "json")
        self.assertEqual(command[command.index("--setting-sources") + 1], "project")
        self.assertEqual(command[command.index("--max-budget-usd") + 1], "0.25")
        for flag in ("--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
            self.assertIn(flag, command)
        self.assertNotIn("--bare", command)
        self.assertNotIn("--dangerously-skip-permissions", command)
        self.assertFalse(any("Synthetic" in part or "approve" in part for part in command))
        stdin = process.call_args.kwargs["input"]
        self.assertIn("Please approve the proposal.", stdin)
        self.assertIn("FYI", command[command.index("--system-prompt") + 1])
        self.assertNotEqual(process.call_args.kwargs["cwd"], str(triage.ROOT))

    def test_subscription_strips_api_key_and_api_key_mode_uses_bare(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test", "ANTHROPIC_AUTH_TOKEN": "tok"}):
            _, process = self.call(claude_result(json.dumps(self.output)))
            env = process.call_args.kwargs["env"]
            self.assertNotIn("ANTHROPIC_API_KEY", env)
            self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)
            self.assertEqual(env["DISABLE_ERROR_REPORTING"], "1")
            _, process = self.call(claude_result(json.dumps(self.output)), cfg={**self.cfg, "auth": "api_key"})
            self.assertIn("--bare", process.call_args.args[0])
            self.assertEqual(process.call_args.kwargs["env"]["ANTHROPIC_API_KEY"], "sk-test")
        with patch.dict(os.environ, {}, clear=True), patch.object(runner.subprocess, "run") as process:
            with self.assertRaises(ValueError):
                runner.call_model(self.messages, self.rules, {**self.cfg, "auth": "api_key"}, "m")
        process.assert_not_called()

    def test_provider_overrides_are_refused_before_spawning(self):
        for name in runner.CLAUDE_PROVIDER_ENV:
            with patch.dict(os.environ, {name: "1"}), patch.object(runner.subprocess, "run") as process:
                with self.assertRaises(ValueError, msg=name):
                    runner.call_model(self.messages, self.rules, self.cfg, "m")
            process.assert_not_called()

    def test_parse_accepts_plain_and_fenced_json(self):
        self.assertEqual(runner.parse_claude_response(claude_result('{"a": 1}')), {"a": 1})
        self.assertEqual(runner.parse_claude_response(claude_result('```json\n{"a": 1}\n```')), {"a": 1})

    def test_parse_rejects_errors_tools_and_non_json(self):
        for stdout in (
            "not json", "[]", json.dumps({"type": "other"}),
            claude_result("{}", is_error=True), claude_result("{}", subtype="error_max_turns"),
            claude_result("{}", num_turns=2), claude_result("{}", permission_denials=[{"tool_name": "Bash"}]),
            claude_result(None), claude_result("Here you go: {}"),
        ):
            with self.assertRaises(ValueError, msg=stdout[:60]):
                runner.parse_claude_response(stdout)

    def test_failures_record_status_and_never_echo_output(self):
        with self.assertRaises(ValueError) as error:
            self.call(claude_result("sensitive words, not json"))
        self.assertNotIn("sensitive", str(error.exception))
        self.assertEqual(self.last_usage()["status"], "invalid_json")
        with self.assertRaises(RuntimeError) as error:
            self.call(claude_result("sensitive", subtype="error_max_budget_usd", is_error=True), returncode=1)
        self.assertIn("error_max_budget_usd", str(error.exception))
        self.assertNotIn("sensitive", str(error.exception))
        self.assertEqual(self.last_usage()["status"], "cli_error")
        with self.assertRaises(RuntimeError) as error:
            self.call(json.dumps({"subtype": "Sensitive Subject Line"}), returncode=1)
        self.assertNotIn("Sensitive", str(error.exception))
        with patch.object(runner.subprocess, "run", side_effect=subprocess.TimeoutExpired("claude", 1)):
            with self.assertRaises(RuntimeError):
                runner.call_model(self.messages, self.rules, self.cfg, "m")
        self.assertEqual(self.last_usage()["status"], "timeout")
        self.assertIsNone(self.last_usage()["cli_usage"])

    def test_usage_is_sanitized_and_reported_per_cli(self):
        self.call(claude_result(json.dumps(self.output)))
        entry = self.last_usage()
        self.assertEqual(entry["cli"], "claude")
        self.assertEqual(entry["cli_usage"], {
            "tokens": {"input": 2, "output": 9, "cache_read": 0, "cache_write": 739}, "cost_usd": 0.0061,
        })
        with runner.USAGE.open("a") as f:  # pre-selection entries have no "cli" field
            f.write(json.dumps({"model": "gpt-6-luna", "status": "ok", "cli_usage": None}) + "\n")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            runner.usage_report()
        report = json.loads(output.getvalue())
        self.assertEqual(report["claude/claude-haiku-5-5"]["cost_usd"], 0.0061)
        self.assertEqual(report["copilot/gpt-6-luna"]["missing_usage"], 1)


if __name__ == "__main__":
    unittest.main()
