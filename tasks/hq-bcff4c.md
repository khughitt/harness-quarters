---
id: hq-bcff4c
title: Rewrite t@t commit authorship in this repository
status: done
priority: 2
size: s
complexity: low
process: direct
owner: main
created: 2026-10-16T16:32:42Z
updated: 2026-10-16T17:22:59Z
started: 2026-10-16T17:15:08Z
completed: 2026-10-16T17:22:59Z
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
- 2026-10-16T17:22:59Z (main): done
  provenance: {"harness_session":"claude-code:9c070e8d-dc83-4336-8ab8-fa5eb8b20204","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-16T17:22:59Z (main): Rewrote 725 commits (717 t@t plus 8 descendants) to Keith Hughitt with filter-repo --mailmap in a scratch mirror; all 725 trees identical; live main moved by guarded update-ref with the working tree untouched; commit map committed as df46d4d (docs/rewrites/2026-10-16-identity-commit-map.txt) for the 38 old SHAs cited in task notes, specs and plans; just test 898 passed; force-pushed with lease (9a69b9a -> df46d4d), origin and main equal, 0 t@t on all refs, no open PRs. Pre-rewrite bundle kept outside Dropbox on titan at /mnt/ssd3/tmp/hq-rewrite-2026-10-16/hq-pre-rewrite.bundle. Closed ahead of runbook ops-e5b39c by user direction: this was its pilot.
  provenance: {"harness_session":"claude-code:9c070e8d-dc83-4336-8ab8-fa5eb8b20204","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
