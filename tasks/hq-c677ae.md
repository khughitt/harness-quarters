---
id: hq-c677ae
title: cli-pane /m picker rows show the thought's color from mindful
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-10-15T08:29:47Z
updated: 2026-10-15T08:29:47Z
depends: []
parent: hq-65f661
tags: []
source: hq-4ba161
agent: claude-code/claude-opus-5-5
---

Why: the source thought for hq-b7b9ac asks for color while picking. Row colors depend on mindful's active scheme, so they come from mindful (decided in hq-4ba161; docs/notes/2026-10-10-context-discovery-brief.md, Picker findings), not from slot indices resolved in hq.

Done when: each picker row draws the resolved color mind6-5a8082 adds to `mindful --json search` rows (a swatch or the title's color, whichever reads better beside the tag chips), with a test row carrying a synthetic color; rows still carry readable tags; a row without the field is an error the test names, not a silent uncolored row, once mindful's contract makes it required.

Where to look: claude/mods/cli-pane/hooks/register.tsx (the picker from hq-b7b9ac), mind6-5a8082 for the field's name and shape. No palette logic in hq.
