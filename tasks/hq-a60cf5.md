---
id: hq-a60cf5
title: session-episodes extract reads every store obs indexes
status: todo
priority: 3
size: s
complexity: low
process: direct
created: 2026-10-20T16:05:12Z
updated: 2026-10-20T16:05:12Z
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
