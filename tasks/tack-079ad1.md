---
id: tack-079ad1
title: "Remove superseded Codex standalone releases, keeping current and previous"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-09-29T21:09:40Z
updated: 2026-09-29T21:09:40Z
depends: []
parent: tack-1a3278
tags: [obs]
agent: claude-code/claude-opus-5-5
---

Why: ~/.codex/packages/standalone/releases keeps all 22 releases the auto-updater installed (7.4G, about 400M each, 2026-09-29); only `current` (a symlink, 0.159.0 then) and one previous release for rollback are needed. This frees space without deciding the session policy.
Done: releases/ holds the target of `current` and the next-newest release only; `codex --version` still runs; the freed size is recorded in the done message. Whether this repeats on a sweep (--every) is decided with the goal policy, not here.
Where to look: docs/notes/2026-09-29-session-store-retention-brief.md; ~/.codex/packages/standalone/{current,releases}. Leave app-server-daemon alone.
