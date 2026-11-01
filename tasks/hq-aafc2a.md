---
id: hq-aafc2a
title: "Support opencode sessions in hq sessions, session-archive, session-episodes and session-logs"
status: todo
priority: 3
size: m
complexity: mid
process: direct
created: 2026-11-01T09:55:07Z
updated: 2026-11-01T09:55:22Z
depends: [hq-ce3ab4]
parent: hq-19bd76
tags: [session-logs]
agent: claude-code/claude-opus-5-5
origin: user
---

Why: opencode is a harness in facts/capabilities.toml, but hq's session tools do not read its store. Part of hq-19bd76: parity through the per-harness adapter seam hq-57d68e establishes, reusing the SQLite capture route the Crush task designs.

Known (obs-175b10): ~/.local/share/opencode/opencode.db (WAL) and opencode-local.db; session carries directory, parent_id, model, time_archived; message and part hold content. Dormant since 2026-09-14.

Done:
- An opencode adapter behind the hq-57d68e seam: hq sessions lists and resumes opencode sessions, session-archive captures both databases (pruning off), session-episodes reads them, and the session-logs skill documents them (replacing its "store only" row).
- Gaps recorded as capability facts with evidence.
- just test passes.

## Notes

- 2026-11-01T09:55:07Z (add): created
  provenance: {"harness_session":"claude-code:165739d7-cba8-40c6-8ba4-1054d912e50f","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"user"}
