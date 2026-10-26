---
id: hq-aa495e
title: Transfer declared session tool and skill links to obs
status: todo
priority: 2
size: s
complexity: mid
process: direct
defer: 2027-02-17
created: 2026-10-26T13:21:09Z
updated: 2026-10-26T13:23:37Z
depends: []
tags: []
source: obs-f5710b plan hq handoff
agent: codex/gpt-6.1-sol
origin: agent
---

Contract: tasks doc obs-f5710b --plan, Task 7, approved spec revision2 e54f9af. Prepare hq declarations for integrated obs launchers/skill; retire the installed test link via [retired], delete moved code/tests/skill and update guides. Prove scratch-home link behavior and just test in a hydrated hq worktree. This follows obs-55431b; add that formal dependency after approved obs plan records reach their registered root, since the tracker cannot resolve the worktree-only record yet. Targets must exist in obs main before hq merge; global activation requires separate user authorization.

## Notes

- 2026-10-26T13:21:09Z (add): created
  provenance: {"harness_session":"codex:01a1780f-e78c-7582-93a0-9507ebf89699","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
- 2026-10-26T13:23:37Z (main): Planning coordination refinement: prepare this hq branch only after the frozen Task 6 obs result (obs-55431b) is complete in its authoritative worktree. Do not add that formal dependency merely when the plan-only records become visible: it would refer to the still-open main copy while code is prepared. At Task 8, after authorized obs runtime integration publishes the completed record, add the edge in this hq worktree before integrating hq. obs-929025 accepts the prepared frozen hq commit and tests; Task 8 owns actual integration/activation. This avoids a cross-project integration cycle and preserves the observed ordering; tracker gap tasks-40b49b.
