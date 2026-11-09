---
id: hq-155ccf
title: Commit cutover writes and enforce receipt ownership
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-11-09T20:21:08Z
updated: 2026-11-09T20:23:18Z
depends: []
parent: hq-74f102
tags: []
source: hq-74f102
agent: codex
origin: agent
spec: docs/specs/2026-11-09-rename-receipt-design.md
plan: docs/plans/2026-11-09-rename-receipt.md
step: "Task 1: Commit cutover writes and enforce receipt ownership"
---

Implement Task 1 of the receipt plan in the parent worktree .worktrees/hq-74f102. Why: raw runbook commits leave a host receipt and post-move receipt commits cannot validate the frozen identity/config. Expected: both apply commits force --json and expose warnings, receipt checks and guard findings are covered, rollback works at both commit boundaries, fixture callers reflect automatic commits, and just test-one tools/test_rename_cutover.py plus just check-hygiene pass under the invoking policy. Keep RED-to-GREEN evidence, counts and tested revision in the parent execution workspace. The real-hook local acceptance remains Task 2; no live cutover or push.

## Notes

- 2026-11-09T20:21:08Z (add): created
  provenance: {"harness_session":"codex:01a1c1cb-f948-7571-9531-9ef02916ebc4","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
- 2026-11-09T20:23:18Z (fix/hq-74f102-rename-receipt): gate: scoped — step of hq-74f102 plan
  provenance: {"harness_session":"codex:01a1c1cb-f948-7571-9531-9ef02916ebc4","harness_session_source":"CODEX_THREAD_ID"}
