---
id: hq-ac80cb
title: "The work Claude home declares no skills: decide whether a work session should have flow, tasks and session-logs"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-06T15:28:54Z
updated: 2026-10-08T10:19:37Z
depends: []
parent: hq-72fd4b
tags: []
source: tack-dcb11a
agent: claude-code/claude-opus-5-5
---

Why: links.toml [harness.claude-work.links] declares CLAUDE.md, settings.json and the status line, and no skills, so a Claude Code session in ~/.claude-work has none of flow, tasks, session-logs, curate, scope or quick-add (~/.claude-work/skills holds only the harness-synced directory). The personal home declares all six, and Codex's work home reads ~/.agents/skills, which has them. The global instructions the work home loads require the tasks skill and the Trials rule's flow, and lore's profiles/work.md writes specs through tasks where. From the residue design §5, which left whether it was intended to the user.

Decision (scope 2026-10-08): give the work home the same six skill links as the personal home. Rejected: keeping the work home bare, which contradicts the instructions it loads. The user overrides if work sessions should stay skill-free.

Done: [harness.claude-work.links] gains "skills/flow", "skills/session-logs", "skills/curate", "skills/scope", "skills/tasks" and "skills/quick-add" with the personal home's targets; just link --apply from main on both hosts; just link-check clean on both; a Claude Code session started with CLAUDE_CONFIG_DIR=~/.claude-work lists the six skills.

Related, not in this task: local/claude/settings.work.json also lacks the personal settings' claude-sessionstart, claude-provenance, claim-guard and claude-posttooluse hooks; whether that is intended is a separate question.

Where: links.toml; docs/notes/2026-10-08-declared-surface-drift-brief.md; docs/specs/2026-10-06-residue-design.md §5; docs/specs/2026-09-19-project-profiles-design.md §3.4 and §10.

## Notes

- 2026-10-08T10:19:35Z (main): scope: scoped; todo under hq-72fd4b, P3 xs low direct; mirror the personal home's six skill links into [harness.claude-work.links] (the instructions it loads require tasks and flow), leaving it bare rejected; brief: docs/notes/2026-10-08-declared-surface-drift-brief.md
