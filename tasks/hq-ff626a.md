---
id: hq-ff626a
title: "rename-cutover detached: sandbox fixture and the guard's records table"
status: todo
priority: 3
size: s
complexity: mid
process: direct
created: 2026-11-02T14:57:04Z
updated: 2026-11-02T14:57:04Z
depends: []
parent: hq-5300fd
tags: []
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-11-02-detached-rename-cutover.md
step: "Task 1: Detached sandbox and the registry guard's records table"
---

Plan Task 1 (spec §4.6, §5). Outcome: Sandbox builds detached checkouts and detached repos over a records repository with its own copy of the records pre-commit hook; commit() stays loud and commit_rename() asserts the records HEAD; registry_view treats a moved [records] key as the rename's own. Why the hook copy: tests must meet the live repository's refusal of a staged prefix without config.

Contract: spec docs/specs/2026-11-02-detached-rename-cutover-design.md revision 6 (0c7825cd) and plan docs/plans/2026-11-02-detached-rename-cutover.md revision 5 (09990011), both user-approved; read the plan's Global constraints first (every check before the first mutation; refusals name their path; tests isolate HOME, XDG and git config; the tracked hook fixture is never edited). Work in .worktrees/hq-5300fd-detached-rename on feat/hq-5300fd-detached-rename. Verification: the task's tests RED then GREEN (guards seen to fail against their named break), then just test.

## Notes

- 2026-11-02T14:57:04Z (add): created
  provenance: {"harness_session":"claude-code:09b6f7cb-8595-42af-8bc2-4cea8a51e5c1","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
