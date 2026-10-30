---
id: hq-7a8a4b
title: The executing-plans task-done helper exits 1 after a successful silent verification command because its summary grep finds no nonblank line; wrapping the command with a success line records completion.
status: idea
priority: 2
created: 2026-09-30T10:10:14Z
updated: 2026-10-30T12:02:25Z
depends: []
tags: [feedback, friction, "from:ops"]
agent: codex
---

## Notes

- 2026-10-02T14:30:57Z (main): scope: shelved; fixed upstream on obra/superpowers dev by PR #2388 (merge 907ad21, 2026-09-26: '|| last="(no output)"'), not yet released — submodule and Claude plugin are both v6.4.1 with the bare grep at task-done:48; the tack action is a submodule/plugin bump once a release carries it
- 2026-10-02T14:30:57Z (main): shelved: a superpowers release containing upstream 907ad21 (PR #2388) — then bump agents/vendor/superpowers and confirm the plugin caches pick it up
- 2026-10-17T12:28:34Z (main): from lore: its wake condition is met. superpowers v7.0.0 (bb92a777) carries the task-done fix, and lore-cf7783 moved both the Claude plugin and lore's vendor/superpowers to it on 2026-10-17. Closing this is hq's call (lore-ba0236 tracked it and is done).
- 2026-10-30T12:02:23Z (main): unshelved
- 2026-10-30T12:02:25Z (main): shelf recovery 2026-10-30: The 2026-10-17 note explicitly records the wake condition met: the supporting release was adopted; restore review rather than postpone the acknowledged handoff. Closing remains an owner decision. Audit evidence retained on tasks-11f6d3.
  provenance: {"harness_session":"codex:01a18ca3-4bd6-7d61-8fb4-f4ce4eda96e2","harness_session_source":"CODEX_THREAD_ID"}
