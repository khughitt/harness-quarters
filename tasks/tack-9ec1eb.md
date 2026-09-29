---
id: tack-9ec1eb
title: Prune AGENTS.md by the provenance audit; per-model variants only where the answer differs by model
status: todo
priority: "2"
size: m
complexity: mid
process: direct
created: 2026-09-12T16:11:20Z
updated: 2026-09-16T15:51:35Z
depends: []
tags: [quick-add, skills]
source: "mindful:thought:8e45d49e001c4e5eb9b00f159dc60e87"
---

Why: every session on every project loads AGENTS.md (~1170 words of rules) and the tasks skill (~3270 words). The provenance audit (doc/instruction-provenance.md, ai-45934e) found that only two rules have post-rule recurrence on a current model (attribution, design docs) and that in both cases the hook is the working guard, not the prose; the largest bullets spend most of their words on mechanics a tool or hook already owns, or on text duplicated between bullets. Removing that costs no guard by construction, so it needs no experiment. Rules with no recorded failure are a different case: dropping one is a hypothesis, and only a measure (ai-9dfba9, ops-8fdaf6) can test it.

Done: (a) the four mechanical children land and AGENTS.md is under ~750 words with every rule the audit marks as a live guard still present, verified by a fresh-session dry read and by the hook still blocking a trailer and a docs/superpowers stage; (b) the removal-experiment child has either run against a measure or been shelved with the measure named as its wake condition. Per-model variants are decided only after (b): a rule becomes a variant only when its answer differs by model, and the record cannot show that until the hook block log carries a model field (ops-acd029).

Where to look: doc/instruction-provenance.md (rows A7, A9, A10, A13, A14–A16 and the ranked removal list); ops hooks/claude-pretooluse (its refusal messages are where mechanics move); the tasks-skill trim is tasks-9a9ef3 in the tasks project, not a child here.

Reframed 2026-09-12 after reading https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra: the axis is instruction age, not model tier — a rule written against an older model's failure becomes dead weight or active harm for every model once the failure is gone. Useful claims: trim skill descriptions to the trigger condition; make SKILL.md a router to supporting docs; revisit every AGENTS.md line; strong models over-read restrictive language, so define completion up front. It cites no evals. Vendored skills (superpowers, ponytail) follow the same audit but are overridden, not edited. If the skill-atoms generator (ai-ec379d) lands, the audit rows are its provenance metadata and variants are its build targets.

Source: mindful:thought:8e45d49e001c4e5eb9b00f159dc60e87

## Notes

- 2026-09-16T14:23:33Z (main): Input landed: doc/instruction-provenance.md (ai-45934e) ranks 13 removal candidates by words saved; the per-model question stays open until the hook log carries a model field (ops task filed from ai-45934e).
- 2026-09-16T15:51:35Z (main): scope: scoped; rewritten as a direct goal over the audit's removal list — four mechanical children (ai-341dcc, ai-443e72, ai-4a90a7, ai-7349c4 which waits on ops-09a86b) whose check is by construction, plus the removal-experiment idea ai-53cc68 waiting on the measure (ai-9dfba9, ops-8fdaf6, ops-acd029); the evals dependency moved from the goal to that child. The tasks-skill trim is tasks-9a9ef3, not a child.
