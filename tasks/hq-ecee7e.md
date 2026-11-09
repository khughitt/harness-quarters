---
id: hq-ecee7e
title: "rename-cutover tests fail locally against hostkit's work-link, which needs storage.anchor_name and sync.ignore_xattr config"
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: fix/hq-ecee7e-hostkit-fixture
created: 2026-11-09T17:08:30Z
updated: 2026-11-09T18:58:57Z
started: 2026-11-09T18:40:50Z
depends: []
tags: [testing]
agent: claude-code/claude-opus-5-5
origin: mixed
---

On 2026-11-09 a deliberate full suite (TT_FORCE=1 just test) on hq main plus a CI fixture fix gave 83 failed, 2318 passed; all 83 failures are in tools/test_rename_cutover.py, raised when tools/rename-cutover runs 'work-link --root <tmp>/sync --ensure .worktrees' and work-link exits with 'missing config: storage.anchor_name and sync.ignore_xattr are required when a synced root is set'. On this host work-link on PATH resolves to hostkit's bin/work-link (added in hostkit 47568a1). The hosted workflow installs dotfiles' work-link pinned to commit 2a686c0c by sha256, so CI passes these tests and does not see the drift. Questions: should the fixture write a hostkit config (via a test-owned HOME/XDG_CONFIG_HOME) for the work-link it calls, should rename-cutover pass the config itself, and should the workflow pin hostkit's work-link instead of the retired dotfiles copy. The rename-cutover code and tests did not change between the last pushed main (47d03066) and current main.

## Scope (2026-11-09)

Outcome: no tools/test_rename_cutover.py test fails on work-link config locally against hostkit's work-link, and CI against the pinned dotfiles copy is unaffected. (Narrowed 2026-11-09: 45 tests still fail on a separate rename-commit receipt drift, filed as hq-0f7499.)

Approach: the Sandbox fixture already isolates XDG_CONFIG_HOME and hardcodes the anchor `.dropbox-work`, which was the dotfiles copy's fixed name. Hostkit's work-link reads storage.anchor_name and sync.ignore_xattr from XDG_CONFIG_HOME/hostkit/config.toml. The fixture writes that test-owned file with sync_root = the sandbox sync dir, anchor_name = ".dropbox-work", ignore_xattr = "com.dropbox.ignored" (the dotfiles copy's hardcoded values), so both implementations behave alike. rename-cutover itself does not pass config: at a real cutover it runs work-link under the host's own hostkit config, which is the right source.

Not in scope: switching CI to hostkit's work-link. Hostkit has no git remote, so the workflow cannot fetch a pinned copy; that waits on publishing hostkit, which is the user's decision.

Verification: just test-one tools/test_rename_cutover.py shows no failure naming work-link (was 83, all work-link); the remaining failures all name the rename-commit receipt (hq-0f7499). The baseline run without the config write is the targeted break.

## Notes

- 2026-11-09T17:08:30Z (add): created
  provenance: {"harness_session":"claude-code:d1bad3e7-58ab-480c-a57c-ab20317aa035","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"mixed"}
- 2026-11-09T18:40:50Z (main): started
  provenance: {"harness_session":"claude-code:007a9370-10d2-4c63-86e7-81dd708478cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-09T18:41:17Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-11-09T18:41:19Z (main): arm: flow-trial-1 — unit tack-ecee7e — flow on
- 2026-11-09T18:42:36Z (main): process direct: fixture-only fix, approach settled by reading tools/rename-cutover, the Sandbox fixture and hostkit bin/hostkit_config.py; CI switch out of scope because hostkit has no git remote
- 2026-11-09T18:42:38Z (main): gate: scoped — adopted
  provenance: {"harness_session":"claude-code:007a9370-10d2-4c63-86e7-81dd708478cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-09T18:42:59Z (fix/hq-ecee7e-hostkit-fixture): resumed
  provenance: {"harness_session":"claude-code:007a9370-10d2-4c63-86e7-81dd708478cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-09T18:43:08Z (fix/hq-ecee7e-hostkit-fixture): gate: implementing .worktrees/hq-ecee7e
  provenance: {"harness_session":"claude-code:007a9370-10d2-4c63-86e7-81dd708478cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-09T18:53:36Z (fix/hq-ecee7e-hostkit-fixture): scope narrowed: with the fixture config, 38 of 83 failures pass; the other 45 all fail on rename-cutover's guard refusing state/tasks/rename-commit/<new>.toml, a receipt tasks 98c2383 added. That is a tool defect beyond this fixture fix, filed as hq-0f7499. Run: 45 failed, 135 passed, 0 mentions of work-link.
- 2026-11-09T18:55:52Z (fix/hq-ecee7e-hostkit-fixture): review: impl round 1 — verdict: accept; findings: minor 1; reviewer: claude-code/claude-opus-5-5
- 2026-11-09T18:58:57Z (fix/hq-ecee7e-hostkit-fixture): gate: verified tree:3213eb8db1a420b7f0e9880f23a256c0eab2f1ad — checks: just test-one tools/test_rename_cutover.py gave 45 failed 135 passed with zero failures naming work-link and every failure naming the rename-commit receipt owned by hq-0f7499 (baseline before the fix 83 failed 97 passed all on work-link config as the targeted break), just check-hygiene passed, broad suite skipped by tt policy; review: minor addressed sync_root now escaped with json.dumps; reviewer: claude-code/claude-opus-5-5
  provenance: {"harness_session":"claude-code:007a9370-10d2-4c63-86e7-81dd708478cd","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
