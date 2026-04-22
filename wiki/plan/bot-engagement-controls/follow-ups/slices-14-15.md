# Bot Engagement Follow-Up Slices 14-15

Menu polish and backend capability boundary follow-ups.

## Follow-Up Slice 14: Menu And Progressive Disclosure Polish

Status: completed on 2026-04-22.

Purpose:

Make daily engagement and admin cards easier to navigate after the safety and creation gaps are
closed.

Work items:

- Add a direct `Settings lookup` item to the daily engagement menu.
- Add button-led settings lookup entrypoints that reuse `/engagement_settings <community_id>` where
  practical.
- Prefer operator-facing labels before backend field names on default cards.
- Move raw IDs and diagnostic backend fields lower in default cards while keeping detail views
  audit-friendly.
- Improve readiness summaries when backend responses expose enough membership, account,
  rate-limit, quiet-hour, or expiry detail to explain blocks accurately.

Acceptance:

- `/engagement` exposes a direct route to settings lookup.
- Default target, settings, topic, style, and prompt cards are compact and intention-first.
- Detail views still expose IDs and audit-relevant state.
- Readiness summaries do not invent precision when the backend does not expose a concrete reason.

Tests:

- UI tests assert the Settings lookup button exists and callback data stays within Telegram limits.
- Formatting tests cover compact default cards and detail-card ID visibility.
- Readiness formatting tests cover backend-provided readiness strings and fallback behavior.

Completed:

- `/engagement` now exposes a direct `Settings lookup` button in the daily engagement menu.
- Added a button-led settings lookup page that lists approved engagement targets with resolved
  communities and opens the existing `/engagement_settings <community_id>` settings surface through
  `eng:set:open`.
- Resolved target cards now include a direct `Settings` button when a community ID is available.
- Default target, prompt profile, topic, and style-rule list cards are more compact and
  operator-facing; raw IDs and diagnostic fields are still present on opened detail cards and
  mutation results.
- Community settings cards now lead with posting posture, safety floor, pacing, quiet hours, and
  engagement-account language before raw community/mode fields.
- Readiness helpers now prefer backend-provided readiness summaries and concrete block reasons, and
  fall back to local summaries only when the backend does not provide a reason.
- Focused bot UI, formatting, and engagement-handler coverage passed with 162 tests.
## Follow-Up Slice 15: Backend Capability Boundary

Status: completed on 2026-04-22.

Purpose:

Move the admin permission source from the transitional Telegram bot allowlist toward backend-owned
operator capabilities or roles.

Work items:

- Add or identify a backend endpoint that exposes engagement operator/admin capabilities for the
  current bot auth context.
- Update the bot to use backend capabilities when available.
- Keep `TELEGRAM_ADMIN_USER_IDS` as a transitional fallback during rollout.
- Make backend authorization the primary contract for prompt, style, topic, target, and advanced
  community-setting mutations.

Acceptance:

- The bot can hide or reject admin-only controls based on backend capabilities.
- Protected backend routes remain authoritative even if bot-side checks are misconfigured.
- Tests cover both backend-capability and transitional-allowlist behavior.

Completed:

- Added `GET /api/operator/capabilities`, which reports whether backend engagement-admin
  capabilities are configured and whether the caller's `X-Telegram-User-Id` has the admin
  capability.
- Added backend-owned `ENGAGEMENT_ADMIN_USER_IDS` configuration. When configured, protected
  target, prompt-profile, style-rule, topic, and community engagement-settings mutation routes
  reject non-admin callers with `403 engagement_admin_required`.
- Updated the bot API client and admin mutation calls to send the Telegram operator ID as
  `X-Telegram-User-Id`.
- Updated bot admin gating to prefer backend capabilities and fall back to
  `TELEGRAM_ADMIN_USER_IDS` only when the backend reports capabilities are unconfigured or the
  endpoint is unavailable.
- Added focused backend capability, API-client header, bot access, and engagement-handler tests.
## Open Questions

- Prompt duplicate and rollback are first-class API routes in the shipped implementation.
- Admin permission now prefers backend capabilities from `GET /api/operator/capabilities` backed by
  `ENGAGEMENT_ADMIN_USER_IDS`; `TELEGRAM_ADMIN_USER_IDS` remains a transitional bot-side fallback
  when backend capabilities are unconfigured.
- Should target approval also create default engagement settings? Current recommendation: keep
  approval and settings separate until product review chooses otherwise.
- Should conversation-state edits survive bot restarts? Current recommendation: keep short-lived
  in-process drafts for the next slices and revisit durable drafts only if operators lose work in
  practice.
