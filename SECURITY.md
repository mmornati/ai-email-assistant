# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's
[private vulnerability reporting](../../security/advisories/new) for this
repository. Include steps to reproduce and the affected version or commit.
You should receive a response within a week.

**Never include real email content, Gmail IDs, OAuth tokens or files from
`state/` in a report.** Reproduce with synthetic data instead.

## Security model

- **Email is untrusted input.** The classifier prompt treats every field as data;
  model output is strictly validated (exact message IDs, known tags, bounded task
  fields, no action overrides) before anything is applied.
- **Dry run by default.** Every mailbox-mutating command needs `--apply`.
- **Bounded actions.** Labels, archive, mark read, star, important, and opt-in
  `trash` (recoverable, journaled, undoable). Nothing is sent, forwarded,
  unsubscribed or permanently deleted.
- **Least privilege.** `scripts/setup-macos.sh` requests only the
  `gmail.modify` and `tasks` OAuth scopes.
- **Isolated model calls.** The Copilot CLI runs tool-free, in a temporary
  directory, with custom instructions, MCP servers and remote export disabled;
  mail goes through stdin, not the process argument list. Custom provider
  overrides are refused.
- **Private local state.** `state/` is created owner-only (`0700`, files `0600`)
  and is excluded from Git and from `tools/share.py` bundles. It is **not encrypted**;
  rely on FileVault and a protected account.

## Known limitations

- Gmail queries and task titles are passed to the `gws` CLI as command-line
  arguments, so other local users could see them in the process list while a
  call runs. Use a single-user machine.
- Model-reported confidence is not a calibrated probability.
- Data sent to Copilot is subject to GitHub's and the model provider's
  retention policies.
