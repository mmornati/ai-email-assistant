# Manual review

Some mail is deliberately left for you: messages the model could not resolve,
messages over the per-run capacity, and everything pending when you run without a
model. They stay **untagged in the inbox**. There is no automatic "FYI" or archive
fallback.

`state/summary.json` lists their IDs under `unresolved_ids`, and the scheduled run
exits with code `2` while any remain.

You can simply handle these messages in Gmail. If you want them tagged and turned
into tasks the same way as the rest, use the review workflow below.

## With Copilot: the `mail-triage` skill

Open the project as a local, folder-backed project in Copilot and ask:

> Use the mail-triage skill. Review the pending messages and summary. Work in dry
> run mode and ask before applying mailbox changes. Do not run another classifier
> unless the pending cases need it.

The skill reads `state/pending.json`, proposes a tag (and a task where the tag
allows one) for each message, writes `state/decisions.json`, previews the result
with `triage.py decide`, and asks you before applying. It treats email content as
untrusted data and never replies, forwards, unsubscribes or permanently deletes.

## By hand: `decisions.json`

A decisions file names the current pending batch and gives a decision per message
ID:

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

- `batch_id` must be copied from the **current** `state/pending.json`.
- A value is either a tag name, or an object with `tag` and optional `task`.
- `task` may contain `title` (1-250 characters, required), `notes` (up to 2,000
  characters), `due` (`YYYY-MM-DD`) and `on_done` (a list that can only narrow the
  tag's configured non-`trash` completion actions).
- You may include only the messages you can resolve. The rest stay in the inbox.

Then preview and apply:

```bash
python3 triage.py decide              # validate and preview
python3 triage.py decide --apply      # recheck the mailbox, create tasks, apply labels
```

`decide` reads `state/decisions.json` by default; pass another path as an argument
to use a different file.

### What gets rejected

`decide` validates the whole file before doing anything:

- a `batch_id` that is not the current pending batch;
- a pending batch older than 24 hours, or made with different rules;
- message IDs that are not in the current batch;
- unknown tags, or extra fields in a decision or task;
- a task on a tag whose policy is `never`;
- empty or over-long titles, over-long notes, malformed or impossible dates;
- task text containing a `[mail-triage` marker;
- `on_done` actions the tag does not already configure, or `trash`.

Plain decisions files in the older format (without `batch_id`) must be regenerated,
not replayed.

With `--apply`, `decide` also rechecks each message right before writing. If one has
left the inbox or already has an `AI/*` label, it stops with "mailbox changed since
classification; run again".

!!! warning "Scheduled runs replace the batch"
    Every run of `runner.py` or `triage.py run`/`pending` creates a new pending batch
    ID, and `runner.py` also overwrites `state/decisions.json` with its own
    decisions. Finish a manual review between scheduled runs, or
    [pause the schedule](schedule.md#pause-or-remove) while you work.

## Replaying a reviewed plan: `apply-plan`

Every dry run writes the exact operations it would perform to `state/plan.json`:
`triage.py run` starts a fresh plan, and later dry-run commands such as `decide`
replace only their own part of it. `apply-plan` executes that plan as previewed,
without searching again or calling a model.

```bash
python3 triage.py apply-plan                          # show what the plan contains
python3 triage.py apply-plan --apply                  # execute it
python3 triage.py apply-plan --apply --exclude rows.csv
```

- It refuses plans older than 24 hours. `--max-age-hours N` changes that limit.
- `--exclude rows.csv` takes a CSV with an `id` column (for example rows exported
  from `state/dry-run.csv`). Those message IDs are left out of label, archive and
  trash operations; a task is skipped if its thread ID is listed.
- Label, archive and trash operations run first, then tasks. A task is skipped if
  its thread already has one.
- Labels that did not exist at preview time are created when the plan is applied.
- After a successful apply, the plan is renamed
  `state/plan.applied-<timestamp>.json`, so it cannot be replayed twice by accident.

!!! note "Use it promptly"
    `apply-plan` does not recheck the mailbox the way `decide --apply` does. If mail
    has moved since the preview, the plan is applied to it anyway. Apply soon after
    reviewing, or run a fresh dry run.

## Undo

```bash
python3 triage.py undo -n 3            # preview reverting the last 3 journal entries
python3 triage.py undo -n 3 --apply
```

Each line of `state/journal.jsonl` is one applied operation. `undo` reverses its
label changes, or restores trashed messages, and removes the line. It does not
delete tasks.

## Backlog, once

After reviewing your rules, and only with your explicit approval, a whole-inbox
backlog can be tagged and swept with the deterministic engine:

```bash
python3 triage.py tag   --window '' --limit 8000 --apply
python3 triage.py sweep --limit 8000 --apply
```

To preview whole-inbox processing including classification (paid if anything is
pending):

```bash
python3 runner.py --window '' --limit 8000
```

The `mail-triage` skill also describes classifying leftover human mail older than
30 days in batches of about 300, with
`triage.py pending --window 'older_than:30d' --limit 300` followed by `decide`.
