---
id: hq-aa9b44
title: "Manage pi's interactive agent-directory configuration in hq, as for Claude Code and Codex"
status: idea
priority: 2
created: 2026-10-15T19:39:21Z
updated: 2026-10-15T19:39:21Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
---

Why: the user wants to customize pi's base configuration and experiment in interactive mode with it versioned, as claude/ and codex/ are. Today [harness.pi] in links.toml links only AGENTS.md into ~/.pi/agent; settings.json is a plain file pi created, and keybindings.json, mcp.json, models.json, APPEND_SYSTEM.md/SYSTEM.md, extensions/, prompts/ and themes/ are absent.

Findings (pi 1.1.0, read 2026-10-15): SettingsManager writes settings.json with writeFileSync under a proper-lockfile lock (realpath: false), so a symlinked file is written through, not replaced. pi writes live state into it: setDefaultModelAndProvider on model select/cycle, setDefaultThinkingLevel/setModelThinkingLevel, lastChangelogVersion after an update, and every /settings change. trust.json (project trust), auth.json, models-store.json (cache) and sessions/ are runtime state and stay out of hq.

Likely shape: pi/settings.json (and the other files as they get content) linked under [harness.pi.links]; the harness-state clean filter and .githooks/live-picks extended to pi's model, thinking and changelog keys; README updated. Distinct from hq-7a69dc (a template for crew's per-attempt headless agent directories), though a managed base config may inform it.
