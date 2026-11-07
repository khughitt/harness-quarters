---
id: hq-aea33f
title: Pin the staged-facts pre-commit check to the index git commits with a real-commit test
status: doing
priority: 3
size: xs
complexity: low
process: direct
owner: test/hq-aea33f-staged-facts-index
created: 2026-10-15T02:02:42Z
updated: 2026-11-07T16:02:47Z
started: 2026-11-07T16:00:43Z
depends: []
tags: []
source: hq-3cdd68
agent: claude-code/claude-opus-5-5
---

The staged-facts check in .githooks/pre-commit copies the index named by `git rev-parse --git-path index` (which honours GIT_INDEX_FILE) and exports the tree it would commit. Reviews of hq-3cdd68 showed that a mutant reading .git/index directly still passes the suite, while a real `git commit -a` then commits an unstaged invalid fact file. Real-commit runs verified the current code by hand only.

Outcome: a test drives `facts_check` with GIT_INDEX_FILE pointing at an alternate index that differs from .git/index (or drives the installed hook through `git commit -a` and `git commit <path>`), and it fails against that mutant.

Also deferred from the same review, optional here: the refusal could note that the fault may already be in HEAD (a --no-verify commit or a merge lands without the hook), and a missing index file raises FileNotFoundError, which is reachable only when the hook is run by hand.

## Notes

- 2026-11-07T16:00:43Z (main): started
- 2026-11-07T16:01:45Z (test/hq-aea33f-staged-facts-index): resumed
- 2026-11-07T16:01:45Z (test/hq-aea33f-staged-facts-index): took over Unix session (owner main, stale)
- 2026-11-07T16:02:08Z (test/hq-aea33f-staged-facts-index): trial: flow-trial-1 — enrolled — flow on
- 2026-11-07T16:02:10Z (test/hq-aea33f-staged-facts-index): arm: flow-trial-1 — unit tack-aea33f — flow on
- 2026-11-07T16:02:45Z (test/hq-aea33f-staged-facts-index): gate: scoped — adopted
- 2026-11-07T16:02:47Z (test/hq-aea33f-staged-facts-index): gate: implementing .worktrees/hq-aea33f
