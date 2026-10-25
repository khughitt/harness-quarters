---
id: hq-2cb1ee
title: Run superpowers 7.0.1 from obra's marketplace with auto-update off
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-10-25T12:18:32Z
updated: 2026-10-25T12:18:41Z
depends: []
tags: [skills]
agent: claude-code
---

claude-plugins-official still pins superpowers 7.0.0 (bb92a77) four days after the 7.0.1 release; obra's superpowers-marketplace offers 7.0.1. User chose 2026-10-25: enable superpowers@superpowers-marketplace, disable the official entry, and set that marketplace's autoUpdate false so the plugin cannot drift ahead of lore's pinned vendor/superpowers. Then install the plugin and bump lore's pin to match.
