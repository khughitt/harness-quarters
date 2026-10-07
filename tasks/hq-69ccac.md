---
id: hq-69ccac
title: Require worktree isolation for direct code changes as well as planned work
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-13T17:29:59Z
updated: 2026-09-13T18:26:06Z
started: 2026-09-13T18:25:48Z
completed: 2026-09-13T18:26:06Z
depends: []
tags: [skills]
source: tasks-61cc5c
---

Why: prism-28e29c ran directly on main because the global worktree rule applies only to brainstorming + planning sessions. The process field in tasks-61cc5c does not fix this. Done: widen the global AGENTS.md worktree trigger to cover any repository code change as well as brainstorming/planning; retain explicit user override, reuse of an existing task worktree, git worktree add under .worktrees/, and just setup when defined. Read-only investigation and task-record maintenance do not need new worktrees. Verify the canonical source and rendered harness instructions, and check a direct small fix selects isolation without entering brainstorming. This policy fix is independent of the tasks CLI change. Where: ai AGENTS.md and the shared instruction distribution/source path; locate the canonical owner before editing.

## Notes

- 2026-09-13T18:25:48Z (main): process: direct (body settles outcome, approach, check). Working in the main ai checkout on purpose: ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md symlink into it, and the task asks to verify the rendered instructions.
- 2026-09-13T18:26:06Z (main): Global worktree rule now triggers on any repository code change, direct or planned: reuse the task's worktree or git worktree add under .worktrees/ with just setup; planned work does it before the spec; read-only investigation and task-record maintenance exempt; explicit in-place instruction wins. Rendered ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md verified through their symlinks. Also tracked the scope skill symlink in agents/skills.
