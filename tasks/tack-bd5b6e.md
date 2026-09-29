---
id: tack-bd5b6e
title: Waiting loops take about 9% of agent context tokens
status: dropped
priority: "2"
created: 2026-09-26T20:51:42Z
updated: 2026-09-27T11:08:05Z
depends: [tack-952dec]
parent: tack-339fdf
tags: [rules, obs]
source: "obs:docs/reports/2026-09-26-tool-failure-modes.md"
agent: claude-code/claude-opus-5-5
---

Measured in obs (docs/reports/2026-09-26-tool-failure-modes.md §4 in the obs checkout): poll and no-op loops take ~9.2% of context tokens across Claude Code and Codex. Claude: a long sleep gets backgrounded and returns in ~13 s, and the agent loops ListAgents + sleep (1,432 such sleeps in 31 sessions; worst 166 calls over 60 min, 143M tokens); subagents spin on true / echo . while a Monitor waits (162 episodes, 174M tokens). Codex: wait_agent times out 67% of the time; 98% of write_stdin calls only poll (2.55B tokens). The global rules already say to wait through the harness's own mechanism; these sessions did not. Question: which instruction or harness setting ends each loop shape (end the turn and be woken, a longer bounded wait, the Monitor tool)? obs-f074aa will detect the episodes.

## Notes

- 2026-09-27T10:52:46Z (main): scope: briefed; three loop shapes framed, goal ai-339fdf created, research ai-952dec filed and blocking this idea; brief: docs/notes/2026-09-27-waiting-loops-brief.md
- 2026-09-27T11:07:35Z (main): finding (ai-952dec): Claude loop shapes have not recurred since early September; Codex needs only the concrete waits in the existing rule, filed as ai-6d496d. proposal: drop once ai-6d496d lands, covered by it.
- 2026-09-27T11:08:05Z (main): dropped
  provenance: {"harness_session":"claude-code:c82c3022-0ecc-44d8-a0dc-7e7b3f114b5e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-27T11:08:05Z (main): covered: ai-952dec found the Claude shapes gone since early September; the Codex fix landed as ai-6d496d (fd9e12a)
  provenance: {"harness_session":"claude-code:c82c3022-0ecc-44d8-a0dc-7e7b3f114b5e","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
