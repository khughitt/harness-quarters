---
id: hq-0b8f2c
title: Probe whether a resumed Claude successor session reads its linked subagent transcript
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-10-23T00:09:51Z
updated: 2026-10-23T00:09:51Z
depends: []
parent: hq-401088
tags: []
agent: claude-code/claude-opus-5-5
---

Why: rules 2-3 in [ref:brief] (keep a unit another session links into) are a policy gate resting on an unknown: does Claude Code, on resuming the successor session or reading its history, open <new>/subagents/agent-<id>.jsonl through the link? If it never does, a dangling link costs nothing and rule 2 can be dropped; if it does, the 30-vs-90-day argument stands.

Bound: an isolated Claude Code home only (no live store). Create a predecessor/successor pair the way the harness does (hand a running background agent to a successor) or, if that cannot be driven, a hand-made link of the same shape; then resume the successor and observe reads of the linked path (strace -e openat, or the transcript/UI) with the link resolving and dangling. Record the result as a capability fact through tools/harness-facts, with the probe under claude/probes/.

Done: a fact naming whether resume reads the linked transcript and what happens when it dangles, cited on hq-1639fd.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-22-claude-prune-links-brief.md — findings, rules 1-3 and the open questions
