---
id: hq-07e3bf
title: Wire the capture notice hook into Claude Code and Codex SessionStart
status: doing
priority: 2
size: s
complexity: low
process: direct
owner: main
created: 2026-10-09T17:59:17Z
updated: 2026-10-10T11:27:35Z
started: 2026-10-10T11:27:30Z
depends: [ops-1aa710]
tags: [hooks]
source: "ops:docs/specs/2026-10-09-capture-triage-design.md#8"
agent: claude-code/claude-opus-5-5
---

Register ops's hooks/capture-notice as a SessionStart hook in the Claude Code settings and in codex/hooks.json (personal; leave hooks.work.json alone), refreshing Codex's trusted hash through hq's usual path. Done when a fresh Claude Code session and a fresh Codex session each show the notice line for a known nonzero pending count, and nothing when it is zero. Piece of ops-2bad69; spec ops docs/specs/2026-10-09-capture-triage-design.md §8.

## Notes

- 2026-10-10T11:27:30Z (main): started
  provenance: {"harness_session":"claude-code:b7850bb1-0a62-4fb3-8409-fa6537d7da3b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-10T11:27:34Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-10-10T11:27:34Z (main): arm: flow-trial-1 — unit tack-07e3bf — flow off
