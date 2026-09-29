---
id: tack-a15e38
title: Jev-style bounded reviewer question over past verified gates
status: idea
priority: "2"
created: 2026-09-22T02:55:34Z
updated: 2026-09-22T02:55:34Z
depends: [tack-634de8]
tags: [flow, obs]
source: docs/specs/2026-09-21-functional-core-design.md
agent: claude-code/claude-fable-5-1
---

From the functional core framing spec section 3.6: ask one bounded, typed question of each verified gate on record ('does this note evidence an independent review of the named tree?', answer with a probability) and compare the distribution against the retros and the review outcomes in the notes. If the answers separate the gates the retros complain about, the question becomes part of the verified gate's check. Wake: the typed verdict shape (spec section 4.2) has landed, so the question has structure to read.
