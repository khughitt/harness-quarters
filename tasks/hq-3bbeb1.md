---
id: hq-3bbeb1
title: "hq pause status reports no pause state when run from a git worktree cwd, though the session's state exists"
status: idea
priority: 2
created: 2026-11-10T09:16:28Z
updated: 2026-11-10T09:16:28Z
depends: []
tags: [feedback, friction, "from:beliefs"]
agent: claude-code/claude-opus-5-5
---

Run from a linked worktree of the session's checkout, the status command prints 'no pause state ... for cwd <worktree path>' and exits 0. Run from the main checkout where the session started, it reports the counts. The global instructions ask a controller to check pause status at every plan-task boundary, and planned work runs in worktrees, so the check silently reads as no state. Expected: resolve the session's state independent of the shell cwd (by session id), or at least exit non-zero and name the cwd that holds the state.

## Notes

- 2026-11-10T09:16:28Z (feedback): created
  provenance: {"harness_session":"claude-code:27300022-9168-4f15-a40f-4ac88a453261","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
