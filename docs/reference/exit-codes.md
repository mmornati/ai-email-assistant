# Exit codes

## `runner.py`

| Code | Meaning |
| --- | --- |
| `0` | Finished, nothing left for review. Also returned by `--usage-report`, and by `--scheduled` outside weekday hours (no scan). |
| `2` | Finished, but some mail still needs review or exceeded the per-run capacity. `state/summary.json` has `status: "needs_review"` and lists `unresolved_ids`. |
| `1` | Failure: a Gmail or Copilot CLI error, a validation failure, a timeout, an invalid configuration, or another process holding the lock. The message is printed to standard error; `summary.json` records `status: "error"` and the error type, except when the lock was held, in which case it is left untouched. |

`2` is not an error: with `--no-model`, or with the starter rules, it is the
expected result whenever untagged mail is waiting. The setup script treats it as
success for its verification dry run.

!!! note "Command-line mistakes also exit 2"
    Python's argument parser exits with `2` for invalid options, for example
    `--limit 0`. In that case it prints a usage message and no run takes place, and
    `summary.json` is not updated.

## `triage.py`

| Code | Meaning |
| --- | --- |
| `0` | Finished. |
| `1` | Failure, with a message on standard error: for example a `gws` error, a rejected decisions file, a stale or missing plan, "nothing to undo", an unknown action, or another process holding the lock. |
| `2` | Invalid command-line usage. |

## `schedule.py`

| Code | Meaning |
| --- | --- |
| `0` | Finished. |
| `1` | Failure (`schedule failed: ...`): `launchctl` error, job already installed, no installed job to remove, or missing interpreter, `gws` or `copilot`. |
| `2` | Invalid usage, or not running on macOS. |

## `mail_setup.py`

| Code | Meaning |
| --- | --- |
| `0` | Finished. |
| `1` | Failure (`mail setup failed: <type>; no mailbox mutations performed`), including stale or invalid selections. |
| `2` | Invalid usage, including out-of-range `--limit`, `--days`, `--max-groups`, or `--apply` with a command other than `approve`. |

## `share.py`

| Code | Meaning |
| --- | --- |
| `0` | ZIP created. |
| `1` | Packaging failed (`packaging failed: ...`). Any previous ZIP is left in place. |

## `scripts/setup-macos.sh`

| Code | Meaning |
| --- | --- |
| `0` | Finished. |
| `64` | Unknown option. |
| nonzero | A check or command failed (for example not macOS, no Homebrew, the conflicting `gws` formula, or failing tests). |

## The launchd job

`python3 schedule.py status` shows the job's last exit code, which is the
`runner.py` code above. A failed scheduled run is retried at the next calendar tick.
