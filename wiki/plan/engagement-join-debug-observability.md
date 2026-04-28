# Engagement Join Debug Observability

## Goal

Make task-first engagement joins easier to debug when an assigned account never transitions from
`account_not_connected` to `account_connecting` or `joined`.

## Scope

- Add structured backend logs around `community.join` worker execution.
- Stop silently swallowing join enqueue failures during task-first confirmation.
- Surface the backend confirmation message in the bot wizard success state.
- Promote resolved task-first target communities into an engagement-eligible status before queuing
  `community.join`.

## Steps

1. Add worker-side logs for join start, skip reasons, account acquisition, join result, and failures.
2. Update task-first confirm so join enqueue failures are logged and returned to the caller.
3. Update the bot confirm success copy to use the backend message.
4. Add regression coverage for join enqueue failure during task-first confirmation.
5. Ensure task-first confirmation marks resolved target communities `approved` before the join job
   runs.
