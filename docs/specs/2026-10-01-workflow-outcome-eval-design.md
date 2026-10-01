# Workflow evaluation from post-implementation outcomes

Status: draft for review, revision 3 (answers review rounds 1 and 2, §10). Task: `tack-026612`.
Inputs: obs-00809f's outcome measures (obs `docs/specs/2026-09-28-outcome-measures-design.md`,
revision 13, and its validation report `docs/reports/2026-09-29-outcome-measures-validation.md`);
the case shape of `tack-99ea5d` (`agents/evals/cases/`); the intent of obs-abfcf9 (cases
in projects, verdicts in obs). Consumers: `tack-7d9375` (randomized arms), `tack-fc26cf`
(cross-family review).

## 1. Purpose

The five existing cases judge whether an agent did the right thing in a session. None
judges a workflow by what its work led to. This spec defines one case that does: it
looks for a regression in defects after close among tasks carried by the `flow` skill
while one version of it was current, against comparable tasks closed without it, with
cost shown alongside.

One case, not a framework. It is the first case whose input is obs's derived tables
rather than a session, and the place where the case shape and obs-abfcf9's verdict
record meet that kind of input.

## 2. What the measures support today

The task says to build only on measures obs-00809f shows are recorded reliably. Its
validation report settles which:

| Measure | State on 2026-10-01 | Used here |
| --- | --- | --- |
| M1–M3 review rounds and findings | E1 below target (precision 0.60); comparisons suppressed as `unvalidated:E1` until obs-c1b5ac | no |
| M4 defects within 30 days of an eligible close | inferred `defect` links: precision 2/3, Wilson [0.21, 0.94]; the report says M4 "cannot yet be read from inferred links alone"; recorded `concerns:` notes only from 2026-09-29; first complete windows 2026-10-17 to 10-29; no exposure term until obs-db1316 | **scored, once gated (below)** |
| M5 change requests and extensions | same evidence as M4 | shown, not scored |
| M6 reopens | same window; 2 of 5 reopens were real rework | shown, not scored |
| M7 dispositions at verified gates | flow tasks only (7 of 18), so it cannot compare flow with no flow | no |
| cost (`output_tokens`, whole task) | `cost` view, scope `own`, stage `*` | shown, not scored |

**The defect-evidence gate.** A complete 30-day window does not make M4 readable; valid
defect links do. obs already gates M1–M3 this way: `UNVALIDATED` in
`outcome_report.py` suppresses a measure's comparisons until its evidence passes
validation. M4 joins that table as `m4_defective: "E2"` (piece 1, §8), and leaves it
when obs records a defect-link validation meeting a target obs owns: the report's
recommended `followup-rubric-v2` rejudge, hand-checked, with defect precision whose
Wilson lower bound is at least 0.7. Recorded `concerns:` notes do not bypass the gate:
their recall (an agent that files a fix without the note) is unmeasured, so a window
built only from recorded notes is gated the same way until obs measures that recall.
While the gate holds, every run of this case returns `insufficient` with reason
`unvalidated:E2`, and the pipeline still runs end to end.

M4's owner is the task authorship (E0), whose attribution was 9 of 10 correct on
hand-check. When obs-c1b5ac re-validates E1, M1–M3 become a second case's input, not an
edit to this one (§8).

## 3. The case

`agents/evals/cases/flow-defects-after-close.md`, in the existing shape:

```yaml
id: flow-defects-after-close
title: No defect regression among tasks the flow skill carried while one version was current
subject:
  kind: flow
  name: flow skill (agents/skills/flow/SKILL.md)
  version: [blob:<SKILL.md git blob>, cohort <from>..<to>]
inputs:
  - kind: query
    ref: obs outcomes report --since <from> --until <to> --cohort --units
    window: <from>..<to>
expected:
  type: choice
  claim: the stratified M4 comparison of skill:flow true against false, read by the rule in §4
  choices: [no-regression-detected, regression, insufficient]
  value: no-regression-detected
observed:
  value: <choice>
  at: <subject version>
judge:
  kind: check
  command: obs outcomes report --since <from> --until <to> --cohort --units | agents/evals/bin/flow-outcome-verdict
  cwd: tack checkout
  pass: prints no-regression-detected
source: [tack-026612, obs-00809f]
evidence: inferred
```

The body below the frontmatter carries what the frontmatter cannot: the conditions
(§5), the caveat (§6), and each run's verdict with its counts until obs-abfcf9 stores
verdicts (§7).

**Subject: a cohort, not an execution record.** No task or note records which flow
version ran, and obs's `skill_calls` has no version column. The subject is therefore a
cohort: the tasks whose first start *and* first eligible close both fall inside the
window during which one blob of `agents/skills/flow/SKILL.md` was the committed file.
Requiring the start inside the window removes tasks that began under an earlier
version; it does not guarantee which content the task's sessions loaded. Three gaps stay
open and are listed as limitations in every run:

