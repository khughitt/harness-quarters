---
id: tack-dcb11a
title: "Residue: rename in place, capability facts, aggregated agent surface, archive review"
status: todo
priority: 1
size: l
complexity: high
process: planned
created: 2026-10-04T10:54:36Z
updated: 2026-10-04T10:58:44Z
depends: [ops-f2405d]
tags: []
source: ops-cb9749
agent: claude-code
---

Why: phase 3 of the agent layer split (ops docs/specs/2026-10-03-agent-layer-split-design.md §4.1, §5.3, §6). What remains of tack after flows and lore leave is harness support: homes, links, state hygiene, session archive, mods, capability facts.

Done: tack renamed in place by the rename design's procedure (tasks rename, identity.toml, the mirror, the registry on each host, links.toml targets, just projects in ops) once the user names it; an ordinary project guide and [agents] scope dropped from identity.toml (landed with phase 2's removal commit); capability facts with a typed value and a separate evidence status, starting with CHILD_WAKES, WAKING and IN_FLIGHT moved out of ops hooks/claim-guard; wake-judge kept here as the probe tool; archive/ and doc/ref/ reviewed in place with a recorded disposition; tack's identity-mirror feedback scope corrected.
