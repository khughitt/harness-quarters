---
id: tack-ec379d
title: Generate SKILL.md from a template and skill atoms with provenance metadata
status: idea
priority: "2"
created: 2026-09-12T16:34:53Z
updated: 2026-09-12T18:52:12Z
depends: []
tags: [quick-add, skills]
source: "mindful:thought:d3bf47e9ec8c4932b86b363fbba790f8"
---

Treat SKILL.md as a build output, not the source. Source is a set of markdown fragments with frontmatter (created, modified, last reviewed, the failure the fragment guards against and where it was observed — the provenance audit's columns, ai-45934e). A generator renders the root fragment of each skill into SKILL.md; a check fails when an output drifts from its source.

Design decided 2026-09-12: one primitive, not two. A fragment may include other fragments (`{{ include: <id> }}` or similar); a template is a fragment that is mostly includes, an atom is one with none, a composite is anything between. Nesting is recursion plus a cycle check. A composite's provenance is derived at assembly time (its own frontmatter plus the union of its children's), never stored, so there are no propagation rules to design. Ordering is the order of includes in the parent. Fragment length is unconstrained by the system; shorter fragments give sharper attribution in evals, which is a curation judgment made per fragment. Atomize on demand — where a fragment is shared across skills or the audit flagged it as questionable — and leave the rest inline prose; granularity settles itself over time. Assembler is roughly a hundred lines. Rejected: templates with slots plus atoms as separate types (strictly more complex, no added expressivity); building on nodes from the start (right primitive, but a corpus and two kernels for a few hundred lines of text — revisit if the atom set wants similarity search or cross-project relations, since the format ports cleanly).

What it buys: skills evals attribute an effect to a fragment rather than a whole file; periodic curation sweeps (curate skill) walk fragments by last-reviewed date; per-model variants become a filter over fragments instead of hand-maintained forks. Vendored skills (superpowers) are an override layer, not fragments.

Deferred: an informativeness score per fragment. Choosing the wrong measure is worse than none; if one ever exists it is derived from removal experiments conditioned on model tier (ops-8fdaf6), a column obs writes, never a field a human fills in.

Source: mindful:thought:d3bf47e9ec8c4932b86b363fbba790f8

## Notes

- 2026-09-12T18:52:12Z (main): Granularity resolved to one recursive fragment primitive; informativeness score deferred (see body).
