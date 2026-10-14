# Rules

`rules.json` is where you teach the assistant your inbox. Anything a rule can
decide is never sent to a model. It is read on every run, so edits take effect on
the next run without reinstalling anything.

`rules.json` is your personal file: `make setup` creates it from
`rules.example.json`, it is excluded from Git, and it is never included in a
shared ZIP. This page explains how rules behave; the field-by-field reference for
`rules.json` and `classifier.json` is [Configuration](../configuration.md).

## Anatomy

```json
{
  "label_prefix": "AI",
  "default_window": "newer_than:7d",
  "sweep_guard": "-is:starred",
  "tasks": {
    "list": "My Tasks",
    "default_due_business_days": 2,
    "max_age_days": 14
  },
  "tags": [
    {
      "name": "Promo",
      "description": "Retail promotions and discount advertising.",
      "match": ["from:shop@deals.example"],
      "on_tag": ["archive", "mark_read"],
      "sweep": [],
      "task": "never",
      "on_task_done": []
    }
  ]
}
```

### Top level

`label_prefix`
:   Prefix of every Gmail label the assistant applies. With `AI`, the tag
    `Meeting/Invite` becomes the label `AI/Meeting/Invite`. Labels are created on
    the first applied run that needs them, including parent labels so they nest.

`default_window`
:   Gmail time filter used for rule matching and for pending mail when no
    `--window` is given. The default `newer_than:7d` means older inbox mail is not
    touched by a normal run.

`sweep_guard`
:   A Gmail query fragment added to every sweep. The default `-is:starred` keeps
    starred mail out of every sweep. It does not apply to `on_tag` or
    `on_task_done` actions.

`tasks`
:   Google Tasks settings: the list name, the default due date, and the maximum age
    of mail that gets an automatic task. See [Tasks](tasks.md).

### A tag

`name`
:   The tag name. The model may only answer with names that exist here.

`description`
:   What belongs in this tag. The model sees these descriptions; they are its only
    definition of your categories. Write them plainly.

`match`
:   A list of Gmail search queries. Anything the query matches in the inbox, within
    the window, gets this tag by rule, without a model.

`on_tag`
:   Actions applied at the moment a message gets this tag, whether by rule or by the
    classifier.

`sweep`
:   A list of `{"when": "<gmail query>", "do": [<actions>]}` entries. On every run,
    inbox mail carrying this tag's label that also matches `when` (and the
    `sweep_guard`) gets the actions.

