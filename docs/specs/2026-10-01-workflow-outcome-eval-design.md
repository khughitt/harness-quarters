# Workflow evaluation from post-implementation outcomes

Status: draft for review. Task: `tack-026612`. Inputs: obs-00809f's outcome measures
(obs `docs/specs/2026-09-28-outcome-measures-design.md`, revision 13, and its validation
report `docs/reports/2026-09-29-outcome-measures-validation.md`); the case shape of
`tack-99ea5d` (`agents/evals/cases/`); the intent of obs-abfcf9 (cases in projects,
verdicts in obs). Consumers: `tack-7d9375` (randomized arms), `tack-fc26cf`
(cross-family review).

## 1. Purpose

The five existing cases judge whether an agent did the right thing in a session. None
judges a workflow by what its work led to. This spec defines one case that does: it
rates the `flow` skill at a version by the defects filed against the tasks it carried
to close, beside the same measure for comparable tasks closed without it, with cost
shown alongside.

One case, not a framework. It is the first case whose input is obs's derived tables
rather than a session, and the place where the case shape and obs-abfcf9's verdict
record meet that kind of input.

## 2. What the measures support today

The task says to build only on measures obs-00809f shows are recorded reliably. Its
validation report settles which:

| Measure | State on 2026-10-01 | Used here |
| --- | --- | --- |
| M1–M3 review rounds and findings | E1 below target (precision 0.60); comparisons suppressed as `unvalidated:E1` until obs-c1b5ac | no |
| M4 defects within 30 days of an eligible close | E2 backfill precision 0.80; recorded `concerns:` notes from 2026-09-29; first complete windows 2026-10-17 to 10-29; no exposure term until obs-db1316 | **scored** |
| M5 change requests and extensions | same evidence as M4 | shown, not scored |
| M6 reopens | same window; 2 of 5 reopens were real rework | shown, not scored |
| M7 dispositions at verified gates | flow tasks only (7 of 18), so it cannot compare flow with no flow | no |
| cost (`output_tokens`, whole task) | `cost` view, scope `own`, stage `*` | shown, not scored |

M4 is therefore the only scored measure. Its owner is the task authorship (E0), whose
attribution was 9 of 10 correct on hand-check. When obs-c1b5ac re-validates E1, M1–M3
become a second case's input, not an edit to this one (§8).

## 3. The case

`agents/evals/cases/flow-defects-after-close.md`, in the existing shape:

```yaml
id: flow-defects-after-close
title: Tasks carried by the flow skill draw no more defects after close than comparable tasks without it
subject:
  kind: flow
  name: flow skill (agents/skills/flow/SKILL.md)
  version: [blob:<SKILL.md git blob>, window <from>..<to>]
inputs:
  - kind: query
    ref: obs outcomes report --since <from> --until <to>
    window: <from>..<to>
expected:
  type: choice
  claim: the M4 comparison of skill:flow true against false, read by the rule in §4
  choices: [not-worse, worse, insufficient]
  value: not-worse
observed:
  value: <choice>
  at: <subject version>
judge:
  kind: check
  command: obs outcomes report --since <from> --until <to> | agents/evals/bin/flow-outcome-verdict
  cwd: tack checkout
  pass: prints not-worse
source: [tack-026612, obs-00809f]
evidence: inferred
```

The body below the frontmatter carries what the frontmatter cannot: the conditions
(§5), the caveat (§6), and each run's verdict with its counts until obs-abfcf9 stores
verdicts (§7).

**Subject version.** No task or note records which flow version ran, and obs's
`skill_calls` has no version column. The version is the git blob hash of
`agents/skills/flow/SKILL.md` (today `9d90fb0`), and the window is the span during which
that blob was the committed file. A blob hash survives the 2026-09-29 history cut: a
pre-cut version is named by its blob from the private archive, and the same content
yields the same hash in both repositories. Versions whose window is shorter than the
data needs are pooled into one subject entry listing every blob, never silently merged.

**Window.** A task belongs to the version in force at its first eligible close, the
anchor obs already uses for task units (outcome spec §8). M4 counts a task only once its
30-day window is complete, so a version is first judgeable 30 days after its window
opens.

**`evidence: inferred`.** M4 rests on E0 authorship and, before 2026-09-29, on E2's
model-judged links; obs labels every comparison view `inferred`. The check judge is
deterministic over that data, which does not make the data observed.

