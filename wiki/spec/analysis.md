# Analysis Spec

## Purpose

Analysis produces community-level summaries and relevance notes from compact collection artifacts.

It helps the operator decide which monitored communities are useful relative to the active context.
In the seed-first MVP, that context is usually the seed group that led to the community. If an
optional future audience brief is attached, analysis may also consider that brief.

Analysis does not score or rank individual people.

## Inputs

`analysis.run` receives:

```json
{
  "collection_run_id": "uuid",
  "requested_by": "telegram_user_id_or_operator|null"
}
```

The worker reads:

- `collection_runs.analysis_input`
- `communities`
- optional `audience_briefs` context when `brief_id` is present
- optional seed-group provenance when needed to explain how a community entered monitoring

## Responsibilities

- Validate that the collection run has usable analysis input.
- Call OpenAI with a community-level analysis prompt.
- Produce a concise summary.
- Extract dominant recurring themes.
- Estimate activity level.
- Describe broadcast vs discussion characteristics.
- Score topical fit at the community level relative to seed-group context, optional brief context, or both.
- Mark centrality as `core` or `peripheral`.
- Write `analysis_summaries`.
- Update `collection_runs.analysis_status`.

## Output

Analysis writes one `analysis_summaries` row with:

- `summary`
- `dominant_themes`
- `activity_level`
- `is_broadcast`
- `relevance_score`
- `relevance_notes`
- `centrality`
- `analysis_window_days`
- `model`

## Relevance Score

`relevance_score` is community-level only.

In the seed-first MVP, it should represent how strongly the community appears to fit the seed-group
context based on recurring themes, activity, language/geography hints visible in collection data,
and available provenance. If a brief is attached, the score may also consider the brief fields.

It must not represent individual user quality, outreach priority, or person-level value.

## Failure Behavior

If analysis input is missing or expired:

- mark `analysis_status = 'skipped'` or `failed` according to the concrete failure
- write an operator-facing error message where appropriate
- do not attempt to reconstruct raw history unless raw message storage was explicitly enabled

## Safety Rules

- No person-level scores.
- No personal outreach recommendations.
- No raw phone numbers.
- Do not expose unnecessary Telegram user identity in model prompts.
- Analysis may call OpenAI; collection, discovery, seed resolution, and expansion may not.
