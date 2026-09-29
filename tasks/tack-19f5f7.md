---
id: tack-19f5f7
title: "Instruct agents to record review: and concerns: notes for outcome measures"
status: doing
priority: 2
size: s
complexity: low
process: direct
owner: main
created: 2026-09-28T11:23:34Z
updated: 2026-09-29T20:14:04Z
started: 2026-09-29T20:14:04Z
depends: []
tags: [rules]
source: obs-00809f
agent: claude-code/claude-opus-5-5
---

Outcome: agents record the two note grammars that obs-00809f's outcome measures read (obs docs/specs/2026-09-28-outcome-measures-design.md §4):
- review: <spec|plan|impl> round <n> — verdict: <revise|accept>; findings: <label> <count>, … | none; reviewer: <harness/model | human> — written by the author agent on the task when a review of its artifact arrives, before acting on it; a short acceptance is still a round.
- concerns: <task-id> <defect|change|extension> — <one line> — written on a follow-up task at filing when it exists because of work closed as done.
Pieces: two short rules in the global AGENTS.md (and its mirrors), a cross-reference from the flow skill (the verified gate stays a disposition record, not a round), and examples of both grammars in agents/flow/gate-notes.md's corpus. Verification: the rendered instruction files carry both rules; the corpus examples parse against the spec's grammar.

## Notes

- 2026-09-29T20:14:04Z (main): started
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
