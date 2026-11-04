---
id: hq-5dc59c
title: Respect explicit user authorization when a paused agent has an active goal
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-11-02T23:54:03Z
updated: 2026-11-04T10:15:17Z
depends: []
parent: hq-2dd09b
tags: [feedback, friction, "from:lore"]
agent: codex
origin: agent
---

The root turn-pause refusal says to set any active goal to paused. The available goal tool permits that status only on an explicit user request, so a counter-triggered pause alone cannot authorize the call. Align the refusal with that authorization boundary or obtain a standing user grant; the agent guidance will report the needed user action rather than call a prohibited operation.

User requested fixing this after accepting audit hq-7fb9d5. Align root refusal text, related guidance and tests with the actual goal-tool boundary. A counter-triggered pause is not an explicit user pause request and grants no standing authorization. Stop owned work, report any goal the agent cannot legally pause, and request the specific user action only when needed; never call a forbidden mutation or claim the goal is paused. Verify no-active-goal, active-goal-without-authorization and explicit-user-pause cases. Preserve enforcement and bookkeeping/cancellation. Hook/global-guidance activation remains separately approved.

## References

- audit (input, required, kind=report): tasks/files/hq-7fb9d5/interruption-audit-report.md — accepted seven-case assessment and recommendations

## Notes

- 2026-11-02T23:54:03Z (feedback): created
  provenance: {"harness_session":"codex:01a19eab-55ff-7ce1-a9ea-059b29926cd2","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
