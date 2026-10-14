#!/usr/bin/env python3
"""Read-only mailbox discovery and preview/approval of exact-sender local rules."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import time
import uuid
from email.utils import parseaddr
from pathlib import Path

import triage


def sender_of(value):
    sender = parseaddr(value)[1].lower()
    # Some parseaddr versions collapse "a@b OR from:c" into one token; require it verbatim.
    if sender not in value.lower():
        return None
    return sender if re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+", sender) else None


def fetch_sample(mid):
    response = triage.gws("gmail", "users", "messages", "get", params={
        "userId": "me", "id": mid, "format": "metadata",
        "metadataHeaders": ["From", "Subject", "Date", "List-Id", "List-Unsubscribe", "Precedence"],
        "fields": "id,snippet,payload(headers)",
    })
    headers = {h["name"].lower(): h["value"] for h in response.get("payload", {}).get("headers", [])}
    return {
        "sender": sender_of(headers.get("from", "")),
        "subject": headers.get("subject", "")[:160],
        "snippet": response.get("snippet", "")[:300],
        "date": headers.get("date", "")[:80],
        "list_id": headers.get("list-id", "")[:160],
        "bulk": bool(headers.get("list-id") or headers.get("list-unsubscribe")
                     or headers.get("precedence", "").lower() in {"bulk", "list"}),
    }


def group_samples(samples, max_groups):
    grouped = {}
    for sample in samples:
        if sample["sender"]:
            grouped.setdefault(sample["sender"], []).append(sample)
    groups = []
    for sender, items in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        if len(items) < 3:
            continue
        development = [m for i, m in enumerate(items) if i % 3 != 2][:3]
        validation = [m for i, m in enumerate(items) if i % 3 == 2][:2]
        examples = []
        for split, selected in (("development", development), ("validation", validation)):
            for index, message in enumerate(selected, 1):
                examples.append({
                    "id": f"{split}-{index}", "split": split,
                    **{k: v for k, v in message.items() if k != "sender"},
                })
        groups.append({
            "id": hashlib.sha256(sender.encode()).hexdigest()[:16],
            "sender": sender, "query": f"from:{sender}", "sample_count": len(items),
            "all_bulk": all(m["bulk"] for m in items),
            "eligible": all(m["bulk"] for m in items) and len(development) == 3 and len(validation) == 2,
            "examples": examples,
        })
        if len(groups) == max_groups:
            break
    return groups


def discover(rules, limit, days, max_groups):
    query = f"newer_than:{days}d -in:sent -in:drafts -in:spam -in:trash"
    ids = triage.search(query, limit)
    samples = [fetch_sample(mid) for mid in ids]
    return {
        "batch_id": str(uuid.uuid4()), "created": time.time(), "rules_version": triage.rules_version(rules),
        "query": query, "limit": limit, "sample_count": len(samples),
        "at_limit": len(ids) >= limit,
        "scope_note": "Recent received mail, including archived mail; bounded, not random or exhaustive.",
        "groups": group_samples(samples, max_groups),
    }


def proposed_rules(rules, discovery, selections):
    if (selections.get("batch_id") != discovery["batch_id"]
            or discovery["rules_version"] != triage.rules_version(rules)):
        raise ValueError("discovery or selections are stale; rediscover using current rules")
    age = time.time() - discovery["created"]
    if not 0 <= age <= 86400:
        raise ValueError("discovery must be less than 24 hours old")
    if set(selections) != {"batch_id", "selections"} or not isinstance(selections["selections"], list):
        raise ValueError("expected batch_id and a selections list")
    groups = {g["id"]: g for g in discovery["groups"]}
    tags = {t["name"]: t for t in rules["tags"]}
    result = copy.deepcopy(rules)
    changes, seen = [], set()
    for selection in selections["selections"]:
        if not isinstance(selection, dict) or set(selection) != {"group_id", "tag", "example_tags"}:
            raise ValueError("each selection requires only group_id, tag and example_tags")
        gid, tag = selection["group_id"], selection["tag"]
        if not isinstance(gid, str) or gid not in groups or gid in seen:
            raise ValueError("unknown or repeated sender group")
        seen.add(gid)
        group = groups[gid]
        if (not isinstance(tag, str) or tag not in tags or tag in {"Action", "FYI", "Backlog"}
                or not group["eligible"]):
            raise ValueError("only recurring bulk groups with separate samples qualify for automated-sender rules")
        sender = sender_of(group["sender"])
        if sender != group["sender"] or group["query"] != f"from:{sender}":
            raise ValueError("invalid exact-sender query")
        expected_ids = {e["id"] for e in group["examples"]}
        labels = selection["example_tags"]
        if (not isinstance(labels, dict) or set(labels) != expected_ids
                or any(label != tag for label in labels.values())):
            raise ValueError("every development and validation example must independently agree on the selected tag")
        matches = [t["name"] for t in rules["tags"] if group["query"] in t["match"]]
        if matches and matches != [tag]:
            raise ValueError("sender query already exists under a conflicting tag")
        if not matches:
            target = next(t for t in result["tags"] if t["name"] == tag)
            target["match"].append(group["query"])
            changes.append({"tag": tag, "query": group["query"], "sample_count": group["sample_count"]})
    return result, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["discover", "preview", "approve"])
    parser.add_argument("--rules", type=Path, default=triage.ROOT / "rules.json")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--max-groups", type=int, default=20)
    parser.add_argument("--selections", type=Path, default=triage.STATE / "setup-selections.json")
    parser.add_argument("--apply", action="store_true", help="approve only: save local rules after user approval")
    args = parser.parse_args()
    if not 1 <= args.limit <= 500 or not 1 <= args.days <= 90 or not 1 <= args.max_groups <= 50:
        parser.error("limit must be 1-500, days 1-90 and max-groups 1-50")
    if args.apply and args.command != "approve":
        parser.error("--apply is only valid for approve")
    os.umask(0o077)
    with triage.run_lock():
        rules = json.loads(args.rules.read_text())
        discovery_path = triage.STATE / "setup-discovery.json"
        if args.command == "discover":
            report = discover(rules, args.limit, args.days, args.max_groups)
            triage.write_json(discovery_path, report)
            print(f"Read {report['sample_count']} messages; {len(report['groups'])} recurring groups. "
                  f"Private discovery: {discovery_path}; no mailbox changes or model calls.")
            return
        report = json.loads(discovery_path.read_text())
        selections = json.loads(args.selections.read_text())
        proposal, changes = proposed_rules(rules, report, selections)
        triage.write_json(triage.STATE / "setup-rules.preview.json", proposal)
        print(json.dumps({"changes": changes, "cleanup_actions_added": False,
                          "existing_policies_preserved": True, "applied": args.apply}, indent=2))
        if args.command == "approve" and args.apply and changes:
            backup = triage.STATE / f"rules.before-setup-{uuid.uuid4().hex}.json"
            triage.write_json(backup, rules)
            triage.write_json(args.rules, proposal)
            print(f"Saved rules; private backup: {backup}. No mail or tasks modified; pending batches need refreshing.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        sys.exit(f"mail setup failed: {type(error).__name__}; no mailbox mutations performed")
