---
id: hq-9c82ab
title: "Write the pi harness-state extension and probe its loading, shutdown bound and picker-event ordering"
status: doing
priority: 3
size: s
complexity: mid
process: direct
owner: feat/pi-live-picks
created: 2026-10-15T22:18:53Z
updated: 2026-10-15T22:44:09Z
started: 2026-10-15T22:44:02Z
depends: []
parent: hq-24416e
tags: []
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-10-15-pi-live-picks.md
step: "Task 1: The pi extension and its probes"
---

Step of the hq-24416e plan (docs/plans/2026-10-15-pi-live-picks.md, Task 1); contract: spec docs/specs/2026-10-15-pi-live-picks-design.md §3.3 and §4.1. The probes decide whether the picker handlers stay (P2), so they run before Task 2 builds on the extension.

## Notes

- 2026-10-15T22:18:56Z (feat/pi-live-picks): gate: scoped — step of hq-24416e plan
- 2026-10-15T22:44:02Z (feat/pi-live-picks): started
  provenance: {"harness_session":"codex:01a141b8-aa66-7ee2-aad3-a00ba1296a0c","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-15T22:44:09Z (feat/pi-live-picks): arm: flow-trial-1 — unit tack-aa9b44 — flow on
