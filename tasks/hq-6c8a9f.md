---
id: hq-6c8a9f
title: "Set up Antigravity CLI (agy) configuration, links, and live-state hygiene in hq"
status: todo
priority: 1
size: m
complexity: mid
process: direct
created: 2026-10-31T21:00:30Z
updated: 2026-10-31T21:00:30Z
depends: []
tags: []
agent: agy
origin: user
---

Why: Antigravity CLI (agy) is being adopted alongside Claude Code, Codex, and pi. Its settings (~/.gemini/antigravity-cli/settings.json) and global customizations (~/.gemini/config/{AGENTS.md,hooks.json,skills.json}) are currently unmanaged on disk, and its live model/effort picks and workspace trust need clean-filter and live-picks preservation across Git rewrites.

Done:
- agy/settings.json, agy/hooks.json, and agy/skills.json are tracked under agy/.
- links.toml declares [harness.agy] (~/.gemini/antigravity-cli -> settings.json) and [harness.agy-config] (~/.gemini/config -> AGENTS.md, hooks.json, skills.json).
- .gitattributes runs filter=harness-state on agy/settings*.json; .githooks/harness-state-clean strips AGY_JSON_KEYS (model, effort, effortByBase, trustedWorkspaces); .githooks/harness-state-refresh covers agy/settings*.json; .githooks/live-picks preserves agy model, effort/effortByBase, and trustedWorkspaces in local/live-picks-agy.json.
- facts/capabilities.toml registers agy in its harnesses list.
- Unit and rollback tests in .githooks/ and tools/ cover agy; README.md and AGENTS.md document the agy/ layout and live-state contract; just test passes.

Where: links.toml, agy/{settings,hooks,skills}.json, .gitattributes, .githooks/{harness-state-clean,harness-state-refresh,live-picks}, facts/capabilities.toml, README.md, AGENTS.md.

## Notes

- 2026-10-31T21:00:30Z (add): created
  provenance: {"origin":"user"}
