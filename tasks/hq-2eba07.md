---
id: hq-2eba07
title: Extract a declarative harness manifest so live-state hooks and capability facts read one source of truth
status: todo
priority: 2
size: m
complexity: mid
process: planned
created: 2026-11-01T01:25:51Z
updated: 2026-11-01T01:25:51Z
depends: []
tags: [architecture]
source: hq-6c8a9f
agent: agy
origin: mixed
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
