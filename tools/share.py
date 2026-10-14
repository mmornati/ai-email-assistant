#!/usr/bin/env python3
"""Create an allowlisted ZIP without private runtime data or active mailbox rules."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = (
    "README.md", "LICENSE", "SECURITY.md", "CONTRIBUTING.md", ".gitignore", "Makefile",
    "triage.py", "runner.py", "schedule.py", "mail_setup.py",
    "classifier.json", "rules.example.json",
    "scripts/setup-macos.sh",
    "tools/share.py", "tools/benchmark.py", "tools/benchmark/fixtures.json",
    "tools/benchmark/requirements.txt", "tools/benchmark/requirements.lock",
    "tests/__init__.py", "tests/test_triage.py", "tests/test_benchmark.py", "tests/test_share.py",
    "tests/test_mail_setup.py", "tests/test_schedule.py", "tests/test_setup_script.py",
    "tests/test_engine.py", "tests/test_providers.py",
    ".github/skills/mail-setup/SKILL.md", ".github/skills/mail-triage/SKILL.md",
    # Identical copies for Claude Code, which reads skills from .claude/skills/.
    ".claude/skills/mail-setup/SKILL.md", ".claude/skills/mail-triage/SKILL.md",
    "docs/README.md", "docs/getting-started.md", "docs/how-it-works.md", "docs/configuration.md",
    "docs/classifier-cli.md", "docs/scheduling.md", "docs/interactive-review.md",
    "docs/costs.md", "docs/operations.md", "docs/sharing.md", "docs/assets/banner.svg",
    "docs/adr/0001-laya-vs-luna.md", "docs/adr/0002-selectable-classifier-cli.md",
)


def package(output: Path, root: Path = ROOT):
    if output.is_symlink() or output.suffix.lower() != ".zip":
        raise ValueError("output must be a non-symlink .zip path")
    payload = {}
    for name in FILES:
        source = root / name
        if (source.is_symlink() or not source.is_file()
                or not source.resolve().is_relative_to(root.resolve())):
            raise ValueError(f"missing or symbolic-link distribution file: {name}")
        payload[name] = source.read_bytes()
    starter = json.loads(payload["rules.example.json"])
    for tag in starter["tags"]:
        if any(tag[key] for key in ("match", "on_tag", "sweep", "on_task_done")):
            raise ValueError("starter rules must not contain mailbox queries or cleanup actions")
    payload["rules.json"] = payload["rules.example.json"]
    json.loads(payload["classifier.json"])
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".mail-share-", delete=False) as destination:
            temporary = Path(destination.name)
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, content in payload.items():
                    archive.writestr(f"ai-mail-assistant/{name}", content)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("archive integrity check failed")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return len(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "ai-mail-assistant.zip")
    args = parser.parse_args()
    count = package(args.output)
    print(f"Created {args.output.resolve()} ({count} files); private state and active rules excluded.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        sys.exit(f"packaging failed: {error}")
