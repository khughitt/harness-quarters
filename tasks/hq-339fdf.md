---
id: hq-339fdf
title: End agent waiting loops in both harnesses
status: todo
priority: 2
created: 2026-09-27T10:52:32Z
updated: 2026-11-07T21:59:21Z
depends: [obs-f074aa]
tags: [rules, obs]
source: "lore:docs/notes/2026-09-27-waiting-loops-brief.md"
agent: claude-code/claude-opus-5-5
origin: agent
---

Waiting loops take about 9.2% of agent context tokens (obs report 2026-09-26 §4). Goal: waiting on background work, a child agent or a long command costs a handful of requests in both harnesses. Brief: lore:docs/notes/2026-09-27-waiting-loops-brief.md. Research first, then one fix per loop shape filed from its result.

## Notes

- 2026-09-27T11:08:05Z (main): Both fixes are in (Claude: none needed; Codex: fd9e12a). Verify and close when obs-f074aa's detectors can show Codex poll loops and Claude sleep/no-op episodes stay near zero after 2026-09-27.
- 2026-11-07T21:59:21Z (main): origin backfill (tasks-0dfdf9): stage 1 unavailable (created 2026-09-27 before tasks-053e89); traced via claude-code:c82c3022-0ecc-44d8-a0dc-7e7b3f114b5e L494 agent scope/decomposition/audit filing (source lore:docs/notes/2026-09-27-waiting-loops-brief.md) -> origin=agent
