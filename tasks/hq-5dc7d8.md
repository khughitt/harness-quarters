---
id: hq-5dc7d8
title: "Test pi live-picks against the pre-change tool pinned at 6b434eb, including an in-flight capture across the rollback"
status: doing
priority: 3
size: s
complexity: mid
process: direct
owner: feat/pi-live-picks
created: 2026-10-15T22:18:54Z
updated: 2026-10-15T23:54:59Z
started: 2026-10-15T23:43:18Z
depends: [hq-031194]
parent: hq-24416e
tags: []
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-10-15-pi-live-picks.md
step: "Task 4: Rollback interleaving test"
---

Step of the hq-24416e plan, Task 4; contract: spec §4.2 case 5 and §5. The pinned commit (not merge-base) keeps the test covering the old tool after this change lands; the interleaving case holds a new-code capture on the lock across the swap to the old hooks, which is the race plan review round 1 reproduced.

## Notes

- 2026-10-15T22:18:58Z (feat/pi-live-picks): gate: scoped — step of hq-24416e plan
- 2026-10-15T23:43:18Z (feat/pi-live-picks): started
  provenance: {"harness_session":"codex:01a141f2-1695-7e12-a1c3-f166c9d338e0","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-15T23:43:28Z (feat/pi-live-picks): arm: flow-trial-1 — unit tack-aa9b44 — flow on
- 2026-10-15T23:43:39Z (feat/pi-live-picks): gate: implementing .worktrees/pi-live-picks — scoped rollback acceptance tests in the existing hydrated worktree
  provenance: {"harness_session":"codex:01a141f2-1695-7e12-a1c3-f166c9d338e0","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-15T23:46:40Z (feat/pi-live-picks): Task 4 scope: test-only acceptance in .githooks/test_live_picks.py, reusing the real temporary-repository fixture; no production, caller, export, or host changes. RED: scratch snapshots only, pi copied into old record makes all four pinned-command cases fail, and unconditional record rewrite makes interleaving fail on old-record byte equality. GREEN: unmodified tool passes all 5 new cases (133 deselected). Full just test is tracked and running; no production gaps found.
- 2026-10-15T23:51:45Z (feat/pi-live-picks): Task 4 implementation committed as 21cce44 (test-only). Self-review: no findings; controller review still required. just test exit 0: 228 agent-tool tests plus 892 hook/tool tests; final focused run 5 passed. git diff --check and tasks check exit 0. RED mutation evidence and synchronization proof are in .superpowers/sdd/2026-10-15-pi-live-picks/task-4-report.md. host-load --section session reports nothing left running.
- 2026-10-15T23:51:45Z (feat/pi-live-picks): parked (waiting on agent): Controller: review commit 21cce44 and task-4-report.md in .worktrees/pi-live-picks, then record the implementation review and verified gate before closing Task 4.
  provenance: {"harness_session":"codex:01a141f2-1695-7e12-a1c3-f166c9d338e0","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-15T23:52:22Z (feat/pi-live-picks): resumed
  provenance: {"harness_session":"codex:01a141b5-89d5-7b72-89c2-3be2a208354f","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-15T23:54:58Z (feat/pi-live-picks): review: impl round 1 — verdict: revise; findings: Important 1; reviewer: codex
- 2026-10-15T23:54:59Z (feat/pi-live-picks): parked (waiting on agent): Original implementer fixes owned subprocess-group cleanup for timeout and interruption in Task 4; controller then dispatches fresh scoped re-review in .worktrees/pi-live-picks
  provenance: {"harness_session":"codex:01a141b5-89d5-7b72-89c2-3be2a208354f","harness_session_source":"CODEX_THREAD_ID"}
