---
id: hq-2e7bf4
title: "Codex SessionStart runs ops's session-start hook, so Codex sessions get the stale-index repair too"
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-10-19T21:48:11Z
updated: 2026-10-19T21:48:11Z
depends: []
tags: [hooks]
source: ops-1d3a70
agent: claude-code/claude-opus-5-5
---

Why: since ops-1d3a70 (2026-10-19) the Claude Code SessionStart hook ~/d/ops/hooks/claude-sessionstart repairs the session's main checkout when the other host's commits left its git index stale, and reports a halted project and stale projects/lore inputs. The Codex home's declared hooks (codex/hooks.json) run familiar, lore's claude-profile and ops's capture-notice at SessionStart, but not that hook, so a Codex session on either host starts with phantom staged changes and commits refused until someone runs git-index-health --repair by hand.

Done: the Codex home's SessionStart runs the ops hook (or the parts of it that apply under Codex), its one-line outputs reach the Codex session, and a Codex session started in a checkout made stale on purpose reports the repair. Settle on the way: whether the hook's name should lose its claude- prefix now that two harnesses run it (hq-fe88ef: a path change costs a Codex re-trust), and whether the work home (hooks.work.json) wants it; the repair acts only inside the synced root either way.
