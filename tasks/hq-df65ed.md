---
id: hq-df65ed
title: "The RPC capability probe leaves its harness subprocess running after a command timeout or interruption, then deletes the temporary session store."
status: done
priority: 2
size: xs
complexity: low
process: direct
owner: probe-cleanup
created: 2026-10-11T21:58:41Z
updated: 2026-10-11T22:59:48Z
started: 2026-10-11T22:16:26Z
completed: 2026-10-11T22:59:48Z
depends: []
tags: [feedback, friction, "from:hq"]
agent: codex
---

The RPC capability probe (pi/probes/rpc-probe.py) leaves its harness subprocess running after a command timeout or interruption, then deletes the temporary session store.

Reproduced without model calls using a fake local process: a prompt response timeout exits the controller; the child remains alive and the temporary directory is gone.

Outcome: every pi process the probe starts is stopped and reaped (its process group) in the probe's final cleanup, before the temporary directory is removed, on success, on an exception and on interrupt. Approach: the probe tracks every Pi it spawns and its finally stops each one's group before rmtree. Verification: a test drives the probe against a fake pi (PI_INSTALL_ROOT-free: point the probe at a fake launcher) whose prompt never answers, with a short command timeout, and asserts the probe exits non-zero, the fake's process group is gone, and the directory is removed; the test is seen failing against the current code. The three deferred launcher minors stay out of scope.

## Notes

- 2026-10-11T21:58:48Z (main): concerns: hq-57132d defect — The RPC probe failure cleanup removes its temporary directory without stopping its child process; a timeout reproduction left that process alive.
- 2026-10-11T22:16:26Z (main): gate: scoped — direct: one cleanup path in one probe script with a fake-process test
- 2026-10-11T22:16:26Z (main): started
  provenance: {"harness_session":"claude-code:35d7a92f-3c81-499f-9159-da9030d280a7","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-11T22:16:32Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-11T22:16:32Z (main): arm: flow-trial-1 — unit tack-df65ed — flow on
- 2026-10-11T22:16:40Z (probe-cleanup): resumed
  provenance: {"harness_session":"claude-code:35d7a92f-3c81-499f-9159-da9030d280a7","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-11T22:16:41Z (probe-cleanup): gate: implementing .worktrees/probe-cleanup
- 2026-10-11T22:25:15Z (probe-cleanup): review: impl round 1 — verdict: revise; findings: important 2, minor 6; reviewer: claude-code/claude-opus-5-5
- 2026-10-11T22:38:35Z (probe-cleanup): review: impl round 2 — verdict: revise; findings: important 2, minor 2; reviewer: claude-code/claude-opus-5-5
- 2026-10-11T22:59:42Z (probe-cleanup): review: impl round 3 — verdict: accept; findings: minor 4; reviewer: claude-code/claude-opus-5-5
- 2026-10-11T22:59:43Z (probe-cleanup): gate: verified tree:e5eb50bf0037b24c98c9731c84b41780601779d8 — checks: just test 228 and 678 passed, tools/test_pi_rpc_probe.py 6 passed on repeated runs and failed against each pre-fix probe and against an rmtree-first mutation, real rpc-probe run after the subreaper fix matched every recorded outcome with nothing left running; review: important addressed tool commands in their own sessions escaped the group kill, important addressed SIGHUP skipped cleanup, important addressed a second signal via a reader thread cut cleanup short, important addressed the test did not check stop-before-remove order, minor addressed repeated killpg could hit a reused group id, minor addressed kill wait was unbounded, minor addressed SIGTERM before the try leaked the directory, minor addressed test flake in alive and the group check, minor addressed test lacked the exception path, minor addressed SIGQUIT untested, minor deferred a signal right after mkdtemp leaks the empty directory, minor deferred exit signals taken by a reader thread wait for the main thread's current wait, minor deferred a second signal before the ignore loop can skip cleanup, minor deferred no feedback while cleanup waits, minor deferred the double-signal test fails on the group child and not on pi; reviewer: claude-code/claude-opus-5-5
- 2026-10-11T22:59:47Z (probe-cleanup): retro: Each review round found a deeper layer of the same process-lifecycle problem (group kill, then detached tool sessions, then signal delivery to reader threads), which a fake pi that mirrored pi's real spawning (a detached child, a stubborn SIGTERM) would have exposed in one pass; for cleanup code, write the adversarial fake from the real tool's source first. Mutation checks per assertion (rmtree-first, no subreaper, no SIGHUP) kept each new test honest.
- 2026-10-11T22:59:48Z (probe-cleanup): done
  provenance: {"harness_session":"claude-code:35d7a92f-3c81-499f-9159-da9030d280a7","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-11T22:59:48Z (probe-cleanup): The RPC probe now stops and reaps every pi it started, their groups, and the detached tool commands reparented to it as subreaper, before removing its directory, on success, on an exception, and on INT, TERM, HUP or QUIT including a second signal during cleanup; tools/test_pi_rpc_probe.py covers each path and the order
  provenance: {"harness_session":"claude-code:35d7a92f-3c81-499f-9159-da9030d280a7","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
