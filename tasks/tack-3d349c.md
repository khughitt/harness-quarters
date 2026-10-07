---
id: tack-3d349c
title: Write flow gate notes with tasks note --stamp so each stage boundary carries its session
status: todo
priority: 2
size: s
complexity: low
process: direct
created: 2026-10-02T19:18:22Z
updated: 2026-10-02T19:18:23Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
---

Why: tasks note --stamp (tasks-0005a6, tasks b6edc13) attaches the harness_session pair to one note. Flow's gate: notes are plain notes, so stage-cost attribution (obs-a6c7d4) still infers each stage's session from the nearest lifecycle marker.

Done: the flow skill writes every gate note with --stamp; the gate text is unchanged (tasks never interprets it). Tell obs-a6c7d4's owner the pair is now present on gate notes so attribution can read it directly.

## Notes

- 2026-10-02T19:18:22Z (main): concerns: tasks-0005a6 extension — adopt note --stamp in the flow skill's gate notes
