# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Public site in the same shape as `mmornati/ai-finance-coach`: a hand-built static landing page (`website/`) published at the
root of GitHub Pages, and MkDocs Material documentation under `/docs/`, built strictly and deployed by a GitHub Actions
workflow. English site; the narrated film ships in English and French.

## Users

Busy professionals whose Gmail inbox is a second job: managers, consultants and engineers who receive a steady mix of
requests, meeting traffic, notifications and newsletters. They work on a Mac, are comfortable pasting a few commands into a
terminal, and use GitHub Copilot or Claude Code. The site visitor wants to know, quickly, whether this will calm their inbox without
handing it to an opaque, expensive AI agent.

## Product Purpose

AI Mail Assistant triages Gmail on a schedule: deterministic Gmail-query rules tag and tidy everything they can, and a
model is called only for the human mail that rules cannot interpret. Requests become Google Tasks with deadlines; ambiguous
mail stays in the inbox, untagged, for a human. Success is an inbox where every message carries an `AI/*` label or is
deliberately waiting for review, a task list of real commitments, and a model bill close to zero on quiet hours.

## Positioning

Rules first, model last. Searching, tagging rule-matched mail, sweeps, task sync, deduplication and the report are plain
code; a scheduled run with nothing unresolved launches no AI session at all. When a model is needed, a cheap model
classifies in batches, only ambiguous cases escalate to a stronger model with bounded body text, and every answer is
validated against the batch, tags, task policy and dates before anything touches the mailbox. Every mailbox-changing
command is a dry run unless `--apply` is given, and applied batches are journalled for `undo`.

## Operating Context

- macOS, launched by a launchd calendar job (weekdays, hourly 08:00 to 19:00) via `schedule.py`; no terminal or app needs
  to be open.
- Talks to Gmail and Google Tasks only through the Google Workspace CLI (`gws`), with the `gmail.modify` and `tasks`
  scopes. Classifies through the CLI the user already has: GitHub Copilot CLI (`copilot`, default) or Claude Code
  (`claude`), selected by `cli` in `classifier.json`, with no tools, in a temporary directory, mail on stdin.
- Configuration is two JSON files: `rules.json` (tags, ordered Gmail queries, actions, sweeps, task policies) and
  `classifier.json` (models, thresholds, batching, per-run caps).
- Output is local files in a private `state/` folder: `summary.json`, `pending.json`, `plan.json`, `usage.jsonl`, a
  journal and a dry-run CSV.
- Two Copilot skills: `mail-setup` (bounded, read-only sender discovery that proposes personal rules) and `mail-triage`
  (interactive review of what is pending).
- `make setup` (wrapping `scripts/setup-macos.sh`) installs and authenticates everything from zero; `make doctor` is a
  health check; `make preview` / `make classify` / `make apply` are the everyday commands (`apply` asks first);
  `tools/share.py` builds a clean ZIP for colleagues; `make demo` runs the engine on the invented demo mailbox.

## Capabilities and Constraints

- Twelve starter tags under the `AI/` label prefix: Action, Alerts, GitHub-Admin, Meeting/Invite, Meeting/Notes, Shares,
  Admin, Internal-Comms, Newsletter, Promo, FYI, Backlog.
- First matching rule wins; per-tag sweeps (archive, mark read, star, important; trash only opt-in); `sweep_guard` keeps
  starred mail untouched by default.
- Task policy per tag (`always`, `optional`, `never`); one task per thread; completing a task can archive its thread.
- Default classifier route on Copilot: `gpt-6-luna` first pass, `gpt-6.1-sol` for escalations; on Claude Code:
  `claude-haiku-5-5` then `claude-sonnet-5-5`. Confidence is model-reported and not calibrated.
- Exit codes: 0 finished, 2 mail needs review or exceeded per-run capacity.
- Not a push integration: it polls a time window (default `newer_than:7d`). macOS only for the schedule. Gmail only.
- Python 3.10+ with no third-party runtime dependencies.

## Brand Commitments

Product name: "AI Mail Assistant" (renamed from "AI E-Mail Assistant"). Voice is plain, precise and honest about limits (the README states what it does not
do as carefully as what it does). Independent project, MIT licence; not affiliated with Google or GitHub.

## Evidence on Hand

- The engine itself, its tests and its README; the guides in `docs/`; ADRs 0001 and 0002; `tools/benchmark.py`.
- Cost estimates published in README and `docs/costs.md` ($0 empty runs, about $0.15 and $2.46 a month in two
  illustrative scenarios at Copilot rates); quote them only with that label.
- The site demo runs the real `runner.py` against an invented mailbox through stand-in `gws` and `copilot` executables;
  every name, company, address and message on the site is synthetic and must be labelled as such.
- No users, testimonials, cost figures from real mailboxes, or accuracy claims exist. Do not invent them; numbers shown
  must come from the demo run and be labelled as demo output.

## Product Principles

1. Code before model: anything a rule can decide is never sent to a model.
2. Nothing changes without consent: dry run by default, validated plans, journalled undo.
3. Unknown stays visible: uncertain mail is left in the inbox for a person, never silently archived.
4. Private by construction: mail-bearing output stays in local `state/`; logs carry counts, not content.
5. Honest about limits: say what it does not do as clearly as what it does.
