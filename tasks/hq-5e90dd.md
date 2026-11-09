---
id: hq-5e90dd
title: Record real-hook acceptance before guide edits
status: doing
priority: 3
size: s
complexity: mid
process: direct
owner: fix/hq-74f102-rename-receipt
created: 2026-11-09T20:21:29Z
updated: 2026-11-09T21:00:03Z
started: 2026-11-09T20:59:28Z
depends: [hq-155ccf]
parent: hq-74f102
tags: []
source: hq-74f102
agent: codex
origin: agent
spec: docs/specs/2026-11-09-rename-receipt-design.md
plan: docs/plans/2026-11-09-rename-receipt.md
step: "Task 2: Record real-hook acceptance before guide edits"
---

Run Task 2 of the receipt plan using the committed Task 1 candidate and task-owned persistent rehearsal storage. Why: synthetic sandbox hooks cannot show that the normal hq hook accepts the receipt commit before identity/guide edits. Expected: an isolated normal-hook run with ops sources reachable only through a sandbox registry, unchanged identity/guides, receipt consumed and renamed records committed, with exact command/status/output and candidate revision attached as real-hook-rehearsal.md. A demonstrated ordering conflict stops for design amendment; no bypass, new hosted omission or live rename. This is a recorded local rehearsal, not a permanent test. Preserve needed raw logs and script under the parent execution workspace, account for retained evidence and discard regenerable copies after verified publication.

## References

- real-hook-evidence (output, kind=report): files:real-hook-rehearsal.md — portable revision-bound local acceptance verdict

## Notes

- 2026-11-09T20:21:29Z (add): created
  provenance: {"harness_session":"codex:01a1c1cb-f948-7571-9531-9ef02916ebc4","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
- 2026-11-09T20:23:23Z (fix/hq-74f102-rename-receipt): gate: scoped — step of hq-74f102 plan
  provenance: {"harness_session":"codex:01a1c1cb-f948-7571-9531-9ef02916ebc4","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-09T20:59:28Z (fix/hq-74f102-rename-receipt): started
  provenance: {"harness_session":"codex:01a1c1cb-f948-7571-9531-9ef02916ebc4","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-09T21:00:03Z (fix/hq-74f102-rename-receipt): arm: flow-trial-1 — unit tack-74f102 — flow on
