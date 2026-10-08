---
id: hq-eb4f24
title: Remove the capability facts consumer mirror
status: doing
priority: 1
size: s
complexity: low
process: direct
owner: main
created: 2026-10-08T18:06:50Z
updated: 2026-10-08T18:07:55Z
started: 2026-10-08T18:07:49Z
depends: []
tags: []
source: tasks-468bc7
agent: codex
---

Execute Task 2 of the approved tasks claim-guard-policy plan. Remove the temporary consumer mirror from pre-commit, tests, recipe and README; retain validation of the staged facts blob, rejection of invalid staged data, and local-state protections. No capability value or native wiring change. Isolated hq worktree and just test required. Commit separately for ordered approved activation.

## Notes

- 2026-10-08T18:07:49Z (main): started
  provenance: {"harness_session":"codex:01a11bed-fe69-7060-9c93-813a4949349b","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-08T18:07:54Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-08T18:07:54Z (main): arm: flow-trial-1 — unit tack-eb4f24 — flow on
