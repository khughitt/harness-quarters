---
id: hq-eff4db
title: Fix README and AGENTS references for the shared checker
status: doing
priority: 3
size: s
complexity: low
process: direct
owner: feat/ops-check-hq-c6a149
created: 2026-10-25T01:23:16Z
updated: 2026-10-25T10:34:39Z
started: 2026-10-25T10:31:11Z
depends: [hq-5f9396]
parent: hq-c6a149
tags: [docs]
agent: claude-code
plan: docs/plans/2026-10-24-ops-check-adoption.md
step: "Task 2: Fix the guide references"
---

Plan Task 2 of hq-c6a149 (spec D8). Apply the plan's table of rewrites; no README or AGENTS finding remains and ops-docs check passes. Why the bare-prefix form: the checker parses the last word before the backtick, so a possessive reads as the prefix s.

## Notes

- 2026-10-25T01:23:31Z (feat/ops-check-hq-c6a149): gate: scoped — step of hq-c6a149 plan
  provenance: {"harness_session":"claude-code:d8d1293e-6232-4059-96de-b979663bc333","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T10:31:11Z (feat/ops-check-hq-c6a149): started
  provenance: {"harness_session":"claude-code:6ef3b6c4-4356-473e-aa75-9402e75eb54d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T10:31:12Z (feat/ops-check-hq-c6a149): gate: implementing .worktrees/ops-check-c6a149
  provenance: {"harness_session":"claude-code:6ef3b6c4-4356-473e-aa75-9402e75eb54d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T10:34:39Z (feat/ops-check-hq-c6a149): review: impl round 1 — verdict: accept; findings: minor 3; reviewer: claude-code/claude-opus-5-5
