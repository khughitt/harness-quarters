---
id: hq-14bab1
title: Turn pause state schema changes need a migration or reset path before they ship
status: dropped
priority: 2
created: 2026-11-02T00:06:08Z
updated: 2026-11-05T14:09:38Z
closed: 2026-11-05T14:09:38Z
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
- 2026-11-05T14:05:00Z (main): scope: drop; preserved idea status, body and source; hq-c58737 already owns completed branch step hq-cc91d4, with explicit version-0/version-1 offline conversion and activation/rollback guidance tree-verified at fix/hq-2dd09b a352cda4 (tools/turn_pause/migrate.py and docs/runbooks/turn-pause-activation.md); main 7abc23c3 remains unversioned, so this is duplicate ownership, not a claim of active migration; origin: filing inferred, claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79 L2502 toolu_01EkbGT7CaoUsxQbPkLuFpSu, sourced add f, unique title/time and positional id-only result L2508 with stderr captured before JSON parsing; controller explicitly filed review carries L2498, agent origin retained; older-request stage not applicable because no origin_session was recorded; brief: docs/notes/2026-11-05-turn-pause-followups-brief.md; proposal: drop this duplicate in favor of hq-c58737; preserve its separate live activation gate and do not drop automatically
  provenance: {"harness_session":"codex:01a1ac00-5258-7c73-9788-26641df81fef","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-05T14:09:38Z (main): dropped
  provenance: {"harness_session":"codex:01a1ac00-5258-7c73-9788-26641df81fef","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-05T14:09:38Z (main): User approved dropping this duplicate in this session. Migration and activation/rollback guidance remain owned by hq-c58737 (branch step hq-cc91d4); separate live activation approval is unchanged. Record-only closure: no owned retained items, new worktree or branch, surviving process, host change, push or PR; no other owners work or evidence was changed.
  provenance: {"harness_session":"codex:01a1ac00-5258-7c73-9788-26641df81fef","harness_session_source":"CODEX_THREAD_ID"}
