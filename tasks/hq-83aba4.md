---
id: hq-83aba4
title: Docs for model pick preservation
status: done
priority: 2
size: xs
complexity: low
process: direct
owner: live-model-preservation
created: 2026-10-10T15:31:15Z
updated: 2026-10-10T17:55:24Z
started: 2026-10-10T17:31:18Z
completed: 2026-10-10T17:55:22Z
depends: [hq-dc9182]
parent: hq-a77096
tags: []
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-10-10-live-model-preservation.md
step: "Task 6: Docs"
---

Outcome: docs explain Stop capture, forget-only resets, picker reset limitations and the shared host lock. Follow revised plan Task 6; use recorded facts, run just test and tools/ops-docs check.

## Notes

- 2026-10-10T17:31:18Z (live-model-preservation): started
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-10T17:31:23Z (live-model-preservation): arm: flow-trial-1 — unit tack-a77096 — flow on
- 2026-10-10T17:31:23Z (live-model-preservation): gate: scoped — adopted approved plan Task 6
- 2026-10-10T17:31:23Z (live-model-preservation): gate: implementing .worktrees/live-model-preservation
- 2026-10-10T17:46:24Z (live-model-preservation): review: impl round 1 — verdict: accept; findings: none; reviewer: codex/gpt-6-astra
- 2026-10-10T17:55:22Z (live-model-preservation): gate: verified tree:b9c255776c4877b0d60e85e24aa73c048f452ae4 — checks: just test 878 passed and tools/ops-docs check passed and git diff --check passed; review: none; reviewer: codex/gpt-6-astra
- 2026-10-10T17:55:22Z (live-model-preservation): retro: Documentation names the observed Stop capture window and forget-only resets rather than promising picker-event recovery. Probe evidence and fresh whole-branch review kept the operational guidance aligned with the implementation.
- 2026-10-10T17:55:22Z (live-model-preservation): done
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-10T17:55:22Z (live-model-preservation): Docs shipped: preservation, Stop capture, forget resets and shared host lock; fresh review accepted; just test 878 passed and ops-docs check passed.
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
