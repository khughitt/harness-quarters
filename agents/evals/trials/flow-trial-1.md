---
id: flow-trial-1
factor: flow
arms: ["on", "off"]
projects: [tack, obs]
enroll: 2026-10-05..2026-11-29
close_by: 2027-01-10
follow_up_to: 2027-02-09
read_on: 2027-02-16
source: [tack-7d9375]
---

Flow on or off, assigned at random to work items in tack and obs. The design is
docs/specs/2026-10-02-flow-trial-design.md; this file is frozen from 2026-10-05.

- Unit: a task's work item, found by climbing its parents while the parent has
  `process` set (§4). One arm per unit, `sha256("flow-trial-1:<root>")[0] & 1`.
- Sessions run `~/.agents/bin/trial-arm <id>` after `tasks start` and follow it (the
  global rule in AGENTS.md, "Trials").
- Watch compliance with `trial-arm status flow-trial-1`. Halt when compliance falls below
  0.8 in either arm once each arm has 15 assessable units (§7).
- Material changes to flow that halt the trial: a gate added, removed or renamed, or a
  change to who judges a gate. Wording edits do not.

## Stop events

<none: a halt writes a dated line here and moves enroll's end, close_by, follow_up_to
and read_on by the same offset>
