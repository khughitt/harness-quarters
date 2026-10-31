---
id: hq-d8a38c
title: Session archive guidance needs opaque tool-argument handling
status: idea
priority: 2
reviewed: true
reviewed_at: 2026-10-31T08:54:13Z
created: 2026-10-30T11:31:52Z
updated: 2026-10-31T08:54:13Z
depends: [obs-55431b]
parent: hq-a4ed45
tags: [feedback, gap, "from:sci"]
agent: codex
origin: agent
---

A current session archive stores tool-call message arguments as opaque gAAAA tokens while completed agent returns remain readable. The session-logs guidance describes parsing tool arguments as text and does not explain this mixed representation or a supported recovery route. A prompt-evidence export therefore preserved unreadable tokens; add detection and guidance to avoid labelling them exact readable prompts. The controller can reconstruct its dispatch text from the live conversation, but that must be identified as reconstruction rather than archive recovery.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-31-session-evidence-contact-brief.md — opaque arguments, honest recovery and Stage B ownership

## Notes

- 2026-10-30T11:31:52Z (feedback): created
  provenance: {"harness_session":"codex:01a18c50-32b0-7103-beae-7c810e393c5c","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
- 2026-10-31T08:54:13Z (main): scope: briefed; original body and P2 preserved; linked the cluster brief and parent hq-a4ed45, recorded the wait on existing obs-55431b, and handed the proposed opaque-argument/reconstruction requirement to that skill owner for reviewed-plan reconciliation. No duplicate reader/skill task, no recovery or activation claimed; actual trial readout and date-specific assessment remain required. origin: stage 1 matched, Codex 01a18c50-32b0-7103-beae-7c810e393c5c L1265 filing call / L1268 full created result with at 2026-10-30T11:31:52Z; L1300/L1311 record the later labelled reconstruction correction. L15 asks to execute another task; this guidance gap was agent-observed, so origin agent remains. Stage 2 not applicable: no origin_session. Lookup usage errors (RFC3339 --since and harness-prefixed show target) were corrected; they are not unavailable source evidence. brief: docs/notes/2026-10-31-session-evidence-contact-brief.md
  provenance: {"harness_session":"codex:01a1911c-b523-7f30-be2c-d617dca80c03","harness_session_source":"CODEX_THREAD_ID"}
