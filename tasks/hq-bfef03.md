---
id: hq-bfef03
title: Migrate tools/harness-facts and facts/capabilities.toml to harnesses.toml
status: doing
priority: 2
size: s
complexity: low
process: direct
owner: feat/hq-2eba07-harness-manifest
created: 2026-11-01T12:36:35Z
updated: 2026-11-01T14:10:33Z
started: 2026-11-01T14:10:33Z
depends: [hq-e8f2db]
parent: hq-2eba07
tags: [hooks]
agent: agy
origin: agent
plan: docs/plans/2026-11-01-harness-manifest.md
step: "Task 2: Migrate tools/harness-facts and facts/capabilities.toml to harnesses.toml"
---

Step 2 of hq-2eba07 plan (spec §5.4): remove duplicate harnesses list from facts/capabilities.toml and read [harnesses] from harnesses.toml in tools/harness-facts with --manifest and backward-compatible positional validate/lookup.

## Notes

- 2026-11-01T12:36:35Z (add): created
  provenance: {"origin":"agent"}
- 2026-11-01T14:10:33Z (feat/hq-2eba07-harness-manifest): started
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
