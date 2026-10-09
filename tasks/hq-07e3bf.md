---
id: hq-07e3bf
title: Wire the capture notice hook into Claude Code and Codex SessionStart
status: todo
priority: 2
size: s
complexity: low
process: direct
created: 2026-10-09T17:59:17Z
updated: 2026-10-09T17:59:18Z
depends: [ops-1aa710]
tags: [hooks]
source: "ops:docs/specs/2026-10-09-capture-triage-design.md#8"
agent: claude-code/claude-opus-5-5
---

Register ops's hooks/capture-notice as a SessionStart hook in the Claude Code settings and in codex/hooks.json (personal; leave hooks.work.json alone), refreshing Codex's trusted hash through hq's usual path. Done when a fresh Claude Code session and a fresh Codex session each show the notice line for a known nonzero pending count, and nothing when it is zero. Piece of ops-2bad69; spec ops docs/specs/2026-10-09-capture-triage-design.md §8.
