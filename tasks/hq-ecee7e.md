---
id: hq-ecee7e
title: "rename-cutover tests fail locally against hostkit's work-link, which needs storage.anchor_name and sync.ignore_xattr config"
status: todo
priority: 2
size: s
complexity: mid
created: 2026-11-09T17:08:30Z
updated: 2026-11-09T17:08:30Z
depends: []
tags: [testing]
agent: claude-code/claude-opus-5-5
origin: mixed
---

On 2026-11-09 a deliberate full suite (TT_FORCE=1 just test) on hq main plus a CI fixture fix gave 83 failed, 2318 passed; all 83 failures are in tools/test_rename_cutover.py, raised when tools/rename-cutover runs 'work-link --root <tmp>/sync --ensure .worktrees' and work-link exits with 'missing config: storage.anchor_name and sync.ignore_xattr are required when a synced root is set'. On this host work-link on PATH resolves to hostkit's bin/work-link (added in hostkit 47568a1). The hosted workflow installs dotfiles' work-link pinned to commit 2a686c0c by sha256, so CI passes these tests and does not see the drift. Questions: should the fixture write a hostkit config (via a test-owned HOME/XDG_CONFIG_HOME) for the work-link it calls, should rename-cutover pass the config itself, and should the workflow pin hostkit's work-link instead of the retired dotfiles copy. The rename-cutover code and tests did not change between the last pushed main (47d03066) and current main.

## Notes

- 2026-11-09T17:08:30Z (add): created
  provenance: {"harness_session":"claude-code:d1bad3e7-58ab-480c-a57c-ab20317aa035","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"mixed"}
