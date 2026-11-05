---
id: hq-ba40e9
title: "Probe whether a Codex compaction fires a hook, to give Codex a compaction counter"
status: idea
priority: 2
reviewed: true
reviewed_at: 2026-11-05T02:15:45Z
created: 2026-11-02T00:06:03Z
updated: 2026-11-05T02:15:45Z
depends: [hq-a5a449]
parent: hq-8f5670
tags: [hooks]
source: "claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79"
agent: claude-code/claude-opus-5-5
origin: agent
---

Follow-up of hq-9aa713. Task 1 left Codex hook-compact-event unknown: two isolated runs with a low auto-compact limit never compacted (cause not established). Until a probe shows PreCompact or PostCompact fires, Codex has no compaction counter and hq pause status prints compactions as count-your-own. Probe with a resumed second turn, record the fact, and wire the event if it fires.

## References

- brief (input, required, kind=brief): docs/notes/2026-11-04-turn-pause-coverage-brief.md — context and questions for this work

## Notes

- 2026-11-02T00:06:03Z (add): created
  provenance: {"harness_session":"claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-05T01:34:52Z (main): Context update from hq-1942a1 and hq-e51fac: automatic compactions are now advisory-only in turn-pause (hq pause status prints 'compactions -/2 (advisory, unhooked)' rather than '(count your own)', and counters.crossed checks only active, calls, and spawns). If this probe later shows a Codex compaction hook event fires, wiring it feeds the advisory compaction counter and one-time warning rather than a hard pause; offline Codex rollout transcripts already record compaction boundaries as type='compacted' and event_msg payload.type='context_compacted'.
- 2026-11-05T02:15:45Z (main): scope: briefed; parented under hq-8f5670, added [ref:brief] and dep on hq-a5a449 for two-turn codex exec resume compaction probe on codex-cli 0.166.0 (compactions are advisory-only after hq-1942a1/hq-e51fac); origin: stage 1 inferred (claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79 L2502/L2508 toolu_01EkbGT7CaoUsxQbPkLuFpSu: single sourced tasks add candidate per title, id-only stdout with 2>&1 stderr captured and no reuse warning; controller follow-up of hq-9aa713 after human "Accept." at L1210; stage 2 n/a, no origin_session; stored origin=agent confirmed); brief: docs/notes/2026-11-04-turn-pause-coverage-brief.md
