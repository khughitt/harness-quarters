---
id: hq-a64a9b
title: "rename-cutover detached: save preconditions and meta"
status: doing
priority: 3
size: m
complexity: mid
process: direct
owner: feat/hq-5300fd-detached-rename
created: 2026-11-02T14:57:06Z
updated: 2026-11-02T16:16:23Z
started: 2026-11-02T15:38:50Z
depends: [hq-ff626a]
parent: hq-5300fd
tags: []
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-11-02-detached-rename-cutover.md
step: "Task 2: save for detached projects"
---

Plan Task 2 (spec §4, §4.1). Outcome: save accepts detached checkouts and repos, refuses linked and unreachable rows, collects records repositories with owned paths, checks branch, stash, worktree, unmerged branches, scoped cleanliness, staged changes and the parent/name contract, and writes the new meta fields. Replaces the two refusal tests.

Contract: spec docs/specs/2026-11-02-detached-rename-cutover-design.md revision 6 (0c7825cd) and plan docs/plans/2026-11-02-detached-rename-cutover.md revision 5 (09990011), both user-approved; read the plan's Global constraints first (every check before the first mutation; refusals name their path; tests isolate HOME, XDG and git config; the tracked hook fixture is never edited). Work in .worktrees/hq-5300fd-detached-rename on feat/hq-5300fd-detached-rename. Verification: the task's tests RED then GREEN (guards seen to fail against their named break), then just test.

## Notes

- 2026-11-02T14:57:06Z (add): created
  provenance: {"harness_session":"claude-code:09b6f7cb-8595-42af-8bc2-4cea8a51e5c1","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T14:57:22Z (feat/hq-5300fd-detached-rename): gate: scoped — step of hq-5300fd plan
  provenance: {"harness_session":"claude-code:09b6f7cb-8595-42af-8bc2-4cea8a51e5c1","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T15:38:50Z (feat/hq-5300fd-detached-rename): started
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T15:39:09Z (feat/hq-5300fd-detached-rename): arm: flow-trial-1 — unit tack-5300fd — flow on
- 2026-11-02T15:39:11Z (feat/hq-5300fd-detached-rename): gate: implementing .worktrees/hq-5300fd-detached-rename
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T16:16:23Z (feat/hq-5300fd-detached-rename): review: impl round 1 — verdict: accept; findings: Minor 4; reviewer: claude-code/claude-opus-5-5
