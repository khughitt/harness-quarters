---
id: tack-8b7a28
title: "Rename tack to harness quarters (hq): design, plan, rehearsal and cutover"
status: doing
priority: 1
size: m
complexity: high
process: planned
owner: feat/rename-hq
created: 2026-10-06T12:59:15Z
updated: 2026-10-06T19:24:26Z
started: 2026-10-06T16:15:19Z
depends: [flows-44890e, obs-ff4e76, tasks-7580d2]
parent: tack-dcb11a
tags: []
source: tack-dcb11a
agent: claude-code/claude-fable-5-1
spec: docs/specs/2026-10-06-rename-to-hq-design.md
plan: docs/plans/2026-10-06-rename-to-hq-preparation.md
---

Why: the user chose the residue's name on 2026-10-06 (parent spec §7.1); the rename runs first in phase 3 so the residue's new consumers are written against the final registry key. Done: the rename design's §7: both hosts adopted and verified, four repositories committed and tasks check clean, the parent spec records the name, the GitHub repository renamed or its rename recorded as deferred, ops-593133 closed.

## Notes

- 2026-10-06T13:08:45Z (feat/residue): review: spec round 1 — verdict: revise; findings: Critical 1, Important 5, Minor 6; reviewer: claude-code/claude-fable-5-1
- 2026-10-06T13:18:48Z (feat/residue): review: spec round 2 — verdict: revise; findings: Important 4, Minor 6; reviewer: claude-code/claude-fable-5-1
- 2026-10-06T13:21:53Z (feat/residue): review: spec round 3 — verdict: revise; findings: P1 4; reviewer: codex/gpt-6-astra
- 2026-10-06T13:21:53Z (feat/residue): user 2026-10-06: keep the rename despite the added work; first make other projects handle a rename in general, since this will not be the last one
- 2026-10-06T14:32:54Z (feat/residue): review: spec round 4 — verdict: revise; findings: P2 1; reviewer: codex/gpt-6-astra
- 2026-10-06T14:52:43Z (feat/residue): review: spec round 5 — verdict: accept; findings: none; reviewer: codex/gpt-6-astra
- 2026-10-06T16:00:08Z (main): From the residue's execution: if this rename's plan sends host scripts that preview with just, do not use 'just --quiet': in just 1.58 it suppresses the recipe's own output, so a preview prints nothing and a failed apply prints an empty tail. Run 'just link' and filter the echoed recipe line (tack docs/plans/2026-10-06-residue.md, execution record).
- 2026-10-06T16:15:19Z (main): started
  provenance: {"harness_session":"claude-code:529a99ac-8d12-4ea1-b9ff-8f3fd73d2c16","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T16:15:31Z (main): arm: flow-trial-1 — unit tack-dcb11a — flow off
- 2026-10-06T16:15:42Z (plan/rename-hq): resumed
  provenance: {"harness_session":"claude-code:529a99ac-8d12-4ea1-b9ff-8f3fd73d2c16","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T16:55:59Z (feat/rename-hq): review: plan round 1 — verdict: revise; findings: Important 2, Minor 7; reviewer: claude-code/claude-fable-5-1
- 2026-10-06T17:11:15Z (feat/rename-hq): review: plan round 2 — verdict: revise; findings: Important 1, Minor 2; reviewer: claude-code/claude-fable-5-1
- 2026-10-06T17:14:05Z (feat/rename-hq): parked (waiting on user, review): User reviews (GPT round) docs/plans/2026-10-06-rename-to-hq-preparation.md with its .env.sh, in .worktrees/tack-8b7a28, after two fresh-context rounds (its code rebuilt from the plan text and run in scratch both times). On acceptance this session executes it inline from Task 1; Task 3 stops for the host-step approval, which covers both hosts.
  provenance: {"harness_session":"claude-code:529a99ac-8d12-4ea1-b9ff-8f3fd73d2c16","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T17:27:03Z (feat/rename-hq): review: plan round 3 — verdict: revise; findings: P1 3; reviewer: codex
- 2026-10-06T17:33:54Z (feat/rename-hq): resumed
  provenance: {"harness_session":"claude-code:529a99ac-8d12-4ea1-b9ff-8f3fd73d2c16","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T17:34:02Z (feat/rename-hq): parked (waiting on user, review): User reviews (GPT round 4) docs/plans/2026-10-06-rename-to-hq-preparation.md in .worktrees/tack-8b7a28 after the round 3 fixes: save checks --old against the checkout's prefix and the registry (Task 4); retarget writes each task's list in one tasks edit save (Task 4); kept files contained by resolved path at save and at rollback before any mutation (Task 5). On acceptance this session executes it inline from Task 1; Task 3 stops for the host-step approval.
  provenance: {"harness_session":"claude-code:529a99ac-8d12-4ea1-b9ff-8f3fd73d2c16","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T17:39:08Z (feat/rename-hq): review: plan round 4 — verdict: accept; findings: none; reviewer: codex
- 2026-10-06T17:57:31Z (feat/rename-hq): resumed
  provenance: {"harness_session":"claude-code:529a99ac-8d12-4ea1-b9ff-8f3fd73d2c16","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T18:06:38Z (feat/rename-hq): review: impl round 1 — verdict: accept; findings: Minor 2; reviewer: claude-code/claude-fable-5-1 (scoped: Tasks 1 and 2, before Task 3's merges)
- 2026-10-06T18:27:34Z (feat/rename-hq): review: impl round 2 — verdict: revise; findings: Important 1, Minor 6; reviewer: claude-code/claude-fable-5-1 (whole branch cad85ca..5b97a2a)
- 2026-10-06T18:30:05Z (feat/rename-hq): phase 1 steps 1 to 3 delivered (docs/plans/2026-10-06-rename-to-hq-preparation.md): the units call ~/.local/bin/session-archive on both hosts; rename-cutover is general (a repositories list, a split apply, a guard that knows the alias retarget and group rewrite, kept trust files); tools/harness-links. Deferred minors for the cutover plan are in the plan's execution record.
- 2026-10-06T18:32:21Z (main): parked (waiting on agent, dependency): When tasks-7580d2 has landed its resolver, write docs/plans/<date>-rename-to-hq-cutover.md for spec §3.1 steps 4 and 5 and phase 2 (the rehearsal; the runbook with its timers, attestations and systemd steps; the second host; verification), taking what flows-44890e and obs-ff4e76 chose, and the deferred minors in the preparation plan's execution record.
  provenance: {"harness_session":"claude-code:529a99ac-8d12-4ea1-b9ff-8f3fd73d2c16","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-06T19:24:26Z (main): From reviewing tasks-7580d2's plan: once [locations] exists, tasks rename and init --force rewrite [locations.<old>]/[locations.<new>] in the registry, and rename-cutover's guard (registry_view keeps every top-level table other than projects, aliases and groups) would then report 'locations' as a foreign change and refuse every rollback. The cutover plan must extend registry_view to drop locations.<old> and locations.<new> and add a test. Also: the second host needs a current tasks binary before its pre-move 'tasks -C <root> init --prefix tack --force' (an older binary drops [locations] on any registry write).
