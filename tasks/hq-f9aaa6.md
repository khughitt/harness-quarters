---
id: hq-f9aaa6
title: Pilot before committing to an extended run
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: docs/pilot-before-long-runs
created: 2026-09-25T09:53:22Z
updated: 2026-09-25T09:53:23Z
started: 2026-09-25T09:53:22Z
completed: 2026-09-25T09:53:23Z
depends: []
tags: [skills]
agent: claude-code/claude-opus-5-5
---

User direction 2026-09-25: before an extended benchmark/experiment run, especially one that needs exclusive use of the machine, first run a much smaller version to catch problems. Prompted by niri-material's idle-budget trace (material-4241c3), where a 58 min TTY run reported a deterministic failure visible in its first 2-minute case, and two refused desktop attempts had already recorded it in their kept traces. Lands as a Processes bullet in AGENTS.md.

## Notes

- 2026-09-25T09:53:22Z (docs/pilot-before-long-runs): started
  provenance: {"harness_session":"claude-code:29e26027-f18b-4d4f-9742-5dc4a9c688ec","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T09:53:23Z (docs/pilot-before-long-runs): done
  provenance: {"harness_session":"claude-code:29e26027-f18b-4d4f-9742-5dc4a9c688ec","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T09:53:23Z (docs/pilot-before-long-runs): Processes bullet added to AGENTS.md: pilot the smallest all-gates version first, analyze a refused or aborted run's completed parts before retrying, name the pilot when asking for the machine.
  provenance: {"harness_session":"claude-code:29e26027-f18b-4d4f-9742-5dc4a9c688ec","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
