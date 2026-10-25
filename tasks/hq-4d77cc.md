---
id: hq-4d77cc
title: "session-logs cannot reach Claude Code subagent transcripts: its store table and id-search glob (projects/*/*.jsonl) and session-episodes miss <session>/subagents/agent-*.jsonl, where a subagent's tool calls live under the parent's session id"
status: idea
priority: 2
created: 2026-10-25T13:41:26Z
updated: 2026-10-25T20:39:05Z
depends: []
tags: [feedback, gap, "from:tasks"]
agent: claude-code
---

A provenance stamp on a record filed by a Claude Code subagent names the parent session (subagents inherit CLAUDE_CODE_SESSION_ID). Following it to the filing call needs the subagent transcript, which sits in <session-uuid>/subagents/agent-*.jsonl. The skill's table and its id-search snippet only cover top-level session files, and session-episodes skips the directory, so a retriever had to walk the layout by hand. Expected: the skill names the subagents directory and the readers include it. Also: api-request-blob records repeat tool_use blocks and need deduplication by tool_use id to avoid phantom duplicate calls.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-25-task-origin-lookup-brief.md — existing reader owners and guidance evidence; remaining origin-query decisions
