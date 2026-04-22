# Queue Engagement Jobs

Detailed engagement target resolution, join, detect, and send job contracts.

### `community.join`

Optional future job for the engagement module. It joins one operator-approved community with one
managed Telegram account.

Payload:

```json
{
  "community_id": "uuid",
  "telegram_account_id": "uuid-or-null",
  "requested_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="engagement_join")`
- The account manager must lease only an `engagement` pool account for this purpose.

Rules:

- Engagement settings must allow joining.
- Private invite links are out of scope for MVP.
- Do not join multiple accounts unless the operator explicitly requests it.
- Record membership state and account outcomes through the engagement and account-manager specs.
### `engagement_target.resolve`

Engagement-specific resolver for manually submitted targets. It may reuse the Telegram entity
resolver adapter, but it writes `engagement_targets` state and must not write seed rows.

Payload:

```json
{
  "target_id": "uuid",
  "requested_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="engagement_target_resolve")`
- This purpose is read-only and must lease only a `search` pool account.

Reads:

- `engagement_targets`

Writes:

- `engagement_targets.status`
- `engagement_targets.community_id`
- `engagement_targets.last_error`
- `communities` for resolved channels/groups

Rules:

- No OpenAI calls.
- No seed groups or seed channels are created.
- Users and bots fail the target as non-community entities.
- Resolved communities still require explicit target approval before join/detect/send.
### `engagement.detect`

Engagement job that detects an approved topic moment and creates a reply opportunity for operator
review.

Payload:

```json
{
  "community_id": "uuid",
  "collection_run_id": "uuid|null",
  "window_minutes": 60,
  "requested_by": "telegram_user_id_or_operator|null"
}
```

May call OpenAI because it is an engagement worker, not collection. It must not send messages.

Rules:

- Prefer the exact engagement message batch from `collection_run_id` when present.
- Fall back to recent stored messages or compact collection artifacts for manual diagnostics and
  scheduler sweeps.
- Do not include unnecessary Telegram user identity in prompts.
- Do not create person-level scores.
- Create reply opportunities only when topic fit, timing, and usefulness are strong enough.
### `engagement.send`

Optional future job for the engagement module. It sends one operator-approved public reply.

Payload:

```json
{
  "candidate_id": "uuid",
  "approved_by": "telegram_user_id_or_operator"
}
```

Uses:

- `account_manager.acquire_account(purpose="engagement_send")`
- The account manager must lease only the joined `engagement` pool account for this purpose.

Rules:

- Candidate must be approved.
- Community settings must allow posting.
- MVP sends replies only.
- Enforce account and community send limits.
- Write an `engagement_actions` audit row for sent, failed, and skipped outcomes.
