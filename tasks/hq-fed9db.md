---
id: hq-fed9db
title: "Keep agent working docs (handoffs, briefs, plans, tasks) in a shared agent thought collection instead of project repos"
status: idea
priority: 2
created: 2026-09-30T14:12:35Z
updated: 2026-10-11T12:05:17Z
depends: []
parent: hq-d7b5b2
tags: [quick-add]
source: "mindful:thought:af11b6542c2d6bb2e3715d0a7dca511c"
agent: claude-code/claude-opus-5-5
---

Instead of committing scoping docs in each project repo, move the doc types agents use to capture ideas, briefs, handoffs, implementation plans and tasks into a common agent thought collection (a sibling of, or mixed graph with, the user's mindful collection), still easy to reach. Repos stay lean: code, key dev/user docs, maybe specs. Touches the design-doc policy (ops profiles, global instructions) and mindful storage.

## Notes

- 2026-10-02T15:29:12Z (main): scope: briefed; parented under tack-d7b5b2; about 2,770 task records, 300 plans, 148 specs, 73 briefs across 21 checkouts; flow's record-with-code, tasks stale_copy, the design_docs profile field, repo-path links, and obs indexing depend on the location; lean: move the narrative layer (briefs, handoffs, plans) only; waits on which layers leave and on timing vs flow-trial-1; brief: docs/notes/2026-10-02-agent-working-docs-brief.md
- 2026-10-02T15:31:04Z (main): Answered: narrative layer only (briefs, handoffs, plans); start now; waits on research tack-fa8757
- 2026-10-10T13:52:03Z (main): scope: briefed; rerun after the user's 2026-10-02 answer, which the brief already records (§5: narrative layer only, start now); no new artifact; still waits on research hq-fa8757, now pointed at mindful's landed authorship (mind6-cfedc7) and raw/curated spaces design (mind6-8df975); brief moved with the lore split, and hq-89bd30 fixes the dangling sources; brief: lore:docs/notes/2026-10-02-agent-working-docs-brief.md
- 2026-10-10T20:11:22Z (main): hq-fa8757 finding (2026-10-10): mindful v6 holds agent-authored briefs/plans verbatim today with stable ids and agent ownership (--as agent:<id>@<model>, --by filter); shape is a shared corpus by owner plus an aliased #agent-docs tag, not a separate collection. Moving plans needs a tasks change (external --plan/--spec link form plus a configured fetch) and a small obs change (no_path for scheme-prefixed plans, recognise the reference in review text). Design task: hq-5a3e12; brief: lore:docs/notes/2026-10-02-agent-working-docs-brief.md §5–§6.
- 2026-10-11T12:05:17Z (main): scope: drop; the hq-fa8757 finding was acted on: design hq-5a3e12 (spec docs/specs/2026-10-10-agent-docs-collection-design.md, accepted and merged in f9f3331) settles the collection shape, reference form and write path, with implementation filed as tasks-91f63b, tasks-00723a, ops-721511, mind6-646ca1, obs-caab0c, lore-ef7e5b, flows-2ea069; nothing in this idea remains outside that design; source thought stays on this record and the brief on goal hq-d7b5b2; proposal: drop as covered by hq-5a3e12
