---
id: hq-8b6ae8
title: "cli-pane's cannot-start test throws from its process.run hook, which the kit skips, so the host's real tasks binary runs"
status: doing
priority: 3
size: xs
complexity: low
process: direct
owner: fix/cli-pane-cannot-start
created: 2026-10-15T08:25:00Z
updated: 2026-10-15T09:43:47Z
started: 2026-10-15T09:43:32Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
---

claude/mods/cli-pane/tests/cli-pane.test.ts 'a CLI that cannot start shows why' answers process.run by throwing. Under claude plugin test 2.1.296 a throwing hook is skipped (the engine reports "test's process.run hook was skipped") and the engine's own run proceeds, so the test reaches the host's real CLI and passes on whatever it prints. Answer with { deny: '<reason>' } instead, which rejects the caller as a failed start does (the pane then reads 'tasks: cli-pane: $.process.run: <reason>'), and assert the reason. Found by hq-4ba161's probe.

## Notes

- 2026-10-15T09:43:32Z (main): started
  provenance: {"harness_session":"claude-code:f0d949b3-991f-4324-a1ad-6e8803719ec0","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-15T09:43:39Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-15T09:43:39Z (main): arm: flow-trial-1 — unit tack-8b6ae8 — flow on
- 2026-10-15T09:43:46Z (main): gate: scoped — adopted
- 2026-10-15T09:43:47Z (fix/cli-pane-cannot-start): resumed
  provenance: {"harness_session":"claude-code:f0d949b3-991f-4324-a1ad-6e8803719ec0","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
