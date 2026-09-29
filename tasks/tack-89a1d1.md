---
id: tack-89a1d1
title: "Turn-boundary gate spec §3.3: the waking-child branch says the guard blocks the report once and the repeat stop is allowed"
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-09-28T10:40:59Z
updated: 2026-09-28T10:40:59Z
depends: []
tags: []
source: ops-0633a8
agent: claude-code/claude-opus-5-5
---

ops-0633a8 changed claim-guard's Claude Code child branch (CHILD_WAKES true) because controllers read option 4 as unsatisfiable and busy-waited: the guard cannot see children, so it blocks the option-4 report once. The reason now appends: 'This guard cannot see children, so it blocks that report once: if your last message already named the running child, reply with one line naming it again and end; the stop that follows is allowed. For a child the harness tracks, never wait in the foreground.' Update the Wakes bullet of docs/specs/2026-09-24-turn-boundary-gate-design.md §3.3 to match, and note in §2 or §4 why detection was rejected: Claude Code's Stop input documents no running-child signal, and the transcript format is undocumented.
