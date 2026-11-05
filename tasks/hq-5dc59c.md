---
id: hq-5dc59c
title: Respect explicit user authorization when a paused agent has an active goal
status: doing
priority: 2
size: xs
complexity: low
process: direct
owner: main
created: 2026-11-02T23:54:03Z
updated: 2026-11-05T20:41:57Z
started: 2026-11-04T10:27:21Z
depends: []
parent: hq-2dd09b
tags: [feedback, friction, "from:lore"]
agent: codex
origin: user
---

The root turn-pause refusal says to set any active goal to paused. The available goal tool permits that status only on an explicit user request, so a counter-triggered pause alone cannot authorize the call. Align the refusal with that authorization boundary or obtain a standing user grant; the agent guidance will report the needed user action rather than call a prohibited operation.

User requested fixing this after accepting audit hq-7fb9d5. Align root refusal text, related guidance and tests with the actual goal-tool boundary. A counter-triggered pause is not an explicit user pause request and grants no standing authorization. Stop owned work, report any goal the agent cannot legally pause, and request the specific user action only when needed; never call a forbidden mutation or claim the goal is paused. Verify no-active-goal, active-goal-without-authorization and explicit-user-pause cases. Preserve enforcement and bookkeeping/cancellation. Hook/global-guidance activation remains separately approved.

## References

- audit (input, required, kind=report): tasks/files/hq-7fb9d5/interruption-audit-report.md — accepted seven-case assessment and recommendations

## Notes

- 2026-11-02T23:54:03Z (feedback): created
  provenance: {"harness_session":"codex:01a19eab-55ff-7ce1-a9ea-059b29926cd2","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
- 2026-11-04T10:15:19Z (main): scope: scoped; user explicitly requested fixes after accepting the audit in this session. Original feedback preserved; current protection/refusal behavior verified by hq-7fb9d5 with source records and transcripts. No implementation or live activation performed.
  provenance: {"harness_session":"codex:01a1a5e8-1e43-71c3-a5b1-6386809e007f","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-04T10:27:21Z (fix/hq-2dd09b): started
  provenance: {"harness_session":"codex:01a1a613-e49a-78d0-a8ab-b3e6a5217919","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-04T10:27:43Z (fix/hq-2dd09b): arm: flow-trial-1 — unit tack-2dd09b — flow off
- 2026-11-04T10:28:25Z (fix/hq-2dd09b): Direct fix shares the hydrated .worktrees/hq-2dd09b worktree. Caller search found ROOT_TEXT used by refusal() for threshold and limits-changed refusals; paused update_goal cancellation is already allowed only with status paused and does not confer user authorization. Baseline hook/allowlist behavior from the warning task remains passing. RED focused refusal/update_goal check: 2 failed, 1 passed, 88 deselected, specifically the unconditional goal instruction. Fix changes instructions and current README, preserving the authorization-neutral allowlist. Semantic review must exercise no active goal, active unauthorized goal and explicit user pause. Live activation remains gated.
- 2026-11-04T10:28:55Z (fix/hq-2dd09b): Verification: RED focused hook refusal/goal allowlist run failed 2 tests and passed 1 (88 deselected); GREEN just test-one tools/test_turn_pause_hook.py tools/test_turn_pause_allowlist.py tools/test_hq_pause.py -q passed 374 tests. Mandatory just check-hygiene passed. No broad suite by valid policy; no remote evidence. No goal status was changed, no host pointer repointed, and no activation performed.
- 2026-11-04T10:31:33Z (fix/hq-2dd09b): review: impl round 1 — verdict: accept; findings: none; reviewer: codex/gpt-6.1-sol
- 2026-11-04T10:49:39Z (fix/hq-2dd09b): Accepted implementation and semantic review cover no active goal, unauthorized active goal and explicit user pause; supporting report docs/notes/2026-11-04-warnings-goals-r1-report.md and integration disclosures docs/notes/2026-11-04-turn-pause-handoff.md. No goal status was changed. Shared locked .worktrees/hq-2dd09b is retained by open hq-c58737; no independent scratch/evidence. Branch fix/hq-2dd09b remains unmerged pending separate user live activation approval; no pushes, services or host-pointer changes. Focused hook/allowlist/CLI374 tests passed, broad work deliberately omitted under policy, mandatory hygiene passed, remote evidence absent.
- 2026-11-04T10:51:58Z (fix/hq-2dd09b): parked (waiting on user, approval): User authorizes live activation of reviewed hq codef7259d9098f66ed2e60fa14f9aeb22824f2ba53d; agent then refreshes main/checks and integrates fix/hq-2dd09b from .worktrees/hq-2dd09b. Shared design approval alone does not authorize activation; see docs/notes/2026-11-04-turn-pause-handoff.md.
  provenance: {"harness_session":"codex:01a1a613-e49a-78d0-a8ab-b3e6a5217919","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-05T20:34:15Z (fix/hq-2dd09b): resumed
- 2026-11-05T20:41:57Z (main): resumed