## 4. Verdict rule

`agents/evals/bin/flow-outcome-verdict` reads the report's JSON on stdin and prints one
choice and the counts behind it. It reads only rows with `factor = "skill:flow"` and
`measure = "m4_defective"`:

- **insufficient** when no such comparison is shown (every one suppressed by obs's own
  rules: unassigned units over half a stratum, a value keeping under half its units
  attributed) or when every shown stratum has a cell under 5, where obs gives counts
  without rates.
- Otherwise, over the shown strata with both cells at 5 or more, pool defective and
  total per value (flow true, flow false), and compute each value's defect rate.
  **worse** when the flow rate exceeds the no-flow rate and a one-sided Fisher exact
  test on the pooled 2×2 table gives p < 0.1; **not-worse** otherwise.

The rule never invents a cell obs suppressed. It pools only within obs's strata, so
size, complexity, project, process and artifact stay held fixed per cell. A one-sided
test at 0.1 is loose on purpose: the question is a regression alarm on small counts,
and a false alarm costs a look at the tasks, which the report lists. M5, M6 and cost are
printed beside the verdict and never enter it.

## 5. Conditions kept visible

Every run prints, and the case body records:

- task difficulty: the strata (size, complexity, process, project) that reached the
  pooled table, and how many strata were suppressed or under 5;
- workflow: flow true and false counts per stratum;
- model and harness: obs's retained/total table for `harness` and `model` over the same
  window, so a flow cell that is mostly one model is visible as such;
- observation coverage: tasks with recorded `concerns:` notes, tasks covered only by E2
  backfill, tasks with authorship `incomplete`, `mixed`, `several` or `unknown`, and
  M4's missing exposure term (obs-db1316).

## 6. What a verdict means

The comparison is historical. Who chose flow, for which tasks, was not random: flow is
picked for work its owner judged to need gates. A `not-worse` says the flow skill at
that version was not associated with more defects among comparable tasks, and a
`worse` says it was; neither establishes that the skill caused the difference.
Randomized arms (`tack-7d9375`) are the stronger evidence and, when they exist, are a
separate case over the arm assignment, not a reweighting of this one.

## 7. Verdict storage until obs-abfcf9

obs-abfcf9 will store verdicts in obs with a case id, subject version, evidence pointer,
typed answer, judge identity and evidence class. Until it lands, each run appends one
line to the case body's `## Verdicts` section:

`<run date> <subject version> <window> <choice> — flow <d>/<n>, no flow <d>/<n>, strata <shown>/<total>, p <value>`

and `observed` holds the latest. This case adds two inputs to obs-abfcf9's design,
recorded there as a note: an input of kind `query` (derived tables, not a session or
fixture), and a subject version that is a blob plus a window rather than a commit.

## 8. Pieces

1. **obs: `--until` on `obs outcomes report`.** The report bounds its window only from
   below (`--since`). A version's window needs both ends. An obs task, filed from here,
   adds an upper bound with the same anchors as `--since`. Rejected alternative: per-task
   version attribution as a new factor value (`skill:flow@<blob>`). It is the better
   long-term shape for comparing many versions at once, but it needs a version column in
   obs's skill index and buys nothing for one case.
2. **tack: `agents/evals/bin/flow-outcome-verdict`** with its test, a fixture report in
   `agents/evals/fixtures/` covering each branch of §4 (all suppressed, under 5, not
   worse, worse).
3. **tack: the case file** with the current blob, its window, and a first run. Before
   2026-10-17 the first run is expected to print `insufficient`, and that run is the
   verification that the pipeline works end to end, not a finding about flow.
4. **obs-abfcf9: a note** carrying §7's two schema inputs.

Out of scope: M1–M3 (a second case once obs-c1b5ac re-validates E1); a runner for
cases (`just eval`, obs-abfcf9); any change to how flow is chosen.

## 9. Verification

- The verdict tool's tests pass on the fixtures, one per branch of §4.
- The case runs end to end against the live obs index through `--until`, and its
  printed counts match `obs outcomes report`'s own human-readable comparison for
  `skill:flow` over the same window.
- The case validates against the five existing cases' shape (same top-level keys), so
  obs-abfcf9's "the existing cases validate unchanged" bar extends to six.
