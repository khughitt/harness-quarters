---
id: hq-bcff4c
title: Rewrite t@t commit authorship in this repository
status: doing
priority: 2
size: s
complexity: low
process: direct
owner: main
created: 2026-10-16T16:32:42Z
updated: 2026-10-16T17:16:26Z
started: 2026-10-16T17:15:08Z
depends: [ops-e5b39c]
tags: []
source: git-identity-leak-2026-10-07
agent: claude-code/claude-opus-5-5
---

Rewrite this repository's t <t@t> commits (from the 2026-10-07 global-config leak; see ops-5749d9) to Keith Hughitt <keith.hughitt@gmail.com>, following the runbook ops-e5b39c. Inventory on titan 2026-10-16: 717 t@t commits on all refs, 0 unpushed on main, 3 worktree(s); remote: khughitt/harness-quarters.

## Notes

- 2026-10-16T17:15:08Z (main): started
  provenance: {"harness_session":"claude-code:9c070e8d-dc83-4336-8ab8-fa5eb8b20204","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-16T17:15:15Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-10-16T17:15:15Z (main): arm: flow-trial-1 — unit tack-bcff4c — flow off
- 2026-10-16T17:16:26Z (main): Taken ahead of runbook ops-e5b39c at the user's direction, as the pilot. Approach: bundle backup; filter-repo --mailmap in a scratch mirror clone (never in the live checkout: its reset --hard could touch filtered live harness state); verify zero t@t and identical trees per commit-map entry; move live main by guarded update-ref (trees identical, working tree untouched); commit the changed-commit map under docs/rewrites/ so old SHAs in append-only task notes stay resolvable; force-push with lease. europa offline 18h at start: verify its Dropbox copy when it reconnects.
