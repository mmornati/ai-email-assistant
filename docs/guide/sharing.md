# Sharing with a colleague

`share.py` builds a clean ZIP you can hand to someone else. Share **only the ZIP**,
never your working folder: the folder contains your private `state/` and your
personal `rules.json`.

## Build the ZIP

```bash
python3 share.py
```

It writes `dist/ai-mail-assistant.zip`. To write somewhere else:

```bash
python3 share.py --output /path/to/new-bundle.zip
```

The output must be a `.zip` path that is not a symbolic link.

The build is safe to repeat. The new archive is written to a temporary file,
checked for integrity, and only then **atomically replaces** the previous ZIP. A
failed build leaves the previous archive in place. It is a one-shot command, so it
can run from an existing scheduler or other automation by absolute path; it
installs no watcher or schedule of its own.

## What is inside

The ZIP contains a single `ai-mail-assistant/` folder built from an explicit
allowlist in `share.py`:

- documentation: `README.md`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and
  `docs/adr/0001-laya-vs-luna.md`;
- the engine: `triage.py`, `runner.py`, `schedule.py`, `mail_setup.py`, `share.py`;
- configuration: `classifier.json`, `rules.example.json`, `.gitignore`;
- `scripts/setup-macos.sh`;
- the two Copilot skills, `mail-setup` and `mail-triage`;
- the offline test suite;
- the optional benchmark: `benchmark.py`, `benchmark-fixtures.json` and its pinned
  requirements files.

Any file not on the list is left out. A listed file that is missing or is a
symbolic link stops the build.

### `rules.json` in the ZIP is the starter

The ZIP's `rules.json` is a copy of `rules.example.json`, **never your active
rules**. The build refuses to run if the starter rules contain any `match`,
`on_tag`, `sweep` or `on_task_done` entries. So the recipient gets the tag
taxonomy and task policies, but no sender-specific queries and no
archive/read/trash or completion actions.

With those rules, model-free runs leave all mail pending, and model-enabled applied
runs can label mail and create tasks. The recipient adds their own queries, for
example with the [`mail-setup`](../getting-started/personal-rules.md) skill.

## What is never inside

Mailbox state, decisions, plans, journals, usage logs and schedule logs (all of
`state/`), your `rules.json`, credentials, installed environments, models,
generated schedules, and any unlisted file. Your own `rules.json` and installed
schedule are unchanged by building the ZIP.

## What the recipient does

1. Unzip into a permanent local folder on their Mac. No Git repository is needed.
2. Run `bash scripts/setup-macos.sh`, or install the prerequisites by hand (see
   [Install](../getting-started/install.md)), and sign in with **their own**
   accounts. Gmail modification and Tasks access are required for applied runs;
   follow the CLI prompts and their organization's OAuth policy.
3. Review `rules.json`, the task-list name, the models allowed in
   `classifier.json`, and any locally configured MCP server names to disable.
4. Run the offline tests and the `mail-setup` skill to personalize sender rules.
   Inspect a model-free dry run before enabling paid classification or mailbox
   changes.
5. Install their own schedule only after review. Extracting the ZIP installs no
   schedule and no credentials. Keep the folder where it was installed, because the
   schedule records its path.
