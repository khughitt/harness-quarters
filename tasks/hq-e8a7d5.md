---
id: hq-e8a7d5
title: "Re-probe Codex write_stdin, wait and exec_command arguments per version, and prepare an upstream request for hooks on them"
status: idea
priority: 2
reviewed: true
reviewed_at: 2026-11-05T02:15:50Z
created: 2026-11-02T00:06:05Z
updated: 2026-11-05T02:15:50Z
depends: [hq-a5a449]
parent: hq-8f5670
tags: [hooks]
source: "claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79"
agent: claude-code/claude-opus-5-5
origin: agent
---

Follow-up of hq-9aa713. Codex 0.166.0 fires no hook for the outer exec, nested write_stdin or top-level wait, and the exec_command hook payload carries only command (shell, login, tty and workdir dropped), so a paused Codex agent can still drive a session it opened before the pause (spec Limitation: unhooked Codex controls). Re-probe on each Codex version (facts hook-unhooked-tools and hook-tool-names; a test fails when they change), and prepare an upstream issue asking for hooks on write_stdin and wait and the full exec_command arguments; publishing it is the user's call. Include the open question whether Codex evaluates commands after loading the user's shell snapshot, which would let zsh global aliases past the shell validator.

## References

- brief (input, required, kind=brief): docs/notes/2026-11-04-turn-pause-coverage-brief.md — context and questions for this work

## Notes

- 2026-11-02T00:06:05Z (add): created
  provenance: {"harness_session":"claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-02T00:30:44Z (main): add: probe whether Codex sends PostToolUse for an allowed nested exec_command that fails (e.g. false), since Codex has no PostToolUseFailure; until then a failed call stays in flight until its agent's Stop (spec wording at hq-9aa713 branch)
- 2026-11-02T09:02:30Z (main): owns retained turn-pause evidence handed over at hq-9aa713's close (host titan): $WORK_ROOT/hq/hq-fe672f (probe logs), hq-7203b2 (replay outputs), hq-77b422 (lifecycle runs), hq-9aa713 (raw ledger and task reports), each with its manifest file; the retained records are on those four tasks; disposal is this task's session's call when it closes
- 2026-11-05T02:15:50Z (main): scope: briefed; parented under hq-8f5670, added [ref:brief] and dep on hq-a5a449 for remaining codex-cli 0.166.0 probes (failed exec_command PostToolUse, explicit shell/login/tty/workdir args, shell_snapshot global aliases; retained hq-9aa713 evidence custody preserved); origin: stage 1 inferred (claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79 L2502/L2508 toolu_01EkbGT7CaoUsxQbPkLuFpSu: single sourced tasks add candidate per title, id-only stdout with 2>&1 stderr captured and no reuse warning; controller follow-up of hq-9aa713 after human "Accept." at L1210; stage 2 n/a, no origin_session; stored origin=agent confirmed); brief: docs/notes/2026-11-04-turn-pause-coverage-brief.md
