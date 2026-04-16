# Audience Brief Spec

## Purpose

Audience Brief is an optional/future context layer.

The active MVP no longer depends on natural-language briefs for discovery. Discovery is driven by
operator-curated `seed_groups`: real example Telegram communities that are resolved and expanded
through graph evidence.

Audience Brief may later turn an operator's natural-language target audience description into a
structured search brief used for filtering, sorting, public web-search adapters, or analysis
context.

The output is not a final relevance judgment. It is search guidance only. It must not replace
seed-group provenance as the explanation for why a community entered review.

## Operator Input

The operator may submit plain text such as:

```text
International students in German-speaking Europe discussing thesis writing, citation issues, and academic English.
```

The API stores the raw input immediately in `audience_briefs.raw_input`.

## Structured Output

The brief processing job fills these existing `audience_briefs` fields:

- `keywords` - core search keywords
- `related_phrases` - phrases and alternate expressions likely to appear in posts or titles
- `language_hints` - ISO-like language hints or plain labels when uncertain
- `geography_hints` - countries, regions, cities, or regional descriptors
- `exclusion_terms` - terms that indicate off-target communities
- `community_types` - likely useful Telegram spaces, such as `channel`, `group`, `discussion`

Arrays should be capped for MVP:

- maximum 12 keywords
- maximum 20 related phrases
- maximum 8 language hints
- maximum 10 geography hints
- maximum 12 exclusion terms
- maximum 6 community types

## Processing Model

Brief extraction can run asynchronously as an RQ job when the optional brief workflow is enabled:

```text
POST /api/briefs
  -> write audience_briefs row
  -> enqueue brief.process
  -> brief.process fills structured fields
  -> optionally enqueue discovery.run in a future brief-driven workflow
```

The API must not call OpenAI directly. It returns after the brief is stored and the processing job is
queued.

MVP seed-first flow should not require this job:

```text
CSV upload
  -> seed.resolve
  -> seed.expand
  -> operator review
```

If a future workflow combines a seed group and a brief, the `brief_id` may be attached to
`seed.expand` or collection analysis as context. The seed group remains the primary intent and
provenance object.

## OpenAI Boundary

OpenAI calls are allowed only in:

- `brief.process`
- `analysis.run`

They are not allowed in:

- API request handlers
- `seed.resolve`
- `discovery.run`
- `expansion.run`
- `seed.expand`
- `collection.run`

`brief.process` must request structured JSON and validate it before writing to the database. Invalid
or incomplete model output fails the job rather than silently starting weak discovery.

## Failure Behavior

If brief processing fails:

- the raw brief remains stored
- structured arrays remain empty or unchanged
- discovery is not started automatically
- the failed RQ job exposes the error through the jobs API

The operator can retry by starting a new processing flow in a later API version. MVP may retry by
creating a new brief.

## Safety Rules

- Do not produce person-level scores.
- Do not infer private or sensitive personal attributes about individual Telegram users.
- Do not include direct outreach instructions.
- Keep output focused on community discovery, indexing, monitoring, and review.
