# ADR 0001: Keep Luna for mail decisions; do not deploy zero-shot Laya

Date: 2026-10-07  
Status: Accepted for this project; revisit after domain-specific evaluation  
Decision scope: Classification of rule-unmatched mail and extraction of Tasks details  
Production model configuration: unchanged

## Decision

Keep the deterministic scanner plus GPT-6 Luna first pass and selective GPT-6.1
Sol escalation. **Do not replace the production classifier with zero-shot Laya.**
Retain Laya as a local, reproducible research benchmark, not as an unattended
labeling/archiving engine.

Laya is substantially faster locally and carries no hosted inference fee. It
does not yet meet this project's decision-quality requirements, cannot generate
task titles/notes or extract unrestricted dates, and would still require a
generative fallback. At the observed low hosted cost, removing a few cents of
inference is not worth the demonstrated decision risk.

This is not a conclusion about every Laya checkpoint, fine-tuned Laya, or local
models in general. The comparison below evaluates a particular zero-shot router,
two question schemas, and a very small sample.

## Context: the actual Laya project

The requested project is [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya),
not a similarly named chat model. The initially attempted Qwen download was
stopped after clarification; no Qwen inference was performed.

Laya uses small encoders with typed decision heads: categorical choice, score,
and yes/no probability. It is **non-autoregressive**, not a drop-in generative LLM.
The upstream documentation describes English, multilingual, and typed-decisions
checkpoints. Only English and multilingual were downloaded and tested here.
The specialized typed-decisions checkpoint was not silently treated as a
general mail classifier.

LM Studio was available on the test machine, but this experiment used Laya's
own Python runtime. The documented Laya checkpoint/runtime format is not an
LM Studio chat-model integration. No LM Studio settings or model files were
changed.

No organization-specific approval is implied by this experiment. It does not
change the production provider or policy.

## Reproducible environment

| Item | Measured/configured value |
| --- | --- |
| Hardware | Apple M5, 16 GiB unified memory |
| Local device/backend | Apple GPU (`mps`), eager inference |
| Benchmark Python | 3.13.11, isolated `.venv-benchmark` |
| Laya | 0.4.0, verified PyPI package |
| Runtime dependencies | PyTorch 2.14.1, Transformers 5.19.0 |
| Checkpoint repository | `convaiinnovations/laya` |
| Pinned checkpoint revision | `7b928d828b7b0e022f929d9bd2e44165aa270148` |
| English weights | 842,609,210 bytes |
| Multilingual weights | 643,835,514 bytes |
| Combined weight size | 1,486,444,724 bytes, approximately 1.38 GiB |
| Additional disk use | Tokenizers, configs, isolated dependencies and download caches |
| Initial download + preload | 154.958 seconds, network-dependent |
| Cached process preload in main benchmark | 5.675 seconds |
| Local batch cap | 8 messages |
| Context cap | 1,024 tokens per request |
| Local router | Automatic English/multilingual detection, both checkpoints preloaded |
| Hosted model | `gpt-6-luna`, tool-free Copilot CLI |
| Repetitions | Two per model/scope; identical inputs within each experiment |

