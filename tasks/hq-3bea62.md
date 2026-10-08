---
id: hq-3bea62
title: "Auto-memory is scoped to one repository, so a preference the owner states for all projects reaches only that repository's sessions"
status: idea
priority: 2
created: 2026-10-06T23:29:41Z
updated: 2026-10-08T10:38:41Z
depends: []
tags: [feedback, gap, "from:material"]
agent: claude-code/claude-opus-5-5
---

Claude Code's auto-memory lives in a per-project directory under the harness home. When the owner states a cross-project preference (here: how every project's review sheets should be presented), saving it as memory leaves sessions in other repositories unaware of it. Nothing in the declared harness surface offers a host-wide memory, or routes such an entry to the shared instruction corpus. Wanted: a host-level memory location linked into every project's harness home, or a documented route that promotes a memory entry to the shared instructions.

## Notes

- 2026-10-08T10:38:41Z (main): scope: drop; the documented route the idea asked for landed in lore fdbd1c6 (lore-c58645, 2026-10-07): the global Feedback rule files the user's cross-project feedback with the owning project (lore for instructions and skills), and a memory may keep only a local copy; filed from the same review-sheet incident, whose preference is now the global Communication rule on image sheets; a host-wide memory stays unwanted since a memory never replaces the report; proposal: drop as delivered by lore-c58645 (lore fdbd1c6)
