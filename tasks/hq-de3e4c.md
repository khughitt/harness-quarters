---
id: hq-de3e4c
title: "Survey what agents look for when they read session logs, to set the verbs of an hq logs CLI"
status: doing
priority: 2
size: m
complexity: mid
process: direct
owner: docs/logs-survey
created: 2026-10-20T16:34:37Z
updated: 2026-10-20T17:51:59Z
started: 2026-10-20T17:00:12Z
depends: []
parent: hq-cff824
tags: [session-logs]
agent: claude-code
---

Question: When agents read Claude Code or Codex session stores by hand, what are they trying to find, how do they do it, and where does it fail or cost the most? The answer sets the verbs and output of a proposed hq logs CLI and its usage skill, for example `hq logs --harness codex --profile work --start-date 2026-10-14 <text>` and `hq trace --task-id <id>` (proposed by the user 2026-10-20).
Where to start: the pilot below; the session-logs skill; [ref:brief] §2 (four store lists, three human-or-injected classifiers); hq-3558a1 (hq sessions search) and the session-search brief docs/notes/2026-10-17-session-search-brief.md, whose lane rules out a new transcript index; obs-c5c599 (report-to-session trace).
Pilot, 2026-10-20, this host: an rg prefilter over all five local stores (13 s) and a parse of 6,949 matching files (49 s) found 2,901 tool calls that touch a session store or its tooling. About half are noise: memory files under ~/.claude/projects/*/memory, overflow reads of tool-results/, edits to the tools themselves, and tasks commands quoting paths. A crude filter leaves about 1,470 calls since September, about 250 of them in Codex. Of those, 472 are hand-written Python JSON parsers, 351 grep or rg, and 68 jq. Seen in a sample: locating a feedback report's origin, recovering an earlier human turn (hq-be3f69), reading a Codex refusal in a scope pass, counting failed reads across sessions, and a reusable scratchpad segmenter (seg.py) one session wrote for itself.
Bound: Read-only. Both harnesses, both homes, and europa if its stores are reachable. The unit is an investigation episode, not a tool call: group the consecutive store-reading calls that serve one question (ten parse attempts can be one hard question) and record its triggering turn (the human or assistant text before it), its cost (calls, wall time, scripts written) and its outcome: found, not found, wrong store, gave up, or outcome unknown (stopping a search does not show it succeeded). Settle the categories on a pilot of 25-30 episodes, then classify at least 150, stratified by harness and profile. Rank question types by both frequency and cost. Note which episodes needed tool outputs, not only inputs (the feedback-origin audit needed outputs for 9 of 72), and which needed a child-to-parent link. No tool code.
Expected result: a table of question types with counts, typical inputs (task id, text, date, cwd, commit, report), the record roles each needs (human, assistant, tool call, tool output, injected), the stores and failures involved, the evidence each answer rested on (provenance stamp, successful task command, tool-output match, textual mention), and the minimal verb set plus output record that covers most of them; the design inputs in [ref:brief] §4 (alternative 4) are hypotheses for this result to confirm or overturn. Record it on this task and in a new brief section.
Ideas it wakes: On completion, run `tasks note hq-c411df --no-reviewed "<finding>"` before this result's branch merges. The locate-owner decision there folds into this CLI's design.

## References

- brief (input, kind=brief): docs/notes/2026-10-20-session-store-reach-brief.md — context and questions for this work
- survey (output, kind=report): docs/notes/2026-10-20-session-log-survey.md — episode taxonomy, costs and CLI implications
- episodes (output, kind=dataset): docs/notes/data/2026-10-20-session-log-survey.jsonl — paraphrased classifications with source references

## Notes

- 2026-10-20T17:00:12Z (main): started
  provenance: {"harness_session":"codex:01a15a40-db33-7ad3-9f26-96bc1d938379","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-20T17:00:21Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-20T17:00:21Z (main): arm: flow-trial-1 — unit tack-de3e4c — flow on
- 2026-10-20T17:00:47Z (main): gate: scoped — adopted
  provenance: {"harness_session":"codex:01a15a40-db33-7ad3-9f26-96bc1d938379","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-20T17:01:02Z (docs/logs-survey): resumed
  provenance: {"harness_session":"codex:01a15a40-db33-7ad3-9f26-96bc1d938379","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-20T17:01:03Z (docs/logs-survey): gate: implementing .worktrees/logs-survey
  provenance: {"harness_session":"codex:01a15a40-db33-7ad3-9f26-96bc1d938379","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-20T17:02:38Z (docs/logs-survey): method: direct read-only episode survey in .worktrees/logs-survey; rebuild the deleted pilot from its source session, screen a 30-episode pilot, then classify at least 150 episodes stratified by harness and home profile; europa is reachable. Raw extracts stay in temporary local storage; committed evidence will use home-relative line/block references and paraphrases.
- 2026-10-20T17:06:55Z (docs/logs-survey): pilot: 30 manually screened episodes fixed seven question categories (schema, behavior, recover, trace, identity, aggregate, inventory) and conservative outcome rules. Rebuilt screen: 7,648 matching local files, 4,113 deduplicated path/tool-matching calls, 432 candidate groups after mechanical noise exclusions (334 Claude personal, 17 Claude work, 81 Codex personal, zero Codex work). These are screening counts, not episode prevalence. Europa has 18 matching files and five memory-only calls, no candidate investigation.
- 2026-10-20T17:28:22Z (docs/logs-survey): result: 183 episodes / 1,092 investigation calls across 132 source files; schema 64, behavior 49, identity 21, inventory 17, recovery 16, aggregates 15, trace 1 batch. Historical outputs needed in 64, parent links in 32, both in 24. Outcomes 177 found, 3 bounded not-found, 3 unknown. All 2,549 referenced line hashes and call/result pairings validate. Report and brief section recommend search+show with metadata/raw streaming; trace composes typed evidence, locate ownership remains with hq-a1c591. Fresh independent review and final just test are running.
- 2026-10-20T17:36:39Z (docs/logs-survey): review: impl round 1 — verdict: revise; findings: Important 1, Minor 2; reviewer: codex/gpt-6.1-sol
- 2026-10-20T17:45:51Z (docs/logs-survey): correction: final review re-audited all32 preliminary parent flags and the remaining summaries.18 episodes need a recorded relationship:6 reverse only,10 forward only,2 both; therefore8 reverse and12 forward, with6 also needing historical outputs for reverse binding.14 preliminary flags were incidental field/child/shell observations. E055 adds an omitted supporting call: final1093 calls,183 episodes. Two Minor annotation corrections deferred to hq-edf5de under review policy. Corrected source/direction checks pass; full suite and fresh scoped re-review are required before close.
- 2026-10-20T17:51:59Z (docs/logs-survey): review: impl round 2 — verdict: accept; findings: none; reviewer: codex/gpt-6.1-sol
