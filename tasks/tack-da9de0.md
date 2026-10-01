---
id: tack-da9de0
title: "Global instructions say to run long checks through the harness's own background mechanism, but Claude Code's background Bash was killed at its time limit after ~30 min with no stated limit"
status: idea
priority: 2
created: 2026-10-01T15:27:33Z
updated: 2026-10-01T15:27:33Z
depends: []
tags: [feedback, gap, "from:obs"]
agent: claude-code/claude-opus-5-5
---

A ~40 min index upgrade started with run_in_background (no timeout set) was stopped 'after reaching its background time limit' at ~30 min. The Processes section points long runs at the harness background mechanism without naming its limit or how to set it; the workable pattern was bounded slices (timeout --signal=INT under the 10 min foreground cap) of an incremental job. Expected: the limit stated, and guidance for runs that exceed it.
