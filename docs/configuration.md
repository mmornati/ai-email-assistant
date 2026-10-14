# Configuration

Two JSON files control everything. Both are read on every run, so edits take
effect immediately without reinstalling the schedule.

| File | In Git? | Purpose |
| --- | --- | --- |
| `rules.json` | No (personal) | Tags, ordered Gmail queries, actions, task policies, default dates |
| `classifier.json` | Yes | Classifier CLI (Copilot or Claude Code), models, thresholds, batching and per-run limits |

## `rules.json`

Created by `make setup` from [`rules.example.json`](../rules.example.json). The
starter preserves the tag taxonomy and task policies, but has no sender-specific
matching, sweeps, archive/read/trash actions, or task-completion actions. With it,
model-free runs leave mail pending; model-enabled applied runs can label mail and
create tasks.

```json
{
  "label_prefix": "AI",
  "default_window": "newer_than:7d",
  "sweep_guard": "-is:starred",
  "tasks": { "list": "My Tasks", "default_due_business_days": 2, "max_age_days": 14 },
  "tags": [
    {"name": "Action", "description": "A human requests a reply, decision, …",
     "match": [], "on_tag": [], "sweep": [], "task": "always", "on_task_done": []}
  ]
}
```

| Key | Meaning |
| --- | --- |
| `label_prefix` | Gmail labels are created as `<prefix>/<tag>`; labelled mail is excluded from later scans |
| `default_window` | Gmail query bounding each scan (default `newer_than:7d`) |
| `sweep_guard` | Query appended to every sweep; by default starred mail is never swept |
| `tasks.list` | Google Tasks list for follow-ups (`make setup` asks; `--task-list NAME`) |
| `tasks.default_due_business_days` | Due date when none is stated, computed in code |
| `tasks.max_age_days` | No new task for mail older than this |
| `tags[].match` | Gmail queries; **the first matching tag wins**, so order matters |
| `tags[].on_tag` | Actions when a message receives the tag |
| `tags[].sweep` | `{"when": "<query>", "do": [actions]}` for inbox mail already carrying the tag, e.g. `{"when": "older_than:3d", "do": ["archive"]}` |
| `tags[].task` | `always`, `optional` (explicit commitment only) or `never` |
| `tags[].on_task_done` | Actions applied to the thread when its task is completed |

Actions: `archive`, `mark_read`, `star`, `important`, and explicitly configured
`trash` (recoverable and journaled).

Add your own Gmail queries to `match` in tag priority order to reduce model use;
the [`mail-setup` skill](getting-started.md#4-personalize-your-rules-mail-setup)
proposes them for you. **Review every cleanup action before enabling it.**

The runner suggests recurring bulk-sender rule candidates in `summary.json` (when a
bulk sender occurs at least three times in a pending batch), but never edits
`rules.json`. Review and approve a sender query and tag before adding it.

## `classifier.json`

| Setting | Default | Meaning |
| --- | --- | --- |
| `cli` | `copilot` | Which `providers` entry classifies mail ([Choosing the classifier CLI](classifier-cli.md)) |
| `providers.copilot.cheap_model` | `gpt-6-luna` | First-pass classification |
| `providers.copilot.escalation_model` | `gpt-6.1-sol` | Ambiguous cases only |
| `confidence_threshold` | `0.85` | First-pass acceptance threshold |
| `escalation_threshold` | `0.9` | Escalation acceptance threshold |
| `batch_size` | `25` | Messages per model invocation |
| `max_batches` | `4` | At most 100 fresh first-pass messages/run |
| `max_escalations` | `10` | Strong-model messages/run, not calls |
| `context_chars` | `4000` | Max current-message plain-text body chars on escalation |
| `timeout_seconds` | `180` | Timeout per CLI invocation |
| `version` | `1` | Bump after intentional classifier-policy changes |
| `providers.copilot.binary` | `copilot` | CLI executable name or absolute path |
| `providers.copilot.disabled_mcp_servers` | `[]` | Also suppress these user MCP server names |
| `providers.claude.*` | see [Claude Code](classifier-cli.md#claude-code) | Binary, models, auth mode and per-call cap |

Both low confidence and `needs_context=true` trigger escalation.

The older flat format (`copilot_binary`, `cheap_model`, ... at the top level) is
still accepted and read as `"cli": "copilot"`. Switching CLI or model invalidates
same-day cached classifications.

Capacity-limited mail stays pending and is eligible on the next run. The limits
bound workload, **not an exact currency budget**. The Copilot CLI has a separate
soft AI-credit cap with a documented minimum of 30 credits; it is not used here as
a micro-call budget. Claude Code's `max_budget_usd_per_call` is a per-call guard
against runaway output, not a budget. See [Costs](costs.md).

Model selection in the Copilot app or Claude Code controls interactive
assistance; it does **not** override `classifier.json` for the external runner.

## Scan window and limits

Every actual scan synchronizes completed tasks and sweeps existing labels, even if
there is no new mail. The default classification window is `newer_than:7d`, and
the default per-query limit is 500. This is a polling design, **not a Gmail
history cursor or push subscription**. Already classified mail is excluded by its
`AI/*` labels. For larger backlogs, use an explicit window/limit:

```bash
python3 runner.py --window '' --limit 8000  # preview whole-inbox processing (paid if pending)
```
