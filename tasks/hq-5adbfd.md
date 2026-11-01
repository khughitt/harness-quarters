---
id: hq-5adbfd
title: Test that every tools/harness_stores adapter slug is declared in harnesses.toml
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-11-01T18:59:57Z
updated: 2026-11-01T18:59:57Z
depends: [hq-2eba07]
tags: []
origin: agent
---

Follow-up from hq-2eba07's final whole-branch review (minor 1, named risk a). tools/harness_stores ADAPTERS are keyed by harness slug; since hq-2eba07 the declared slugs live in harnesses.toml ([harnesses.<slug>]). Add a test asserting every ADAPTERS slug is a declared harness, so a new adapter cannot name an undeclared harness. Lands after feat/hq-2eba07-harness-manifest is merged.

## Notes

- 2026-11-01T18:59:57Z (add): created
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
