---
id: hq-de5be1
title: "After a pi login on europa, confirm a default model and thinking pick there is captured to local/live-picks-pi.json"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-19T09:22:21Z
updated: 2026-10-19T09:22:21Z
depends: []
parent: hq-aa9b44
tags: []
agent: claude-code/claude-opus-5-5
---

Why: hq-a8d65f installed and linked pi on europa, but no login exists there yet, so no model or thinking pick could be made; its 2026-10-16 note asked to verify pi defaults survive capture plus checkout on europa.

Done: after the user logs in to pi on europa (auth.json is per host), pick a default model and a thinking level in an interactive pi; local/live-picks-pi.json in hq records both units; pi/settings.json keeps them after a checkout of that file run on titan (avoid index-writing git on europa). The shutdown refresh already exits 0 on europa (hq-a8d65f).
