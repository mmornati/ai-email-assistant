import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import mail_setup
import triage


class MailSetupTests(unittest.TestCase):
    def setUp(self):
        self.rules = json.loads((triage.ROOT / "rules.example.json").read_text())
        self.samples = [{
            "sender": "news@example.invalid", "bulk": True, "subject": f"Newsletter {i}",
            "snippet": "Informational newsletter", "date": "", "list_id": "<news.example.invalid>",
        } for i in range(6)]
        self.report = {
            "batch_id": "setup-batch", "created": time.time(),
            "rules_version": triage.rules_version(self.rules),
            "groups": mail_setup.group_samples(self.samples, 20),
        }
        group = self.report["groups"][0]
        self.selections = {
            "batch_id": "setup-batch",
            "selections": [{
                "group_id": group["id"], "tag": "Newsletter",
                "example_tags": {e["id"]: "Newsletter" for e in group["examples"]},
            }],
        }

    def test_group_samples_are_bounded_and_separate(self):
        groups = mail_setup.group_samples(self.samples, 1)
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertTrue(group["eligible"])
        self.assertEqual(len(group["examples"]), 5)
        development = {e["subject"] for e in group["examples"] if e["split"] == "development"}
        validation = {e["subject"] for e in group["examples"] if e["split"] == "validation"}
        self.assertFalse(development & validation)
        self.assertEqual((len(development), len(validation)), (3, 2))

    def test_nonbulk_or_too_few_samples_are_not_eligible(self):
        for samples in (self.samples[:3], [{**s, "bulk": False} for s in self.samples]):
            group = mail_setup.group_samples(samples, 20)[0]
            self.assertFalse(group["eligible"])
            report = {**self.report, "groups": [group]}
            with self.assertRaises(ValueError):
                mail_setup.proposed_rules(self.rules, report, self.selections)

    def test_metadata_read_has_no_bodies_or_recipients(self):
        with patch.object(triage, "gws", return_value={
            "id": "private-id", "snippet": "x" * 500,
            "payload": {"headers": [
                {"name": "From", "value": "Mailing List <news@example.invalid>"},
                {"name": "List-Id", "value": "<news.example.invalid>"},
                {"name": "Subject", "value": "Weekly update"},
            ]},
        }) as api:
            sample = mail_setup.fetch_sample("private-id")
        self.assertTrue(sample["bulk"])
        self.assertEqual(len(sample["snippet"]), 300)
        self.assertNotIn("id", sample)
        params = api.call_args.kwargs["params"]
        self.assertEqual(params["format"], "metadata")
        self.assertNotIn("To", params["metadataHeaders"])
        self.assertNotIn("body", params["fields"])
        self.assertEqual(api.call_args.args, ("gmail", "users", "messages", "get"))

    def test_discovery_only_searches_and_reads_bounded_mail(self):
        with patch.object(triage, "search", return_value=["a", "b"]) as search, \
                patch.object(mail_setup, "fetch_sample", side_effect=self.samples[:2]) as fetch:
            report = mail_setup.discover(self.rules, 200, 30, 20)
        search.assert_called_once_with("newer_than:30d -in:sent -in:drafts -in:spam -in:trash", 200)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(report["sample_count"], 2)
        self.assertFalse(report["at_limit"])

    def test_sender_query_rejects_search_syntax(self):
        self.assertEqual(mail_setup.sender_of("List <NEWS@example.invalid>"), "news@example.invalid")
        for value in ("bad", "news@example.invalid OR from:person@example.invalid", "x@domain/*"):
            self.assertIsNone(mail_setup.sender_of(value))

    def test_sender_must_appear_verbatim_whatever_parseaddr_returns(self):
        with patch.object(mail_setup, "parseaddr", return_value=("", "news@example.invalidorfrom")):
            self.assertIsNone(mail_setup.sender_of("news@example.invalid OR from:person@example.invalid"))

    def test_append_preserves_all_existing_policies(self):
        original = copy.deepcopy(self.rules)
        proposed, changes = mail_setup.proposed_rules(self.rules, self.report, self.selections)
        self.assertEqual(self.rules, original)
        newsletter = next(t for t in proposed["tags"] if t["name"] == "Newsletter")
        self.assertEqual(newsletter["match"], ["from:news@example.invalid"])
        newsletter["match"] = []
        self.assertEqual(proposed, original)
        self.assertEqual(len(changes), 1)

    def test_disagreement_missing_examples_and_action_tags_fail(self):
        for edit in (
            lambda s: s["selections"][0]["example_tags"].update({"validation-1": "Action"}),
            lambda s: s["selections"][0]["example_tags"].pop("validation-2"),
            lambda s: s["selections"][0].update({"tag": "Action"}),
            lambda s: s["selections"][0].update({"tag": "FYI"}),
            lambda s: s["selections"][0].update({"query": "from:example.invalid"}),
        ):
            selections = copy.deepcopy(self.selections)
            edit(selections)
            with self.assertRaises(ValueError):
                mail_setup.proposed_rules(self.rules, self.report, selections)

    def test_stale_discovery_and_changed_rules_fail(self):
        for report in (
            {**self.report, "created": time.time() - 86401},
            {**self.report, "created": time.time() + 100},
            {**self.report, "rules_version": "changed"},
            {**self.report, "batch_id": "other"},
        ):
            with self.assertRaises(ValueError):
                mail_setup.proposed_rules(self.rules, report, self.selections)

    def test_duplicates_and_conflicting_rules(self):
        self.selections["selections"].append(copy.deepcopy(self.selections["selections"][0]))
        with self.assertRaises(ValueError):
            mail_setup.proposed_rules(self.rules, self.report, self.selections)
        self.selections["selections"].pop()
        for tag in ("Newsletter", "Promo"):
            rules = copy.deepcopy(self.rules)
            next(t for t in rules["tags"] if t["name"] == tag)["match"] = ["from:news@example.invalid"]
            report = {**self.report, "rules_version": triage.rules_version(rules)}
            if tag == "Newsletter":
                _, changes = mail_setup.proposed_rules(rules, report, self.selections)
                self.assertEqual(changes, [])
            else:
                with self.assertRaises(ValueError):
                    mail_setup.proposed_rules(rules, report, self.selections)

    def test_preview_does_not_change_rules_approve_saves_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            state.mkdir()
            rule_path = root / "rules.json"
            rule_path.write_text(json.dumps(self.rules))
            selections = state / "setup-selections.json"
            triage.write_json(selections, self.selections)
            triage.write_json(state / "setup-discovery.json", self.report)
            with patch.object(triage, "STATE", state), patch("builtins.print"), \
                    patch.object(triage, "gws") as api:
                for command, flags in (("preview", []), ("approve", []), ("approve", ["--apply"])):
                    with patch("sys.argv", ["mail_setup.py", command, "--rules", str(rule_path),
                                            "--selections", str(selections), *flags]):
                        mail_setup.main()
                    if not flags:
                        self.assertEqual(json.loads(rule_path.read_text()), self.rules)
                api.assert_not_called()
            backup = list(state.glob("rules.before-setup-*.json"))
            self.assertEqual(len(backup), 1)
            self.assertEqual(json.loads(backup[0].read_text()), self.rules)
            self.assertEqual(rule_path.stat().st_mode & 0o777, 0o600)
            new_rules = json.loads(rule_path.read_text())
            self.assertEqual(next(t for t in new_rules["tags"] if t["name"] == "Newsletter")["match"],
                             ["from:news@example.invalid"])


if __name__ == "__main__":
    unittest.main()
