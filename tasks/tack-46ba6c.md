---
id: tack-46ba6c
title: codex-trust follow-ups from the branch review
status: done
priority: 3
size: s
complexity: low
process: direct
owner: main
created: 2026-09-29T10:42:51Z
updated: 2026-09-29T20:21:08Z
started: 2026-09-29T20:17:47Z
completed: 2026-09-29T20:21:08Z
depends: []
tags: [rules]
source: tack-de8d97
model: claude-sonnet-5-5
agent: claude-code/claude-opus-5-5
---

Deferred minors from the tack-de8d97 whole-branch review: (1) a failing post-checkout makes git switch/checkout exit 1 after it succeeded — decide report-only vs documented, pin with a test; (2) README and spec §1 omit cherry-pick, revert, rebase --abort, merge --abort from the no-hook cases; (3) forgetting a directory races concurrent turn ends — consider codex-trust forget <path> under the lock; (4) capture drops hand-written comments in local/codex/trust.toml — say it is machine-owned; (5) linked-worktree test covers only checkout --, add merge/switch/rebase; (6) harness-state-refresh exits with an empty message when codex-trust dies without stderr.

## Notes

- 2026-09-29T14:11:41Z (main): (7) git checkout of codex/config.toml rewrites it 0644 and restore keeps the mode it finds, so the live file loses 0600 after any checkout (seen in the tack-de8d97 rollout); decide whether restore/hook should set 0600
- 2026-09-29T20:17:47Z (main): started
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T20:21:04Z (fix/trust-followups): decisions: (1) hooks report on stderr and exit 0, pinned by test; (7) restore drops group/other access on the live file; (3) codex-trust forget <path>. Ran sync and forget over a copy of the real 45-table config: parses, one table removed. No fresh-context review dispatched (small, mutation-checked tests).
- 2026-09-29T20:21:08Z (fix/trust-followups): done
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T20:21:08Z (fix/trust-followups): all seven follow-ups: hook failures report and exit 0; README and spec list the four more no-hook commands (probed); codex-trust forget; trust.toml documented machine-owned; linked-worktree test covers checkout, switch, merge, rebase; refresh names a silent sync death; restore keeps the live config 0600
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
