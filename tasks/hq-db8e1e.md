---
id: hq-db8e1e
title: Root-cause test_recovery_signal_is_retried_by_reconciliation returning failed under parallel load
status: idea
priority: 2
created: 2026-10-25T02:28:14Z
updated: 2026-10-25T20:39:25Z
depends: []
tags: []
source: hq-a7b473
agent: claude-code/claude-opus-5-5
---

Seen once (hq-a7b473's report, just test at load ~98 on 32 CPUs): Europa's dependency-restore returned a failed response where the test expected interrupted. Root cause not established; no failure text was retained.

Established in hq-a7b473: a signal inside hosts.request always yields Interrupted (window._call), so the remote operation failed before the SIGTERM reached the request. The fixture's 20 s sync budget expiring is ruled out as the cause: with that path the sender still fires afterwards (its condition is a failing --is-ancestor poll on Europa), and before hq-a7b473 such a late SIGTERM killed the pytest worker (reproduced: exit 143) rather than producing the reported assertion. So dependency-restore most likely failed before its first unknown-ancestor poll: targets.closed, _snapshot, titan_head, familiar._grafted, a HEAD that does not resolve (source_proof loops without an ancestor call until the budget), or a transport Stop in hosts.request. One fixture candidate: Dropbox._cycle computes held and its file list once per cycle, so a cycle that began before the test set the hold can copy refs read after Titan's revert without the revert's objects.

hq-a7b473 made the test print failed.error on that assertion and stopped a late sender from killing the process, so a recurrence now names its cause. Wake: the test fails again with that message; read the message, then fix the named path (fixture or tool) and verify under the same parallel segment.

## Notes

- 2026-10-25T02:28:24Z (fix/cutover-timing-a7b473): shelved: test_recovery_signal_is_retried_by_reconciliation fails again; its assertion now prints the dependency-restore error that names the path
- 2026-10-25T12:00:04Z (feat/ops-check-hq-c6a149): Recurred 2026-10-25 in a full just test at load average about 65 on the primary host (branch feat/ops-check-hq-c6a149, no relay cutover code changed): dependency-restore returned failed with error: familiar's source did not reach 1b2fa1c75208 on this host within 20 s (HEAD 929462bdb2b9 is not 1b2fa1c75208 or a tasks-only descendant of it (1b2fa1c75208 or 929462bdb2b9 is not a commit here)); it may still be synchronizing; nothing was restored here. That is the 20 s sync budget path the body called ruled out. The test passed alone at load 18.
- 2026-10-25T12:00:06Z (feat/ops-check-hq-c6a149): unshelved
- 2026-10-25T20:39:25Z (main): Verification recurrence during a record/document-only scope pass on hq main dc51f61 (only a brief was edited; no runtime or test code changed): just test ran 231 agent tests and 1051 hook/tool tests successfully, then the parallel relay segment reported 388 passed and 1 failed in 383.02 s. test_recovery_signal_is_retried_by_reconciliation again returned ('dependency-restore', 'europa', 'failed') instead of interrupted. Retained assertion error: familiar's source did not reach 0259432ed832 on this host within 20 s (HEAD 504e50b3f0ef is not 0259432ed832 or a tasks-only descendant of it (0259432ed832 or 504e50b3f0ef is not a commit here)); it may still be synchronizing; nothing was restored here. This matches the previous recurrence's 20-second source-sync path; root cause and host contention were not investigated. Full recipe exited 1 before its final isolated segment; no retry or fix attempted. Status, priority, review state and scope are unchanged.
  provenance: {"harness_session":"codex:01a174ba-22b1-76d0-9d10-43ed3394938b","harness_session_source":"CODEX_THREAD_ID"}
