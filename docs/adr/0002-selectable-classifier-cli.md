# ADR 0002: Selectable classifier CLI (Copilot or Claude Code)

Date: 2026-10-14  
Status: Accepted  
Decision scope: Which command-line tool `runner.py` uses for paid classification  
Production default: unchanged (`"cli": "copilot"`)

## Decision

`classifier.json` selects the classifier CLI with `"cli"`, either `"copilot"`
(GitHub Copilot CLI, the default) or `"claude"` (Claude Code). Each CLI keeps its
own binary and models under `"providers"`, so switching is a one-key change and
neither CLI's settings are lost. The deterministic scanner, cache, validation,
task policy and reporting are shared and unchanged.

Claude Code defaults to the user's **subscription login**, with the pinned models
`claude-haiku-5-5` (first pass) and `claude-sonnet-5-5` (escalation).

## Context

The runner already treated the model as an untrusted, isolated subprocess: no
tools, a temporary working directory, mail on stdin, strict JSON validated
locally. Some users have Claude subscriptions rather than Copilot seats, and
Claude Code can be isolated to the same standard, so supporting it needs no new
trust model.

## Options considered

1. **Call the Anthropic API from Python with the SDK.** Cleanest isolation and
   exact usage data, but it adds the project's first Python package dependency,
   needs an API key (no subscription login), and a key would have to be stored for
   the schedule. Rejected for now.
2. **Replace Copilot with Claude Code.** Breaks existing installs and shared
   ZIPs. Rejected.
3. **A config switch over a small backend table (chosen).** One `call_model`
   skeleton handles the temp directory, stdin, timeout, usage recording and
   error redaction; each backend supplies its command, environment checks,
   response parser and usage sanitizer. The older flat Copilot-only config is
   still read as `copilot`.

## Claude Code isolation

`claude -p --output-format json --tools "" --strict-mcp-config --mcp-config
'{"mcpServers":{}}' --setting-sources project --disable-slash-commands
--no-session-persistence --permission-mode dontAsk --max-budget-usd <cap>
--system-prompt <instructions>`, run in an empty temporary directory with mail on
stdin. The response must be one successful, tool-free turn.

### Subscription vs `--bare`

`--bare` skips every automatic context source but accepts only
`ANTHROPIC_API_KEY`, which the schedule cannot hold safely. Synthetic probes on
Claude Code 2.1.284 with subscription auth and the flags above showed:

- the global `~/.claude/CLAUDE.md` and project instructions are **not** sent;
- a short account section containing the signed-in email **is** sent;
- `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` does not remove it and adds an environment
  section, so it is not used.

Sending the account email to the account's own provider was judged acceptable.
`"auth": "api_key"` remains available for interactive use and adds `--bare`;
`schedule.py` refuses to install with it.

## Consequences

- **Pinned model IDs.** On Claude Code 2.1.284 the `haiku` alias resolves to
  Claude Haiku 4.5, so aliases would silently change classifications and cost.
- **CLI cost estimate is wrong for unrecognized IDs.** That version does not
  recognize `claude-haiku-5-5`/`claude-sonnet-5-5` and prices them at Claude
  Opus 5.5 rates (about 40x Haiku). Usage keeps it only as `cli_cost_usd`; cost is
  computed from tokens, with 1-hour cache writes (`cache_write_1h`) priced
  separately. `--max-budget-usd` uses the same estimate, so the default cap is
  $1.00, a runaway guard rather than a budget.
- **Small overhead.** Replacing the system prompt keeps a call's fixed overhead
  near 700-800 cache-write tokens, against ~17,000 measured for Copilot.
- **Refused proxies.** A terminal inside a Claude Code session sets
  `ANTHROPIC_BASE_URL`, which the runner refuses, so manual runs must come from a
  normal terminal. This is intended: mail must not be routed through an
  unexpected endpoint.
- **Skills in two places.** Claude Code reads `.claude/skills/`; the skills are
  byte-identical copies of `.github/skills/`, enforced by a test.
- **Cache invalidation on switch.** The cache key includes the selected CLI and
  models, so switching re-classifies that day's pending mail once.

## Open items

- Confirm that subscription auth works from the LaunchAgent with no terminal.
- Measure whether `--effort low` reduces Haiku 5.5's output tokens (696 output
  tokens for a two-message probe suggests default thinking) without lowering
  decision quality.
- Revisit `--json-schema` structured output once a per-batch schema is designed.
