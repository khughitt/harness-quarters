---
id: hq-d288ac
title: "retros: request JSON explicitly from tasks and name unreachable projects when none report statuses"
status: moved
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-02T08:13:53Z
updated: 2026-11-08T16:31:46Z
depends: []
tags: [flow]
source: tack-fc26cf
agent: claude-code/claude-opus-5-5
moved_to: flows-ca5e89
---

Found by the tack-fc26cf reviews, still open on main. agents/bin/retros runs tasks without --json, so TASKS_FORMAT=pretty in the environment makes it exit 2 ('returned no JSON'). statuses() (raise at ~:120) reports 'tasks projects reported no statuses' when every registered project is unreachable, without naming them, contrary to its docstring. Done: pass --json on every tasks call; the all-unreachable case names the projects; a test for each.

## Notes

- 2026-11-08T16:31:44Z (main): checked flows e096318: retros already passes --json on every tasks call (bin/retros:159,165,173); the all-unreachable statuses() raise at bin/retros:133 still names no projects. Code moved to flows in flows-f8ea06; moving the task there.
- 2026-11-08T16:31:46Z (main): moved to flows-ca5e89
  provenance: {"harness_session":"claude-code:51fffea7-6ed5-4a54-b2d7-3a0f02c1306a","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
