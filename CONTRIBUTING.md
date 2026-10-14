# Contributing

Thanks for helping! A few ground rules keep this project safe for people's inboxes.

## Development

- Python 3.10+, standard library only for the runtime. Benchmark dependencies
  stay isolated in `tools/benchmark/requirements.*`.
- Run the offline test suite before opening a pull request:

  ```bash
  make test   # python3 -m unittest discover -s tests -t .
  make lint   # shellcheck scripts/*.sh and byte-compile
  ```

  Tests must never touch a real mailbox, Google Tasks, or a paid model: mock
  `triage.gws` and `runner.call_model`.
- New files that should ship in the shared ZIP go in the `FILES` allowlist in
  `tools/share.py`; user-facing guides live in `docs/` and are linked from
  `docs/README.md`.

## Where things live

| Path | Contents |
| --- | --- |
| `*.py` (top level) | CLI entry points; their paths are referenced by installed schedules and skills, so keep them there |
| `scripts/` | Shell installer and health check |
| `tools/` | Maintainer tooling: ZIP packager, optional benchmark |
| `docs/` | Guides, assets and architecture decision records (`docs/adr/`) |
| `.github/skills/` | Copilot skills shipped with the project |

## Rules for changes

- **Never commit real mail data.** Use `example.invalid` addresses and synthetic
  subjects in fixtures. `state/` and `rules.json` are git-ignored on purpose.
- Keep every mailbox mutation behind `--apply` and recorded in the journal.
- Do not add actions that send, forward, unsubscribe or permanently delete mail.
- Treat any new model output as untrusted: validate its shape and values
  before use, and add a test that malformed output fails closed.
- Keep `rules.example.json` free of sender-specific queries and cleanup actions
  (enforced by `tests/test_share.py`).
