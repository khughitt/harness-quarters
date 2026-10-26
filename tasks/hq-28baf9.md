---
id: hq-28baf9
title: Amend the session evidence reader spec with Stage A's implementation rulings and live findings
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-10-26T02:53:19Z
updated: 2026-10-26T02:53:19Z
depends: []
parent: hq-cff824
tags: [session-logs]
source: obs-d98663
agent: claude-code
origin: agent
---

obs-d98663 built Stage A of the reader against spec ae0f8ee (rev 5) and plan 1fea7bf. Its controller ruled on gaps the spec leaves open and its live six-root run measured shapes the spec did not know. The spec (docs/specs/2026-10-23-session-evidence-reader-design.md) should record each, as a reviewed revision, before Stage B rewrites the skill around the reader:

1. §8.3 Codex fork boundary: the native session_meta subagent_history_start_ordinal agreed with the parent turn-id boundary on 269/269 live forks that carry it (Codex >= 0.147; older forks lack it). Decide whether the reader honours it (it would turn parent-unavailable forks from ambiguous into fork_history). Stage A does not (ruling R11).
2. §8.2 rows for Codex kinds with none (Stage A labels them unknown, R15): event_msg token_count (the bulk of ~2.1M unknown records over 33 GiB), thread_settings_applied, response_item additional_tools, and the other unknown kinds the live run counted.
3. §8.3 resume rule 3: 'or a file has no unshared record' read as 'a file with no unshared record cannot meet the timing test'; a wholly copied original with a resume that adds records is a decided resume, not a tie (R26).
4. §4.3 relation 'mismatch' for a file whose name carries the id but whose recorded identity differs (R19); index rows under no current root counted and making an empty answer unknown, basis index_roots_mismatch (R20).
5. §9.1 a run of responses with no opening input forms a turn with trigger null (R28); turn field abort_reason (R30).
6. §7.2 a record ref's target line is exempt from --limit, with coverage target.turn_cut (step 10).
7. §4.6/§6.5 new coverage fields and bases: matches.collapsed_copies and basis collapsed_copy_match (a match only in a collapsed copy makes an empty answer unknown), files.aliases_not_read and basis alias_not_read, query.sort_basis (activity order is per copy group), task.mentions_since (mention listing bounded by the task's earliest time); command fields cut to --text-bytes (R39, R44-R48).
8. §8.3 'clean prefix' wording: newer live forks copy a run of turns from mid-parent, and some copy no parent task_started; the turn-id rule still held on 20/20 sampled forks.

The full ruling list with reasons and costs is in obs-d98663's attached ledger (sdd-ledger.md).

## Notes

- 2026-10-26T02:53:19Z (add): created
  provenance: {"harness_session":"claude-code:ad0396b3-824c-4825-aa17-a5252221a532","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
