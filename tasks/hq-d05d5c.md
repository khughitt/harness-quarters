---
id: hq-d05d5c
title: session-episodes and rename-cutover read records from the records field of tasks projects
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: hq-d05d5c-records-readers
created: 2026-10-22T20:55:57Z
updated: 2026-10-23T11:56:40Z
started: 2026-10-23T11:42:30Z
depends: [tasks-211e28]
tags: []
source: tasks-dc16eb
agent: claude-code/claude-fable-5-1
---

tasks:docs/specs/2026-10-22-records-home-design.md §4, §7.4. session-episodes lists worktrees of root and reads <wt>/tasks/<id>.md, requiring root/tasks; read the one copy under records (trial measurement: land kind-aware, a no-op for in-tree, before any project detaches). rename-cutover takes records for the record and tasks/files paths.

## Notes

- 2026-10-22T20:58:18Z (main): hq-5a3e12 was closed with the ruling on 2026-10-22 by the design session; this piece is the two reader changes only.
- 2026-10-23T11:42:30Z (main): started
  provenance: {"harness_session":"claude-code:f7a1ba88-e38e-4353-b879-b62ae0b89719","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T11:43:06Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-10-23T11:43:09Z (main): arm: flow-trial-1 — unit tack-d05d5c — flow off
- 2026-10-23T11:43:23Z (hq-d05d5c-records-readers): resumed
  provenance: {"harness_session":"claude-code:f7a1ba88-e38e-4353-b879-b62ae0b89719","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T11:56:40Z (hq-d05d5c-records-readers): baseline: just test in .worktrees/hq-d05d5c-records-readers exit 0 (stages: 1024 passed, 389 passed, 1 passed)
