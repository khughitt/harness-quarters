---
id: hq-6b2c2b
title: Run hq's pre-commit checks on clean non-fast-forward merges with a pre-merge-commit hook
status: done
priority: 3
size: xs
complexity: low
process: direct
owner: feat/hq-6b2c2b-pre-merge-commit
created: 2026-10-15T08:03:38Z
updated: 2026-11-07T16:47:46Z
started: 2026-11-07T16:40:18Z
completed: 2026-11-07T16:47:44Z
closed: 2026-11-07T16:47:44Z
depends: []
tags: []
source: hq-3cdd68
agent: claude-code/claude-opus-5-5
---

git runs pre-commit for ordinary commits and for a conflicted merge resolved with `git commit`, but a merge that auto-resolves cleanly runs only pre-merge-commit, which .githooks does not define. Review of hq-3cdd68 confirmed it: `git merge --no-ff` of a branch that deletes a probe landed without any check. Two branches that each pass on their own can also merge into a broken pair, for example one moving the fact file and reader default while the other adds a fact or edits the reader. A fast-forward merge creates no commit and runs no hook, but each of its commits already passed pre-commit.

Approach: add .githooks/pre-merge-commit that runs pre-commit's checks (local/ refusal, the docs check, and the staged-tree facts check); git documents pre-merge-commit as taking no arguments, and the index it sees holds the merge result. Test: a clean --no-ff merge that deletes a probe, and one that deletes the fact file, are refused, and a valid clean merge passes. Confirm that `just setup`'s core.hooksPath already covers the new hook, and that the existing post-merge hook is unaffected.

Out of scope: --no-verify commits, which no hook can see.

## Notes

- 2026-11-07T16:40:18Z (main): started
- 2026-11-07T16:40:20Z (feat/hq-6b2c2b-pre-merge-commit): resumed
- 2026-11-07T16:40:44Z (feat/hq-6b2c2b-pre-merge-commit): trial: flow-trial-1 — enrolled — flow on
- 2026-11-07T16:40:46Z (feat/hq-6b2c2b-pre-merge-commit): arm: flow-trial-1 — unit tack-6b2c2b — flow on
- 2026-11-07T16:41:13Z (feat/hq-6b2c2b-pre-merge-commit): gate: scoped — adopted
- 2026-11-07T16:41:15Z (feat/hq-6b2c2b-pre-merge-commit): gate: implementing .worktrees/hq-6b2c2b
- 2026-11-07T16:47:39Z (feat/hq-6b2c2b-pre-merge-commit): review: impl round 1 — verdict: accept; findings: none; reviewer: agy/subagent
- 2026-11-07T16:47:41Z (feat/hq-6b2c2b-pre-merge-commit): gate: verified tree:f9703222172dc4199299e854a3171912a2406d37 — checks: just test-one .githooks/test_pre_commit_facts.py .githooks/test_pre_commit.py -n auto (57 passed), just check-hygiene exit 0; review: none; reviewer: agy/subagent session:agy:ea546a60-3279-4ce1-b021-2afbc815a462
- 2026-11-07T16:47:44Z (feat/hq-6b2c2b-pre-merge-commit): done
- 2026-11-07T16:47:44Z (feat/hq-6b2c2b-pre-merge-commit): Added executable .githooks/pre-merge-commit delegating to .githooks/pre-commit so clean non-fast-forward merges run local/ refusal, ops-check, ops-docs check, and staged-tree harness-facts and harness_state.py checks against the merge result in the index. Confirmed just setup's core.hooksPath .githooks covers the new hook and post-merge continues to run after successful merges. Added test_clean_no_ff_merges_are_checked_by_pre_merge_commit in .githooks/test_pre_commit_facts.py covering probe deletion refusal, fact-file deletion refusal, valid merge pass, and post-merge execution. Focused baseline in policy-off checkout: 56 passed before changes, 57 passed after changes; broad baseline omitted by policy. Verified with just test-one and just check-hygiene. Dispositions: nothing pushed; no surviving processes; others' work untouched; branch merged to local main and worktree removed.
- 2026-11-07T16:47:46Z (feat/hq-6b2c2b-pre-merge-commit): retro: clean
