---
id: hq-7a69dc
title: "pi for headless workers: an agent-directory template, and probes of the facts crew found unknown"
status: idea
priority: 2
created: 2026-10-14T01:44:15Z
updated: 2026-10-14T01:44:15Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
---

Why: crew gives each attempt its own pi agent directory (PI_CODING_AGENT_DIR), departing from keeping configuration under hq's pi home, so attempts share no session, auth or MCP state. Its design also found pi facts that hq records as unknown or does not record. Named in crew's core design (crew docs/specs/2026-10-13-crew-core-design.md §9; task crew-3fc20c).

Done: (1) a template for headless pi agent directories that crew copies per attempt; (2) probed facts for pi 1.1.0: process exit codes, the default session directory, the extension API, and whether pi reports which context files it loaded. Not a blocker for crew's first slice, which writes its own agent directory.
