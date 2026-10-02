# Randomized flow trial

Status: draft revision 1, for review. Task: `tack-7d9375`.
Inputs: the outcome measures of obs-00809f; the report fields of obs-0491f1 (`--until`,
`--cohort`, `--units`, the E2 gate); the case shape and the historical flow case of
`tack-026612` (`docs/specs/2026-10-01-workflow-outcome-eval-design.md`, whose §6 names
randomized arms as the stronger evidence and asks for them as a separate case).

## 1. Purpose

The historical case compares tasks that flow carried with tasks it did not. Flow was
chosen for work its owner judged to need gates, so any difference may come from that
choice rather than from flow. This spec assigns flow on or off at random, in projects
that opt in, so a comparison of the two arms estimates what flow itself does to defects
after close, with cost reported beside it.

One factor, one trial. The task's wider outcome (harness, model, effort and skill
variants) needs the arm to reach the harness before the session starts, which needs a
launcher or a cross-harness child. Neither exists. Flow is the one factor a running session
controls on its own, so it comes first. §9 lists what a later factor reuses.

## 2. Decisions taken in brainstorming

- **Factor:** flow on or off, applied by the session that starts the task (user,
  2026-10-02).
- **Eligibility:** projects that opt in; scoped work at its first start (user,
  2026-10-02).
- **Mechanism (this spec):** the arm is a pure function of the trial and the task id,
  so it exists for every eligible task whether or not anyone looked it up. The session
  looks it up with one tool after `tasks start`. Rejected alternatives: drawing in the
  `tasks start` command, which would couple the tracker to experiments and add a piece
  in another project, and a hook on `tasks start`, which would need one adapter per
  harness. Both would raise compliance. Neither is needed for an unbiased comparison,
  because the analysis is by assigned arm (§6) and compliance is measured.

## 3. The trial file

`agents/evals/trials/flow-trial-1.md`, one file per trial:

```yaml
id: flow-trial-1
factor: flow
arms: [on, off]
projects: [tack, obs]
enroll: 2026-10-05..2026-11-01
read_on: 2026-12-31
source: [tack-7d9375]
```

- `projects` is the opt-in. The first list is `tack` and `obs`, the two projects that
  already use flow. Each one's AGENTS.md also carries the session rule (§4), so a
  project joins by adding both and leaves by removing both.
- `enroll` is a closed range of whole UTC days. A task enrolls when its first `started`
  lifecycle note falls inside it. Enrollment is fixed by date, not by a running count,
  so the trial holds no state. At about 100 first starts a week across tack and obs
  (217 in the 15 days to 2026-10-02), four weeks gives about 400 starts, 200 per arm.
- `read_on` is the one date the verdict is read (§6). Early runs return
  `insufficient: before read date`, and the tool computes nothing from them. It is set
  so that a task closing up to four weeks after enrollment ends still has its full
  30-day defect window.
- The file is frozen once enrollment opens. A change to it after that date is a new
  trial with a new id. The body records the rules below, the stop events (§7) and the
  verdict lines.

## 4. Assignment and the session rule

**Arm.** `arm = "on" if sha256("<trial id>:<task id>")[0] & 1 else "off"`, over the
canonical id (prefix and hex, no trailing period). It is balanced in expectation and
cannot be redrawn. Before the start, nobody can predict a task's arm without running
the function, and no one files tasks with that in mind.

**Eligibility.** Two conditions, the same in `trial-arm` and in the verdict: the task's
prefix is in `projects`, and its first `started` note is inside `enroll`. A task that was
first started before the trial and is resumed during it is not enrolled. The verdict
sees only obs's rows, so status and children cannot be conditions. An idea started for
scoping is enrolled at that start, and its arm holds through implementation. Goals are
not started in practice (the tasks skill never picks one). If one is started anyway, it
enrolls like any other task.

**`agents/bin/trial-arm <task-id>`** finds the active trials, checks eligibility from
`tasks show`, and prints one line:

- `flow-trial-1: flow on`, or `flow-trial-1: flow off`, or
- `not enrolled: <reason>` (`no trial for <prefix>`, `first start <date> outside
  enroll`, `not started`).

On the first lookup for an enrolled task it writes the note
`arm: flow-trial-1 — flow on|off` and does nothing on later lookups. It exits 0 for
both outcomes, 1 when the task is missing, and 2 when trial files overlap on a project.
`trial-arm status flow-trial-1` lists the enrolled tasks, each with its arm, and whether
`flow-state` shows flow gates on it, plus the compliance so far. This is not an outcome,
so reading it is not a peek. It exits 2 when an `arm:` note disagrees with the
function.

**The rule in each opted-in project's AGENTS.md:**

> Flow trial: after `tasks start`, run `~/.agents/bin/trial-arm <id>` and follow it.
> `flow on` runs the task under the flow skill; `flow off` runs it without flow, whatever
> else would choose it. The task's `process` is unchanged in both arms.

**Overrides.** The user may override an arm, for example by asking for a task to run
under flow. The session then writes `arm: flow-trial-1 — override: <why>` and does what
the user asked. The task stays in its assigned arm for the analysis and counts as
non-compliant. An agent never overrides on its own judgment.

## 5. Compliance

A task complies when its assigned arm matches whether flow carried it. Two readers
judge that, each from its own evidence: the verdict reads obs's `skill:flow` credit on
the task's unit (credited `true` means flow ran); `trial-arm status` reads `flow-state`
(any `gate:` note means flow ran), so compliance can be watched during enrollment without
obs. Units whose `skill:flow` state is unknown or several count as non-compliant.
Compliance is reported per arm. The `arm:` note is a convenience for people and for
`status`. The verdict never reads notes: it recomputes every arm from the function.

## 6. The verdict

