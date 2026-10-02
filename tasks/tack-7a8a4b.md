---
id: tack-7a8a4b
title: The executing-plans task-done helper exits 1 after a successful silent verification command because its summary grep finds no nonblank line; wrapping the command with a success line records completion.
status: shelved
priority: 2
created: 2026-09-30T10:10:14Z
updated: 2026-10-02T14:30:58Z
depends: []
tags: [feedback, friction, "from:ops"]
agent: codex
---

## Notes

- 2026-10-02T14:30:57Z (main): scope: shelved; fixed upstream on obra/superpowers dev by PR #2388 (merge 907ad21, 2026-09-26: '|| last="(no output)"'), not yet released — submodule and Claude plugin are both v6.4.1 with the bare grep at task-done:48; the tack action is a submodule/plugin bump once a release carries it
- 2026-10-02T14:30:57Z (main): shelved: a superpowers release containing upstream 907ad21 (PR #2388) — then bump agents/vendor/superpowers and confirm the plugin caches pick it up
