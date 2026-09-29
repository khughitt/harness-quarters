---
id: tack-7a1b66
title: Detached smoke runs own their cleanup and the turn report lists what is left running
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-21T21:03:21Z
updated: 2026-09-21T21:03:39Z
started: 2026-09-21T21:03:26Z
completed: 2026-09-21T21:03:39Z
depends: []
tags: [rules]
source: ops-38be00
agent: claude-code/claude-opus-5
---

The ai half of ops-38be00: a smoke or live-run script an agent launches detached (setsid nohup … & disown, a background bun/node/weston, a tmux server) must own a cleanup that reaps its children on its own exit and on the harness's stop, and the end-of-turn report lists any process the session leaves running. ops's bin/host-load (section session) is the check; its orphans sweep verifies across sessions. Lands in AGENTS.md, the global instructions.

## Notes

- 2026-09-21T21:03:26Z (main): started
  provenance: {"harness_session":"claude-code:b8195a28-17fd-4ebc-a65c-00a2a97213e8","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T21:03:39Z (ai-7a1b66): done
  provenance: {"harness_session":"claude-code:b8195a28-17fd-4ebc-a65c-00a2a97213e8","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-21T21:03:39Z (ai-7a1b66): AGENTS.md gains a Processes section: detached smoke and live runs own their cleanup and reap on exit and harness stop; the end-of-turn report names anything left running, checked with host-load --section session; --kill stays the user's call.
  provenance: {"harness_session":"claude-code:b8195a28-17fd-4ebc-a65c-00a2a97213e8","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
