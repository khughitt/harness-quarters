---
id: flow-trial-1-delivery
title: Effect of flow on clean delivery of work items, by randomized arm
subject:
  kind: flow
  name: flow skill (agents/skills/flow/SKILL.md), trial flow-trial-1
  version: [trial flow-trial-1, enroll 2026-10-05..2026-11-29]
inputs:
  - kind: query
    ref: agents/bin/trial-arm census flow-trial-1
  - kind: query
    ref: obs --json outcomes report --since 2026-10-05 --until 2027-01-10 --cohort --units
expected:
  type: choice
  claim: the intention-to-treat comparison of delivered clean, flow on against flow off, over every enrolled unit, read by the rule in docs/specs/2026-10-02-flow-trial-design.md §6
  choices: [flow-better, no-difference-detected, flow-worse, insufficient]
  value: no-difference-detected
observed:
  value: <choice: the first line of the run up to any colon>
  reason: <the text after "insufficient: ", or null>
  at: trial flow-trial-1, enroll 2026-10-05..2026-11-29
judge:
  kind: check
  command: agents/bin/trial-arm census flow-trial-1 > <tmp> && obs --json outcomes report --since 2026-10-05 --until 2027-01-10 --cohort --units | agents/bin/trial-verdict agents/evals/trials/flow-trial-1.md --census <tmp>
  cwd: tack checkout
  pass: prints no-difference-detected
source: [tack-7d9375, obs-00809f]
evidence: inferred
---

The randomized counterpart of flow-defects-after-close. Work items in tack and obs
whose earliest start falls between 2026-10-05 and 2026-11-29 were assigned flow on or
off by a hash of their root id. The case compares, over every enrolled unit, the share
delivered clean: the root first closed `done` by 2027-01-10, and no member drew a
defect in the 30 days after its own first close. `expected` is the null hypothesis,
stated before any data. Either direction is a finding.

The rule is read once, on or after 2027-02-16. Earlier runs print
`insufficient: before read date` and compute nothing. Two limits travel with every
verdict: a unit that flow's gates stop on purpose counts against flow, and defects are
watched only after first closes.

## Verdicts

<one entry per run, newest last: `<run date> <choice>[: <reason>] — <counts line>`, then the tool's remaining lines indented>
