---
id: tack-fe88ef
title: Hook commands name the lore and ops checkouts by path; link them under ~/.local/bin so a rename of either costs no Codex re-trust
status: idea
priority: 3
size: s
created: 2026-10-06T13:23:04Z
updated: 2026-10-06T13:23:04Z
depends: []
tags: []
source: tack-8b7a28
agent: claude-code/claude-fable-5-1
---

The September rename moved harness-state-refresh behind a ~/.local/bin link so the command string survives a rename. The profile hook (~/d/lore/hooks/claude-profile) and ops's hooks (~/d/ops/hooks/…) are still named by checkout path in claude/settings.json and codex/hooks*.json. Renaming lore or ops would change those strings and cost a re-trust in every Codex home. Changing them now costs one re-trust. From the rename design §3.6.
