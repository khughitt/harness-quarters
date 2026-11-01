---
id: hq-e8f2db
title: "Add harnesses.toml manifest and shared harness_state loader, cleaners, and checks"
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-11-01T12:36:07Z
updated: 2026-11-01T12:36:07Z
depends: []
parent: hq-2eba07
tags: [hooks]
agent: agy
origin: agent
plan: docs/plans/2026-11-01-harness-manifest.md
step: "Task 1: Root harnesses.toml and shared harness_state loader, cleaners, and checks"
---

Step 1 of hq-2eba07 plan (spec §5.1-§5.2, §5.3.6): create root harnesses.toml and extend .githooks/harness_state.py with ManifestError, LiveStateSpec, load_manifest, check_gitattributes, check_filter_config, check_clean_tree, pure JSON/TOML cleaners, and CLI check.

## Notes

- 2026-11-01T12:36:07Z (add): created
  provenance: {"origin":"agent"}
