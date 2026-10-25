---
id: hq-6ad37e
title: Residue design status line predates its landed goal
status: doing
priority: 3
size: xs
complexity: low
process: direct
owner: docs/curate-docs-hq-30fd95
created: 2026-10-24T22:15:21Z
updated: 2026-10-25T00:08:49Z
started: 2026-10-24T23:33:47Z
depends: []
tags: [docs]
source: hq-30fd95
agent: claude-code
---

Found by the curate-docs pass hq-30fd95 at 8686be3 (criterion 2). docs/specs/2026-10-06-residue-design.md, hq's declared authority, carries 'Status: accepted 2026-10-06', while hq-dcb11a, the goal it decided, landed 2026-10-09; the status line does not record that. Fix: add the landing (hq-dcb11a, 2026-10-09) to the status line. If the residue design no longer decides what hq builds (hq has since gained the pinned relay and pi runtimes and hq sessions), name the current authority in identity.toml instead and run just docs.

## Notes

- 2026-10-24T23:33:47Z (main): started
  provenance: {"harness_session":"claude-code:c2f3e76e-ba29-4176-9424-f3373a5a3562","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-24T23:33:57Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-24T23:33:57Z (main): arm: flow-trial-1 — unit tack-6ad37e — flow on
- 2026-10-24T23:35:07Z (main): gate: scoped — adopted
  provenance: {"harness_session":"claude-code:c2f3e76e-ba29-4176-9424-f3373a5a3562","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-24T23:35:15Z (docs/curate-docs-hq-30fd95): resumed
  provenance: {"harness_session":"claude-code:c2f3e76e-ba29-4176-9424-f3373a5a3562","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-24T23:46:41Z (docs/curate-docs-hq-30fd95): baseline: just test in .worktrees/docs-30fd95 at dacb4c5: 1042 + 389 + 1 passed, exit 0
- 2026-10-24T23:47:01Z (docs/curate-docs-hq-30fd95): gate: implementing .worktrees/docs-30fd95
  provenance: {"harness_session":"claude-code:c2f3e76e-ba29-4176-9424-f3373a5a3562","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-24T23:53:38Z (docs/curate-docs-hq-30fd95): review: impl round 1 — verdict: revise; findings: minor 1; reviewer: claude-code
- 2026-10-24T23:56:01Z (docs/curate-docs-hq-30fd95): review: impl round 2 — verdict: accept; findings: none; reviewer: claude-code
- 2026-10-25T00:08:33Z (docs/curate-docs-hq-30fd95): gate: verified tree:e050910363d0bcd2fbb5d15552293db59fa845a7 — checks: just test 231 and 1042 passed and relay-cutover 388 passed with 1 failed test_service_run_wait_and_result at load 34 (known flake hq-38e479) which passed 3 of 3 rerun alone, tools/ops-docs check 0, tasks check no errors, docs-only diff since dacb4c5; review: minor addressed status line named the pre-rename id as the closing id; reviewer: claude-code
  provenance: {"harness_session":"claude-code:c2f3e76e-ba29-4176-9424-f3373a5a3562","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-25T00:08:49Z (docs/curate-docs-hq-30fd95): retro: A one-line status fix still needed the id history checked; the rename had finished before the goal closed, so the closing id was hq, not tack.
