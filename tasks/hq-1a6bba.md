---
id: hq-1a6bba
title: "Migrate harness-state-clean, harness-state-refresh, and codex-trust to harnesses.toml"
status: todo
priority: 2
size: s
complexity: mid
process: direct
owner: feat/hq-2eba07-harness-manifest
created: 2026-11-01T13:14:43Z
updated: 2026-11-01T18:20:13Z
started: 2026-11-01T15:38:31Z
depends: [hq-f5ccb6]
parent: hq-2eba07
tags: [hooks]
agent: agy
origin: agent
plan: docs/plans/2026-11-01-harness-manifest.md
step: "Task 4: Migrate harness-state-clean, harness-state-refresh, and codex-trust to harnesses.toml"
---

Step 4 of hq-2eba07 plan (spec §5.3.1-§5.3.3): drive .githooks/{harness-state-clean,harness-state-refresh,codex-trust} from harnesses.toml via harness_state.py, preserving CLAUDE_JSON_KEYS re-export until hq-7e1e9c and deferring manifest loading in refresh and codex-trust hook mode.

## Notes

- 2026-11-01T13:14:43Z (add): created
  provenance: {"origin":"agent"}
- 2026-11-01T15:38:31Z (feat/hq-2eba07-harness-manifest): started
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T16:44:22Z (feat/hq-2eba07-harness-manifest): review: impl round 1 — verdict: accept; findings: Minor 3; reviewer: claude-code/claude-sonnet-5-5
- 2026-11-01T16:44:23Z (feat/hq-2eba07-harness-manifest): done
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T16:44:23Z (feat/hq-2eba07-harness-manifest): Task 4 complete: d725843f; harness-state-clean, harness-state-refresh and codex-trust driven by harnesses.toml. Verification: RED 7 failed before change; focused .githooks + relay_cutover 733 passed; just test rc=0 (247+1321+391+1 passed); ops-check, ops-docs check, harness-facts check, tasks check clean. Review round 1 accept (sonnet-5-5), 3 minors deferred in plan ledger.
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
