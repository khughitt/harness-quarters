---
id: hq-c4cbbc
title: Register the hooks in both homes and add the Profiles section
status: done
priority: "2"
size: s
complexity: low
process: direct
owner: project-profiles
created: 2026-09-19T17:15:42Z
updated: 2026-09-21T11:48:44Z
started: 2026-09-21T11:38:35Z
completed: 2026-09-21T11:48:44Z
depends: [ops-0a0059, ops-b601db]
parent: hq-45ac4c
tags: [rules, hooks]
model: "claude-opus-5[1m]"
agent: "claude-code/claude-opus-5[1m]"
plan: docs/plans/2026-09-19-project-profiles.md
step: "Task 2: Register the hooks in both homes and add the Profiles section"
---

## Notes

- 2026-09-21T11:38:35Z (project-profiles): started
  provenance: {"harness_session":"claude-code:5e1c7878-739e-4237-9d2c-1ed9bed06701","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T11:48:44Z (project-profiles): Live check, personal home (headless claude -p, Sonnet 5, --debug=hooks confirms the SessionStart hook ran): ai -> 'profile: personal (identity.toml [ai].profiles); home: personal; design docs: commit; gh: khughitt; PRs: by-permission — later layers win: core < profile < this repository's instructions < you. `ops-profile explain` shows every source.'; unregistered scratch clone of obra/superpowers -> 'profile: external (profiles.toml default); home: personal; design docs: exclude; gh: khughitt; PRs: required — …'. Haiku 4.5 missed the line twice when asked to quote it; Sonnet quoted it every time — a reader flake, not a hook one.
- 2026-09-21T11:48:44Z (project-profiles): Live check, work home (CLAUDE_CONFIG_DIR=~/.claude-work): <work>/<repo> -> 'profile: work (identity.toml [rad].profiles); home: work; design docs: exclude; gh: <work-account>; PRs: by-permission — …'. In a scratch repo, the session's empty probe commit carrying a session-URL attribution trailer as its second -m was refused: 'PreToolUse:Bash hook error: [~/d/ops/hooks/claude-pretooluse]: claude-pretooluse: refusing to write an AI attribution line … drop the line and rerun.' No commit created; attribution-blocks.log gained the 2026-09-21T11:47:39Z entry. Sonnet declined the command on its own instructions on the first ask; naming the hook as the thing under test got it to run once. No GitHub contact.
- 2026-09-21T11:48:44Z (project-profiles): done
  provenance: {"harness_session":"claude-code:5e1c7878-739e-4237-9d2c-1ed9bed06701","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T11:48:44Z (project-profiles): claude-profile registered in both homes' SessionStart, claude-pretooluse added to the work home's PreToolUse, Profiles section in AGENTS.md; live in every home through the settings symlinks and proven in personal, external, and work sessions
  provenance: {"harness_session":"claude-code:5e1c7878-739e-4237-9d2c-1ed9bed06701","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
