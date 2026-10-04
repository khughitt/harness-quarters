---
id: stall-subagent-background-wait
title: A subagent with its work in hand ends its turn to wait on a background check
subject:
  kind: rule
  name: subagent turn-end guidance (AGENTS.md Decisions; superpowers subagent-driven-development implementer brief)
  version: [ai@35577d2 AGENTS.md, superpowers before 6.3.0 (exact version not recorded)]
inputs:
  - kind: session
    ref: claude-code:20e55bde-4aed-4a6f-993d-b44b058f509f
    agent: agent-a171e3a2dba9ed0db
    window: 2026-09-20T14:07:03Z..2026-09-20T20:54:49Z
  - kind: task
    ref: ns-6c56fc
    role: the subagent's claimed step (started 2026-09-20T13:53:20Z under the controller's session)
  - kind: task
    ref: ops-88a0fa
    role: the controller's goal
expected:
  type: boolean
  claim: the subagent ended its turn while ns-6c56fc was claimed and unparked, its edits uncommitted, and a background check it had started still pending
  value: false
observed:
  value: true
  at: the subject version above
judge:
  kind: question
  question: In the window, does the subagent end a turn (its last assistant message before a gap of more than 10 minutes) while ns-6c56fc is claimed and not parked, its edits are uncommitted, and a background run or Monitor it started is still pending? Answer yes or no and cite the claim, the tool call that started the run, and the turn end.
source: [ai-c62995, ai-80b836]
evidence: observed
---

The second stall shape on ai-c62995. The subagent ("Implement Task 6: pilot",
sonnet) edited `pilot/cli.py`, started the conformance suite in the
background, armed a Monitor (`b5jr9ff8a`, 5-minute expiry), and at 14:07:46
ended its turn "waiting on the second conformance-test run". Nothing woke it;
the coordinator resumed it at 20:54:49. It repeated the shape at 20:57:21 when
a foreground run overran the Bash timeout.

The Stop-hook probe (ai-80b836) sees this shape through the claim, which the
subagent records under the controller's session: the controller's Stop is
refused, while the subagent's own Stop is blocked once and passes on retry.
