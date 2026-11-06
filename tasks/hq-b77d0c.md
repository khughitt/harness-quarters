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
updated: 2026-11-06T01:18:53Z
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
