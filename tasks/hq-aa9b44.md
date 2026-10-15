---
id: hq-aa9b44
title: "Manage pi's interactive agent-directory configuration in hq, as for Claude Code and Codex"
status: todo
priority: 2
size: m
complexity: mid
process: direct
created: 2026-10-15T19:39:21Z
updated: 2026-10-15T19:43:58Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
---

Why: the user wants to customize pi's base configuration and experiment in interactive mode with it versioned in hq, as claude/ and codex/ are. Today [harness.pi] in links.toml links only AGENTS.md into ~/.pi/agent; settings.json there is a plain file pi created (holding only lastChangelogVersion), and keybindings.json, mcp.json, models.json, APPEND_SYSTEM.md/SYSTEM.md, extensions/, prompts/ and themes/ are absent.

Done: both children closed — pi's settings.json is tracked under pi/ and linked into ~/.pi/agent with its session state kept out of the index, and pi's model and thinking picks survive a git rewrite as Claude's and Codex's do. Other agent-directory files (keybindings.json, APPEND_SYSTEM.md, prompts/, themes/, extensions/) are linked one links.toml line each as they gain content; they need no task. This goal's closeout is direct.

Established (pi 1.1.0, read 2026-10-15 in ~/.local/share/pi/1.1.0, dist/core/settings-manager.js, core/agent-session.js, modes/interactive/interactive-mode.js):
- SettingsManager.withLock writes settings.json with writeFileSync under a proper-lockfile lock (realpath: false): a symlinked file is written through, not replaced.
- Session state pi writes there: defaultProvider + defaultModel together (setDefaultModelAndProvider, on model select and cycle; one picker unit); defaultThinkingLevel (setThinkingLevel with persist; a second unit, like Claude's effortLevel); lastChangelogVersion (interactive startup after an update; bookkeeping).
- Configuration pi writes there, to stay tracked: every /settings change, including modelThinkingLevels (onModelThinkingLevelChange in /settings) and enabledModels (scoped models).
- Runtime state that stays out of hq: auth.json, trust.json (project trust, its own file), models-store.json (catalog cache), sessions/.
- tools/harness-links refuses a real file at a link path, so the existing ~/.pi/agent/settings.json moves aside before `just link --apply`.

Where: links.toml [harness.pi]; .gitattributes; .githooks/harness-state-clean, live-picks, harness-state-refresh and their tests; docs/specs/2026-10-10-live-model-preservation-design.md; README.md's pi/ entry. Related: hq-7a69dc (crew's per-attempt headless agent directories, a different home); relay-828903 (a pi adapter in relay's live-agent registry).

## Notes

- 2026-10-15T19:41:36Z (main): scope: scoped; filed 2026-10-15 from a crew session and scoped against pi 1.1.0's settings-manager, agent-session and interactive-mode code and hq's harness-state-clean, live-picks, harness-state-refresh and harness-links; split into hq-61a47e (link and filter, direct) and hq-24416e (pick preservation and pi turn-end capture, planned, depends on hq-61a47e)
- 2026-10-15T19:43:58Z (main): trial: flow-trial-1 — enrolled — flow on
