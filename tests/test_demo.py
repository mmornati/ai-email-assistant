"""The website demo runs the production engine on an invented mailbox; keep it working and its story true."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run.json"
            subprocess.run([sys.executable, str(ROOT / "demo" / "run_demo.py"), "--quiet", "--out", str(out)],
                           check=True, capture_output=True, text=True)
            cls.steps = {s["name"]: s for s in json.loads(out.read_text())["steps"]}

    def test_rules_route_most_mail_and_the_model_sees_only_the_rest(self):
        preview = self.steps["preview"]
        self.assertEqual(preview["summary"]["pending"], 10)
        self.assertEqual([c["model"] for c in preview["model_calls"]], ["gpt-6-luna", "gpt-6.1-sol"])
        self.assertEqual(preview["model_calls"][1]["messages"], 3)
        self.assertFalse(preview["tasks"], "a dry run must not create tasks")

    def test_apply_reuses_the_preview_classifications(self):
        apply = self.steps["apply"]
        self.assertEqual(apply["model_calls"], [])
        self.assertEqual(apply["summary"]["cached"], 9)
        self.assertEqual(len(apply["tasks"]), 4)
        self.assertEqual(len(apply["summary"]["unresolved_ids"]), 1)
        self.assertEqual(apply["summary"]["rule_candidates"][0]["sender"], "events@summit.example")

    def test_unresolved_mail_stays_untagged_in_the_inbox(self):
        unresolved = self.steps["apply"]["summary"]["unresolved_ids"][0]
        row = next(m for m in self.steps["apply"]["mailbox"] if m["id"] == unresolved)
        self.assertTrue(row["inbox"])
        self.assertEqual(row["tags"], [])

    def test_quiet_hour_calls_no_model_and_completed_task_archives(self):
        self.assertEqual(self.steps["quiet"]["model_calls"], [])
        before = sum(m["inbox"] for m in self.steps["quiet"]["mailbox"])
        after = sum(m["inbox"] for m in self.steps["done"]["mailbox"])
        self.assertEqual(before - after, 1)

    def test_starred_mail_is_protected_from_sweeps(self):
        starred = next(m for m in self.steps["apply"]["mailbox"] if m["starred"])
        self.assertTrue(starred["inbox"])
        self.assertEqual(starred["tags"], ["Newsletter"])


if __name__ == "__main__":
    unittest.main()
