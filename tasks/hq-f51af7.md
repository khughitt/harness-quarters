---
id: hq-f51af7
title: Probe the pick lifecycle in scratch homes
status: done
priority: 2
size: s
complexity: mid
process: direct
owner: live-model-preservation
created: 2026-10-10T15:31:15Z
updated: 2026-10-10T15:47:25Z
started: 2026-10-10T15:36:00Z
completed: 2026-10-10T15:47:23Z
depends: []
parent: hq-a77096
tags: []
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-10-10-live-model-preservation.md
step: "Task 1: Probe the pick lifecycle in scratch homes"
---

Outcome: probe model event ordering and reset behavior in isolated scratch homes. Approach and verification: approved plan Task 1; supervised private tmux server with cleanup, credential-free evidence, capability validation and just test.

## Notes

- 2026-10-10T15:36:00Z (live-model-preservation): started
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-10T15:36:05Z (live-model-preservation): arm: flow-trial-1 — unit tack-a77096 — flow on
- 2026-10-10T15:36:59Z (live-model-preservation): gate: scoped — adopted approved plan Task 1
- 2026-10-10T15:36:59Z (live-model-preservation): gate: implementing .worktrees/live-model-preservation
- 2026-10-10T15:41:14Z (live-model-preservation): attached: hq-probe-evidence-portable.txt (9402 bytes): Scratch-home picker settings and hook-time evidence; credential-free with portable path labels
- 2026-10-10T15:41:24Z (live-model-preservation): probe: Claude 2.1.296 model event ordering false; reset clears fields true. Codex 0.162.1 reset clears fields false. Probe supervisor exited; private tmux server and scratch homes removed.
- 2026-10-10T15:43:55Z (live-model-preservation): review: impl round 1 — verdict: revise; findings: Important 1, Minor 1; reviewer: codex
- 2026-10-10T15:43:55Z (live-model-preservation): cleanup correction: absence check initially passed but Codex pid 2249705 survived TUI exit and recreated cache/lock directories; supervisor did not reap that descendant; cleaning the recorded probe process before final verification
- 2026-10-10T15:46:33Z (live-model-preservation): review: impl round 2 — verdict: accept; findings: Minor 1; reviewer: codex
- 2026-10-10T15:46:53Z (live-model-preservation): gate: verified tree:3bca60f8160eafe584d4716a563e619fe0072e02 — checks: just test 793 passed + harness-facts check passed + probe process and scratch absence verified; review: minor deferred stale socket check must be fixed before supervisor reuse; reviewer: codex
- 2026-10-10T15:46:53Z (live-model-preservation): retro: Scratch probes falsified the event-ordering prerequisite before hook code changed. Independent review caught an orphan Codex writer; stopped it and verified cleanup again. Tooling feedback: flows-6a19a1.
- 2026-10-10T15:47:23Z (live-model-preservation): gate: verified tree:3bca60f8160eafe584d4716a563e619fe0072e02 — checks: just test 793 passed + harness-facts check passed + probe process and scratch absence verified; review: minor deferred stale socket check must be fixed before supervisor reuse; reviewer: codex/unknown
- 2026-10-10T15:47:23Z (live-model-preservation): retro: Independent review caught the late writer and verified cleanup; flow requires a model slot in the gate so unknown explicitly marks unavailable model identity. Feedback: flows-6a19a1 and flows-59bd6b.
- 2026-10-10T15:47:23Z (live-model-preservation): done
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-10T15:47:23Z (live-model-preservation): Probed Claude pre-write event ordering (false), Claude reset clearing fields (true), Codex reset clearing fields (false); recorded raw evidence and facts; 793 tests passed. Prerequisite failed, so implementation remains blocked on revised spec review.
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
