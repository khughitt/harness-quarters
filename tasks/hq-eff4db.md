---
id: hq-eff4db
title: Fix README and AGENTS references for the shared checker
status: done
priority: 3
size: s
complexity: low
process: direct
owner: feat/ops-check-hq-c6a149
created: 2026-10-25T01:23:16Z
updated: 2026-10-25T10:34:42Z
started: 2026-10-25T10:31:11Z
completed: 2026-10-25T10:34:41Z
closed: 2026-10-25T10:34:41Z
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
- 2026-10-25T10:34:40Z (feat/ops-check-hq-c6a149): gate: verified tree:1e11c593dd1f31678c9349b1608935cbb509f5d7 — checks: ops-check grep for README and AGENTS findings prints nothing, ops-docs check rc 0, ops-check total 291 to 261 lines, tasks check clean; review: minor deferred prefix/.worktrees lost its backticks beside a backticked sibling and could be written with angle brackets, minor deferred history.jsonl and state_5.sqlite now formatted differently as planned, minor deferred README line 58 runs to 97 columns left unwrapped to avoid the prefix trap; reviewer: claude-code/claude-opus-5-5
  provenance: {"harness_session":"claude-code:6ef3b6c4-4356-473e-aa75-9402e75eb54d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T10:34:40Z (feat/ops-check-hq-c6a149): retro: applying the plan table as exact string substitutions with a count assert made the edit mechanical, and the reviewer running the checker's own parser functions in-process was a stronger check than rereading the diff.
- 2026-10-25T10:34:41Z (feat/ops-check-hq-c6a149): done
  provenance: {"harness_session":"claude-code:6ef3b6c4-4356-473e-aa75-9402e75eb54d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T10:34:41Z (feat/ops-check-hq-c6a149): 30 README and AGENTS references rewritten per plan at 95e4871; reviewed, 3 minor deferred
  provenance: {"harness_session":"claude-code:6ef3b6c4-4356-473e-aa75-9402e75eb54d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
