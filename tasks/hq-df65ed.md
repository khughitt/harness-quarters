---
id: hq-df65ed
title: "The RPC capability probe leaves its harness subprocess running after a command timeout or interruption, then deletes the temporary session store."
status: idea
priority: 2
created: 2026-10-11T21:58:41Z
updated: 2026-10-11T21:58:41Z
depends: []
tags: [feedback, friction, "from:hq"]
agent: codex
---

Reproduced without model calls using a fake local process: a prompt response timeout exits the controller; the child remains alive and the temporary directory is gone. The reproducer reaped the child. Stop and reap the process group in final cleanup before removing the session store, and cover the error path. The completed capability evidence itself is consistent; the three previously deferred launcher issues remain minor.
