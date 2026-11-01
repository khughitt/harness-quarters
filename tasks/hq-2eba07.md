---
id: hq-2eba07
title: Extract a declarative harness manifest so live-state hooks and capability facts read one source of truth
status: doing
priority: 2
size: m
complexity: mid
process: planned
owner: feat/hq-2eba07-harness-manifest
created: 2026-11-01T01:25:51Z
updated: 2026-11-01T10:14:45Z
started: 2026-11-01T09:55:45Z
depends: []
tags: [hooks]
source: hq-6c8a9f
agent: agy
origin: mixed
spec: docs/specs/2026-11-01-harness-manifest-design.md
---

Why: Onboarding agy in hq-6c8a9f required parallel edits across .githooks/harness-state-clean (JSON_FILES, *_JSON_KEYS), .githooks/harness-state-refresh (PATTERNS), .githooks/live-picks (OWNED, RECORDS, JSON_GROUPS, CLEAN, FIELD), and facts/capabilities.toml (harnesses). A declarative manifest eliminates per-harness constant duplication while keeping format/store adapters explicit.

Done:
- A declarative harness manifest in hq defines each harness's settings path, format, clean-filter keys, and live-picks units and record file.
- .githooks/harness-state-clean, .githooks/harness-state-refresh, and .githooks/live-picks load the manifest instead of maintaining parallel per-harness constant tables.
- Rollback and unit tests continue to pass via just test.

Where: .githooks/{harness-state-clean,harness-state-refresh,live-picks}, facts/capabilities.toml.

## Notes

- 2026-11-01T01:25:51Z (add): created
  provenance: {"origin":"mixed"}
- 2026-11-01T09:55:45Z (main): started
- 2026-11-01T09:56:11Z (feat/hq-2eba07-harness-manifest): resumed
- 2026-11-01T09:56:27Z (feat/hq-2eba07-harness-manifest): trial: flow-trial-1 — enrolled — flow off
- 2026-11-01T09:56:28Z (feat/hq-2eba07-harness-manifest): arm: flow-trial-1 — unit tack-2eba07 — flow off
- 2026-11-01T10:06:10Z (feat/hq-2eba07-harness-manifest): originating ask (agy session fdddf278, 2026-10-31/2026-11-01): user asked how to improve harness abstraction/compartmentalization/configuration so onboarding new harnesses minimizes ad-hoc/hardcoded logic, and asked at hq-6c8a9f closeout for follow-ups; filing agent scoped hq-2eba07 to a declarative manifest driving .githooks/{harness-state-clean,harness-state-refresh,live-picks} and facts/capabilities.toml. Selected Approach 1 (root harnesses.toml read by .githooks/harness_state.py and tools/harness-facts, removing duplicate harnesses list from facts/capabilities.toml); rejected Approach 2 (extending links.toml, which keys on home directories rather than capability slugs or tracked settings files) and Approach 3 (.githooks/harnesses.toml with duplicate harnesses kept in facts/capabilities.toml).
