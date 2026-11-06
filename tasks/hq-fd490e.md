---
id: hq-fd490e
title: Activate the reviewed layout and account for adoption
status: blocked
priority: 2
size: s
complexity: mid
process: direct
created: 2026-11-06T02:19:55Z
updated: 2026-11-06T04:50:57Z
depends: [hq-7930ee]
parent: hq-b77d0c
tags: []
agent: codex
origin: agent
spec: docs/specs/2026-11-05-harness-layout-design.md
plan: docs/plans/2026-11-05-harness-layout.md
step: "Task 2: Activate the reviewed layout and account for adoption"
---

Execute Task 2 only after Task 1 has passed final review and the user has separately approved the frozen live activation package, affected-host no-writer window and conditional recovery. Apply only from main, preserve uncommitted/private state, verify one host end to end and retain explicit ownership for other-host adoption and snapshots. No unreviewed runtime edits or implicit host authorization.

## Notes

- 2026-11-06T02:19:55Z (add): created
  provenance: {"harness_session":"codex:01a1ae6a-b6e7-7e32-bff6-a39714dc9d75","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
- 2026-11-06T02:20:08Z (refactor/hq-b77d0c-harness-layout): Await parent plan approval, accepted build, and explicit live activation authorization; controller unblocks at that gate.
  provenance: {"harness_session":"codex:01a1ae6a-b6e7-7e32-bff6-a39714dc9d75","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-06T04:50:57Z (refactor/hq-b77d0c-harness-layout): Task1 is complete and independently accepted. Operational preparation is finished in docs/notes/2026-11-06-harness-layout-activation.md at b0c044f11ef8c4c43487ab9688a05055d7529d09. Runtime 062f7131a59dc81fb22148b05a11741e5642853a, main base 71a4934294f055d42c1cf9dae8290937656fc934; all later branch changes are records only. Before live execution, user must approve this exact package and a no-settings-writer window covering every sharing host; Titan and Europa are proposed, not yet confirmed. Controller/operator then starts this task, rechecks actual base/state/launchers and performs the tested runbook from main. Do not merge or repoint links before that authority. Parent hq-b77d0c retains the worktree and execution/review workspace through this gate.
