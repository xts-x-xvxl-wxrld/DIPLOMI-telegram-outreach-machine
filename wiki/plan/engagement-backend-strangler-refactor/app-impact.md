# Engagement Backend Strangler — Positive App Impact

These simplifications improve the live engagement experience directly, not only
code health.

## 1. Permission-Triad Collapse

Expected app impact:

- fewer "why did join/detect/send not happen" failures caused by hidden flag
  drift between targets, settings, and worker checks
- no more need for repair-oriented issue flows such as permission resync just
  to restore the intended engagement state
- clearer operator behavior because lifecycle and mode become the only real
  controls

## 2. One Active Runtime Settings Model

Expected app impact:

- fewer precedence bugs where legacy community settings and task-first
  engagement settings disagree
- more predictable scheduler, collection, join, detect, and send behavior
- simpler bot edits because one write path controls the live runtime

## 3. Target Demotion

Expected app impact:

- less operator confusion because targets stop behaving like mini control-plane
  records
- fewer backend branches caused by mixing reference intake, approval, runtime
  permissions, and manual jobs on the same object
- simpler recovery flows because engagement lifecycle owns the runtime intent

## 4. Cockpit Read-Model Narrowing

Expected app impact:

- a more stable engagement cockpit because home, approvals, issues, detail, and
  sent feed stop depending on broad in-memory snapshots
- lower regression risk when changing one cockpit screen
- easier debugging of issue/approval visibility because each screen gets a
  clearer read boundary

## 5. Compat Bot/Admin Surface Reduction

Expected app impact:

- cleaner operator UX if the product remains task-first, because old
  permission-first controls stop competing with the wizard/cockpit model
- fewer support/debug situations caused by legacy manual join/detect/settings
  flows changing live behavior through side channels
- stronger product consistency across bot copy, callbacks, and backend
  semantics

## 6. Compat Facade Removal

Expected app impact:

- faster and safer engagement iteration because new work lands in the real
  active modules instead of old umbrella surfaces
- lower test and import indirection, which should reduce accidental regressions
  during follow-up engagement cleanup
