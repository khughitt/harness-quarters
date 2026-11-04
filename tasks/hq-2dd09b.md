---
id: hq-2dd09b
title: Reduce premature turn-pause interruptions and make stop events reviewable
status: todo
priority: 2
size: m
complexity: mid
process: direct
created: 2026-11-04T10:13:23Z
updated: 2026-11-04T10:17:03Z
depends: [lore-296a0f, obs-1450e7]
tags: []
source: hq-7fb9d5
agent: codex
origin: user
---

The user accepted the seven-case audit and requested actionable work to address its gaps. Keep safeguards against true runaway execution while ordinary authorized implementation continues. First milestone: warning/counter semantics are consistent across hook and guidance, a measured spawn-policy revision is prepared, and durable event history can distinguish enforced pauses from agent-initiated stops.

Evidence: completed audit hq-7fb9d5 and its independently accepted interruption-audit-report.md attachment. Four stops exhausted no configured limit; three were driven by policy during progressing plans. This is not a claim of a population-wide 100% false-positive rate.

This goal collects hq fixes and cross-project guidance/reporting prerequisites; each implementation task has its own verification. Preserve the existing 16-hour/root-call guard until a reviewed replacement is approved. Creating these tasks does not authorize live hook/global-instruction activation, host services, pushes or PRs. The one-week reassessment remains separately eligible even when fixes are incomplete.

## References

- audit (input, required, kind=report): tasks/files/hq-7fb9d5/interruption-audit-report.md — accepted seven-case assessment and recommendations

## Notes

- 2026-11-04T10:13:23Z (add): created
  provenance: {"harness_session":"codex:01a1a5e8-1e43-71c3-a5b1-6386809e007f","harness_session_source":"CODEX_THREAD_ID","origin":"user"}
- 2026-11-04T10:14:47Z (main): concerns: hq-7fb9d5 extension — implement the accepted audit recommendations and make future interruption rates reviewable; the completed audit itself is not defective.
- 2026-11-04T10:15:29Z (main): Filed hq warning text hq-51209b, lore guidance lore-296a0f, spawn policy hq-704fe5, hq history hq-e10b76, obs reporting obs-1450e7; reused hq-c58737 for read-only diagnostics/pointer audits and hq-5dc59c for goal authorization. Independent check-in hq-b9d356 is deferred until2026-11-11 with no completion dependencies. Broader obs-59789b scope remains preserved.
- 2026-11-04T10:17:03Z (main): Filing verification: seven executable corrective tasks are todo with explicit size, complexity and process: hq-51209b and lore-296a0f for warning/counter semantics, hq-704fe5 for measured spawn policy, hq-e10b76 and obs-1450e7 for history/reporting, reused hq-c58737 for read-only diagnostics/pointer audits, reused hq-5dc59c for goal authorization. Existing hq-5aa005 feedback waits on the shared protected-path fix; original feedback bodies remain intact. hq-b9d356 is an independent todo deferred until November 11, 2026, with no dependencies or parent hiding it behind completion. Current hq/lore/obs task checks all exit0 with zero errors; warnings5/14/3 are retained rather than silently fixed. No implementation, branch, worktree, scratch, host pointer, service, push or live policy activation occurred; tasks remain open for future execution. Process observation: host-load --section session reported nothing left running. The check-in is a dated tracker task, not an automatic notification.
