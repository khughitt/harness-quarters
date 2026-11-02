---
id: hq-e8a7d5
title: "Re-probe Codex write_stdin, wait and exec_command arguments per version, and prepare an upstream request for hooks on them"
status: idea
priority: 2
created: 2026-11-02T00:06:05Z
updated: 2026-11-02T00:06:05Z
depends: []
tags: []
source: "claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79"
agent: claude-code/claude-opus-5-5
origin: agent
---

Follow-up of hq-9aa713. Codex 0.166.0 fires no hook for the outer exec, nested write_stdin or top-level wait, and the exec_command hook payload carries only command (shell, login, tty and workdir dropped), so a paused Codex agent can still drive a session it opened before the pause (spec Limitation: unhooked Codex controls). Re-probe on each Codex version (facts hook-unhooked-tools and hook-tool-names; a test fails when they change), and prepare an upstream issue asking for hooks on write_stdin and wait and the full exec_command arguments; publishing it is the user's call. Include the open question whether Codex evaluates commands after loading the user's shell snapshot, which would let zsh global aliases past the shell validator.

## Notes

- 2026-11-02T00:06:05Z (add): created
  provenance: {"harness_session":"claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
