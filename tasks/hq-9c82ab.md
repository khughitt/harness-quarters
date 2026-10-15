---
id: hq-9c82ab
title: "Write the pi harness-state extension and probe its loading, shutdown bound and picker-event ordering"
status: todo
priority: 3
size: s
complexity: mid
process: direct
created: 2026-10-15T22:18:53Z
updated: 2026-10-15T22:18:56Z
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
