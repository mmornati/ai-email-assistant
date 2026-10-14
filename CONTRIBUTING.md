# Contributing

Thanks for helping! A few ground rules keep this project safe for people's inboxes.

## Development

- Python 3.10+, standard library only for the runtime. Benchmark dependencies
  stay isolated in `requirements-benchmark.*`.
- Run the offline test suite before opening a pull request:

  ```bash
  python3 -m unittest discover -s tests -t .
  shellcheck scripts/*.sh
  ```

  Tests must never touch a real mailbox, Google Tasks, or a paid model: mock
  `triage.gws` and `runner.call_model`.

## Rules for changes

- **Never commit real mail data.** Use `example.invalid` addresses and synthetic
  subjects in fixtures. `state/` and `rules.json` are git-ignored on purpose.
- Keep every mailbox mutation behind `--apply` and recorded in the journal.
- Do not add actions that send, forward, unsubscribe or permanently delete mail.
- Treat any new model output as untrusted: validate its shape and values
  before use, and add a test that malformed output fails closed.
- Keep `rules.example.json` free of sender-specific queries and cleanup actions
  (enforced by `tests/test_share.py`).
