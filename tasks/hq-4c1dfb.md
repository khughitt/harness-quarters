---
id: hq-4c1dfb
title: Close remaining traceback and reporting gaps in harness-state hooks
status: done
priority: 2
size: s
complexity: low
process: direct
owner: fix/hq-4c1dfb-hook-reporting
created: 2026-11-01T19:26:16Z
updated: 2026-11-07T12:12:06Z
started: 2026-11-07T12:00:05Z
completed: 2026-11-07T12:11:39Z
closed: 2026-11-07T12:11:39Z
depends: []
tags: [hooks]
origin: agent
---

Deferred from hq-2eba07's reviews (ledger attached there). On the live hook surface, under filter.harness-state.required = true: (1) .githooks/harness-state-clean main() reads stdin outside its error handling, so a non-UTF-8 config still ends in a traceback instead of 'harness-state-clean: <path>: <problem>'. (2) .githooks/pre-commit staged_checks() runs facts_check(tree) or manifest_check(...), so a facts failure hides every manifest/filter problem until the next commit attempt; run both and combine. (3) pre-commit's export-failure message embeds the checkout-index command, including the temporary --prefix path, on stderr. Each needs a focused test asserting the named message and no Traceback.

## Notes

- 2026-11-01T19:26:16Z (add): created
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-07T12:00:05Z (fix/hq-4c1dfb-hook-reporting): started
- 2026-11-07T12:00:29Z (fix/hq-4c1dfb-hook-reporting): trial: flow-trial-1 — enrolled — flow off
- 2026-11-07T12:00:31Z (fix/hq-4c1dfb-hook-reporting): arm: flow-trial-1 — unit tack-4c1dfb — flow off
- 2026-11-07T12:11:31Z (fix/hq-4c1dfb-hook-reporting): Focused baseline (policy-off checkout, .tt.toml automatic_broad = false): ran 'just test-one .githooks/test_harness_state_clean.py .githooks/test_pre_commit_facts.py' before code changes (63 passed in 38.57s); deliberately omitted broad 'just test' / 'just ci-test' per .tt.toml policy.
- 2026-11-07T12:11:33Z (fix/hq-4c1dfb-hook-reporting): flow-trial-1: flow off (unit tack-4c1dfb)
- 2026-11-07T12:11:35Z (fix/hq-4c1dfb-hook-reporting): rework: none
- 2026-11-07T12:11:37Z (fix/hq-4c1dfb-hook-reporting): scope-drift: none
- 2026-11-07T12:11:39Z (fix/hq-4c1dfb-hook-reporting): done
- 2026-11-07T12:11:39Z (fix/hq-4c1dfb-hook-reporting): Landed in 4530e9aa on fix/hq-4c1dfb-hook-reporting: moved harness-state-clean stdin UTF-8 decode inside ValueError handler; changed pre-commit staged_checks() to run both facts_check and manifest_check over one export; stripped staged-tree-* temporary paths from with_staged_tree() export error messages. Verified RED (4 failed) -> GREEN ('just test-one .githooks/test_harness_state_clean.py .githooks/test_pre_commit_facts.py .githooks/test_pre_commit.py': 84 passed in 43.89s) and mandatory 'just check-hygiene' (exit 0).
- 2026-11-07T12:12:06Z (main): Merged fix/hq-4c1dfb-hook-reporting (4530e9aa) to main via fast-forward; ran tt-report (focused test-one: 2 runs, 84 passed; check-hygiene: 1 pass; broad test skipped per .tt.toml policy); verified only regenerable local/ directories and __pycache__/.pytest_cache existed in worktree, no host pointers resolved into .worktrees/hq-4c1dfb, and removed worktree and branch. Nothing pushed; no surviving processes.
