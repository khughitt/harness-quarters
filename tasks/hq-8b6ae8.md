---
id: hq-8b6ae8
title: "cli-pane's cannot-start test throws from its process.run hook, which the kit skips, so the host's real tasks binary runs"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-15T08:25:00Z
updated: 2026-10-15T08:25:44Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
---

claude/mods/cli-pane/tests/cli-pane.test.ts 'a CLI that cannot start shows why' answers process.run by throwing. Under claude plugin test 2.1.296 a throwing hook is skipped (the engine reports "test's process.run hook was skipped") and the engine's own run proceeds, so the test reaches the host's real CLI and passes on whatever it prints. Answer with { deny: '<reason>' } instead, which rejects the caller as a failed start does (the pane then reads 'tasks: cli-pane: $.process.run: <reason>'), and assert the reason. Found by hq-4ba161's probe.
