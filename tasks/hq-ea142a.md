---
id: hq-ea142a
title: "rename-cutover detached: rollback restores the owned paths"
status: todo
priority: 3
size: l
complexity: high
process: direct
created: 2026-11-02T14:57:10Z
updated: 2026-11-02T14:57:10Z
depends: []
parent: hq-5300fd
tags: []
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-11-02-detached-rename-cutover.md
step: "Task 4: rollback restores the records repository's owned paths"
---

Plan Task 4 (spec §4.5 steps 1-5, §4.6). Outcome: rollback walks and classifies leftovers, writes records patches and leftover copies before the first reset or restore, restores owned paths with git restore over the index-or-saved-head set, deletes <new>/ whole, recreates <old>/ directories, commits after restore_dir over the index-or-HEAD set, and leaves detached repos' code checkouts alone. Plan review round 5 note: choose the next unused rollback-leftovers-<n> once per rollback attempt, before the pre-pass writes any file, so every copy of one attempt lands under the same <n> (do not re-probe per file or per repository).

Contract: spec docs/specs/2026-11-02-detached-rename-cutover-design.md revision 6 (0c7825cd) and plan docs/plans/2026-11-02-detached-rename-cutover.md revision 5 (09990011), both user-approved; read the plan's Global constraints first (every check before the first mutation; refusals name their path; tests isolate HOME, XDG and git config; the tracked hook fixture is never edited). Work in .worktrees/hq-5300fd-detached-rename on feat/hq-5300fd-detached-rename. Verification: the task's tests RED then GREEN (guards seen to fail against their named break), then just test.

## Notes

- 2026-11-02T14:57:10Z (add): created
  provenance: {"harness_session":"claude-code:09b6f7cb-8595-42af-8bc2-4cea8a51e5c1","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
