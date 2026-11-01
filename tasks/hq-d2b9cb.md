---
id: hq-d2b9cb
title: "Enforce fail-closed filter config, staged-tree pre-commit gate, and reference docs"
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-11-01T12:36:38Z
updated: 2026-11-01T13:15:02Z
depends: [hq-1a6bba]
parent: hq-2eba07
tags: [hooks, docs]
agent: agy
origin: agent
plan: docs/plans/2026-11-01-harness-manifest.md
step: "Task 5: Enforce fail-closed filter config, staged-tree pre-commit gate, and reference docs"
---

Step 5 of hq-2eba07 plan (spec §5.3.5-§5.3.6, §5.5, §7): set filter.harness-state.required = true in just setup (noting the shared repository config write on hq-2eba07 at that moment), enforce check_filter_config in harness-state-refresh and pre-commit (--staged-tree), and update AGENTS.md, README.md, and docs/runbooks/adding-a-harness.md.

## Notes

- 2026-11-01T12:36:38Z (add): created
  provenance: {"origin":"agent"}
