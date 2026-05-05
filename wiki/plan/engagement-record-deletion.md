# Engagement Record Deletion

## Goal

Add safe operator-facing deletion for user-created engagement records without
breaking audit history, job safety, or the task-first cockpit.

## Scope

- task-first engagement deletion
- engagement topic deletion
- bot and API entrypoints that let operators invoke those actions
- tests and spec updates for the new lifecycle rules

## Constraints

- Active engagements and anything with reply history should not be physically
  removed if that would break audit trails.
- Topic deletion must respect live references from engagements, candidates, and
  related admin assets.
- Draft-only setup records may be hard-deleted when they never entered runtime
  history and the delete will not strand broken references.

## Plan

1. Add an archive-first lifecycle contract to the engagement API and bot specs.
2. Implement a task-first engagement delete service that:
   - hard-deletes draft-only setups with no runtime history
   - archives everything else
   - disables posting/join settings and target permissions when archiving
3. Implement a topic delete service that:
   - blocks deletion while non-archived engagements still reference the topic
   - deactivates topics that still have historical references
   - hard-deletes only fully unreferenced topics and their topic-scoped style
     rules / embeddings
4. Expose the new delete actions through API routes and bot callbacks.
5. Add regression tests for delete results, blocked states, and cockpit/topic
   admin UX.

## Acceptance

- Operators can remove an engagement from the task-first surface without
  leaving it editable or visible as active work.
- Operators can remove a topic without breaking historical candidates or active
  engagements.
- Task-first wizard and cockpit behavior remain stable after deletions.
