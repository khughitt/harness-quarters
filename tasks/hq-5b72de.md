---
id: hq-5b72de
title: "quick-add: drop the show --json pre-read before mindful tag"
status: done
priority: "3"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-12T13:41:19Z
updated: 2026-09-16T14:13:29Z
started: 2026-09-16T14:12:58Z
completed: 2026-09-16T14:13:29Z
depends: []
tags: [skills]
source: mind6-7ee879
model: "claude-opus-5[1m]"
---

Section 4 of skills/quick-add/SKILL.md reads 'mindful --json show <seed>' and diffs related[].id before every 'mindful tag' because tag appended the relation unconditionally. mind6-7ee879 made tag idempotent (an existing relatesTo to the resolved target is a no-op, no version), so the skill can run 'mindful tag <seed> <id>' for every approved tag and drop the pre-read and the known-id bookkeeping. Needs the mind6 build that carries the fix on PATH first.

## Notes

- 2026-09-16T14:12:02Z (main): Rated low: the mind6 fix (mind6-7ee879) is done, the skill section is identified, and the check is a tag run against an already-related seed producing no new version.
- 2026-09-16T14:12:58Z (main): Process direct: installed mindful release 47f2ba4 descends from fix 8c3a614; the skill now tags via the web API whose tag op calls Mindful.tag, so the get pre-read in §4 is the only change.
- 2026-09-16T14:13:29Z (main): quick-add §4 now sends one tag op per approved tag with no get pre-read or known-id bookkeeping; the API's tag op calls the idempotent Mindful.tag (ops ee19517).
