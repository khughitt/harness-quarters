---
id: hq-1a6bba
title: "Migrate harness-state-clean, harness-state-refresh, and codex-trust to harnesses.toml"
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: feat/hq-2eba07-harness-manifest
created: 2026-11-01T13:14:43Z
updated: 2026-11-01T15:38:31Z
started: 2026-11-01T15:38:31Z
depends: [hq-f5ccb6]
parent: hq-2eba07
tags: [hooks]
agent: agy
origin: agent
plan: docs/plans/2026-11-01-harness-manifest.md
step: "Task 4: Migrate harness-state-clean, harness-state-refresh, and codex-trust to harnesses.toml"
---

Step 4 of hq-2eba07 plan (spec §5.3.1-§5.3.3): drive .githooks/{harness-state-clean,harness-state-refresh,codex-trust} from harnesses.toml via harness_state.py, preserving CLAUDE_JSON_KEYS re-export until hq-7e1e9c and deferring manifest loading in refresh and codex-trust hook mode.

## Notes

- 2026-11-01T13:14:43Z (add): created
  provenance: {"origin":"agent"}
- 2026-11-01T15:38:31Z (feat/hq-2eba07-harness-manifest): started
  provenance: {"harness_session":"claude-code:fdf3b32f-5e63-4593-bba2-4e994bcdf1eb","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
