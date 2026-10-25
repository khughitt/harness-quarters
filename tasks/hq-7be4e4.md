---
id: hq-7be4e4
title: Design a print-only review prompt preview from the brief
status: todo
priority: 2
size: s
complexity: high
process: planned
created: 2026-10-25T12:26:34Z
updated: 2026-10-25T12:26:34Z
depends: []
parent: hq-4c1555
tags: []
source: docs/notes/2026-10-13-first-prompt-motifs-brief.md
agent: codex
---

Why: The owner wants less copying of review targets and context between sessions. The two completed experiments support investigating a narrow print-only preview, while hq-2b3929's path-based selection proposal is post-hoc and only partly independently confirmed. Read [ref:brief] for the original intent and bounds, [ref:drafts] for the observed corrections and recommendation, and [ref:dry-run] for the recovery limits.

Done: Produce a frozen, reviewable design for a print-only review prompt preview and obtain the owner's design review before any implementation. Compare starting from an artifact path against the rejected latest-task-handoff default and stopping with manual requests. Recommend the smallest supported review kinds and input contract; do not silently promote inferred candidates into an authoritative frozen review target.

The design settles: resolving the repository and named checkout/worktree from the path; selecting an explicit commit or proposing the latest commit touching that path on that checkout's HEAD; validating repository/commit/blob identity and refusing a differing working file; finding candidate tasks from explicit artifact links and notes without basename-only matching; handling absent, ambiguous, incidental or superseded matches; showing provenance, inferred fields, prior verdicts (including accepts before a merge) and later artifact revisions. Decide whether implementation reviews belong in the first version; if included, require an explicit commit and preserve supplied report/context and verification counts. Keep historical reconstruction distinct from current readiness. Unsupported review kinds and unavailable out-of-tree inputs remain explicit.

Bound: Design only. No product CLI, harness launch, interactive editor, new session collection, reconstruction of the missing 41 identities, mandatory shared schema, session index, fzf, dual launch or new template consumer. A preview prints text for the person to edit and use. Consider existing task refs/notes first; any proposed tasks/flows handoff change needs a demonstrated gap and named ownership rather than becoming an assumed prerequisite. Production CLI spelling and ops vocabulary adoption are decided with a later implementation scope.

Verification to specify: use the retained C01/C02/C03 examples with the observed-versus-derived distinction, plus focused fixtures for ambiguity, missing revision, wrong checkout, changed working bytes, hash conflict, stale selection, earlier verdicts and unsupported kinds. Do not treat these three historical cases or constructed fixtures as population coverage or a test of an interactive editor. Human judgement of any eventual rendered preview remains a separate gate.

Where to look: tools/hq_cli/{cli,sessions,launch,projects}.py, tools/hq.toml and tools/test_hq_sessions.py currently implement session listing/resume, not new review prompts. Reports are committed in 7d66d22 and the experiment merged at 0ed7d6b. hq-2d8e81 owns the private retained inputs; verify its current manifest records before reading raw inputs and keep raw request text local. The brief already carries the report-level evidence, so no fresh collection is needed.

Ideas it wakes: After the reviewed design records its recommendation, run tasks note hq-2d8e81 --no-reviewed "<finding, reviewed design revision and next bounded action>" before the design branch merges. hq-2d8e81 stays an idea until that result supports a production scope.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-13-first-prompt-motifs-brief.md — owner intent, completed experiments and preview design bounds
- drafts (input, required, kind=report): tasks/files/hq-2b3929/validated-review-draft-report.md — observed corrections, thin path-selection evidence and design recommendation
- dry-run (input, required, kind=report): tasks/files/hq-268cc2/review-dry-run-report.md — recovery limits and validation gap
