# Randomized flow trial

Status: draft revision 2, for review (round 1 findings in §11). Task: `tack-7d9375`.
Inputs: the outcome measures of obs-00809f; the report fields of obs-0491f1 (`--until`,
`--cohort`, `--units`, the E2 gate); the case shape and the historical flow case of
`tack-026612` (`docs/specs/2026-10-01-workflow-outcome-eval-design.md`, whose §6 names
randomized arms as the stronger evidence and asks for them as a separate case); the
flow skill's parent and child contract (`agents/skills/flow/SKILL.md`, "Planned parent
and children").

## 1. Purpose

The historical case compares tasks that flow carried with tasks it did not. Flow was
chosen for work its owner judged to need gates, so any difference may come from that
choice rather than from flow. This spec assigns flow on or off at random to work items
in projects that opt in. Comparing the two arms over every enrolled work item then
estimates what flow itself does to delivery and to defects after close, with cost
reported beside it.

One factor, one trial. The task's wider outcome (harness, model, effort and skill
variants) needs the arm to reach the harness before the session starts, which needs a
launcher or a cross-harness child. Neither exists. Flow is the one factor a running
session controls on its own, so it comes first. §9 lists what a later factor reuses.

## 2. Decisions taken in brainstorming

- **Factor:** flow on or off, applied by the session that starts the work (user,
  2026-10-02).
- **Eligibility:** projects that opt in; work at its first start (user, 2026-10-02).
- **Mechanism (this spec):** the arm is a pure function of the trial and the work item's
  id. The session looks it up with one tool after `tasks start`. Rejected alternatives:
  drawing in the `tasks start` command, which would couple the tracker to experiments and
  add a piece in another project, and a hook on `tasks start`, which would need one
  adapter per harness. Both would raise compliance. Neither is needed for an unbiased
  comparison, because the analysis is by assigned arm over every enrolled unit (§6) and
  compliance is measured (§5).

## 3. The trial file

`agents/evals/trials/flow-trial-1.md`, one file per trial:

```yaml
id: flow-trial-1
factor: flow
arms: [on, off]
projects: [tack, obs]
enroll: 2026-10-05..2026-11-29
close_by: 2027-01-10
follow_up_to: 2027-02-09
read_on: 2027-02-16
source: [tack-7d9375]
```

All dates are whole UTC days, inclusive.

- `projects` is the opt-in. The first list is `tack` and `obs`, the two projects that
  already use flow. Each one's AGENTS.md also carries the session rule (§4), so a
  project joins by adding both and leaves by removing both.
- `enroll`: a unit (§4) enrolls when its earliest first start falls inside this range.
  Enrollment is fixed by date, not by a running count, so the trial holds no state.
  The range is eight weeks because units are work items, not tasks: the 217 first starts
  in tack and obs over the 15 days to 2026-10-02 fell into 64 units, about 30 a week.
  Eight weeks gives about 240 units, 120 per arm.
- `close_by`: six weeks after enrollment ends. A unit's outcome counts only a close on
  or before this day. A unit still open on it, or one closed later, did not deliver
  (§6).
- `follow_up_to`: `close_by` plus 30 days. Every task closed by `close_by` has its whole
  30-day defect window by this day, so the analysis has no incomplete windows.
- `read_on`: `follow_up_to` plus seven days, so follow-ups filed on the last day of a
  window are indexed. Earlier runs print `insufficient: before read date`, and the
  tool computes nothing from them.
- The file is frozen once enrollment opens. A change after that is a new trial with a
  new id. The one exception is a halt (§7). The body records the rules below, the stop
  events and the verdict lines.

## 4. The unit, assignment and the session rule

**The unit is the work item, not the task.** Flow runs each child of a planned parent
under the parent's flow, in the parent's worktree, and the parent can verify only after
every child closes. An `on` parent with an `off` child cannot satisfy both. A task's
unit is found by climbing its `parent` chain within its own project while the parent
has `process` set. The last task reached is the unit's root. Umbrella goals (no
`process`) stop the climb, so independent pieces under one goal stay separate units. A
planned task and the step children of its plan share one unit. A task with no parent
is its own unit.

