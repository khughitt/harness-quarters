---
id: tack-baf823
title: A doc that describes a grammar carries an example parsed before review
status: shelved
priority: "2"
created: 2026-09-24T14:36:14Z
updated: 2026-09-24T14:50:06Z
depends: []
tags: [flow]
source: ai-c78706
agent: "claude-code/claude-opus-5-5[1m]"
---

Retro group (curation pass ai-c78706), 3 retros: ai-f6a3a1 (writing the grammar and corpus before the parser made review a grammar-vs-code diff; all four findings came from it), ai-6a599a (parsing a concrete instance of the documented shape turned the doc row into a checked example; 'worth doing for any doc that describes a grammar'), ai-634de8 (the first note in the new shape was parsed before it was written). Proposal: a rule or flow line: when a change documents a machine-read shape (a note grammar, a frontmatter, a CLI output), write the grammar and a corpus first and parse the documented example before review. Target: agents/skills/flow/SKILL.md or AGENTS.md; possibly a candidate for the functional-core framing doc (ai-634de8) instead. Human decides.

## Notes

- 2026-09-24T14:50:06Z (main): shelved: a retro outside the functional-core tree (ai-634de8 and its steps) credits a grammar or corpus written before its parser, or a review finds a documented shape that fails to parse
- 2026-09-24T14:50:06Z (main): scope: shelved; all three retros come from one effort (ai-634de8, ai-f6a3a1, ai-6a599a) whose spec already required corpus-first for gate notes, so this is one practice seen once, not a recurrence; wakes on a second effort
