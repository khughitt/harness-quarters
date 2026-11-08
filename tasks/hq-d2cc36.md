---
id: hq-d2cc36
title: "Correct adding-a-harness runbook: agy exports ANTIGRAVITY_CONVERSATION_ID as its native session id"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-11-08T12:56:34Z
updated: 2026-11-08T12:56:34Z
depends: []
related: [relay-7b8340]
tags: []
source: tasks-b42efc
agent: claude-code/claude-opus-5-5
origin: agent
---

hq docs/runbooks/adding-a-harness.md says agy exports no native session id. agy exports ANTIGRAVITY_CONVERSATION_ID (equal to the hook payload conversationId, subagents included; relay-7b8340 probe), and tasks-b42efc's design (tasks records docs/specs/2026-11-08-agy-session-identity-design.md) uses it for agy:<conversationId> claims and provenance. Update the line, and note the two-phase provenance rollout (readers first, then writers) as the precedent for future harnesses.

## Notes

- 2026-11-08T12:56:34Z (add): created
  provenance: {"harness_session":"claude-code:791569f1-2567-4c3f-a61f-77b15d2ce4f1","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
