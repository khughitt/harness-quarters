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
updated: 2026-10-16T00:07:01Z
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
- 2026-10-15T23:55:20Z (feat/pi-live-picks): resumed
  provenance: {"harness_session":"codex:01a141f2-1695-7e12-a1c3-f166c9d338e0","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-15T23:58:34Z (feat/pi-live-picks): Corrective round 1: addressed Important I1 with a test-only owned_process context for all new rollback capture/refresh/runner calls. Each starts a new session and always SIGKILLs its process group, including after leader exit, while the Popen context reaps its direct child and SIGTERM handling restores on exit. RED cleanup regression: 4 failed for surviving descendants under timeout/SIGINT/SIGTERM/leader-exit; GREEN focused: 9 passed. Real descendant probe adopts and reaps its own orphans even on RED. Full just test is tracked; raw logs are in the plan workspace.
- 2026-10-16T00:05:11Z (feat/pi-live-picks): Corrective round 1 committed as 8484599: I1 process-group ownership addressed and self-reviewed. Final scratch RED: all 4 cleanup modes fail on surviving descendants under direct-child-only mutation; final focused GREEN 9 passed. Full just test exit 0: 228 agent-tool tests and 896 hook/tool tests. git diff --check and tasks check pass. Full raw logs and exact evidence appended to task-4-report.md. host-load reports nothing left running; controller owns fresh scoped re-review.
- 2026-10-16T00:05:12Z (feat/pi-live-picks): parked (waiting on agent): Controller: dispatch fresh scoped re-review of I1 fix commit 8484599 in .worktrees/pi-live-picks against task-4-report.md and raw cleanup logs, then record the ruling and verified gate if accepted.
  provenance: {"harness_session":"codex:01a141f2-1695-7e12-a1c3-f166c9d338e0","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-16T00:05:47Z (feat/pi-live-picks): resumed
  provenance: {"harness_session":"codex:01a141b5-89d5-7b72-89c2-3be2a208354f","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-16T00:06:49Z (feat/pi-live-picks): review: impl round 2 — verdict: accept; findings: none; reviewer: codex
- 2026-10-16T00:07:00Z (feat/pi-live-picks): gate: verified tree:de171a4794aeef9c0f24117c1c834964e058641a — checks: just test exit 0 with 228 agent tests and 896 hook-tool tests plus nine rollback-cleanup focused tests and targeted scratch mutation failures; review: important addressed owned subprocess groups and direct-child reaping on timeout or interruption; reviewer: codex
- 2026-10-16T00:07:00Z (feat/pi-live-picks): retro: A nonblocking-flock handshake proved new code was loaded before rollback without timing guesses. Fresh review found timeout cleanup needed full process groups; real descendant regressions proved timeout and interrupt paths before the green suite and scoped acceptance.
