---
id: tack-3bea62
title: "Auto-memory is scoped to one repository, so a preference the owner states for all projects reaches only that repository's sessions"
status: idea
priority: 2
created: 2026-10-06T23:29:41Z
updated: 2026-10-06T23:29:41Z
depends: []
tags: [feedback, gap, "from:material"]
agent: claude-code/claude-opus-5-5
---

Claude Code's auto-memory lives in a per-project directory under the harness home. When the owner states a cross-project preference (here: how every project's review sheets should be presented), saving it as memory leaves sessions in other repositories unaware of it. Nothing in the declared harness surface offers a host-wide memory, or routes such an entry to the shared instruction corpus. Wanted: a host-level memory location linked into every project's harness home, or a documented route that promotes a memory entry to the shared instructions.
