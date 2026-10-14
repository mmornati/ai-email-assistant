"""The invented mailbox and ruleset used by the demo.

Every person, company, address and message here is fictional. Domains use the reserved `.example`
top-level domain so nothing can resolve. `hours` is the message age when the demo starts; the
`model` block is what the stand-in classifier answers for messages that reach it.
"""
from __future__ import annotations

OWNER = "Sam Rivera <sam@harbor.example>"

# (hours ago, sender, subject, snippet, extras)
# extras: list=True adds List-Unsubscribe; starred/unread flags; body for escalations; model answers.
MESSAGES = [
    # --- people asking for something: no rule can know, so the model reads them
    dict(hours=2, sender="Priya Nair <priya@harbor.example>",
         subject="Q4 hiring plan: need your sign-off by Thursday",
         snippet="Hi Sam, the Q4 plan is final on our side. Can you approve the two senior roles before Thursday so "
                 "recruiting can open them on Friday?",
         model={"luna": {"tag": "Action", "task": {"title": "Approve the Q4 hiring plan (two senior roles)",
                                                    "notes": "Priya needs sign-off so recruiting can open the roles "
                                                             "on Friday.", "due_in": 2},
                         "confidence": 0.96, "needs_context": False}}),
    dict(hours=5, sender="Jonas Weber <jonas.weber@client.example>",
         subject="Re: renewal",
         snippet="Thanks for the call. Attached is the version legal is happy with, see my note on clause 7.",
         body="Hi Sam,\n\nThanks for the call. Attached is the version legal is happy with. The only change is clause 7 "
              "(notice period 60 days instead of 90). Could you confirm you accept the revised terms by the 24th, so "
              "we can countersign before the end of the month?\n\nBest,\nJonas",
         model={"luna": {"tag": "Action", "task": None, "confidence": 0.62, "needs_context": True},
                "sol": {"tag": "Action", "task": {"title": "Confirm the revised renewal terms to Jonas (clause 7)",
                                                   "notes": "Notice period moves from 90 to 60 days. Jonas wants a "
                                                            "confirmation so both sides can countersign.",
                                                   "due_in": 4},
                        "confidence": 0.94, "needs_context": False}}),
    dict(hours=7, sender="Léa Dubois <lea@harbor.example>",
         subject="Onboarding deck for Monday",
         snippet="Could you review the onboarding deck before Monday's call? Mostly slides 4 to 9, the pricing part.",
         model={"luna": {"tag": "Action", "task": {"title": "Review the onboarding deck (slides 4-9) before Monday",
                                                    "notes": "Léa asks for a review of the pricing slides.",
                                                    "due_in": 3},
                         "confidence": 0.93, "needs_context": False}}),
    dict(hours=9, sender="Tom Okafor <tom@partner.example>",
         subject="quick one",
         snippet="Hey Sam, saw the new tiers on the site. One thing I could not work out from the page",
         body="Hey Sam,\n\nSaw the new tiers on the site. One thing I could not work out from the page: does the Team "
              "plan include API access, or is that Business only? We need to know before we pitch it to our board "
              "next week.\n\nCheers, Tom",
         model={"luna": {"tag": "FYI", "task": None, "confidence": 0.55, "needs_context": True},
                "sol": {"tag": "Action", "task": {"title": "Tell Tom whether the Team plan includes API access",
                                                   "notes": "He needs the answer before his board pitch next week."},
                        "confidence": 0.91, "needs_context": False}}),
    dict(hours=11, sender="Marta Silva <marta@harbor.example>",
         subject="Notes from the vendor call",
         snippet="Sharing my notes from today's call with the logistics vendor: pricing holds, SLA moves to 99.9, "
                 "next check-in in two weeks.",
         model={"luna": {"tag": "Meeting/Notes", "task": None, "confidence": 0.92, "needs_context": False}}),
    dict(hours=20, sender="Ana Costa <ana@harbor.example>",
         subject="Friday?",
         snippet="Are you around on Friday?",
         body="Are you around on Friday?",
         model={"luna": {"tag": "FYI", "task": None, "confidence": 0.41, "needs_context": True},
                "sol": {"tag": "FYI", "task": None, "confidence": 0.58, "needs_context": True}}),
    dict(hours=26, sender="Daniel Kim <daniel@harbor.example>",
         subject="Moved the launch retro to the 3rd floor",
         snippet="Small change: the launch retro is now in Room 3B, same time. No action needed.",
         model={"luna": {"tag": "FYI", "task": None, "confidence": 0.95, "needs_context": False}}),
    # --- a bulk sender no rule knows yet: classified, and proposed as a rule candidate
    dict(hours=4, sender="Summit Events <events@summit.example>", list=True,
         subject="Webinar: shipping AI features safely (Oct 28)",
         snippet="Join our panel on guardrails, evaluation and rollout. Free, 45 minutes.",
         model={"luna": {"tag": "Newsletter", "task": None, "confidence": 0.97, "needs_context": False}}),
    dict(hours=30, sender="Summit Events <events@summit.example>", list=True,
         subject="Last seats: the platform engineering roundtable",
         snippet="A few seats are left for Thursday's roundtable.",
         model={"luna": {"tag": "Newsletter", "task": None, "confidence": 0.96, "needs_context": False}}),
    dict(hours=50, sender="Summit Events <events@summit.example>", list=True,
         subject="Your weekly events digest",
         snippet="Five events picked for you this week.",
         model={"luna": {"tag": "Newsletter", "task": None, "confidence": 0.97, "needs_context": False}}),
    # --- rule-matched traffic: tagged by plain code, never sent to a model
    dict(hours=1, sender="Calendar <calendar@harbor.example>",
         subject="Invitation: Pricing review @ Wed 10:00", snippet="Priya Nair has invited you to Pricing review."),
    dict(hours=3, sender="Calendar <calendar@harbor.example>",
         subject="Updated invitation: 1:1 Sam / Léa @ Thu 15:00", snippet="This event has been updated."),
    dict(hours=14, sender="Calendar <calendar@harbor.example>",
         subject="Accepted: Launch retro @ Fri 11:00", snippet="Daniel Kim has accepted this invitation."),
    dict(hours=40, sender="Calendar <calendar@harbor.example>",
         subject="Invitation: Quarterly planning @ Mon 09:30", snippet="Marta Silva has invited you."),
    dict(hours=2, sender="Code Review <notifications@code.example>", list=True,
         subject="[harbor/api] Review requested: Rate-limit the export endpoint (#482)",
         snippet="Léa requested your review on this pull request."),
    dict(hours=6, sender="Code Review <notifications@code.example>", list=True,
         subject="[harbor/api] CI failed on main", snippet="The workflow run failed for commit 3fe1c09."),
    dict(hours=29, sender="Code Review <notifications@code.example>", list=True,
         subject="[harbor/web] Merged: New pricing page (#311)", snippet="Pull request merged by Daniel Kim."),
    dict(hours=33, sender="Code Review <notifications@code.example>", list=True,
         subject="[harbor/api] Dependabot: bump urllib3", snippet="Bumps urllib3 to the latest patch."),
    dict(hours=55, sender="Code Review <notifications@code.example>", list=True,
         subject="[harbor/infra] Issue closed: flaky deploy step", snippet="Closed as completed."),
    dict(hours=3, sender="Status <status@monitor.example>",
         subject="[FIRING] api p95 latency above 800 ms", snippet="Alert started 09:12. Region eu-west."),
    dict(hours=2, sender="Status <status@monitor.example>",
         subject="[RESOLVED] api p95 latency above 800 ms", snippet="Alert resolved after 41 minutes."),
    dict(hours=60, sender="Status <status@monitor.example>",
         subject="Certificate for status.harbor.example expires in 14 days", snippet="Renew before the 31st."),
    dict(hours=8, sender="Docs <drive-shares@docs.example>",
         subject="Priya Nair shared \"Q4 Plan\" with you", snippet="Priya Nair has invited you to edit."),
    dict(hours=27, sender="Docs <drive-shares@docs.example>",
         subject="Léa Dubois commented on \"Onboarding deck\"", snippet="\"Can we simplify slide 6?\""),
    dict(hours=12, sender="Travel desk <receipts@travel.example>",
         subject="Your receipt: train to Lyon", snippet="Booking HX42 confirmed. Total paid on the company card."),
    dict(hours=36, sender="Cloud Billing <billing@cloud.example>",
         subject="Invoice for September is available", snippet="Your invoice is ready to download."),
    dict(hours=48, sender="Payroll <payroll@harbor.example>",
         subject="Your October payslip is available", snippet="Log in to the HR portal to view it."),
    dict(hours=10, sender="Harbor All-Hands <all-hands@harbor.example>", list=True,
         subject="This week at Harbor: offsite dates, new parental leave policy", snippet="Three things to know."),
    dict(hours=58, sender="Harbor All-Hands <all-hands@harbor.example>", list=True,
         subject="Office closed on the 1st", snippet="The office will be closed for the public holiday."),
    dict(hours=13, sender="The Weekly Byte <hello@weeklybyte.example>", list=True,
         subject="The Weekly Byte #212: smaller models, bigger wins", snippet="This week: distillation in practice."),
    dict(hours=37, sender="Product Notes <digest@productnotes.example>", list=True,
         subject="Product Notes: onboarding teardown", snippet="We looked at twenty onboarding flows."),
    dict(hours=61, sender="Design Systems Weekly <hello@designsystems.example>", list=True,
         subject="Tokens, themes and dark mode", snippet="A field guide to theming at scale."),
    dict(hours=84, sender="The Weekly Byte <hello@weeklybyte.example>", list=True, starred=True,
         subject="The Weekly Byte #211: the evaluation issue", snippet="The issue everyone forwarded."),
    dict(hours=4, sender="Deals <shop@deals.example>", list=True,
         subject="48h only: 30% off everything", snippet="Our biggest sale of the season."),
    dict(hours=28, sender="Deals <shop@deals.example>", list=True,
         subject="Your cart misses you", snippet="Complete your order today."),
    dict(hours=52, sender="Deals <shop@deals.example>", list=True,
         subject="New arrivals picked for you", snippet="Fresh styles just landed."),
    dict(hours=15, sender="Meeting Notes <notes-bot@meet.example>",
         subject="Summary: Weekly product sync", snippet="Decisions: ship the pricing page Tuesday."),
    # --- outside the default 7-day window: never touched by a scheduled run
    dict(hours=24 * 12, sender="Old Thread <someone@elsewhere.example>",
         subject="Lunch next month?", snippet="Old mail stays where it is."),
]


