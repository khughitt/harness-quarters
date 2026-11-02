---
id: hq-ff626a
title: "rename-cutover detached: sandbox fixture and the guard's records table"
status: doing
priority: 3
size: s
complexity: mid
process: direct
owner: feat/hq-5300fd-detached-rename
created: 2026-11-02T14:57:04Z
updated: 2026-11-02T15:38:41Z
started: 2026-11-02T15:05:18Z
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
- 2026-11-02T14:57:20Z (feat/hq-5300fd-detached-rename): gate: scoped — step of hq-5300fd plan
  provenance: {"harness_session":"claude-code:09b6f7cb-8595-42af-8bc2-4cea8a51e5c1","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T15:05:18Z (feat/hq-5300fd-detached-rename): started
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T15:05:39Z (feat/hq-5300fd-detached-rename): arm: flow-trial-1 — unit tack-5300fd — flow on
- 2026-11-02T15:05:42Z (feat/hq-5300fd-detached-rename): gate: implementing .worktrees/hq-5300fd-detached-rename
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T15:38:30Z (feat/hq-5300fd-detached-rename): review: impl round 1 — verdict: accept; findings: Minor 3; reviewer: claude-code/claude-opus-5-5
- 2026-11-02T15:38:32Z (feat/hq-5300fd-detached-rename): gate: verified tree:1d81f53eeb1fdfafcda78aa843a5676ef2d08dea — checks: just test exit 0 (harness-facts ok, agents/bin 268 passed, .githooks and tools 1931 passed, relay xdist 391 passed, signal test 1 passed) and focused tools/test_rename_cutover.py 99 passed, RED seen for the moved-records-key test, guards seen failing against records-dropped-whole and core.hooksPath-unset breaks; review: minor deferred commit_rename hand-copies the command apply will print (Task 3 brief), minor deferred no Task 1 test drives commit_rename (exercised from Task 3), minor deferred add and delete guard cases do not assert the reported key name (Task 3 brief); reviewer: claude-code/claude-opus-5-5
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T15:38:41Z (feat/hq-5300fd-detached-rename): retro: briefing the implementer to skim later tasks paid off, the fixture already exposes records, hook and is_detached for Tasks 2-5; the reviewer's live hook-overwrite probe confirmed Task 5's premise early, worth asking reviewers for such forward probes
