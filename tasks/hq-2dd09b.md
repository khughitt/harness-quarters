---
id: hq-2dd09b
title: Reduce premature turn-pause interruptions and make stop events reviewable
status: todo
priority: 2
size: m
complexity: mid
process: direct
created: 2026-11-04T10:13:23Z
updated: 2026-11-04T10:15:11Z
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
