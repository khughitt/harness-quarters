---
id: hq-aea33f
title: Pin the staged-facts pre-commit check to the index git commits with a real-commit test
status: done
priority: 3
size: xs
complexity: low
process: direct
owner: test/hq-aea33f-staged-facts-index
created: 2026-10-15T02:02:42Z
updated: 2026-11-07T16:09:47Z
started: 2026-11-07T16:00:43Z
completed: 2026-11-07T16:09:47Z
closed: 2026-11-07T16:09:47Z
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
- 2026-11-07T16:09:41Z (test/hq-aea33f-staged-facts-index): review: impl round 1 — verdict: accept; findings: none; reviewer: agy
- 2026-11-07T16:09:43Z (test/hq-aea33f-staged-facts-index): gate: verified tree:563315741856631b2b1f9db8d7f5a3260de996c9 — checks: just test-one .githooks/test_pre_commit_facts.py .githooks/test_pre_commit.py -n auto (56 passed), just check-hygiene; review: none; reviewer: agy
- 2026-11-07T16:09:45Z (test/hq-aea33f-staged-facts-index): retro: rounds: 0 spec, 0 plan, 1 impl; checks-missed: none; drift: none; friction: none
- 2026-11-07T16:09:47Z (test/hq-aea33f-staged-facts-index): done
- 2026-11-07T16:09:47Z (test/hq-aea33f-staged-facts-index): Added test_facts_check_and_real_commits_follow_the_committed_index in .githooks/test_pre_commit_facts.py driving both facts_check with GIT_INDEX_FILE pointing at an alternate index and the installed pre-commit hook through git commit -a and git commit <path> (verified to fail against the .git/index mutant), plus test_missing_index_file_fails_cleanly_without_traceback and missing-index/HEAD-fault diagnostics in .githooks/pre-commit. Focused baseline: just test-one .githooks/test_pre_commit_facts.py -n auto (36 passed; broad baseline omitted per .tt.toml policy-off checkout). Verified with just test-one .githooks/test_pre_commit_facts.py .githooks/test_pre_commit.py -n auto (56 passed) and just check-hygiene. Disclosures: nothing pushed; no surviving processes; others' work untouched; branch test/hq-aea33f-staged-facts-index merged fast-forward into local main and worktree .worktrees/hq-aea33f removed.
