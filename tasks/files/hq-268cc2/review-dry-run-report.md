# Review prompt dry run

hq-268cc2, 2026-10-24. Recommendation: retain an editable, explicitly selected
review draft as the next launcher milestone; do not implement a production
`hq review <task-id>` command from this result. The saved experiment does not
identify 41 of its 44 reported cases. One recoverable historical target can be
reconstructed, while two saved mappings point to the wrong task. This is evidence
for preserving provenance and refusing guesses, not a measured success rate for a
production resolver.

## Inputs and recovery

The six retained inspection files and their manifest matched the checkpoint in
hq-2d8e81 before use. The manifest hash is
`ab51fa82c9fe8f162e8feec9d3276aa1cc804e9bb03893d4afa9568e837acbd1`.
The local collector reads session stores, but was only inspected: it was not run.
No sessions were collected, launched or changed.

`launcher-experiment.txt` contains aggregate counts and exactly three sample
mappings: task id, typed basename, linked spec and linked plan. It contains no
44-case inventory or resolver implementation. `first_prompts.py` is the collector,
not that resolver; the other five files do not supply the missing case inventory.
A current basename search cannot establish which tasks the original experiment
selected. Matching a total by tuning a new selector would not establish identity.

The dry-run script reads all 444 existing dataset rows and recovers each of those
three sample mappings to a unique review-opening session. The sample tuple is the
provenance of the reported mapping; its basename only locates the corresponding
existing request. The script does not use basename agreement as proof that the task
is correct. The other 41 positions stay unavailable without invented session ids.

The three current task snapshots were obtained with `tasks show <id> --json`.
Their spec/plan links agree with the three saved tuples. `tasks root <id> --pretty`
was also checked to confirm the registered repositories. These are current snapshots,
not historical task-state snapshots. The script rejects a task created after its
request and only considers revision evidence dated before the request's recorded
opening minute. Original opening timestamps have minute precision.

## Results

The categories are exclusive. “Matched” means a historical target and supporting
context were reconstructed; it does not mean a current review is ready to launch.
“Incomplete” means an identified case lacks required target context; “ambiguous”
means the reported mapping or revision conflicts; “unavailable” means the original
case identity cannot be recovered.

| Result | Of the reported 44 | Of the 3 recovered mappings |
| --- | ---: | ---: |
| Matched historical context | 1/44 | 1/3 |
| Incomplete | 0/44 | 0/3 |
| Ambiguous or misbound | 2/44 | 2/3 |
| Unavailable case identity | 41/44 | — |

These three were selected as differing examples by the original report. They are
not a representative sample. The remaining 41 are not counted as target-resolution
failures, and zero incomplete cases does not imply complete metadata elsewhere.

| Case | Existing session locator | Reported task | Explicit review kind | Finding |
| --- | --- | --- | --- | --- |
| C01 | 01a15373-04e4-7ce0-bdad-bc1fca36dbb4 | relay-fe38b1 | Spec | The request is in familiar and names its relay-consumer spec. The mapped task belongs to relay, links a different spec, and was created at 09:56:30Z after the request opened at 09:17Z on October 19. No prompt for that task is substituted. |
| C02 | 01a1690f-e053-70f1-9247-2f139b03a3cb | beliefs-f24fe9 | Implementation | The task id and repository agree. Two explicit merge notes, at 13:33:04Z and 13:33:07Z on October 23, bind the implementation to b923277 before the 14:02Z opening. The execution ledger supplies scope, rulings and deferred findings. |
| C03 | 01a16941-1e94-77e2-89b2-5c5d5b38a107 | hq-bb90ca | Spec | The request names the session-evidence-reader design at 14:54Z on October 23. The mapped fixture child was created at 16:11:45Z, links only the implementation plan, and cites the spec as implementation context. A later child's body cannot establish the intended review handoff. |

C02's frozen revision resolves to
`b92327703aafcb43eb88717545121b787543bf3c`. Its spec, implementation plan and execution
ledger all exist at that commit; their blob bytes were hashed in local evidence.
The helper itself does not check repository or artifact availability; the reported
matched result requires the separate frozen-commit and blob checks above.
The generated prompt selects implementation review explicitly, names that commit,
and reads those three context files through `git show`, including the ledger's
scope, rulings and deferred findings. This preserves the review's required meaning
without copying the long opening report verbatim or treating the ledger as the
implementation being reviewed. The spec/plan fields alone would select the wrong
review kind. No arbitrary latest SHA was used.

The task snapshot now includes a later implementation-review verdict. No active
review request or current worktree is established by these closed task records.
C02 therefore remains a historical reconstruction, with that limitation written in
the draft. C01 and C03 have blocked previews explaining the misbinding. All three
editable previews remain local; their location is in the task's retained-item note.
No work-home prompt text is included in this report.

## Checks and limits

The one throwaway script remains outside the repository. Four assert-based
self-checks cover an unambiguous implementation revision, absent revision evidence,
conflicting implementation revisions, and evidence written after the request.
The unambiguous case also contains an unrelated later spec SHA and checks that it
is not selected. The initial positive check failed before implementation; all four
checks subsequently caught their targeted breaks and passed on the intact script.

The real dry run consumed all 444 existing dataset rows and all three recovered
task snapshots. The matched commit and its three referenced files were checked
against the real repository. This tests no product command, live launch, UI, schema,
shared template, session index or prediction of conversation outcomes. Plan, brief,
fix, ledger-only, PR, pasted-report and out-of-tree hash review resolution were not
validated by the recoverable cases. A synthetic positive check is not an extra
observed case or a reason to increase the matched count.

## Concrete handoff gaps and ownership

- **Missing case provenance:** the prior launcher result retained totals but no
  per-case task/session mapping or resolution evidence. Preserve such an inventory
  with any later evaluation. This is an experiment-evidence gap owned by hq; it is
  not a tasks/flows schema requirement.
- **Target identity versus incidental references:** C01 crosses repositories and
  C03 selects a later child that merely cites the document. tasks should preserve
  the distinction between a review target and input/context references if a
  production consumer needs it. flows should emit the exact target owner and
  artifact at the review gate. A basename or body mention must remain a candidate.
- **Kind and revision binding:** C02's fields name a spec and plan although the
  request concerns implementation; its usable revision is an explicit merge note.
  flows should record the review kind together with the matching artifact or code
  revision at the gate. tasks is the proposed owner of exposing that binding to a
  consumer if existing refs/notes prove insufficient. This experiment does not
  establish that new fields are necessary.
- **Current versus historical review state:** closed records and old worktree notes
  do not establish an active handoff; C02 even has a later review verdict. flows
  should mark which request/round is current or superseded, with tasks exposing
  the corresponding record. Until then, an editable draft must name what is unknown
  and require an explicit selection rather than silently reusing historical state.

No new tasks/flows project or prerequisite schema is proposed. hq-2d8e81 owns the
next decision and the retained original inputs, script, snapshots and editable
previews. It should first decide whether the original case mapping can be recovered
from the owner, or whether a smaller, explicitly identified sample is sufficient
for a future editable-preview experiment. This task does not collect replacement
cases or infer which of the remaining 41 the original resolver selected.
