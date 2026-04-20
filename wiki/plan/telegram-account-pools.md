# Telegram Account Pool Separation Plan

## Goal

Split managed Telegram accounts into two hard pools:

```text
search      -> read-only resolution, expansion, entity intake, target resolution, collection
engagement  -> approved community joins and approved public replies
```

This prevents broad search/collection identities from becoming public posting identities.

## Current Context

Today, workers pass a `purpose` to the account manager, but all purposes select from the same
`telegram_accounts` table without a pool filter. Engagement join/send therefore cannot overlap
concurrently with search work, but can reuse the same Telegram identity over time.

That is too blended for public engagement. The implementation should make pool separation a backend
invariant.

## Design Decisions

- Add `telegram_accounts.account_pool` with values `search`, `engagement`, and `disabled`.
- Existing accounts default to `search`.
- Account status remains health/lease state and is separate from pool state.
- `engagement_target.resolve` is read-only and uses the `search` pool.
- `community.join` and `engagement.send` use only the `engagement` pool.
- `engagement.detect` remains accountless in the MVP.
- Explicit `telegram_account_id` values must not bypass pool validation.
- `assigned_account_id` must reference an engagement account.

## Slice 1: Spec And Plan

Status: completed.

Tasks:

- Add `wiki/spec/telegram-account-pools.md`.
- Add this plan.
- Update account-manager, database, engagement, and queue specs with the pool separation contract.
- Update `wiki/index.md`.
- Record the design change in `wiki/log.md`.

Acceptance:

- Future implementation agents can see the purpose-to-pool mapping.
- Existing accounts are specified to migrate safely into the `search` pool.
- Engagement assignment and send preflight rules reject search accounts.

## Slice 2: Schema And Model

Status: pending.

Tasks:

- Add Alembic migration for `telegram_accounts.account_pool`.
- Default existing rows to `search`.
- Add SQLAlchemy model field and enum/constants.
- Add index for `(account_pool, status, last_used_at)`.

Acceptance:

- Migration upgrade/downgrade works.
- Existing tests continue to create usable search accounts by default.

## Slice 3: Account Manager Routing

Status: pending.

Tasks:

- Add `engagement_target_resolve` to allowed account purposes.
- Implement purpose-to-pool mapping.
- Filter `acquire_account()` by required pool.
- Validate pool in `acquire_account_by_id()`.
- Exclude `disabled` accounts from all leases.

Acceptance:

- Search purposes never lease engagement accounts.
- Engagement join/send never lease search accounts.
- Explicit account ID selection cannot bypass the pool.

## Slice 4: Engagement Guards

Status: pending.

Tasks:

- Validate `assigned_account_id` against the engagement pool.
- Make `community.join` select only engagement-pool memberships/accounts.
- Make `engagement.send` reject historical joined memberships backed by search accounts.
- Keep `engagement_target.resolve` read-only and search-pool only.

Acceptance:

- Engagement cannot join or send through search accounts.
- Existing historical memberships do not authorize sends unless the account is engagement-pool.

## Slice 5: Onboarding And Operator UX

Status: pending.

Tasks:

- Add `--account-pool search|engagement` to `scripts/onboard_telegram_account.py`.
- Default non-interactive onboarding to `search`.
- Show pool values in safe account admin/debug output where applicable.
- Add a deliberate operator path for marking an account as `engagement`.

Acceptance:

- Operators can create dedicated accounts for both pools.
- Search remains the safe default.

## Slice 6: Tests And Release

Status: pending.

Tasks:

- Add tests listed in `wiki/spec/telegram-account-pools.md`.
- Update wiki log after implementation.
- Commit and push the completed slice when a remote is configured.

Acceptance:

- Full account-manager and engagement worker tests pass.
- Pool separation is enforced by backend tests, not just documented.

## Open Questions

- Should first successful engagement join automatically set `assigned_account_id`?
- Should account pool changes be script-only at first, or exposed through bot admin controls?
- Should recent search activity block or only warn before changing an account to `engagement`?
