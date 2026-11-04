# Reliability plan revision 2 self-review

Type: report. Owner: hq-c58737 for hq-2dd09b. Status: self-review complete;
human plan review pending. Reviewer: codex/gpt-6.1-sol, verified in this turn by
`timeout 2 relay model --harness codex --pretty`.

Input: revision 2 of `docs/plans/2026-11-04-turn-pause-reliability.md`, frozen in
the same commit as this report. Authority: original design at `95773e6e` plus
the user-approved ended-prompt-guard addendum at `90740430`. The original plan
remains recoverable at `3c29183b`; both design files remain unedited.

Verdict: accept for human plan review. This is the author's self-review,
not an independent implementation review or authorization to execute revision 2.
No unresolved actionable plan findings or deferred minors.

## Coverage

| Binding requirement | Plan location |
| --- | --- |
| Safe protected readers, real metadata, grace, mutation/composition rejection | Completed Task 1 and Review Focus 1 |
| Cap60/warning45, budgets, strict boundary and frozen replay control | Completed Task 2 and Global Constraints |
| One atomic record, bounded transitions, privacy, migration and rollback | Completed Task 3 Steps1–7; continuation Steps8–12 extends the required field explicitly |
| Exact guard keys/digests, sorted unique rows, finite typed windows | Shared Contracts; Task 3 Steps8–10 malformed-input tests |
| Stripped text, UTF-8 SHA256, fresh containers, no hash import on normal path | Task 3 Interfaces, helper tests, Step11 hot-path check |
| End/idle capture is atomic; ended-state counters clear; guards survive restart | Task 4 Steps1/3/4/5 and existing root locks |
| Worker/injected rejection before matching; wake-window/cron precedence and consumption | Task 3 helper tests and Task 4 ended-prompt tests |
| Genuine resume clears guards and advances once; retention clears root identity | Shared Contracts recognition limit and Task 4 tests |
| Prompt fingerprints remain private and permit guesses | Global Constraints, Task 3 docs, Task 5 negative presentation tests |
| No fabricated turn or notification certainty; late notification race | Task 4 events/races, no-turn case and Review Focus 2 |
| Seven-day versus30-day retention,512 roots, bounded32 maintenance and lock rechecks | Task 4 Steps4/5 and Review Focus 4 |
| CLI read-only selection, coverage/unknowns, portable A–G handoff | Task 5 and Review Focus 5; obs consumer remains separate |
|50ms serial/concurrent p99, pilot first, no persistence/target substitution | Task 4 Step6; Task 5 must refresh evidence if its hot path changes |
| Reviewed inputs, native method, dependency order and separate activation | State, Setup, Human Gates; reuse the five existing children |

The step scan found no undefined cross-task helper or missing state field.
Task 3 produces `empty_guards`, `capture_guards` and `guarded_prompt_kind` in
existing prompt.py; Task 4 consumes those exact names. History/CLI consume only
public snapshots/events. RootRecord changes; RootState's active dictionary and
legacy rollback shape do not gain a private compatibility field.

Every new implementation segment has named RED tests, a protected focused
command and its expected result, GREEN/hygiene commands and a commit. Prior
steps are explicitly historical rather than replayed. Task 3's contract-focused
gate leaves the already-known Task 4 regression explicit; Task 4's full focused
gate must turn that regression green. No skipped test or suite becomes a pass.

The five Review Focus rows each map to owning-task tests, including the captured
unmarked wake, worker consumption ordering, reset/notification race, cleanup race
and private CLI projection. No separate review seat was dispatched for this
writing-plans self-review. The fresh whole-branch review is still required later.

The plan retains the original completed steps for recoverability and adds a
bounded continuation. Most additions specify interfaces, failure cases, gates
and ownership; they do not transcribe implementation bodies. An obvious command
typo, `python 3`, is corrected to `python3` in the measurement step.

## Rulings and limits

Ruling: reopen hq-cc91d4 after plan approval instead of adding an overlapping
sixth child or silently treating its original completion as the new contract.
Why: the schema/converter contract changes before branch integration, and the
repository explicitly reopens closed records for pre-integration corrections.
Cost: another focused Task 3 completion, preserving its prior BASE and history.
Revision: revision-2 Setup and Task 3 continuation.

Ruling: preserve the recorded zero-valued stored-limit behavior while retaining
positive configuration validation.
Why: the tree's existing zero-limit hook tests and Task 3 execution ruling
already establish that behavior; the earlier plan's blanket positive wording
was inaccurate for persisted records.
Cost: a zero-valued stored limit remains an immediate boundary rather than a
parse error. Revision: Shared Contracts and Task 3 Step11.

Ruling: clear an imported/uninitialized active record with no known turn without
fabricating a positive turn/event identity.
Why: legacy RootState permits turn=None and migration preserves it, while event
turns are positive. Ending that state must not manufacture an observed human turn.
Cost: no synthetic session_end event for that unobserved turn; CLI must disclose
the missing turn evidence. Revision: Task 4 no-turn test and Step4; Task 5 tests.

Ruling: follow the addendum's explicit guard clearing on a genuine nonmatching
resume and disclose the resulting recognition limit.
Why: retaining guards into active matching would change the approved design and
current engine/replay contract. Known pending schedules are protected while the
ended root retains their guards; after clearing, prior schedules are unknown
until native active-state evidence records them again.
Cost: a surviving unmarked scheduled prompt can look genuine after that loss of
evidence, as it can after root eviction. The plan makes no permanent-provenance
guarantee. Revision: Shared Contracts recognition limit and Task 4 Step3, following
the approved addendum's Recognition and resumption section.

Ruling: Task 3's continuation proves its schema/helper contract separately from
the already-recorded Task 4 integration regression.
Why: hook end/resume integration is Task 4's dependent deliverable, and the task
record already owns that failing test. The focused scope is named explicitly.
Cost: the controller must not misreport a contract GREEN as a passing branch;
Task 4 and final verification require the regression to pass. Revision: Task 3
Step11 and Task 4 Step5.

## Handoff

Human review of the newly frozen plan is the next gate. After approval, reopen
Task 3 for its continuation, then complete Tasks4–5 inline, latency measurement,
fresh whole-branch review and any required corrective re-reviews. Keep live
activation separate. The present change writes documentation/task records only;
runtime tests are not rerun for this document update, and the known regression
remains deliberately RED. Broad suites remain disabled by the checkout policy.
