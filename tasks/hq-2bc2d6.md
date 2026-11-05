---
id: hq-2bc2d6
title: Probe environment inheritance and process ancestry for shell-launched Claude Code and Codex child sessions
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-11-05T02:14:06Z
updated: 2026-11-05T02:14:06Z
depends: []
parent: hq-8f5670
tags: [hooks]
source: docs/notes/2026-11-04-turn-pause-coverage-brief.md
origin: agent
---

Question: What environment variables (`CLAUDECODE`, `CLAUDE_ENV_FILE`, `CODEX_*`, or custom `HQ_*` variables) and `/proc/<pid>/stat` process ancestry survive inside a child `claude -p` or `codex exec` session launched from Claude Code `Bash` and from Codex `exec_command` (`workspace-write` sandbox)?
Where to start: `tools/turn_pause/adapters.py` (`normalize`), `tools/turn_pause/state.py` (`find_harness_pid`), `docs/notes/2026-11-01-turn-pause-activation.md`, and `[ref:brief]`, which compares environment-token linkage against `/proc` ancestry across the 2x2 parent/child matrix.
Bound: Probe the 2x2 parent/child launch matrix (`claude -p` and `codex exec` invoked from Claude Code `Bash` and Codex `exec_command`) using a diagnostic hook dump in an isolated test home; do not modify live `turn-pause` state accounting in this task.
Expected result: Record which parent-session linkage signal survives each launch pair and recommend the concrete linkage mechanism on this task and in `[ref:brief]`.
Ideas it wakes: On completion, run `tasks note hq-f247c3 --no-reviewed "<finding>"` on each named waiting idea, before this result's branch merges.

## References

- brief (input, required, kind=brief): docs/notes/2026-11-04-turn-pause-coverage-brief.md — context and questions for this work

## Notes

- 2026-11-05T02:14:06Z (add): created
  provenance: {"origin":"agent"}
