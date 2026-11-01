---
id: hq-e8f2db
title: "Add harnesses.toml manifest and shared harness_state loader, cleaners, and checks"
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: feat/hq-2eba07-harness-manifest
created: 2026-11-01T12:36:07Z
updated: 2026-11-01T14:10:30Z
started: 2026-11-01T13:37:20Z
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
- 2026-11-01T13:37:20Z (feat/hq-2eba07-harness-manifest): started
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T13:57:37Z (feat/hq-2eba07-harness-manifest): review: impl round 1 — verdict: accept; findings: minor 6; reviewer: claude-code/claude-sonnet-5-5
- 2026-11-01T14:10:30Z (feat/hq-2eba07-harness-manifest): review: impl round 2 — verdict: accept; findings: none; reviewer: claude-code/claude-haiku-5-5
