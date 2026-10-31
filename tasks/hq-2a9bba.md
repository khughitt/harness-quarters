---
id: hq-2a9bba
title: Inline execution ledger completion assumes one checkout and cannot record a task verified in its registered main after a worktree merge
status: shelved
priority: 2
defer: 2026-11-30
created: 2026-09-30T19:31:44Z
updated: 2026-10-31T11:21:19Z
depends: []
tags: [feedback, gap, "from:beliefs"]
agent: codex
---

## Notes

- 2026-10-02T14:30:57Z (main): scope: shelved; workspace and ledger resolve per git toplevel (sdd-workspace: .superpowers/sdd/<plan> under rev-parse --show-toplevel), so a worktree's ledger is invisible from main by design upstream; workaround is to run task-done in the worktree before merging. No body or second report says why verification moved to main after merge
- 2026-10-02T14:30:57Z (main): shelved: a second report of needing to record task completion from main after a worktree merge, or tack adopting a ledger shared across checkouts
- 2026-10-31T11:21:17Z (main): shelved: A second report of needing to record task completion from main after a worktree merge, or adoption of a ledger shared across checkouts
- 2026-10-31T11:21:19Z (main): scope: shelved; renewed legacy undated shelf with a 30-day checkpoint and no wake targets. Installed vendor 2ce8aa15d05bd57213e6f746f953aafb7ded7a8b and upstream main/dev sdd-workspace blob b4661eb6ef646dae804c6b7932ccdbe942520a55 still resolve the workspace under the invoking Git top level. Open cross-project search found no second matching incident. Preserve the 2026-10-02 condition and workaround: record completion in the task worktree before merging; no shared-ledger adoption was found. Evidence checked 2026-10-31; upstream open/closed issues and PRs, main/dev workspace/ledger code and release notes searched. origin: filing event unavailable (no creation/feedback occurrence stamp survives in this record); older request not locatable from a bound filing event; origin left unset. No brief or draft spec created.
  provenance: {"harness_session":"codex:01a191ae-246c-7733-8215-139b32049d32","harness_session_source":"CODEX_THREAD_ID"}
