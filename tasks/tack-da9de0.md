---
id: tack-da9de0
title: "Global instructions say to run long checks through the harness's own background mechanism, but Claude Code's background Bash was killed at its time limit after ~30 min with no stated limit"
status: doing
priority: 2
size: xs
complexity: low
process: direct
owner: main
created: 2026-10-01T15:27:33Z
updated: 2026-10-02T15:36:18Z
started: 2026-10-02T15:36:18Z
depends: []
tags: [feedback, gap, "from:obs"]
agent: claude-code/claude-opus-5-5
---

Why: the Processes section sends long checks to "the harness's own background mechanism" without its limit. A ~40 min obs index upgrade started with Claude Code's `run_in_background` and no timeout was stopped at its background time limit after ~30 min. The Bash tool's contract: with `run_in_background`, `timeout` is the background limit, default 1800000 ms (30 min), max 7200000 ms (2 h); the foreground maximum is 600000 ms (10 min).

Done when the Processes bullet that names Codex's bounded waits also names Claude Code's: background Bash runs 30 min unless `timeout` is set, at most 2 h, so set it to cover the run; a run longer than 2 h is split into resumable slices (an incremental job run in bounded passes, each under the limit, as the obs upgrade did with `timeout --signal=INT`) or handed to a tracked process the user agrees to. Check the edit renders in every AGENTS.md mirror.

Where to look: AGENTS.md "Processes", the bullet beginning "Never end a turn waiting on work the harness does not track".

## Notes

- 2026-10-02T15:33:38Z (main): scope: scoped; todo P2 xs/low/direct; the limit is in the Bash tool contract (background default 30 min via timeout, max 2 h); add it beside the Codex wait limits in Processes, with slicing for longer runs
- 2026-10-02T15:36:18Z (main): started
  provenance: {"harness_session":"claude-code:e8e1b806-1b76-4ade-bab5-f0cdc5fe34ad","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
