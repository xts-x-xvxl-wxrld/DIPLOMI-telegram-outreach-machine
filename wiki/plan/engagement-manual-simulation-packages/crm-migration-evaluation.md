# CRM Migration Evaluation Package

## Goal

Use this package to manually configure one engagement around CRM migration
conversations, then test whether the system spots useful public reply openings
without sounding salesy.

## Topic Wizard Copy

### Wizard Step Order

Use this package in the current topic-brief flow order:

1. Topic name
2. Conversation target
3. Trigger keywords
4. Negative keywords
5. Position guidance
6. Voice / style
7. Good reply examples
8. Bad reply examples
9. Avoid rules / review

### Topic Name

`CRM migration evaluation`

### Conversation Target

```text
People comparing CRM tools, planning CRM migrations, or discussing migration
risks such as exports, custom fields, notes, activity history, integrations,
reporting continuity, onboarding friction, and rollout timing.
```

### Trigger Keywords

```text
crm migration, migrate crm, crm switch, crm export, crm imports, custom fields,
activity history, salesforce migration, hubspot migration, pipedrive migration,
reporting continuity, crm rollout, crm evaluation, compare crms, switching crm
```

### Negative Keywords

```text
job post, hiring, discount code, promo code, meme, shitpost, giveaway, agency
pitch, dm me, personal mobile numbers, cold email copywriter, wifi, router, pm
tool, sprint planning
```

### Position Guidance

```text
Be practical, calm, and useful. Focus on export completeness, field mapping,
data cleanup, integration effort, reporting continuity, team adoption, and the
real workload of switching. Add one useful comparison point or one clarifying
question when there is a natural opening. Do not hard-sell, do not exaggerate,
and do not claim personal customer experience.
```

### Voice / Style

```text
Neutral, short, informed, slightly conversational. No hype. No links unless
someone directly asks for one. Prefer 1 to 3 sentences.
```

### Good Reply Examples

```text
I would compare export completeness and custom field mapping before anything
else. Those two usually tell you how painful the real migration will be.
```

```text
One useful check is whether activity history and notes survive the move cleanly.
Teams often discover the real migration cost there, not in the feature list.
```

```text
If you are narrowing vendors, I would look at reporting continuity, integration
rebuild effort, and how much cleanup the team needs after import.
```

### Bad Reply Examples

```text
We solved this perfectly, just switch now and you will be fine.
```

```text
DM me and I will show you the best CRM for this.
```

```text
Our product is clearly the winner and everyone here eventually picks it.
```

### Avoid Rules

```text
No DMs.
No fake consensus.
No pretending to be a customer.
No urgency or pressure.
No links unless directly requested.
No generic "book a demo" language.
```

## Engagement Wizard Copy

### Engagement Name

`CRM migration conversations`

### Community Target Guidance

```text
Use this package in founder, revops, sales-ops, CRM, or B2B operations
Telegram groups where people regularly compare tools or discuss migration work.
```

### Topic To Choose

`CRM migration evaluation`

### Recommended Mode

`Draft`

### Operator Note

```text
This engagement is for public conversations about replacing or evaluating CRM
tools. It should engage on real migration questions, comparison requests, or
practical pain points. It should skip job posts, memes, discounts, promo bait,
and unrelated operations threads.
```

## Should Trigger

Use these as sample incoming messages that should create a likely engagement
opening.

```text
We are replacing our CRM this month and the main fear is losing notes and
custom fields. What would you compare first?
```

```text
For teams that migrated CRMs recently, what was harder in real life: exports,
integrations, or user adoption?
```

```text
We keep getting impressed by demos, but I mostly care about how cleanly we can
leave later. Anyone compare tools that way?
```

```text
Switched CRMs last quarter and honestly the winner was just the one with less
messy exports. Fancy features mattered less than clean migration.
```

```text
What criteria would you use to compare CRM pricing against the actual migration
work a small ops team has to absorb?
```

```text
Anyone have a good checklist for testing whether activity history and notes
survive a CRM move?
```

```text
We are shortlisting CRMs and I do not trust feature grids anymore. Which
migration red flags show up too late for most teams?
```

```text
Past happy customer of our current stack here, but migration still hurt more
than expected. Curious what people would validate earlier next time.
```

## Should Not Trigger

Use these as sample incoming messages that should be skipped or rejected.

```text
Hiring a revops manager in Berlin. DM if interested.
```

```text
Anyone have a discount code for a CRM annual plan this week?
```

```text
Current pipeline mood: one spreadsheet, three tabs, zero hope.
```

```text
Looking for a cold email copywriter, referrals welcome.
```

```text
Drop your SaaS here and I will review all of them live later.
```

```text
Which PM tool should I use for sprint planning?
```

```text
Need a founder list with personal mobile numbers by tonight.
```

```text
Our office wifi is dying again, recommend a router.
```

## Operator Review Notes

### Approve

- the message is clearly about CRM migration, evaluation, exports, cleanup, or
  rollout risk
- the draft adds one practical point or one clarifying question
- the draft sounds natural and not promotional

### Edit

- the topic match is real, but the draft is too generic
- the draft is useful but slightly too polished, too long, or too conversion-led
- the reply should be softened into a more public-discussion tone

### Reject

- the message is off-topic, spammy, or privacy-sensitive
- the opening is too weak to join naturally
- the draft sounds like a pitch instead of a contribution
