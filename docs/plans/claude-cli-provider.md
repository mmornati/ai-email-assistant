# Plan: selectable classifier CLI (Copilot or Claude)

Status: in progress — steps 1 (refactor) and 2 (Claude backend) implemented. Branch: `claude/claude-cli-integration-plan-640b25`.

## Goal

Let the user choose, in `classifier.json`, which CLI runs the paid classification
step in `runner.py`: the existing GitHub Copilot CLI (`copilot`) or Claude Code
(`claude`). Everything model-free (rules, sweeps, Tasks sync, cache, validation,
reporting) stays identical. The selected CLI must get the same isolation guarantees
the Copilot path has today:

- no tools, no MCP servers, no project/user instructions, hooks or plugins;
- mail goes through stdin, never `argv`;
- a temporary, empty working directory;
- custom provider/base-URL environment overrides are refused;
- CLI output and errors never land in logs (they can contain mail);
- strict JSON response, validated by the same `validate_prediction`.

## Where Copilot is wired today

| Place | Copilot coupling |
| --- | --- |
| `runner.py` `load_config` | requires the exact key set incl. `copilot_binary`, `disabled_mcp_servers` |
| `runner.py` `call_model` | builds the `copilot` command, strips `COPILOT_ALLOW_ALL`, refuses `COPILOT_PROVIDER_*`, reads `--usage-output-file` |
| `runner.py` `parse_cli_response` | parses Copilot JSONL events (`assistant.message`, `phase=final_answer`) |
| `runner.py` `record_usage` / `usage_report` | Copilot usage keys (`totalNanoAiu`, `tokenDetails`) |
| `runner.py` `cache_key` | hashes the whole config |
| `schedule.py` install | hard-coded `shutil.which("copilot")` |
| `scripts/setup-macos.sh` | installs `copilot-cli`, runs `copilot login`, `--skip-copilot` |
| `benchmark.py` | calls `runner.call_model`, reads `cli_usage`, model price table |
| `.github/skills/*` | Copilot-only skill location; Claude Code reads `.claude/skills/` |
| `README.md`, `SECURITY.md`, `share.py` | Copilot-only docs and ZIP allowlist |

Tests patch `runner.call_model`, so keeping its signature keeps `tests/test_triage.py`
classification tests unchanged.

## 1. Configuration format

New `classifier.json` (one key switches the CLI; each CLI keeps its own models):

```json
{
  "version": 1,
  "cli": "copilot",
  "confidence_threshold": 0.85,
  "escalation_threshold": 0.9,
  "batch_size": 25,
  "max_batches": 4,
  "max_escalations": 10,
  "context_chars": 4000,
  "timeout_seconds": 180,
  "providers": {
    "copilot": {
      "binary": "copilot",
      "cheap_model": "gpt-6-luna",
      "escalation_model": "gpt-6.1-sol",
      "disabled_mcp_servers": []
    },
    "claude": {
      "binary": "claude",
      "cheap_model": "claude-haiku-5-5",
      "escalation_model": "claude-sonnet-5-5",
      "auth": "subscription",
      "max_budget_usd_per_call": 0.25
    }
  }
}
```

Rules in `load_config`:

- `cli` must be `"copilot"` or `"claude"`; unknown values fail fast.
- Top-level keys stay an exact set (as today). `providers` must contain the entry
  for the selected `cli`; other entries are validated if present, so a typo in the
  inactive block is caught before the user switches.
- Per-provider exact key sets:
  - copilot: `binary`, `cheap_model`, `escalation_model`, `disabled_mcp_servers`
  - claude: `binary`, `cheap_model`, `escalation_model`, `auth`
    (`"subscription"` or `"api_key"`), `max_budget_usd_per_call` (positive number)
- **Legacy format:** a file with `copilot_binary`, `cheap_model`, … and no `cli` is
  accepted and normalized to `cli: "copilot"` with the same values, so existing
  installs and shared ZIPs keep working. No automatic rewrite of the user's file.
- `load_config` returns a normalized dict: shared settings plus `cli`, plus the
  active provider's settings flattened (`binary`, `cheap_model`, `escalation_model`, …).
  The rest of `runner.py` keeps reading `cfg["cheap_model"]` etc.
- `version` keeps its current meaning (classifier policy). The format is detected
  by the `cli` key, not by bumping `version`.

Optional one-off override: `runner.py --cli claude` replaces `cfg["cli"]` after
loading (useful to compare/probe without editing the file). The provider block must
still exist and validate. `--usage-report` is unaffected.

