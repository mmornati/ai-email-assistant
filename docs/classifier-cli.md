# Choosing the classifier CLI

Pending mail is classified by a CLI you select in `classifier.json`: the
[GitHub Copilot CLI](https://docs.github.com/copilot/how-tos/copilot-cli)
(default) or [Claude Code](https://claude.com/product/claude-code). The same tool
also hosts the interactive review skills; neither is the hourly scheduler.
The reasoning and the measurements behind the Claude Code defaults are in
[ADR 0002](adr/0002-selectable-classifier-cli.md).

## Select at install time

```bash
bash scripts/setup-macos.sh --cli claude    # installs Claude Code, sets "cli", runs claude auth login
bash scripts/setup-macos.sh --cli copilot   # the default
```

`make doctor` checks whichever CLI `classifier.json` selects.

## Select later

`classifier.json` selects the CLI with `"cli"` and keeps each CLI's binary and
models under `"providers"`:

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

## GitHub Copilot CLI

Copilot calls have no available tools, run in a temporary working directory,
suppress project custom instructions and remote session export, and receive mail
through stdin, not command-line arguments. Built-in MCP servers and the
configured `disabled_mcp_servers` names are disabled. Refused environments:
`COPILOT_PROVIDER_BASE_URL` and `COPILOT_PROVIDER_TYPE`.

The installed Copilot CLI must support `--available-tools=`,
`--no-custom-instructions`, `--no-remote-export`, `--output-format json`, and
`--usage-output-file`. Check `copilot --help` and `copilot help permissions`.

## Claude Code

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

Claude Code was verified with version 2.1.284; it must support `-p`,
`--output-format json`, `--tools`, `--strict-mcp-config`, `--setting-sources`,
`--no-session-persistence` and `--max-budget-usd` (check `claude --help`).

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

`max_budget_usd_per_call` is a per-call guard against runaway output, measured in
the CLI's own estimate, not a budget. See [Costs](costs.md#claude-code-rates-and-measured-overhead)
for why that estimate is unreliable for these models.

## Data retention

The selected CLI's provider retention policy applies to data sent to it: Copilot
(GitHub and the model provider) or Claude Code (Anthropic; terms differ between
a Claude subscription and API-key use).
