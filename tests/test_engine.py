"""Deterministic Gmail/Tasks engine behaviour, with the gws CLI mocked."""
import contextlib
import datetime as dt
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import triage


class EngineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.state = Path(temp.name)
        for p in (patch.object(triage, "STATE", self.state),
                  patch.object(triage, "JOURNAL", self.state / "journal.jsonl"),
                  patch.object(triage, "REPORT", triage.Report()),
                  patch.object(triage, "PLAN", [])):
            p.start()
            self.addCleanup(p.stop)
        self.rules = triage.load_rules(triage.ROOT / "rules.example.json")

    def test_labels_and_queries_are_derived_from_tag_names(self):
        tag = next(t for t in self.rules["tags"] if t["name"] == "Meeting/Invite")
        self.assertEqual(tag["label"], "AI/Meeting/Invite")
        self.assertEqual(tag["q"], "label:ai-meeting-invite")
        self.assertIn("-label:ai-action", triage.any_tag_excluded(self.rules))

    def test_missing_rules_explains_how_to_create_them(self):
        with self.assertRaises(FileNotFoundError) as error:
            triage.load_rules(self.state / "rules.json")
        self.assertIn("rules.example.json", str(error.exception))

    def test_action_labels(self):
        self.assertEqual(triage.action_labels(["archive", "mark_read", "star"]),
                         (["STARRED"], ["INBOX", "UNREAD"]))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            triage.action_labels(["unsubscribe"])

    def test_default_due_skips_weekends(self):
        tasks = triage.Tasks.__new__(triage.Tasks)
        tasks.cfg = {"default_due_business_days": 2}
        friday = dt.date(2026, 10, 9)

        class FakeDate(dt.date):
            @classmethod
            def today(cls):
                return friday

        with patch.object(triage.dt, "date", FakeDate):
            self.assertEqual(tasks.default_due(), "2026-10-13")

    def test_task_marker_round_trip(self):
        notes = "ctx\n\n[mail-triage thread=abc123 tag=Meeting/Notes on_done=archive,mark_read]"
        match = triage.MARKER.search(notes)
        self.assertEqual((match["thread"], match["tag"], match["on_done"]),
                         ("abc123", "Meeting/Notes", "archive,mark_read"))

    def test_dry_run_records_plan_and_never_calls_gws(self):
        with patch.object(triage, "gws") as gws, contextlib.redirect_stdout(io.StringIO()):
            triage.act(["m1"], ["archive", "trash"], False, "reason", ["Label_1"])
        gws.assert_not_called()
        self.assertEqual([op["op"] for op in triage.PLAN], ["modify", "trash"])
        self.assertIn("m1", triage.REPORT.gone)
        self.assertFalse(triage.JOURNAL.exists())

    def test_apply_is_journaled_in_chunks(self):
        ids = [f"m{i}" for i in range(triage.BATCH + 1)]
        with patch.object(triage, "gws", return_value={}) as gws, contextlib.redirect_stdout(io.StringIO()):
            triage.modify(ids, ["L"], ["INBOX"], True, "reason")
        self.assertEqual(gws.call_count, 2)
        entries = [json.loads(line) for line in triage.JOURNAL.read_text().splitlines()]
        self.assertEqual([len(e["ids"]) for e in entries], [triage.BATCH, 1])

    def test_undo_reverses_last_batches_only(self):
        triage.JOURNAL.write_text("".join(json.dumps(e) + "\n" for e in (
            {"ids": ["old"], "add": ["A"], "remove": ["INBOX"], "reason": "old"},
            {"ids": ["new"], "add": ["B"], "remove": ["INBOX"], "reason": "new"},
            {"ids": ["t"], "trash": True, "reason": "trash"},
        )))
        with patch.object(triage, "gws", return_value={}) as gws, contextlib.redirect_stdout(io.StringIO()):
            triage.cmd_undo(None, SimpleNamespace(n=2, apply=True))
        calls = [(c.args[3], c.kwargs.get("body")) for c in gws.call_args_list]
        self.assertEqual(calls[0][0], "untrash")
        self.assertEqual(calls[1], ("batchModify", {"ids": ["new"], "addLabelIds": ["INBOX"], "removeLabelIds": ["B"]}))
        self.assertEqual(len(triage.JOURNAL.read_text().splitlines()), 1)

    def test_undo_rejects_zero_batches(self):
        # `lines[-0:]` would otherwise select the whole journal.
        with patch.object(sys, "argv", ["triage.py", "undo", "-n", "0", "--apply"]), \
                patch.object(triage, "gws") as gws, contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit):
            triage.cli()
        gws.assert_not_called()

    def test_gws_retries_rate_limits_then_fails_closed(self):
        busy = subprocess.CompletedProcess([], 1, "", "429 rateLimitExceeded")
        done = subprocess.CompletedProcess([], 0, '{"ok": true}', "")
        with patch.object(triage.subprocess, "run", side_effect=[busy, done]) as run, \
                patch.object(triage.time, "sleep"):
            self.assertEqual(triage.gws("gmail", "x", params={"a": 1}), {"ok": True})
        self.assertEqual(run.call_args.args[0][:3], ["gws", "gmail", "x"])
        denied = subprocess.CompletedProcess([], 1, "", "403 insufficientPermissions")
        with patch.object(triage.subprocess, "run", return_value=denied) as run, \
                self.assertRaises(SystemExit):
            triage.gws("gmail", "x")
        run.assert_called_once()

    def test_search_paginates_up_to_limit(self):
        pages = [{"messages": [{"id": "1"}, {"id": "2"}], "nextPageToken": "p2"},
                 {"messages": [{"id": "3"}]}]
        with patch.object(triage, "gws", side_effect=pages) as gws:
            self.assertEqual(triage.search("in:inbox", 10), ["1", "2", "3"])
        self.assertEqual(gws.call_args.kwargs["params"]["pageToken"], "p2")

    def test_completed_task_archives_only_inbox_messages_of_its_thread(self):
        tasks = SimpleNamespace(name="My Tasks", by_thread=lambda: {
            "t1": {"status": "completed", "tag": "Action", "title": "Done", "on_done": "archive"},
            "t2": {"status": "needsAction", "tag": "Action", "title": "Open", "on_done": None},
        })
        thread = {"messages": [{"id": "a", "labelIds": ["INBOX"]}, {"id": "b", "labelIds": []}]}
        with patch.object(triage, "Tasks", return_value=tasks), \
                patch.object(triage, "gws", return_value=thread) as gws, \
                patch.object(triage, "act") as act, contextlib.redirect_stdout(io.StringIO()):
            triage.cmd_sync(self.rules, SimpleNamespace(apply=False))
        gws.assert_called_once()
        self.assertEqual(act.call_args.args[:3], (["a"], ["archive"], False))

    def test_starter_rules_take_no_action_on_completed_tasks(self):
        tasks = SimpleNamespace(name="My Tasks", by_thread=lambda: {
            "t1": {"status": "completed", "tag": "Action", "title": "Done", "on_done": None}})
        with patch.object(triage, "Tasks", return_value=tasks), patch.object(triage, "gws") as gws, \
                contextlib.redirect_stdout(io.StringIO()):
            triage.cmd_sync(self.rules, SimpleNamespace(apply=True))
        gws.assert_not_called()


if __name__ == "__main__":
    unittest.main()
