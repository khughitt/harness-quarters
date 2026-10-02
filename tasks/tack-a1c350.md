---
id: tack-a1c350
title: Implementation-plan command uses a bare unittest module name that the test front door cannot import; use its package-qualified name.
status: idea
priority: 2
created: 2026-09-30T18:15:46Z
updated: 2026-10-02T15:33:37Z
depends: []
tags: [feedback, friction, "from:tasks"]
agent: codex
---

## Notes

- 2026-10-02T15:33:37Z (main): scope: drop; one plan in the tasks project named a bare unittest module (test_cli); the session corrected it to tests.test_cli in place (Codex rollout 01a0f385, 2026-09-30). The general remedy, plans that run their verification commands while writing them, is upstream writing-plans PR obra/superpowers#2295 (open). proposal: drop as a one-off already fixed in its plan, with the general fix tracked upstream
