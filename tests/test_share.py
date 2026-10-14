import json
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

import share
import triage


class ShareTests(unittest.TestCase):
    def test_only_allowlisted_files_and_safe_starter_rules_are_shared(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            for name in share.FILES:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((share.ROOT / name).read_bytes())
            (root / "state").mkdir()
            sentinel = uuid.uuid4().hex
            (root / "state" / "pending.json").write_text(sentinel)
            (root / "rules.json").write_text(sentinel)
            (root / ".env").write_text(sentinel)
            (root / "unexpected.txt").write_text(sentinel)
            output = Path(directory) / "bundle.zip"
            self.assertEqual(share.package(output, root), len(share.FILES) + 1)
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()),
                                 {f"ai-mail-assistant/{name}" for name in (*share.FILES, "rules.json")})
                for name in archive.namelist():
                    self.assertNotIn(sentinel.encode(), archive.read(name))
                    self.assertNotIn(str(Path.home()).encode(), archive.read(name))
                rules = json.loads(archive.read("ai-mail-assistant/rules.json"))
                for tag in rules["tags"]:
                    for key in ("match", "on_tag", "sweep", "on_task_done"):
                        self.assertEqual(tag[key], [])
            self.assertEqual(share.package(output, root), len(share.FILES) + 1)
            self.assertEqual(list(output.parent.glob(".mail-share-*")), [])

    def test_starter_rules_load_and_keep_the_existing_taxonomy(self):
        starter = triage.load_rules(share.ROOT / "rules.example.json")
        self.assertEqual([t["name"] for t in starter["tags"]], [
            "Action", "Alerts", "GitHub-Admin", "Meeting/Invite", "Meeting/Notes", "Shares",
            "Admin", "Internal-Comms", "Newsletter", "Promo", "FYI", "Backlog",
        ])
        self.assertEqual(next(t for t in starter["tags"] if t["name"] == "Action")["task"], "always")

    def test_missing_source_does_not_create_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.zip"
            with self.assertRaises(ValueError):
                share.package(output, Path(directory))
            self.assertFalse(output.exists())

    def test_failed_rebuild_preserves_previous_zip_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle.zip"
            share.package(output)
            original = output.read_bytes()
            with patch.object(share.zipfile.ZipFile, "testzip", return_value="broken"):
                with self.assertRaises(ValueError):
                    share.package(output)
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(list(output.parent.glob(".mail-share-*")), [])

    def test_output_must_not_overwrite_source_or_follow_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.zip"
            target.write_text("preserved")
            link = Path(directory) / "link.zip"
            link.symlink_to(target)
            for output in (link, Path(directory) / "rules.json"):
                with self.assertRaises(ValueError):
                    share.package(output)
            self.assertEqual(target.read_text(), "preserved")


if __name__ == "__main__":
    unittest.main()
