---
id: hq-ce3ab4
title: "Support Crush sessions in hq sessions, session-archive, session-episodes and session-logs"
status: todo
priority: 2
size: l
complexity: high
process: planned
created: 2026-11-01T09:55:05Z
updated: 2026-11-01T09:55:05Z
depends: []
parent: hq-19bd76
tags: [session-logs]
agent: claude-code/claude-opus-5-5
origin: user
---

Why: Crush is in active use (about 150 sessions across 24 projects as of 2026-10-15, per obs-175b10), but hq's session tools do not read it. Part of hq-19bd76: parity through the per-harness adapter seam hq-57d68e establishes.

Known (obs-175b10): one SQLite store per project at <project>/.crush/crush.db, listed in ~/.local/share/crush/projects.json; several project paths are symlink aliases of one checkout, so stores dedupe by resolved db path; tables sessions (parent_session_id, timings, message_count) and messages (role, parts JSON). A live SQLite database does not fit session-archive's append-only file mirror, so capture needs a database route (for example a consistent read-only snapshot) designed here.

Done:
- A Crush adapter behind the hq-57d68e seam: hq sessions lists and resumes Crush sessions across projects, session-archive captures the stores consistently while Crush writes (pruning off), session-episodes reads them, and the session-logs skill documents them.
- Gaps recorded as capability facts with evidence; crush added to facts/capabilities.toml harnesses.
- just test passes.

## Notes

- 2026-11-01T09:55:05Z (add): created
  provenance: {"harness_session":"claude-code:165739d7-cba8-40c6-8ba4-1054d912e50f","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"user"}
