---
id: hq-72fd4b
title: "The declared harness surface matches what each host runs, and says when it drifts"
status: todo
priority: 2
created: 2026-10-08T10:19:02Z
updated: 2026-10-08T10:19:02Z
depends: []
tags: []
source: docs/notes/2026-10-08-declared-surface-drift-brief.md
---

Why: the residue's surface audit (hq-dcb11a) and the rename (hq-8b7a28) left four places where a host's harness surface differs from, or can silently drift from, what hq declares: a stray Codex skill on the second host, a work Claude home without the skills its instructions assume, hook commands that break on a lore or ops rename, and capability facts probed on harness versions no longer installed.

Done: the four children are closed, each by its own done line; the staleness question (hq-e18255) is decided from the brief and the re-probe's result.

Where: docs/notes/2026-10-08-declared-surface-drift-brief.md; links.toml; facts/capabilities.toml; docs/specs/2026-10-06-residue-design.md §4.6 and §5.