**Cache:** `cache_key` hashes the normalized active config, which includes `cli`
and the active models. Switching CLI or model invalidates same-day cached
classifications (correct: a different classifier produced them); editing the
inactive provider block does not.

## 2. Backend abstraction in `runner.py`

Keep one public entry point, `call_model(messages, rules, cfg, model)`, and move
CLI specifics behind a small backend table (plain functions, matching the module's
style; no new dependency):

```python
BACKENDS = {"copilot": COPILOT, "claude": CLAUDE}
# each: name, refuse_env(), command(cfg, model, workdir), env(cfg),
#       parse(stdout) -> dict, usage(stdout, workdir) -> dict | None
```

`call_model` becomes the shared skeleton: env check, temp dir, `subprocess.run`
with `input=`, timeout handling, usage recording, error messages that name the CLI
but never include its output. The current Copilot code moves verbatim into the
Copilot backend (step 1 of the rollout is a pure refactor with no behavior change).

Split `prompt_for` into `instructions(rules)` (fixed classifier rules + allowed
tags) and `payload(messages)` (untrusted mail JSON). Copilot still receives
`instructions + payload` on stdin exactly as today; Claude receives the
instructions as its system prompt and only the payload on stdin (see below).

## 3. Claude backend

### Command

```text
claude -p
  --model <model>
  --output-format json
  --tools ""                         # no built-in tools at all
  --strict-mcp-config --mcp-config '{"mcpServers":{}}'   # no MCP servers
  --setting-sources project          # skip user settings: no user hooks/plugins/permissions
  --disable-slash-commands           # no skills
  --no-session-persistence           # no transcript written to ~/.claude
  --permission-mode dontAsk
  --max-budget-usd <max_budget_usd_per_call>
  --system-prompt <instructions(rules)>
  [--bare]                           # only when auth == "api_key"
```

- Runs with `cwd` = the empty temp dir, so `project` settings and project
  `CLAUDE.md` resolve to nothing.
- `--system-prompt` replaces Claude Code's coding-agent system prompt with the
  classifier instructions: less overhead per call and better instruction-following.
  The instructions contain only tag definitions (from `rules.json`), never mail.
- Mail payload goes on stdin.
- `--bare` is the strongest isolation (skips hooks, plugins, auto-memory, keychain,
  `CLAUDE.md` discovery) but **only accepts `ANTHROPIC_API_KEY` / `apiKeyHelper`
  auth**, not a Claude subscription login. Hence the `auth` setting:
  - `api_key`: add `--bare`; require `ANTHROPIC_API_KEY` in the environment
    (schedule docs explain how to provide it without putting it in the plist,
    e.g. `apiKeyHelper` reading the macOS keychain).
  - `subscription`: no `--bare`; rely on the flags above. Must verify (see
    "Verification spikes") whether the user-level `~/.claude/CLAUDE.md` and
    auto-memory are still injected; if so, document the overhead/privacy effect or
    find the opt-out.

### Environment

- Refuse to run if any of `ANTHROPIC_BASE_URL`, `ANTHROPIC_BEDROCK_BASE_URL`,
  `ANTHROPIC_VERTEX_BASE_URL`, `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`,
  `CLAUDE_CODE_USE_FOUNDRY` is set (same policy as the `COPILOT_PROVIDER_*` refusal:
  never silently route mail to another provider).
- Drop `ANTHROPIC_API_KEY` from the child env when `auth == "subscription"`, so the
  billing route is the one the user configured.
- Set `NO_COLOR=1`, `DISABLE_AUTOUPDATER=1`, `DISABLE_TELEMETRY=1`,
  `DISABLE_ERROR_REPORTING=1` (error reports could carry prompt fragments).

### Response parsing (`parse_claude_response`)

`--output-format json` prints one result object. Accept only when:

- it is a JSON object with `type == "result"`, `subtype == "success"`,
  `is_error is False`;
- `num_turns == 1` (a tool-free single answer, mirroring the Copilot
  "one tool-free final message" check);
