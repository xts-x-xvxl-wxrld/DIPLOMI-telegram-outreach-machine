# Bot Engagement Navigation

Operator mode, navigation, and progressive disclosure contracts for the engagement cockpit.

## Operator Modes

The bot has two engagement modes.

### Daily Engagement

Daily engagement is for normal review work.

Entry point:

```text
/engagement
```

Primary controls:

- what needs review today
- approved replies waiting to send
- clear edit, approve, reject, and send actions
- recent action outcomes
- handoff links for community, topic, and voice tuning

Daily controls may be available to ordinary allowlisted operators.

### Engagement Admin

Engagement admin is for configuration that can affect model output or outbound permissions.

Entry point:

```text
/engagement_admin
```

Primary controls:

- which communities may be watched, drafted for, or posted in
- what topics the system should notice
- how replies should sound
- safety limits, quiet hours, and account assignment
- advanced prompt profile controls

Admin controls require an admin permission layer in addition to the normal bot allowlist when the
backend exposes that distinction. Until then, the bot may enforce a transitional Telegram admin
allowlist such as `TELEGRAM_ADMIN_USER_IDS`, while still treating backend authorization as the
source of truth.

## Navigation

The primary navigation must be operator-intention first. Backend entities such as targets, settings,
prompt profiles, style rules, and action rows should be secondary implementation details unless the
operator opens an advanced or diagnostic view.

Recommended top-level engagement menu:

```text
Engagement
  Today
  Review replies
  Approved to send
  Communities
  Topics
  Recent actions
  Admin
```

Recommended engagement admin menu:

```text
Engagement Admin
  Setup
    Communities
    Topics
    Voice rules
    Limits and accounts
  Advanced
    Prompt profiles
    Audit and diagnostics
```

The operator-facing labels should answer common questions:

```text
What needs my review today?
Where are we allowed to participate?
What should the system notice?
How should replies sound?
Why can or can't this be posted?
What changed recently?
```

Telegram reply-keyboard buttons may open these menus, but every state-changing action must also be
reachable through an explicit command for traceability and testing.

Inline callback data must stay under Telegram's 64-byte limit. UUID-heavy actions should use short
prefixes and compact action segments.

## Operator Intention Model

The cockpit should hide backend complexity until it helps the operator make a decision.

| Operator intention | Primary UI label | Backend concepts behind it |
|---|---|---|
| Review what needs attention | Today, Review replies, Approved to send | candidates, candidate statuses, revisions, send jobs |
| Decide where engagement is allowed | Communities | engagement targets, community engagement settings, memberships |
| Decide what to notice | Topics | engagement topics, trigger keywords, negative keywords, topic examples |
| Tune how replies sound | Voice rules | style rules, topic guidance, prompt fragments |
| Understand whether posting is safe | Readiness, Blocked reasons | target permissions, settings mode, joined account, rate limits, expiry |
| Investigate or tune internals | Advanced | prompt profiles, prompt versions, audit/action rows, diagnostics |

Rules:

- Show a short readiness summary before raw booleans.
- Show only the next safe actions for the current state by default.
- Put IDs, raw permission fields, prompt profile internals, and diagnostic details behind expandable
  cards or advanced commands.
- Keep command paths available for traceability, testing, and power users, but make button-led flows
  the normal operator path.
- Prefer verbs the operator understands: watch, draft, review, post, tune, pause, block.
- Avoid making the operator choose between backend concepts that represent one real-world decision.

### Readiness Summaries

Community cards should summarize engagement readiness in one line before showing lower-level fields.

Recommended readiness labels:

- `Not approved`
- `Approved, not joined`
- `Watching only`
- `Drafting replies`
- `Ready to post with review`
- `Paused`
- `Blocked: no joined engagement account`
- `Blocked: posting permission off`
- `Blocked: rate limit or quiet hours`

Candidate cards should summarize send readiness in one line:

- `Needs review`
- `Approved, ready to send`
- `Blocked: community not ready`
- `Blocked: reply expired`
- `Blocked: account or rate limit`
- `Sent`
- `Rejected`
- `Failed, retry may be available`

The readiness summary is derived from backend state. It must not replace backend validation; it is a
human-readable explanation of the same preflight rules.

### Progressive Disclosure

The bot should keep the default card small. Detailed controls should appear only when the operator
opens the relevant item.

Candidate card default actions:

| Candidate state | Default actions |
|---|---|
| `needs_review` | Edit, Approve, Reject |
| `approved` | Send, Reopen/Edit, Reject |
| `failed` | Retry, View error, Reject |
| `sent` | View audit |
| `rejected` or `expired` | View audit |

Community card default actions should be similarly state-aware:

- Not approved: add or approve engagement community.
- Approved but not joined: join or keep watching without join.
- Watching only: enable drafting or pause.
- Drafting: review suggested replies, adjust topics, or pause.
- Ready to post: review approved replies, adjust limits, or pause posting.
- Blocked: show the single most important next fix first.
