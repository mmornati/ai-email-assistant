# Configuration

Two JSON files configure everything. Both are read on every run; edits need no
reinstall of the schedule.

## `rules.json`

Your personal rules. Created from `rules.example.json` by the setup script and
excluded from Git and from shared ZIPs. Choose another file with `--rules`.

### Top-level fields

| Field | Type | Starter value | Meaning |
| --- | --- | --- | --- |
| `label_prefix` | string | `"AI"` | Prefix of every Gmail label. A tag `X` becomes the label `AI/X`. |
| `default_window` | string | `"newer_than:7d"` | Gmail time filter for rule matching and pending mail when `--window` is not given. |
| `sweep_guard` | string | `"-is:starred"` | Query fragment added to every sweep. |
| `tasks` | object | see below | Google Tasks settings. |
| `tags` | array | 12 tags | Ordered list of tags. Order is precedence: first match wins. |

### `tasks`

| Field | Type | Starter value | Meaning |
| --- | --- | --- | --- |
| `list` | string | `"My Tasks"` | Google Tasks list name; created on the first applied run that needs it. If absent, `Mail Triage` is used. |
| `default_due_business_days` | integer | `2` | Due date for tasks without an explicit date, in business days from today. |
| `max_age_days` | integer | `14` | Automatic (rule or `always`-tag) tasks are skipped for mail older than this. Explicit tasks are always created. |

### Each tag

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | Tag name; also the label suffix. A `/` nests labels, as in `Meeting/Invite`. |
| `description` | string | Definition the classifier sees for this tag. |
| `match` | array of strings | Gmail queries. Each is searched as `in:inbox <window> (<query>)`, excluding mail with any `AI/*` label. |
| `on_tag` | array of actions | Applied when a message gets this tag, by rule or by decision. |
| `sweep` | array of objects | Each `{"when": "<gmail query>", "do": [<actions>]}` applies `do` to inbox mail with this label matching `when` and `sweep_guard`. |
| `task` | `"always"`, `"optional"` or `"never"` | Task policy. |
| `on_task_done` | array of actions | Applied to the thread's inbox messages when its task is completed. |

Each tag's Gmail label search term is derived from its full label, lowercased with
`/` and spaces replaced by `-`: `AI/Meeting/Invite` is searched as
`label:ai-meeting-invite`.

### Actions

| Action | Gmail effect |
| --- | --- |
| `archive` | Remove `INBOX`. |
| `mark_read` | Remove `UNREAD`. |
| `star` | Add `STARRED`. |
| `important` | Add `IMPORTANT`. |
| `trash` | Move to Trash (opt-in; recoverable for 30 days; undoable). |

An unknown action stops the run with an error.

### Starter tags

`rules.example.json` defines these twelve tags with empty `match`, `on_tag`,
`sweep` and `on_task_done` lists:

| Tag | Task policy | Description |
| --- | --- | --- |
| Action | always | A human requests a reply, decision, approval, signature or commitment. |
| Alerts | optional | Monitoring incidents, outages, security and expiry warnings. |
| GitHub-Admin | optional | Repository administration, pull request and issue notifications. |
| Meeting/Invite | never | Calendar invitations, updates and RSVPs. |
| Meeting/Notes | optional | Meeting summaries, notes and preparation. |
| Shares | optional | Documents shared with the recipient, document comments and collaboration notifications. |
| Admin | optional | HR, travel, invoices, receipts and administrative information. |
| Internal-Comms | optional | Company-wide announcements and internal mailing lists. |
| Newsletter | never | Newsletters, webinars and vendor marketing. |
| Promo | never | Retail promotions and discount advertising. |
| FYI | optional | Informational human mail with no request to act. |
| Backlog | never | Old mail explicitly selected for backlog review; do not infer age without a date. |

Any change to `rules.json` changes its hash, which invalidates the current pending
batch, decisions files and the classification cache.

## `classifier.json`

Models, thresholds, batching and per-run limits for `runner.py`. Choose another
file with `--config`.

The file must contain **exactly** these twelve keys; a missing or extra key stops
the run with "classifier configuration has missing or unknown keys".

| Key | Type and validation | Default | Meaning |
| --- | --- | --- | --- |
| `version` | positive integer | `1` | Bump after intentional classifier-policy changes. |
| `cheap_model` | nonempty string | `gpt-6-luna` | First-pass model. |
| `escalation_model` | nonempty string | `gpt-6.1-sol` | Model for ambiguous cases. |
| `confidence_threshold` | number, 0 to 1 | `0.85` | First-pass answers below this are escalated. |
| `escalation_threshold` | number, 0 to 1 | `0.9` | Escalated answers below this are held for review. |
| `batch_size` | positive integer | `25` | Messages per model call. |
| `max_batches` | positive integer | `4` | First-pass calls per run. |
| `max_escalations` | integer, 0 or more | `10` | Messages escalated per run. `0` disables escalation; ambiguous mail is then left for review. |
| `context_chars` | positive integer | `4000` | Maximum plain-text body characters sent on escalation. |
| `timeout_seconds` | positive integer | `180` | Timeout per CLI call. |
| `copilot_binary` | nonempty string | `copilot` | CLI executable name or absolute path. |
| `disabled_mcp_servers` | list of nonempty strings | `[]` | Your MCP server names to disable for classifier calls. |

The whole file is part of the classification cache key, so any change invalidates
cached decisions.

If loading fails, the runner writes a `state/summary.json` with `status: "error"`
and the error type, and exits with a failure code.

### Environment

The runner refuses to call the classifier if `COPILOT_PROVIDER_BASE_URL` or
`COPILOT_PROVIDER_TYPE` is set, and removes `COPILOT_ALLOW_ALL` from the CLI's
environment. See [Model routing](../guide/model-routing.md#how-the-copilot-call-is-isolated).
