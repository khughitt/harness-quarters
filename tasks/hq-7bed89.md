---
id: hq-7bed89
title: "Probe agy 1.5.0 PreInvocation, PreToolUse, PostToolUse and subagent hook payloads for turn-pause"
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-11-05T02:14:04Z
updated: 2026-11-05T02:14:04Z
depends: []
parent: hq-8f5670
tags: [hooks]
source: docs/notes/2026-11-04-turn-pause-coverage-brief.md
origin: agent
---

Question: What exact JSON payloads does `agy 1.5.0` deliver to `PreInvocation`, `PreToolUse` (`"matcher": "*"`), `PostToolUse` (`"matcher": "*"`), and `Stop` across root tool calls and `invoke_subagent` runs, does `PreInvocation` (`lastUserInput`) distinguish a new human turn from a background or subagent wake, and does `{"decision": "deny", "reason": "..."}` on `PreToolUse` block non-`run_command` tools?
Where to start: `agy/hooks.json`, `agy/hook`, `tools/turn_pause/adapters.py`, and the `agy` hook schema summarized in `[ref:brief]`, which frames the two `agy` integration options and open payload questions.
Bound: Run one isolated probe of `agy 1.5.0` hook events (`PreInvocation`, `PreToolUse`, `PostToolUse`, `Stop`, and one `invoke_subagent` call) into a temporary log without activating `turn-pause` in `agy/hooks.json`; do not ship the production `agy` adapter in this task.
Expected result: Update `agy` hook capability facts through `tools/harness-facts` (in a worktree) and record the captured payload schema and adapter recommendation on this task and in `[ref:brief]`.
Ideas it wakes: On completion, run `tasks note hq-be1fd6 --no-reviewed "<finding>"` on each named waiting idea, before this result's branch merges.

## References

- brief (input, required, kind=brief): docs/notes/2026-11-04-turn-pause-coverage-brief.md — context and questions for this work

## Notes

- 2026-11-05T02:14:04Z (add): created
  provenance: {"origin":"agent"}
