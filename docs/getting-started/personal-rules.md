# Personal rules with `mail-setup`

The starter `rules.json` has twelve tags and no sender queries, so out of the box
every message goes to the classifier. The `mail-setup` skill helps you add
exact-sender rules for the automated mail you receive regularly. Every message a
rule recognizes is tagged by plain code and never sent to a model.

The skill learns configuration, not model weights. No model training or local
model is involved.

## Ask Copilot

Open the project folder as a local, folder-backed project in Copilot and ask:

> Use the mail-setup skill to inspect my mailbox read-only, propose personalized
> rules, and ask before saving them. Do not modify mail or create tasks.

The skill drives `mail_setup.py` through three commands, and asks you before the
last one.

```bash
python3 mail_setup.py discover
python3 mail_setup.py preview            # after the skill writes setup-selections.json
python3 mail_setup.py approve --apply    # only after you approve the displayed rules
```

## 1. Discover

`discover` reads at most **200 received messages from the last 30 days**,
including archived mail (it excludes sent, drafts, spam and trash). For each
message it fetches only selected headers (From, Subject, Date, List-Id,
List-Unsubscribe, Precedence) and a short snippet. No bodies, no attachments, no
model calls, no mailbox changes.

It groups messages by exact sender address and keeps up to 20 groups with at
least three messages. For each group it sets aside up to three "development"
examples and two separate "validation" examples. A group is **eligible** for an
automated-sender rule only if every sampled message from that sender carries
bulk or mailing-list headers and both example sets are complete (in practice, at
least six sampled messages from that address).

The result goes to `state/setup-discovery.json`, which stays private.

You can widen the bounds explicitly, up to hard caps:

```bash
python3 mail_setup.py discover --limit 500 --days 90 --max-groups 50
```

These are caps, not a request to read the whole mailbox.

## 2. Review and preview

The skill reads the development examples of each eligible group and classifies
them from your tag descriptions, then judges the validation examples separately.
It rejects groups with requests to reply, approve or sign, mixed purposes, weak
evidence, conflicting categories, or text that tries to instruct an AI. Human
senders without bulk headers are left for per-message classification.

For defensible candidates it writes `state/setup-selections.json` and runs
`preview`, which writes the proposed ruleset to `state/setup-rules.preview.json`
and prints the changes without touching `rules.json`. The skill should show you
the proposed sender queries, the tag, the observed message count, and any
disagreements or rejected candidates, then ask you to approve those exact changes.

An empty selection is a valid outcome. If nothing qualifies, keeping the starter
rules is fine; run discovery again as mail accumulates.

## 3. Approve

`approve --apply` saves the rules only if all of these hold:

- the discovery is less than 24 hours old and was made with the current rules;
- every selected group is eligible;
- every development and validation example was independently given the selected tag;
- the tag is not `Action`, `FYI` or `Backlog`;
- the exact query does not already exist under a different tag.

It then backs up your previous rules to a private
`state/rules.before-setup-<id>.json` and atomically saves `rules.json` with the new
`from:address` queries appended to each tag's `match` list. Existing exact queries
are not duplicated.

What it **cannot** do: add cleanup actions (archive, mark read, trash), add
domain-wide or wildcard queries, or add rules for `Action`, `FYI` or `Backlog`.

!!! warning "New rules inherit existing cleanup"
    On the starter rules no cleanup is enabled, so a new rule only tags mail. If
    you have already added `on_tag` or `sweep` actions to a tag, a new sender query
    under that tag inherits them on the next applied run. Review those before
    approving.

!!! note "First match wins"
    The validator rejects only exact duplicates. A broader, earlier query (for
    example a domain-wide one you wrote yourself) can still capture the sender
    first. Check precedence by eye. See [Rules](../guide/rules.md#first-match-wins).

Changed rules invalidate earlier pending batches and the classification cache. A
model-free preview shows the effect:

```bash
python3 runner.py --no-model
```

## Limits worth knowing

This is a bounded recent sample, not a random sample, not a human-labeled
accuracy test, and not a guarantee about future mail. Bulk headers alone do not
prove a sender is safe to auto-tag; that is why the examples are reviewed. The
skill does not enable classification, mailbox changes or scheduling.

## Adding rules by hand

You can also edit `rules.json` yourself: add Gmail search queries to a tag's
`match` list, in tag priority order. The runner also suggests candidates: any bulk
sender seen at least three times in a pending batch appears under
`rule_candidates` in `state/summary.json`. The runner never edits `rules.json`
itself. See [Rules](../guide/rules.md).
