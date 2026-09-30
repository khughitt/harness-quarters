---
id: tack-079ad1
title: "Remove superseded Codex standalone releases, keeping current and previous"
status: done
priority: 3
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-29T21:09:40Z
updated: 2026-09-30T14:54:00Z
started: 2026-09-30T14:53:59Z
completed: 2026-09-30T14:53:59Z
depends: []
parent: tack-1a3278
tags: [obs]
model: claude-opus-5-5
agent: claude-code/claude-opus-5-5
---

Why: ~/.codex/packages/standalone/releases keeps all 22 releases the auto-updater installed (7.4G, about 400M each, 2026-09-29); only `current` (a symlink, 0.159.0 then) and one previous release for rollback are needed. This frees space without deciding the session policy.
Done: releases/ holds the target of `current` and the next-newest release only; `codex --version` still runs; the freed size is recorded in the done message. Whether this repeats on a sweep (--every) is decided with the goal policy, not here.
Where to look: docs/notes/2026-09-29-session-store-retention-brief.md; ~/.codex/packages/standalone/{current,releases}. Leave app-server-daemon alone.

## Notes

- 2026-09-30T14:53:59Z (main): started
  provenance: {"harness_session":"claude-code:a98f6b52-4a0e-45db-a015-99bd1e97063e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-30T14:53:59Z (main): done
  provenance: {"harness_session":"claude-code:a98f6b52-4a0e-45db-a015-99bd1e97063e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-30T14:53:59Z (main): Removed 21 superseded Codex releases (0.144.6 to 0.158.0); kept current 0.159.2 and previous 0.159.0; freed 7084 MiB (releases/ now 848M); codex --version runs; no running process or link used a removed release. The auto-updater adds about 400M per release, so a recurring sweep is for tack-401088's design to decide.
  provenance: {"harness_session":"claude-code:a98f6b52-4a0e-45db-a015-99bd1e97063e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
