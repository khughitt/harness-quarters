---
id: tack-a15e38
title: Jev-style bounded reviewer question over past verified gates
status: shelved
priority: 2
created: 2026-09-22T02:55:34Z
updated: 2026-09-29T20:54:33Z
depends: [tack-634de8]
tags: [flow, obs]
source: docs/specs/2026-09-21-functional-core-design.md
agent: claude-code/claude-fable-5-1
---

From the functional core framing spec section 3.6: ask one bounded, typed question of each verified gate on record ('does this note evidence an independent review of the named tree?', answer with a probability) and compare the distribution against the retros and the review outcomes in the notes. If the answers separate the gates the retros complain about, the question becomes part of the verified gate's check. Wake: the typed verdict shape (spec section 4.2) has landed, so the question has structure to read.

## Notes

- 2026-09-29T20:54:33Z (main): scope: shelved; its wake (the typed verdict, spec 4.2) landed 2026-09-22, but the corpus is too thin to separate anything: 31 verified gates across projects, 9 with a review: field, 27 retros, and no retro complains that a review was missing or not independent. obs-00809f's judged rounds (pilot 2: attribution 0.65 against a 0.9 gate) are the larger corpus a probe would join to.
- 2026-09-29T20:54:33Z (main): shelved: obs-00809f attributes review rounds to tasks reliably (so gate notes can be compared with observed reviews), or 60 verified gates carry the review: field (9 on 2026-09-29), or a retro names a gate whose review was not independent
