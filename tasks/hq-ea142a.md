---
id: hq-ea142a
title: "rename-cutover detached: rollback restores the owned paths"
status: doing
priority: 3
size: l
complexity: high
process: direct
owner: feat/hq-5300fd-detached-rename
created: 2026-11-02T14:57:10Z
updated: 2026-11-02T18:00:28Z
started: 2026-11-02T17:15:04Z
depends: [hq-62ba95]
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
- 2026-11-02T14:57:26Z (feat/hq-5300fd-detached-rename): gate: scoped — step of hq-5300fd plan
  provenance: {"harness_session":"claude-code:09b6f7cb-8595-42af-8bc2-4cea8a51e5c1","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T17:15:04Z (feat/hq-5300fd-detached-rename): started
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T17:15:27Z (feat/hq-5300fd-detached-rename): arm: flow-trial-1 — unit tack-5300fd — flow on
- 2026-11-02T17:15:30Z (feat/hq-5300fd-detached-rename): gate: implementing .worktrees/hq-5300fd-detached-rename
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T18:00:26Z (feat/hq-5300fd-detached-rename): review: impl round 1 — verdict: accept; findings: Minor 4; reviewer: claude-code/claude-opus-5-5
- 2026-11-02T18:00:28Z (feat/hq-5300fd-detached-rename): gate: verified tree:d37bca12e5ac7ae722dc203a3e1bc34694496b9d — checks: just test exit 0 (harness-facts ok, agents/bin 268 passed, .githooks and tools 1993 passed, relay xdist 391 passed, signal test 1 passed) and focused tools/test_rename_cutover.py 161 passed, all 23 new tests seen RED, four targeted breaks (resetting detached repo code checkouts, skipping commit_records, committing before the registry restore, not recreating dirs) each seen failing, reviewer probes of the retry, index.lock, staged foreign file, attachments and links converged; review: minor deferred a link at the new or old records directory crashes rollback after it starts (Task 5 brief), minor deferred the walk silently skips an unreadable directory (Task 5 brief), minor deferred pre-pass mkdir and copy failures raise raw exceptions (Task 5 brief), minor deferred two records repositories with one basename share a patch label (Task 5 brief); reviewer: claude-code/claude-opus-5-5
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
