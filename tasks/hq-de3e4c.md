---
id: hq-de3e4c
title: "Survey what agents look for when they read session logs, to set the verbs of an hq logs CLI"
status: todo
priority: 2
size: m
complexity: mid
process: direct
created: 2026-10-20T16:34:37Z
updated: 2026-10-20T16:50:59Z
depends: []
parent: hq-cff824
tags: [session-logs]
agent: claude-code
---

Question: When agents read Claude Code or Codex session stores by hand, what are they trying to find, how do they do it, and where does it fail or cost the most? The answer sets the verbs and output of a proposed hq logs CLI and its usage skill, for example `hq logs --harness codex --profile work --start-date 2026-10-14 <text>` and `hq trace --task-id <id>` (proposed by the user 2026-10-20).
Where to start: the pilot below; the session-logs skill; [ref:brief] §2 (four store lists, three human-or-injected classifiers); hq-3558a1 (hq sessions search) and the session-search brief docs/notes/2026-10-17-session-search-brief.md, whose lane rules out a new transcript index; obs-c5c599 (report-to-session trace).
Pilot, 2026-10-20, this host: an rg prefilter over all five local stores (13 s) and a parse of 6,949 matching files (49 s) found 2,901 tool calls that touch a session store or its tooling. About half are noise: memory files under ~/.claude/projects/*/memory, overflow reads of tool-results/, edits to the tools themselves, and tasks commands quoting paths. A crude filter leaves about 1,470 calls since September, about 250 of them in Codex. Of those, 472 are hand-written Python JSON parsers, 351 grep or rg, and 68 jq. Seen in a sample: locating a feedback report's origin, recovering an earlier human turn (hq-be3f69), reading a Codex refusal in a scope pass, counting failed reads across sessions, and a reusable scratchpad segmenter (seg.py) one session wrote for itself.
Bound: Read-only. Both harnesses, both homes, and europa if its stores are reachable. The unit is an investigation episode, not a tool call: group the consecutive store-reading calls that serve one question (ten parse attempts can be one hard question) and record its triggering turn (the human or assistant text before it), its cost (calls, wall time, scripts written) and its outcome: found, not found, wrong store, gave up, or outcome unknown (stopping a search does not show it succeeded). Settle the categories on a pilot of 25-30 episodes, then classify at least 150, stratified by harness and profile. Rank question types by both frequency and cost. Note which episodes needed tool outputs, not only inputs (the feedback-origin audit needed outputs for 9 of 72), and which needed a child-to-parent link. No tool code.
Expected result: a table of question types with counts, typical inputs (task id, text, date, cwd, commit, report), the record roles each needs (human, assistant, tool call, tool output, injected), the stores and failures involved, the evidence each answer rested on (provenance stamp, successful task command, tool-output match, textual mention), and the minimal verb set plus output record that covers most of them; the design inputs in [ref:brief] §7 are hypotheses for this result to confirm or overturn. Record it on this task and in a new brief section.
Ideas it wakes: On completion, run `tasks note hq-c411df --no-reviewed "<finding>"` before this result's branch merges. The locate-owner decision there folds into this CLI's design.

## References

- brief (input, kind=brief): docs/notes/2026-10-20-session-store-reach-brief.md — context and questions for this work
