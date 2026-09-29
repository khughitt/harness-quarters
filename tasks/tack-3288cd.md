---
id: tack-3288cd
title: "Cutover tool: save, guard, rollback"
status: done
priority: "2"
size: m
complexity: mid
process: direct
owner: rename-tack
created: 2026-09-27T14:01:26Z
updated: 2026-09-27T15:34:51Z
started: 2026-09-27T15:15:42Z
completed: 2026-09-27T15:34:51Z
depends: [tack-1dd07b]
parent: tack-4b1878
tags: []
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-09-27-rename-to-tack.md
step: "Task 3: Cutover tool — `save`, guard, `rollback`"
---

## Notes

- 2026-09-27T15:15:42Z (rename-tack): started
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T15:34:51Z (rename-tack): done
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T15:34:51Z (rename-tack): tools/rename-cutover save/guard/rollback with tests (e994d1a, c2006a1); rollback refuses a real file at .worktrees, stops on ambiguous move state, keeps a patch of changes since save before each reset; 5 rollback tests go green with Task 4's apply
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
