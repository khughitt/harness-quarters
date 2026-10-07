---
id: hq-d288ac
title: "retros: request JSON explicitly from tasks and name unreachable projects when none report statuses"
status: todo
priority: "3"
size: xs
complexity: low
process: direct
created: 2026-10-02T08:13:53Z
updated: 2026-10-02T08:13:53Z
depends: []
tags: [flow]
source: tack-fc26cf
agent: claude-code/claude-opus-5-5
---

Found by the tack-fc26cf reviews, still open on main. agents/bin/retros runs tasks without --json, so TASKS_FORMAT=pretty in the environment makes it exit 2 ('returned no JSON'). statuses() (raise at ~:120) reports 'tasks projects reported no statuses' when every registered project is unreachable, without naming them, contrary to its docstring. Done: pass --json on every tasks call; the all-unreachable case names the projects; a test for each.
