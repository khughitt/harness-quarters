---
id: hq-deb3e4
title: Register claude-profile in the Codex hooks file
status: done
priority: "2"
size: xs
complexity: low
process: direct
created: 2026-09-20T09:28:45Z
updated: 2026-09-21T12:07:44Z
completed: 2026-09-21T12:07:44Z
depends: []
tags: [hooks]
model: "claude-opus-5[1m]"
agent: codex
---

Probe ops .worktrees/project-profiles/docs/notes/2026-09-19-codex-sessionstart-context-probe.md showed Codex injects SessionStart stdout. Track the personal and work Codex hooks files in ai and add the profile hook entry.

## Notes

- 2026-09-21T11:57:57Z (project-profiles): codex/hooks.json = the previously untracked ~/.codex/hooks.json (familiar entries, unchanged) plus a second SessionStart group running ops hooks/claude-profile (trust key session_start:1:0, so the existing trusted hashes stay valid). codex/hooks.work.json carries the profile hook only: the work Codex home had no hooks file, and adding familiar there is a separate decision. Trust hashes are not fabricated; Codex asks once per home on the next interactive launch.
- 2026-09-21T12:07:44Z (main): Installed: ~/.codex/hooks.json (was an untracked copy of the familiar entries, saved aside then replaced) and ~/.codex-work/hooks.json (new) are symlinks to codex/hooks.json and codex/hooks.work.json. Live check with codex exec --dangerously-bypass-hook-trust --sandbox read-only (codex-cli 0.155.1, stdin from /dev/null — codex exec otherwise waits on a non-tty stdin): personal home in ai -> 'profile: personal (identity.toml [ai].profiles); home: personal; design docs: commit; gh: khughitt; PRs: by-permission — …' quoted by the model; work home in <work>/<repo> -> 'profile: work (identity.toml [rad].profiles); home: unknown; design docs: exclude; gh: <work-account>; PRs: by-permission — …'. The fragment is delivered in both. 'home: unknown' (and 'home: personal' when Codex is launched from inside a Claude session) is ops-profile's environment-only harness detection: Codex hooks get no CODEX_* variables, only the Claude-shaped payload with transcript_path under the home — filed ops-d12cb7. The hooks.work.json symlink was repointed at a scratch env-dumping copy for one run and restored in the same command. Trust: Codex will ask once per home to trust the new session_start:1:0 entry on the next interactive launch; no hash was written by hand.
- 2026-09-21T12:07:44Z (main): done
  provenance: {"harness_session":"claude-code:5e1c7878-739e-4237-9d2c-1ed9bed06701","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T12:07:44Z (main): codex/hooks.json and codex/hooks.work.json tracked with the claude-profile SessionStart entry, both homes symlinked to them, profile line and fragment observed in personal and work Codex sessions; home detection under Codex is ops-d12cb7
  provenance: {"harness_session":"claude-code:5e1c7878-739e-4237-9d2c-1ed9bed06701","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
