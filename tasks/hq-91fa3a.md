---
id: hq-91fa3a
title: Strip Codex bookkeeping keys from the harness-state clean filter
status: done
priority: "2"
size: s
complexity: low
process: direct
owner: main
created: 2026-09-27T13:09:02Z
updated: 2026-09-27T13:14:56Z
started: 2026-09-27T13:13:49Z
completed: 2026-09-27T13:14:56Z
depends: []
parent: hq-de40d0
tags: [hooks]
agent: claude-code/claude-opus-5-5
---

Why: Codex writes bookkeeping into codex/config*.toml that the harness-state filter lets through, so the diff mixes it with real configuration (observed 2026-09-27: screen_reader_detection_done and a model_availability_nux counter beside a real hooks.state trusted_hash).

Done: .githooks/harness-state-clean strips, from codex/config*.toml, screen_reader_detection_done under [tui], the whole [tui.model_availability_nux] table, and last_updated and last_revision under every [marketplaces.<name>] table (source_type and source stay). The strip is table-aware: a (table, key) list and a dropped-table list, replacing the top-level-only rule, which keeps model and model_reasoning_effort at top level. The module docstring and README's filter paragraph list the new keys. hooks.state trusted_hash and projects trust_level are untouched.

Check: new cases in .githooks/test_harness_state_clean.py (each key stripped in its table, the same key name kept in another table, the dropped table removed with its blank line, marketplace source kept); uv run --with pytest pytest .githooks/test_harness_state_clean.py passes; git diff -- codex/config.toml on today's tree shows only the trusted_hash hunk.

Where: .githooks/harness-state-clean, .githooks/test_harness_state_clean.py, README.md (filter setup section).

## Notes

- 2026-09-27T13:13:49Z (main): started
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T13:14:56Z (codex-bookkeeping): done
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T13:14:56Z (codex-bookkeeping): harness-state filter strips Codex bookkeeping table-aware: [tui] screen_reader_detection_done, the [tui.model_availability_nux] table, [marketplaces.*] last_updated/last_revision; tests cover each plus trust keys kept; README lists them; codex configs renormalised. Filtered live codex diff now shows only real config (a Stop hook trust hash; work MCP tool approvals and a project trust in the work file).
  provenance: {"harness_session":"claude-code:6abb1c47-ce3b-484f-a5f8-8eb56f5595d2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
