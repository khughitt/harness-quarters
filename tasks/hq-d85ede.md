---
id: hq-d85ede
title: "Probe whether an answer from outside the terminal can reach a waiting question, per harness"
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: main
created: 2026-10-11T17:52:01Z
updated: 2026-10-11T18:24:42Z
started: 2026-10-11T18:24:19Z
depends: []
tags: [hooks, cross-project]
agent: claude-code/claude-fable-5-1
---

Piece of ops-cb50a8 (typed exchanges; phone inbox). Spike: the output is capability facts and a recommendation, not kept code.

Question: which documented route for answering a waiting question from outside the terminal works in the installed versions (Claude Code 2.1.296, codex-cli 0.162.1 on 2026-10-11) and in the session modes actually used here: an interactive terminal session, and a managed session launched headless. Does the harness then continue the same turn, and what happens to a late answer after a restart?

Start from the documented paths, not from workarounds:
- Claude Code (code.claude.com/docs/en/hooks, "Tools that require user interaction"): a PreToolUse hook on AskUserQuestion returns permissionDecision allow with updatedInput echoing the questions and an answers map (question text to option label; multi-select joins labels with commas). The hook must block until an answer arrives, so measure how long a hook may wait in an interactive session (the hook timeout and its ceiling), whether the terminal stays usable while it waits, and what the user sees. Separately, permissionDecision defer: honoured only under claude -p, single tool call in the turn; the process exits with stop_reason tool_deferred and claude -p --resume replays the PreToolUse. Test it for the managed-session case only. Record what deny with a reason does to a withdrawn question (the model should see "question withdrawn" and move on), not as an answer route.
- Codex: request_user_input and request_user_input_async through the app-server JSON-RPC protocol (item/tool/requestUserInput and its answers map), and whether a hook or the PermissionRequest decision object can carry an answer to a terminal session. hq-5e63d9 records that the async card cannot be withdrawn; measure what a late answer to a stale card does.
- OpenCode: the question event and its reply path.

For every route: a delayed answer (minutes), an answer after the session restarted, and two answers to one question.

Done: one row per harness, session mode and route in facts/capabilities.toml with the evidence (version, probe, outcome) in the shape the controller-wake facts use, distinguishing unknown from unsupported; a note on ops-cb50a8 and on relay-f58531 with the recommended route per harness and the constraint it imposes on the relay design (a blocking hook with a ceiling, a resumable managed session, or a protocol client). Keep probe code out of the repository.

## Notes

- 2026-10-11T18:24:19Z (main): started
  provenance: {"harness_session":"claude-code:d008368b-1363-45b2-9427-35f33dcaefff","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-11T18:24:24Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-11T18:24:25Z (main): arm: flow-trial-1 — unit tack-d85ede — flow on
- 2026-10-11T18:24:42Z (main): gate: scoped — adopted
