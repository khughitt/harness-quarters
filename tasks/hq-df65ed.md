---
id: hq-df65ed
title: "The RPC capability probe leaves its harness subprocess running after a command timeout or interruption, then deletes the temporary session store."
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-10-11T21:58:41Z
updated: 2026-10-11T22:16:26Z
depends: []
tags: [feedback, friction, "from:hq"]
agent: codex
---

The RPC capability probe (pi/probes/rpc-probe.py) leaves its harness subprocess running after a command timeout or interruption, then deletes the temporary session store.

Reproduced without model calls using a fake local process: a prompt response timeout exits the controller; the child remains alive and the temporary directory is gone.

Outcome: every pi process the probe starts is stopped and reaped (its process group) in the probe's final cleanup, before the temporary directory is removed, on success, on an exception and on interrupt. Approach: the probe tracks every Pi it spawns and its finally stops each one's group before rmtree. Verification: a test drives the probe against a fake pi (PI_INSTALL_ROOT-free: point the probe at a fake launcher) whose prompt never answers, with a short command timeout, and asserts the probe exits non-zero, the fake's process group is gone, and the directory is removed; the test is seen failing against the current code. The three deferred launcher minors stay out of scope.

## Notes

- 2026-10-11T21:58:48Z (main): concerns: hq-57132d defect — The RPC probe failure cleanup removes its temporary directory without stopping its child process; a timeout reproduction left that process alive.
