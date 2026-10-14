# Try the demo

The demo runs the production engine end to end on an invented mailbox. It needs no
Google account, no Copilot account and no network access, and it makes no paid
model calls.

You can also step through a recorded run in the browser:
[open the online demo console](https://mmornati.github.io/ai-email-assistant/demo/).

## Run it

From the project folder:

```bash
python3 demo/run_demo.py
```

The engine needs Python 3.10 or newer. macOS ships Python 3.9 as `python3`; if the
demo stops with `the engine needs Python 3.10+`, run it with a newer interpreter,
for example the one the [setup script](install.md) installs.

Options:

| Option | Effect |
| --- | --- |
| `--quiet` | Do not print the commands and their output. |
| `--out run.json` | Also write a JSON snapshot of every step (the mailbox, tasks, summary and model calls after each step). |
| `--workspace DIR` | Keep the throwaway workspace in `DIR` (new or empty) instead of a temporary folder, so you can inspect its `state/` afterwards. |

By default nothing is kept: the workspace is a temporary folder that is deleted at
the end.

## What is real and what is fake

The demo copies `triage.py`, `runner.py` and `classifier.json` into a temporary
workspace, writes the demo `rules.json` there, and puts `demo/fakes/` first on
`PATH`. Two programs in that folder stand in for the real CLIs:

`demo/fakes/gws`
:   A stand-in for the Google Workspace CLI. It serves the invented mailbox from a
    JSON file and answers the exact Gmail and Google Tasks calls `triage.py` makes,
    with a small Gmail query evaluator (`in:`, `is:`, `label:`, `from:`, `to:`,
    `subject:`, `newer_than:`, `older_than:`, `OR`, negation and parentheses).
    Nothing leaves the machine.

`demo/fakes/copilot`
:   A stand-in for the GitHub Copilot CLI. It reads the real prompt `runner.py`
    sends on stdin and answers with a scripted classification for each message,
    in the same JSON event format the real CLI produces. Its token counts are
    estimated from text length and are **not real usage**.

Everything else is the production code path: rule matching, sweeps, the pending
batch, the classification cache, escalation, validation, the mailbox recheck,
task creation and deduplication, task-completion sync, the journal and
`state/summary.json`.

The mailbox and rules live in `demo/demo_mailbox.py`. The mailbox belongs to an
invented "Sam Rivera" at an invented company. All domains use the reserved
`.example` top-level domain. The scripted classifier answers, including their
confidence values, are written by hand in that file; they are not output from a
real model.

## What each step shows

The demo prints each command with its output, then a one-line recap per step.
The figures quoted here come from a demo run on the invented mailbox. Task due
dates depend on the day you run it.

### 1. Arrive

38 messages in the inbox, all unread: requests from colleagues and a client,
calendar traffic, code-review notifications, monitoring alerts, document shares,
receipts, internal announcements, newsletters, promotions, a meeting-notes bot,
and one 12-day-old message outside the default 7-day window.

### 2. Dry run preview

```text
$ python3 triage.py run
$ python3 runner.py
```

`triage.py run` shows the deterministic part on its own: rules tag 27 messages,
the promotions are archived as soon as they are tagged, sweeps plan to archive the
resolved alert and the code-review and newsletter mail older than a day, and 10
untagged messages are written to `state/pending.json`.

`runner.py` repeats the scan and classifies the 10 pending messages. The cheap
model receives all 10 in one call. Three come back as needing context or below
the confidence threshold, so they go to the stronger model in one call, with
their plain-text body. Two of those are resolved; one ("Friday?") is still
ambiguous and is held for review.

![The dry-run step in the demo console](../assets/screens/console-preview-light.webp#only-light){ loading=lazy }
![The dry-run step in the demo console](../assets/screens/console-preview-dark.webp#only-dark){ loading=lazy }

*Demo output on an invented mailbox.*

The runner prints one line:

```text
[runner] dry-run needs_review: 9 classified, 11 archived, 1 unresolved; summary: ~/ai-email-assistant/state/summary.json
```

Nothing in the mailbox has changed. The 11 archives and 4 tasks are planned, and
the 9 validated classifications are saved in the same-day cache. A three-message
bulk sender that no rule knew yet (`events@summit.example`) is listed in the
summary as a rule candidate that requires approval.

### 3. Apply

```text
$ python3 runner.py --apply
$ python3 runner.py --usage-report
```

The applied run reuses the 9 cached classifications, so it makes **no model
call**. It rechecks that each message is still in the inbox and unlabeled, creates
the 4 tasks, applies labels, and archives 11 messages. The inbox goes from 38 to 27.

![The apply step in the demo console](../assets/screens/console-apply-light.webp#only-light){ loading=lazy }
![The apply step in the demo console](../assets/screens/console-apply-dark.webp#only-dark){ loading=lazy }

*Demo output on an invented mailbox.*

`--usage-report` sums the recorded model calls: one call per model in this run.
In the demo the token figures come from the stand-in and are estimates, not
billing data.

### 4. Quiet hour

```text
$ python3 runner.py --apply
```

The next run finds nothing new. The one ambiguous message was already held for
review today, so it is not sent to a model again. No model call is made. The run
exits with code 2 because one message still needs a person.

![The quiet-hour step in the demo console](../assets/screens/console-quiet-light.webp#only-light){ loading=lazy }
![The quiet-hour step in the demo console](../assets/screens/console-quiet-dark.webp#only-dark){ loading=lazy }

*Demo output on an invented mailbox.*

### 5. Task done

The demo marks the task "Approve the Q4 hiring plan (two senior roles)" as
completed in the fake Google Tasks, then runs `runner.py --apply` again. The sync
step sees the completed task and applies the `Action` tag's `on_task_done` action
(`archive`) to that thread. The inbox goes from 27 to 26. Still no model call.

## Reading the result

After the steps, the demo prints a recap such as:

```text
[preview] Dry run: rules plan, the model classifies what rules cannot: status=needs_review model calls=2 tasks=0 in inbox=38
[apply] Applied run: cached decisions reused, labels and tasks written: status=needs_review model calls=0 tasks=4 in inbox=27
[quiet] The next hour: nothing new, no model call: status=needs_review model calls=0 tasks=4 in inbox=27
[done] A completed task archives its thread: status=needs_review model calls=0 tasks=4 in inbox=26
```

`status=needs_review` on every step is the "Friday?" message: it is deliberately
left untagged in the inbox rather than guessed.

To look at the state files the engine wrote, keep the workspace:

```bash
python3 demo/run_demo.py --workspace /tmp/mail-demo
ls /tmp/mail-demo/state
```

[State files](../reference/state-files.md) explains each one.
