---
id: hq-14bab1
title: Turn pause state schema changes need a migration or reset path before they ship
status: idea
priority: 2
created: 2026-11-02T00:06:08Z
updated: 2026-11-05T14:04:59Z
depends: []
parent: hq-2dd09b
tags: []
source: "claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79"
agent: claude-code/claude-opus-5-5
origin: agent
---

Follow-up of hq-9aa713 (Task 6 refused-call fix review). The hook reads state fail-closed, so any later change to TurnState or RootState fields makes every live session's state unreadable and refuses every tool call until SessionEnd removes the file; a genuine prompt does not recover it. Before the first post-activation schema change, add a versioned read with an explicit migration, or an hq pause reset command the user runs, and say which in the activation notes.

## References

- brief (input, required, kind=brief): docs/notes/2026-11-05-turn-pause-followups-brief.md — duplicate migration work and branch-versus-live limitation

## Notes

- 2026-11-02T00:06:08Z (add): created
  provenance: {"harness_session":"claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
