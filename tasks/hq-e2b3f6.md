---
id: hq-e2b3f6
title: Backfill complexity ratings for open tasks
status: done
priority: "2"
size: xs
complexity: high
process: direct
owner: main
created: 2026-09-12T15:09:51Z
updated: 2026-09-16T14:12:02Z
started: 2026-09-16T14:11:55Z
completed: 2026-09-16T14:12:02Z
depends: []
tags: []
source: tasks-be447b
model: "claude-opus-5[1m]"
---

Rate every open scoped task in this project — status todo, doing, or blocked; ideas are rated when they are scoped, not before — plus any recurring task (`tasks list --periodic`), with the rubric in the tasks skill: low = approach established, relevant context identified, correctness has a clear check; mid = bounded investigation or implementation choices remain, scope and acceptance criteria clear; high = substantial discovery, subtle reasoning about interacting behaviour, or an unresolved architectural call. Read each task body, its notes, and any linked spec or plan first, and rate the judgment that remains after that preparation — not the size: a large mechanical change is low, a one-line subtle fix can be high. `tasks list --status todo --status doing --status blocked` lists the set; `tasks edit <id> --complexity <level>` sets each. Done when `tasks ready --max-complexity high` reports no "unassessed hidden" warning. Rated high itself because rating is judgment work reserved for a frontier session (tasks docs/specs/2026-09-12-task-complexity-design.md §3.3); it must not be picked under a cutoff.

## Notes

- 2026-09-16T14:11:55Z (main): Process direct: record maintenance only, the rubric is in the skill and the check is the ready warning.
- 2026-09-16T14:12:02Z (main): Rated ai-5b72de low; every other open scoped task already carried a rating. ready --max-complexity high reports no unassessed warning.
