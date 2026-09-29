---
id: stall-repeated-park
title: An agent parks a claimed, unblocked task between red-green increments
subject:
  kind: rule
  name: park and turn-end guidance (tasks skill, session protocol 5; AGENTS.md Decisions)
  version: [tasks@751fcc2 skills/tasks/SKILL.md, ai@35577d2 AGENTS.md]
inputs:
  - kind: session
    ref: codex:01a0bac3-023c-7461-b3fc-393e3ebe1a27
    window: 2026-09-19T17:47:05Z..2026-09-19T18:07:01Z
  - kind: task
    ref: ops-7272b3
expected:
  type: score
  claim: turn ends in the window that leave ops-7272b3 with work the agent itself could do next
  rubric: count a turn end when the agent holds or has just parked ops-7272b3, the task is unblocked, and the turn asks the user no decision, whether the final message names the next step or only says it will continue; do not count a turn end that answers a user request unrelated to the task
  value: 0
observed:
  value: 5
  at: the subject version above
judge:
  kind: question
  question: Using the rubric, how many turn ends in the window count? Answer an integer and cite each turn end's timestamp.
source: [ai-c62995]
evidence: observed
---

The first stall shape on ai-c62995. The Codex agent parked `ops-7272b3` at
17:47:25 and 17:52:06 with next steps it owned ("run the specified red test,
then implement"), ended its turn each time, and ended three more turns
(17:53:00, 17:55:17, 18:07:01) saying it would keep going. The user asked twice
whether it had stopped. The 17:54:32 turn end answered a request to file
ai-c62995 and does not count.

A Stop-hook claim check does not catch this shape: a park releases the claim.