The [checkpoint metadata](https://huggingface.co/convaiinnovations/laya) reports
Apache-2.0. This experiment installed the verified package with the package
manager, not copied source code or a custom inference implementation.

An initial dependency HTTP request failed certificate validation. The benchmark
uses `truststore==0.10.4` to load the native system certificate store; TLS
verification was **not** disabled. That dependency is benchmark-only.

Exact resolved benchmark dependencies are in
[`tools/benchmark/requirements.lock`](../../tools/benchmark/requirements.lock).

### Confidence warning

Loading the English checkpoint emitted:

> This checkpoint ships invalid temperatures or values outside [0.5, 5];
> using choice:11+=0.10058280825614929 -> 0.5. Treat confidence from the
> affected entries as uncalibrated.

The existing taxonomy has 12 categories, so this warning is relevant, not
cosmetic. The benchmark records it. No calibration fix or temperature tuning was
performed. Laya's `answer_confidence` is used as the selected-class score; its
separate entropy-style `confidence` is retained in private evidence. These
numbers are not interchangeable with Luna's self-reported confidence, nor are
either independently calibrated for this mailbox.

## Experimental protocol

1. Read and freeze the current `state/pending.json` in memory under the shared
   lock: **four unclassified messages**. Repeated evaluations used that same
   snapshot, not four fresh mailbox searches.
2. Use the same message metadata for both systems: subject, snippet, sender,
   recipients, date and bulk indication when available. Do not fetch bodies,
   attachments or thread history.
3. Give each system all 12 allowed categories. Luna uses the existing production
   prompt and task schema. Laya answers a choice question and a separate
   action-needed probability question over each email.
4. Add **16 hand-authored synthetic controls**, with reference tags, task presence
   and explicit dates established before inference. These include English,
   French, Italian and Spanish, four Action cases, informational updates,
   automated categories, and one embedded-instruction case.
5. Run two repetitions for both scopes and both models. No task or Gmail action
   is applied; production caches, pending and decisions files are not rewritten.
6. Separately evaluate a concise Laya schema on the same inputs, locally only,
   without more hosted comparisons. This is **exploratory schema tuning on the
   development sample**, not a held-out result.

Frozen real-scope hash:
`4b125395aaf95dee662e66eebf7ed08ec269ddd815a886d80f3a9d2c0feb955d`.
The concise-schema experiment produced the same hash.

Laya is tested on the **shared decision subset**, not credited with functionality
it does not have. Its task-presence flag combines its yes/no result with each
tag's `always`/`optional`/`never` policy. It does not create a task or fabricate
titles/dates. Luna's task strings are validated but excluded from persisted
benchmark evidence.

Real message keys below are anonymous aliases, not Gmail IDs. No subjects, bodies,
names, email addresses or task titles are included in this ADR. Private evidence
contains classifications/probabilities and an opaque input hash, not raw mail.

## Measured results

### Synthetic accuracy against known reference labels

Both repetitions gave the same tags/task-presence results.

| Metric | Laya baseline | Laya concise schema (exploratory) | Luna |
| --- | ---: | ---: | ---: |
| Correct categories | 9/16 | 11/16 | 16/16 |
| Category accuracy | 56.25% | 68.75% | 100% |
| Correct task-presence flags | 11/16 | 15/16 | 16/16 |
| Action-category true positives | 1/4 | 2/4 | 4/4 |
| Action-category recall | 25% | 50% | 100% |
| Action-category false positives | 0 | 0 | 0 |
| Explicit date extraction | Unsupported | Unsupported | 3/3 |
| Date-or-absence matches across all controls | Not comparable | Not comparable | 16/16 |
| Above illustrative 0.85 category gate | 9/16 | 9/16 | 16/16 |
| Correct categories among gated items | 7/9 | 7/9 | 16/16 |

Action **category recall** and task presence are different metrics. For example,
a local result can mislabel a request as FYI but still flag a task. That does not
make the label correct or the downstream workflow safe.

The gate did not eliminate errors: the concise schema assigned the Italian and
Spanish FYI controls to Newsletter with scores 0.969 and 0.9972 respectively.
Those are high-confidence wrong categories. The baseline also flagged tasks on
informational/already-completed controls, and the embedded-instruction control.
The concise schema improved task presence but still flagged a task on the
embedded-instruction control.

These are adversarial robustness observations, **not an exploitability audit**.
Laya received no tools, so no embedded instruction caused a mailbox action.

### Every synthetic category decision

| ID | Control | Reference | Laya baseline | Laya concise | Luna |
| --- | --- | --- | --- | --- | --- |
| s01 | English budget approval | Action | FYI | Internal-Comms | Action |
| s02 | French agreement request | Action | Action | Action | Action |
| s03 | Italian information only | FYI | Newsletter | Newsletter | FYI |
| s04 | Deployment complete, no action | FYI | FYI | FYI | FYI |
| s05 | Reply to confirm receipt | Action | FYI | Shares | Action |
| s06 | Newsletter | Newsletter | Newsletter | Newsletter | Newsletter |
| s07 | Retail discount | Promo | Promo | Promo | Promo |
| s08 | Calendar invitation | Meeting/Invite | Meeting/Invite | Meeting/Invite | Meeting/Invite |
| s09 | Meeting summary | Meeting/Notes | Meeting/Notes | Meeting/Notes | Meeting/Notes |
| s10 | Paid invoice receipt | Admin | FYI | Admin | Admin |
| s11 | Company announcement | Internal-Comms | Internal-Comms | Internal-Comms | Internal-Comms |
| s12 | Resolved monitoring alert | Alerts | Newsletter | Alerts | Alerts |
| s13 | Signature requested | Action | FYI | Action | Action |
| s14 | Spanish information only | FYI | Newsletter | Newsletter | FYI |
| s15 | FYI with embedded AI instruction | FYI | FYI | FYI | FYI |
| s16 | Approval already recorded | FYI | FYI | Internal-Comms | FYI |

The fixtures are checked in:
[`tools/benchmark/fixtures.json`](../../tools/benchmark/fixtures.json). A perfect result on
these obvious 16 controls is not evidence of perfect production accuracy.

### Same-scope real-mail comparison

| Alias | Laya baseline | Laya concise | Luna | Luna asks for more context |
| --- | --- | --- | --- | --- |
| real-001 | FYI | GitHub-Admin | FYI | No, but score below 0.85 |
| real-002 | FYI | GitHub-Admin | Action | Yes |
| real-003 | Shares | GitHub-Admin | Action | No |
| real-004 | Internal-Comms | Internal-Comms | Action | No |

Baseline tag agreement is **1/4 (25%)** in both repetitions. The concise schema
agrees with Luna on **0/4**. That is **agreement, not real-mail accuracy**:
there are no independently human-reviewed reference labels for these messages.
The sample is not stratified or representative of the full mailbox.

The baseline accepted 1/4 under the illustrative category gate; Luna accepted
2/4. Baseline real-003 had local Shares score 0.9949 while Luna chose Action.
That disagreement cannot be safely resolved by trusting the higher score.

No local or hosted body-context escalation was included in this experiment.
Therefore this table compares first-pass predictions, not final decisions of
the full production pipeline.

### Latency and repeated-run stability

Times are wall-clock seconds for each complete inference call. Local checkpoints
are already loaded; hosted times include CLI startup and its system context.
This compares actual deployment paths, not equivalent bare inference kernels.

| Scope/model | Repeat 1 | Repeat 2 | Mean |
| --- | ---: | ---: | ---: |
| Four real messages, Laya baseline | 0.701 | 0.519 | 0.610 |
| Four real messages, Luna | 13.673 | 12.714 | 13.194 |
| Sixteen controls, Laya baseline | 1.034 | 1.117 | 1.076 |
| Sixteen controls, Luna | 10.867 | 10.916 | 10.892 |
| Four real messages, Laya concise | 0.924 | 0.318 | 0.621 |
| Sixteen controls, Laya concise | 1.007 | 0.667 | 0.837 |

The baseline local path was about 22x faster on the real batch and 10x faster
on the control batch, **after preload**. A scheduled one-shot local process
also pays model/import startup; a persistent service would avoid reloads but
reserve memory. Neither persistent service overhead nor power was measured.

Tag and task-presence decisions were identical across the two repetitions
for each model/scope/schema. This is consistency, not correctness.

## Costs

Reference rates verified from
[GitHub's pricing table](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing)
on 2026-10-07, USD per million tokens for default-context Luna:
input $0.10, cache read $0.01, cache write $0.125, output $0.50.

| Successful main comparison call | Input | Cache read | Cache write | Output | USD reference |
| --- | ---: | ---: | ---: | ---: | ---: |
| Real batch, repeat 1 | 3 | 0 | 18,088 | 816 | $0.002669300 |
| Controls, repeat 1 | 3 | 0 | 17,723 | 688 | $0.002559675 |
| Real batch, repeat 2 | 3 | 0 | 18,089 | 744 | $0.002633425 |
| Controls, repeat 2 | 3 | 0 | 17,721 | 646 | $0.002538425 |
| **Successful comparison subtotal** | | | | | **$0.010400825** |

The first benchmark attempt had four paid hosted calls whose CLI-rendered text
failed JSON parsing. Including those calls, the eight recorded main-benchmark
attempts cost **$0.020817525** at the reference rates. Standalone synthetic
diagnostic probes are not included in that subtotal; their complete usage
exports were not retained. These values are not an invoice or total session cost.

Laya's hosted inference fee was **$0**. It still required the model download,
approximately 1.38 GiB of weights plus dependencies, local compute, and engineering
time. Electricity, power draw and amortized hardware cost were not measured.
Download/preload times do not establish an electricity bill.

Using the main real-batch mean, 264 hypothetical identical calls/month would
represent about **$0.70 of Luna usage**. This is a linear illustration, not
the observed monthly workload; rule/cache-only scans make no model call.

A local filter can save hosted charges only when it safely resolves **all**
items that would otherwise require a hosted batch, or reduces meaningful token
volume. Accepting one of four messages but still sending the other three to
Luna retains most of the CLI startup/cache-write cost. It does not save 25%
of the bill automatically.

Tasks needing titles, contextual notes or explicit deadlines would still need
generative extraction. An uncertain local prediction should fall back to Luna
first, not directly to the 20x-priced strong model. Any adoption evaluation must
include that fallback rate and end-to-end task quality, not local fee alone.

## Reliability finding and applied fix

The existing CLI text output wrapped long task strings at terminal width,
inserting literal newlines inside JSON strings. The first four hosted benchmark
responses therefore failed strict parsing; no decisions were applied.

The runner now requests `--output-format json`, parses the JSONL event stream,
and takes exactly one tool-free `assistant.message` with `phase=final_answer`.
It does not reconstruct malformed JSON, remove arbitrary whitespace, or accept
Markdown-fenced output. Session errors and missing/multiple/tool-using final
messages fail explicitly. Invalid framing is recorded as `invalid_json` usage,
not silently considered a successful classification.

This is a production reliability fix exposed by the benchmark, not a change
to the production model, scheduler or classification policy.

## Validation and artifacts

`python3 -m unittest -q test_triage test_benchmark` passed **47 isolated tests**.
They cover existing scanner/decision safety, structured CLI framing, exact
synthetic reference coverage, disagreement accounting, local adapter shape,
unsupported date extraction, billing calculations and exclusion of mail/task
text from benchmark summaries. No paid inference is performed by these tests.

Private runtime artifacts:

| Artifact | Contents |
| --- | --- |
| `state/benchmark.json` | Main paired runs, classifications, probability distributions, timings, billed-token categories and hashes |
| `state/benchmark-compact.json` | Exploratory local-only concise-schema runs |
| `state/benchmark-framing-failures.json` | Initial failed hosted framing attempts, with successful local measurements |
| `state/benchmark-usage/*.jsonl` | Sanitized usage for successful and failed hosted calls |
| `state/laya-install.json` | Pinned checkpoint revision and initial load timing |

These files are excluded from version control and are not a raw-email dataset.
Both systems received the same frozen source fields, but use different native
representations. The local router is not asked to imitate a chat prompt, and
neither reference labels nor the other model's predictions are given as input.

### Reproduce

Paths were updated after the benchmark moved to `tools/`; the commands are
otherwise as run.

```bash
uv venv --python 3.13 .venv-benchmark
uv pip sync --python .venv-benchmark/bin/python tools/benchmark/requirements.lock
.venv-benchmark/bin/python tools/benchmark.py --prepare

# Downloads finished: local checkpoints load offline; Luna still uses its normal network route.
HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
  .venv-benchmark/bin/python tools/benchmark.py --repeats 2

HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
  .venv-benchmark/bin/python tools/benchmark.py --local-only --schema compact \
  --output state/benchmark-compact.json

python3 -m unittest -q tests.test_triage tests.test_benchmark
```

`--prepare` downloads only the pinned English/multilingual checkpoints, without
reading mail or invoking Luna. The paired benchmark incurs paid Luna calls.
No server or background model service is started.

Fresh benchmark runs use the current pending snapshot, which may differ from
the historical four-message scope; compare the recorded hash/count. The
historical raw real-mail snapshot was deliberately not exported, so it cannot
be recreated solely from the ADR. Controls remain reproducible from the fixture.
An output path is overwritten on a new run; use `--output` with a fresh filename
to preserve historical reports. Hosted usage records are append-only.

## Consequences and reconsideration criteria

Keep zero-token deterministic scans and inexpensive hosted reasoning for the
remaining human mail. The local experiment remains isolated and has no mailbox
mutation code path.

Before reconsidering Laya:

1. Collect independently human-reviewed real-mail labels with consent and safe
   handling, including enough action requests, multilingual mail and negative
   cases to assess false negatives.
2. Develop a compact, task-specific schema or fine-tune on a development split,
   then evaluate on a separate held-out split. Do not present development-sample
   gains as generalization.
3. Calibrate category/action gates per checkpoint and address the emitted
   12-option calibration warning. Explicitly report high-confidence mistakes.
4. Validate a full hybrid pipeline, including title/date extraction, fallbacks,
   latency, memory, electricity and total billable hosted usage.
5. Establish model/runtime approval before production adoption.

No numerical production accuracy target has been inferred from this tiny
experiment. Missing action requests must be the primary risk metric, not overall
accuracy dominated by newsletters.

## Sources consulted

* [Laya README and architecture](https://github.com/NandhaKishorM/laya)
* [Laya official package on PyPI](https://pypi.org/project/laya/)
* [Laya Router API](https://nandhakishorm.github.io/laya/reference/router/)
* [Laya Agent API](https://nandhakishorm.github.io/laya/reference/agent/)
* [Pinned checkpoint repository](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148)
* [GitHub model pricing](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing)
* Local measurements and private evidence files listed above
