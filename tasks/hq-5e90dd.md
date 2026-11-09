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
updated: 2026-11-09T21:10:35Z
started: 2026-11-09T20:59:28Z
depends: [hq-155ccf]
related: [tasks-7180ec]
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
- 2026-11-09T21:00:56Z (fix/hq-74f102-rename-receipt): gate: implementing .worktrees/hq-74f102
  provenance: {"harness_session":"codex:01a1c1cb-f948-7571-9531-9ef02916ebc4","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-09T21:08:55Z (fix/hq-74f102-rename-receipt): attached: real-hook-rehearsal.md (2736 bytes): Normal hook passes before and after hqprobe rename on the merged candidate; guides unchanged and receipt consumed.
- 2026-11-09T21:10:33Z (fix/hq-74f102-rename-receipt): Recorded local real-hook rehearsal PASS on candidate b5f88e231ab0a64c2ede833543b7be1a48dc117f, including main before rehearsal. Normal unrenamed hook baseline, tasks --json rename hq hqprobe, and tasks --json commit --project hqprobe all exited 0 with full committed task records. Both traces show .githooks/pre-commit; identity.toml, README and AGENTS stayed byte-identical, receipt was consumed and working tree clean. Driver verify mode rechecked saved logs/trace/input hashes, HEAD ancestry, committed task paths and bytes without rerunning the hook; plan-task-done exited 0, log task-2-tests-gsxIKr.log in parent's workspace. Portable report real-hook-rehearsal.md is attached, listed by tasks show and byte-identical to its committed payload.
  provenance: {"harness_session":"codex:01a1c1cb-f948-7571-9531-9ef02916ebc4","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-09T21:10:33Z (fix/hq-74f102-rename-receipt): Preparation failures are preserved in the parent's workspace and report: first baseline lacked lore source context; second baseline passed but rename required retained named refs that clone kept as remote refs. Exact matching source commits established both fixture causes; final case faithfully restored context without hook bypass or a code workaround. No behavior suite rerun for this operational verification; mandatory normal attachment/merge hooks passed, broad suite deliberately omitted under policy, no hosted evidence. Feedback tasks-7180ec records the exact-ref refusal's useful diagnostic.
  provenance: {"harness_session":"codex:01a1c1cb-f948-7571-9531-9ef02916ebc4","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-09T21:10:33Z (fix/hq-74f102-rename-receipt): Inline operator self-check; parent final independent whole-branch review remains required. No child-owned retained worktree, scratch or external evidence and no processes; parent hq-74f102 owns the shared mutable execution workspace and worktree across final review. No pushes, live rename or host pointers. Branch remains unmerged at parent's .worktrees/hq-74f102.
  provenance: {"harness_session":"codex:01a1c1cb-f948-7571-9531-9ef02916ebc4","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-09T21:10:35Z (fix/hq-74f102-rename-receipt): gate: verified tree:5541e47c201a311baa2d9c0225c726923d953aa3 — checks: real-hook rehearsal and saved evidence verification passed with both normal hook commits successful; review: none; reviewer: codex/gpt-6.1-sol
  provenance: {"harness_session":"codex:01a1c1cb-f948-7571-9531-9ef02916ebc4","harness_session_source":"CODEX_THREAD_ID"}
