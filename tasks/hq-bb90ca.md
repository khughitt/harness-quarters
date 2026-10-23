---
id: hq-bb90ca
title: "SL11 fixtures for turn-final messages, task evidence, forks and escapes"
status: done
priority: 2
size: s
complexity: mid
process: direct
owner: session-evidence-reader
created: 2026-10-23T16:11:45Z
updated: 2026-10-23T17:41:30Z
started: 2026-10-23T16:28:09Z
completed: 2026-10-23T17:29:57Z
closed: 2026-10-23T17:29:57Z
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

## Notes

- 2026-10-23T16:11:45Z (session-evidence-reader): gate: scoped — step of hq-c411df plan
  provenance: {"harness_session":"claude-code:2d4a0242-c612-4fd2-86ef-f40cb8d35dc4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T16:28:09Z (session-evidence-reader): started
  provenance: {"harness_session":"claude-code:f7f539e5-48f4-4265-a16a-be9f26e40276","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T16:28:20Z (session-evidence-reader): arm: flow-trial-1 — unit tack-c411df — flow on
- 2026-10-23T16:28:26Z (session-evidence-reader): gate: implementing .worktrees/session-evidence-reader
  provenance: {"harness_session":"claude-code:f7f539e5-48f4-4265-a16a-be9f26e40276","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T17:06:03Z (session-evidence-reader): review: impl round 1 — verdict: revise; findings: important 1, minor 7; reviewer: claude-code/claude-opus-5-5
- 2026-10-23T17:18:11Z (session-evidence-reader): review: impl round 2 — verdict: accept; findings: minor 5; reviewer: claude-code/claude-opus-5-5
- 2026-10-23T17:22:35Z (session-evidence-reader): review: impl round 3 — verdict: accept; findings: minor 2; reviewer: claude-code/claude-opus-5-5
- 2026-10-23T17:29:33Z (session-evidence-reader): gate: verified tree:d6057f6ef57c62e0bb915d5e861ba5e5462cf946 — checks: SL11 self-checks seen failing with fixtures absent then passing (uv run pytest tools/test_session_log_cases.py 34 passed) and 20 targeted fixture breaks each failing its test and passing when reverted and just test passed on this tree (agents/bin 231 and tools 1037 and relay cutover 389 + 1) and fixture key layouts probed against live Claude and Codex stores keys-only and the task document captured from the real tasks CLI over an isolated scratch registry; review: important addressed XK history start ordinal contradicted its ambiguous copied range, minor addressed Codex ordinals were 1-based, minor addressed exec and spawn output shapes and spawn namespace, minor addressed stop summary before the synthetic turn end, minor addressed queued human attachment keys and placement, minor addressed live key order on four records, minor addressed XK status left open, minor addressed self-check gaps for documented facts, minor addressed XK status reasoning named the open question, minor addressed fork key copy label disagreement stated, minor addressed Codex version ranges corrected, minor addressed overlong prose line, minor addressed self-checks for queued placement and zero-based ordinals, minor deferred ordinal loop passes vacuously on an empty glob, minor deferred paragraph reflow near cases line 76; reviewer: claude-code/claude-opus-5-5
  provenance: {"harness_session":"claude-code:f7f539e5-48f4-4265-a16a-be9f26e40276","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T17:29:46Z (session-evidence-reader): deviations from plan Task 1, each ruled for live fidelity: TD harness_session_source is the real CLI value CLAUDE_CODE_SESSION_ID (plan wrote native) because TD is real tasks show output, CM:18 queued human attachment follows the tool result (plan put it before) because every live human queued attachment does, CM:59 has no stop_hook_summary before its turn_duration (plan rule said every one does) because live writes none after a synthetic message, XE te7 adds the spawn output as live spawns and XP do, XK carries subagent_history_start_ordinal 7 (past its last record) because live forks from Codex 0.150 carry the key and its value must agree with the all-copied range. Spec 8.3 fork-boundary question carried to obs-d98663.
- 2026-10-23T17:29:47Z (session-evidence-reader): retro: probing live key layouts before writing fixtures paid off, but a keys-only probe missed what a key's value means (subagent_history_start_ordinal), which only a reviewer comparing values to behaviour caught. Generating fixtures from a scratch script made three fix rounds cheap, since line refs could be re-derived. Writing fixtures before the RED tests cost a move-aside step: write the tests first.
- 2026-10-23T17:29:57Z (session-evidence-reader): done
  provenance: {"harness_session":"claude-code:f7f539e5-48f4-4265-a16a-be9f26e40276","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T17:29:57Z (session-evidence-reader): SL11 fixtures, cases section and self-checks landed (4ea2d2f and the review-fix commit); verified tree d6057f6, three review rounds, two minors deferred
  provenance: {"harness_session":"claude-code:f7f539e5-48f4-4265-a16a-be9f26e40276","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-23T17:41:29Z (main): attached: gen_sl11.py (36738 bytes): generator that writes the SL11 fixtures (python3 -I gen_sl11.py <fixtures-dir> <tasks-show-json>)
- 2026-10-23T17:41:30Z (main): attached: capture-task.sh (1522 bytes): captures tasks show zz-000021 --json from the real CLI over an isolated scratch registry
