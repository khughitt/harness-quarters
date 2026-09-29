---
id: tack-6d496d
title: "Codex waits: name wait_agent 3600000 and write_stdin 300000 in the waiting rule"
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-27T11:07:25Z
updated: 2026-09-27T11:07:55Z
started: 2026-09-27T11:07:42Z
completed: 2026-09-27T11:07:55Z
depends: []
parent: tack-339fdf
tags: [rules]
model: claude-opus-5-5
agent: claude-code/claude-opus-5-5
---

Why: Codex agents wait with short timeouts and loop. Pre-rule, 2,208 of 3,681 wait_agent calls timed out, mostly at 45-60 s requests (60-80% time out), while 300-600 s requests time out 11-14%. Since the rule, three sessions polled one long command with empty write_stdin about every 30 s (258 polls). Probed on Codex 0.157.1 (ai-952dec, brief docs/notes/2026-09-27-waiting-loops-brief.md): wait_agent accepts timeout_ms up to 3600000 and returns when the child finishes; an empty write_stdin is capped at background_terminal_max_timeout (default 300000) without warning and returns when the command ends.

Done: the AGENTS.md Processes bullet 'Never end a turn waiting on work the harness does not track' names Codex's bounded waits concretely, in one clause: wait_agent with timeout_ms 3600000 and an empty write_stdin with yield_time_ms 300000, both returning as soon as the child or command finishes, never a loop of shorter waits. No new bullet. Later check: obs-f074aa's poll-loop detector on Codex sessions after the change.

## Notes

- 2026-09-27T11:07:42Z (main): started
  provenance: {"harness_session":"claude-code:c82c3022-0ecc-44d8-a0dc-7e7b3f114b5e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T11:07:55Z (docs/codex-waits): done
  provenance: {"harness_session":"claude-code:c82c3022-0ecc-44d8-a0dc-7e7b3f114b5e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T11:07:55Z (docs/codex-waits): AGENTS.md waiting bullet names Codex's longest bounded waits: wait_agent timeout_ms 3600000, empty write_stdin yield_time_ms 300000, never a loop of shorter waits
  provenance: {"harness_session":"claude-code:c82c3022-0ecc-44d8-a0dc-7e7b3f114b5e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
