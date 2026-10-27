---
id: hq-f9c31a
title: "Parallel cutover tests still fail intermittently after hq-a7b473: recovery-signal retry and familiar base rule"
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: fix/hq-f9c31a-parallel-cutover-flakes
created: 2026-10-25T12:02:21Z
updated: 2026-10-27T12:38:38Z
started: 2026-10-27T11:50:32Z
depends: []
tags: []
agent: claude-code
---

In the parallel cutover stage of just test (pytest -n auto over tools/test_relay_cutover_bootstrap.py and tools/test_relay_cutover_transport.py), two tests failed on 2026-10-25 in a docs-only worktree whose baseline run of the same suite passed an hour earlier: test_relay_cutover_bootstrap.py::test_recovery_signal_is_retried_by_reconciliation (dependency-restore on europa ended with status 'failed', expected 'interrupted') and test_relay_cutover_transport.py::test_familiar_base_rule[untracked-record]. Both passed 5 of 5 focused serial reruns. hq-a7b473 closed timing failures at cancellation and service-start boundaries and named the first test, so the fix did not cover every interleaving. Next: reproduce under -n auto with load (repeat the stage, e.g. pytest-repeat or a loop), find the timing dependency and make the test deterministic; just test passes repeatedly under -n auto.

## Notes

- 2026-10-25T12:02:27Z (main): concerns: hq-a7b473 defect — test_recovery_signal_is_retried_by_reconciliation, which hq-a7b473 fixed, failed again under the parallel just test run (plus test_familiar_base_rule[untracked-record]); both pass serially
- 2026-10-27T11:50:32Z (main): started
  provenance: {"harness_session":"claude-code:03d08d67-a0a4-459d-a60d-b3787154304c","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-27T11:50:50Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-10-27T11:50:52Z (main): arm: flow-trial-1 — unit tack-f9c31a — flow off
- 2026-10-27T11:51:01Z (fix/hq-f9c31a-parallel-cutover-flakes): resumed
  provenance: {"harness_session":"claude-code:03d08d67-a0a4-459d-a60d-b3787154304c","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-27T12:10:28Z (fix/hq-f9c31a-parallel-cutover-flakes): root cause 1 (recovery-signal): the test's _signal_when sender gave up silently after a fixed 60 s from before restore_window; reaching Europa's source poll took 9.7 s serial and 23.4 s in the parallel segment at load ~6-15, so at load 65-98 no SIGTERM came and Europa's 20 s sync budget failed the step. Reproduced word for word by shrinking the window to 5 s. Fix: the sender keeps no deadline; regression test test_signal_sender_waits_out_a_slow_host (RED then GREEN)
- 2026-10-27T12:15:55Z (fix/hq-f9c31a-parallel-cutover-flakes): root cause 2 (base rule untracked-record): not a status failure. The retained log of the 2026-10-25 run (WORK_ROOT hq/hq-2b3929/just-test-final.log) shows the object-store snapshot assert: the before snapshot held .git/objects/maintenance.lock, gone by the after one. Every fixture git commit starts 'git maintenance run --auto --quiet --detach' (GIT_TRACE, git 2.56), which holds that lock briefly; under load it spans a snapshot. Any snapshot-comparing case can hit it. Fix: familiar_history sets maintenance.auto=false in the fixture checkout (Europa's is a copytree of Titan's); regression test test_fixture_commits_leave_the_object_store_settled traces a commit on both hosts (RED then GREEN)
- 2026-10-27T12:38:38Z (fix/hq-f9c31a-parallel-cutover-flakes): review: impl round 1 — verdict: revise; findings: Important 1, Minor 4; reviewer: claude-code/claude-opus-5-5
