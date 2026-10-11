---
id: hq-d85ede
title: "Probe whether an answer from outside the terminal can reach a waiting question, per harness"
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-10-11T17:52:01Z
updated: 2026-10-11T17:52:01Z
depends: []
tags: [hooks, cross-project]
agent: claude-code/claude-fable-5-1
---

Piece of ops-cb50a8 (typed exchanges; phone inbox). Spike: the output is capability facts and a recommendation, not kept code.

Question: when a session is blocked on a question to the user, can a process outside its terminal supply the answer, and does the harness then continue the same turn? Which routes work, per harness?

Routes to try, each with a throwaway probe and the session log as evidence:
- Claude Code: (a) a PreToolUse hook on AskUserQuestion that replies deny with a reason carrying the answer, so the model proceeds as if answered; (b) the same hook allowing with updatedInput; (c) an MCP tool the agent calls instead of AskUserQuestion that blocks until a file or socket delivers the answer, with a timeout; (d) what the Notification events (idle_prompt, permission_prompt) and the permission-prompt tool option expose. Record whether the turn continues, what the model sees, and how long a blocked call may wait.
- Codex: request_user_input and request_user_input_async through the app-server JSON-RPC protocol (item/tool/requestUserInput and its answers map), and whether a hook or the PermissionRequest decision object can carry an answer. hq-5e63d9 records that the async card cannot be withdrawn; measure what a late answer to a stale card does.
- OpenCode: the question event and its reply path.

Done: one row per harness and route in facts/capabilities.toml with the evidence (version, probe, outcome) in the shape the controller-wake facts use, distinguishing unknown from unsupported; a note on ops-cb50a8 and on the relay design piece with the recommended route per harness and the constraint it imposes (blocking tool with timeout, hook reply, or protocol client). Keep probe code out of the repository.
