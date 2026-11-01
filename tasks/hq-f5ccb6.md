---
id: hq-f5ccb6
title: Migrate live-picks to harnesses.toml
status: todo
priority: 2
size: m
complexity: mid
process: direct
created: 2026-11-01T12:36:37Z
updated: 2026-11-01T13:14:41Z
depends: [hq-bfef03]
parent: hq-2eba07
tags: [hooks]
agent: agy
origin: agent
plan: docs/plans/2026-11-01-harness-manifest.md
step: "Task 3: Migrate live-picks to harnesses.toml"
---

Step 3 of hq-2eba07 plan (spec §5.3.4): check main for hq-ece26a, copy harnesses.toml into live-picks scratch fixtures, and drive .githooks/live-picks from harnesses.toml via harness_state.py with lazy usage(), deferred pre-lock loading in hook mode, multi-unit TOML support, clean-only skipping, LiveStateSpec adopt_detached, and 6b434eb rollback byte parity.

## Notes

- 2026-11-01T12:36:37Z (add): created
  provenance: {"origin":"agent"}
