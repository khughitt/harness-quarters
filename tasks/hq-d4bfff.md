---
id: hq-d4bfff
title: "Confirm OpenCode on europa lists the shared skills (flow, curate, tasks, session-logs)"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-10T12:51:00Z
updated: 2026-10-10T12:51:01Z
depends: []
tags: []
source: hq-915ef2
agent: claude-code/claude-opus-5-5
---

hq-915ef2 found OpenCode v2.0.26 reads ~/.agents/skills and ~/.claude/skills itself, so no link is needed; titan verified. On europa: check 'opencode --version' is 2.x with that discovery, that ~/.agents/skills holds the declared links (just link-check), and that 'opencode run --standalone' lists flow, curate, tasks and session-logs. If OpenCode there is older, upgrade it rather than adding a link.

## Notes

- 2026-10-10T12:51:00Z (main): concerns: hq-915ef2 extension — the second host's half of its done check; europa was offline at close
