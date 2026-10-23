---
id: hq-0b8f2c
title: Probe whether a resumed Claude successor session reads its linked subagent transcript
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-10-23T00:09:51Z
updated: 2026-10-23T00:32:22Z
depends: []
parent: hq-401088
tags: []
agent: claude-code/claude-opus-5-5
---

Question: Does Claude Code, on resuming a successor session or reading its history, open <new>/subagents/agent-<id>.jsonl through its link, and what happens when the link dangles?

Where to start: [ref:brief] records rules 2–3 (keep a unit another session links into), which are a policy gate resting on this unknown. If Claude never reads it, a dangling link may cost nothing and rule 2 can be dropped; if it does, the 30-versus-90-day retention argument stands. Keep this separate from the proven linking-unit quarantine-release failure.

Bound: An isolated Claude Code home only (no live store). Create a predecessor/successor pair the way the harness does (hand a running background agent to a successor) or, if that cannot be driven, a hand-made link of the same shape; then resume the successor and observe reads of the linked path (strace -e openat, or the transcript/UI) with the link resolving and dangling. Record the result as a capability fact through tools/harness-facts, with the probe under claude/probes/. No live-home changes or retention implementation.

Expected result: Record a fact naming whether resume reads the linked transcript and what happens when it dangles, cite it on hq-1639fd and update the brief. Distinguish a harness-created pair from a hand-made fixture and identify any observation limit; recommend whether the target-retention policy is justified by the result.

Ideas it wakes: On completion, run `tasks note hq-1639fd --no-reviewed "<finding and capability fact>"` before this result's branch merges.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-22-claude-prune-links-brief.md — findings, rules 1-3 and the open questions
