---
id: hq-5adbfd
title: Test that every tools/harness_stores adapter slug is declared in harnesses.toml
status: doing
priority: 2
size: xs
complexity: low
process: direct
owner: test/hq-5adbfd-adapter-slug-manifest
created: 2026-11-01T18:59:57Z
updated: 2026-11-07T11:08:09Z
started: 2026-11-07T11:05:04Z
depends: [hq-2eba07]
tags: []
origin: agent
---

Follow-up from hq-2eba07's final whole-branch review (minor 1, named risk a). tools/harness_stores ADAPTERS are keyed by harness slug; since hq-2eba07 the declared slugs live in harnesses.toml ([harnesses.<slug>]). Add a test asserting every ADAPTERS slug is a declared harness, so a new adapter cannot name an undeclared harness. Lands after feat/hq-2eba07-harness-manifest is merged.

## Notes

- 2026-11-01T18:59:57Z (add): created
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-07T11:05:04Z (main): started
- 2026-11-07T11:05:06Z (test/hq-5adbfd-adapter-slug-manifest): resumed
- 2026-11-07T11:05:31Z (test/hq-5adbfd-adapter-slug-manifest): trial: flow-trial-1 — enrolled — flow on
- 2026-11-07T11:05:33Z (test/hq-5adbfd-adapter-slug-manifest): arm: flow-trial-1 — unit tack-5adbfd — flow on
- 2026-11-07T11:08:07Z (test/hq-5adbfd-adapter-slug-manifest): gate: scoped — adopted
- 2026-11-07T11:08:09Z (test/hq-5adbfd-adapter-slug-manifest): gate: implementing .worktrees/hq-5adbfd
