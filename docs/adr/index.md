# Architecture decisions

Architecture decision records (ADRs) explain significant choices: the context, the
evidence, what was decided and what would change the decision.

| ADR | Date | Status | Decision |
| --- | --- | --- | --- |
| [0001: Laya versus Luna](0001-laya-vs-luna.md) | 2026-10-07 | Accepted | Keep the deterministic scanner with GPT-6 Luna first pass and selective GPT-6.1 Sol escalation. Do not replace the classifier with zero-shot Laya; keep Laya as a local research benchmark. |

ADR 0001 records a measured local experiment: setup, every synthetic category
outcome, latency, the confidence limitations, costs, the reliability fix it exposed,
and how to reproduce it. Its sample is very small, and it is explicitly not a
conclusion about local models in general.

For a short summary, see [Model routing](../guide/model-routing.md#why-not-a-local-model-adr-0001).
