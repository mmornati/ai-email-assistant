# Getting started

From a fresh Mac to a reviewed first run in about ten minutes. Every step is
safe to repeat, and nothing here changes your mailbox.

- [1. Install and configure](#1-install-and-configure)
- [2. Check the installation](#2-check-the-installation)
- [3. First run: preview](#3-first-run-preview)
- [4. Personalize your rules](#4-personalize-your-rules-mail-setup)
- [5. Classify, review, apply](#5-classify-review-apply)
- [6. Put it on a schedule](#6-put-it-on-a-schedule)
- [Manual installation](#manual-installation)

## 1. Install and configure

```bash
git clone https://github.com/mmornati/ai-email-assistant.git
cd ai-email-assistant
make setup-preview   # print every command first; changes nothing
make setup           # install, authenticate, verify
```

`make setup` runs [`scripts/setup-macos.sh`](../scripts/setup-macos.sh). It is
idempotent and safe to re-run. It:

1. installs Python 3.10+ (if needed), the
   [Google Workspace CLI](https://github.com/googleworkspace/cli) (`googleworkspace-cli`),
   the Google Cloud CLI (`gcloud-cli`) and the classifier CLI with Homebrew:
   the [GitHub Copilot CLI](https://docs.github.com/copilot/how-tos/copilot-cli)
   (`copilot-cli`) by default, or [Claude Code](https://claude.com/product/claude-code)
   (`claude-code`) with `--cli claude`;
2. creates a private `state/` folder and `rules.json` from the starter rules, asking
   which Google Tasks list should receive follow-up tasks (default: `My Tasks`);
3. logs in to `gcloud`, runs `gws auth setup` (OAuth client + Gmail/Tasks APIs)
   and `gws auth login` with **only** the `gmail.modify` and `tasks` scopes, then
   `copilot login` or `claude auth login`;
4. runs the offline tests and a read-only, model-free dry run.

It never modifies mail, never passes `--apply`, and never installs the schedule.

Options (pass them to the script directly):

| Option | Effect |
| --- | --- |
| `--dry-run` | Print the commands; change nothing (`make setup-preview`) |
| `--check` | Health check only (`make doctor`) |
| `--yes` | Answer yes to every prompt (browser logins still open) |
| `--cli copilot\|claude` | Classifier CLI to install, log in to and select in `classifier.json` ([details](classifier-cli.md)) |
| `--project ID` | Reuse an existing Google Cloud project for `gws auth setup` |
| `--task-list NAME` | Google Tasks list written into a **new** `rules.json` |
| `--skip-auth` | Install tools and local files only; no logins |
| `--no-model-cli` | Model-free setup: no classifier CLI (`runner.py --no-model` only); `--skip-copilot` still works |
| `--skip-verify` | Skip the tests and the read-only dry run |

```bash
bash scripts/setup-macos.sh --cli claude --task-list "Inbox follow-ups"
```

> [!WARNING]
> Homebrew's `gws` formula is an unrelated tool with the same binary name.
> Install `googleworkspace-cli`, not `gws`; the script checks for this.

## 2. Check the installation

```bash
make doctor
```

```text
==> AI Mail Assistant health check
  ✓ macOS
  ✓ Homebrew
  ✓ Python 3.10+ (/opt/homebrew/bin/python3.13)
  ✓ Google Workspace CLI (gws)
  ✓ Google Cloud CLI (first-time OAuth setup only)
  ✓ GitHub Copilot CLI (selected classifier CLI)
  ✓ rules.json
  ✓ state/ is private (0700)
  ✓ gws authorized for Gmail + Tasks
  ○ Hourly schedule installed (optional)  → make schedule-install, after reviewing a dry run
```

`✗` items are required and print how to fix them; `○` items are optional.
The command exits non-zero while anything required is missing, so it also works
in scripts.

## 3. First run: preview

```bash
make preview         # python3 runner.py --no-model
```

A **read-only, model-free** dry run: it reads mail metadata, applies your rules
and the classification cache, and writes the plan. Nothing is changed and no
model is called. Exit code `2` just means some mail still needs classification.

Review `state/summary.json`, `state/pending.json` and `state/plan.json`
(`make summary` prints the first).

## 4. Personalize your rules: `mail-setup`

The starter rules have no sender-specific queries, so at first every message
goes to the classifier. Teach the rules your recurring senders to cut model use.

Open the folder as a Local, folder-backed project in Copilot, or start `claude`
in it (Claude Code reads the same skill from `.claude/skills/`), and ask:

> Use the mail-setup skill to inspect my mailbox read-only, propose personalized
> rules, and ask before saving them. Do not modify mail or create tasks.

The skill runs `mail_setup.py discover` (`make discover`). The script reads at most
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
python3 mail_setup.py discover           # make discover
python3 mail_setup.py preview            # make rules-preview, after the skill writes setup-selections.json
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

## 5. Classify, review, apply

```bash
make classify        # python3 runner.py          dry run, paid classification if needed
make apply           # python3 runner.py --apply  asks for confirmation, then changes mail
```

Every mailbox-mutating command is a **dry run unless `--apply` is supplied**.
A model-enabled dry run can still incur model charges. It saves its validated
classifications for same-day reuse and writes the operation plan.

Review `state/summary.json`, `state/pending.json` and `state/plan.json`. After
approval, either replay exactly the reviewed plan
(`python3 triage.py apply-plan --apply`, see [Interactive review](interactive-review.md)), or run a
fresh scan with `make apply`.

## 6. Put it on a schedule

```bash
make schedule-render    # inspect the generated launchd job
make schedule-install   # hourly, Mon–Fri 08:00–19:00; future runs use --apply
make schedule-status
```

Details, timing and the model-free variant: [Scheduling](scheduling.md).

## Manual installation

Prefer to do it by hand? You need macOS, Python 3.10+, an authenticated
[`gws` CLI](https://github.com/googleworkspace/cli) with Gmail and Tasks access,
and (for classification) the authenticated classifier CLI selected in
`classifier.json` ([Choosing the classifier CLI](classifier-cli.md)).
There are no additional Python package dependencies.

```bash
brew install googleworkspace-cli
brew install --cask gcloud-cli copilot-cli   # or claude-code
mkdir -m 700 state && cp rules.example.json rules.json
gws auth setup                         # OAuth client + Gmail/Tasks APIs, if needed
gws auth login --scopes https://www.googleapis.com/auth/gmail.modify,https://www.googleapis.com/auth/tasks
gws auth status
copilot login                          # or: claude auth login (then runner.py --select-cli claude)
python3 -m unittest discover -q -s tests -t .
python3 runner.py --no-model
```

Do not use read-only access for applied runs; Gmail modification and Tasks
access are required. Follow the CLI prompts and your organization's OAuth policy.

The classifier CLI must support the flags listed in
[Choosing the classifier CLI](classifier-cli.md). Both configured models must be
accessible under your account and organization policy.

---

Next: [How it works](how-it-works.md) · [Configuration](configuration.md) ·
[Operations & troubleshooting](operations.md)
