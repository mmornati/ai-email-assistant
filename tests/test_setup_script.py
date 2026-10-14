import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "setup-macos.sh"


def stub(directory: Path, name: str, body: str):
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)


class SetupScriptTests(unittest.TestCase):
    """Hermetic: a fake project and stubbed system tools; nothing is installed or logged into."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / "project"
        (self.project / "scripts").mkdir(parents=True)
        shutil.copy(SCRIPT, self.project / "scripts" / SCRIPT.name)
        shutil.copy(ROOT / "rules.example.json", self.project / "rules.example.json")
        self.bin = Path(temp.name) / "bin"
        self.home = Path(temp.name) / "home"
        self.home.mkdir()
        self.bin.mkdir()
        self.brew_log = Path(temp.name) / "brew.log"
        stub(self.bin, "uname", "echo Darwin")
        stub(self.bin, "sw_vers", "echo 99.0")
        prefix = Path(temp.name) / "brew-prefix"
        (prefix / "bin").mkdir(parents=True)
        stub(prefix / "bin", "python3", "exit 0")  # passes the 3.10+ check whatever runs the tests
        stub(self.bin, "brew", f'echo "$*" >> "{self.brew_log}"\n'
                               'case "$1" in --version) echo "Homebrew 9.9.9";; '
                               f'--prefix) echo "{prefix}";; list) exit 1;; esac')

    def run_script(self, *args):
        # Only the basic utilities the script needs, so real gws/gcloud/copilot on the host are invisible.
        for tool in ("dirname", "head", "awk", "chmod", "mkdir", "cp", "cat", "stat"):
            if not (self.bin / tool).exists():
                (self.bin / tool).symlink_to(shutil.which(tool))
        env = {"PATH": str(self.bin), "HOME": str(self.home)}
        return subprocess.run([shutil.which("bash"), str(self.project / "scripts" / SCRIPT.name), *args],
                              capture_output=True, text=True, env=env, timeout=60)

    def test_script_is_valid_bash_and_shellcheck_clean(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        if shutil.which("shellcheck"):
            subprocess.run(["shellcheck", str(SCRIPT)], check=True)

    def test_help_and_unknown_option(self):
        self.assertEqual(self.run_script("--help").returncode, 0)
        result = self.run_script("--bogus")
        self.assertEqual(result.returncode, 64)
        self.assertIn("unknown option", result.stderr)

    def test_refuses_other_platforms(self):
        stub(self.bin, "uname", "echo Linux")
        result = self.run_script("--dry-run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("macOS", result.stderr)

    def test_requires_homebrew_and_never_pipes_installers(self):
        (self.bin / "brew").unlink()
        result = self.run_script("--dry-run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("https://brew.sh", result.stderr)
        self.assertNotIn("curl", SCRIPT.read_text())

    def test_dry_run_changes_nothing(self):
        result = self.run_script("--dry-run", "--skip-auth", "--skip-verify")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted(p.name for p in self.project.iterdir()), ["rules.example.json", "scripts"])
        self.assertNotIn("install", self.brew_log.read_text())
        self.assertIn("brew install googleworkspace-cli", result.stdout)
        self.assertIn("brew install --cask gcloud-cli", result.stdout)

    def test_default_cli_is_copilot_and_selection_is_left_alone(self):
        result = self.run_script("--dry-run", "--skip-auth", "--skip-verify")
        self.assertIn("brew install --cask copilot-cli", result.stdout)
        self.assertNotIn("claude-code", result.stdout)
        self.assertNotIn("--select-cli", result.stdout)

    def test_cli_claude_installs_claude_code_and_selects_it(self):
        result = self.run_script("--dry-run", "--skip-verify", "--cli", "claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("brew install --cask claude-code", result.stdout)
        self.assertNotIn("copilot-cli", result.stdout)
        self.assertIn("runner.py --select-cli claude", result.stdout)
        self.assertIn("claude auth login", result.stdout)
        self.assertNotIn("copilot login", result.stdout)
        self.assertNotIn("brew install", self.brew_log.read_text())

    def test_cli_option_is_validated_and_model_cli_can_be_skipped(self):
        result = self.run_script("--dry-run", "--cli", "gpt")
        self.assertEqual(result.returncode, 64)
        self.assertIn("copilot or claude", result.stderr)
        for flag in ("--no-model-cli", "--skip-copilot"):
            result = self.run_script("--dry-run", "--skip-verify", "--cli", "claude", flag)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("claude-code", result.stdout)
            self.assertNotIn("claude auth login", result.stdout)

    def test_conflicting_gws_formula_is_rejected(self):
        stub(self.bin, "brew", 'case "$1" in --version) echo "Homebrew 9.9.9";; '
                               'list) [ "$3" = gws ] && exit 0; exit 1;; esac')
        result = self.run_script("--dry-run", "--skip-auth", "--skip-verify")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("brew uninstall gws", result.stderr)

    def test_creates_private_state_and_keeps_existing_rules(self):
        for name in ("gws", "gcloud", "copilot"):
            stub(self.bin, name, "exit 0")
        result = self.run_script("--skip-auth", "--skip-verify")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.project / "state").stat().st_mode & 0o777, 0o700)
        rules = self.project / "rules.json"
        self.assertEqual(rules.read_text(), (self.project / "rules.example.json").read_text())
        self.assertEqual(rules.stat().st_mode & 0o077, 0)
        rules.write_text("{}")
        self.assertEqual(self.run_script("--skip-auth", "--skip-verify").returncode, 0)
        self.assertEqual(rules.read_text(), "{}")

    def test_task_list_option_only_changes_the_list_name(self):
        for name in ("gws", "gcloud", "copilot"):
            stub(self.bin, name, "exit 0")
        (self.bin / "python3").symlink_to(sys.executable)  # the real interpreter edits rules.json
        task_list = 'Work "follow-ups" ✓'
        result = self.run_script("--skip-auth", "--skip-verify", "--task-list", task_list)
        self.assertEqual(result.returncode, 0, result.stderr)
        rules = json.loads((self.project / "rules.json").read_text())
        starter = json.loads((self.project / "rules.example.json").read_text())
        self.assertEqual(rules["tasks"]["list"], task_list)
        starter["tasks"]["list"] = task_list
        self.assertEqual(rules, starter)

    def test_check_reports_missing_pieces_and_changes_nothing(self):
        result = self.run_script("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("✗ Google Workspace CLI", result.stdout)
        self.assertIn("brew install googleworkspace-cli", result.stdout)
        self.assertIn("✗ rules.json", result.stdout)
        self.assertEqual(sorted(p.name for p in self.project.iterdir()), ["rules.example.json", "scripts"])
        self.assertFalse(self.brew_log.exists() and "install" in self.brew_log.read_text())

    def test_check_passes_after_setup(self):
        for name in ("gws", "gcloud", "copilot"):
            stub(self.bin, name, "exit 0")
        self.assertEqual(self.run_script("--skip-auth", "--skip-verify").returncode, 0)
        result = self.run_script("--check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("✓ state/ is private (0700)", result.stdout)
        self.assertIn("ready", result.stdout)

    def test_requests_least_privilege_scopes(self):
        text = SCRIPT.read_text()
        self.assertIn("auth/gmail.modify", text)
        self.assertNotRegex(text, r"auth/(drive|gmail\.send|cloud-platform)")
        self.assertNotIn("--apply", [line.strip() for line in text.splitlines() if line.strip().startswith("run ")])


if __name__ == "__main__":
    unittest.main()
