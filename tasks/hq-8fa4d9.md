---
id: hq-8fa4d9
title: "Record Codex TUI notification behaviour as capability facts: allowlist filtering, unfocused-only default, tmux DCS wrapping"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-17T02:58:29Z
updated: 2026-10-17T02:58:29Z
depends: []
tags: [hooks]
source: hq-1ec500
agent: claude-code/claude-opus-5-5
---

The live acceptance in docs/notes/2026-10-15-agent-attention-brief.md (Live Codex acceptance) established on Codex 0.163.0: the [tui] notifications allowlist is honoured by the actual TUI (agent-turn-complete suppressed; async-question raised by request_user_input_async; plan-mode-prompt raised by request_user_input and the plan implementation prompt); notifications are sent only while unfocused by default, with the focus flag starting true; OSC 9 is DCS-wrapped for tmux whenever TMUX or TMUX_PANE is set. Record these as facts in facts/capabilities.toml through tools/harness-facts with that note as the record, so a Codex version change re-probes them (README re-probing procedure). Approval and MCP elicitation stay unknown: unreachable under approval_policy never. Verify with tools/harness-facts get for each new fact and just test.
