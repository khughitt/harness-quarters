---
id: hq-ead668
title: "live-picks capture, restore, sync and forget"
status: done
priority: 2
size: m
complexity: mid
process: direct
owner: live-model-preservation
created: 2026-10-10T15:31:15Z
updated: 2026-10-10T16:24:33Z
started: 2026-10-10T16:05:08Z
completed: 2026-10-10T16:24:30Z
depends: [hq-7fd822]
parent: hq-a77096
tags: []
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-10-10-live-model-preservation.md
step: "Task 3: `live-picks` capture, restore, sync and forget"
---

Outcome: live-picks capture/restore/sync/forget/hook implement the saved-pick record and all-absent restoration rule. Follow revised plan Task 3; only forget records default, preserve parsed values and filter output, prove direct behavior RED→GREEN, and run just test.

## Notes

- 2026-10-10T16:05:08Z (live-model-preservation): started
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-10T16:05:12Z (live-model-preservation): arm: flow-trial-1 — unit tack-a77096 — flow on
- 2026-10-10T16:05:12Z (live-model-preservation): gate: scoped — adopted approved plan Task 3
- 2026-10-10T16:05:12Z (live-model-preservation): gate: implementing .worktrees/live-model-preservation
- 2026-10-10T16:13:56Z (live-model-preservation): review: impl round 1 — verdict: revise; findings: Important 1; reviewer: codex
- 2026-10-10T16:24:30Z (live-model-preservation): review: impl round 2 — verdict: accept; findings: Minor 1; reviewer: codex
- 2026-10-10T16:24:30Z (live-model-preservation): gate: verified tree:4327d9a3283bb81f2c072ff982c85e2f3af8ad7c — checks: just test 839 passed and isolation regressions plus error-handler mutation RED to GREEN; review: minor deferred invalid UTF8 record diagnostic omits record path and recovery guidance; reviewer: codex/unknown
- 2026-10-10T16:24:30Z (live-model-preservation): retro: Broad planned cases passed but review found filesystem failures aborting the healthy file. Five targeted cases reproduced it; per-file refusals now preserve healthy capture and restaging. The filesystem-error assertion was also proven against a targeted handler mutation.
- 2026-10-10T16:24:30Z (live-model-preservation): done
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-10T16:24:30Z (live-model-preservation): Implemented capture/restore/sync/forget/hook with filter-owned fields and one host lock; isolated live-file failures, preserved healthy captures and hook restaging; regression and mutation tests RED to GREEN, 839 tests passed, fresh review accepted with one deferred minor diagnostic.
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
