---
id: hq-1dce70
title: Tighten weak and brittle assertions left in the harness manifest tests
status: done
priority: 2
size: s
complexity: low
process: direct
owner: test/hq-1dce70-manifest-test-assertions
created: 2026-11-01T19:26:19Z
updated: 2026-11-07T12:21:02Z
started: 2026-11-07T12:12:22Z
completed: 2026-11-07T12:20:27Z
closed: 2026-11-07T12:20:27Z
depends: []
tags: [tests]
origin: agent
---

Deferred from hq-2eba07's reviews. (1) The clean-only refresh test asserts no local/live-picks file has 'extra' in its name; assert the set of local/live-picks* names is unchanged instead. (2) The harness-state-clean runpy test builds its scratch manifest by splitting harnesses.toml on a literal header string; build it from parsed data. (3) Pre-commit-level tests cover filter.harness-state.required unset but not 'false' (unit and CLI tests cover false). (4) test_refresh_refuses_when_filter_required_is_unset_or_false now also covers smudge cases; rename it. (5) The live-picks CLI broken-manifest test does not prove the checkout lock was never taken. (6) just test's agents/bin run prints 'WARNING in core: flasgger is not installed'; find its source and silence or satisfy it so gate output is clean.

## Notes

- 2026-11-01T19:26:19Z (add): created
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-07T12:12:22Z (test/hq-1dce70-manifest-test-assertions): started
- 2026-11-07T12:12:46Z (test/hq-1dce70-manifest-test-assertions): trial: flow-trial-1 — enrolled — flow off
- 2026-11-07T12:12:47Z (test/hq-1dce70-manifest-test-assertions): arm: flow-trial-1 — unit tack-1dce70 — flow off
- 2026-11-07T12:20:19Z (test/hq-1dce70-manifest-test-assertions): Focused baseline (policy-off checkout, .tt.toml automatic_broad = false): ran 'just test-one' on the 6 affected test modules before edits (21 passed in 27.02s); deliberately omitted broad 'just test' / 'just ci-test' per .tt.toml policy.
- 2026-11-07T12:20:21Z (test/hq-1dce70-manifest-test-assertions): flow-trial-1: flow off (unit tack-1dce70)
- 2026-11-07T12:20:23Z (test/hq-1dce70-manifest-test-assertions): rework: none
- 2026-11-07T12:20:25Z (test/hq-1dce70-manifest-test-assertions): scope-drift: none
- 2026-11-07T12:20:27Z (test/hq-1dce70-manifest-test-assertions): done
- 2026-11-07T12:20:27Z (test/hq-1dce70-manifest-test-assertions): Tightened harness manifest test assertions across .githooks/test_harness_state_refresh.py (exact live-picks* byte snapshot before/after clean-only refresh; renamed filter required/smudge test), .githooks/test_harness_state_clean.py (TOML parse/serialize instead of string splitting on harnesses.toml), .githooks/test_pre_commit.py and .githooks/test_pre_commit_facts.py (filter.harness-state.required = false coverage), and .githooks/test_live_picks.py (assert local/harness-state.lock is never created on broken-manifest CLI/hook runs), and added -p no:httpbin to justfile and tools/test-suite. Verified with 'just test-one' (24 passed in 33.64s, no flasgger warning) and mandatory 'just check-hygiene' (exit 0).
- 2026-11-07T12:21:02Z (main): Merged test/hq-1dce70-manifest-test-assertions (5c85088a) to main via fast-forward; ran tt-report (focused test-one: 3 runs, 24 passed; check-hygiene: 1 pass; broad test skipped per .tt.toml policy); verified only regenerable local/ directories and __pycache__/.pytest_cache existed in worktree, no host pointers resolved into .worktrees/hq-1dce70, and removed worktree and branch. Nothing pushed; no surviving processes.
