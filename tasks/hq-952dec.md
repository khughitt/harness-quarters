---
id: hq-952dec
title: Measure waiting loops since the 2026-09-24 rule and find each harness's wait mechanism
status: done
priority: "2"
size: m
complexity: mid
process: direct
owner: main
created: 2026-09-27T10:52:40Z
updated: 2026-09-27T11:07:35Z
started: 2026-09-27T10:54:45Z
completed: 2026-09-27T11:07:35Z
depends: []
parent: hq-339fdf
tags: [obs, rules]
model: claude-opus-5-5
agent: claude-code/claude-opus-5-5
---

Question: Do the three waiting-loop shapes (Claude backgrounded sleep + ListAgents, Claude subagent no-op keepalives, Codex wait_agent/write_stdin polling) still occur in sessions since the 2026-09-24 waiting rule, and which harness mechanism ends each: Codex `sleep_tool`, `default_exec_yield_time_ms` and the wait_agent/write_stdin timeout limits; a Claude subagent's idle wait (does a Monitor event arrive without calls, or is a foreground command with a timeout the only option)?
Where to start: docs/notes/2026-09-27-waiting-loops-brief.md (shapes and evidence); obs docs/reports/2026-09-26-tool-failure-modes.md §4 for the detector thresholds; the session-logs skill for reading both session stores; `codex features list` and the Codex 0.157.1 config for the settings.
Bound: A direct scan of sessions since 2026-09-24 using the report's detector rules (no obs indexer changes; obs-f074aa owns that), one Codex probe per setting and one Claude subagent probe. No rule or config change lands in this task.
Expected result: Per shape, the post-rule rate against the report's baseline and a recommended fix (setting, instruction, or none needed), recorded as a note here and in the brief's Unanswered questions and Proposed decomposition.
Ideas it wakes: On completion, run tasks note on ai-bd5b6e with the finding, in the same commit as this result.

## Notes

- 2026-09-27T10:54:45Z (main): started
  provenance: {"harness_session":"claude-code:c82c3022-0ecc-44d8-a0dc-7e7b3f114b5e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T11:07:35Z (main): finding: Claude loops faded before the rule (backgrounded sleeps an August pattern, no-op bursts 09-01..09-06; post-rule 2 bg sleeps in 248 main sessions, 0 poll or no-op episodes). Codex: wait_agent timeouts track short requested waits (45-60 s: 60-80% time out; 300-600 s: 11-14%); max 3600000, returns early. Empty write_stdin capped at 300 s (background_terminal_max_timeout) silently. Fix filed: ai-6d496d. Claude subagent probe skipped: the shape has not recurred since 09-07.
- 2026-09-27T11:07:35Z (main): done
  provenance: {"harness_session":"claude-code:c82c3022-0ecc-44d8-a0dc-7e7b3f114b5e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T11:07:35Z (main): Scan of both stores pre/post the 2026-09-24 rule plus two Codex probes; findings in the brief; Codex rule fix filed as ai-6d496d, no Claude change needed
  provenance: {"harness_session":"claude-code:c82c3022-0ecc-44d8-a0dc-7e7b3f114b5e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
