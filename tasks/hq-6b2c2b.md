---
id: hq-6b2c2b
title: Run hq's pre-commit checks on clean non-fast-forward merges with a pre-merge-commit hook
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-15T08:03:38Z
updated: 2026-10-15T08:03:38Z
depends: []
tags: []
source: hq-3cdd68
agent: claude-code/claude-opus-5-5
---

git runs pre-commit for ordinary commits and for a conflicted merge resolved with `git commit`, but a merge that auto-resolves cleanly runs only pre-merge-commit, which .githooks does not define. Review of hq-3cdd68 confirmed it: `git merge --no-ff` of a branch that deletes a probe landed without any check. Two branches that each pass on their own can also merge into a broken pair, for example one moving the fact file and reader default while the other adds a fact or edits the reader. A fast-forward merge creates no commit and runs no hook, but each of its commits already passed pre-commit.

Approach: add .githooks/pre-merge-commit that runs pre-commit's checks (local/ refusal, the docs check, and the staged-tree facts check); git documents pre-merge-commit as taking no arguments, and the index it sees holds the merge result. Test: a clean --no-ff merge that deletes a probe, and one that deletes the fact file, are refused, and a valid clean merge passes. Confirm that `just setup`'s core.hooksPath already covers the new hook, and that the existing post-merge hook is unaffected.

Out of scope: --no-verify commits, which no hook can see.
