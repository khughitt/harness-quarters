---
id: tack-2a9bba
title: Inline execution ledger completion assumes one checkout and cannot record a task verified in its registered main after a worktree merge
status: shelved
priority: 2
created: 2026-09-30T19:31:44Z
updated: 2026-10-02T14:30:58Z
depends: []
tags: [feedback, gap, "from:beliefs"]
agent: codex
---

## Notes

- 2026-10-02T14:30:57Z (main): scope: shelved; workspace and ledger resolve per git toplevel (sdd-workspace: .superpowers/sdd/<plan> under rev-parse --show-toplevel), so a worktree's ledger is invisible from main by design upstream; workaround is to run task-done in the worktree before merging. No body or second report says why verification moved to main after merge
- 2026-10-02T14:30:57Z (main): shelved: a second report of needing to record task completion from main after a worktree merge, or tack adopting a ledger shared across checkouts
