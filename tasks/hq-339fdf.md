---
id: hq-339fdf
title: End agent waiting loops in both harnesses
status: todo
priority: "2"
created: 2026-09-27T10:52:32Z
updated: 2026-09-27T11:08:05Z
depends: [obs-f074aa]
tags: [rules, obs]
source: docs/notes/2026-09-27-waiting-loops-brief.md
agent: claude-code/claude-opus-5-5
---

Waiting loops take about 9.2% of agent context tokens (obs report 2026-09-26 §4). Goal: waiting on background work, a child agent or a long command costs a handful of requests in both harnesses. Brief: docs/notes/2026-09-27-waiting-loops-brief.md. Research first, then one fix per loop shape filed from its result.

## Notes

- 2026-09-27T11:08:05Z (main): Both fixes are in (Claude: none needed; Codex: fd9e12a). Verify and close when obs-f074aa's detectors can show Codex poll loops and Claude sleep/no-op episodes stay near zero after 2026-09-27.
