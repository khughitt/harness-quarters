---
id: hq-bfef03
title: Migrate tools/harness-facts and facts/capabilities.toml to harnesses.toml
status: done
priority: 2
size: s
complexity: low
process: direct
owner: feat/hq-2eba07-harness-manifest
created: 2026-11-01T12:36:35Z
updated: 2026-11-01T14:41:54Z
started: 2026-11-01T14:10:33Z
completed: 2026-11-01T14:41:54Z
closed: 2026-11-01T14:41:54Z
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
- 2026-11-01T14:27:03Z (feat/hq-2eba07-harness-manifest): review: impl round 1 — verdict: revise; findings: important 2, minor 4; reviewer: claude-code/claude-sonnet-5-5
- 2026-11-01T14:41:53Z (feat/hq-2eba07-harness-manifest): review: impl round 2 — verdict: accept; findings: none; reviewer: claude-code/claude-haiku-5-5
- 2026-11-01T14:41:54Z (feat/hq-2eba07-harness-manifest): done
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-01T14:41:54Z (feat/hq-2eba07-harness-manifest): Task 2 complete: tools/harness-facts reads [harnesses] from harnesses.toml; capabilities.toml harnesses list removed (54953664, fix fa6ff5f6). Verification: focused 110 passed; just test rc=0 (247, 1301, 391, 1 passed); list/get output byte-identical; ops-check, ops-docs check, harness-facts check, tasks check exit 0. Task review (sonnet) revise -> fix round 1 -> re-review clean (haiku). Deferred minors in SDD ledger. Nothing pushed.
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
