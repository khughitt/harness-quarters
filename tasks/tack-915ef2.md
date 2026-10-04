---
id: tack-915ef2
title: "OpenCode sees no custom skills: the manifest declares no skills link for its home"
status: todo
priority: 2
size: s
complexity: low
process: direct
created: 2026-10-04T17:30:45Z
updated: 2026-10-04T17:30:45Z
depends: []
tags: []
source: flows-f8ea06
agent: claude-code/claude-opus-5-5
---

Observed 2026-10-04 during the flows cutover (flows-f8ea06, Task 6): Claude Code, Codex and Crush list the flow skill; OpenCode lists no custom skill at all. links.toml [harness.opencode.links] declares only AGENTS.md, ~/.config/opencode has no skills directory, and opencode.json loads only the superpowers plugin, so this predates the cutover. Done: find the skill path(s) OpenCode v2 reads (its own skills dir, ~/.agents/skills or ~/.claude/skills compatibility), declare the link in links.toml, apply on both hosts, and confirm an OpenCode session lists flow, curate, tasks and session-logs.
