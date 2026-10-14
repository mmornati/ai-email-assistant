# Commands and flags

For everyday use, run the `make` targets: `make help` lists them, and
[Operations](../operations.md#command-reference) maps each one to the command it
runs. This page is the complete flag reference for the scripts underneath.

Run every command from the project folder. Every command that can change Gmail or
Google Tasks is a dry run unless `--apply` is given.

## `runner.py`

The scheduled entry point: model-free scan, gated classification, validation,
application and summary.

```bash
python3 runner.py [options]
```

| Option | Default | Effect |
| --- | --- | --- |
| `--apply` | off | Apply rules and validated decisions. Without it, a dry run. |
| `--no-model` | off | Rules and cache only; never invoke a model. Uncached pending mail stays for review. |
| `--retry-review` | off | Retry mail held for review today (a paid retry). |
| `--scheduled` | off | Exit 0 without scanning if run outside weekdays 08:00-19:59 local time. Used by the schedule. |
| `--usage-report` | off | Print recorded token totals per `cli/model` from `state/usage.jsonl`; no scan, no model call. (`make usage`) |
| `--cli {copilot,claude}` | `cli` from `classifier.json` | Use this classifier CLI for this run only; the file is unchanged. |
| `--select-cli {copilot,claude}` | | Set `cli` in `classifier.json` (only that key is rewritten) and exit; no scan, no model call. |
| `--config PATH` | `classifier.json` | Classifier configuration. |
| `--rules PATH` | `rules.json` | Rules file. |
| `--window QUERY` | `default_window` from rules | Gmail time filter. `''` means the whole inbox. |
| `--limit N` | `500` | Maximum messages per Gmail query. Must be positive. |

Examples:

```bash
python3 runner.py --no-model                 # free preview (make preview)
python3 runner.py                            # preview with classification, may cost (make classify)
python3 runner.py --apply                    # real run (make apply, after a prompt)
python3 runner.py --window '' --limit 8000   # preview whole-inbox processing
python3 runner.py --usage-report             # make usage
python3 runner.py --select-cli claude        # switch the classifier CLI
```

Output: one line of status and counts. Writes `state/summary.json` on every run.

## `triage.py`

The deterministic engine and the interactive commands.

```bash
python3 triage.py [--rules PATH] <command> [options]
```

`--rules PATH` (default `rules.json`) goes **before** the command.

### Commands

| Command | What it does |
| --- | --- |
| `run` | `sync`, then `tag`, then `sweep`, then `pending`. No model call. |
| `tag` | Apply rule-based tags (Gmail queries in `rules.json`), `on_tag` actions, and tasks for `always` tags. |
| `sweep` | Run each tag's sweeps. |
| `pending` | Write untagged inbox mail in the window to `state/pending.json` with a new batch ID. Changes nothing in Gmail. |
| `decide [FILE]` | Validate and apply decisions from `FILE` (default `state/decisions.json`), then run sweeps. |
| `sync` | For completed Google Tasks, apply the tag's `on_task_done` actions to the thread's inbox messages. |
| `apply-plan` | Replay `state/plan.json` from the last dry run(s). |
| `undo` | Revert the last N applied journal entries. |

### Options

| Option | Commands | Default | Effect |
| --- | --- | --- | --- |
| `--apply` | all | off | Actually modify Gmail and Tasks. |
| `--limit N` | `run`, `tag`, `sweep`, `pending`, `decide`, `sync` | `500` | Maximum messages per query. |
| `--report FILE` | `run`, `tag`, `sweep`, `pending`, `decide`, `sync` | `state/dry-run.csv` in a dry run; none when applying | Write a per-message CSV of tags, actions and tasks. |
| `--window QUERY` | `run`, `tag`, `pending` | `default_window` | Gmail time filter, for example `newer_than:7d`; `''` for the whole inbox. |
| `-n N` | `undo` | `1` | Number of journal entries to revert (at least 1). |
| `--max-age-hours H` | `apply-plan` | `24` | Refuse plans older than this. |
| `--exclude CSV` | `apply-plan` | none | CSV with an `id` column of messages to leave untouched. |

In a dry run, `run` starts a fresh `state/plan.json` and `state/dry-run.csv`; later
dry-run commands such as `decide` merge into them.

Examples:

```bash
python3 triage.py run                       # deterministic dry run, default window
python3 triage.py run --apply               # deterministic changes, no classification
python3 triage.py pending                   # new pending batch
python3 triage.py decide                    # validate and preview decisions
python3 triage.py decide --apply
python3 triage.py sync --apply              # sync completed tasks only
python3 triage.py apply-plan --apply
python3 triage.py undo -n 3 --apply
```

## `schedule.py`

Render, install, inspect or remove the macOS launchd job. macOS only.

```bash
python3 schedule.py {render,install,status,uninstall} [options]
```

| Command | Effect |
| --- | --- |
| `render` | Print the job definition (plist). Installs nothing. |
| `install` | Write `~/Library/LaunchAgents/local.ai-mail-assistant.plist` and register it. No immediate run. Refuses if the file exists. |
| `status` | Print `launchctl print` for the job, including its last exit code. |
| `uninstall` | Unload the job and delete the plist. Mail and `state/` are unchanged. |

| Option | Default | Effect |
| --- | --- | --- |
| `--python PATH` | the interpreter running `schedule.py` | Absolute interpreter path recorded in the job. |
| `--no-model` | off | Install a strictly model-free schedule (`runner.py --no-model`). |
| `--dry-run` | off | Schedule previews instead of mailbox changes (omits `--apply`). |

The `make schedule-render`, `make schedule-install`, `make schedule-status` and
`make schedule-uninstall` targets run these commands with default options.

`install` requires the interpreter to exist, `gws` on `PATH`, and, unless
`--no-model`, the classifier CLI selected in `classifier.json` on `PATH`. It
refuses Claude Code with `"auth": "api_key"`. See [Scheduling](../scheduling.md).

## `mail_setup.py`

Read-only sender discovery, and preview/approval of exact-sender rules. Usually
driven by the `mail-setup` skill.

```bash
python3 mail_setup.py {discover,preview,approve} [options]
```

| Command | Effect |
| --- | --- |
| `discover` | Read a bounded sample of recent received mail and write `state/setup-discovery.json`. No mailbox changes, no model calls. |
| `preview` | Validate `state/setup-selections.json` against the discovery and write `state/setup-rules.preview.json`. Prints the changes. |
| `approve` | Same as `preview`; with `--apply`, back up the old rules and save the new ones. |

| Option | Default | Allowed | Effect |
| --- | --- | --- | --- |
| `--rules PATH` | `rules.json` | | Rules file to read and update. |
| `--limit N` | `200` | 1-500 | Maximum messages sampled. |
| `--days N` | `30` | 1-90 | How far back to sample. |
| `--max-groups N` | `20` | 1-50 | Maximum sender groups reported. |
| `--selections PATH` | `state/setup-selections.json` | | Reviewed selections file. |
| `--apply` | off | `approve` only | Save the approved rules. |

## `tools/share.py`

Build a clean ZIP from an explicit file allowlist (`make share`). See
[Sharing a ZIP](../sharing.md).

```bash
python3 tools/share.py [--output PATH]
```

| Option | Default | Effect |
| --- | --- | --- |
| `--output PATH` | `dist/ai-mail-assistant.zip` | Destination; must be a non-symlink `.zip` path. |

## `scripts/setup-macos.sh`

Install, authenticate and verify on macOS (`make setup`; `make setup-preview` adds
`--dry-run`, `make doctor` adds `--check`). See
[Getting started](../getting-started.md#1-install-and-configure).

```bash
scripts/setup-macos.sh [options]
```

| Option | Effect |
| --- | --- |
| `-y`, `--yes` | Answer yes to every prompt (still opens browser logins). |
| `-n`, `--dry-run` | Print the commands that would run; change nothing. |
| `-c`, `--check` | Health check only; change nothing. Exits 1 if anything required is missing. |
| `--project ID` | Use an existing Google Cloud project for `gws auth setup`. |
| `--task-list NAME` | Google Tasks list written into a new `rules.json` (default `My Tasks`). |
| `--skip-auth` | Install tools and local files only; no logins. |
| `--cli NAME` | Classifier CLI to install, log in to and select in `classifier.json`: `copilot` or `claude`. Default: the `cli` already set. |
| `--no-model-cli` | Do not install or log in to any classifier CLI (model-free use only). `--skip-copilot` is the older name. |
| `--skip-verify` | Do not run the tests or the read-only dry run. |
| `-h`, `--help` | Show help. |

## `demo/run_demo.py`

Run the real engine on an invented mailbox with stand-in `gws` and `copilot`
programs. The demo always uses the Copilot path. See
[Try the demo](../getting-started/demo.md).

```bash
python3 demo/run_demo.py [--out PATH] [--workspace DIR] [--quiet]
```

| Option | Effect |
| --- | --- |
| `--out PATH` | Also write a JSON snapshot of every step. |
| `--workspace DIR` | Keep the workspace in this new or empty folder. |
| `--quiet` | Print nothing. |

## `tools/benchmark.py` (optional)

A read-only research benchmark comparing the local Laya runtime with the small
model of the selected classifier CLI, described in [ADR 0001](../adr/0001-laya-vs-luna.md) and
[Operations](../operations.md#local-model-evaluation-laya). It never applies
decisions. It needs the isolated dependencies pinned in
`tools/benchmark/requirements.lock`; the scheduled runner does not.

| Option | Default | Effect |
| --- | --- | --- |
| `--device {mps,cpu}` | `mps` | Local inference device. |
| `--prepare` | off | Download the pinned checkpoints only; read no mail, call no hosted model. |
| `--repeats N` | `2` | Repetitions, 1-3. |
| `--schema {baseline,compact}` | `baseline` | Question schema for the local model. |
| `--local-only` | off | Skip the hosted model. |
| `--output PATH` | `state/benchmark.json` | Evidence file. |
