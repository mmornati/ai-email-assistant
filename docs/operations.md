# Operations and troubleshooting

## Command reference

| `make` target | Underlying command | Changes mail? |
| --- | --- | :---: |
| `make preview` | `python3 runner.py --no-model` | No |
| `make classify` | `python3 runner.py` | No (paid if mail is pending) |
| `make apply` | `python3 runner.py --apply` | **Yes**, after a confirmation prompt |
| `make review` | `python3 triage.py apply-plan` | No |
| `make retry-review` | `python3 runner.py --retry-review` | No (paid) |
| `make summary` | `cat state/summary.json` | No |
| `make usage` | `python3 runner.py --usage-report` | No |
| `make discover` | `python3 mail_setup.py discover` | No |
| `make rules-preview` | `python3 mail_setup.py preview` | No |
| `make doctor` | `scripts/setup-macos.sh --check` | No |

The engine also exposes lower-level commands:

```bash
python3 triage.py run                       # deterministic dry run, last 7 days
python3 triage.py run --apply               # deterministic changes, no classification call
python3 triage.py pending                   # new pending batch
python3 triage.py decide                    # validate and preview current manual decisions
python3 triage.py sync --apply              # sync completed tasks only
python3 triage.py undo -n 3 --apply         # revert last 3 journal batches
python3 runner.py --window '' --limit 8000  # preview whole-inbox processing (paid if pending)
```

## Reports, journal and undo

Dry-run `triage.py` writes a per-message `state/dry-run.csv`; `decide` merges
into it. `--report <file>` also writes a CSV when applying. Metadata headers are
cached locally; unread flags in historical reports may be stale. The runner
instead produces a compact deterministic summary and the same dry-run plan.

`state/journal.jsonl` supports undo for label changes/trash; undo does **not**
delete created tasks. An applied operation plan is renamed
`state/plan.applied-<timestamp>.json`.

## Retrying held mail

Still-ambiguous cases are held for review without repeat paid attempts that day.
To deliberately retry:

```bash
python3 runner.py --retry-review       # paid retry, dry run (make retry-review)
python3 runner.py --retry-review --apply
```

## Troubleshooting

Start with `make doctor`; it names each missing piece and how to fix it.

| Symptom | Fix |
| --- | --- |
| `gws` authorization missing or expired | Stop unattended work, then `gws auth status` and `gws auth login --services gmail,tasks` (or re-run `make setup`), then preview again |
| Copilot errors / not logged in | `copilot login` |
| Model access or CLI flag errors | Verify the installed CLI flags (see [manual installation](getting-started.md#manual-installation)) and permitted model names in `classifier.json` |
| Stale batch / decisions rejected | Regenerate pending and decisions; batches expire after 24 hours |
| `gws` is a different tool | `brew uninstall gws`, then `brew install googleworkspace-cli` |
| macOS Python is 3.9 | `make setup` installs `python@3.13`; or run `make PYTHON=/path/to/python3 …` |
| Exit code `2` | Not an error: mail awaits classification or review |

Do not bypass validation, replay legacy files, or use blanket tool permissions.

## Local model evaluation (Laya)

[ADR 0001: Laya versus Luna](adr/0001-laya-vs-luna.md) records the measured
local experiment, all category outcomes, latency, confidence limitations,
costs and reproduction commands. **Production remains on Luna.**

Laya's local typed-decision runtime was tested, not a chat model in LM Studio.
It was faster and had no hosted inference fee, but the zero-shot baseline got
9/16 synthetic categories right versus Luna's 16/16. A concise exploratory schema
improved Laya to 11/16, still missing Action categories and showing high-confidence
errors. Real-mail agreement was measured separately; without human reference
labels it is not an accuracy result.

The optional benchmark dependencies are isolated in `.venv-benchmark` and pinned
in [`tools/benchmark/requirements.lock`](../tools/benchmark/requirements.lock).
They are not required by the scheduled runner. `tools/benchmark.py` never applies
decisions. It persists classification-only evidence under `state/`; no raw mail
or task text is exported. Running the offline tests needs no model downloads.
The historical ADR records the original personalized-rules experiment;
benchmarking the starter rules is a different configuration.
