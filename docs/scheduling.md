# Scheduling

The recommended schedule runs **outside the AI app**, as a macOS launchd
job. Empty runs start no AI session and cost nothing in model tokens.

## Install

```bash
make schedule-render     # python3 schedule.py render   — inspect; does not install
make schedule-install    # python3 schedule.py install  — persistent; future runs use --apply
make schedule-status     # python3 schedule.py status   — registered job and last exit code
```

`install` checks that the classifier CLI selected in `classifier.json` is on
`PATH` and prints which one the job will use. It refuses Claude Code with
`"auth": "api_key"`, because the job never stores an API key.

The installer records the absolute current interpreter path and current `PATH`.
It creates `~/Library/LaunchAgents/local.ai-mail-assistant.plist` and registers
it in the current user's GUI session. **Installation does not run a scan.**
It refuses to overwrite an existing job.

If your interpreter is managed by a version manager, use its absolute path
to avoid relying on interactive-shell setup:

```bash
/absolute/path/to/python3 schedule.py install
```

If you prefer an entirely model-free schedule or previews only:

```bash
python3 schedule.py install --no-model
python3 schedule.py install --dry-run
```

These are alternative installations, not additional jobs. To change installation
options, uninstall, then install again. Model/rule edits are read on each run and
do not require reinstalling; interpreter, `PATH`, or project-path changes do.
Switching `cli` is a config edit too, as long as the other CLI's binary is on the
`PATH` recorded at install time (for example `~/.local/bin` for Claude Code's
native installer); otherwise reinstall.

> [!IMPORTANT]
> Do not run the external schedule and an app automation at the same time.

## Timing and machine lifecycle

The job runs **Monday–Friday, hourly at minute 00, from 08:00 through 19:00
inclusive**, in the Mac's local timezone: 12 opportunities/day, 60/week,
approximately 264 in a 22-workday month. The equivalent cron expression is
`0 8-19 * * 1-5`; the installed job uses calendar entries, not cron.

It runs as the logged-in user, without a terminal or the Copilot/Claude app being open.
The Mac must be powered on and that user logged in. Calendar events missed during
sleep may be coalesced into one wake-up run, not replayed hour by hour. Missed runs
while shut down/logged out are not a guaranteed backlog queue. `--scheduled`
skips wake-up catch-ups outside weekday 08:00–19:59.

`state/run.lock` prevents overlapping runner/triage commands. A competing process
exits explicitly rather than modifying shared state. The file can remain after
exit; the OS releases the actual lock automatically, including after a crash.

## Monitoring

The external job does **not** create an app Automation run card or automatically
open an app chat. Its status is in local files:

```bash
make schedule-status
make summary                          # cat state/summary.json
tail -n 20 state/schedule.log
tail -n 20 state/schedule-error.log
make usage                            # python3 runner.py --usage-report
```

| Exit code | Meaning |
| --- | --- |
| `0` | Finished |
| `2` | Mail still needs review, or exceeded per-run capacity |
| other | Failure (including a competing lock holder) |

`summary.json` has counts, newly created task titles/due dates/Gmail links,
unresolved IDs, recurring bulk-sender rule candidates and an explicit status/error
type; it is replaced each run. The schedule retries on its next calendar tick,
not in a tight restart loop. Counts in a dry-run summary are planned, not applied.

For immediate manual processing, run `runner.py` directly; it need not wait for
the next calendar event.

## Pause or remove

```bash
make schedule-uninstall               # python3 schedule.py uninstall — mail is untouched
```

## Disable any app automation

If you previously ran triage as a Copilot app Automation, disable it when using
the external schedule. Keeping it enabled reintroduces AI startup cost on every
tick.

## App-only automation alternative

If an external schedule is unsuitable, uninstall it first, then create/edit a
Local project Automation (described for Copilot) with:

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

**This alternative still pays for the parent app session on empty runs.**
The runner's classifier is a separate CLI process with its own model setting.
Do not claim this option achieves zero-token scans overall.
