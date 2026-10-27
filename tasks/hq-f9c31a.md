---
id: hq-f9c31a
title: "Parallel cutover tests still fail intermittently after hq-a7b473: recovery-signal retry and familiar base rule"
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: main
created: 2026-10-25T12:02:21Z
updated: 2026-10-27T11:50:50Z
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
