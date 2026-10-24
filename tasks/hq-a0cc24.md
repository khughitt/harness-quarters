---
id: hq-a0cc24
title: "No guide names just relay-subscribers, which renders the config every relay hook reads"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-24T22:15:24Z
updated: 2026-10-24T22:15:24Z
depends: []
tags: [docs]
source: hq-30fd95
agent: claude-code
---

Found by the curate-docs pass hq-30fd95 at 8686be3 (criterion 8). The justfile recipe relay-subscribers renders relay/subscribers.template.json into ~/.config/relay/subscribers.json (FORCE=1 replaces different content). Every relay hook in codex/hooks.json and the Claude settings passes that file with --subscribers. Only a dated plan (docs/plans/2026-10-19-relay-cutover.md) mentions the recipe. docs/runbooks/relay-runtime.md, which README links for installing and upgrading relay, does not name it, so a reader setting up relay on a new host cannot find the step. Add one sentence to relay-runtime.md.
