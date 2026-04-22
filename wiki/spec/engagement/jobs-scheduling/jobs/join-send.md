# Engagement Join And Send Jobs

Detailed `community.join` and `engagement.send` worker contracts.

### `community.join`

Joins one approved community with one managed Telegram account.

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

Rules:

- `allow_join` must be true.
- An approved engagement target with `allow_join = true` must exist for the community.
- The community must be approved for engagement.
- Private invite links are out of scope for MVP.
- Do not join multiple accounts unless requested by the operator.
- Respect FloodWait and account health mapping.

Worker preflight:

1. Load community.
2. Load settings; skip if missing, disabled, or `allow_join = false`.
3. Verify an approved engagement target with `allow_join = true`.
4. Select or acquire an account according to the membership selection contract.
5. Mark membership `join_requested`.
6. Resolve the Telegram entity.
7. Join or confirm already joined.
8. Mark membership `joined` or `failed`.
9. Write an `engagement_actions` audit row with `action_type = join`.
10. Release account in `finally`.

Telethon adapter contract:

```python
@dataclass
class JoinResult:
    status: Literal["joined", "already_joined", "inaccessible"]
    joined_at: datetime | None
    error_message: str | None = None

class TelegramEngagementAdapter:
    async def join_community(self, *, session_file_path: str, community: Community) -> JoinResult:
        ...
```
### `engagement.send`

Sends one approved public reply.

Payload:

```json
{
  "candidate_id": "uuid",
  "approved_by": "telegram_user_id_or_operator"
}
```

`candidate_id` is the legacy API field name for the approved reply opportunity ID.

Uses:

- `account_manager.acquire_account(purpose="engagement_send")`

Rules:

- Reply opportunity must be `approved`.
- Community settings must allow posting.
- An approved engagement target with `allow_post = true` must exist for the community.
- `require_approval` must be satisfied.
- The account must have joined the community.
- The joined membership account must be in the `engagement` account pool.
- Daily and spacing limits must pass for the account and community.
- MVP sends replies only; top-level posts are future/optional.
- Store an `engagement_actions` row whether the result is sent, failed, or skipped.

Worker preflight:

1. Load reply opportunity with topic and community.
2. Skip if reply opportunity is not approved.
3. Skip if reply opportunity is expired or past `reply_deadline_at`.
4. Load settings; skip if missing, disabled, or `allow_post = false`.
5. Verify an approved engagement target with `allow_post = true`.
6. Reject top-level send if `reply_only = true` and `source_tg_message_id` is missing.
7. Load joined membership; skip if none exists.
8. Check community and account send limits.
9. Create or resume `engagement_actions` row with idempotency key.
10. Acquire the membership account with `purpose = engagement_send`.
11. Send reply through Telethon.
12. Mark action sent and reply opportunity sent.
13. Release account in `finally`.

Rate-limit contract:

- Count only `engagement_actions` with `status = sent`.
- Community limit uses `community_id` and a rolling 24-hour window.
- Account limit uses `telegram_account_id` and a rolling 24-hour window.
- Spacing limit uses the latest sent action for the community and for the account; both must pass.
- Failed or skipped actions do not consume rate-limit quota.

Telethon adapter contract:

```python
@dataclass
class SendResult:
    sent_tg_message_id: int
    sent_at: datetime

class TelegramEngagementAdapter:
    async def send_public_reply(
        self,
        *,
        session_file_path: str,
        community: Community,
        reply_to_tg_message_id: int,
        text: str,
    ) -> SendResult:
        ...
```

Error mapping:

| Error | Account outcome | Action status | Reply opportunity status |
|---|---|---|---|
| FloodWait | rate_limited | failed | approved |
| banned/deauthorized | banned | failed | failed |
| transient network | error | failed | approved |
| community inaccessible | success | skipped | approved |
| message no longer replyable | success | skipped | expired |
| validation/safety failure | success | skipped | failed |