- `result` is a string; return `json.loads(result)`. Optionally strip a single
  surrounding ```json fence before parsing, since models sometimes add one; anything
  else is `invalid_json`.

`error_max_budget_usd`, `error_max_turns` and similar subtypes map to the existing
`cli_error` status with a message that names the subtype only.

Later improvement (not in the first cut): `--json-schema` with a per-batch schema
(required message IDs, enum of allowed tags) for structured output. Local validation
stays authoritative either way.

### Usage

Map Claude's `usage` to the existing sanitized shape so reports stay uniform:

| Claude field | stored as |
| --- | --- |
| `usage.input_tokens` | `tokens.input` |
| `usage.output_tokens` | `tokens.output` |
| `usage.cache_read_input_tokens` | `tokens.cache_read` |
| `usage.cache_creation_input_tokens` | `tokens.cache_write` |
| `total_cost_usd` | `cost_usd` (new, Claude only) |

`record_usage` gains a `cli` field per entry. `usage_report` groups by
`cli/model` (old entries without `cli` count as `copilot`) and sums `cost_usd`
when present. Usage is taken from stdout, so a non-JSON/timeout call still records
`cli_usage: null` ("missing usage" ≠ free, as documented today).

## 4. Scheduling (`schedule.py`)

- `install` loads `classifier.json` (unless `--no-model`) and checks
  `shutil.which(cfg["binary"])` for the selected CLI instead of `"copilot"`.
  Error text names the CLI.
- The recorded `PATH` must include the Claude install location
  (`~/.local/bin` for the native installer, Homebrew prefix for the cask);
  `which` at install time already guarantees this.
- Auth in a LaunchAgent: `subscription` relies on the login stored in the user's
  keychain (LaunchAgent runs in the GUI session); `api_key` needs a key source that
  works non-interactively. Verify both (spike 3).
- Switching CLI later is a config edit, not a reinstall, unless the new binary is
  not on the recorded `PATH` (document this next to the existing reinstall notes).

## 5. Setup script (`scripts/setup-macos.sh`)

- New `--cli copilot|claude` (default: the value in `classifier.json`, else
  `copilot`). `--skip-copilot` stays as an alias for a new `--no-model-cli`.
- `claude`: install with `brew install --cask claude-code` (Homebrew, consistent
  with the other tools; no `curl | sh`), then offer `claude auth login`
  (or `claude setup-token` for a long-lived token; confirm which is right for
  unattended runs in spike 3).
- When `--cli` differs from the config, set `"cli"` in `classifier.json` with a
  small Python `json` rewrite (atomic, idempotent, printed in `--dry-run`).
- Final hints mention the chosen CLI and the matching interactive skill location.

## 6. Interactive skills

Copilot reads `.github/skills/`; Claude Code reads `.claude/skills/`. Options:

1. **Copies + drift test (recommended):** add `.claude/skills/mail-triage/SKILL.md`
   and `.claude/skills/mail-setup/SKILL.md` identical to the `.github` ones, plus a
   test that asserts byte equality. Simple, works in the ZIP and on every OS.
2. Symlinks: less duplication, but `share.py` and Windows/ZIP handling get harder.
3. A `CLAUDE.md` pointing at `.github/skills`: no native skill discovery.

Also make the skill text CLI-neutral ("outside the AI app" instead of "outside
Copilot") and add the `.claude/skills` files to `share.py`'s allowlist.

Note: this repository is itself developed with Claude Code worktrees under
`.claude/worktrees/`; make sure `.gitignore` ignores `.claude/worktrees/` and
`.claude/settings.local.json` but **not** `.claude/skills/`.

## 7. Benchmark

`benchmark.py` calls `runner.call_model` and computes cost from a per-model rate
table. Add Claude model rates (verified on the implementation date, as the README
does for Copilot) and prefer the CLI-reported `cost_usd` when present.

## 8. Documentation

- README: "Choosing the classifier CLI" section (config key, auth modes, what is
  isolated, what is not); prerequisites per CLI; schedule notes; usage report.
- Claude cost table with verified prices and date, plus a measured synthetic
  startup-overhead probe like the existing Copilot one (spike 2).
- Privacy note: mail snippets/bodies go to the selected provider; subscription vs
  API data-handling terms differ; link both vendors' policies.
- `SECURITY.md`: list the Claude env refusals and isolation flags.
- `docs/adr/0002-selectable-classifier-cli.md`: why a config switch with per-CLI
  model blocks, why no direct API SDK (keeps "no Python dependencies" and reuses
  the user's CLI login), and the `--bare` trade-off.

## 9. Tests (offline, no paid calls)

`tests/test_triage.py` / new `tests/test_providers.py`:

- `load_config`: new format OK for each CLI; unknown `cli`; missing active provider
  block; unknown/missing provider keys; bad `auth`; non-positive budget; legacy
  format normalized to copilot; `--cli` override.
- `cache_key` changes when `cli` or active model changes, not when the inactive
  block changes.
- Claude command: `-p`, `--tools ""`, strict MCP, `--setting-sources project`,
  `--no-session-persistence`, `--max-budget-usd`, `--bare` only for `api_key`;
  no mail text in `argv`; `cwd` is a temp dir; payload on stdin; system prompt
  contains no message fields.
- Env: each forbidden variable raises before spawning; `ANTHROPIC_API_KEY`
  stripped for `subscription`.
- `parse_claude_response`: success; `is_error`; non-success subtypes;
  `num_turns > 1`; non-string/invalid `result`; fenced JSON.
- Timeout and nonzero exit record usage with status and never echo stdout/stderr.
- `record_usage` mapping for Claude usage; `usage_report` groups by `cli/model`,
  legacy lines count as copilot.
- Existing Copilot tests still pass unchanged after the refactor (regression gate).
- `schedule.py install` checks the configured binary (copilot and claude).
- Setup script `--dry-run --cli claude` installs `claude-code`, not `copilot-cli`,
  and prints the config change; `--skip-copilot` still works.
- Skill copies identical; `share.py` ZIP contains `.claude/skills/*` and no
  `.claude/worktrees` or local settings.

## 10. Verification spikes (before finalizing docs)

Each is a manual run with a synthetic, non-mail prompt:

1. **Isolation:** with `subscription` auth and the flags above, confirm no user
   hooks fire, no MCP servers start, no tools are offered, and whether
   `~/.claude/CLAUDE.md`/auto-memory reach the model. Check `--setting-sources`
   behavior with an empty project dir and whether `--setting-sources ""` is allowed.
2. **Overhead:** record tokens/cost of a one-message classification for each
   Claude model with `--system-prompt` vs default, and with/without `--bare`.
3. **Unattended auth:** run `runner.py` from the installed LaunchAgent with each
   `auth` mode; confirm keychain/OAuth works without a terminal.
4. **Output contract:** confirm the exact `--output-format json` fields
   (`subtype`, `num_turns`, `usage`, `total_cost_usd`) on the installed version
   and pin a minimum Claude Code version in README.

## Spike results (2026-10-14, Claude Code 2.1.284, synthetic prompts only)

- **Output contract (spike 4):** `-p --output-format json` prints one object with
  `type: "result"`, `subtype`, `is_error`, `num_turns`, `permission_denials`,
  `result`, `usage.{input,output,cache_read_input,cache_creation_input}_tokens` and
  `total_cost_usd`, as assumed. The pinned ID `claude-haiku-5-5` works, with a harmless
  `unrecognized_model` notice on stderr.
- **Isolation (spike 1, subscription auth):** with `--setting-sources project`,
  `--system-prompt` and an empty cwd, the global `~/.claude/CLAUDE.md` and project
  instructions are **not** sent. The only extra context is a short account section
  (the signed-in email). `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` does not remove it and adds
  an environment section, so it is not used. `--exclude-dynamic-system-prompt-sections`
  is ignored with `--system-prompt`.
- **Overhead (spike 2, partial):** a tiny prompt costs ~740-815 cache-write tokens
  (vs ~17k for Copilot). A two-message synthetic classification on Haiku used 1,635
  cache-write and 696 output tokens; the CLI reported `total_cost_usd` 0.027.
  Output tokens are higher than the visible JSON, which suggests thinking tokens;
  evaluate `--effort low` before publishing cost figures.
- **Provider override check:** a Claude Code session sets `ANTHROPIC_BASE_URL` for
  its own proxy, so `runner.py` refuses the Claude backend when started from inside
  one. This is intended; the LaunchAgent environment does not have it. Document it.
- Unattended auth from the LaunchAgent (spike 3) is still open.

## Rollout (one PR, reviewable commits)

1. Refactor: config normalization + backend table, Copilot only; legacy and new
   config formats; no behavior change. All existing tests green.
2. Claude backend + `--cli` override + usage changes + tests.
3. `schedule.py` and setup script.
4. Skills copies, `share.py`, `.gitignore`.
5. Spikes 1–4, then README/SECURITY/ADR/benchmark rates with measured numbers.

Default stays `"cli": "copilot"` so existing users see no change.

## Open decisions

- Default Claude models: `claude-haiku-5-5` (first pass) and `claude-sonnet-5-5`
  (escalation) are proposed; pinned IDs rather than aliases (`haiku`, `sonnet`)
  so a silent alias upgrade does not change classifications or cost.
- ~~Default `auth` for Claude~~ — decided: `subscription`; `api_key` (`--bare`)
  stays available.
- Skill sharing approach (copies + drift test proposed).
