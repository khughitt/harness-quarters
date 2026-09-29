---
id: tack-46ba6c
title: codex-trust follow-ups from the branch review
status: doing
priority: 3
size: s
complexity: low
process: direct
owner: main
created: 2026-09-29T10:42:51Z
updated: 2026-09-29T20:17:47Z
started: 2026-09-29T20:17:47Z
depends: []
tags: [rules]
source: tack-de8d97
agent: claude-code/claude-opus-5-5
---

Deferred minors from the tack-de8d97 whole-branch review: (1) a failing post-checkout makes git switch/checkout exit 1 after it succeeded — decide report-only vs documented, pin with a test; (2) README and spec §1 omit cherry-pick, revert, rebase --abort, merge --abort from the no-hook cases; (3) forgetting a directory races concurrent turn ends — consider codex-trust forget <path> under the lock; (4) capture drops hand-written comments in local/codex/trust.toml — say it is machine-owned; (5) linked-worktree test covers only checkout --, add merge/switch/rebase; (6) harness-state-refresh exits with an empty message when codex-trust dies without stderr.

## Notes

- 2026-09-29T14:11:41Z (main): (7) git checkout of codex/config.toml rewrites it 0644 and restore keeps the mode it finds, so the live file loses 0600 after any checkout (seen in the tack-de8d97 rollout); decide whether restore/hook should set 0600
- 2026-09-29T20:17:47Z (main): started
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
