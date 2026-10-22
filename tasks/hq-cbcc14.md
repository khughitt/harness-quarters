---
id: hq-cbcc14
title: Establish safe retention for Claude units referenced by successor links
status: todo
priority: 2
size: s
complexity: high
process: direct
created: 2026-10-22T17:51:08Z
updated: 2026-10-22T17:51:08Z
depends: []
parent: hq-401088
tags: []
source: docs/notes/2026-10-22-claude-prune-links-brief.md
agent: codex
---

Question: Does the current Claude prune protocol break a surviving successor session's subagent transcript link, and can retaining referenced target units prevent that without weakening no-follow traversal or quarantine recovery?

Where to start: [ref:brief] records the observed relationship, current code and alternatives. Trace tools/session_archive/capture.py walk_files, inputs.py claude_units, prune.py evaluate/prune_run/delete_claude_unit and quarantine.py inodes/release/remove_empty_dirs. Reuse tools/test_session_archive_prune_claude.py and its existing hooks and fixture conventions. The archive spec sections 3.2-3.4 define the invariants; obs-396637 fixed the downstream indexer abort, not this retention policy.

Bound: Use only synthetic stores and archive state. Start with two Claude units: an otherwise eligible older unit holding a regular transcript, and an ineligible younger unit linking to it. Exercise dry-run and apply in isolated fixtures; record the first stage at which the link breaks and the linking unit's later quarantine outcome. Trace relative/absolute target resolution, already dangling links and a link created or retargeted at the existing precheck/quarantine/delete hooks; use the smallest additional case needed to settle each boundary. Do not touch live stores, timers, home routing or another project's code. Do not implement a production retention rule, a group-delete mechanism or a new service.

Expected result: Record a compact evidence table and recommendation on this task and in the brief: unit eligibility, target/link state before and after quarantine, restoration/partial-failure behavior, what a reference-retention rule can guarantee, and any race it cannot close. Recommend the minimum design change, identify whether hq-624351 needs an additional rollout gate, and say whether a reviewed archive-spec/plan revision is needed. Keep hq-3b9c4c's strict-readiness work separate. Check any fixture through the repository's documented test front door and record the result. A snapshot must not be described as excluding concurrent writers.

Ideas it wakes: On completion, run `tasks note hq-1639fd --no-reviewed "<finding>"` before this result's branch merges, so the idea can be re-scoped from the observed behavior and recommendation.

## References

- brief (input, required, kind=brief): docs/notes/2026-10-22-claude-prune-links-brief.md — retention question, evidence and alternatives
- archive-spec (input, required, kind=spec): docs/specs/2026-09-30-session-archive-design.md — no-follow, capture and quarantine invariants
