---
id: hq-4bff46
title: "Replica config key, lock wait and live-source boundary"
status: doing
priority: 1
size: s
complexity: low
process: direct
owner: feat/hq-adfed6-archive-replica
created: 2026-11-08T10:24:44Z
updated: 2026-11-08T11:18:43Z
started: 2026-11-08T11:11:42Z
depends: []
parent: hq-adfed6
tags: []
agent: claude-code/claude-opus-5-5
origin: agent
plan: docs/plans/2026-11-08-session-archive-replica.md
step: "Task 1: Configuration, lock wait and the live-source boundary"
---

Scope: plan docs/plans/2026-11-08-session-archive-replica.md, section 'Task 1: Configuration, lock wait and the live-source boundary', against spec docs/specs/2026-11-07-session-archive-replica-design.md revision e46d5e87. Done: that section's code and tests, focused just test-one runs seen RED then GREEN, just check-hygiene clean, committed on feat/hq-adfed6-archive-replica in .worktrees/hq-adfed6. Why the details matter is stated inline in the plan section; keep them.

## Notes

- 2026-11-08T10:24:44Z (add): created
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-08T10:24:47Z (feat/hq-adfed6-archive-replica): gate: scoped — step of hq-adfed6 plan
  provenance: {"harness_session":"claude-code:e67b959b-22b0-46a4-8c00-24ed459c426d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T11:11:42Z (feat/hq-adfed6-archive-replica): started
- 2026-11-08T11:12:06Z (feat/hq-adfed6-archive-replica): arm: flow-trial-1 — unit tack-adfed6 — flow on
- 2026-11-08T11:12:08Z (feat/hq-adfed6-archive-replica): gate: implementing .worktrees/hq-adfed6
- 2026-11-08T11:18:43Z (feat/hq-adfed6-archive-replica): review: impl round 1 — verdict: accept; findings: none; reviewer: agy/gemini-4-argon
- 2026-11-08T11:18:43Z (feat/hq-adfed6-archive-replica): gate: verified tree:30b503e13d957a36cc3a785edcf7867dd68e1286 — checks: just test-one tools/test_session_archive_config.py 22 passed and targeted break failed 2/2 and just check-hygiene clean; review: none; reviewer: agy/gemini-4-argon session:agy:9001347e-70cf-4191-9c42-b30078dada85
- 2026-11-08T11:18:43Z (feat/hq-adfed6-archive-replica): retro: [verified] Separating load_config's replica_root parsing from filesystem stat checks kept the unmounted-replica boundary simple and fast to test.
- 2026-11-08T11:18:43Z (feat/hq-adfed6-archive-replica): closeout: focused scope just test-one tools/test_session_archive_config.py (22 passed); mandatory checks just check-hygiene clean; broad suite just test skipped per .tt.toml automatic_broad = false; remote evidence none; retained items none owned by hq-4bff46 (worktree and plan workspace remain owned by open parent hq-adfed6)
