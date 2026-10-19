---
id: hq-5f06aa
title: Move harness-remap from ops into hq as hq remap
status: todo
priority: 3
size: s
complexity: mid
process: direct
defer: 2026-11-30
created: 2026-10-19T11:56:10Z
updated: 2026-10-19T12:06:42Z
depends: []
tags: []
source: ops-630a87 boundary-proposal-r3.md A7
agent: claude-code/claude-opus-5-5
---

Why: rewriting session stores after a checkout move is part of their file lifecycle, which hq owns (revision 3, A7). Interface unchanged; it also learns every declared home instead of the fixed defaults. Deferred past enrollment: hq is enrolled and obs indexes the stores it rewrites. Before landing, pass the flow-trial-1 gate (revision 3, change 5): judge the step's effect on what enrolled sessions see and what obs and the verdict tools measure; a step that changes either waits for readout (2027-02-16).

## Notes

- 2026-10-19T12:06:42Z (main): The 2026-11-30 deferral is the date to reassess this step against flow-trial-1, not an authorization: nothing that affects treatment or measurement lands before readout (2027-02-16) (owner review 2026-10-19).
