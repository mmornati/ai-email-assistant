# Sharing a ZIP

Give a colleague a clean copy without your mail data or personal rules.

```bash
make share                     # python3 tools/share.py
```

Share **only `dist/ai-mail-assistant.zip`**, not this working folder. The packager
includes source, tests, documentation, the interactive skills, classifier settings
and optional benchmark scripts from an explicit allowlist. It excludes mailbox
state, decisions, usage/logs, credentials, installed environments, models,
machine-generated schedules and unlisted files.

Re-running the same command rebuilds and **atomically replaces** the previous ZIP
only after the new archive passes its integrity check. A failed build preserves
the previous archive. Use `--output /path/to/new-bundle.zip` for a different
destination. This one-shot command is suitable for an existing scheduler or other
automation; no watcher or new schedule is installed:

```bash
python3 /absolute/path/to/ai-mail-assistant/tools/share.py
```

The ZIP's `rules.json` comes from **`rules.example.json`, never the active local
rules**. The starter preserves the tag taxonomy and task policies, but has no
sender-specific matching, sweeps, archive/read/trash actions, or task-completion
actions. The original `rules.json` and existing schedule in the sender's folder
are unchanged.

## For recipients

1. Unzip into a permanent local folder on macOS. No repository is required.
2. Run `make setup` (or `bash scripts/setup-macos.sh`) and authenticate
   **your own accounts** (`--cli claude` to classify with Claude Code); see
   [Getting started](getting-started.md) for the manual alternative. Do not use read-only access for applied runs; Gmail
   modification and Tasks access are required. Follow the CLI prompts and your
   organizational OAuth policy.
3. Review `rules.json`, the task-list name, the classifier CLI and allowed models
   in `classifier.json`, and any locally configured MCP server names to disable.
4. Run the offline tests (`make test`) and the
   [`mail-setup` onboarding skill](getting-started.md#4-personalize-your-rules-mail-setup)
   to personalize sender rules. Inspect a model-free dry run (`make preview`)
   before deliberately enabling paid classification or mailbox changes.
5. Install your own schedule only after review. No schedule or credentials are
   installed by extraction. Keep the folder at its installed path.