def tag(name, description, task, match=(), on_tag=(), sweep=(), on_task_done=()):
    return {"name": name, "description": description, "match": list(match), "on_tag": list(on_tag),
            "sweep": list(sweep), "task": task, "on_task_done": list(on_task_done)}


RULES = {
    "label_prefix": "AI",
    "default_window": "newer_than:7d",
    "sweep_guard": "-is:starred",
    "tasks": {"list": "My Tasks", "default_due_business_days": 2, "max_age_days": 14},
    "tags": [
        tag("Action", "A human requests a reply, decision, approval, signature or commitment.", "always",
            on_task_done=["archive"]),
        tag("Alerts", "Monitoring incidents, outages, security and expiry warnings.", "optional",
            match=["from:status@monitor.example"],
            sweep=[{"when": "subject:RESOLVED", "do": ["archive", "mark_read"]}]),
        tag("GitHub-Admin", "Repository administration, pull request and issue notifications.", "optional",
            match=["from:notifications@code.example"],
            sweep=[{"when": "older_than:1d", "do": ["archive", "mark_read"]}]),
        tag("Meeting/Invite", "Calendar invitations, updates and RSVPs.", "never",
            match=["from:calendar@harbor.example"]),
        tag("Meeting/Notes", "Meeting summaries, notes and preparation.", "optional",
            match=["from:notes-bot@meet.example"]),
        tag("Shares", "Documents shared with the recipient, document comments and collaboration notifications.",
            "optional", match=["from:drive-shares@docs.example"]),
        tag("Admin", "HR, travel, invoices, receipts and administrative information.", "optional",
            match=["from:receipts@travel.example OR from:billing@cloud.example OR from:payroll@harbor.example"]),
        tag("Internal-Comms", "Company-wide announcements and internal mailing lists.", "optional",
            match=["from:all-hands@harbor.example"]),
        tag("Newsletter", "Newsletters, webinars and vendor marketing.", "never",
            match=["from:hello@weeklybyte.example OR from:digest@productnotes.example "
                   "OR from:hello@designsystems.example"],
            sweep=[{"when": "older_than:1d", "do": ["archive", "mark_read"]}]),
        tag("Promo", "Retail promotions and discount advertising.", "never",
            match=["from:shop@deals.example"], on_tag=["archive", "mark_read"]),
        tag("FYI", "Informational human mail with no request to act.", "optional"),
        tag("Backlog", "Old mail explicitly selected for backlog review; do not infer age without a date.", "never"),
    ],
}