**Arm.** `arm = "on" if sha256("<trial id>:<unit root id>")[0] & 1 else "off"`, over
the canonical id. Every task in a unit has the unit's arm. Nobody can predict a unit's
arm before the work starts without running the function, and no one files tasks with
that in mind.

**Enrollment.** A unit enrolls when its root's prefix is in `projects` and the earliest
first `started` note among its tasks falls inside `enroll`. A unit any of whose tasks
started before `enroll` is not enrolled; its later children are not enrolled either. A
child started after `enroll` ends belongs to its unit and takes the unit's arm. An idea
started for scoping enrolls at that start, and the arm holds through implementation.

**Frozen membership.** The tree can change after enrollment. The first lookup on each
task writes the note `arm: flow-trial-1 — unit <root id> — flow on|off`, and that
recorded unit stands for the task from then on. A task that never had a lookup belongs
to the unit computed from the tree when the census runs. Where a later reparenting
makes the recorded and computed units disagree, the census lists the task and keeps the
recorded unit.

**`agents/bin/trial-arm <task-id>`** finds the active trials, resolves the unit from
`tasks show`, and prints one line:

- `flow-trial-1: flow on (unit <root id>)`, or the same with `flow off`, or
- `not enrolled: <reason>` (`no trial for <prefix>`, `unit <root id> first started
  <date>, outside enroll`, `not started`).

On the first lookup for a task in an enrolled unit it writes the `arm:` note, and later
lookups write nothing. It exits 0 for both outcomes, 1 when the task is missing, and 2
when trial files overlap on a project or when a task's recorded arm disagrees with the
function.

**The rule in each opted-in project's AGENTS.md:**

> Flow trial: after `tasks start`, run `~/.agents/bin/trial-arm <id>` and follow it.
> `flow on` runs the task under the flow skill; `flow off` runs it without flow, whatever
> else would choose it. Every task in a unit has the unit's arm. The task's `process` is
> unchanged in both arms.

**Overrides.** The user may override an arm, for example by asking for a unit to run
under flow. The session then writes `arm: flow-trial-1 — override: <why>` on the task it
is working and does what the user asked. The unit stays in its assigned arm for the
analysis and counts as non-compliant. An agent never overrides on its own judgment.

## 5. Treatment evidence and compliance

**Evidence that flow carried a unit** is task-specific and read from the unit's own
records. A unit was treated when any of its tasks carries a `gate:` note for a state
past `scoped` (`designed`, `planned`, `implementing`, `verified` or `closed`). `gate:
scoped` does not count, because flow writes it on children when it files them. Session
skill credit does not count either, because obs credits a flow load to every later
task in the same session. obs's `skill:flow` factor is printed beside the verdict as a
cross-check and never decides compliance.

**When compliance can be assessed.** A unit is assessable once its root has closed
`done`. Before that point, an `on` unit can be treated without having reached a gate
past `scoped` yet. A unit that is dropped, shelved or still open on `close_by` is
unassessable and is counted separately by arm. An `on` unit complies when it was
treated. An `off` unit complies when it was not. Compliance per arm is the share of its
assessable units that comply.

**Readers.** `trial-arm status flow-trial-1` lists the enrolled units with their arm,
state and treatment evidence, and gives compliance so far. Compliance is not an outcome,
so reading it during enrollment is not a peek. The census (§6) applies the same rule as
of `close_by`.

## 6. The verdict

### Inputs

1. **The census**, from `agents/bin/trial-arm census flow-trial-1`. It is built from the
   task records of the trial's projects, not from obs, because obs's units hold only
   tasks with an eligible close. The census is JSON with one entry per enrolled unit:
   root, arm, enrolled-at, and the unit's state on `close_by` (`done`, `dropped`,
   `shelved`, `open`). Each unit carries its members: task, first start, close kind
   and date, the gate states past `scoped`, and any override. The census also lists
   membership conflicts (§4). State on `close_by` reads the lifecycle notes' timestamps,
   so a close after `close_by` makes the unit `open`.
2. **The obs report**: `obs --json outcomes report --since 2026-10-05 --until 2027-01-10
   --cohort --units`, run on or after `read_on`. Every task in it closed by `close_by`,
   and its 30-day window ended by `follow_up_to`, so every window is complete.

