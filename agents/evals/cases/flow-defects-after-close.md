---
id: flow-defects-after-close
title: No defect regression among tasks the flow skill carried while one version was current
subject:
  kind: flow
  name: flow skill (agents/skills/flow/SKILL.md)
  version: [blob:9d90fb017099eb006f1e7d012f9aea5db944950a, cohort 2026-09-30..2026-10-02]
inputs:
  - kind: query
    ref: obs --json outcomes report --since 2026-09-30 --until 2026-10-02 --cohort --units
    window: 2026-09-30..2026-10-02
expected:
  type: choice
  claim: the stratified M4 comparison of skill:flow true against false, read by the rule in docs/specs/2026-10-01-workflow-outcome-eval-design.md §4
  choices: [no-regression-detected, regression, insufficient]
  value: no-regression-detected
observed:
  value: insufficient
  reason: unvalidated
  at: blob:9d90fb017099eb006f1e7d012f9aea5db944950a, cohort 2026-09-30..2026-10-02
judge:
  kind: check
  command: obs --json outcomes report --since 2026-09-30 --until 2026-10-02 --cohort --units | agents/bin/flow-outcome-verdict
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

obs scores a task only once 30 days have passed since its first eligible close,
so no run before 2026-10-30 has a task to score: earlier runs check the empty
path and the gate. `obs` here is `python3 obs.py` in the obs checkout.

## Verdicts

2026-10-02 blob:9d90fb0 cohort 2026-09-30..2026-10-02 insufficient: unvalidated — flow 0/0, no flow 0/0, strata 0/0, p -, OR -
    provisional: M4 is unvalidated:E2; the counts and tables are the strata that would enter once it clears
    strata:
    flow x harness x model:
    after close (shown, not scored):
      flow true: changes 0, extensions 0, reopened 0 of 0
      flow false: changes 0, extensions 0, reopened 0 of 0
      defective tasks, flow true: none
      defective tasks, flow false: none
    coverage:
      excluded authorship: none
    cost (output_tokens):
      flow true: median -, total 0, missing 0
      flow false: median -, total 0, missing 0
    limitations:
      no exposure: how much the work was touched after close needs the task-to-commit join (obs-db1316); defects are counted per task without it
      cohort, not execution: pre-start skill loads count (obs credits a skill invoked at or before the task's end)
      cohort, not execution: a session keeps skill content it loaded earlier across later turns and resumptions
      cohort, not execution: harness homes load the skill from the main checkout's working tree, so uncommitted edits can run
      historical association: flow was chosen, not assigned; a verdict does not establish cause
