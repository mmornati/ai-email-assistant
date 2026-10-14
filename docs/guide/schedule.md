# Schedule

The recommended setup is a local macOS schedule that runs `runner.py` directly.
It does not start an AI session at all when there is no unresolved mail. Copilot
is the classifier and the interactive review tool, not the scheduler.

## Install

```bash
python3 schedule.py render     # print the generated job; installs nothing
python3 schedule.py install    # register the job; future runs use --apply
python3 schedule.py status     # show the registered job and its last exit code
```

`install`:

- records the **absolute path of the interpreter** you ran it with, and your current
  `PATH`;
- checks that the interpreter exists and that `gws` (and `copilot`, unless
  `--no-model`) are on that `PATH`;
- writes `~/Library/LaunchAgents/local.ai-mail-assistant.plist` and registers it in
  your user's GUI session with `launchctl bootstrap`;
- **does not run a scan**: the first run happens at the next scheduled time;
- refuses to overwrite an existing job.

If your Python comes from a version manager, install with its absolute path so the
job does not depend on interactive shell setup:

```bash
/absolute/path/to/python3 schedule.py install
```

### Variants

```bash
python3 schedule.py install --no-model   # rules and cache only; never calls a model
python3 schedule.py install --dry-run    # previews only; never changes the mailbox
```

These are alternative installations, not extra jobs. A `--dry-run` schedule can
still make paid model calls unless you also pass `--no-model`.

To change installation options, uninstall and install again. Edits to `rules.json`
and `classifier.json` are read on every run and need no reinstall. A new
interpreter, a changed `PATH`, or moving the project folder does.

### What the job runs

```text
<python> <project>/runner.py --scheduled --apply [--no-model]
```

(`--apply` is left out with `--dry-run`.) The working directory is the project
folder, standard output goes to `state/schedule.log`, and standard error to
`state/schedule-error.log`.

## Timing

The job runs **Monday to Friday, hourly at minute 00, from 08:00 through 19:00
inclusive**, in the Mac's local time zone: 12 runs a day, 60 a week, about 264 in a
22-workday month. The equivalent cron expression is `0 8-19 * * 1-5`, but the job
uses launchd calendar entries, not cron.

## The machine lifecycle

- It runs as you, without a terminal or the Copilot app open. The Mac must be on
  and you must be logged in.
- Runs missed while the Mac sleeps may be coalesced into one run on wake, not
  replayed hour by hour. Runs missed while it is shut down or logged out are not
  queued.
- `--scheduled` makes a wake-up run outside weekdays 08:00-19:59 exit at once,
  without scanning or calling a model.
- If a run fails, the next attempt is the next calendar tick. There is no tight
  restart loop.
- Two runs never overlap: `state/run.lock` makes a competing process exit.

Every real run still syncs completed tasks and sweeps existing labels, even with no
new mail. Those steps make Gmail and Tasks API calls but no model calls.

This is **polling**, not a Gmail push subscription or history cursor. Each run
looks at the inbox within `default_window` (`newer_than:7d` by default), up to 500
messages per query. Already classified mail is excluded by its `AI/*` label.

## Exit codes and logs

| Exit code | Meaning |
| --- | --- |
| `0` | Finished. |
| `2` | Mail still needs review, or exceeded the per-run capacity. |
| other | Failure, including a competing lock holder. |

The job has no app notification or chat. Check its state with:

```bash
python3 schedule.py status
cat state/summary.json
tail -n 20 state/schedule.log
tail -n 20 state/schedule-error.log
python3 runner.py --usage-report
```

`state/schedule.log` holds one line of counts and status per run. In the
[demo](../getting-started/demo.md), on an invented mailbox, the applied run printed:

```text
[runner] apply needs_review: 9 classified, 11 archived, 1 unresolved; summary: ~/ai-email-assistant/state/summary.json
```

The engine's per-message output (subjects, senders, task titles) is not written to
the schedule log. Error messages go to `state/schedule-error.log`. `state/summary.json` is replaced on every run;
see [State files](../reference/state-files.md#summaryjson).

Log files accumulate; rotate or archive them privately if they grow.

## Run now

To process mail immediately, run the runner yourself; it does not need to wait for
the schedule:

```bash
python3 runner.py --apply
```

## Pause or remove

```bash
python3 schedule.py uninstall
```

This unloads the job and deletes the plist. Your mailbox and `state/` are unchanged.

## Alternative: a Copilot app automation

If a launchd job is not suitable, you can run the same command from a Copilot app
Automation instead. **Uninstall the launchd job first**; do not run both.

| Setting | Value |
| --- | --- |
| Environment | Local |
| Workspace | This folder |
| Mode | Autopilot |
| Schedule | Custom cron: `0 8-19 * * 1-5` |
| Parent model | A lightweight permitted model, or Auto with Efficiency |
| Prompt | The prompt below |

> Run `python3 runner.py --apply` in this project. Do not classify mail yourself,
> load the mail-triage skill, or launch subagents. Read state/summary.json and
> report its status and counts briefly. If exit code is 2, report that unresolved
> messages require review. If the command fails, report failure; do not bypass
> validation or retry in a loop.

!!! warning "This alternative is not free on empty runs"
    The app starts a full agent session on every tick, even when the inbox is
    empty, and you pay for that parent session. The runner's classifier is still a
    separate CLI process with its own model setting. Only the launchd schedule
    achieves zero model tokens on quiet runs.

If you previously used an app automation and switch to the launchd schedule,
disable the automation: leaving it on brings back the AI startup cost on every
tick.

## Other platforms

`schedule.py` works only on macOS. On other systems it stops with a message
suggesting you run `runner.py` from your platform's own scheduler. That path is not
documented or covered by this project's setup script.
