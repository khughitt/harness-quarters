---
id: tack-322fa4
title: "A general model of tack's kinds (skills, hooks, flows) that an adaptive layer can modulate by model tier"
status: shelved
priority: 2
created: 2026-09-30T14:12:36Z
updated: 2026-09-30T14:48:03Z
depends: []
tags: [quick-add]
source: "mindful:thought:a3b0b88f1902753a00a058225bd3a798"
agent: claude-code/claude-opus-5-5
---

Name the types of things tack represents: skills, hooks, flows/processes (formulated as DAGs or weighted graphs with prose on nodes/edges, gates, decisions, thresholds), and anything else. With that model, an adaptive layer (by model tier/family or other state) can be an alternate flow or a modified one (different prose, weights). Context: making hooks and skills adaptive raises what else should respond to the same variables. Related: tack-9ec1eb (per-model variants).

## Notes

- 2026-09-30T14:12:41Z (main): Related: ops-1a552c (model-adaptive hook messages)
- 2026-09-30T14:28:37Z (main): shelved: tack-ec379d wakes (the eval chain obs-00809f -> tack-026612 exists), or a second adaptive dimension beyond hook text (ops-1a552c) is implemented, giving two concrete kinds to generalise from
- 2026-09-30T14:28:37Z (main): scope: shelved; the skills half is tack-ec379d's fragment design (per-model variants as a filter over fragments), shelved on the same missing eval chain; hooks half is ops-1a552c, whose evidence points at repetition, not model tier; brief: ops:docs/notes/2026-09-30-adaptive-hook-messages-brief.md
- 2026-09-30T14:48:03Z (main): Correction after review of the brief: claim-guard child detection (ops-ed76fe) had already removed most repeat blocks; ops-1a552c now targets unnecessary blocks, not model tier. The shelf and its wake condition stand.
