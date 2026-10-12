---
id: hq-7abbf7
title: Probe whether a Claude Code managed session can be answered through the Agent SDK canUseTool callback
status: todo
priority: 3
size: s
complexity: mid
process: direct
created: 2026-10-12T10:30:53Z
updated: 2026-10-12T10:30:53Z
depends: []
tags: [hooks, question]
agent: claude-code/claude-opus-5-5
---

Follow-up of hq-d85ede: answer-server-managed and answer-server-terminal are unknown for claude-code. The docs name an Agent SDK canUseTool callback as a permission host for AskUserQuestion. Probe whether a session launched through the SDK can hold a question open while an outside client answers it minutes later, whether the same turn continues, and what a process restart does, compared with the defer-and-resume route already recorded in answer-defer-managed. Isolated setup and scratch probe code as in hq-d85ede.
Done: claude-code rows of answer-server-managed (and answer-server-terminal if a terminal route exists) probed or explicitly left unknown with the reason, checks pass, and the result noted on relay-f58531 when it offers the relay a simpler route than defer and resume.