`task`
:   `always`, `optional` or `never`. See [Tasks](tasks.md#task-policies).

`on_task_done`
:   Actions applied to the thread's inbox messages once its task is completed.

## First match wins

Tags are evaluated in the order they appear in the file. For every tag, each
`match` query is searched as:

```text
in:inbox <window> (<your query>) -label:ai-action -label:ai-alerts ...
```

The exclusions cover every tag, so mail that already has an `AI/*` label is never
re-tagged, and a message matched by an earlier tag in this run is skipped by later
ones. Put specific rules before broad ones. If an early tag has a broad query (for
example a whole domain), it will capture mail you meant for a later tag.

Mail no rule matches becomes pending and goes to the classifier, unless you run
with `--no-model`, in which case it stays untagged in the inbox.

## Actions

| Action | Effect in Gmail |
| --- | --- |
| `archive` | Removes the `INBOX` label. |
| `mark_read` | Removes the `UNREAD` label. |
| `star` | Adds the `STARRED` label. |
| `important` | Adds the `IMPORTANT` label. |
| `trash` | Moves the message to Gmail Trash. Opt-in only. |

An unknown action name stops the run with an error listing the allowed ones.

!!! warning "`trash` is opt-in"
    `trash` is never in the starter rules and is used only where you write it. Gmail
    keeps trashed mail for 30 days, and trash operations are journaled, so
    `triage.py undo` can restore them. Nothing is ever permanently deleted. A task
    in a hand-written decisions file can narrow a tag's completion actions, but
    never add `trash`; the classifier cannot set completion actions at all.

## Worked example: the demo rules

The [demo](../getting-started/demo.md) uses this ruleset (from
`demo/demo_mailbox.py`) on an invented mailbox. Descriptions are shortened here.

| Tag | `match` | `on_tag` | `sweep` | `task` | `on_task_done` |
| --- | --- | --- | --- | --- | --- |
| Action | | | | always | `archive` |
| Alerts | `from:status@monitor.example` | | `subject:RESOLVED` → archive, mark_read | optional | |
| GitHub-Admin | `from:notifications@code.example` | | `older_than:1d` → archive, mark_read | optional | |
| Meeting/Invite | `from:calendar@harbor.example` | | | never | |
| Meeting/Notes | `from:notes-bot@meet.example` | | | optional | |
| Shares | `from:drive-shares@docs.example` | | | optional | |
| Admin | `from:receipts@travel.example OR from:billing@cloud.example OR from:payroll@harbor.example` | | | optional | |
| Internal-Comms | `from:all-hands@harbor.example` | | | optional | |
| Newsletter | `from:hello@weeklybyte.example OR from:digest@productnotes.example OR from:hello@designsystems.example` | | `older_than:1d` → archive, mark_read | never | |
| Promo | `from:shop@deals.example` | archive, mark_read | | never | |
| FYI | | | | optional | |
| Backlog | | | | never | |

The same tags as JSON, for three of them:

```json
[
{"name": "Alerts", "description": "Monitoring incidents, outages, security and expiry warnings.",
 "match": ["from:status@monitor.example"], "on_tag": [],
 "sweep": [{"when": "subject:RESOLVED", "do": ["archive", "mark_read"]}],
 "task": "optional", "on_task_done": []},
{"name": "Promo", "description": "Retail promotions and discount advertising.",
 "match": ["from:shop@deals.example"], "on_tag": ["archive", "mark_read"],
 "sweep": [], "task": "never", "on_task_done": []},
{"name": "Action", "description": "A human requests a reply, decision, approval, signature or commitment.",
 "match": [], "on_tag": [], "sweep": [], "task": "always", "on_task_done": ["archive"]}
]
```

What happened in the demo run on the invented mailbox:

- **Rules tagged 27 of the 37 messages in the window** without a model: alerts,
  code-review notifications, invitations, the notes bot, document shares,
  receipts and invoices, internal announcements, known newsletters and promotions.
- **Promotions** were archived and marked read the moment they were tagged
  (`on_tag`).
- **Alerts** stayed in the inbox while firing; the `[RESOLVED]` notification was
  swept out.
- **Code-review notifications and newsletters** older than a day were swept;
  recent ones stayed visible.
- **A starred newsletter** older than a day stayed in the inbox, because the
  `sweep_guard` `-is:starred` excludes it from every sweep.
- **Human mail** (`Action`, `FYI`, and the meeting notes a colleague wrote by
  hand) has no `match` queries, so it went to the classifier. The notes from the
  bot were matched by rule; the notes from a person were classified as
  `Meeting/Notes` by the model.
- **A newsletter sender no rule knew** (`events@summit.example`, three messages)
  was classified as `Newsletter` and listed in `state/summary.json` as a rule
  candidate. Its older messages were then swept by the `Newsletter` sweep in the
  same run.
- **A 12-day-old message** was outside `newer_than:7d` and was not touched.
- **Completing the `Action` task** "Approve the Q4 hiring plan" archived its
  thread on the next run (`on_task_done: ["archive"]`). The message stays unread,
  because only `archive` is configured.

## Writing good rules

- Prefer exact senders (`from:alerts@vendor.example`) over domains. The
  [`mail-setup`](#sender-rules-from-mail-setup) skill only ever proposes exact
  senders.
- Keep `Action` and `FYI` free of `match` queries unless you are sure. Whether a
  person is asking you for something is exactly what rules cannot see.
- Add cleanup (`on_tag`, `sweep`) only for mail you would never want to miss in
  the inbox, and preview with a dry run first.
- Use `older_than:` in sweeps so recent notifications stay visible for a while.
- Watch `rule_candidates` in `state/summary.json`: any bulk sender that appeared
  at least three times in a pending batch is listed there, with the tag the model
  gave it. The runner never edits `rules.json` itself.

Changing `rules.json` invalidates the current pending batch and the
classification cache, because both are tied to a hash of the rules. A model-free
preview (`make preview`) shows the effect of a change.

## Sender rules from `mail-setup`

The starter rules have no sender queries, so at first every message goes to the
classifier. The `mail-setup` skill proposes exact-sender rules for the automated
mail you receive regularly. How to run it, in Copilot or Claude Code, is in
[Getting started](../getting-started.md#4-personalize-your-rules-mail-setup).
This section adds what the scripts check along the way.

**Discovery** (`make discover`, `python3 mail_setup.py discover`) searches received
mail from the last 30 days, excluding sent, drafts, spam and trash, up to 200
messages. For each one it fetches only the From, Subject, Date, List-Id,
List-Unsubscribe and Precedence headers and Gmail's snippet. It groups messages by
exact sender address, keeps senders with at least three messages (up to 20 groups
by default), and sets aside up to three development and two validation examples
per group. A group is **eligible** only if every sampled message from that sender
has bulk or mailing-list headers and both example sets are complete. The result
goes to the private `state/setup-discovery.json`.

**Preview** (`make rules-preview`) writes the proposed ruleset to
`state/setup-rules.preview.json` and prints the changes; `rules.json` is not
touched.

**Approval** (`python3 mail_setup.py approve --apply`) saves the rules only if:

- the discovery is less than 24 hours old and was made with the current rules;
- every selected group is eligible;
- every development and validation example was given the selected tag;
- the tag is not `Action`, `FYI` or `Backlog`;
- the exact query does not already exist under a different tag.

It then backs up the previous rules to a private
`state/rules.before-setup-<id>.json` and saves `rules.json` with the new
`from:address` queries appended to each tag's `match` list. It cannot add cleanup
actions or domain-wide queries.

!!! warning "New rules inherit existing cleanup"
    On the starter rules no cleanup is enabled, so a new rule only tags mail. If
    you have already added `on_tag` or `sweep` actions to a tag, a new sender query
    under that tag inherits them on the next applied run. Review those before
    approving.

The validator rejects only exact duplicates. A broader, earlier query (for example
a domain-wide one you wrote yourself) can still capture the sender first, because
[the first match wins](#first-match-wins).
