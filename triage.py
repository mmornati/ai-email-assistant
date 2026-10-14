#!/usr/bin/env python3
"""AI mail triage for Gmail, driven by the `gws` CLI.

Pipeline:
  tag     apply rule-based tags (Gmail queries in rules.json)
  pending dump untagged inbox mail as compact JSON for an agent to classify
  decide  apply the agent's decisions (tag + optional Google Task) from decisions.json
  sync    for completed Google Tasks, apply the tag's on_task_done actions to the thread
  sweep   run each tag's follow-up actions (archive, mark_read, ...)
  run     sync + tag + sweep + pending (what the automation calls)
  undo    revert the last N applied batches from journal.jsonl

Every mutating command is a dry run unless --apply is given.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import fcntl
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state"
JOURNAL = STATE / "journal.jsonl"
PENDING = STATE / "pending.json"
REPORT_FILE = STATE / "dry-run.csv"
META_CACHE = STATE / "meta-cache.json"
_meta_cache: dict | None = None
BATCH = 1000
ACTIONS = {
    "archive": {"remove": ["INBOX"]},
    "mark_read": {"remove": ["UNREAD"]},
    "star": {"add": ["STARRED"]},
    "important": {"add": ["IMPORTANT"]},
    "trash": {},  # opt-in only; recoverable from Gmail Trash for 30 days, and via `undo`
}
MARKER = re.compile(r"\[mail-triage thread=(?P<thread>\w+) tag=(?P<tag>[\w/-]+)(?: on_done=(?P<on_done>[\w,]*))?\]")


def write_json(path: Path, data):
    path.parent.mkdir(exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8", opener=lambda p, flags: os.open(p, flags, 0o600)) as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    temporary.replace(path)


@contextmanager
def run_lock():
    STATE.mkdir(exist_ok=True, mode=0o700)
    with (STATE / "run.lock").open("a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit("another triage process is running; try again after it finishes")
        yield


def rules_version(rules):
    return hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()


def save_meta_cache():
    if _meta_cache:
        STATE.mkdir(exist_ok=True)
        write_json(META_CACHE, _meta_cache)


class Report:
    """Per-message plan of what a run does (or would do): written as CSV for review."""

    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.planned: dict[str, str] = {}  # id -> tag assigned in this run (not yet a Gmail label in dry run)
        self.gone: set[str] = set()        # ids that leave the inbox in this run

    def row(self, mid: str) -> dict:
        return self.rows.setdefault(mid, {"tag": "", "source": "", "actions": [], "task": ""})

    def tag(self, ids, tag: str, source: str):
        for i in ids:
            r = self.row(i)
            r["tag"], r["source"] = tag, source
            self.planned[i] = tag

    def act(self, ids, actions, reason: str):
        for i in ids:
            self.row(i)["actions"].append(f"{'+'.join(actions)} ({reason})")
            if "archive" in actions or "trash" in actions:
                self.gone.add(i)

    def task(self, mid: str, text: str, *, title=None, due=None, thread=None):
        row = self.row(mid)
        row["task"] = text
        if thread is not None:
            row["task_detail"] = {
                "title": title, "due": due, "thread": thread,
                "link": f"https://mail.google.com/mail/u/0/#all/{thread}",
            }

    def write(self, path: Path, merge: bool):
        import csv
        old = {}
        if merge and path.exists():
            with path.open() as f:
                old = {r["id"]: r for r in csv.DictReader(f)}
        need = [i for i in self.rows if i not in old]
        with ThreadPoolExecutor(4) as ex:
            meta = dict(zip(need, ex.map(fetch_meta, need)))
        for i, r in self.rows.items():
            m = meta.get(i) or old[i]
            o = old.get(i, {})
            old[i] = {"date": m.get("date", ""), "from": m.get("from", ""), "subject": m.get("subject", ""),
                      "unread": m.get("unread", ""), "tag": r["tag"] or o.get("tag", ""),
                      "source": r["source"] or o.get("source", ""),
                      "actions": " | ".join(r["actions"]) or o.get("actions", "") or "keep in inbox",
                      "task": r["task"] or o.get("task", ""), "id": i,
                      "link": f"https://mail.google.com/mail/u/0/#all/{m.get('thread') or o.get('link', '').rsplit('/', 1)[-1]}"}
        cols = ["date", "from", "subject", "unread", "tag", "source", "actions", "task", "id", "link"]
        STATE.mkdir(exist_ok=True)
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, cols)
            w.writeheader()
            w.writerows(old.values())
        save_meta_cache()
        print(f"[report] {len(old)} messages -> {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")


REPORT = Report()
PLAN_FILE = STATE / "plan.json"
PLAN: list[dict] = []  # operations recorded during a dry run, replayed by `apply-plan`


def gws(*args: str, params: dict | None = None, body: dict | None = None) -> dict:
    cmd = ["gws", *args]
    if params is not None:
        cmd += ["--params", json.dumps(params)]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    retryable = ("429", "500", "503", "Quota exceeded", "rateLimitExceeded", "userRateLimitExceeded", "backendError")
    for attempt in range(7):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0:
            out = p.stdout.strip()
            return json.loads(out) if out else {}
        err = p.stderr + p.stdout
        if attempt < 6 and any(r in err for r in retryable):
            time.sleep(min(60, 2 ** attempt * 2) + random.random())
            continue
        sys.exit(f"gws failed ({' '.join(args)}): {p.stderr.strip() or p.stdout.strip()}")
    return {}


def load_rules(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; copy rules.example.json to rules.json "
                         "or run scripts/setup-macos.sh")
    rules = json.loads(path.read_text())
    prefix = rules["label_prefix"]
    for t in rules["tags"]:
        t["label"] = f"{prefix}/{t['name']}"
        t["q"] = "label:" + t["label"].lower().replace("/", "-").replace(" ", "-")
    return rules


def any_tag_excluded(rules: dict) -> str:
    return " ".join(f"-{t['q']}" for t in rules["tags"])


def search(q: str, limit: int) -> list[str]:
    ids, token = [], None
    while len(ids) < limit:
        params = {"userId": "me", "q": q, "maxResults": min(500, limit - len(ids)),
                  "fields": "messages(id),nextPageToken"}
        if token:
            params["pageToken"] = token
        res = gws("gmail", "users", "messages", "list", params=params)
        ids += [m["id"] for m in res.get("messages", [])]
        token = res.get("nextPageToken")
        if not token:
            break
    return ids


class Labels:
    def __init__(self, apply: bool):
        self.apply = apply
        res = gws("gmail", "users", "labels", "list", params={"userId": "me", "fields": "labels(id,name)"})
        self.by_name = {l["name"]: l["id"] for l in res.get("labels", [])}

    def id(self, name: str) -> str:
        if name in self.by_name:
            return self.by_name[name]
        if not self.apply:
            return f"<new:{name}>"
        # Gmail requires parents to exist for nested labels to display as a tree.
        parts = name.split("/")
        for i in range(1, len(parts) + 1):
            n = "/".join(parts[:i])
            if n not in self.by_name:
                res = gws("gmail", "users", "labels", "create", params={"userId": "me"},
                          body={"name": n, "labelListVisibility": "labelShow",
                                "messageListVisibility": "show"})
                self.by_name[n] = res["id"]
        return self.by_name[name]


def modify(ids: list[str], add: list[str], remove: list[str], apply: bool, reason: str) -> None:
    if not ids:
        return
    print(f"  {'APPLY' if apply else 'DRY  '} {len(ids):5d} msgs  {reason}  +{add} -{remove}")
    if not apply:
        PLAN.append({"op": "modify", "ids": list(ids), "add": list(add), "remove": list(remove), "reason": reason})
        return
    STATE.mkdir(exist_ok=True)
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        gws("gmail", "users", "messages", "batchModify", params={"userId": "me"},
            body={"ids": chunk, "addLabelIds": add, "removeLabelIds": remove})
        with JOURNAL.open("a") as f:
            f.write(json.dumps({"ts": time.time(), "reason": reason, "ids": chunk,
                                "add": add, "remove": remove}) + "\n")


def action_labels(actions: list[str]) -> tuple[list[str], list[str]]:
    add, remove = [], []
    for a in actions:
        if a not in ACTIONS:
            sys.exit(f"unknown action '{a}' (allowed: {', '.join(ACTIONS)})")
        add += ACTIONS[a].get("add", [])
        remove += ACTIONS[a].get("remove", [])
    return add, remove


def trash(ids: list[str], apply: bool, reason: str) -> None:
    if not ids:
        return
    print(f"  {'APPLY' if apply else 'DRY  '} {len(ids):5d} msgs  {reason}  TRASH")
    if not apply:
        PLAN.append({"op": "trash", "ids": list(ids), "reason": reason})
        return
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda i: gws("gmail", "users", "messages", "trash",
                                  params={"userId": "me", "id": i, "fields": "id"}), ids))
    with JOURNAL.open("a") as f:
        f.write(json.dumps({"ts": time.time(), "reason": reason, "ids": ids, "trash": True}) + "\n")


def act(ids: list[str], actions: list[str], apply: bool, reason: str, extra_add: list[str] = ()) -> None:
    add, remove = action_labels(actions)
    if actions:
        REPORT.act(ids, actions, reason)
    if list(extra_add) or add or remove:
        modify(ids, [*extra_add, *add], remove, apply, reason)
    if "trash" in actions:
        trash(ids, apply, reason)


def cmd_tag(rules, args, labels):
    print(f"[tag] window: {args.window or 'all inbox'}")
    excl = any_tag_excluded(rules)
    tagged_now: set[str] = set()
    auto_tasks: dict[str, dict] = {}
    groups = []
    for t in rules["tags"]:
        ids: list[str] = []
        for m in t["match"]:
            q = f"in:inbox {args.window} ({m}) {excl}".strip()
            ids += [i for i in search(q, args.limit) if i not in tagged_now and i not in ids]
        tagged_now.update(ids)
        groups.append((t, ids))
        if t.get("task") == "always":
            auto_tasks.update({i: {"tag": t["name"]} for i in ids})
    ensure_tasks(rules, auto_tasks, args.apply)
    for t, ids in groups:
        REPORT.tag(ids, t["name"], "rule")
        act(ids, t["on_tag"], args.apply, f"tag {t['label']}", [labels.id(t["label"])])
    return tagged_now


def cmd_sweep(rules, args, labels):
    print("[sweep]")
    guard = rules.get("sweep_guard", "")
    for t in rules["tags"]:
        planned = {i for i, tg in REPORT.planned.items() if tg == t["name"]}
        for s in t["sweep"]:
            ids = search(f"in:inbox {t['q']} {s['when']} {guard}", args.limit)
            if not args.apply and planned:
                # Dry run: mail tagged in this run has no label yet, so evaluate the sweep on its match queries.
                ids += [i for i in search(f"in:inbox {s['when']} {guard}", args.limit)
                        if i in planned and i not in ids]
            ids = [i for i in ids if i not in REPORT.gone]
            for i in ids:
                if i not in REPORT.planned:
                    REPORT.row(i).update(tag=t["name"], source="existing label")
            act(ids, s["do"], args.apply, f"sweep {t['label']} [{s['when']}]")


def fetch_meta(mid: str) -> dict:
    """Headers rarely change, so they are cached; only the unread flag may be stale in the report."""
    global _meta_cache
    if _meta_cache is None:
        _meta_cache = json.loads(META_CACHE.read_text()) if META_CACHE.exists() else {}
    if mid in _meta_cache:
        return _meta_cache[mid]
    try:
        m = _fetch_meta(mid)
        _meta_cache[mid] = m
        return m
    except SystemExit as e:  # a single unreadable message (e.g. chat items) must not abort the run
        return {"id": mid, "thread": mid, "from": "", "to": "", "cc": "", "date": "", "bulk": False,
                "unread": "", "subject": f"<unreadable: {str(e)[:80]}>", "snippet": ""}


def _fetch_meta(mid: str) -> dict:
    d = gws("gmail", "users", "messages", "get", params={
        "userId": "me", "id": mid, "format": "metadata",
        "metadataHeaders": ["From", "To", "Cc", "Subject", "Date", "List-Unsubscribe"],
        "fields": "id,threadId,labelIds,snippet,payload/headers"})
    h = {x["name"].lower(): x["value"] for x in d.get("payload", {}).get("headers", [])}
    return {"id": d["id"], "thread": d.get("threadId"), "from": h.get("from", ""),
            "to": h.get("to", "")[:200], "cc": h.get("cc", "")[:200], "date": h.get("date", ""),
            "subject": h.get("subject", ""), "bulk": "list-unsubscribe" in h,
            "unread": "UNREAD" in d.get("labelIds", []), "snippet": d.get("snippet", "")[:240]}


def cmd_pending(rules, args, _labels=None, skip: set[str] = frozenset()):
    q = f"in:inbox {args.window} {any_tag_excluded(rules)}".strip()
    ids = [i for i in search(q, args.limit) if i not in skip]
    with ThreadPoolExecutor(4) as ex:
        items = list(ex.map(fetch_meta, ids))
    save_meta_cache()
    for i in ids:
        REPORT.row(i).update(tag="?", source="needs agent classification")
    STATE.mkdir(exist_ok=True)
    write_json(PENDING, {
        "batch_id": uuid.uuid4().hex,
        "created": time.time(),
        "rules_version": rules_version(rules),
        "tags": {t["name"]: t["description"] for t in rules["tags"]},
        "messages": items})
    print(f"[pending] {len(items)} untagged messages -> {PENDING.relative_to(ROOT)}")


class Tasks:
    """Google Tasks list used as the to-do side of the triage. One task per Gmail thread."""

    def __init__(self, rules: dict, apply: bool):
        self.cfg = rules.get("tasks", {})
        self.apply = apply
        self.list_id = None
        name = self.cfg.get("list", "Mail Triage")
        res = gws("tasks", "tasklists", "list", params={"maxResults": 100, "fields": "items(id,title)"})
        for tl in res.get("items", []):
            if tl["title"] == name:
                self.list_id = tl["id"]
        if not self.list_id and apply:
            self.list_id = gws("tasks", "tasklists", "insert", body={"title": name})["id"]
        self.name = name

    def all(self) -> list[dict]:
        if not self.list_id:
            return []
        items, token = [], None
        while True:
            params = {"tasklist": self.list_id, "maxResults": 100, "showCompleted": True,
                      "showHidden": True, "fields": "items(id,title,notes,status,due,completed),nextPageToken"}
            if token:
                params["pageToken"] = token
            res = gws("tasks", "tasks", "list", params=params)
            items += res.get("items", [])
            token = res.get("nextPageToken")
            if not token:
                return items

    def by_thread(self) -> dict[str, dict]:
        out = {}
        for t in self.all():
            m = MARKER.search(t.get("notes") or "")
            if m:
                out[m["thread"]] = {**t, **m.groupdict()}
        return out

    def default_due(self) -> str:
        d, n = dt.date.today(), int(self.cfg.get("default_due_business_days", 2))
        while n:
            d += dt.timedelta(days=1)
            n -= d.weekday() < 5
        return d.isoformat()

    def create(self, thread: str, tag: str, title: str, notes: str, due: str | None, on_done: list[str] | None):
        due = due or self.default_due()
        dt.date.fromisoformat(due)
        marker = f"[mail-triage thread={thread} tag={tag}" + (f" on_done={','.join(on_done)}" if on_done is not None else "") + "]"
        body = {"title": title[:250], "due": f"{due}T00:00:00.000Z",
                "notes": f"{notes.strip()}\n\nhttps://mail.google.com/mail/u/0/#all/{thread}\n{marker}"}
        print(f"  {'APPLY' if self.apply else 'DRY  '} task  due {due}  [{tag}] {title[:80]}")
        if self.apply:
            gws("tasks", "tasks", "insert", params={"tasklist": self.list_id}, body=body)
        else:
            PLAN.append({"op": "task", "thread": thread, "tag": tag, "body": body})


def thread_of(mid: str) -> dict:
    d = gws("gmail", "users", "messages", "get", params={
        "userId": "me", "id": mid, "format": "metadata", "metadataHeaders": ["Subject"],
        "fields": "threadId,internalDate,payload/headers"})
    subj = next((h["value"] for h in d.get("payload", {}).get("headers", []) if h["name"] == "Subject"), "")
    age = (time.time() - int(d.get("internalDate", 0)) / 1000) / 86400
    return {"thread": d["threadId"], "subject": subj, "age_days": age}


def validate_decisions(raw, pending, rules):
    if not isinstance(raw, dict) or set(raw) != {"batch_id", "decisions"}:
        raise ValueError("decisions must contain exactly batch_id and decisions; regenerate legacy files")
    if raw["batch_id"] != pending.get("batch_id"):
        raise ValueError("decisions belong to a different pending batch")
    if pending.get("rules_version") != rules_version(rules):
        raise ValueError("rules changed since pending was generated; run again")
    created = pending.get("created")
    if not isinstance(created, (int, float)) or not 0 <= time.time() - created <= 86400:
        raise ValueError("pending batch is invalid or older than 24h; run again")
    raw = raw["decisions"]
    if not isinstance(raw, dict):
        raise ValueError("decisions must be an object keyed by message ID")
    allowed = {m["id"] for m in pending["messages"]}
    if set(raw) - allowed:
        raise ValueError("decision IDs are not in the current pending batch")
    decisions = {mid: (v if isinstance(v, dict) else {"tag": v}) for mid, v in raw.items()}
    tags = {t["name"]: t for t in rules["tags"]}
    for d in decisions.values():
        if set(d) - {"tag", "task"} or not isinstance(d.get("tag"), str) or d["tag"] not in tags:
            raise ValueError("invalid decision or unknown tag")
        task = d.get("task")
        if task is None:
            continue
        if not isinstance(task, dict) or not task or set(task) - {"title", "notes", "due", "on_done"}:
            raise ValueError("task must be a nonempty object with only title, notes, due, on_done")
        if tags[d["tag"]].get("task") == "never":
            raise ValueError("this tag does not allow tasks")
        if not isinstance(task.get("title"), str) or not task["title"].strip() or len(task["title"]) > 250:
            raise ValueError("task title must contain 1-250 characters")
        if "notes" in task and (not isinstance(task["notes"], str) or len(task["notes"]) > 2000):
            raise ValueError("task notes must be a string of at most 2000 characters")
        if "due" in task:
            if not isinstance(task["due"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", task["due"]):
                raise ValueError("due must be YYYY-MM-DD")
            dt.date.fromisoformat(task["due"])
        if "on_done" in task:
            actions = task["on_done"]
            if not isinstance(actions, list) or any(not isinstance(a, str) for a in actions):
                raise ValueError("on_done must be a list of actions")
            permitted = set(tags[d["tag"]].get("on_task_done", [])) - {"trash"}
            if set(actions) - permitted:
                raise ValueError("on_done may only use non-trash actions already configured for the tag")
    return decisions


def fetch_context(mid: str, max_chars: int) -> str:
    """Fetch plain text for ambiguous messages, without exposing attachments."""
    d = gws("gmail", "users", "messages", "get", params={
        "userId": "me", "id": mid, "format": "full", "fields": "payload"})

    def text_parts(part):
        if part.get("filename"):
            return []
        out = []
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            data = part["body"]["data"]
            out.append(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace"))
        for child in part.get("parts", []):
            out.extend(text_parts(child))
        return out

    return "\n".join(text_parts(d.get("payload", {})))[:max_chars]


def cmd_decide(rules, args, labels):
    pending = json.loads(PENDING.read_text())
    decisions = validate_decisions(json.loads(Path(args.file).read_text()), pending, rules)
    tags = {t["name"]: t for t in rules["tags"]}
    # Recheck mutable mailbox state before any task or label is written.
    if args.apply:
        label_ids = {labels.by_name[t["label"]] for t in rules["tags"] if t["label"] in labels.by_name}
        for mid in decisions:
            current = gws("gmail", "users", "messages", "get", params={
                "userId": "me", "id": mid, "format": "minimal", "fields": "labelIds"})
            actual = set(current.get("labelIds", []))
            if "INBOX" not in actual or actual & label_ids:
                raise ValueError("mailbox changed since classification; run again")
    print("[decide]")
    # Create tasks first: if task creation fails, the message remains pending for retry.
    ensure_tasks(rules, decisions, args.apply)
    by_tag: dict[str, list[str]] = {}
    for mid, d in decisions.items():
        by_tag.setdefault(d["tag"], []).append(mid)
    for tag, ids in by_tag.items():
        REPORT.tag(ids, tag, "agent")
        act(ids, tags[tag]["on_tag"], args.apply, f"decide {tags[tag]['label']}", [labels.id(tags[tag]["label"])])

    cmd_sweep(rules, args, labels)  # agent-tagged mail may already qualify for its tag's sweep


def ensure_tasks(rules, decisions: dict[str, dict], apply: bool):
    tags = {t["name"]: t for t in rules["tags"]}
    wants = {mid: d for mid, d in decisions.items()
             if d.get("task") or tags[d["tag"]].get("task") == "always"}
    if not wants:
        return
    tasks = Tasks(rules, apply)
    existing = tasks.by_thread()
    with ThreadPoolExecutor(8) as ex:
        info = dict(zip(wants, ex.map(thread_of, wants)))
    print(f"[tasks] list '{tasks.name}'")
    max_age = tasks.cfg.get("max_age_days")
    open_titles = {x["title"] for x in existing.values() if x.get("status") != "completed"}
    seen, skipped_old = set(), 0
    for mid, d in wants.items():
        th = info[mid]["thread"]
        t = d.get("task") or {}
        title = t.get("title") or info[mid]["subject"]
        if th in existing:
            REPORT.task(mid, f"exists: {existing[th]['title'][:80]} ({existing[th].get('status')})")
            continue
        if th in seen or title in open_titles:
            REPORT.task(mid, f"duplicate of task: {title[:80]}")
            continue
        # Explicit agent decisions always get their task; rule-based ones only for recent mail.
        if not d.get("task") and max_age and info[mid]["age_days"] > max_age:
            REPORT.task(mid, f"no task: older than {max_age}d")
            skipped_old += 1
            continue
        seen.add(th)
        open_titles.add(title)
        due = t.get("due") or tasks.default_due()
        tasks.create(th, d["tag"], title, t.get("notes", ""), due, t.get("on_done"))
        REPORT.task(mid, f"CREATE due {due}: {title}"[:200], title=title, due=due, thread=th)
    if skipped_old:
        print(f"  skipped {skipped_old} rule-matched messages older than {max_age}d (no task)")


def cmd_sync(rules, args, _labels=None):
    """Completed task -> apply on_done (per-task override, else the tag's on_task_done) to the thread."""
    tags = {t["name"]: t for t in rules["tags"]}
    tasks = Tasks(rules, apply=False)
    print(f"[sync] list '{tasks.name}'")
    for th, t in tasks.by_thread().items():
        if t.get("status") != "completed":
            continue
        actions = t["on_done"].split(",") if t.get("on_done") is not None else \
            tags.get(t["tag"], {}).get("on_task_done", ["archive"])
        actions = [a for a in actions if a]
        if not actions:
            continue
        res = gws("gmail", "users", "threads", "get", params={
            "userId": "me", "id": th, "format": "minimal", "fields": "messages(id,labelIds)"})
        ids = [m["id"] for m in res.get("messages", []) if "INBOX" in m.get("labelIds", [])]
        act(ids, actions, args.apply, f"task done [{t['tag']}] {t['title'][:50]}")


def cmd_undo(_rules, args, _labels=None):
    if not JOURNAL.exists():
        sys.exit("nothing to undo")
    lines = JOURNAL.read_text().splitlines()
    todo, keep = lines[-args.n:], lines[:-args.n]
    for line in reversed(todo):
        e = json.loads(line)
        print(f"  {'APPLY' if args.apply else 'DRY  '} undo {len(e['ids'])} msgs  {e['reason']}")
        if args.apply and e.get("trash"):
            for i in e["ids"]:
                gws("gmail", "users", "messages", "untrash", params={"userId": "me", "id": i, "fields": "id"})
        elif args.apply:
            gws("gmail", "users", "messages", "batchModify", params={"userId": "me"},
                body={"ids": e["ids"], "addLabelIds": e["remove"], "removeLabelIds": e["add"]})
    if args.apply:
        JOURNAL.write_text("".join(l + "\n" for l in keep))


def write_plan(cmd: str, merge: bool):
    """`run` starts a fresh plan; later dry-run commands (decide, sweep...) replace only their own ops."""
    old = []
    if merge and PLAN_FILE.exists():
        old = [o for o in json.loads(PLAN_FILE.read_text())["ops"] if o.get("cmd") != cmd]
    ops = old + [{**o, "cmd": cmd} for o in PLAN]
    STATE.mkdir(exist_ok=True)
    write_json(PLAN_FILE, {"created": time.time(), "ops": ops})
    print(f"[plan] {len(ops)} operations -> {PLAN_FILE.relative_to(ROOT)}  (apply with: triage.py apply-plan --apply)")


def cmd_apply_plan(rules, args):
    """Replay state/plan.json exactly as previewed, without re-searching or re-classifying."""
    if not PLAN_FILE.exists():
        sys.exit("no plan: run a dry run first (e.g. `triage.py run` then `triage.py decide`)")
    plan = json.loads(PLAN_FILE.read_text())
    age_h = (time.time() - plan["created"]) / 3600
    if age_h > args.max_age_hours:
        sys.exit(f"plan is {age_h:.1f}h old (> {args.max_age_hours}h); re-run the dry run or pass --max-age-hours")
    ops = plan["ops"]
    skip = set()
    if args.exclude:
        import csv
        with open(args.exclude) as f:
            skip = {r.get("id") or r.get("ID") for r in csv.DictReader(f)} - {None, ""}
    labels = Labels(args.apply)
    print(f"[apply-plan] {len(ops)} ops from plan created {age_h:.1f}h ago" + (f", excluding {len(skip)} ids" if skip else ""))

    def resolve(ids_):  # placeholders for labels that did not exist at dry-run time
        return [labels.id(i[5:-1]) if i.startswith("<new:") else i for i in ids_]

    task_ops = [o for o in ops if o["op"] == "task"]
    for o in ops:
        ids = [i for i in o.get("ids", []) if i not in skip]
        if o["op"] == "modify":
            modify(ids, resolve(o["add"]), resolve(o["remove"]), args.apply, f"plan: {o['reason']}")
        elif o["op"] == "trash":
            trash(ids, args.apply, f"plan: {o['reason']}")
    if task_ops:
        tasks = Tasks(rules, args.apply)
        existing = tasks.by_thread()
        print(f"[tasks] list '{tasks.name}'")
        for o in task_ops:
            if o["thread"] in existing or o["thread"] in skip:
                print(f"  skip  task (exists or excluded) {o['body']['title'][:70]}")
                continue
            existing[o["thread"]] = {}
            print(f"  {'APPLY' if args.apply else 'DRY  '} task  due {o['body']['due'][:10]}  [{o['tag']}] {o['body']['title'][:80]}")
            if args.apply:
                gws("tasks", "tasks", "insert", params={"tasklist": tasks.list_id}, body=o["body"])
    if args.apply:
        PLAN_FILE.rename(PLAN_FILE.with_suffix(f".applied-{int(time.time())}.json"))
        print("[apply-plan] done; plan archived (undo with: triage.py undo -n <batches> --apply)")
    else:
        print("(preview — add --apply to execute this plan)")


def main():
    os.umask(0o077)  # state, journal and reports contain private mail metadata
    with run_lock():
        cli()


def cli():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rules", default=str(ROOT / "rules.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, window=True):
        p.add_argument("--apply", action="store_true", help="actually modify Gmail (default: dry run)")
        p.add_argument("--limit", type=int, default=500, help="max messages per query")
        p.add_argument("--report", default=None,
                       help=f"per-message CSV of tags/actions/tasks (default in dry run: {REPORT_FILE.relative_to(ROOT)})")
        if window:
            p.add_argument("--window", default=None,
                           help="Gmail time filter, e.g. 'newer_than:7d'; use '' for the whole inbox")
        return p

    common(sub.add_parser("tag"))
    common(sub.add_parser("sweep"), window=False)
    common(sub.add_parser("pending")).set_defaults(apply=False)
    common(sub.add_parser("run"))
    common(sub.add_parser("sync"), window=False)
    d = common(sub.add_parser("decide"), window=False)
    d.add_argument("file", nargs="?", default=str(STATE / "decisions.json"))
    u = sub.add_parser("undo")
    u.add_argument("-n", type=int, default=1, help="number of journal batches to revert")
    u.add_argument("--apply", action="store_true")
    a = sub.add_parser("apply-plan", help="execute state/plan.json produced by the last dry run(s)")
    a.add_argument("--apply", action="store_true", help="execute (default: show what the plan contains)")
    a.add_argument("--max-age-hours", type=float, default=24)
    a.add_argument("--exclude", help="CSV with an 'id' column of messages to leave untouched "
                                      "(e.g. rows exported from the review sheet)")

    args = ap.parse_args()
    if args.cmd == "undo" and args.n < 1:
        ap.error("-n must be at least 1")
    rules = load_rules(Path(args.rules))
    if getattr(args, "window", None) is None and hasattr(args, "window"):
        args.window = rules["default_window"]

    if args.cmd == "apply-plan":
        cmd_apply_plan(rules, args)
        return
    if args.cmd in ("pending", "undo"):
        {"pending": cmd_pending, "undo": cmd_undo}[args.cmd](rules, args)
        return
    labels = Labels(args.apply)
    if args.cmd == "run":
        cmd_sync(rules, args)
        tagged = cmd_tag(rules, args, labels)
        cmd_sweep(rules, args, labels)
        cmd_pending(rules, args, skip=tagged | REPORT.gone)
    else:
        {"tag": cmd_tag, "sweep": cmd_sweep, "decide": cmd_decide, "sync": cmd_sync}[args.cmd](rules, args, labels)
    report = args.report or (None if args.apply else str(REPORT_FILE))
    if report and REPORT.rows:
        # `run` starts a fresh report; `decide` etc. merge into it so one file shows the whole plan.
        REPORT.write(Path(report), merge=args.cmd != "run")
    if not args.apply:
        write_plan(args.cmd, merge=args.cmd != "run")
        print("(dry run — re-run with --apply to modify Gmail)")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as e:
        sys.exit(f"triage failed: {e}")
