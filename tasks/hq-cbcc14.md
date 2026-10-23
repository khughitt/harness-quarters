---
id: hq-cbcc14
title: Establish safe retention for Claude units referenced by successor links
status: done
priority: 2
size: s
complexity: high
process: direct
owner: cbcc14-prune-links
created: 2026-10-22T17:51:08Z
updated: 2026-10-23T00:01:19Z
started: 2026-10-22T23:17:06Z
completed: 2026-10-23T00:01:19Z
closed: 2026-10-23T00:01:19Z
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

## Notes

- 2026-10-22T23:17:06Z (main): started
  provenance: {"harness_session":"claude-code:321ed526-7fc0-454a-a1d3-78653b539c96","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-22T23:17:17Z (main): arm: flow-trial-1 — unit tack-401088 — not enrolled
- 2026-10-22T23:17:23Z (cbcc14-prune-links): resumed
  provenance: {"harness_session":"claude-code:321ed526-7fc0-454a-a1d3-78653b539c96","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-22T23:49:48Z (cbcc14-prune-links): review: impl round 1 — verdict: revise; findings: Important 3, Minor 7; reviewer: claude-code/claude-opus-5-5
- 2026-10-22T23:55:49Z (cbcc14-prune-links): review: impl round 2 — verdict: accept; findings: Minor 7; reviewer: claude-code/claude-opus-5-5
- 2026-10-23T00:01:18Z (cbcc14-prune-links): just test at fbd2052 (docstring-only change after): 228 + 1005 + 389 + 1 passed, exit 0. Baseline at f7fe35a: 1 relay-cutover timing flake under load average ~35 (test_service_run_wait_and_result, 0.2 s service-start), passed alone in 1.9 s.
- 2026-10-23T00:01:19Z (cbcc14-prune-links): done
  provenance: {"harness_session":"claude-code:321ed526-7fc0-454a-a1d3-78653b539c96","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T00:01:19Z (cbcc14-prune-links): Fixtures (14 cases) and brief findings: pruning the older unit breaks the successor's link at quarantine; the linking unit's own prune strands its link and halts later runs, unseen by the dry run. Recommended rules 1-3 with gates recorded on hq-624351 (dep on hq-1639fd) and the obs-reader halt on hq-3b9c4c; hq-1639fd re-opened for scoping. Reviews: round 1 revise, round 2 accept (7 minors carried to hq-1639fd).
  provenance: {"harness_session":"claude-code:321ed526-7fc0-454a-a1d3-78653b539c96","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
