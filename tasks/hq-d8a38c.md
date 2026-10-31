---
id: hq-d8a38c
title: Session archive guidance needs opaque tool-argument handling
status: idea
priority: 2
created: 2026-10-30T11:31:52Z
updated: 2026-10-31T08:54:08Z
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
