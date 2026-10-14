# Using the Copilot app

Keep this folder configured as a **Local, folder-backed project**. It has no Git
checkout requirement. Model selection in the app controls interactive assistance;
it does **not** override `classifier.json` for the external runner.

Two skills ship with the project:

| Skill | Use it for |
| --- | --- |
| [`mail-setup`](../.github/skills/mail-setup/SKILL.md) | First-run, read-only discovery of recurring senders and approved rule updates ([guide](getting-started.md#4-personalize-your-rules-mail-setup)) |
| [`mail-triage`](../.github/skills/mail-triage/SKILL.md) | Interactive review of pending mail, manual classification and task correction |

## Interactive review (recommended app use)

Open the project and ask:

> Use the mail-triage skill. Review the pending messages and summary. Work in dry
> run mode and ask before applying mailbox changes. Do not run another classifier
> unless the pending cases need it.

The skill supports manual classification and task/deadline correction. A manually
written decisions file must copy the **current** `pending.json` batch ID:

```json
{
  "batch_id": "<current pending batch_id>",
  "decisions": {
    "<message id>": "FYI",
    "<another message id>": {
      "tag": "Action",
      "task": {"title": "Approve the proposal", "due": "2026-10-08"}
    }
  }
}
```

```bash
python3 triage.py decide              # validates and previews manual decisions
python3 triage.py apply-plan          # previews the combined dry-run operation plan (make review)
python3 triage.py apply-plan --apply  # replay exactly the approved plan
```

A fresh `run`/`pending` creates a new batch ID. Decisions older than 24 hours,
foreign IDs, changed rules, unknown tags, invalid dates, prohibited tasks or
action overrides are rejected. Plain pre-migration decisions files must be
regenerated, not replayed. A subset is allowed for cases you can resolve.

`apply-plan` remains a separate human-approved replay path: it does not call a
model or repeat searches; it rejects plans older than 24h by default. Use it
promptly because mailbox state may have changed since the preview. `--exclude
rows.csv` excludes listed message IDs as in the original workflow.

## Running triage from the app on a timer

Prefer the [external schedule](scheduling.md). If you must use an app
Automation, see the [app-only alternative](scheduling.md#app-only-automation-alternative)
and its cost caveat.
