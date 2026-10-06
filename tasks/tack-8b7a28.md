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
updated: 2026-10-06T17:33:54Z
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
