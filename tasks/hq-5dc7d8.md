---
id: hq-5dc7d8
title: "Test pi live-picks against the pre-change tool pinned at 6b434eb, including an in-flight capture across the rollback"
status: todo
priority: 3
size: s
complexity: mid
process: direct
created: 2026-10-15T22:18:54Z
updated: 2026-10-15T22:26:59Z
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
