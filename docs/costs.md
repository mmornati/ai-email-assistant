# Costs and token estimates

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

## Measured CLI startup overhead

A tool-free **synthetic probe**, not an inbox run, used 3 input tokens, 16,784
cache-write tokens and 9 output tokens with the small model. Applying the rates
above gives approximately **$0.00210** for that call:

```text
(3 * 0.10 + 16,784 * 0.125 + 9 * 0.50) / 1,000,000
```

This demonstrates why batching and skipping empty runs matter: even a tiny prompt
can carry substantial CLI system context. Actual classifier prompts are larger.

An additional synthetic one-message classification validated both configured
models. The small-model call used 3 input, 17,379 cache-write and 64 output tokens
(approximately $0.00220). The stronger-model call used 3 input, 17,387 cache-write
and 27 output tokens (approximately $0.04374). These were separate validation
calls, not production triage or an accuracy benchmark.

## Illustrative monthly budgets, not observed inbox costs

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
length can cost more. Running the same workflow as an app automation would instead
start a full agent session on every one of those ticks, even when the inbox is empty.

## Measure your real usage

```bash
make usage            # python3 runner.py --usage-report
```

`state/usage.jsonl` records each call's model, message count, status, duration,
prompt/response character counts and sanitized CLI token totals. Characters are
**not** tokens. A timeout or missing usage export is marked as missing usage;
it does not prove that the failed call was free. Model response validation can
fail after a successfully billed call.

For each model, use the reported token categories:

```text
USD = (input * input_rate + cache_read * cache_read_rate
       + cache_write * cache_write_rate + output * output_rate) / 1,000,000
AI credits at reference rate = USD * 100
```

Use the CLI's billing token categories, not an additional sum of the inclusive
model input totals, to avoid double-counting cached tokens. Reconcile with the
account's Copilot usage view; legacy plans may expose premium-request accounting
instead. CLI logs and synthetic probes are not the account invoice.
