# Engagement Lifecycle Contract

Detailed lifecycle terminology, status values, and cross-cutting invariants for engagement.

## Terminology

Operator-facing engagement language should use **reply opportunity**, not `candidate`. A reply
opportunity is a time-sensitive opening to answer a specific public message in an approved
community. It has a source post, topic, suggested reply, review state, and send deadline.

The current database and API still use `engagement_candidates`, `candidate_id`, and
`EngagementCandidateOut` for compatibility with implemented code. New UI copy, docs, and future API
aliases should prefer `reply opportunity`. A later migration may rename storage and endpoints, but
until then the spec treats `candidate` as a legacy implementation name for a reply opportunity.

Collection and detection are separate:

| Step | What it does | What it must not do |
|---|---|---|
| Collection | Reads approved communities and stores bounded public artifacts such as recent message samples, metadata, and optional raw messages. | Decide whether to engage, call OpenAI for engagement, draft replies, notify operators, join, or send. |
| Detection | Reads collection artifacts for approved engagement targets, applies topic/timing/policy gates, may call OpenAI, and creates reply opportunities for review. | Scrape Telegram directly in MVP, collect broad history, join, send, or mutate collection/analysis state. |

## Durable Status Values

Status fields are PostgreSQL `text` columns in the MVP, validated by Python enums and API schemas.

### Engagement Setting Modes

Allowed `community_engagement_settings.mode` values:

- `disabled`
- `observe`
- `suggest`
- `require_approval`
- `auto_limited`

MVP allowed modes:

- `disabled`
- `observe`
- `suggest`
- `require_approval`
- `auto_limited`

### Membership Statuses

Allowed `community_account_memberships.status` values:

- `not_joined`
- `join_requested`
- `joined`
- `failed`
- `left`
- `banned`

State transitions:

```text
not_joined -> join_requested -> joined
not_joined -> join_requested -> failed
joined -> left
joined -> banned
failed -> join_requested
left -> join_requested
```

`banned` is terminal until the operator manually resets the row.

### Reply Opportunity Statuses

Allowed `engagement_candidates.status` values. The table name is legacy; these are reply
opportunity statuses:

- `needs_review`
- `approved`
- `rejected`
- `sent`
- `expired`
- `failed`

State transitions:

```text
needs_review -> approved
needs_review -> rejected
needs_review -> expired
approved -> sent
approved -> failed
approved -> expired
failed -> approved
```

Rules:

- `sent`, `rejected`, and `expired` are terminal for normal API operations.
- A failed reply opportunity may be re-approved by the operator when the failure was operational.
- The API must reject approval of expired reply opportunities.

### Action Statuses

Allowed `engagement_actions.status` values:

- `queued`
- `sent`
- `failed`
- `skipped`

State transitions:

```text
queued -> sent
queued -> failed
queued -> skipped
```

Action rows are append-only for audit. Status may be updated on the same action row while the worker
is executing, but completed action rows must not be rewritten except for an explicit operator
correction workflow.

## Global Invariants

These rules apply across all engagement code:

- No API route calls Telethon.
- No collection worker imports engagement services or writes engagement tables.
- No engagement worker writes `community_members.event_count` or `analysis_summaries`.
- No engagement prompt includes phone numbers or unnecessary sender identity.
- No reply opportunity is sent unless its status is `approved`.
- No reply opportunity is sent outside the engagement's configured send mode.
- No send occurs when the community settings row is missing or disabled.
- No send occurs when `allow_post = false`.
- No join occurs when `allow_join = false`.
- No join, detection, or send occurs unless an approved `engagement_targets` row grants the matching
  `allow_join`, `allow_detect`, or `allow_post` permission.
- No direct messages are supported by any payload, adapter, or API route.
- Outbound text must be stored exactly as sent.
- Each worker must be idempotent enough to tolerate RQ retry without duplicate sends.

## Ethics And Platform Rules

Telegram user accounts managed through Telethon are scarce operational identities. Engagement must
be transparent, sparse, and useful.

Baseline rules:

- Use dedicated Telegram accounts, not the operator's main personal account.
- Clearly configure the account identity before use; do not impersonate unrelated people.
- Prefer replies to existing discussion over unsolicited top-level posts.
- Keep all engagement public inside approved communities.
- Never contact individual users privately.
- Do not generate deceptive claims of personal experience, affiliation, popularity, urgency, or
  consensus.
- Prefer no reply when the value of a reply is weak or ambiguous.
- Respect Telegram flood-wait behavior and community moderation norms.
- Keep an audit trail of every join, draft, approval, rejection, send, skip, and failure.

## Safety Rules

- Engagement is opt-in per community.
- `Draft` mode requires human approval before send.
- `Auto send` is allowed only through explicit operator setup and capped
  automatic-send policy.
- No DMs.
- No person-level scoring.
- No hidden manipulation or fake consensus.
- No mass joining.
- All outbound actions are auditable.
- Collection remains read-only and must not send messages.
- Analysis remains community-level and must not produce outreach instructions for individuals.
