---
id: hq-ca01cf
title: Delete quiesce-timers and the archive leftovers
status: todo
priority: 3
size: s
complexity: low
process: direct
defer: 2026-11-30
created: 2026-10-19T11:55:19Z
updated: 2026-11-02T20:16:52Z
depends: [hq-7e1e9c]
tags: []
source: ops-630a87 boundary-proposal-r3.md A1
agent: claude-code/claude-opus-5-5
---

Why: one-off cutover tools and archived settings with no consumer (survey map hq): tools/quiesce-timers and its tests, claude/archive, codex/archive, the empty agent and command links. tools/rename-cutover stays (user decision 2026-11-02, see notes). Deferred past flow-trial-1 enrollment because hq is an enrolled project. Before landing, pass the flow-trial-1 gate (revision 3, change 5): judge the step's effect on what enrolled sessions see and what obs and the verdict tools measure; a step that changes either waits for readout (2027-02-16).

## Notes

- 2026-10-19T12:06:41Z (main): The 2026-11-30 deferral is the date to reassess this step against flow-trial-1, not an authorization: nothing that affects treatment or measurement lands before readout (2027-02-16) (owner review 2026-10-19).
- 2026-10-27T14:17:59Z (main): Depends on hq-7e1e9c (scope pass of hq-7e81ed, 2026-10-27): tools/relay_cutover_bootstrap/quiesce.py runs tools/quiesce-timers, so the relay cutover tool's deletion lands first or with this one.
- 2026-11-02T20:01:03Z (main): premise changed (hq-5300fd, landed 2026-11-02 as 083e10c1): rename-cutover is no longer a one-off with no consumer; it is now the general rename tool for in-tree and detached projects that the tasks records-home design (§4, §5.4) expects. Deleting it needs a decision on whether renames keep a cutover tool; the quiesce-timers and archive parts are unaffected
- 2026-11-02T20:16:52Z (main): scope: rename-cutover removed from this task; the user agreed on 2026-11-02 to keep the tool for now, since the records-home design relies on it and it now covers detached projects
