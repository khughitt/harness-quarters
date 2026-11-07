---
id: hq-8fa4d9
title: "Record Codex TUI notification behaviour as capability facts: allowlist filtering, unfocused-only default, tmux DCS wrapping"
status: doing
priority: 3
size: xs
complexity: low
process: direct
owner: feat/hq-8fa4d9-codex-tui-notification-facts
created: 2026-10-17T02:58:29Z
updated: 2026-11-07T16:14:54Z
started: 2026-11-07T16:10:24Z
depends: []
tags: [hooks]
source: hq-1ec500
agent: claude-code/claude-opus-5-5
---

The live acceptance in docs/notes/2026-10-15-agent-attention-brief.md (Live Codex acceptance) established on Codex 0.163.0: the [tui] notifications allowlist is honoured by the actual TUI (agent-turn-complete suppressed; async-question raised by request_user_input_async; plan-mode-prompt raised by request_user_input and the plan implementation prompt); notifications are sent only while unfocused by default, with the focus flag starting true; OSC 9 is DCS-wrapped for tmux whenever TMUX or TMUX_PANE is set. Record these as facts in facts/capabilities.toml through tools/harness-facts with that note as the record, so a Codex version change re-probes them (README re-probing procedure). Approval and MCP elicitation stay unknown: unreachable under approval_policy never. Verify with tools/harness-facts get for each new fact and just test.

## Notes

- 2026-10-17T02:58:29Z (main): concerns: hq-1ec500 extension — the acceptance evidence lives only in a note; capability facts make it re-probed on version change
- 2026-11-07T16:10:24Z (main): started
- 2026-11-07T16:10:26Z (feat/hq-8fa4d9-codex-tui-notification-facts): resumed
- 2026-11-07T16:10:50Z (feat/hq-8fa4d9-codex-tui-notification-facts): trial: flow-trial-1 — enrolled — flow off
- 2026-11-07T16:10:52Z (feat/hq-8fa4d9-codex-tui-notification-facts): arm: flow-trial-1 — unit tack-8fa4d9 — flow off
- 2026-11-07T16:14:54Z (feat/hq-8fa4d9-codex-tui-notification-facts): retro: rounds: 0 spec, 0 plan, 0 impl; checks-missed: none; drift: none; friction: none
