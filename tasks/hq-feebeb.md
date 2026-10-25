---
id: hq-feebeb
title: Attachment fallback for the refused files
status: doing
priority: 3
size: m
complexity: mid
process: direct
owner: feat/ops-check-hq-c6a149
created: 2026-10-25T01:23:18Z
updated: 2026-10-25T11:07:35Z
started: 2026-10-25T10:54:04Z
depends: [hq-eff4db, hq-df1183]
parent: hq-c6a149
tags: [docs]
agent: claude-code
plan: docs/plans/2026-10-24-ops-check-adoption.md
step: "Task 5: Attachment fallback for the refused files"
---

Plan Task 5 of hq-c6a149 (spec D6). File the restoration task, keep exact raw bytes under WORK_ROOT with retained records written before any detach, replace each attachment with a labelled portable derivative and its mapping note. Why raw copies: the files are evidence and must be restorable byte for byte once the exemption ships. Task 6 reruns the sequence for attachments main brings in.

## Notes

- 2026-10-25T01:23:33Z (feat/ops-check-hq-c6a149): gate: scoped — step of hq-c6a149 plan
  provenance: {"harness_session":"claude-code:d8d1293e-6232-4059-96de-b979663bc333","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T10:54:04Z (feat/ops-check-hq-c6a149): started
  provenance: {"harness_session":"claude-code:6ef3b6c4-4356-473e-aa75-9402e75eb54d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T10:54:05Z (feat/ops-check-hq-c6a149): gate: implementing .worktrees/ops-check-c6a149
  provenance: {"harness_session":"claude-code:6ef3b6c4-4356-473e-aa75-9402e75eb54d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T11:04:53Z (feat/ops-check-hq-c6a149): review: impl round 1 — verdict: revise; findings: important 1, minor 2; reviewer: claude-code/claude-opus-5-5
- 2026-10-25T11:07:32Z (feat/ops-check-hq-c6a149): review: impl round 2 — verdict: accept; findings: none; reviewer: claude-code/claude-opus-5-5
- 2026-10-25T11:07:34Z (feat/ops-check-hq-c6a149): gate: verified tree:4ba0eacba79aec2faee8cbf859ff6c78a8bf5d62 — checks: eleven raw copies match their 9738ea0 blobs and their retained records, manifest hash matches the scratch record, ops-check rc 0 and the cached D7 pair primary 0 simulated 0, checker layout functions in-process flag 0 derivatives and all 11 raw originals, tasks check clean; review: important addressed hq-c075d0 ledger derivative kept ten glued host names and was re-derived with substring replacement and reattached, minor addressed titan_head kept by ruling as a real function name with notes on hq-583ac7 and hq-c6c847, minor deferred the main-added hq-83c787 attachment goes through Task 6 Step 1; reviewer: claude-code/claude-opus-5-5
  provenance: {"harness_session":"claude-code:6ef3b6c4-4356-473e-aa75-9402e75eb54d","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T11:07:35Z (feat/ops-check-hq-c6a149): retro: building derivatives with the checker's own value set made them pass by construction, but the checker's whole-word rule is narrower than D5's every-spelling rule, so a case-insensitive substring grep belongs in the derive step itself; the reviewer caught what the checker could not.
