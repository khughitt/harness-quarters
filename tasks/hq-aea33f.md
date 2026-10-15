---
id: hq-aea33f
title: Pin the staged-facts pre-commit check to the index git commits with a real-commit test
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-15T02:02:42Z
updated: 2026-10-15T02:02:42Z
depends: []
tags: []
source: hq-3cdd68
agent: claude-code/claude-opus-5-5
---

The staged-facts check in .githooks/pre-commit copies the index named by `git rev-parse --git-path index` (which honours GIT_INDEX_FILE) and exports the tree it would commit. Reviews of hq-3cdd68 showed that a mutant reading .git/index directly still passes the suite, while a real `git commit -a` then commits an unstaged invalid fact file. Real-commit runs verified the current code by hand only.

Outcome: a test drives `facts_check` with GIT_INDEX_FILE pointing at an alternate index that differs from .git/index (or drives the installed hook through `git commit -a` and `git commit <path>`), and it fails against that mutant.

Also deferred from the same review, optional here: the refusal could note that the fault may already be in HEAD (a --no-verify commit or a merge lands without the hook), and a missing index file raises FileNotFoundError, which is reachable only when the hook is run by hand.