- **pre-start loads:** obs credits a skill invoked at or before the task's end
  (`outcomes._factors_of`), so a load before the task's first start, possibly before
  the window, counts toward `skill:flow`;
- **held content:** a session that loaded the skill earlier keeps that content in its
  context across later turns and resumptions, whatever was committed since;
- **uncommitted edits:** the harness homes link the skill to the main checkout's
  working tree, so a session can load an edit that was never committed.

The verdict is labelled a cohort verdict, never "flow at blob X ran and produced …". If
obs later records the skill content each session loaded, version attribution per task
replaces the cohort (out of scope here).

**Window boundaries.** obs's `--since` and `--until` take calendar dates, inclusive,
anchored at midnight UTC, and blob transitions happen within a day. A cohort window is
therefore the whole UTC days contained in the blob's interval: `from` is the first UTC
day starting at or after the commit that introduced the blob, and `to` is the last UTC
day ending at or before the commit that replaced it (today, for the current blob). A
blob whose interval contains no whole day has no cohort of its own and is pooled. The
days cut at each end are listed with the window. Rejected alternative: timestamp bounds,
which would widen obs's shared `when` value for every command to recover at most two
partial days per version.

The blob hash survives the 2026-09-29 history cut: a pre-cut version is named by its
blob from the private archive, and the same content yields the same hash in both
repositories (today's is `9d90fb0`). The no-flow arm of the cohort is the tasks
satisfying the same start-and-close condition that did not use the flow skill. Versions
whose windows are too short to fill a cohort are pooled into one subject entry that
lists every blob and the combined window, never silently merged.

**`evidence: inferred`.** M4 rests on E0 authorship and, before 2026-09-29, on E2's
model-judged links; obs labels every comparison view `inferred`. The check judge is
deterministic over that data, which does not make the data observed.

## 4. Verdict rule

`agents/evals/bin/flow-outcome-verdict` reads the report's JSON on stdin and prints one
choice, the reason, and the counts behind it. The cohort is applied once, in obs:
`--cohort` restricts the task units to those whose first start and first eligible close
both fall in the window *before* obs aggregates cells and decides suppression, so the
`unassigned` and `low_retention` decisions are taken over the cohort, not over the plain
close window. The `--units` rows are the same units. The tool reads the
`factor = "skill:flow"`, `measure = "m4_defective"` comparisons for obs's suppression
decisions and exact per-cell counts, recounts the cells from the task rows, and refuses
(exit 2) on any disagreement, since that means the two halves of the report describe
different units. It filters nothing itself.

1. **insufficient: unvalidated** when the comparisons carry `suppressed_reason`
   `unvalidated:E2` (§2's gate).
2. A stratum (obs's key: project, size, complexity, process, artifact) **enters** when
   obs shows its comparison (not suppressed for `unassigned` or `low_retention`) and both
   arms have at least one scored task in the cohort. Strata that do not enter are counted
   by reason in the output.
3. **insufficient: too few** when either arm has fewer than 10 scored tasks across the
   entering strata.
4. Otherwise, a one-sided **exact conditional test** of a common odds ratio of 1 across
   the entering strata: conditional on each stratum's margins, the flow arm's defective
   count in that stratum is hypergeometric; the test statistic is their sum, its null
   distribution the convolution of the per-stratum hypergeometrics, and p is the
   probability of a sum at least the observed. Each stratum is compared only with
   itself, so a flow arm better in every stratum can never be called a regression by a
   difference in stratum mix. **regression** when p < 0.1; **no-regression-detected**
   otherwise. The tool prints the Mantel–Haenszel common odds ratio beside p as the size
   of the difference.

`no-regression-detected` means only what it says: this cohort gave no evidence of more
defects with flow at the stated level. It is not evidence of equivalence, and the case
never states one. A one-sided test at 0.1 is loose on purpose: the question is a
regression alarm on small counts, and a false alarm costs a look at the tasks, which the
output lists. The convolution is exact and small (counts are tens), written in the
standard library, no statistics package. M5, M6 and cost are printed beside the verdict
and never enter it.

## 5. Conditions kept visible

Every run prints, over the **scored cohort** (the task rows that entered step 4, or
would have, for an `insufficient`), counting distinct tasks:

- task difficulty: per entering stratum, the flow and no-flow counts and defective
  counts; strata that did not enter, by reason;
- model and harness, jointly with flow: a flow × harness × model table of task counts,
  so a flow arm that is mostly one model is visible as such rather than inferred from
  marginals;
- observation coverage, per arm: tasks whose defect evidence is a recorded `concerns:`
  note, an inferred E2 link, or no link; tasks excluded for authorship `incomplete`,
  `mixed`, `several` or `unknown`; and M4's missing exposure term (obs-db1316);
- cost: per arm, median and total `output_tokens` beside the verdict.

The case body records the same tables at each run (§7).

## 6. What a verdict means

The comparison is historical. Who chose flow, for which tasks, was not random: flow is
picked for work its owner judged to need gates. A `regression` says flow tasks in this
cohort drew more defects than comparable tasks without it, beyond what stratum-matched
chance gives at p < 0.1; a `no-regression-detected` says the cohort did not show that.
Neither establishes that the skill caused anything. Randomized arms (`tack-7d9375`) are
the stronger evidence and, when they exist, are a separate case over the arm assignment,
not a reweighting of this one.

## 7. Verdict storage until obs-abfcf9

obs-abfcf9 will store verdicts in obs with a case id, subject version, evidence pointer,
typed answer, judge identity and evidence class. Until it lands, each run appends to the
case body's `## Verdicts` section one line,

`<run date> <blobs> cohort <from>..<to> <choice>[: <reason>] — flow <d>/<n>, no flow <d>/<n>, strata <entered>/<total>, p <value>, OR <value>`

followed by §5's tables, and `observed` holds the latest choice. This case adds three
inputs to obs-abfcf9's design, recorded there as a note: an input of kind `query`
(derived tables, not a session or fixture); a subject version that is a blob set plus a
cohort window rather than a commit; and an `insufficient` answer that carries a reason.

## 8. Pieces

1. **obs: what the report must expose** (one obs task, filed from here):
   - `--until` on `obs outcomes report`: the shared `when` value, inclusive through
     the end of that UTC day, on the same task anchor as `--since`;
   - `--cohort`: task units enter only when their first start and first eligible close
     both fall within `--since`..`--until`, applied before cell aggregation and
     suppression, and to `--units`;
   - `m4_defective: "E2"` in `UNVALIDATED`, and the defect-link validation that clears
     it, as §2 states (the rejudge itself is obs's work under its E2 recommendation;
     this task only adds the gate);
   - exact counts per comparison cell: `n` restricted to attributed, measured units (as
     today) and a new `sum` of the measure, so a binary measure's defective count is
     exact rather than recovered from a rounded mean; `total` stays as is and is not
     read as a denominator;
   - `--units`: task-level rows for the windowed task units (the cohort's under
     `--cohort`), each with task id, first
     start, first eligible close, stratum, credit state and values for each factor
     (harness, model, effort, `skill:*`), defect, change and extension counts with the
     evidence class of each link (recorded or inferred), reopens, and `output_tokens`.
   Rejected alternative: a per-task flow version as a factor value
   (`skill:flow@<blob>`). It would replace the cohort with execution evidence, but it
   needs the skill content each session loaded, which no harness records today.
2. **tack: `agents/evals/bin/flow-outcome-verdict`** with its tests over fixture reports
   in `agents/evals/fixtures/`, one per branch of §4 (unvalidated, too few, regression,
   no regression), plus the Simpson's-paradox case from review round 1 (flow better in
   each of two strata, worse pooled: must not be `regression`), and a count mismatch
   between task rows and comparison rows (must exit 2). The cohort's own boundary
   cases (a task started the day before `--since`; a stratum that passes retention over
   the close window and fails it over the cohort) are tests in the obs task, where the
   filter lives.
3. **tack: the case file** with the current blob, its window, and a first run. While
   the E2 gate holds, that run prints `insufficient: unvalidated`; it is the
   verification that the pipeline works end to end, not a finding about flow.
4. **obs-abfcf9: a note** carrying §7's three schema inputs.

Out of scope: M1–M3 (a second case once obs-c1b5ac re-validates E1); the E2 rejudge
(obs); a runner for cases (`just eval`, obs-abfcf9); per-session skill-content
recording; any change to how flow is chosen.

## 9. Verification

- The verdict tool's tests pass on every fixture in §8 piece 2.
- The case runs end to end against the live obs index with `--until`, `--cohort` and
  `--units`, and its per-cell counts match the comparison rows for `skill:flow` over
  the same cohort (the tool's own refusal check, exercised live).
- The case has the five existing cases' top-level keys, so obs-abfcf9's "the existing
  cases validate unchanged" bar extends to six.

## 10. Review record

- **Round 1** (codex, 2026-10-01): revise; P1 3, P2 3. Answered in revision 2:
  defect evidence gated on validated defect links, not on window completeness (§2);
  pooling replaced by an exact conditional test within obs's strata (§4); the passing
  answer renamed `no-regression-detected` and stated as no evidence of regression, not
  equivalence (§4, §6); the subject restated as a start-and-close cohort with the
  uncommitted-edit gap named (§3); exact per-cell sums and task-level rows added to the
  obs piece (§8); conditions computed jointly over distinct tasks in the scored cohort
  (§5).
- **Round 2** (codex, 2026-10-01): revise; P1 1, P2 2. Answered in revision 3: the
  cohort filter moved into obs (`--cohort`), applied before cell aggregation and
  suppression so obs's retention decisions and the tool's recount describe the same
  units (§4, §8); the guarantee about which content a task loaded removed, with
  pre-start loads, held content and uncommitted edits listed as limitations (§3);
  cohort windows set to whole UTC days inside each blob interval, timestamp bounds
  rejected (§3).
