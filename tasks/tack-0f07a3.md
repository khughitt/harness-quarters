---
id: tack-0f07a3
title: Mirror obs's pasted-content human-turn rule for Codex in session-episodes and the session-logs skill
status: done
priority: 2
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-28T20:11:53Z
updated: 2026-09-29T20:11:56Z
started: 2026-09-29T20:10:48Z
completed: 2026-09-29T20:11:56Z
depends: []
tags: [obs]
source: obs-00809f
model: claude-sonnet-5-5
---

obs now treats a Codex user message beginning <pasted_content as the person (as it already did for Claude Code). session-episodes and the session-logs skill's 'Human or injected' list must apply the same rule; the three lists change together.

## Notes

- 2026-09-29T20:10:48Z (main): started
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T20:11:56Z (feat/pasted-codex): done
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T20:11:56Z (feat/pasted-codex): session-episodes counts a Codex <pasted_content user turn as human (wrapper tags stripped); the session-logs skill and design spec state the rule for both harnesses; obs adapters already carry it
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
