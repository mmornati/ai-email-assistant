import contextlib
import io
import json
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import schedule


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.target = self.root / "LaunchAgents" / f"{schedule.LABEL}.plist"
        for p in (patch.object(schedule, "ROOT", self.root), patch.object(schedule, "TARGET", self.target),
                  patch.object(schedule.sys, "platform", "darwin"),
                  patch.object(schedule.shutil, "which", return_value="/usr/bin/true")):
            p.start()
            self.addCleanup(p.stop)
        self.launchctl = patch.object(schedule, "launchctl", return_value="").start()
        self.write_config("copilot")
        self.addCleanup(patch.stopall)

    def write_config(self, cli, **claude):
        raw = json.loads((Path(schedule.__file__).parent / "classifier.json").read_text())
        raw["cli"] = cli
        raw["providers"]["claude"].update(claude)
        (self.root / "classifier.json").write_text(json.dumps(raw))

    def main(self, *argv):
        with patch.object(sys, "argv", ["schedule.py", *argv]), contextlib.redirect_stdout(io.StringIO()) as out:
            schedule.main()
        return out.getvalue()

    def test_render_is_a_valid_plist_and_installs_nothing(self):
        job = plistlib.loads(self.main("render").encode())
        self.assertEqual(job["Label"], schedule.LABEL)
        self.assertEqual(job["ProgramArguments"][1:], [str(self.root / "runner.py"), "--scheduled", "--apply"])
        self.assertFalse(self.target.exists())
        self.launchctl.assert_not_called()

    def test_logs_stay_in_private_state(self):
        job = schedule.definition(sys.executable)
        for key in ("StandardOutPath", "StandardErrorPath"):
            self.assertEqual(Path(job[key]).parent, self.root / "state")

    def test_install_writes_plist_and_bootstraps_without_running(self):
        self.main("install", "--dry-run")
        job = plistlib.loads(self.target.read_bytes())
        self.assertNotIn("--apply", job["ProgramArguments"])
        self.assertFalse(job["RunAtLoad"])
        self.assertEqual((self.root / "state").stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.launchctl.call_args_list[0].args[0], "bootstrap")

    def test_install_refuses_to_overwrite(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text("existing")
        with self.assertRaises(ValueError):
            self.main("install")
        self.assertEqual(self.target.read_text(), "existing")

    def test_install_requires_cli_tools(self):
        with patch.object(schedule.shutil, "which", return_value=None), self.assertRaises(ValueError):
            self.main("install")
        self.assertFalse(self.target.exists())

    def test_model_free_install_does_not_need_copilot(self):
        (self.root / "classifier.json").unlink()
        with patch.object(schedule.shutil, "which", side_effect=lambda name: name == "gws" or None):
            self.main("install", "--no-model")
        self.assertIn("--no-model", plistlib.loads(self.target.read_bytes())["ProgramArguments"])

    def test_install_checks_the_configured_cli(self):
        for cli in ("copilot", "claude"):
            self.write_config(cli)
            other = {"copilot": "claude", "claude": "copilot"}[cli]
            with patch.object(schedule.shutil, "which", side_effect=lambda name: name != cli or None), \
                    self.assertRaises(ValueError) as error:
                self.main("install")
            self.assertIn(f"({cli})", str(error.exception))
            with patch.object(schedule.shutil, "which", side_effect=lambda name: name != other or None):
                self.assertIn(f"({cli})", self.main("install"))
            self.target.unlink()

    def test_install_refuses_api_key_auth_and_invalid_config(self):
        self.write_config("claude", auth="api_key")
        with self.assertRaises(ValueError) as error:
            self.main("install")
        self.assertIn("subscription", str(error.exception))
        (self.root / "classifier.json").write_text("{}")
        with self.assertRaises(ValueError):
            self.main("install")
        self.assertFalse(self.target.exists())
        self.assertIn("runner.py", self.main("render"))  # rendering never reads the classifier config

    def test_uninstall(self):
        with self.assertRaises(ValueError):
            self.main("uninstall")
        self.target.parent.mkdir(parents=True)
        self.target.write_text("x")
        self.main("uninstall")
        self.assertFalse(self.target.exists())
        self.assertEqual(self.launchctl.call_args.args[0], "bootout")

    def test_other_platforms_are_rejected(self):
        with patch.object(schedule.sys, "platform", "linux"), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.main("render")


if __name__ == "__main__":
    unittest.main()
