#!/usr/bin/env python3
"""Render, install, inspect, or remove the local macOS mail-triage schedule."""
from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LABEL = "local.ai-mail-assistant"
TARGET = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def calendar():
    return [{"Weekday": day, "Hour": hour, "Minute": 0}
            for day in range(1, 6) for hour in range(8, 20)]


def definition(python, no_model=False, dry_run=False):
    args = [str(Path(python).resolve()), str(ROOT / "runner.py"), "--scheduled"]
    if not dry_run:
        args.append("--apply")
    if no_model:
        args.append("--no-model")
    return {
        "Label": LABEL,
        "ProgramArguments": args,
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONUNBUFFERED": "1"},
        "StartCalendarInterval": calendar(),
        "RunAtLoad": False,
        "StandardOutPath": str(ROOT / "state" / "schedule.log"),
        "StandardErrorPath": str(ROOT / "state" / "schedule-error.log"),
    }


def launchctl(*args):
    result = subprocess.run(["launchctl", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"launchctl {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["render", "install", "status", "uninstall"])
    parser.add_argument("--python", default=sys.executable, help="absolute interpreter path recorded in the job")
    parser.add_argument("--no-model", action="store_true", help="install a strictly model-free rules/cache schedule")
    parser.add_argument("--dry-run", action="store_true", help="schedule previews instead of mailbox mutations")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("this scheduler is for macOS; use runner.py with your platform's scheduler")
    os.umask(0o077)
    service = f"gui/{os.getuid()}/{LABEL}"
    definition_ = definition(args.python, args.no_model, args.dry_run)
    if args.command == "render":
        print(plistlib.dumps(definition_).decode(), end="")
    elif args.command == "status":
        print(launchctl("print", service))
    elif args.command == "install":
        if not Path(definition_["ProgramArguments"][0]).is_file() or not shutil.which("gws"):
            raise ValueError("a valid interpreter and gws on PATH are required")
        if not args.no_model and not shutil.which("copilot"):
            raise ValueError("Copilot CLI must be available on PATH")
        if TARGET.exists():
            raise ValueError(f"{TARGET} already exists; inspect it, then uninstall before replacing")
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        (ROOT / "state").mkdir(exist_ok=True, mode=0o700)
        with TARGET.open("xb") as f:
            plistlib.dump(definition_, f)
        try:
            launchctl("bootstrap", f"gui/{os.getuid()}", str(TARGET))
            launchctl("print", service)
        except RuntimeError:
            # Keep the generated file for diagnosis; do not pretend installation succeeded.
            raise
        print(f"Installed {TARGET}; weekdays hourly 08:00-19:00 local time; no immediate run.")
    else:
        if not TARGET.exists():
            raise ValueError(f"no installed schedule at {TARGET}")
        launchctl("bootout", f"gui/{os.getuid()}", str(TARGET))
        TARGET.unlink()
        print(f"Removed {TARGET}; mailbox and state files are unchanged.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as e:
        sys.exit(f"schedule failed: {e}")
