---
id: hq-f5ccb6
title: Migrate live-state hooks to harnesses.toml
status: todo
priority: 2
size: m
complexity: mid
process: direct
created: 2026-11-01T12:36:37Z
updated: 2026-11-01T12:36:37Z
depends: [hq-bfef03]
parent: hq-2eba07
tags: [hooks]
agent: agy
origin: agent
plan: docs/plans/2026-11-01-harness-manifest.md
step: "Task 3: Migrate live-state hooks to harnesses.toml"
---

Step 3 of hq-2eba07 plan (spec §5.3.1-§5.3.4): drive .githooks/{harness-state-clean,harness-state-refresh,live-picks,codex-trust} from harnesses.toml via harness_state.py with deferred pre-lock loading in hooks, lazy usage(), and multi-unit TOML support.

## Notes

- 2026-11-01T12:36:37Z (add): created
  provenance: {"origin":"agent"}
