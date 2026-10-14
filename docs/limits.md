# What it does not do

Knowing the limits is part of using this safely. Everything below follows from the
code and the guides.

## Mail actions

- It does not send, reply, forward or unsubscribe.
- It does not permanently delete anything. `trash` is opt-in and recoverable.
- It does not touch attachments.
- It does not mark mail read, star it or archive it unless your rules say so.
  The starter rules contain no cleanup actions at all.

## Coverage

- **Gmail only**, through the Google Workspace CLI. No other mail providers.
- **Google Tasks only** for to-dos.
- **Two classifier CLIs.** Models are called only through the GitHub Copilot CLI
  or Claude Code. There is no direct model API integration and no other provider.
  See [Choosing the classifier CLI](classifier-cli.md).
- **macOS only** for the schedule and the setup script.
- **Polling, not push.** It checks the inbox on a schedule (hourly on weekdays,
  08:00-19:00, by default). There is no Gmail push subscription or history cursor.
- **A recent window.** Normal runs look at inbox mail from the last 7 days
  (configurable), up to 500 messages per query. Older mail is left alone unless you
  run a backlog pass explicitly.
- **Inbox only.** Mail already archived is not classified.
- **The Mac must be on and you logged in.** Runs missed while the Mac is off or you
  are logged out are not queued; runs missed during sleep may be coalesced into one.

## Understanding mail

- The cheap model sees metadata and a 240-character snippet, not the body.
- The stronger model sees at most 4,000 characters of the message's own plain-text
  body. It does not see HTML-only content, attachments or earlier messages in the
  thread, so mail that depends on those may stay unresolved.
- It cannot safely infer requests or deadlines that the text does not state. If a
  deadline is not evidenced, the due date is a default of two business days.
- Confidence is self-reported by the model, **not calibrated**. There is no
  published accuracy figure for real mail.
- Uncertain mail is not guessed. It stays untagged in the inbox for you.
- There is no automatic "FYI" or archive fallback for unknown mail.

## Cost and capacity

- The per-run limits (100 fresh messages, 10 escalations by default) bound workload,
  **not money**. They are not a billing cap.
- A dry run with classification still costs model usage.
- Large backlogs are processed over several runs, or with an explicit window and
  limit.
- Running the job as an app automation pays for an agent session on every tick,
  even when nothing needs classifying. See [Costs](costs.md).

## Learning

- It does not learn from your corrections automatically. The `mail-setup` skill
  proposes exact-sender rules from a bounded recent sample, and the runner lists
  rule candidates, but **you** approve every rule.
- It does not train or fine-tune a model.

## Guarantees it does not make

- Gmail and Google Tasks changes are not one atomic transaction. A partial failure
  can leave tasks created without labels; inspect errors and the journal.
- Rule and sweep changes applied before a later failure in the same run are not
  rolled back.
- `undo` reverts labels and trash, but does not delete created tasks.
- `apply-plan` replays a reviewed plan without rechecking the mailbox; mail may have
  changed since the preview.

## Privacy

- `state/` is owner-only but **not encrypted** by the tool. Use FileVault and a
  protected account.
- Data sent for classification goes to the selected classifier CLI's provider:
  GitHub Copilot (GitHub's and the model provider's retention policies) or Claude
  Code (Anthropic's, which differ between a Claude subscription and API-key use).
- Gmail queries and task titles are visible in the local process list while a `gws`
  call runs. Use a single-user machine.
- The classifier call is isolated from tools, MCP servers and custom instructions,
  but account-level CLI context may still apply; with subscription auth, Claude
  Code adds a short account section with your sign-in email. It is not a bare
  model API call.

## Project status

- There are no published user numbers, testimonials, or accuracy or cost figures
  from real mailboxes. Numbers on this site come from a demo on an invented mailbox
  and are labeled as such.
- It is an independent project, not affiliated with Google or GitHub.
