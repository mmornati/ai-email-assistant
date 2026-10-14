# Safety

The design goal is simple: nothing changes without your consent, nothing changes
that cannot be reverted, and nothing in an email can make the tool do something.
This page lists the mechanisms and, just as plainly, their limits.

## Dry run by default

Every command that changes Gmail or Google Tasks is a dry run unless you pass
`--apply`. A dry run reads mail metadata and writes only local files in `state/`,
such as `plan.json`, `summary.json`, `pending.json` and, for `triage.py`,
`dry-run.csv`. It does not create labels or task lists.

A dry run with classification (`make classify`) can still **cost model usage**:
it calls the classifier so you can see real decisions. `make preview`
(`python3 runner.py --no-model`) is the free preview. `make apply` asks for
confirmation before it passes `--apply`.

![The dry-run step in the demo console: planned changes, nothing applied](../assets/screens/console-preview-light.webp#only-light){ loading=lazy }
![The dry-run step in the demo console: planned changes, nothing applied](../assets/screens/console-preview-dark.webp#only-dark){ loading=lazy }

*Demo output on an invented mailbox.*

## A narrow set of actions

The only mailbox actions are: apply an `AI/*` label, `archive`, `mark_read`,
`star`, `important`, and `trash` where you configure it. Plus creating Google
Tasks. Nothing is sent, forwarded, unsubscribed or permanently deleted. Trashed
mail stays recoverable from Gmail Trash for 30 days, and trash operations are
journaled for undo.

`make setup` requests only the `gmail.modify` and `tasks` OAuth scopes.

## Validated model output

The classifier's answer is checked strictly before anything is applied:

- exactly the requested message IDs, no more and no fewer;
- exactly the fields `tag`, `task`, `confidence`, `needs_context`;
- tags that exist in your rules;
- tasks only where the tag's policy allows, with bounded title and notes and real
  `YYYY-MM-DD` dates;
- no completion-action overrides and no task text containing the task marker.

One invalid answer fails its whole batch; nothing from that batch is applied. The
model cannot invent a tag, add an action, or choose what happens when a task is
completed.

## Recheck before writing

On an applied run, right before writing, the runner fetches each classified
message's current labels. If a message has left the inbox or gained an `AI/*` label
since the scan, the run stops instead of acting on stale information.

## Unresolved mail stays in the inbox

Mail the model is unsure about is not guessed, archived or filed as "FYI". It stays
untagged in the inbox, its ID is listed in `state/summary.json`, and the run exits
with code `2`. See [Interactive review](../interactive-review.md) to resolve it,
and [Operations](../operations.md#retrying-held-mail) to retry it deliberately.

## `sweep_guard`

Every sweep query includes the `sweep_guard` from `rules.json`, `-is:starred` by
default. Starring a message keeps it out of every sweep. In the demo, a starred
newsletter older than a day stayed in the inbox while unstarred ones were swept.

The guard applies to sweeps only. `on_tag` and `on_task_done` actions do not use it.

## Plans and replay

A dry run's exact operations go to `state/plan.json`. `triage.py apply-plan
--apply` replays exactly that plan, without searching again or calling a model,
and refuses plans older than 24 hours by default. Decisions files and pending
batches are also tied to the current rules and expire after 24 hours.

`apply-plan` does not recheck the mailbox before writing. Use it promptly after a
preview.

## Journal and undo

Every applied label change and trash operation is appended to
`state/journal.jsonl`. `triage.py undo -n N --apply` reverts the last `N` entries:
it reverses label changes and restores trashed messages. It does not delete tasks
that were created.

Gmail and Google Tasks writes are not one atomic transaction. Tasks are created
before labels so that a failed task leaves the message untagged and eligible for
retry. After a partial failure, inspect the error and the journal. If a run fails
after rules and sweeps were applied, those changes stay applied; they are not
rolled back automatically.

## Private local state

- `state/` is created owner-only (`700`). `triage.py`, `runner.py`,
  `schedule.py` and `mail_setup.py` set a `077` umask, so new files are readable
  only by you; JSON state and usage files are written with mode `600`.
- `state/` and `rules.json` are excluded from Git and from the ZIP built by
  `make share` (`tools/share.py`); see [Sharing a ZIP](../sharing.md).
- State holds sensitive mail metadata and task details and is **not encrypted** by
  this application. Rely on FileVault and a protected user account, and do not share
  it. Review the permissions of any files that existed before you installed.

## Logs carry counts, not content

The runner captures the engine's per-message output privately. The one line it
prints, which the schedule writes to `state/schedule.log`, contains only status and
counts. When a run fails, `state/summary.json` records the exception **type**, not
its message, because external error messages can contain mail content.

Interactive `triage.py` commands print subjects and task titles to your terminal,
and `state/dry-run.csv` contains senders and subjects. Treat those as private.

## Email is untrusted data

Email content is written by other people, and some of it may try to instruct an AI.
The tool's stance:

- The classifier prompt states that email fields are untrusted data and that any
  instructions inside them must be ignored.
- The classifier has **no tools**: it can only return JSON, which is then
  validated. Even a fully manipulated answer is limited to choosing among your own
  tags and proposing a bounded task.
- Whichever classifier CLI `classifier.json` selects runs without tools, in an
  empty temporary directory, with mail passed on stdin. The Copilot CLI call
  disables MCP servers, custom instructions and remote export; the Claude Code
  call disables tools, MCP servers, skills, user settings and session
  persistence. The exact flags are in
  [Choosing the classifier CLI](../classifier-cli.md).
- The runner refuses to call a CLI when an environment variable would route mail
  to a different provider (for example `COPILOT_PROVIDER_BASE_URL` or
  `ANTHROPIC_BASE_URL`).
- The `mail-triage` and `mail-setup` skills, in Copilot or Claude Code, treat email
  content as untrusted data and never follow instructions found in it; `mail-setup`
  rejects senders whose mail contains suspicious AI instructions.
- The task marker is matched as the **last** marker in a task's notes, and
  proposed task text containing a marker is rejected, so mail text cannot hijack
  which thread a task controls.
- Title-based task deduplication applies only to automatic tasks, so a crafted
  subject cannot suppress the task for a real request.

## CSV formula neutralization

Subjects and senders are attacker-controlled. When `state/dry-run.csv` is written,
any cell that begins with `=`, `+`, `-`, `@`, a tab or a carriage return is
prefixed with a single quote, so a spreadsheet opens it as text instead of
evaluating it as a formula.

## Known limitations

From [SECURITY.md](https://github.com/mmornati/ai-email-assistant/blob/main/SECURITY.md):

- Gmail queries and task titles are passed to the `gws` CLI as command-line
  arguments, so other local users could see them in the process list while a call
  runs. Use a single-user machine.
- Model-reported confidence is not a calibrated probability.
- Data sent to Copilot is subject to GitHub's and the model provider's retention
  policies; data sent to Claude Code is subject to Anthropic's, which differ
  between a Claude subscription and API-key use.
- Claude Code with subscription auth still adds a short account section (the
  signed-in email) to each call.
- With Claude Code, the tag descriptions from `rules.json` are passed on the
  command line, so other local users can see them in the process list. Mail
  content never goes there.

To report a vulnerability, use GitHub's private vulnerability reporting, and never
include real mail, Gmail IDs, tokens or `state/` files in a report.
