# State files

Everything the tool writes lives in `state/` in the project folder (the launchd
job definition itself is in `~/Library/LaunchAgents/`; see
[Scheduling](../scheduling.md)). The folder is owner-only, excluded from Git and
from shared ZIPs, and **not encrypted**. Several
files contain mail metadata (senders, subjects, snippets) or task details; treat
the whole folder as private.

## Overview

| File | Written by | Contains mail data | Purpose |
| --- | --- | --- | --- |
| `summary.json` | `runner.py`, every run | Task titles and message IDs | Status and counts of the last run. Replaced each run. |
| `pending.json` | `runner.py`, `triage.py run`/`pending` | Yes | Current batch of untagged inbox mail. |
| `decisions.json` | `runner.py`, or you | Task titles | Decisions for the current batch. |
| `plan.json` | any dry run | Task titles and notes | Exact operations a dry run would perform. |
| `plan.applied-<timestamp>.json` | `triage.py apply-plan --apply` | Task titles and notes | The plan after it was applied. |
| `dry-run.csv` | `triage.py` dry runs, or `--report` | Yes | Per-message plan for review in a spreadsheet. |
| `journal.jsonl` | any `--apply` | Message IDs | Applied label and trash operations, for `undo`. |
| `classification-cache.json` | `runner.py` | Decisions | Same-day validated decisions and review holds. |
| `meta-cache.json` | `triage.py`, `runner.py` | Yes | Cached message headers and snippets. |
| `usage.jsonl` | `runner.py` | No | One line per model call. Accumulates. |
| `run.lock` | `triage.py`, `runner.py`, `mail_setup.py` | No | Process lock. May remain after exit. |
| `schedule.log` | the launchd job | No (counts only) | Standard output of scheduled runs. |
| `schedule-error.log` | the launchd job | Possibly | Standard error of scheduled runs. |
| `setup-discovery.json` | `mail_setup.py discover` | Yes | Sender groups and samples. |
| `setup-selections.json` | the `mail-setup` skill | No | Reviewed selections. |
| `setup-rules.preview.json` | `mail_setup.py preview`/`approve` | No | Proposed rules. |
| `rules.before-setup-<id>.json` | `mail_setup.py approve --apply` | No | Backup of the previous rules. |
| `benchmark.json`, `laya-install.json`, `benchmark-usage/` | `tools/benchmark.py` | Classification evidence only | Optional benchmark output. |

## `summary.json`

Written at the end of every `runner.py` run, including failed ones. In a dry run,
counts are **planned**, not applied.

| Field | Meaning |
| --- | --- |
| `started`, `finished` | Unix timestamps. |
| `apply` | `true` for an applied run, `false` for a dry run. |
| `status` | `ok`, `needs_review` (some mail unresolved), or `error`. `running` appears only if a run was interrupted before it finished. |
| `error_type` | On `error` only: the exception type, never its message. |
| `pending` | Messages that reached the pending batch this run. |
| `classified` | Messages with an accepted decision (fresh or cached). |
| `cached` | How many of those came from the same-day cache. |
| `unresolved_ids` | Gmail IDs held for review or over capacity. |
| `tags` | Count per tag across everything this run tagged or touched. `?` counts pending messages left unresolved. |
| `actions` | Count per action combination (for example `archive+mark_read`). |
| `archived` | Messages that leave the inbox in this run (archive or trash). |
| `tasks_created` | Tasks created (or planned, in a dry run). |
| `tasks` | Each created task: `title`, `due`, `thread`, `link`. |
| `rule_candidates` | Bulk senders seen at least three times in the pending batch: `sender`, `count`, suggested `query`, `classified_tags`, `requires_approval` (always `true`). |

If `classifier.json` fails to load, the summary has only `started`, `finished`,
`apply`, `status` and `error_type`.

Example from the applied step of the [demo](../getting-started/demo.md). **Demo
output on an invented mailbox**; IDs and dates come from that run.

```json
{
 "started": 1792007230.030658,
 "apply": true,
 "status": "needs_review",
 "pending": 10,
 "classified": 9,
 "cached": 9,
 "unresolved_ids": [
  "0a5d8bcc49c89b9d"
 ],
 "tags": {
  "Alerts": 3,
  "GitHub-Admin": 5,
  "Meeting/Invite": 4,
  "Meeting/Notes": 2,
  "Shares": 2,
  "Admin": 3,
  "Internal-Comms": 2,
  "Newsletter": 7,
  "Promo": 3,
  "Action": 4,
  "?": 1,
  "FYI": 1
 },
 "actions": {
  "archive+mark_read": 11
 },
 "archived": 11,
 "tasks_created": 4,
 "tasks": [
  {
   "title": "Approve the Q4 hiring plan (two senior roles)",
   "due": "2026-10-16",
   "thread": "1d7c350f170a9aa0",
   "link": "https://mail.google.com/mail/u/0/#all/1d7c350f170a9aa0"
  },
  {
   "title": "Confirm the revised renewal terms to Jonas (clause 7)",
   "due": "2026-10-20",
   "thread": "6b01c344dbe5827b",
   "link": "https://mail.google.com/mail/u/0/#all/6b01c344dbe5827b"
  },
  {
   "title": "Review the onboarding deck (slides 4-9) before Monday",
   "due": "2026-10-19",
   "thread": "c4b8874158675113",
   "link": "https://mail.google.com/mail/u/0/#all/c4b8874158675113"
  },
  {
   "title": "Tell Tom whether the Team plan includes API access",
   "due": "2026-10-16",
   "thread": "85961c6be2cfc730",
   "link": "https://mail.google.com/mail/u/0/#all/85961c6be2cfc730"
  }
 ],
 "rule_candidates": [
  {
   "sender": "events@summit.example",
   "count": 3,
   "query": "from:events@summit.example",
   "classified_tags": [
    "Newsletter"
   ],
   "requires_approval": true
  }
 ],
 "finished": 1792007232.188311
}
```

