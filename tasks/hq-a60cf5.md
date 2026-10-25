---
id: hq-a60cf5
title: session-episodes extract reads every store obs indexes
status: todo
priority: 3
size: s
complexity: low
process: direct
defer: 2027-02-17
created: 2026-10-20T16:05:12Z
updated: 2026-10-25T18:02:55Z
depends: []
parent: hq-cff824
tags: [session-logs]
agent: claude-code
---

Why: _roots (agents/bin/session-episodes:1213) reads ~/.claude/projects and ~/.codex/sessions, one path per SESSION_LOGS_CLAUDE / SESSION_LOGS_CODEX. obs's store_roots (obs stores.py) indexes both Claude homes and sessions plus archived_sessions under both Codex homes (obs-0d1d99). So the pre-flow episodes handed to obs baseline silently miss ~/.claude-work, ~/.codex-work and the 594 rollouts in ~/.codex/archived_sessions on this host, while the session-logs skill says every file in both stores is seen.
Done: the default roots match obs's six. Each SESSION_LOGS_* variable accepts an os.pathsep list that replaces the defaults, as OBS_CODEX_SESSIONS does. A Codex thread present in both sessions and archived_sessions counts once. The stderr summary counts files per root. The skill's Stores table and extract step name the roots. Tests in agents/bin/test_session_episodes.py use temporary stores only, and just test passes.
Where to look: agents/bin/session-episodes (_roots, scan_stores); obs stores.py store_roots and obs-0d1d99 for the duplicate-thread rule; agents/skills/session-logs/SKILL.md; [ref:brief] §2. This is independent of the brief's choice of origin-lookup owner.

## References

- brief (input, kind=brief): docs/notes/2026-10-20-session-store-reach-brief.md — context and questions for this work
- trial-gate (input, required, kind=spec): docs/specs/2026-10-23-session-evidence-reader-design.md — sections 11.1–11.4 and the scoped skill-text edit require a gate assessment before landing

## Notes

- 2026-10-20T16:51:34Z (main): decision 2026-10-20: kept independent of the proposed hq logs shared reader (brief §4): the silent coverage gap in obs's baseline input is worth closing now, and the shared reader, when it lands, replaces _roots with an import. No dependency to add.
- 2026-10-25T18:02:54Z (test/hq-a45dd8-two-turn-evidence): trial gate assessment under hq-cff824: the scoped change includes editing the installed session-logs skill Stores table and extract instructions, so it changes enrolled-session treatment regardless of whether baseline extraction itself feeds the trial verdict. Spec ae0f8ee sections 11.1 and 11.4 leave the planning-doc measurement classification unsettled; this assessment does not override it. Keep the whole scoped change deferred until after 2027-02-16 readout, reassess on/after 2027-02-17 and pass the gate on the landing date. This supersedes the 2026-10-20 note saying the gap is worth closing now; no skill or extractor roots changed. Preserve independent ownership rather than adding a new implementation dependency.
