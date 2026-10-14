# Guide

How AI E-Mail Assistant works and how to shape it to your inbox.

[How it works](how-it-works.md)
:   The pipeline, station by station, from the scheduled tick to the summary.

[Rules](rules.md)
:   `rules.json`: tags, Gmail queries, first-match precedence, actions and sweeps,
    with a worked example.

[Model routing](model-routing.md)
:   `classifier.json`: the cheap model, escalation, thresholds, caching, isolation of
    the Copilot call, and how to read your usage.

[Tasks](tasks.md)
:   How mail becomes Google Tasks, how duplicates are avoided, and how completing a
    task tidies its thread.

[Schedule](schedule.md)
:   The macOS launchd job: install, timing, logs, and the app-automation
    alternative.

[Manual review](review.md)
:   Resolving what the model left for you with the `mail-triage` skill, a decisions
    file and a replayable plan.

[Safety](safety.md)
:   Dry runs, validation, rechecks, the journal and undo, private state, and how
    email content is treated as untrusted.

[Sharing](sharing.md)
:   Building a clean ZIP for a colleague, and what they need to do with it.
