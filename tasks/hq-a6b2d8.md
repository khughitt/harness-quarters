---
id: hq-a6b2d8
title: Rerun flow-defects-after-close once its cohort has scored tasks
status: todo
priority: "3"
size: xs
complexity: low
process: direct
defer: 2026-10-31
created: 2026-10-02T12:10:55Z
updated: 2026-10-02T12:10:56Z
depends: []
tags: [flow]
source: tack-026612
agent: claude-code/claude-opus-5-5
---

The first run (2026-10-02) of agents/evals/cases/flow-defects-after-close.md had an empty cohort: obs scores a task only 30 days after its first eligible close (WINDOW_MS), so the 2026-09-30 cohort has no scored task before 2026-10-30. Rerun the judge command with --until the run date, cross-check strata against the filtered skill:flow x m4_defective rows (plan docs/plans/2026-10-01-workflow-outcome-eval.md Task 5 step 4), and append the verdict. If SKILL.md's blob changed, the window ends the day before the change. Also look at coverage.cohort_unknown_start (13 on 2026-10-02): tasks closed in the window with no known start are left out of the cohort.

## Notes

- 2026-10-02T12:10:55Z (flow-eval-run): concerns: tack-026612 extension — the first live run's cohort was empty by the 30-day rule; the first scoring run is due after 2026-10-30
