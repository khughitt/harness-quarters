---
id: hq-eff4db
title: Fix README and AGENTS references for the shared checker
status: todo
priority: 3
size: s
complexity: low
process: direct
created: 2026-10-25T01:23:16Z
updated: 2026-10-25T01:23:16Z
depends: []
parent: hq-c6a149
tags: [docs]
agent: claude-code
plan: docs/plans/2026-10-24-ops-check-adoption.md
step: "Task 2: Fix the guide references"
---

Plan Task 2 of hq-c6a149 (spec D8). Apply the plan's table of rewrites; no README or AGENTS finding remains and ops-docs check passes. Why the bare-prefix form: the checker parses the last word before the backtick, so a possessive reads as the prefix s.