A new case, `agents/evals/cases/flow-trial-1-defects.md`, in the existing shape:

```yaml
id: flow-trial-1-defects
title: Effect of flow on defects after close, by randomized arm
subject:
  kind: flow
  name: flow skill (agents/skills/flow/SKILL.md), trial flow-trial-1
  version: [trial flow-trial-1, enroll 2026-10-05..2026-11-01]
inputs:
  - kind: query
    ref: obs --json outcomes report --since 2026-10-05 --until 2026-12-31 --cohort --units
expected:
  type: choice
  claim: the intention-to-treat M4 comparison of flow on against flow off, read by the rule in docs/specs/2026-10-02-flow-trial-design.md §6
  choices: [flow-fewer-defects, no-difference-detected, flow-more-defects, insufficient]
  value: no-difference-detected
judge:
  kind: check
  command: obs --json outcomes report --since 2026-10-05 --until 2026-12-31 --cohort --units | agents/bin/trial-verdict agents/evals/trials/flow-trial-1.md
  cwd: tack checkout
source: [tack-7d9375, obs-00809f]
evidence: inferred
```

`expected` is the null hypothesis, stated before the data. It is not a hope. Either
direction is a finding.

**`agents/bin/trial-verdict <trial file>`** reads the report on stdin. Under `--cohort`
the report keeps units whose first start and first eligible close both fall between
`--since` and `--until`, so the tool keeps those whose prefix is in `projects` and whose
first start is inside `enroll`, then:

1. `insufficient: before read date` when the run date (`--as-of <date>`, default
   today in UTC) is earlier than `read_on`, and nothing else is computed.
2. `insufficient: unvalidated` while the report lists `m4` as `E2` (the same gate as the
   historical case).
3. Assign each unit its arm by the function. A unit is defective when its `defects` count
   is at least 1. The 2×2 table is arm by defective, over every enrolled, closed unit,
   whatever flow actually did (intention to treat).
4. `insufficient: too few` when either arm has fewer than 100 closed units, or fewer
   than 5 defective units in total.
5. `insufficient: compliance` when compliance in either arm is below 0.8. At that level
   the assigned arm no longer stands for the treatment.
6. Otherwise, run Fisher's exact test, two-sided, at α = 0.1. Report
   `flow-fewer-defects` or `flow-more-defects` by the direction of the difference when
   p < 0.1, and `no-difference-detected` otherwise.

The output follows the historical tool: the choice on the first line; then the counts
(`on <d>/<n>, off <d>/<n>, p <value>, risk difference <value> [90% Newcombe interval]`); then the
conditions. The conditions show compliance per arm, enrolled tasks that had not closed
by `--until` (per arm, since a difference in closing rates is itself a result), drops
per arm, median `output_tokens` per arm, and change requests and reopens per arm. These
are shown and never scored. There is no stratification: randomization balances strata
in expectation. The per-stratum counts are printed so an imbalance can be seen.

**One read.** The rule is applied once, on or after `read_on`. Later runs reproduce
it. A rerun after that date that gives a different choice (because obs rejudged links)
appends a line and says why. The first line stays.

**Storage.** As in the historical case's §7: until obs-abfcf9 lands, each run appends a
line to the case body's `## Verdicts` section, and `observed` holds the latest choice.

## 7. Stopping

The trial ends when enrollment closes. There is no early stop for efficacy: the data
gated by E2 are not read before `read_on`. A trial can be halted early for one of these
reasons only, none of them read from outcomes:

- the user halts it;
- `trial-arm status` shows compliance below 0.8 in either arm after 40 enrolled tasks;
- flow changes during enrollment in a way the trial file's body names as material, for
  example new gates. Edits to wording do not halt it.

To halt, set `enroll`'s end to the halt date (the one edit allowed after opening) and
write a dated line in the body giving the reason. The verdict then reads what enrolled,
usually as `insufficient: too few`.

## 8. Pieces

1. **tack: `agents/bin/trial-arm`**, with tests over fixture task records: enrolled on
   and off, each reason for not enrolling, idempotent note writing, overlapping trials
   (exits 2), a status listing with compliance, and an `arm:` note that contradicts the
   function (status exits 2).
2. **tack: `agents/bin/trial-verdict`**, with tests over fixture reports: one per branch
   of §6 (before read date, unvalidated, too few, compliance, more, fewer, no
   difference), plus a unit outside `enroll` or outside `projects` (ignored), and
   duplicate task rows (exits 2).
3. **tack: the trial file, the case file, and the AGENTS.md rule in tack.** The case
   file's first run is before `read_on` and prints `insufficient: before read date`.
   That checks the pipeline end to end.
4. **obs: the same rule in its AGENTS.md.** A one-line task filed from here in obs, so
   that obs's own checkout owns the change.

Pieces 1 to 3 do not depend on obs-0491f1. Only the verdict's live run does. Enrollment
can open before that obs work lands, because arms exist from the function alone.

Out of scope: randomizing harness, model or effort; the blind two-arm comparison on
small tasks (filed as an idea under the task's goal); changes to the historical case.
Enrolled tasks remain in its cohort. During enrollment, that cohort's flow and no-flow
groups become partly randomized, which only reduces its selection effect.

## 9. Reuse by a later factor

A trial file with another `factor` and its own `arms`, the same arm function, and the
same verdict tool with the factor's credit field in place of `skill:flow`. The new part
for harness, model or effort is how the arm reaches the session before it starts (a
launcher, or a child dispatched with the arm). That is a separate design.

## 10. Verification

- The tests of pieces 1 and 2 pass.
- `trial-arm` on a live tack task started inside `enroll` prints an arm and writes one
  note. On a task first started before `enroll` it prints `not enrolled`.
- The case runs end to end against the live obs index once obs-0491f1 lands, and prints
  `insufficient: before read date`.
