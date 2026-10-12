---
id: hq-7b65dc
title: "Capability fact: Claude Code refuses a subagent Write to a report*-named file"
status: todo
priority: 3
size: s
complexity: mid
process: direct
created: 2026-10-12T11:00:29Z
updated: 2026-10-12T11:00:29Z
depends: []
tags: []
source: lore-5501d5
agent: claude-code/claude-opus-5-5
---

Claude Code refuses a subagent's Write when the basename starts with `report` (`report.md`, `report-*.md`) with "Subagents should return findings as text, not write report files." `<slug>-report.md` names (SDD's `task-N-report.md`) are accepted. Local logs on 2026-10-12: 6 refusals, about 500 accepted writes. Record it in facts/capabilities.toml with a probe that confirms the basename rule (prefix only vs any 'report' token) on the current version. lore's Processes fragment now carries the naming rule (lore-5501d5).
