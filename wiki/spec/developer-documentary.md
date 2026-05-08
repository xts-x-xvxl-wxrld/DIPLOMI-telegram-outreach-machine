# Developer Documentary Spec

## Goal

Create a developer-facing documentation lane that grows from inspected evidence during normal agent
and human work. The result should help engineers understand how the codebase is wired without
trying to rewrite every spec or annotate every line of code.

## Scope

This documentation is for developers working on the repository:
- architecture notes about active code structure
- module guides for ownership boundaries and entrypoints
- execution-flow pages for important runtime paths
- recurring implementation patterns and project vocabulary

Out of scope:
- operator manuals for using the Telegram app
- speculative docs for uninspected areas
- line-by-line code commentary
- replacing `wiki/spec/` as the behavior source of truth

## Artifact Roles

Keep the three wiki lanes separate:

- `wiki/spec/` defines product, behavior, and architecture contracts.
- `wiki/code-index/` is the fast navigation layer for finding code.
- `wiki/dev-docs/` is the deeper developer documentary for verified code understanding.

`wiki/dev-docs/` should explain how live code is organized and how important flows move through the
system. It may link to specs and code indexes, but it should not duplicate them wholesale.

## Evidence Rule

Developer documentary pages must be evidence-based:

- document facts that were directly inspected in code, tests, or current edits
- mark reasonable but unproven conclusions as inference or open questions
- prefer narrow pages over broad summaries when coverage is incomplete

Agents and developers should never present unverified repo folklore as settled fact.

## Page Types

Recommended page families under `wiki/dev-docs/`:

- `architecture/` for subsystem maps and cross-cutting boundaries
- `modules/` for package or subsystem guides
- `flows/` for end-to-end execution paths
- `patterns/` for recurring implementation seams and conventions
- `glossary.md` for stable project vocabulary

Each page should stay focused on one bounded subject.

## Page Content

Module guides should usually cover:
- purpose
- owns / does not own
- key files
- entrypoints and facades
- main dependencies
- invariants and boundaries
- related tests
- common change patterns
- known footguns
- open questions

Flow pages should usually cover:
- trigger
- step-by-step path
- state changes
- failure points
- related tests
- follow-up questions

## Maintenance Protocol

When an agent or developer inspects, debugs, or changes an area:

1. Update the matching `wiki/dev-docs/` page when useful knowledge was confirmed from the files,
   tests, runtime behavior, or current edits you touched.
2. Create the narrowest new page only when no suitable page exists.
3. Link to the relevant spec and code-index entrypoint instead of copying large sections.
4. Update `wiki/index.md` only when new dev-doc entrypoints, specs, plans, or directories appear.
5. Append `wiki/log.md` when documentary artifacts are created or materially updated.

## Agent Expectations

Agents should treat `wiki/dev-docs/` as a living developer memory:
- read it when the task touches an already-documented subsystem
- improve it after inspection, debugging, or implementation work in that area
- keep wording concrete, current, and useful to the next engineer

The protocol should reward incremental truth over completeness theater.
