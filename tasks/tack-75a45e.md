---
id: tack-75a45e
title: "session-episodes: keep result text only for tasks-mentioning calls to bound memory"
status: todo
priority: "3"
size: s
complexity: low
process: direct
created: 2026-09-19T16:15:45Z
updated: 2026-09-19T16:15:45Z
depends: []
tags: [obs]
agent: claude-code/claude-opus-5
---

extract holds Event.text for every tool_result, assistant and human record of both stores in memory for the whole run (23.5 GB of JSONL on this host today; the acceptance run survived). Text is consumed only for the result of a call whose command mentions tasks, the next human turn after an anchor, and text_only (a boolean). show/confirm/label re-read the file anyway. Keep result text only when the paired call is a candidate; measure peak RSS before and after.
