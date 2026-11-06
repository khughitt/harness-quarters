---
id: hq-b77d0c
title: Group harness files and external integrations under common directories
status: doing
priority: 2
size: m
complexity: mid
process: planned
owner: refactor/hq-b77d0c-harness-layout
created: 2026-11-06T01:17:05Z
updated: 2026-11-06T01:48:07Z
started: 2026-11-06T01:17:12Z
depends: []
tags: []
agent: codex
origin: user
spec: docs/specs/2026-11-05-harness-layout-design.md
---

The user asks to reduce root-directory clutter by grouping harness-specific files under harnesses/ and external skills/integrations under external/, illustrating agy, claude, codex, crush, opencode, pi and ponytail. Prepare a short design for review, then a reviewed implementation plan. Preserve existing harness behavior, live selections and private state. Treat the example as a repository layout change; current session-log stores remain in native harness homes. Candidate moves are agy/, claude/, codex/, pi/ and ponytail/; inspect all operational path consumers and home-link activation before implementation. No new harness integration is requested.

## Notes

- 2026-11-06T01:17:05Z (add): created
  provenance: {"harness_session":"codex:01a1ae6a-b6e7-7e32-bff6-a39714dc9d75","harness_session_source":"CODEX_THREAD_ID","origin":"user"}
- 2026-11-06T01:17:12Z (main): started
  provenance: {"harness_session":"codex:01a1ae6a-b6e7-7e32-bff6-a39714dc9d75","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-06T01:17:36Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-11-06T01:17:38Z (main): arm: flow-trial-1 — unit tack-b77d0c — flow off
- 2026-11-06T01:17:52Z (refactor/hq-b77d0c-harness-layout): resumed
  provenance: {"harness_session":"codex:01a1ae6a-b6e7-7e32-bff6-a39714dc9d75","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-06T01:18:53Z (refactor/hq-b77d0c-harness-layout): Scope choices: move existing agy, claude, codex and pi directories under harnesses, and ponytail under external. Keep shared agents/relay, private local state and native session logs where they are; no empty Crush/OpenCode integrations. Direct moves avoid compatibility aliases. These are author recommendations from the current user request, not prior approvals. just setup completed in the locked task worktree; implementation baseline deferred until execution under policy-off focused testing.
- 2026-11-06T01:19:33Z (refactor/hq-b77d0c-harness-layout): retained: {"version":1,"host":"titan","kind":"worktree","path":".worktrees/hq-b77d0c","state":"kept","verification":"verified","purpose":"Review the proposed layout design, then plan and implement the approved moves","next_owner":"task:hq-b77d0c","cleanup_trigger":"After approved implementation and live activation, integrate the branch and inspect retained contents before removal"}
- 2026-11-06T01:19:33Z (refactor/hq-b77d0c-harness-layout): Frozen design for user review: repository hq (in-tree records at .), branch refactor/hq-b77d0c-harness-layout, commit bf0256cd5e6fc2fa329db785d741c990f780be8c, path docs/specs/2026-11-05-harness-layout-design.md. Open from main at .worktrees/hq-b77d0c/docs/specs/2026-11-05-harness-layout-design.md. Only the design and task records changed; implementation awaits design and subsequent plan review.
- 2026-11-06T01:19:33Z (refactor/hq-b77d0c-harness-layout): Verification: just check-hygiene and git diff --check passed. tasks check had no errors and one existing record_growth warning for hq-c58737. Focused runtime tests and baseline deliberately deferred until implementation; this turn only drafted documentation. Broad tests not run under automatic_broad=false. No remote evidence claimed.
- 2026-11-06T01:19:33Z (refactor/hq-b77d0c-harness-layout): Park disclosures: nothing pushed; no process survives (host-load --section session reported nothing left running). No live links or host pointers repointed. Existing main edits in agy/settings.json and codex/config.toml and the other task worktree were untouched. Branch refactor/hq-b77d0c-harness-layout remains unmerged at .worktrees/hq-b77d0c; controller continues after user design review, then prepares the plan for review. Eventual live-surface integration requires explicit activation approval and a tested merge/relink sequence. Current task retained set is this locked worktree only; no scratch or off-tree evidence created. Git status, including ignored entries, was empty; setup-created empty local/codex/rules directories remain regenerable.
- 2026-11-06T01:19:52Z (refactor/hq-b77d0c-harness-layout): retention checkpoint: observed 2026-11-06T01:19:41Z on titan; basis hq in-tree records . commit 33bbb7a61e84448b15c942706667729209979982:tasks/hq-b77d0c.md; retained by refactor/hq-b77d0c-harness-layout; this host: kept verified 1, kept unknown 0, released 0; changed 1. Rechecked all kept/verified items on this host. No unknown items. Other hosts are outside this observation. Next: user reviews the frozen design, then controller prepares the implementation plan.
  provenance: {"harness_session":"codex:01a1ae6a-b6e7-7e32-bff6-a39714dc9d75","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-06T01:19:54Z (refactor/hq-b77d0c-harness-layout): parked (waiting on user, review): User: review the frozen design at .worktrees/hq-b77d0c/docs/specs/2026-11-05-harness-layout-design.md (revision in task note). Controller: incorporate any corrections, then use writing-plans to prepare the implementation plan for review in this same worktree.
  provenance: {"harness_session":"codex:01a1ae6a-b6e7-7e32-bff6-a39714dc9d75","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-06T01:48:07Z (refactor/hq-b77d0c-harness-layout): resumed
  provenance: {"harness_session":"codex:01a1ae6a-b6e7-7e32-bff6-a39714dc9d75","harness_session_source":"CODEX_THREAD_ID"}
