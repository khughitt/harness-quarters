---
id: hq-ca01cf
title: "Delete rename-cutover, quiesce-timers and the archive leftovers"
status: todo
priority: 3
size: s
complexity: low
process: direct
defer: 2026-11-30
created: 2026-10-19T11:55:19Z
updated: 2026-10-19T12:06:41Z
depends: []
tags: []
source: ops-630a87 boundary-proposal-r3.md A1
agent: claude-code/claude-opus-5-5
---

Why: one-off cutover tools and archived settings with no consumer (survey map hq): tools/rename-cutover, tools/quiesce-timers and their tests, claude/archive, codex/archive, the empty agent and command links. Deferred past flow-trial-1 enrollment because hq is an enrolled project. Before landing, pass the flow-trial-1 gate (revision 3, change 5): judge the step's effect on what enrolled sessions see and what obs and the verdict tools measure; a step that changes either waits for readout (2027-02-16).

## Notes

- 2026-10-19T12:06:41Z (main): The 2026-11-30 deferral is the date to reassess this step against flow-trial-1, not an authorization: nothing that affects treatment or measurement lands before readout (2027-02-16) (owner review 2026-10-19).
