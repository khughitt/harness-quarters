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
updated: 2026-10-24T23:35:15Z
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
