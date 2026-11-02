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
updated: 2026-11-02T16:16:25Z
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
- 2026-11-02T16:16:25Z (feat/hq-5300fd-detached-rename): gate: verified tree:ceab069c38fc2e24cafeed5c210bc10c4d0f3707 — checks: just test exit 0 (harness-facts ok, agents/bin 268 passed, .githooks and tools 1952 passed, relay xdist 391 passed, signal test 1 passed) and focused tools/test_rename_cutover.py 120 passed, 23 new tests seen RED before the save changes, five declared plan deviations accepted by the reviewer; review: minor deferred dangling symlink at the new records directory passes save (Task 3 brief), minor deferred a new directory tracked at HEAD but deleted on disk passes save (Task 3 brief), minor deferred old-directory refusal says untracked for tracked edits (Task 3 brief), minor deferred reachable row without kind reported as unreachable (Task 3 brief); reviewer: claude-code/claude-opus-5-5
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
