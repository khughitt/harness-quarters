---
id: tack-0a09d0
title: Profile-aware enforcement check in the work home
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-19T17:30:20Z
updated: 2026-09-21T11:54:08Z
started: 2026-09-21T11:52:10Z
completed: 2026-09-21T11:54:08Z
depends: [tack-c4cbbc, ops-acc467]
parent: tack-45ac4c
tags: [hooks]
model: "claude-opus-5[1m]"
agent: "claude-code/claude-opus-5[1m]"
plan: docs/plans/2026-09-19-project-profiles.md
step: "Task 3: Profile-aware enforcement check in the work home"
---

## Notes

- 2026-09-21T11:52:10Z (main): started
  provenance: {"harness_session":"claude-code:5e1c7878-739e-4237-9d2c-1ed9bed06701","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T11:54:08Z (main): Work-home probe 2026-09-21 (CLAUDE_CONFIG_DIR=~/.claude-work, headless Sonnet 5 in <work>/<repo>; GH_TOKEN/GITHUB_TOKEN unset; GH_CONFIG_DIR at a disposable hosts.yml with user: khughitt and no real tokens; a stub gh first on PATH logging to calls.log and exiting 1). 'gh issue comment 1 --body probe' was refused: "PreToolUse:Bash hook error: [~/d/ops/hooks/claude-pretooluse]: claude-pretooluse: refusing a gh write under the 'khughitt' account: <work checkout> resolves to profile work (identity.toml [rad].profiles), whose gh account is '<work-account>'. Run `gh auth switch --user <work-account>` and rerun." calls.log did not exist afterwards: the stub was never reached. Then 'gh pr view 1' reached the stub (calls.log: 'pr view 1', exit 1) — reads are not guarded. One extra stub line, 'auth token --user khughitt', is Claude Code's own startup GitHub probe (the binary carries it), not the agent or the hook. ~/.config/gh untouched (hosts.yml mtime 2026-09-19); no GitHub request made; probe dir removed.
- 2026-09-21T11:54:08Z (main): done
  provenance: {"harness_session":"claude-code:5e1c7878-739e-4237-9d2c-1ed9bed06701","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T11:54:08Z (main): Profile-aware gh account refusal observed live in the work home through a tokenless GH_CONFIG_DIR and stub gh: write refused naming profile work and <work-account> before reaching gh, read passed through
  provenance: {"harness_session":"claude-code:5e1c7878-739e-4237-9d2c-1ed9bed06701","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
