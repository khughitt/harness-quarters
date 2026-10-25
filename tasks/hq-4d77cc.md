---
id: hq-4d77cc
title: "session-logs cannot reach Claude Code subagent transcripts: its store table and id-search glob (projects/*/*.jsonl) and session-episodes miss <session>/subagents/agent-*.jsonl, where a subagent's tool calls live under the parent's session id"
status: idea
priority: 2
reviewed: true
reviewed_at: 2026-10-25T20:39:06Z
created: 2026-10-25T13:41:26Z
updated: 2026-10-25T20:39:06Z
depends: []
tags: [feedback, gap, "from:tasks"]
agent: claude-code
---

A provenance stamp on a record filed by a Claude Code subagent names the parent session (subagents inherit CLAUDE_CODE_SESSION_ID). Following it to the filing call needs the subagent transcript, which sits in <session-uuid>/subagents/agent-*.jsonl. The skill's table and its id-search snippet only cover top-level session files, and session-episodes skips the directory, so a retriever had to walk the layout by hand. Expected: the skill names the subagents directory and the readers include it. Also: api-request-blob records repeat tool_use blocks and need deduplication by tool_use id to avoid phantom duplicate calls.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-25-task-origin-lookup-brief.md — existing reader owners and guidance evidence; remaining origin-query decisions

## Notes

- 2026-10-25T20:39:06Z (main): scope: drop; checked hq dc51f61 current skill and session-episodes::scan_stores (Claude */*.jsonl only) against reviewed reader spec ae0f8ee sections 5.2, 8.1/8.3 and 10.1, and plan 1fea7bf. The reported child-file discovery and api-request-blob call-id deduplication gaps are real in the installed reader but already assigned to obs-d98663; usage guidance and extractor/classifier integration belong to deferred obs-f5710b. Native/path evidence must distinguish reader child coverage from pre-flow episode eligibility; no new parser or extraction promise. Preserved captured body and status; added existing brief reference and carried the details to obs-f5710b. origin: stage 1 unavailable (no creation occurrence note or filing-session stamp); stage 2 not applicable (no origin_session); origin remains unknown, without claiming a transcript search failed. brief: docs/notes/2026-10-25-task-origin-lookup-brief.md; proposal: drop as covered by obs-d98663 and obs-f5710b, not as delivered. Trial-readout/date-specific gates remain binding.
  provenance: {"harness_session":"codex:01a174ba-22b1-76d0-9d10-43ed3394938b","harness_session_source":"CODEX_THREAD_ID"}
