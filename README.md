# AI E-Mail Assistant

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Low-cost Gmail triage using deterministic rules first and a model only when
human mail needs interpretation. No model is involved in searching, tagging
rule-matched mail, sweeping old notifications, synchronizing completed tasks,
deduplicating tasks, or generating the routine report.

**Recommended setup:** a local macOS schedule runs `runner.py`. It does not
launch an AI session when there is no unresolved mail. The classifier is a CLI
you choose in `classifier.json`: the GitHub Copilot CLI (default) or Claude Code.
The same tool also hosts the interactive review skills; neither is the hourly
scheduler.

## Quick start (macOS)

```bash
git clone https://github.com/mmornati/ai-email-assistant.git
cd ai-email-assistant
scripts/setup-macos.sh --dry-run   # show every command first
scripts/setup-macos.sh             # install, authenticate, verify
```

The setup script is idempotent and safe to re-run. It:

1. installs Python 3.10+ (if needed), the
   [Google Workspace CLI](https://github.com/googleworkspace/cli) (`googleworkspace-cli`),
   the Google Cloud CLI (`gcloud-cli`) and the classifier CLI with Homebrew:
   the [GitHub Copilot CLI](https://docs.github.com/copilot/how-tos/copilot-cli)
   (`copilot-cli`) by default, or [Claude Code](https://claude.com/product/claude-code)
   (`claude-code`) with `--cli claude`;
2. creates a private `state/` folder and `rules.json` from the starter rules;
3. logs in to `gcloud`, runs `gws auth setup` (OAuth client + Gmail/Tasks APIs)
   and `gws auth login` with **only** the `gmail.modify` and `tasks` scopes, then
   `copilot login` or `claude auth login`;
4. runs the offline tests and a read-only, model-free dry run.

It never modifies mail, never passes `--apply`, and never installs the schedule.
Use `--cli claude` to classify with Claude Code (it also sets `"cli"` in
`classifier.json`), `--no-model-cli` for a model-free setup (`--skip-copilot`
still works), `--project <id>` to reuse an existing Google Cloud project, and
`--help` for all options.

> **Note:** Homebrew's `gws` formula is an unrelated tool with the same binary
> name. Install `googleworkspace-cli`, not `gws`; the script checks for this.

## How it works

```text
macOS calendar schedule (no AI session)
  -> shared process lock
  -> sync completed Google Tasks
  -> Gmail-query rules: first matching tag wins
  -> per-tag sweeps
  -> pending, untagged inbox messages
       -> reuse validated same-day cached classifications
       -> nothing left: exit, zero model calls
       -> small-model batches
       -> ambiguous cases only: bounded body text + stronger model
       -> validate batch, IDs, tags, tasks and deadlines
       -> recheck current inbox/label state
       -> create tasks, then apply labels
  -> deterministic state/summary.json
```

Unknown or still-ambiguous mail stays **untagged and in the inbox** for review;
there is no automatic "FYI" or archive fallback. Already completed rule/sweep
operations are not rolled back if classification subsequently fails.

### Files

| File | Purpose |
| --- | --- |
| `triage.py` | Existing deterministic mailbox/Tasks engine and interactive commands |
| `rules.json` | Tags, ordered Gmail queries, actions, task policies and default dates |
| `runner.py` | Scan, cache, gated classification, validation and reporting |
| `classifier.json` | Classifier CLI (Copilot or Claude Code), models, thresholds, batching and per-run limits |
| `schedule.py` | Render/install/status/uninstall the macOS calendar job |
| `tests/` | Isolated tests; no mailbox access or paid model calls |
| `scripts/setup-macos.sh` | Install, authenticate and verify from zero on macOS |
| `.github/skills/mail-triage/SKILL.md` | Interactive review procedure (Copilot) |
| `.claude/skills/*/SKILL.md` | Identical skill copies for Claude Code; a test keeps them in sync |
| `rules.example.json` | Generic starter rules; no sender-specific queries or automatic cleanup |
| `share.py` | Build a clean ZIP from an explicit file allowlist |
| `mail_setup.py` | Bounded read-only sender discovery and approved local-rule updates |
| `.github/skills/mail-setup/SKILL.md` | First-run personalized ruleset review |
| `state/` | Private local runtime data; excluded from version control |
| `rules.json` | Your personal rules, created from `rules.example.json`; excluded from version control |

## Sharing and installing the ZIP

```bash
python3 share.py
```

Share **only `dist/ai-mail-assistant.zip`**, not this working folder. The packager
includes source, tests, documentation, the interactive skill, classifier settings
and optional benchmark scripts. It excludes mailbox state, decisions, usage/logs,
credentials, installed environments, models, machine-generated schedules and
unlisted files. Re-running the same command rebuilds and **atomically replaces**
the previous ZIP only after the new archive passes its integrity check. A failed
build preserves the previous archive. Use `--output /path/to/new-bundle.zip`
for a different destination. This one-shot command is suitable for an existing
scheduler or other automation; no watcher or new schedule is installed:

```bash
python3 /absolute/path/to/ai-mail-assistant/share.py
```

The ZIP's `rules.json` comes from **`rules.example.json`, never the active local
rules**. The starter preserves the tag taxonomy and task policies, but has no
sender-specific matching, sweeps, archive/read/trash actions, or task-completion
actions. With it, model-free runs leave mail pending; model-enabled applied runs
can label mail and create tasks. Add your own Gmail queries to `match` in tag
priority order to reduce model use. Review every cleanup action before enabling it.
The original `rules.json` and existing schedule in the sender's folder are unchanged.

Recipients should:

1. Unzip into a permanent local folder on macOS. No repository is required.
2. Run `bash scripts/setup-macos.sh`, or install the prerequisite CLIs below
   manually, and authenticate **their own accounts**.
   Use `gws auth setup` if OAuth configuration is needed, then
   `gws auth login --services gmail,tasks`, `gws auth status`, and `copilot login`
   or `claude auth login` for the classifier CLI selected in `classifier.json`.
   Do not use read-only access for applied runs; Gmail modification and Tasks
   access are required. Follow the CLI prompts and organizational OAuth policy.
3. Review `rules.json`, the task-list name, the classifier CLI and allowed models
   in `classifier.json`, and any locally configured MCP server names to disable.
4. Run the offline tests and the `mail-setup` onboarding skill below to personalize
   sender rules. Inspect a model-free dry run before deliberately enabling paid
   classification or mailbox changes.
5. Install their own schedule only after review. No schedule or credentials are
   installed by extraction. Keep the folder at its installed path.

Optional benchmark scripts do not require model downloads to run the offline
tests. The historical ADR records the original personalized-rules experiment;
benchmarking the starter rules is a different configuration.

## Prerequisites and first run

`scripts/setup-macos.sh` handles everything in this section. Manually, use
Python 3.10+ on macOS, an authenticated
[`gws` CLI](https://github.com/googleworkspace/cli) with Gmail and Tasks access,
and the authenticated classifier CLI selected in `classifier.json` (see
[Choosing the classifier CLI](#choosing-the-classifier-cli)).
There are no additional Python package dependencies.

The installed Copilot CLI must support `--available-tools=`,
`--no-custom-instructions`, `--no-remote-export`, `--output-format json`, and
`--usage-output-file`.
Check `copilot --help` and `copilot help permissions`. Claude Code was verified
with version 2.1.284; it must support `-p`, `--output-format json`, `--tools`,
`--strict-mcp-config`, `--setting-sources`, `--no-session-persistence` and
`--max-budget-usd` (check `claude --help`). Both configured models must be
accessible under your account and organization policy.

```bash
cd /path/to/ai-mail-assistant
python3 -m unittest discover -q -s tests -t .
python3 runner.py --no-model          # dry-run rules/cache only; never calls a model
python3 runner.py                     # dry run with paid classification if necessary
```

Every mailbox-mutating command is a **dry run unless `--apply` is supplied**.
A model-enabled dry run can still incur model charges. It saves its validated
classifications for same-day reuse and writes the operation plan.

Review `state/summary.json`, `state/pending.json` and `state/plan.json`. After
approval, either apply the reviewed plan (see below), or run:

```bash
python3 runner.py --apply             # fresh scan, validated classification and application
```

Do not run both scheduling systems below at the same time.

## First-run personalized rules: `mail-setup`

Open the extracted folder as a Local folder-backed project in Copilot, or start
`claude` in it (Claude Code reads the same skill from `.claude/skills/`), and ask:

> Use the mail-setup skill to inspect my mailbox read-only, propose personalized
> rules, and ask before saving them. Do not modify mail or create tasks.

The included skill runs `mail_setup.py discover`. The script reads at most
**200 received messages from the last 30 days**, including archived mail,
groups exact sender addresses deterministically and writes bounded samples to
`state/setup-discovery.json`. It fetches only selected metadata headers and short
snippets, not bodies/attachments; makes no model calls; and never modifies mail
or tasks. The reviewing Copilot or Claude Code session consumes its normal tokens. No model
training or local-model installation is needed.

For each recurring group, up to three development and two separate validation
examples are included. Only groups with bulk/list indicators on **all sampled
messages** and enough examples qualify for automated-sender rules. The skill
reviews the two sets separately and rejects mixed-purpose or action-request
senders. This is a bounded recent sample, not a random sample, independently
human-labeled accuracy test or guarantee about future mail.

```bash
python3 mail_setup.py discover
python3 mail_setup.py preview            # after the skill writes setup-selections.json
python3 mail_setup.py approve --apply    # only after approving the displayed rules
```

Preview creates `state/setup-rules.preview.json` without modifying `rules.json`.
Approval validates batch/rules freshness (24 hours), all reviewed example IDs and
category agreement, backs up the old configuration privately, then atomically
appends approved exact-sender queries. It cannot add cleanup actions, domain-wide
queries, or Action/FYI/Backlog sender rules. Existing policies are preserved:
on starter rules no cleanup is enabled; on personalized rules a new match can
inherit **existing** cleanup/task policies, so review those before approval.
Exact-query conflicts are rejected; broader overlapping existing queries still
need human review because first-match precedence applies.

Non-bulk human senders, disagreements and groups with insufficient history remain
for per-message classification. If nothing qualifies, keeping the starter rules
is a valid result. Discover again as mail accumulates; never manufacture agreeing
examples. After changes, refresh pending batches before processing them.

Advanced explicit bounds: `discover --limit 500 --days 90 --max-groups 50`.
These are hard caps, not a request to read the entire mailbox. All discovery,
selection, preview and backup data is private `state/` and excluded from ZIPs.
The skill does not enable classification, mailbox application or scheduling.

## Recommended schedule: outside the AI app

### Installation

```bash
python3 schedule.py render            # inspect the generated job; does not install
python3 schedule.py install           # persistent schedule; future runs use --apply
python3 schedule.py status            # inspect the registered job and last exit code
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

### Timing and machine lifecycle

The job runs **Monday-Friday, hourly at minute 00, from 08:00 through 19:00
inclusive**, in the Mac's local timezone: 12 opportunities/day, 60/week,
approximately 264 in a 22-workday month. The equivalent cron expression is
`0 8-19 * * 1-5`; the installed job uses calendar entries, not cron.

It runs as the logged-in user, without a terminal or the Copilot/Claude app being open.
The Mac must be powered on and that user logged in. Calendar events missed during
sleep may be coalesced into one wake-up run, not replayed hour by hour. Missed runs
while shut down/logged out are not a guaranteed backlog queue. `--scheduled`
skips wake-up catch-ups outside weekday 08:00-19:59.

Every actual scan still synchronizes completed tasks and sweeps existing labels,
even if there is no new mail. The default classification window is
`newer_than:7d`, and the default per-query limit is 500. This is a polling design,
**not a Gmail history cursor or push subscription**. Already classified mail is
excluded by its `AI/*` labels. For larger backlogs, use an explicit window/limit.

`state/run.lock` prevents overlapping runner/triage commands. A competing process
exits explicitly rather than modifying shared state. The file can remain after
exit; the OS releases the actual lock automatically, including after a crash.

### Disable any app automation

If you previously ran triage as a Copilot app Automation, disable it when using
the external schedule. Keeping it enabled reintroduces AI startup cost on every
tick.

The external job does **not** create an app Automation run card or automatically
open an app chat. Its status is in local files:

```bash
python3 schedule.py status
cat state/summary.json
tail -n 20 state/schedule.log
tail -n 20 state/schedule-error.log
python3 runner.py --usage-report
```

Exit codes: `0` = finished, `2` = mail still needs review or exceeded per-run
capacity, other nonzero = failure (including a competing lock holder).
`summary.json` has counts, newly created task titles/due dates/Gmail links,
unresolved IDs, recurring bulk-sender rule candidates and an explicit status/error type;
it is replaced each run. The schedule retries on its next calendar tick, not
in a tight restart loop.
Counts in a dry-run summary are planned, not applied. Rule candidates are generated
when a bulk sender occurs at least three times in a pending batch; the runner
never edits `rules.json`. Review and approve a sender query and tag before adding it.

To pause/remove the external schedule without changing mail:

```bash
python3 schedule.py uninstall
```

For immediate manual processing, run `runner.py` directly; it need not wait for
the next calendar event.

## Configuring the Copilot app (or Claude Code)

Keep this folder configured as a **Local, folder-backed project**. It has no Git
checkout requirement. Model selection in the app controls interactive assistance;
it does **not** override `classifier.json` for the external runner.

Claude Code needs no project setup: run `claude` in this folder and the same
skills load from `.claude/skills/`. The prompts below work unchanged. The
app-only automation alternative is described for Copilot.

### Interactive review (recommended app use)

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
python3 triage.py apply-plan          # previews the combined dry-run operation plan
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

### App-only automation alternative

If an external schedule is unsuitable, uninstall it first, then create/edit a
Local project Automation with:

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

## Choosing the classifier CLI

`classifier.json` selects the CLI that classifies pending mail with `"cli"`, and
keeps each CLI's binary and models under `"providers"`. The reasoning and the
measurements behind the Claude Code defaults are in
[ADR 0002](docs/adr/0002-selectable-classifier-cli.md).

```json
{
  "cli": "claude",
  "providers": {
    "copilot": {"binary": "copilot", "cheap_model": "gpt-6-luna", "escalation_model": "gpt-6.1-sol",
                "disabled_mcp_servers": []},
    "claude": {"binary": "claude", "cheap_model": "claude-haiku-5-5",
               "escalation_model": "claude-sonnet-5-5", "auth": "subscription",
               "max_budget_usd_per_call": 1.0}
  }
}
```

Switch with an editor or with:

```bash
python3 runner.py --select-cli claude   # validates the file, rewrites only "cli"
python3 runner.py --cli claude          # one paid dry run with Claude Code; file unchanged
```

Every `providers` block is validated on each run, so a mistake in the inactive
one is reported before you switch to it. Switching invalidates same-day cached
classifications (a different classifier produced them).

### Claude Code

Each classification is one `claude -p --output-format json` call with:

- no tools (`--tools ""`), no MCP servers (`--strict-mcp-config` with an empty
  config), no skills (`--disable-slash-commands`) and no saved session
  (`--no-session-persistence`);
- `--setting-sources project` in an empty temporary directory, so your user
  settings, hooks, plugins and permissions are not loaded;
- the classifier instructions and tag definitions as the system prompt
  (replacing Claude Code's coding-agent prompt) and the mail on stdin only;
- a per-call cap, `--max-budget-usd` = `max_budget_usd_per_call`.

The answer must be a single successful, tool-free turn; anything else is recorded
as an error and no decision is applied.

| Setting | Default | Meaning |
| --- | --- | --- |
| `providers.claude.cheap_model` | `claude-haiku-5-5` | First-pass classification |
| `providers.claude.escalation_model` | `claude-sonnet-5-5` | Ambiguous cases only |
| `providers.claude.auth` | `subscription` | `subscription` or `api_key` (see below) |
| `providers.claude.max_budget_usd_per_call` | `1.0` | Runaway guard, in the CLI's own cost estimate |

Keep pinned model IDs. On Claude Code 2.1.284 the `haiku` alias resolved to the
older Claude Haiku 4.5, so an alias can silently change both classifications and
cost.

**Auth.** `subscription` (default) uses your `claude auth login` and removes
`ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` from the call's environment so billing
stays on that login. With these flags, a synthetic probe showed that your global
`~/.claude/CLAUDE.md` and project instructions are **not** sent; Claude Code still
adds a short account section containing your sign-in email. `api_key` adds
`--bare`, which also skips that and every other automatic context, but accepts only
`ANTHROPIC_API_KEY`; the scheduled job cannot use it.

**Refused environments.** Like Copilot's custom-provider variables, the runner
refuses to call Claude Code when `ANTHROPIC_BASE_URL`, `ANTHROPIC_BEDROCK_BASE_URL`,
`ANTHROPIC_VERTEX_BASE_URL`, `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX` or
`CLAUDE_CODE_USE_FOUNDRY` is set. A terminal inside a Claude Code session sets
`ANTHROPIC_BASE_URL` for that session's own proxy, so run `runner.py` from a normal
terminal or the schedule, not from inside Claude Code.

## Model routing and configuration

Default `classifier.json` settings:

| Setting | Default | Meaning |
| --- | --- | --- |
| `cli` | `copilot` | Which `providers` entry classifies mail |
| `providers.copilot.cheap_model` | `gpt-6-luna` | First-pass classification |
| `providers.copilot.escalation_model` | `gpt-6.1-sol` | Ambiguous cases only |
| `confidence_threshold` | `0.85` | First-pass acceptance threshold |
| `escalation_threshold` | `0.9` | Escalation acceptance threshold |
| `batch_size` | `25` | Messages per model invocation |
| `max_batches` | `4` | At most 100 fresh first-pass messages/run |
| `max_escalations` | `10` | Strong-model messages/run, not calls |
| `context_chars` | `4000` | Max current-message plain-text body chars on escalation |
| `timeout_seconds` | `180` | Timeout per CLI invocation |
| `version` | `1` | Bump after intentional classifier-policy changes |
| `providers.copilot.binary` | `copilot` | CLI executable name or absolute path |
| `providers.copilot.disabled_mcp_servers` | configured names | Also suppress these user MCP servers |

The Claude Code block is described in [Choosing the classifier CLI](#choosing-the-classifier-cli).

The older flat format (`copilot_binary`, `cheap_model`, ... at the top level) is
still accepted and read as `"cli": "copilot"`. Switching CLI or model invalidates
same-day cached classifications.

Confidence is **model-reported, not calibrated probability**. Before relying on
unattended decisions for important mail, review representative output. Both low
confidence and `needs_context=true` trigger escalation. No powerful parent or
subagent-per-message is involved.

The stronger model receives only the ambiguous message's bounded plain-text body;
attachments and other thread messages are not fetched. HTML-only messages or
references requiring missing thread history may remain unresolved. Classification
cannot safely infer missing requests/deadlines.

Copilot calls have no available tools, run in a temporary working directory, suppress
project custom instructions and remote session export, and receive mail through
stdin, not command-line arguments. Built-in MCP servers and the configured server
names are disabled. Claude Code calls get the equivalent isolation listed above. Account-level CLI system context/plugins may still add
overhead; this is **not** a bare model API call. Custom provider environment
overrides are refused to prevent silently routing mail to another provider.

Cache keys include message metadata, rules, classifier settings and today's local
date. New replies have new message IDs and are evaluated independently. Successful
classification is saved before application, so retries need not pay for it again.
Still-ambiguous cases are held for review without repeat paid attempts that day.
Changing input/config/date invalidates their cache; to deliberately retry:

```bash
python3 runner.py --retry-review       # paid retry, dry run
python3 runner.py --retry-review --apply
```

Capacity-limited mail stays pending and is eligible on the next run. The limits
bound workload, **not an exact currency budget**. The Copilot CLI has a separate soft
AI-credit cap with a documented minimum of 30 credits; it is not used here as a
micro-call budget. Claude Code's `max_budget_usd_per_call` is a per-call guard
against runaway output, measured in the CLI's estimate (see below), not a budget.

## Costs and token estimates

**Zero model calls = zero model tokens/charges** for that scan. Mail API calls
still take time and consume their normal service quota.

Rates below are USD per million tokens, default context tier, verified against
[GitHub's pricing documentation](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing)
on **2026-10-07**. Prices, availability and your organization's billing can change.
One AI credit is $0.01 at the documented reference rate. This is usage value,
not necessarily extra cash charged beyond your plan's included allowance.

| Model | Input | Cache read | Cache write | Output |
| --- | ---: | ---: | ---: | ---: |
| GPT-6 Luna | $0.10 | $0.01 | $0.125 | $0.50 |
| GPT-6.1 Sol | $2.00 | $0.10 | $2.50 | $10.00 |

The input/output/cache-write rates differ by 20x between these models; cache-read
rates differ by 10x. Routing does not imply a 20x saving for the whole pipeline.

### Measured CLI startup overhead

A tool-free **synthetic probe**, not an inbox run, used 3 input tokens, 16,784
cache-write tokens and 9 output tokens with the small model. Applying the rates
above gives approximately **$0.00210** for that call:

```text
(3 * 0.10 + 16,784 * 0.125 + 9 * 0.50) / 1,000,000
```

This demonstrates why batching and skipping empty runs matter: even a tiny prompt
can carry substantial CLI system context. Actual classifier prompts are larger.

### Claude Code rates and measured overhead

Anthropic API rates, USD per million tokens, taken from Anthropic's model price
list as of **2026-10-06** ([pricing](https://platform.claude.com/docs/en/about-claude/pricing)).
Claude Haiku 5.5 rates apply to prompts of 100K tokens or fewer. Cache writes cost
1.25x input for a 5-minute TTL and 2x for a 1-hour TTL; Claude Code wrote 1-hour
entries in every probe below.

| Model | Input | Cache read | Cache write 5m | Cache write 1h | Output |
| --- | ---: | ---: | ---: | ---: | ---: |
| Claude Haiku 5.5 | $0.10 | $0.01 | $0.125 | $0.20 | $0.50 |
| Claude Sonnet 5.5 | $2.00 | $0.20 | $2.50 | $4.00 | $10.00 |

With a **subscription** login these are reference values: usage counts toward the
plan's limits rather than being billed per token. With `api_key` auth they are
the billed rates.

Because the system prompt replaces Claude Code's default one and no tools are
offered, overhead is small. Synthetic probes on Claude Code 2.1.284 (not inbox
runs, not an accuracy benchmark):

- a tiny JSON echo used 2 input, 720-815 cache-write and 9 output tokens,
  about **$0.00015** at Haiku rates (vs ~17,000 cache-write tokens for Copilot);
- a two-message classification used 2 input, 1,635 cache-write and 696 output
  tokens, about **$0.00068** at Haiku rates. Output exceeds the visible JSON,
  most likely because Haiku 5.5 thinks by default; lowering effort is untested.

**Do not use the CLI's reported cost for these models.** Claude Code 2.1.284 does
not recognize `claude-haiku-5-5` or `claude-sonnet-5-5` and prices them at
Claude Opus 5.5 rates: the two-message probe above reported $0.027, about 40x
the Haiku figure. The runner stores that number as `cli_cost_usd` only for
reference; compute cost from tokens. `--max-budget-usd` uses the same estimate,
which is why the default cap is $1.00 rather than a few cents.

An additional synthetic one-message classification validated both configured
models. The small-model call used 3 input, 17,379 cache-write and 64 output tokens
(approximately $0.00220). The stronger-model call used 3 input, 17,387 cache-write
and 27 output tokens (approximately $0.04374). These were separate validation
calls, not production triage or an accuracy benchmark.

### Illustrative monthly budgets, not observed inbox costs

For a simple conservative planning scenario, assume each fresh small-model call
has 20,000 cache-write tokens and 2,000 output tokens: **$0.0035/call**.
Assume each escalation call has the same counts: **$0.07/call**.
These are illustrative token mixes, not guarantees or billing caps; actual input,
cache-read/write accounting and reasoning/output length differ.

| Scenario over 22 workdays | Estimated usage value |
| --- | ---: |
| Rules/cache resolve everything | $0 |
| 2 small calls/day; no escalation | $0.154/month |
| 12 small calls/day; no escalation | $0.924/month |
| 12 small calls/day + 1 escalation call/day | $2.464/month |
| 4 small calls + 1 escalation call on every one of 264 ticks | $22.176/month |

The last row illustrates why escalation rate matters; it is **not a maximum
bill**. Large messages, batches, provider retries, altered settings or output
length can cost more. Running the same workflow as an app automation would instead start a full
agent session on every one of those ticks, even when the inbox is empty.

### Measure your real usage

```bash
python3 runner.py --usage-report
```

`state/usage.jsonl` records each call's CLI, model, message count, status, duration,
prompt/response character counts and sanitized CLI token totals. The report groups
by `cli/model` (entries written before CLI selection count as `copilot`). Claude
Code entries add `cache_write_1h`, the 1-hour-TTL part of `cache_write`, and the
CLI's own `cli_cost_usd` estimate (see the warning above). Characters are
**not** tokens. A timeout or missing usage export is marked as missing usage;
it does not prove that the failed call was free. Model response validation can
fail after a successfully billed call.

For each model, use the reported token categories:

```text
USD = (input * input_rate + cache_read * cache_read_rate
       + cache_write * cache_write_rate + output * output_rate) / 1,000,000
AI credits at reference rate = USD * 100
```

For Claude Code, price `cache_write_1h` at the 1-hour rate and only
`cache_write - cache_write_1h` at the 5-minute rate. `benchmark.py` applies this
with the rates above.

Use the CLI's billing token categories, not an additional sum of the inclusive
model input totals, to avoid double-counting cached tokens. Reconcile with the
account's Copilot usage view (legacy plans may expose premium-request accounting
instead) or your Claude plan's usage page / Anthropic Console. CLI logs and synthetic probes are not the account invoice.

## Tasks, actions and safety

`rules.json` keeps the original first-match behavior. A tag's `task` is `always`,
`optional` or `never`; optional tasks require an explicit commitment. Default
due dates are computed in code as +2 business days, not guessed by the model.
Each task stores a `[mail-triage thread=... tag=...]` marker and a Gmail link.
Existing tasks are deduplicated by thread and open title.

Completing a task causes the next scan's sync to apply the tag's `on_task_done`
actions to that thread's inbox messages. Available deterministic actions are
`archive`, `mark_read`, `star`, `important`, and explicitly configured `trash`.
The classifier cannot add action overrides or invent a tag.

Nothing is sent, forwarded, unsubscribed, or permanently deleted. Email is
untrusted content, never authority to execute instructions. Tasks are created
before classification labels so a failed task write leaves mail eligible for
retry. Gmail/Tasks mutations are not an atomic transaction; inspect errors after
partial failures.

New JSON state/usage files have owner-only permissions. State contains sensitive
mail metadata and task details and is **not encrypted by this application**;
use a protected account/disk, do not share it, and review any pre-existing file
permissions. The selected CLI's provider retention policy still applies to data
sent to Copilot (GitHub and the model provider) or Claude Code (Anthropic; terms
differ between a Claude subscription and API-key use).
Routine schedule logs omit subjects/bodies/tasks; interactive engine reports can
contain them. Usage logs accumulate; rotate/archive them privately as needed.

## Existing commands, backlog and recovery

```bash
python3 triage.py run                       # deterministic dry run, last 7 days
python3 triage.py run --apply               # deterministic changes, no classification call
python3 triage.py pending                   # new pending batch
python3 triage.py decide                    # validate and preview current manual decisions
python3 triage.py sync --apply              # sync completed tasks only
python3 triage.py undo -n 3 --apply          # revert last 3 journal batches
python3 runner.py --window '' --limit 8000  # preview whole-inbox processing (paid if pending)
```

Dry-run `triage.py` writes a per-message `state/dry-run.csv`; `decide` merges
into it. `--report <file>` also writes a CSV when applying. Metadata headers are
cached locally; unread flags in historical reports may be stale. The runner
instead produces a compact deterministic summary and the same dry-run plan.

`state/journal.jsonl` supports undo for label changes/trash; undo does **not**
delete created tasks. An applied operation plan is renamed
`state/plan.applied-<timestamp>.json`.

For authentication failures, stop unattended work, use `gws auth status` and
`gws auth login --services gmail,tasks`, or `copilot login` / `claude auth login`
for the classifier CLI, then rerun a preview. If Claude Code is refused because of
`ANTHROPIC_BASE_URL`, you are probably running inside a Claude Code session; use a
normal terminal. For model-access/CLI errors, verify the installed flags and
permitted model names. For stale batches, regenerate pending and decisions.
Do not bypass validation, replay legacy files, or use blanket tool permissions.

## Local Laya evaluation

[ADR 0001: Laya versus Luna](docs/adr/0001-laya-vs-luna.md) records the measured
local experiment, all category outcomes, latency, confidence limitations,
costs and reproduction commands. **Production remains on Luna.**

Laya's local typed-decision runtime was tested, not a chat model in LM Studio.
It was faster and had no hosted inference fee, but the zero-shot baseline got
9/16 synthetic categories right versus Luna's 16/16. A concise exploratory schema
improved Laya to 11/16, still missing Action categories and showing high-confidence
errors. Real-mail agreement was measured separately; without human reference
labels it is not an accuracy result.

The optional benchmark dependencies are isolated in `.venv-benchmark` and pinned
in `requirements-benchmark.lock`. They are not required by the scheduled runner.
`benchmark.py` never applies decisions. It persists classification-only evidence
under `state/`; no raw mail or task text is exported.

The experiment also fixed long-response CLI JSON corruption: classification now
reads the final assistant message from structured JSONL events rather than
terminal-wrapped text. Upgrade checks must include `--output-format json`.

## Contributing, security and license

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Please report
vulnerabilities privately as described in [SECURITY.md](SECURITY.md); never share
real mail or files from `state/` in issues.

Released under the [MIT License](LICENSE). This project is not affiliated with
Google or GitHub. You are responsible for complying with your organization's
policies on mailbox automation and AI processing of email.
