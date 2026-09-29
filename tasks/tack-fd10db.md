---
id: tack-fd10db
title: Relay entry for claim-guard over relay's turn-end guard
status: todo
priority: "2"
size: s
complexity: low
process: direct
created: 2026-09-25T02:36:07Z
updated: 2026-09-25T02:36:07Z
depends: [tack-539508]
parent: tack-756baa
tags: [hooks]
source: ai-21ea5d
agent: claude-code/claude-opus-5-5
---

Thin adapter over ops hooks/claim-guard decide(), in the idiom of relay-guard over claude-pretooluse; replaces the native Stop entries at the cutover. Spec docs/specs/2026-09-24-turn-boundary-gate-design.md §3.4.
