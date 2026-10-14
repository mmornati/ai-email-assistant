# FAQ

## Does it read my whole mailbox?

No. A normal run searches only the **inbox**, within the `default_window`
(`newer_than:7d` unless you change it), up to 500 messages per query. Sweeps look at
inbox mail that already carries one of its `AI/*` labels, regardless of age. The
sync step reads your task list and the label state of threads whose task you
completed.

For pending mail it fetches only metadata headers (From, To, Cc, Subject, Date,
List-Unsubscribe) and Gmail's snippet. It fetches a message **body** only when that
message is escalated to the stronger model, and then only up to 4,000 characters
of plain text from that message, without attachments or other thread messages.

The `mail-setup` discovery reads at most 200 received messages from the last 30
days, including archived mail, headers and snippets only, unless you raise the
bounds explicitly (hard caps 500 messages and 90 days).

A whole-inbox pass happens only if you ask for one, with `--window ''`.

## What is sent to the model?

For each pending message: its Gmail message and thread IDs, From, To and Cc (each
truncated to 200 characters), date, subject, a snippet of up to 240 characters, and
whether it has a `List-Unsubscribe` header. Plus your tag names, descriptions and
task policies. Escalated messages also include their bounded plain-text body.
Mail matched by a rule is never sent.

## What does it cost?

A run that rules and the same-day cache resolve completely makes **zero model
calls**, so it costs no model tokens. Gmail and Tasks API calls still take time and
use your normal Google quota.

When the classifier runs, the cost depends on your Copilot plan, the models'
rates, how many messages need classification, and how many escalate. The project
does not publish costs from real mailboxes. The README gives the per-token rates it
checked on 2026-10-07, two synthetic single-call probes, and clearly labeled
illustrative monthly scenarios; see its
[costs section](https://github.com/mmornati/ai-email-assistant#costs-and-token-estimates).
Prices and your organization's billing can change.

To see your own usage, run `python3 runner.py --usage-report` and reconcile with your
Copilot usage view. The per-run limits in `classifier.json` bound the workload, not
the bill.

Running the job as a Copilot app automation instead of the launchd schedule costs
more: the app starts an agent session on every tick, even when the inbox is empty.

## Which models does it use?

By default `gpt-6-luna` for the first pass and `gpt-6.1-sol` for escalations,
through the GitHub Copilot CLI and your Copilot account. You can name other models
in `classifier.json`, as long as your account and organization policy allow them.
The model selected in the Copilot app does not change what the runner uses.

[ADR 0001](adr/0001-laya-vs-luna.md) explains why a local model was evaluated and
not adopted.

## Can I run it without a model?

Yes. `python3 runner.py --no-model` uses rules and the same-day cache only and never
starts the Copilot CLI. `python3 schedule.py install --no-model` schedules exactly
that, and `scripts/setup-macos.sh --skip-copilot` installs without the Copilot CLI.

Without a model, mail no rule matches stays untagged in the inbox, and runs exit
with code 2 while any is pending. `triage.py` also works entirely without a model,
and you can classify pending mail yourself with a [decisions file](guide/review.md).

## Why macOS only?

The schedule is a launchd job created by `schedule.py`, which refuses to run on
other systems, and the setup script relies on macOS and Homebrew. The engine itself
is plain Python with no third-party runtime dependencies; on another system,
`schedule.py` suggests running `runner.py` from your platform's scheduler. That
setup is not documented or supported by this project.

## Why Gmail only?

The engine is built on Gmail's search syntax and labels and on Google Tasks, through
the Google Workspace CLI. There is no support for other mail providers.

## Is it push or polling?

Polling. The schedule runs hourly on weekdays from 08:00 to 19:00 and looks at the
recent inbox each time. There is no Gmail push subscription or history cursor, so
new mail waits until the next run (or until you run `runner.py` yourself).

## What if the model is wrong?

- Its answers are validated: it can only choose among your tags, propose bounded
  tasks, and cannot add actions.
- Doubtful answers (low reported confidence or `needs_context`) go to a stronger
  model, and if still doubtful, stay in the inbox for you.
- Confidence is self-reported and not calibrated, so a confident answer can still
  be wrong. Review representative output from your own mail before relying on it
  unattended, and keep cleanup actions conservative.
- A wrong label can be removed in Gmail, or reverted with `triage.py undo`. A wrong
  task can be deleted in Google Tasks.

## How do I undo?

```bash
python3 triage.py undo -n 3            # preview reverting the last 3 journal entries
python3 triage.py undo -n 3 --apply
```

Every applied label change and trash operation is journaled in
`state/journal.jsonl`; undo reverses them, restoring trashed mail. It does not
delete tasks. See [Safety](guide/safety.md#journal-and-undo).

## Will it send, delete or unsubscribe?

No. It never sends, forwards, replies, unsubscribes or permanently deletes. The only
actions are labels, archive, mark read, star, important, and `trash` if you
configure it (recoverable for 30 days).

## Where does my data go?

- Mail metadata, decisions, plans and logs stay in the local `state/` folder,
  owner-only and **not encrypted** by the tool; use FileVault.
- Classification requests go to GitHub Copilot under your account, and are subject
  to GitHub's and the model provider's retention policies.
- Gmail and Tasks access goes through the Google Workspace CLI with your own OAuth
  client and the `gmail.modify` and `tasks` scopes.
- Routine schedule logs contain counts, not subjects or bodies.
- Gmail queries and task titles are passed to `gws` as command-line arguments, so
  other local users could see them in the process list during a call. Use a
  single-user machine.

## Can someone take over the assistant by emailing me?

Email content is treated as data. The classifier has no tools, its output is
validated, and the worst a manipulated answer can do is pick one of your tags or
propose a bounded task. See [Safety](guide/safety.md#email-is-untrusted-data).

## Does it work with a work account?

Nothing in the code distinguishes personal and work accounts. It needs a Gmail
account you can authorize with the `gmail.modify` and `tasks` scopes, and a Copilot
account allowed to use the configured models (unless you run model-free). Your
organization may restrict OAuth clients, mailbox automation or AI processing of
email. You are responsible for following those policies.
