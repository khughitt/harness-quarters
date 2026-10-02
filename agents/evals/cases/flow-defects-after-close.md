---
id: flow-defects-after-close
title: No defect regression among tasks the flow skill carried while one version was current
subject:
  kind: flow
  name: flow skill (agents/skills/flow/SKILL.md)
  version: [blob:9d90fb017099eb006f1e7d012f9aea5db944950a, cohort 2026-09-30..<run date>]
inputs:
  - kind: query
    ref: obs --json outcomes report --since 2026-09-30 --until <run date> --cohort --units
    window: 2026-09-30..<run date>
expected:
  type: choice
  claim: the stratified M4 comparison of skill:flow true against false, read by the rule in docs/specs/2026-10-01-workflow-outcome-eval-design.md §4
  choices: [no-regression-detected, regression, insufficient]
  value: no-regression-detected
observed:
  value: <choice: the first line of the run up to any colon>
  reason: <the text after "insufficient: ", or null>
  at: blob:9d90fb017099eb006f1e7d012f9aea5db944950a, cohort 2026-09-30..<run date>
judge:
  kind: check
  command: obs --json outcomes report --since 2026-09-30 --until <run date> --cohort --units | agents/bin/flow-outcome-verdict
  cwd: tack checkout
  pass: prints no-regression-detected
source: [tack-026612, obs-00809f]
evidence: inferred
---

The first case judged from obs's derived tables rather than a session. It looks
for a defect regression after close (M4) among tasks that the flow skill carried
and that both started and closed while one `SKILL.md` blob was committed, against
comparable tasks closed without flow, stratum by stratum. Cost, change requests,
extensions and reopens are printed beside the verdict and never enter it; so are
the defective tasks' ids, for inspecting an alarm.

A verdict is about a cohort, not an execution: loads before a task's first start
count, a session keeps content it loaded earlier, and the harness homes load the
skill from the main checkout's working tree, uncommitted edits included. The
comparison is historical: flow was chosen for work its owner judged to need gates,
so `no-regression-detected` says only that this cohort gave no evidence of more
defects with flow (p < 0.1, one-sided, exact within strata), and `regression`
does not establish cause. Randomized arms (tack-7d9375) are the stronger evidence.

Until obs validates its defect links (E2, Wilson lower bound ≥ 0.7 on defect
precision), every run returns `insufficient: unvalidated`, with provisional
tables. That run checks the pipeline, not flow.

The window starts at the first whole UTC day after `ba4395b` committed this blob
(2026-09-29T20:15:27Z); the partial day 2026-09-29 is cut.

## Verdicts

<one entry per run, newest last: the §7 line, then the tool's remaining lines indented>
