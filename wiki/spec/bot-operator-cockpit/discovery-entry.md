# Bot Operator Cockpit Discovery Entry

Discovery cockpit vocabulary, cards, callbacks, readiness summaries, and seed-group compatibility.

## Discovery Entry

The `Discovery` button should open a Discovery cockpit rather than dropping the operator directly
into backend seed-group lists.

Recommended Discovery cockpit:

```text
Discovery
  Start search
  Needs attention
  Review communities
  Watching
  Recent activity
  Help
```

This cockpit reframes the core search workflow around what the operator is trying to do:

| Button | Operator meaning | Backend concepts behind it |
|---|---|---|
| `Start search` | Add example communities for a new or existing search. | seed groups, seed channels, CSV import, direct Telegram entity intake |
| `Needs attention` | Show searches or communities that need operator attention before they can move forward. | unresolved seeds, failed seed resolution, failed snapshots, queued/stuck jobs |
| `Review communities` | Decide which suggested communities should be watched. | candidate communities, seed-group candidate lists, review decisions |
| `Watching` | Inspect communities already approved for monitoring. | communities with `monitoring` status, snapshot runs, latest snapshots |
| `Recent activity` | Inspect recent background work, job outcomes, and operational events. | seed resolution, snapshots, expansion/future jobs |
| `Help` | Show discovery-specific input guidance. | CSV shape, public link rules, direct commands |

The first implementation should reuse existing backend routes where possible. It should not
introduce new API routes merely to rename the operator surface. If a screen needs a filtered view
that existing routes cannot provide, add a read-only API route before adding bot-only filtering
logic.

### Discovery Vocabulary

The UI should translate backend nouns into operator-facing language:

| Backend term | Operator label |
|---|---|
| `seed_group` | Search |
| `seed_channel` | Example community |
| `resolve seeds` | Check examples |
| `candidate` | Suggested community |
| `approve` | Watch |
| `reject` | Skip |
| `collection` | Collect details |
| `job` | Recent job or background work |

Backend IDs remain available on detail cards for traceability, but cards should lead with the
operator label and readiness summary.

### Discovery Home Card

Recommended copy:

```text
Discovery

Next: Review 24 suggested communities.

Needs attention: 3 searches
Review communities: 24
Watching: 11 communities
Recent activity: 2 jobs need attention
```

The home card should be action-biased. The `Next:` line should name the most useful next step based
on current state, for example:

```text
Next: Start a search with example communities.
Next: Check 3 searches that need attention.
Next: Review 24 suggested communities.
Next: Inspect 2 failed jobs.
```

The exact counts may be omitted in the first slice if the API does not expose them cheaply, but the
card should still preserve the `Next:` line and the six-entry cockpit shape.

### Discovery Callback Namespace

Use a compact discovery-specific namespace under the top-level operator cockpit:

```text
disc:home
disc:start
disc:attention
disc:review
disc:watching
disc:activity
disc:help
disc:all
disc:search:<search_id>
disc:examples:<search_id>:<offset>
disc:check:<search_id>
disc:candidates:<search_id>:<offset>
disc:watch:<community_id>
disc:skip:<community_id>
```

The `op:discovery` callback should route to `disc:home` behavior. The existing seed-group callback
namespace may remain in place for item-level actions during the transition, but new discovery
navigation should use `disc:*`.

### Start Search

`Start search` should be a small search hub rather than only an upload hint.

Recommended hub:

```text
Start search
  New search
  Add examples to existing search
  All searches
  CSV format
```

Button meanings:

| Button | Operator meaning | Backend concepts behind it |
|---|---|---|
| `New search` | Start a discovery set from fresh example communities. | create/import seed group |
| `Add examples to existing search` | Add more example communities to a known search. | append seed channels to seed group |
| `All searches` | Browse every search, including searches with no current alert or review queue. | list seed groups |
| `CSV format` | Show import format and public-link rules. | seed CSV documentation |

The first implementation may keep `New search` and `Add examples to existing search` as guidance
around the current CSV/direct-intake flow rather than a full multi-step conversation.

`Start search` should explain these input paths:

- upload a CSV with `group_name,channel`
- send one public `@username` or `t.me` link for direct classification
- use an existing community as an example when that workflow is added

The `All searches` path is important even when it is not a top-level cockpit button. It prevents
searches from disappearing when they are not currently in `Needs attention`, `Review communities`,
or `Watching`.

### Needs Attention

`Needs attention` should show searches or communities that need operator attention before they can
move forward:

- searches with unresolved example communities
- searches with failed example checks
- searches with setup jobs that failed or are stuck
- searches with no usable examples
- watched communities whose collection jobs failed
- any discovery job that needs inspection or retry

Cards should explain the next safe action before raw counts:

```text
Search: Hungarian SaaS founders

Readiness: Needs attention
Examples checked: 21 of 24
Needs attention: 3 failed examples

Next: Check examples
```

### Review Communities

`Review communities` should show suggested communities waiting for a human decision.

Candidate cards should answer:

- what the community is
- why the system found it
- which search it belongs to
- what happens if the operator chooses the primary action

Recommended card shape:

```text
Open SaaS Hungary

Readiness: Needs review
Why found: Mentioned by 3 example communities
Signals: linked discussion, forwarded source
Members: 4,820
Search: Hungarian SaaS founders

Suggested next step: Watch this community
Community ID: <id>
```

Recommended buttons:

- `Watch`
- `Skip`
- `Show why`
- `Community profile`

`Watch` maps to the existing review-approve behavior that moves a community to monitoring and
queues collection. `Skip` maps to the existing reject behavior. Approval and rejection commands may
remain named `/approve` and `/reject`, but the normal button-led path should use `Watch` and `Skip`.

### Watching

`Watching` should show communities already approved for monitoring.

Cards should emphasize operational state:

- latest snapshot status
- latest snapshot summary when available
- latest analysis summary when available
- whether engagement settings exist when engagement is enabled

Recommended buttons:

- `Community profile`
- `Collect details`
- `Members`
- `Engagement`

### Recent Activity

`Recent activity` should collect background work and outcomes into one operational view:

- seed/example checks
- collection jobs
- expansion jobs when re-enabled
- failed jobs that need inspection

The view should provide refresh controls and short failure messages. It should avoid exposing noisy
worker internals until the operator opens a job detail card.

The operator-facing label should be `Recent activity`; individual rows may still be job cards when
the underlying object is a job.

### Discovery Help

`Discovery Help` should be shorter and more focused than global help:

- CSV upload columns: `group_name`, `channel`
- optional CSV columns: `title`, `notes`
- public Telegram references only
- private invite links are rejected
- direct handle intake accepts `@username` and public `t.me` links
- no people search and no person-level scores

### Discovery Readiness Summaries

Search cards should use one of these readiness labels before raw fields:

- `Needs examples`
- `Ready to check examples`
- `Checking examples`
- `Ready to review`
- `Review in progress`
- `Watching communities`
- `Needs attention: examples failed`
- `Needs attention: collection failed`
- `Paused`

Example-community cards should use:

- `Not checked yet`
- `Checking`
- `Confirmed public community`
- `Already known`
- `Failed: private or unavailable`
- `Failed: not a community`

Suggested-community cards should use:

- `Needs review`
- `Strong match`
- `Already watching`
- `Skipped`
- `Needs details`
- `Collecting details`
- `Ready to inspect`

Readiness summaries are display explanations of backend state. They must not replace backend
validation or review state.

### Seed-Group Compatibility

Seed cards should continue to expose the existing operations while they are renamed in the UI:

- open seed group
- check examples
- example communities
- suggested communities
