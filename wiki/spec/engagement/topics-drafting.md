# Engagement Topics And Drafting

Topic matching, trigger selection, runtime prompt assembly, and prompt rules for reply opportunity drafting.

## Topics

Engagement topics define when the app should consider a public reply.

Operator-facing topic guidance has two required parts:

| Field | Question it answers | Stored in MVP |
|---|---|---|
| Conversation target | What kind of conversation are we looking for? | `description`, `trigger_keywords`, and `negative_keywords` |
| Position guidance | What position should we take? | `stance_guidance` |

The UI should present these as two distinct topic-guidance values even if the first implementation
stores the conversation target across the existing description and keyword fields. The conversation
target is used to identify opportunities; the position guidance is used when deciding what a useful
reply would say.

Recommended table: `engagement_topics`

```sql
id                    uuid PRIMARY KEY
name                  text NOT NULL
description           text
stance_guidance       text NOT NULL
trigger_keywords      text[] NOT NULL DEFAULT '{}'
negative_keywords     text[] NOT NULL DEFAULT '{}'
example_good_replies  text[] NOT NULL DEFAULT '{}'
example_bad_replies   text[] NOT NULL DEFAULT '{}'
active                boolean NOT NULL DEFAULT true
created_at            timestamptz NOT NULL DEFAULT now()
updated_at            timestamptz NOT NULL DEFAULT now()
```

Topic guidance should describe the desired conversation and how to be useful inside it, not how to
manipulate the group.

Good guidance:

```text
Conversation target: People comparing open-source CRM tools, asking about CRM migration, or
discussing practical CRM evaluation criteria.

Position guidance: Be factual, brief, and non-salesy. Mention tradeoffs such as setup effort,
integrations, export access, team adoption, and data quality.
```

Bad guidance:

```text
Convince users that our product is best and make it look like the whole group agrees.
```

Validation contract:

- `name` is required and should be unique case-insensitively.
- `stance_guidance` is required.
- Active topics must provide at least one semantic-profile input: `description`, `trigger_keywords`,
  or `example_good_replies`.
- `trigger_keywords` remain useful as a deterministic fallback and negative-audit surface, but they
  are not required for every active topic before semantic selection is enabled.
- Keywords are case-folded and trimmed before storage.
- `example_bad_replies` should be used in prompts as negative examples only.
- Disallowed guidance includes instructions to deceive, impersonate, harass, target individuals,
  generate fake consensus, or evade moderation.

Service contract:

```python
def create_topic(db, *, payload: EngagementTopicCreate) -> EngagementTopicView:
    ...

def update_topic(db, *, topic_id: UUID, payload: EngagementTopicUpdate) -> EngagementTopicView:
    ...

def list_active_topics(db) -> list[EngagementTopic]:
    ...
```

## Detection And Drafting Prompt Rules

The engagement detector may use OpenAI to decide whether a live message sample is a good moment for
a reply and to draft that reply at detection time.

### Instruction Model

The reply-generation agent must be instructed through durable admin configuration, not ad hoc
worker code. The active prompt profile is editable through the engagement bot controls, and every
edit should create an immutable prompt-profile version before activation.

Draft generation should use a lean prompt. The worker assembles the final drafting prompt at runtime from
these layers:

```text
immutable safety floor
  + active prompt profile
  + topic guidance and examples
  + global/account/community/topic style rules
  + community-level summary
  + selected source post or trigger excerpt
  + reply target context, when needed
```

Recent public message batches may be used for opportunity detection, but they should not be dumped
into the draft-generation prompt by default. The runtime prompt should receive only the minimum
context needed to write a focused public reply.

The runtime prompt input is assembled from:

- community identity and description
- topic guidance and examples
- selected source post text
- optional reply-context text from the same thread
- community summary and dominant themes
- active global/account/community/topic style rules
- active prompt profile plus immutable safety floor

The detector stores the model-produced `suggested_reply` and prompt provenance on the candidate.
Operators may then approve it as-is or edit it into `final_reply` before send. The send worker uses
the approved `final_reply`; it does not call OpenAI again.

The operator-facing instruction controls should answer five questions:

| Question | Stored as | Example |
|---|---|---|
| What kind of conversation are we looking for? | topic conversation target, trigger keywords, negative keywords | notice CRM migration discussions; ignore hiring posts |
| What position should it take? | topic `stance_guidance` | be practical, compare tradeoffs, avoid sales pressure |
| How should it sound here? | style rules | brief, transparent, no links unless asked |
| What is allowed to be claimed? | prompt profile and account/community style rules | may say "we maintain a tool"; must not claim to be a customer |
| What should it avoid? | bad examples, validation, and safety floor | no DMs, no urgency, no fake consensus, no personal profiling |

Style rules answer one primary user question: how should this account sound in this community?
They belong in the rendered user prompt alongside topic guidance and examples, not in the immutable
safety floor. Community, account, and topic style rules may make replies shorter, calmer, more
transparent, or more specific to the local discussion.

The editable prompt profile can tune the model's role, reasoning rubric, output format, and tone.
It cannot override hard product rules. If a prompt profile, topic, or style rule conflicts with
reply-only mode, approval requirements, no-DM rules, link validation, or rate limits, backend
validation and worker preflight win.

The generator should behave like a helpful public participant for the configured operator account:

- Reply only when the current discussion already creates a relevant opening.
- Add one useful thought, question, comparison, caveat, or resource.
- Prefer short replies that fit the community's current tone.
- Say nothing when the reply would be generic, promotional, late, or off-topic.
- Never invent personal experience, customer status, moderator authority, affiliation, statistics,
  scarcity, urgency, or consensus.
- Never target a named individual, rank people, or suggest moving the conversation to DMs.
- Avoid links by default; allow links only when the topic or style policy permits them and the
  operator approves the final reply.

Recommended generated reply shape:

```text
1-3 sentences
directly references the public topic being discussed
adds practical value or a clarifying question
does not ask for private contact
does not sound like an advertisement
```

The model must always be allowed to return `should_engage = false`. A "no reply" decision is a
successful outcome when the moment is weak, stale, risky, off-topic, already answered, or too old to
join naturally.

Immutable safety floor:

```text
No DMs.
No fake consensus.
No impersonation.
No auto-send.
```

Other research and product boundaries, such as no person-level scores and no hidden collection
internals, remain enforced by database design, analysis boundaries, validation, and worker preflight
rather than being expanded into a noisy immutable drafting prompt.

Structured output:

```json
{
  "should_engage": true,
  "topic_match": "topic name",
  "reason": "The group is discussing CRM alternatives.",
  "suggested_reply": "Short public reply text.",
  "risk_notes": []
}
```

If `should_engage = false`, the worker should not create a reply opportunity unless the operator
requested a debug trace. A runtime-generated reply opportunity is therefore conditional on both
context quality and model output.

Reply validation rules:

- Maximum 800 characters in MVP.
- No request to DM.
- No claim that the account is a customer, founder, moderator, or ordinary community member unless
  explicitly configured as true for that account.
- No unverifiable statistics.
- No hostile, harassing, or manipulative language.
- No hidden disclosure of collection or analysis internals.
- No links unless the topic policy allows links and the operator approves the final reply.
