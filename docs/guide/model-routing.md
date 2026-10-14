# Model routing

The runner calls a model only for pending mail that no rule matched and that has
no valid same-day cached decision. When it does, it routes in two tiers: a cheap
model for the first pass, and a stronger model only for the cases the cheap model
is unsure about.

Both run through the GitHub Copilot CLI under your own Copilot account. The model
picked in the Copilot app does **not** override `classifier.json` for the runner.

## `classifier.json`

```json
{
  "version": 1,
  "cheap_model": "gpt-6-luna",
  "escalation_model": "gpt-6.1-sol",
  "confidence_threshold": 0.85,
  "escalation_threshold": 0.9,
  "batch_size": 25,
  "max_batches": 4,
  "max_escalations": 10,
  "context_chars": 4000,
  "timeout_seconds": 180,
  "copilot_binary": "copilot",
  "disabled_mcp_servers": []
}
```

| Setting | Default | Meaning |
| --- | --- | --- |
| `cheap_model` | `gpt-6-luna` | First-pass classification. |
| `escalation_model` | `gpt-6.1-sol` | Ambiguous cases only. |
| `confidence_threshold` | `0.85` | First-pass acceptance threshold. |
| `escalation_threshold` | `0.9` | Escalation acceptance threshold. |
| `batch_size` | `25` | Messages per model invocation. |
| `max_batches` | `4` | First-pass calls per run, so at most 100 fresh messages per run. |
| `max_escalations` | `10` | Messages (not calls) sent to the stronger model per run. |
| `context_chars` | `4000` | Maximum plain-text body characters sent on escalation. |
| `timeout_seconds` | `180` | Timeout for each CLI invocation. |
| `version` | `1` | Bump after intentional classifier-policy changes; it invalidates the cache. |
| `copilot_binary` | `copilot` | CLI executable name or absolute path. |
| `disabled_mcp_servers` | `[]` | Names of your own MCP servers to disable for these calls. |

