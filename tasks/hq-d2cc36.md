---
id: hq-d2cc36
title: "Correct adding-a-harness runbook: agy exports ANTIGRAVITY_CONVERSATION_ID as its native session id"
status: done
priority: 3
size: xs
complexity: low
process: direct
owner: docs/hq-d2cc36-agy-session-id
created: 2026-11-08T12:56:34Z
updated: 2026-11-08T16:35:55Z
started: 2026-11-08T16:33:34Z
completed: 2026-11-08T16:35:55Z
closed: 2026-11-08T16:35:55Z
depends: []
related: [relay-7b8340]
tags: []
source: tasks-b42efc
model: claude-opus-5-5
agent: claude-code/claude-opus-5-5
origin: agent
---

hq docs/runbooks/adding-a-harness.md says agy exports no native session id. agy exports ANTIGRAVITY_CONVERSATION_ID (equal to the hook payload conversationId, subagents included; relay-7b8340 probe), and tasks-b42efc's design (tasks records docs/specs/2026-11-08-agy-session-identity-design.md) uses it for agy:<conversationId> claims and provenance. Update the line, and note the two-phase provenance rollout (readers first, then writers) as the precedent for future harnesses.

## Notes

- 2026-11-08T12:56:34Z (add): created
  provenance: {"harness_session":"claude-code:791569f1-2567-4c3f-a61f-77b15d2ce4f1","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-08T16:33:34Z (main): started
  provenance: {"harness_session":"claude-code:51fffea7-6ed5-4a54-b2d7-3a0f02c1306a","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T16:33:36Z (docs/hq-d2cc36-agy-session-id): resumed
  provenance: {"harness_session":"claude-code:51fffea7-6ed5-4a54-b2d7-3a0f02c1306a","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T16:34:01Z (docs/hq-d2cc36-agy-session-id): trial: flow-trial-1 — enrolled — flow off
- 2026-11-08T16:34:03Z (docs/hq-d2cc36-agy-session-id): arm: flow-trial-1 — unit tack-d2cc36 — flow off
- 2026-11-08T16:35:55Z (docs/hq-d2cc36-agy-session-id): done
  provenance: {"harness_session":"claude-code:51fffea7-6ed5-4a54-b2d7-3a0f02c1306a","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-08T16:35:55Z (docs/hq-d2cc36-agy-session-id): adding-a-harness runbook: agy stamps via ANTIGRAVITY_CONVERSATION_ID (tasks c74a4ee, obs join.py already accepts agy); provenance rollout rewritten as readers, install gate, then writers, with tasks-b42efc as precedent; checks: just check-hygiene exit 0 (docs-only, no test obligation)
  provenance: {"harness_session":"claude-code:51fffea7-6ed5-4a54-b2d7-3a0f02c1306a","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
