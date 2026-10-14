# Install on macOS

## The short version

```bash
git clone https://github.com/mmornati/ai-email-assistant.git
cd ai-email-assistant
scripts/setup-macos.sh --dry-run   # show every command first
scripts/setup-macos.sh             # install, authenticate, verify
```

The setup script is idempotent: re-run it at any time to repair or verify a setup.
It never modifies mail, never passes `--apply`, and never installs the schedule.

!!! warning "Homebrew's `gws` formula is a different tool"
    Homebrew has an unrelated formula called `gws` (a git workspace tool) that
    installs a binary with the same name as the Google Workspace CLI. Install
    `googleworkspace-cli`, not `gws`. The setup script checks for this and stops
    with an explanation if the `gws` formula is installed; run `brew uninstall gws`
    if you do not need it, then re-run the script.

## What the script does

1. **Checks the platform.** It stops unless it is running on macOS, and stops if
   [Homebrew](https://brew.sh) is missing (install Homebrew yourself after
   reviewing its script, then re-run).
2. **Finds Python 3.10+.** It looks for `python3` and Homebrew's `python3`. If
   neither is 3.10 or newer (macOS ships 3.9), it installs `python@3.13` with
   Homebrew.
3. **Installs the command-line tools** with Homebrew, skipping any that are
   already on your `PATH`:
    - `googleworkspace-cli`, which provides `gws`
      ([Google Workspace CLI](https://github.com/googleworkspace/cli));
    - the `gcloud-cli` cask, which provides `gcloud`;
    - the `copilot-cli` cask, which provides `copilot`
      ([GitHub Copilot CLI](https://docs.github.com/copilot/how-tos/copilot-cli)),
      unless you pass `--skip-copilot`.
4. **Creates private local files.** It creates `state/` with owner-only
   permissions (or tightens an existing one to `700`), and copies
   `rules.example.json` to `rules.json` if you do not have a `rules.json` yet. An
   existing `rules.json` is left untouched.
5. **Signs you in**, asking before each step:
    - `gcloud auth login`, needed once to create the OAuth client;
    - `gws auth setup` (with `--project ID` if you passed one), which creates or
      reuses a Google Cloud project with an OAuth client;
    - `gcloud services enable gmail.googleapis.com tasks.googleapis.com` if those
      APIs are not enabled yet;
    - `gws auth login` with **only** the `gmail.modify` and `tasks` scopes;
    - `copilot login`, unless you passed `--skip-copilot`.
6. **Verifies.** It runs the offline test suite (no mailbox access, no model calls)
   and, after asking, a read-only, model-free dry run: `runner.py --no-model`. Exit
   code 2 from that dry run is expected: it means untagged mail is waiting for
   classification.
7. **Prints the next steps.**

`gmail.modify` lets the tool read message metadata, change labels and archive. It
does not include sending. `tasks` lets it read and create Google Tasks.

## Options

| Option | Effect |
| --- | --- |
| `-y`, `--yes` | Answer yes to every prompt. Browser logins still open. |
| `-n`, `--dry-run` | Print the commands that would run; change nothing. |
| `--project ID` | Use an existing Google Cloud project for `gws auth setup`. |
| `--skip-auth` | Install tools and local files only; no logins (and no read-only dry run). |
| `--skip-copilot` | Do not install or log in to the Copilot CLI. Only model-free runs (`runner.py --no-model`) will work. |
| `--skip-verify` | Do not run the tests or the read-only dry run. |
| `-h`, `--help` | Show the help. |

An unknown option prints the help and exits with code 64.

## Installing by hand

If you prefer not to run the script, you need:

- Python 3.10+ on macOS. There are no additional Python package dependencies.
- An authenticated [`gws` CLI](https://github.com/googleworkspace/cli) with Gmail
  and Tasks access. Use `gws auth setup` if OAuth configuration is needed, then
  `gws auth login --services gmail,tasks`, and check with `gws auth status`. Do not
  use read-only access if you intend to apply changes: Gmail modification and Tasks
  access are required.
- An authenticated [Copilot CLI](https://docs.github.com/copilot/how-tos/copilot-cli)
  (`copilot login`), unless you will only run model-free.
- A private `state/` folder and a `rules.json`:

    ```bash
    mkdir -m 700 state
    cp rules.example.json rules.json
    ```

The installed Copilot CLI must support `--available-tools=`,
`--no-custom-instructions`, `--no-remote-export`, `--output-format json` and
`--usage-output-file`. Check with `copilot --help` and `copilot help permissions`.
Both models named in `classifier.json` must be available to your account under
your organization's policy.

## If something fails

- **Authentication errors from `gws`:** run `gws auth status`, then
  `gws auth login --services gmail,tasks`, and re-run a preview.
- **Copilot errors:** run `copilot login`, check that the installed CLI supports
  the flags above, and that the model names in `classifier.json` are permitted for
  your account.
- **`gws` is the wrong program:** see the warning at the top of this page.

Then continue with [your first run](first-run.md).