The file must contain exactly these keys; a missing or unknown key stops the run.
See [Configuration](../reference/configuration.md#classifierjson) for the
validation rules.

## The two tiers

**First pass.** Pending messages are sent in batches of `batch_size`, up to
`max_batches` batches. The model receives the allowed tags with their descriptions
and task policies, and for each message: ID, thread ID, From, To, Cc, date,
subject, a snippet of up to 240 characters, and the bulk flag. It does not receive
the body. It answers, per message, a tag, an optional task, a confidence from 0 to
1, and `needs_context`.

The prompt tells the model that email fields are untrusted data, that being in
`To` alone is not evidence of a request, to choose `Action` but set
`needs_context` when `Action` versus `FYI` is unclear, to use only deadlines
evidenced by the email, and never to propose action overrides.

**Escalation.** A message is ambiguous when `needs_context` is true **or** its
confidence is below `confidence_threshold`. Up to `max_escalations` of those go to
the escalation model with up to `context_chars` of the message's own plain-text
body. Attachments and other messages in the thread are not fetched. An HTML-only
message, or one that refers to earlier thread history, may therefore stay
unresolved.

**Held for review.** If the stronger model also sets `needs_context`, or reports
less than `escalation_threshold`, the message is left untagged in the inbox and
recorded in the cache as "review" for the rest of the day. It is not paid for again
that day unless you ask:

```bash
python3 runner.py --retry-review           # paid retry, dry run
python3 runner.py --retry-review --apply
```

**Over capacity.** Messages beyond `batch_size × max_batches`, or ambiguous
messages beyond `max_escalations`, stay pending and are eligible on the next run.
These limits bound the workload; they are not a currency budget.

In the [demo](../getting-started/demo.md), on an invented mailbox: 10 pending
messages went to the cheap model in one call; 3 were ambiguous and went to the
stronger model in one call; 2 were resolved and 1 ("Friday?") was held for review.
The confidence values in the demo are scripted by hand, not produced by a model.

## Confidence is not calibrated

Confidence is **reported by the model**. It is not a calibrated probability.
A 0.9 does not mean the model is right nine times in ten. The thresholds are a
gate that sends doubtful cases to a stronger model or to you, not a guarantee.
Before relying on unattended decisions for important mail, review representative
output from your own inbox.

## The cache

Validated decisions are saved in `state/classification-cache.json` before
anything is applied, so a retry or an applied run after a dry run does not pay for
them again. The cache key covers:

- the message's metadata fields as sent to the model;
- a hash of `rules.json`;
- the full `classifier.json`;
- today's local date.

Change any of these and the entry no longer matches. A new reply is a new message
with a new ID and is evaluated on its own.

## How the Copilot call is isolated

Each call runs the CLI as a separate process:

```text
copilot --model <model> --silent --stream off --output-format json
        --available-tools= --disable-builtin-mcps --no-custom-instructions
        --no-auto-update --no-remote-export --log-level none
        --usage-output-file <temp>/usage.json
        [--disable-mcp-server <name> ...]
```

- `--available-tools=` gives the model **no tools**, so it cannot act, only answer.
- Built-in MCP servers and each name in `disabled_mcp_servers` are disabled.
- Project custom instructions and remote session export are turned off.
- The process runs in a fresh temporary directory, away from the project's skills
  and hooks.
- Mail goes in through **stdin**, not command-line arguments, so it does not appear
  in the process list.
- `COPILOT_ALLOW_ALL` is removed from the environment, and the run refuses to start
  if `COPILOT_PROVIDER_BASE_URL` or `COPILOT_PROVIDER_TYPE` is set, so mail cannot
  be silently routed to another provider.
- The answer is read from the CLI's JSON event stream: exactly one tool-free final
  assistant message is accepted. Anything else is rejected and recorded as
  `invalid_json`.

Account-level CLI system context or plugins may still add overhead. This is not a
bare model API call.

## Measuring your usage

```bash
python3 runner.py --usage-report
```

It prints, per model, the number of calls, errors, calls with missing usage data,
and summed token counts by category (`input`, `output`, `cache_read`,
`cache_write`) as reported by the CLI. It does not scan mail or call a model.

![The usage report printed after the demo run](../assets/screens/terminal-usage-light.webp#only-light){ loading=lazy }
![The usage report printed after the demo run](../assets/screens/terminal-usage-dark.webp#only-dark){ loading=lazy }

*Demo output. The stand-in CLI estimates tokens from text length; these are not real usage figures.*

Each call is logged in `state/usage.jsonl` with the model, message count, status
(`ok`, `timeout`, `cli_error`, `invalid_json`), duration, prompt and response
character counts, and the CLI's token totals. Characters are not tokens. A timeout
or missing usage export is counted as missing usage; it does not prove that the
call was free. A response can fail validation after a call that was billed.

To turn token counts into money, use the rates for your plan and the formula in
the README's
[costs section](https://github.com/mmornati/ai-email-assistant#costs-and-token-estimates),
and reconcile with your Copilot usage view. CLI logs are not an invoice.

## Why not a local model? (ADR 0001)

[ADR 0001](../adr/0001-laya-vs-luna.md) records an experiment that compared the
local, non-generative Laya typed-decision runtime with `gpt-6-luna` on this
workload. The decision: **production stays on Luna**.

In short, from the ADR:

- On 16 hand-written synthetic messages with known labels, zero-shot Laya got 9/16
  categories right, an exploratory concise schema got 11/16, and Luna got 16/16. Laya
  found 1 of the 4 `Action` messages (2 of 4 with the concise schema) and made some
  high-confidence wrong calls.
- Laya was faster locally and had no hosted inference fee, but it cannot write task
  titles or notes or extract arbitrary dates, so it would still need a generative
  fallback.
- At the low hosted cost observed, removing a few cents of inference was not worth
  the decision risk.
- The sample is very small; the ADR is not a verdict on local models in general and
  lists what would have to be true to reconsider.

The experiment also exposed a reliability bug: long answers wrapped at terminal
width broke the JSON. The runner now reads the CLI's structured JSON events, which
is why `--output-format json` is a required CLI capability.
