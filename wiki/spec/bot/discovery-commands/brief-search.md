# Bot Brief And Search Commands

Detailed optional brief and query-driven search command contracts.

### `/brief <audience description>`

Optional/future command. The active MVP should not require briefs for discovery.

Calls `POST /api/briefs` with:

```json
{
  "raw_input": "operator text",
  "auto_start_discovery": true
}
```

The API queues `brief.process`. The bot returns the brief ID and queued job ID.
### `/briefs`

Lists recent briefs and high-level candidate counts.

If the API does not yet expose a list endpoint, this command can wait until the optional brief layer
returns.
### `/search <plain language query>`

Starts a query-driven community search through `POST /api/search-runs`.

Request:

```json
{
  "query": "operator text",
  "requested_by": "telegram_user_id_or_operator",
  "enabled_adapters": ["telegram_entity_search"]
}
```

The bot reports the search run ID, queued `search.plan` job ID, and a refresh action for the run.
Search copy should describe public communities, not outreach targets.

Validation:
- Empty query text is rejected locally before calling the API when possible.
- Private invite links are not accepted as search queries.
- Plain public `@username` or `t.me/...` handle intake may continue to use the direct entity intake
  path unless the operator explicitly uses `/search`.
### `/searches`

Calls `GET /api/search-runs` and shows recent search runs with:

- title or raw query
- status
- query count
- candidate count
- promoted/rejected counts
- latest error when present
- inline open and candidates actions
### `/search_run <search_run_id>`

Calls `GET /api/search-runs/{search_run_id}` and
`GET /api/search-runs/{search_run_id}/queries`.

The bot shows:
- search title/raw query
- status and latest error
- query status counts
- candidate and review counts
- ranking version when available
- inline refresh, queries, candidates, and rerank actions
### `/search_candidates <search_run_id>`

Calls `GET /api/search-runs/{search_run_id}/candidates`.

Candidate cards show:
- title
- username or Telegram link when available
- member count when available
- score and short score-component summary when ranked
- compact evidence summary
- candidate ID and linked community ID when resolved
- run-scoped promote, reject, archive, and detail controls

Candidate cards must not expose raw message history, sender identity, phone numbers, or
person-level scores. Paging should use inline Telegram controls.
### `/promote_search <candidate_id>`

Calls `POST /api/search-candidates/{candidate_id}/review` with:

```json
{
  "action": "promote",
  "requested_by": "telegram_user_id_or_operator"
}
```

Promotion is run-scoped. It does not approve the community for monitoring and does not create an
engagement target.
### `/reject_search <candidate_id>`

Calls `POST /api/search-candidates/{candidate_id}/review` with:

```json
{
  "action": "reject",
  "requested_by": "telegram_user_id_or_operator"
}
```

The first implementation treats rejection as run-scoped. Global rejection is a later explicit
action.
### `/archive_search <candidate_id>`

Calls `POST /api/search-candidates/{candidate_id}/review` with:

```json
{
  "action": "archive",
  "requested_by": "telegram_user_id_or_operator"
}
```

Archive hides or defers the candidate within the current run only.

### `/convert_search <candidate_id> [seed_group_name]`

Calls `POST /api/search-candidates/{candidate_id}/convert-to-seed`.

If `seed_group_name` is omitted, the API appends to the search-run-derived seed group. Inline bot
conversion controls are shown after promotion and on promoted candidate cards.
