# Getting started

Four short steps take you from nothing to a reviewed first run. None of them
changes your mailbox until you deliberately pass `--apply`.

1. **[Try the demo](demo.md).** Run the real engine on an invented mailbox. No Google
   account, no Copilot account, no model calls. About a minute.
2. **[Install](install.md).** One script installs the command-line tools with
   Homebrew, creates private local files, signs you in, and verifies the install.
3. **[First run](first-run.md).** Run the tests, preview what the rules would do
   without a model, preview with classification, read the results, then apply.
4. **[Personal rules](personal-rules.md).** Let the `mail-setup` skill look at a
   bounded recent sample of your mail and propose exact-sender rules for you to
   approve. More rules means fewer model calls.

When you are happy with manual runs, [install the schedule](../guide/schedule.md).

## What you need

- A Mac with [Homebrew](https://brew.sh). The setup script installs Python 3.10+ if
  your system only has the Python 3.9 that ships with macOS.
- A Gmail account, and the ability to create or reuse an OAuth client in a Google
  Cloud project, within your organization's OAuth policy.
- A GitHub Copilot account with access to the two models in `classifier.json`, if
  you want classification. Without it, the rules still work: see
  [Can I run it without a model?](../faq.md#can-i-run-it-without-a-model)
- Comfort pasting a few commands into Terminal.

!!! note "Nothing is installed in the background"
    The setup script never modifies mail, never passes `--apply`, and never installs
    the hourly schedule. Each of those is a separate, explicit step.
