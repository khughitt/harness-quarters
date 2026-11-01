---
id: hq-e8f2db
title: "Add harnesses.toml manifest and shared harness_state loader, cleaners, and checks"
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: feat/hq-2eba07-harness-manifest
created: 2026-11-01T12:36:07Z
updated: 2026-11-01T18:20:11Z
started: 2026-11-01T13:37:20Z
depends: []
parent: hq-2eba07
tags: [hooks]
agent: agy
origin: agent
plan: docs/plans/2026-11-01-harness-manifest.md
step: "Task 1: Root harnesses.toml and shared harness_state loader, cleaners, and checks"
---

Step 1 of hq-2eba07 plan (spec §5.1-§5.2, §5.3.6): create root harnesses.toml and extend .githooks/harness_state.py with ManifestError, LiveStateSpec, load_manifest, check_gitattributes, check_filter_config, check_clean_tree, pure JSON/TOML cleaners, and CLI check.

## Notes

- 2026-11-01T12:36:07Z (add): created
  provenance: {"origin":"agent"}
- 2026-11-01T13:37:20Z (feat/hq-2eba07-harness-manifest): started
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T13:57:37Z (feat/hq-2eba07-harness-manifest): review: impl round 1 — verdict: accept; findings: minor 6; reviewer: claude-code/claude-sonnet-5-5
- 2026-11-01T14:10:30Z (feat/hq-2eba07-harness-manifest): review: impl round 2 — verdict: accept; findings: none; reviewer: claude-code/claude-haiku-5-5
- 2026-11-01T14:10:32Z (feat/hq-2eba07-harness-manifest): done
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T14:10:32Z (feat/hq-2eba07-harness-manifest): Task 1 complete: harnesses.toml + harness_state loader/checks/cleaners (254ad152, fix b8cf2b71). Verification: test_harness_manifest.py 63 passed; just test rc=0 (247, 1289, 391, 1 passed); ops-check, ops-docs check, harness-facts check, tasks check exit 0. Task review accepted (sonnet) with 2 minors re-graded Important and fixed; re-review clean (haiku). Deferred minors and rulings in SDD ledger .worktrees/hq-2eba07/.superpowers/sdd/2026-11-01-harness-manifest/progress.md. Nothing pushed.
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T18:20:11Z (feat/hq-2eba07-harness-manifest): resumed
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
