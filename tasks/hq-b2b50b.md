---
id: hq-b2b50b
title: turn-pause's 4 h active-time limit stops valid long sessions; set the cutoff from historic session data
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-11-02T19:14:07Z
updated: 2026-11-02T20:22:20Z
depends: []
tags: [feedback, friction, "from:mm"]
agent: claude-code
origin: user
---

The user asked for this (their request): the 4 h active-time limit is too aggressive. It paused a valid subagent-driven plan execution partway through a task, while the session's other counters were far below their limits (about 59 of 500 calls, 7 of 30 spawns, 0 of 2 compactions). The user suggests something closer to 12 or 16 h. They want the implementer to choose the cutoff from historic session data, so that it catches the true outlier sessions without ending valid long-running ones. My reading: a session that only dispatches subagents and waits on them accrues active time while doing little itself, so wall-clock active time may be a weak signal compared with the call, spawn and compaction counters.

## Notes

- 2026-11-02T19:14:07Z (feedback): created
  provenance: {"harness_session":"claude-code:c67f4b5f-818d-4533-83b0-172009b992c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