Reading it: 10 messages were pending, all 9 accepted decisions came from the cache
written by the earlier dry run (no model call), 11 messages left the inbox, 4 tasks
were created, and one message is waiting for a person.

## `pending.json`

| Field | Meaning |
| --- | --- |
| `batch_id` | Random ID of this batch. Decisions must quote it. |
| `created` | Unix timestamp. Batches older than 24 hours are rejected by `decide`. |
| `rules_version` | SHA-256 of the rules used; decisions are rejected if the rules changed. |
| `tags` | Allowed tag names and their descriptions. |
| `messages` | One object per message: `id`, `thread`, `from`, `to` and `cc` (first 200 characters), `date`, `subject`, `bulk` (has `List-Unsubscribe`), `unread`, `snippet` (first 240 characters). |

After an **applied** runner run, `messages` is reduced to the unresolved ones.

## `decisions.json`

```text
{"batch_id": "<pending batch_id>", "decisions": {"<message id>": "<tag>" or {"tag": "<tag>", "task": {...}}}}
```

`runner.py` overwrites this file on every run with the decisions it accepted. See
[Interactive review](../interactive-review.md#interactive-review-recommended-app-use)
for writing it yourself.

## `plan.json`

`{"created": <timestamp>, "ops": [...]}`. Each operation has `op` (`modify`,
`trash` or `task`), the `cmd` that recorded it, and:

- `modify`: `ids`, `add`, `remove` (label IDs; labels that did not exist yet appear
  as `<new:AI/Name>`), `reason`;
- `trash`: `ids`, `reason`;
- `task`: `thread`, `tag`, and the Google Tasks `body` (title, due, notes with link
  and marker).

## `dry-run.csv`

Columns: `date`, `from`, `subject`, `unread`, `tag`, `source` (`rule`, `agent`,
`existing label` or `needs agent classification`), `actions` (or `keep in inbox`),
`task`, `id`, `link`. Values that start with `=`, `+`, `-`, `@`, a tab or a carriage
return are prefixed with `'` so spreadsheets do not run them as formulas. Header
data comes from `meta-cache.json`, so the `unread` flag can be stale.

## `journal.jsonl`

One JSON object per applied operation: `ts`, `reason`, `ids`, and either
`add`/`remove` label IDs or `"trash": true`. Label changes are split into Gmail
batches of up to 1,000 messages, one line each.
`triage.py undo -n N --apply` reverses the last `N` lines and removes them.

## `classification-cache.json`

Keys are SHA-256 hashes of the message metadata, rules hash, classifier settings
and today's date. Values are either `{"decision": {...}}` or `{"review": true}` for
mail held for review today. Entries for messages no longer pending are dropped.

## `usage.jsonl`

One line per model call. `make usage` (`python3 runner.py --usage-report`) totals
it per `cli/model`; [Costs](../costs.md#measure-your-real-usage) explains how to
turn the token counts into money.

| Field | Meaning |
| --- | --- |
| `ts` | Unix timestamp. |
| `cli` | `copilot` or `claude`. Lines written before the classifier CLI became selectable have no `cli` and count as `copilot`. |
| `model` | Model name. |
| `messages` | Messages in the call. |
| `status` | `ok`, `timeout`, `cli_error` or `invalid_json`. |
| `prompt_chars`, `response_chars` | Character counts (not tokens). |
| `duration_seconds` | Wall time. |
| `cli_usage` | `null` if the CLI reported no usage. Otherwise `tokens` with `input`, `output`, `cache_read`, `cache_write` when present. Copilot entries may add `totalNanoAiu` and `totalUserRequests`. Claude Code entries may add `tokens.cache_write_1h` (the 1-hour-TTL part of `cache_write`) and `cli_cost_usd`, the CLI's own cost estimate, which [is not reliable for these models](../costs.md#claude-code-rates-and-measured-overhead). |

Demo line (invented mailbox, Copilot path; the stand-in CLI estimates tokens from
text length, so these are not real usage figures):

```json
{"ts": 1792007205.012898, "cli": "copilot", "model": "gpt-6-luna", "messages": 10, "status": "ok", "prompt_chars": 5734, "response_chars": 1498, "duration_seconds": 0.036, "cli_usage": {"totalUserRequests": 1, "tokens": {"input": 1433, "output": 317}}}
```

The file grows forever; rotate or archive it privately if needed.
