---
id: hq-7a69dc
title: "pi for headless workers: an agent-directory template, and probes of the facts crew found unknown"
status: idea
priority: 2
reviewed: true
created: 2026-10-14T01:44:15Z
updated: 2026-10-15T13:05:30Z
depends: [hq-f1aff0]
parent: hq-40a8d0
tags: []
agent: claude-code/claude-opus-5-5
---

Why: crew gives each attempt its own pi agent directory (PI_CODING_AGENT_DIR), departing from keeping configuration under hq's pi home, so attempts share no session, auth or MCP state. Its design also found pi facts that hq records as unknown or does not record. Named in crew's core design (crew docs/specs/2026-10-13-crew-core-design.md §9; task crew-3fc20c).

Done: (1) a template for headless pi agent directories that crew copies per attempt; (2) probed facts for pi 1.1.0: process exit codes, the default session directory, the extension API, and whether pi reports which context files it loaded. Not a blocker for crew's first slice, which writes its own agent directory.

## Notes

- 2026-10-15T13:05:28Z (main): scope: briefed; parented under goal hq-40a8d0; crew's implemented prepareAgentDir and pi-rpc flags (crew 90f1c66) need no template yet, so the lean is no hq template until a needed agent-directory setting is shown; the four unknown facts go to research hq-f1aff0, which wakes this idea and notes lore-ba22f3; brief: docs/notes/2026-10-15-headless-workers-brief.md
