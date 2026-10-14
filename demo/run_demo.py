#!/usr/bin/env python3
"""Run the real engine end to end on an invented mailbox, with no Google account and no model.

    python3 demo/run_demo.py                      # prints each step, keeps nothing
    python3 demo/run_demo.py --out run.json       # also writes the snapshot the website and film are drawn from

A throwaway workspace gets copies of triage.py, runner.py and classifier.json plus the demo rules.
`demo/fakes/` is put first on PATH, so `gws` and `copilot` are stand-ins: the mailbox is a JSON file and
the classifier answers from a script. Everything else, including validation, caching, tasks, sweeps
and the summary, is the production code path.
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from demo_mailbox import MESSAGES, OWNER, RULES  # noqa: E402

SHOWN_ROOT = "~/ai-email-assistant"


def hex_id(n):
    return hashlib.sha256(f"demo-{n}".encode()).hexdigest()[:16]


def seed(now):
    messages, answers = [], {}
    for n, m in enumerate(MESSAGES):
        mid = hex_id(n)
        when = now - m["hours"] * 3600
        headers = {"From": m["sender"], "To": OWNER, "Subject": m["subject"],
                   "Date": email.utils.formatdate(when, localtime=True)}
        if m.get("list"):
            headers["List-Unsubscribe"] = "<mailto:unsubscribe@list.example>"
        labels = ["INBOX", "UNREAD"] + (["STARRED"] if m.get("starred") else [])
        messages.append({"id": mid, "threadId": mid, "labelIds": labels, "headers": headers,
                         "snippet": m["snippet"], "body": m.get("body", m["snippet"]),
                         "internalDate": int(when * 1000)})
        if "model" in m:
            answers[mid] = m["model"]
    labels = [{"id": name, "name": name} for name in ("INBOX", "UNREAD", "STARRED", "IMPORTANT", "TRASH", "SENT")]
    return {"messages": messages, "labels": labels, "tasklists": [{"id": "list1", "title": "My Tasks"}],
            "tasks": [], "calls": []}, answers


def mailbox_view(db, now):
    names = {l["id"]: l["name"] for l in db["labels"]}
    rows = []
    for m in sorted(db["messages"], key=lambda m: -m["internalDate"]):
        name, address = email.utils.parseaddr(m["headers"]["From"])
        rows.append({
            "id": m["id"], "from": name or address, "address": address, "subject": m["headers"]["Subject"],
            "snippet": m["snippet"], "hours": round((now * 1000 - m["internalDate"]) / 3600000, 1),
            "inbox": "INBOX" in m["labelIds"], "unread": "UNREAD" in m["labelIds"],
            "starred": "STARRED" in m["labelIds"],
            "tags": [names[l][3:] for l in m["labelIds"] if names.get(l, "").startswith("AI/")],
        })
    return rows


class Demo:
    def __init__(self, workspace: Path, verbose: bool):
        self.ws, self.verbose = workspace, verbose
        self.state = workspace / "demo-mailbox.json"
        self.answers = workspace / "demo-answers.json"
        self.model_log = workspace / "demo-model-calls.jsonl"
        for name in ("triage.py", "runner.py", "classifier.json"):
            shutil.copy2(ROOT / name, workspace / name)
        (workspace / "rules.json").write_text(json.dumps(RULES, indent=1))
        self.now = time.time()
        db, answers = seed(self.now)
        self.state.write_text(json.dumps(db, ensure_ascii=False, indent=1))
        self.answers.write_text(json.dumps(answers, ensure_ascii=False))
        self.env = {**os.environ, "PATH": f"{HERE / 'fakes'}{os.pathsep}{os.environ['PATH']}",
                    "DEMO_STATE": str(self.state), "DEMO_ANSWERS": str(self.answers),
                    "DEMO_MODEL_LOG": str(self.model_log), "NO_COLOR": "1"}
        for k in ("COPILOT_PROVIDER_BASE_URL", "COPILOT_PROVIDER_TYPE"):
            self.env.pop(k, None)

    def db(self):
        return json.loads(self.state.read_text())

    def model_calls(self):
        if not self.model_log.exists():
            return []
        return [json.loads(l) for l in self.model_log.read_text().splitlines()]

    def run(self, *args):
        command = [sys.executable, *args]
        p = subprocess.run(command, cwd=self.ws, env=self.env, capture_output=True, text=True)
        text = (p.stdout + p.stderr).replace(str(self.ws), SHOWN_ROOT).rstrip()
        shown = "python3 " + " ".join(args)
        if self.verbose:
            print(f"\n$ {shown}\n{text}")
        return {"command": shown, "exit": p.returncode, "output": text}

    def step(self, name, title, *commands):
        before_calls = len(self.model_calls())
        transcript = [self.run(*c) for c in commands]
        summary_file = self.ws / "state" / "summary.json"
        summary = json.loads(summary_file.read_text()) if summary_file.exists() else None
        calls = self.model_calls()[before_calls:]
        db = self.db()
        return {"name": name, "title": title, "transcript": transcript, "summary": summary,
                "model_calls": [{"model": c["model"], "messages": len(c["ids"]), "prompt_chars": c["prompt_chars"]}
                                for c in calls],
                "mailbox": mailbox_view(db, self.now),
                "tasks": [{"title": t["title"], "due": t["due"][:10], "status": t["status"]} for t in db["tasks"]]}

    def complete_task(self, prefix):
        db = self.db()
        for t in db["tasks"]:
            if t["title"].startswith(prefix):
                t["status"] = "completed"
        self.state.write_text(json.dumps(db, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, help="write the snapshot JSON here")
    ap.add_argument("--workspace", type=Path, help="keep the workspace in this (new or empty) folder")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    if sys.version_info < (3, 10):
        sys.exit("the engine needs Python 3.10+")
    with tempfile.TemporaryDirectory(prefix="mail-demo-") as tmp:
        ws = (args.workspace or Path(tmp)).resolve()
        ws.mkdir(parents=True, exist_ok=True)
        demo = Demo(ws, not args.quiet)
        start = demo.step("arrive", "The inbox before the first run")
        steps = [
            start,
            demo.step("preview", "Dry run: rules plan, the model classifies what rules cannot",
                      ("triage.py", "run"), ("runner.py",)),
            demo.step("apply", "Applied run: cached decisions reused, labels and tasks written",
                      ("runner.py", "--apply"), ("runner.py", "--usage-report")),
            demo.step("quiet", "The next hour: nothing new, no model call", ("runner.py", "--apply")),
        ]
        demo.complete_task("Approve the Q4 hiring plan")
        steps.append(demo.step("done", "A completed task archives its thread", ("runner.py", "--apply")))
        calls = demo.model_calls()
        first = {i for c in calls if "luna" in c["model"] for i in c["ids"]}
        second = {i for c in calls if "sol" in c["model"] for i in c["ids"]}
        tagged = {m["id"] for m in steps[2]["mailbox"] if m["tags"]}

        def route(mid):
            if mid in second:
                return "escalated" if mid in tagged else "waiting"
            if mid in first:
                return "model"
            return "rule" if mid in tagged else "outside"

        snapshot = {
            "generated": dt.date.today().isoformat(),
            "weekday": dt.date.today().strftime("%A"),
            "synthetic": "Every person, company, address and message in this run is invented.",
            "owner": OWNER,
            "rules": [{"name": t["name"], "match": t["match"], "on_tag": t["on_tag"],
                       "sweep": t["sweep"], "task": t["task"]} for t in RULES["tags"]],
            "classifier": json.loads((ROOT / "classifier.json").read_text()),
            "routes": {m["id"]: route(m["id"]) for m in start["mailbox"]},
            "steps": steps,
        }
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n")
        if not args.quiet:
            for s in steps[1:]:
                st = s["summary"] or {}
                print(f"\n[{s['name']}] {s['title']}: status={st.get('status')} model calls={len(s['model_calls'])} "
                      f"tasks={len(s['tasks'])} in inbox={sum(m['inbox'] for m in s['mailbox'])}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
