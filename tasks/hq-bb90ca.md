---
id: hq-bb90ca
title: "SL11 fixtures for turn-final messages, task evidence, forks and escapes"
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-10-23T16:11:45Z
updated: 2026-10-23T16:11:45Z
depends: []
parent: hq-c411df
tags: []
plan: docs/plans/2026-10-23-session-evidence-reader.md
step: "Task 1: SL11 fixtures for turn-final messages, task evidence, forks and escapes"
---

Task 1 of the approved plan docs/plans/2026-10-23-session-evidence-reader.md (hq 1fea7bf), implementing spec docs/specs/2026-10-23-session-evidence-reader-design.md (ae0f8ee) section 14.3 and the escaped-text control of 14.2. Work in .worktrees/session-evidence-reader, the parent hq-c411df worktree.

Contract: the plan section "Task 1" is the contract, including its fixture list, record rules, CM turn list (13 turns, 9 turn_duration records), XE/XF/XK shapes, task document and escape files, and its seven steps. Why each detail matters:
- Live key layouts (copied from live records, keys only): obs tests these fixtures against live-store behaviour; a hand-invented layout would pass the fixtures and fail live (spec rounds 2-3).
- The Stop-hook continuation in live order (end_turn, isMeta feedback, hook_blocking_error, blocked stop_hook_summary): the earlier order passed a fixture while live data misfired (spec round 3, F1).
- The Skill-load isMeta record mid-turn: the case that split 23% of live human turns under an earlier rule.
- XK with no f9 rollout anywhere: the missing-parent fork case of spec round 4; its copied final must never become the fork's.
- The three CT3 calls: single-segment error vs the two && chain forms (spec round 4, finding 2).
- The escape files: the byte-prefilter counterexample of spec round 4.
- Widening test_every_fixture_file_is_listed_by_the_cases_document to turns/: the listing test otherwise fails (plan round 1).

Verification: the SL11 self-checks fail before the fixtures exist, then pass; just test passes; each new assertion fails under its targeted break (step 6). No private text in fixtures.