### Outcome

The **primary outcome** is defined for every enrolled unit, with no unit excluded:
**delivered clean**. The unit's root closed `done` by `close_by`, and none of its member
tasks has a defect (`defects` ≥ 1 in obs's unit row) in its 30-day window. A unit that
was dropped, shelved, still open on `close_by`, or delivered with a defect has not
delivered clean. The question the primary outcome answers is whether flow changes the
chance that a work item is delivered within six weeks of enrollment closing and holds
up for 30 days after. Its limit is stated with every verdict: a unit that flow's gates
stop on purpose counts against flow.

**Missing defect data.** A member task closed `done` by `close_by` with no row in the
obs report has an unknown defect state, and so does its unit. When unknown units are at
most 5% of done units, the primary analysis counts them as clean, and a sensitivity line
counts them as defective. Both lines are printed. Above 5% the verdict is
`insufficient: missing defect data`.

**Secondary outcomes**, printed and never scored:

- by arm over all enrolled units: delivered (done by `close_by`); delivered with a
  defect; dropped; shelved; open;
- among delivered units only, labeled as a comparison conditional on delivery and not a
  causal estimate: the defect rate, change requests, extensions and reopens;
- the median `output_tokens` per delivered unit, summed over members;
- the per-stratum counts of unit roots (project, size, complexity, process), so an
  imbalance can be seen. There is no stratification, because randomization balances
  strata in expectation.

### The case

`agents/evals/cases/flow-trial-1-delivery.md`, in the existing shape:

```yaml
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
judge:
  kind: check
  command: agents/bin/trial-arm census flow-trial-1 > <tmp> && obs --json outcomes report --since 2026-10-05 --until 2027-01-10 --cohort --units | agents/bin/trial-verdict agents/evals/trials/flow-trial-1.md --census <tmp>
  cwd: tack checkout
source: [tack-7d9375, obs-00809f]
evidence: inferred
```

`expected` is the null hypothesis, stated before the data. It is not a hope. Either
direction is a finding.

### The rule

`agents/bin/trial-verdict <trial file> --census <file> [--as-of <date>]` reads the report
on stdin and stops at the first step that applies:

1. `insufficient: before read date` when the run date (`--as-of`, default today in UTC)
   is earlier than `read_on`. Nothing else is computed.
2. Exit 2 when the inputs disagree: a census member's first start or first close
   (to the UTC day) differs from its obs row, or a task appears twice in either input.
   obs rows for tasks in no census unit are ignored: they belong to other projects or
   to units first started before `enroll`.
3. `insufficient: unvalidated` while the report lists `m4` as `E2` (the historical
   case's gate).
4. `insufficient: missing defect data` above the 5% bound.
5. `insufficient: too few` when either arm has fewer than 100 enrolled units.
6. `insufficient: compliance` when compliance in either arm is below 0.8, or when either
   arm has fewer than 30 assessable units.
7. Otherwise, run Fisher's exact test on arm by delivered clean, two-sided, at α = 0.1.
   When p < 0.1, the answer is `flow-better` or `flow-worse` by the direction. Otherwise
   it is `no-difference-detected`.

The output follows the historical tool. The first line is the choice. The second gives
the counts: `on <clean>/<enrolled>, off <clean>/<enrolled>, p <value>, risk difference
<value> [90% Newcombe interval]`. Then come the sensitivity line, compliance per arm
with its unassessable counts, the secondary outcomes, and the outcome's stated limit.

**One read.** The rule is applied on or after `read_on`. Later runs reproduce it. A
rerun that gives a different choice (because obs rejudged links) appends a line and
says why. The first line stays.

**Storage.** As in the historical case's §7: until obs-abfcf9 lands, each run appends a
line to the case body's `## Verdicts` section, and `observed` holds the latest choice.

## 7. Stopping

The trial ends when enrollment closes. There is no early stop for efficacy, and no
outcome is read before `read_on`. A trial can be halted early for one of these reasons
only, none of them read from outcomes:

- the user halts it;
- `trial-arm status` shows compliance below 0.8 in either arm once each arm has 15
  assessable units;
- flow changes during enrollment in a way the trial file's body names as material, for
  example new gates. Edits to wording do not halt it.

To halt, set `enroll`'s end to the halt date and move `close_by`, `follow_up_to` and
`read_on` by the same offsets (the one edit allowed after opening). Then write a dated
line in the body giving the reason. The verdict reads what enrolled, usually as
`insufficient: too few`.

## 8. Pieces

1. **tack: `agents/bin/trial-arm`** (lookup, `status`, `census`), with tests over fixture
   task records:
   - unit resolution: a standalone task; a planned parent with step children (one unit,
     one arm); a child under an umbrella goal (its own unit); the climb never crossing
     projects;
   - enrollment: inside the window; a unit with a pre-window start (not enrolled, and its
     later children not either); a child started after `enroll` ends (enrolled, with the
     unit's arm);
   - notes: idempotent `arm:` writing; a reparented task keeping its recorded unit, with
     the conflict listed by the census; a recorded arm that contradicts the function
     (exits 2);
   - compliance: `gate: scoped` alone is untreated; `gate: implementing` on any member is
     treated; a dropped unit is unassessable;
   - census: state on `close_by` from lifecycle timestamps (a close the day after counts
     as `open`).
2. **tack: `agents/bin/trial-verdict`**, with tests over fixture censuses and reports:
   one per step of §6's rule; a census unit with no obs rows that is `dropped`
   (`not delivered`, not missing); missing defect data at 5% and above it; a unit
   with a defect in a child but not in its root (not clean); the sensitivity line.
3. **tack: the trial file, the case file, and the AGENTS.md rule in tack.** The case
   file's first run is before `read_on` and prints `insufficient: before read date`.
   That checks the pipeline end to end.
4. **obs: the same rule in its AGENTS.md.** A one-line task filed from here in obs, so
   that obs's own checkout owns the change.

Pieces 1 to 3 do not depend on obs-0491f1. Only the verdict's live run does. Enrollment
can open before that obs work lands, because arms come from the function and the census
from the task records.

Out of scope: randomizing harness, model or effort; the blind two-arm comparison on
small tasks (filed as an idea under the task's goal); changes to the historical case.
Enrolled tasks remain in that case's cohort. During enrollment its flow and no-flow
groups become partly randomized, which only reduces its selection effect.

## 9. Reuse by a later factor

A later trial needs a trial file with another `factor` and its own `arms`, plus the
same unit, arm function, census and outcome. Its treatment evidence is the one new rule
(§5's counterpart for that factor). The other new part, for harness, model or effort,
is how the arm reaches the session before it starts: a launcher, or a child dispatched
with the arm. That is a separate design.

## 10. Verification

- The tests of pieces 1 and 2 pass.
- `trial-arm` on a live tack task started inside `enroll` prints an arm and its unit,
  and writes one note. On a task in a unit first started before `enroll` it prints
  `not enrolled`.
- `trial-arm census flow-trial-1` runs against the live tack and obs records.
- The case runs end to end against the live obs index once obs-0491f1 lands, and prints
  `insufficient: before read date`.

## 11. Review round 1 (2026-10-02)

| Finding | Resolution |
| --- | --- |
| P1: analysis restricted to closed tasks breaks the causal claim | The primary outcome, delivered clean, is defined over every enrolled unit with a missing-data rule. Comparisons among delivered units only are secondary and labeled conditional (§6). |
| P1: a parent and its children could get incompatible arms | The unit is the work item: the climb through parents with `process` set. One arm per unit, membership frozen by the first note, analysis at the unit (§4). |
| P1: the read date did not guarantee complete windows | Separate `close_by`, `follow_up_to` (`close_by` plus 30 days) and `read_on` (§3). Every counted close has a complete window. |
| P2: the obs units could not supply open and dropped counts | A census of enrolled units from the task records is the verdict's second input, with a cross-check against obs (§6, piece 1). |
| P2: skill credit and any gate note did not establish treatment | Treatment means a gate past `scoped` on the unit's own tasks. Compliance can be assessed once the root closes `done`. Skill credit is only a printed cross-check (§5). |
