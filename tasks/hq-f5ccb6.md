---
id: hq-f5ccb6
title: Migrate live-picks to harnesses.toml
status: done
priority: 2
size: m
complexity: mid
process: direct
owner: feat/hq-2eba07-harness-manifest
created: 2026-11-01T12:36:37Z
updated: 2026-11-01T15:38:29Z
started: 2026-11-01T14:41:56Z
completed: 2026-11-01T15:38:29Z
closed: 2026-11-01T15:38:29Z
depends: [hq-bfef03]
parent: hq-2eba07
tags: [hooks]
agent: agy
origin: agent
plan: docs/plans/2026-11-01-harness-manifest.md
step: "Task 3: Migrate live-picks to harnesses.toml"
---

Step 3 of hq-2eba07 plan (spec §5.3.4): check main for hq-ece26a, copy harnesses.toml into live-picks scratch fixtures, and drive .githooks/live-picks from harnesses.toml via harness_state.py with lazy usage(), deferred pre-lock loading in hook mode, multi-unit TOML support, clean-only skipping, LiveStateSpec adopt_detached, and 6b434eb rollback byte parity.

## Notes

- 2026-11-01T12:36:37Z (add): created
  provenance: {"origin":"agent"}
- 2026-11-01T14:41:56Z (feat/hq-2eba07-harness-manifest): started
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T15:19:09Z (feat/hq-2eba07-harness-manifest): review: impl round 1 — verdict: accept; findings: minor 5; reviewer: claude-code/claude-opus-5-5
- 2026-11-01T15:38:28Z (feat/hq-2eba07-harness-manifest): review: impl round 2 — verdict: accept; findings: none; reviewer: claude-code/claude-haiku-5-5
- 2026-11-01T15:38:29Z (feat/hq-2eba07-harness-manifest): done
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T15:38:29Z (feat/hq-2eba07-harness-manifest): Task 3 complete: live-picks driven by harnesses.toml with multi-unit TOML, no runpy (ee7ce1c9, fix 7bcba063). Verification: test_live_picks 182 passed; just test rc=0 (247, 1314, 391, 1 passed); ops-check, ops-docs check, harness-facts check, tasks check exit 0. Task review (opus) accepted, 1 minor re-graded Important (rollback test must delete harnesses.toml to guard load-before-lock) fixed with RED/GREEN; re-review clean (haiku). hq-ece26a sequencing: HEAD..main touched no .githooks/live-picks, no merge needed. Deferred minors in SDD ledger. Nothing pushed.
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
