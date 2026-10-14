# Your first run

Work through these in order. Only the last step changes your mailbox.

## 1. Run the offline tests

```bash
cd /path/to/ai-email-assistant
python3 -m unittest discover -q -s tests -t .
```

The tests never touch a real mailbox, Google Tasks or a paid model.

## 2. Preview the rules, without a model

```bash
python3 runner.py --no-model
```

This is a dry run that never calls a model. It reads mail metadata, works out
what your rules would tag, sweep and archive, and lists the inbox mail no rule
matched. Nothing in Gmail or Google Tasks changes.

With the starter rules, which contain no sender queries, every recent inbox
message ends up pending, and the command exits with code 2. That is expected: it
means mail is waiting for classification or review.

!!! tip "Fewer pending messages means fewer model calls"
    Before paying for classification, consider [personal rules](personal-rules.md).
    Every message a rule recognizes is never sent to a model.

## 3. Preview with classification

```bash
python3 runner.py
```

Still a dry run: nothing in the mailbox changes. But this one may call the
classifier, so **it can incur model charges**. Validated classifications are saved
in a same-day cache, so a later `--apply` the same day reuses them instead of
paying again.

![Terminal output of a dry run](../assets/screens/terminal-dry-run-light.webp#only-light){ loading=lazy }
![Terminal output of a dry run](../assets/screens/terminal-dry-run-dark.webp#only-dark){ loading=lazy }

*Demo output on an invented mailbox.*

The runner prints a single line with counts, for example (from the demo):

```text
[runner] dry-run needs_review: 9 classified, 11 archived, 1 unresolved; summary: ~/ai-email-assistant/state/summary.json
```

In a dry run, "archived" and the task counts are **planned**, not applied.

## 4. Read what it would do

Three files in `state/` tell you everything:

`state/summary.json`
:   Counts per tag and per action, how many messages would leave the inbox, the
    tasks that would be created (title, due date, Gmail link), the IDs of messages
    left for review, and bulk senders suggested as new rules.

`state/pending.json`
:   The untagged inbox messages that reached classification: sender, recipients,
    date, subject and a short snippet.

`state/plan.json`
:   The exact list of operations the dry run would perform: label changes,
    archives, trash (if configured) and task creations.

For a per-message view of the rule-based part, run the deterministic engine on
its own; it writes a CSV you can open in a spreadsheet:

```bash
python3 triage.py run          # dry run; writes state/dry-run.csv and state/plan.json
```

See [State files](../reference/state-files.md) for every field.

## 5. Apply

When the preview looks right, you have two options.

=== "Fresh applied run"

    ```bash
    python3 runner.py --apply
    ```

    Scans again, reuses today's cached classifications where nothing changed,
    validates, rechecks the mailbox, then creates tasks and applies labels and
    actions.

=== "Replay the reviewed plan"

    ```bash
    python3 triage.py apply-plan           # show what the plan contains
    python3 triage.py apply-plan --apply   # execute exactly that plan
    ```

    Replays `state/plan.json` as previewed, without searching again or calling a
    model. It refuses plans older than 24 hours by default. Mailbox state may have
    changed since the preview, so use it promptly. See
    [Manual review](../guide/review.md).

Either way, applied label changes and trash operations are recorded in
`state/journal.jsonl`, one line per operation. An applied run usually writes
several lines (for example one per tag and one per sweep). To revert the last
three:

```bash
python3 triage.py undo -n 3           # preview
python3 triage.py undo -n 3 --apply   # revert
```

`undo` reverts labels, archive, read state and trash. It does not delete tasks
that were created. Look at the end of `state/journal.jsonl` first to choose `-n`.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Finished; nothing left for review. |
| `2` | Finished, but some mail still needs review or exceeded the per-run capacity. |
| other | Failure, including another run holding the lock. |

## Next

- [Personal rules](personal-rules.md) to cut model calls.
- [Schedule](../guide/schedule.md) to run hourly on weekdays.
- [Manual review](../guide/review.md) to resolve what the model left for you.
