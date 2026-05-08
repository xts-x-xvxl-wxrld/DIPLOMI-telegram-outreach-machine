# Developer Documentary Protocol

## Purpose

Keep a verified developer documentary that grows from real inspection work instead of periodic
"document everything" pushes.

## Evidence Standard

Only record knowledge that was confirmed by one or more of:
- direct code reads
- related tests
- current implementation changes
- current runtime or validation output

If something seems likely but is not proven, label it as an open question or an inference.

## When To Update

Update a dev-doc page when you:
- inspect a subsystem's files to complete a task
- debug behavior in that subsystem
- change code in that subsystem
- change ownership boundaries, entrypoints, or flow shape
- confirm a previously unclear invariant or footgun

Do not create broad pages for areas you barely touched.

## Writing Rules

- prefer one narrow page per subsystem or flow
- link to specs and code-index pages instead of duplicating them
- describe responsibilities, seams, and behavior shape rather than paraphrasing source line by line
- keep statements concrete and developer-useful
- when a local validation script only checks tracked files, stage or otherwise
  track new files before trusting a green result; `scripts/check_fragmentation.py`
  follows `git ls-files`, so brand-new oversized files can slip past an
  unstaged local run and fail later in CI

## Suggested Page Types

- module guide
- flow guide
- architecture note
- pattern note
- glossary term

## Required Follow-Through

When documentary artifacts change:

1. update `wiki/index.md` if a new entrypoint or directory was created
2. append `wiki/log.md`
3. keep the relevant spec updated if design or behavior changed

## Style

Aim for pages that help the next engineer answer:
- where do I start reading?
- what does this area own?
- what can I safely change here?
- what breaks easily if I get this wrong?
