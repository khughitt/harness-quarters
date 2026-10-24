---
id: hq-a45dd8
title: Add a two-turn task-evidence fixture so the session-level task_evidence label is tested
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-10-23T17:40:19Z
updated: 2026-10-24T11:42:13Z
depends: []
parent: hq-cff824
tags: []
agent: claude-code
---

Why: SL11's CT1 and CT3 each contain one turn. At a226bbe, CT1 has seven records and tools/test_session_log_cases.py only checks that TD's stamped note falls somewhere within that session. The reviewed reader contract [ref:reader-spec] section 9.4 assigns task_evidence: session to turns outside the evidence span, but the plan's obs step 9 assertion currently selects zero such turns. hq-c411df's integration review identified this gap.

Done:
- Append a second completed typed-human turn after CT1:7 in tools/fixtures/session-logs/turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000022.jsonl, using the existing synthetic Claude 2.1.304 record shapes. Preserve the first seven records and TD's note at 2026-10-12T12:00:30Z. The second turn starts after the first ends; neither turn mentions zz-000021.
- Extend the fixture self-check in tools/test_session_log_cases.py to require two completed turns, prove the stamp is inside only the first turn's bounded span, and prove the second is outside it. Write the assertion first so the existing one-turn fixture fails; do not add a transcript parser to the fixture checks.
- Update [ref:cases]' CT1 inventory and SL11 Question C with both turn ranges: the first has provenance_stamp and the second has task_evidence: session, which is session association rather than evidence inside that turn.
- Include the two deferred hq-bb90ca round-3 minors already recorded on this task: bind the Codex fixture paths in test_sl11_codex_statuses_by_closing_event and assert exactly three before checking ordinals, and reflow the turns/ paragraph near line 76 of the cases document.
- Before this result's branch merges, record the new fixture/cases commit and exact turn references on obs-d98663. That task owns re-vendoring from hq main and the reader assertion: require exactly two CT1 turns, one with the stamp and one with task_evidence: session. Do not implement or roll out the obs reader here.
- Verification: demonstrate the new self-check fails before the fixture update and passes after it; run just test successfully. The fixture self-check proves the input distinctions exist; the actual reader labels remain obs-d98663's acceptance obligation.

Where: [ref:cases] is the current line-reference and replay contract; [ref:reader-spec] sections 9.4 and 14.3 establish the required labels. The frozen plan at 1fea7bf:docs/plans/2026-10-23-session-evidence-reader.md, obs step 9, contains the vacuous assertion. Keep that reviewed plan unchanged and carry its correction in the obs handoff note.

## Original captured report

Why: SL11's CT1 and CT3 each hold one turn, so spec section 9.4's task_evidence: session label (a session's turns outside the evidence span) has no fixture, and obs step 9's assertion of it is vacuous (hq-c411df integration review, noted on obs-d98663). Approach: a second CT1 turn after the stamped note's span in tools/fixtures/session-logs/turns, a self-check, and a cases-document row. Re-vendor into obs after. Verification: the new self-check fails before the fixture exists.

## References

- cases (input, required, kind=report): docs/notes/session-log-acceptance-cases.md — CT1 turn ranges, replay contract and SL11 task-evidence expectations
- reader-spec (input, required, kind=spec): docs/specs/2026-10-23-session-evidence-reader-design.md — reviewed task-evidence contract, sections 9.4 and 14.3

## Notes

- 2026-10-23T17:52:52Z (main): fold in two deferred minors from hq-bb90ca's round-3 review while touching the same files: the ordinal loop in test_sl11_codex_statuses_by_closing_event passes vacuously if its glob matches nothing (bind the paths and assert there are three, or move it into its own test), and the turns/ paragraph near line 76 of docs/notes/session-log-acceptance-cases.md is wrapped short (reflow it).
