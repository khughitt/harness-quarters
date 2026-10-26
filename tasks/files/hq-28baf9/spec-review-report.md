Revise revision 6 before human review. I found two Important contract mismatches and one Minor coverage clarification. hq-28baf9 remains with the controller to correct the document and freeze a new revision; no implementation change is needed for these findings.

Reviewer: `codex/gpt-6.1-sol`, verified this turn by `timeout 2 relay model --harness codex --pretty`. Reviewer session: `01a177b0-3ff7-7c70-ba3e-a29aded078e0`.

Reviewed frozen hq commit `e8ff3707051c164a8fd522117c2e6096cd1426ea`, `docs/specs/2026-10-23-session-evidence-reader-design.md`, against base `4f32e64`. All spec line references below name that frozen revision. Implementation references name obs `062b73e`.

**Important findings**

1. **Task searches do not emit evidence files before mention-only files.** Spec §6.4, lines 590–591, promises that precedence. In `../obs/session_logs_query.py:549`, `_task_stream` sorts the combined `kept` list, including both evidence and mention-only files, by the selected file order.

   With an older stamped session and a newer mention-only session, `--task ID --mentions --sessions --limit 1` can emit only the mention. A caller following the promised order could mistake the first result for the strongest available evidence. An isolated check using the frozen sorting functions confirmed this ordering.

   Smallest correction: describe the combined files’ actual sort order and remove the evidence-first promise.

2. **The new `mismatch` definition promises protection that Claude lookups do not provide.** Spec §5.2, lines 400–402, says a native filename matching the requested id but disagreeing with recorded identity becomes `mismatch` and is never read as that session. That describes the tested Codex case, but the text applies to both harnesses.

   For Claude, `../obs/session_logs_place.py:311` takes the filename stem as identity, and `_relation` returns `own` before examining recorded `sessionId`. The normalizer retains a UUID filename’s identity when records disagree, marking it `file_name_unconfirmed` (`../obs/session_logs_records.py:500`). Thus a Claude transcript renamed to another session’s UUID remains an `own` candidate and is read under that filename identity. An isolated check confirmed this path.

   This matters when someone relies on the stated protection against misattributing a renamed transcript. Smallest correction: scope the shipped R19 guarantee to Codex and state Claude’s filename-authority limit and `file_name_unconfirmed` result. Changing Claude’s behavior would require separate implementation work.

**Minor finding**

3. **`turn_cut` can describe a view from which nothing was omitted.** Spec §7.2, lines 716–718, introduces `limits.hit` and `target.turn_cut` as the result of cutting the view. The implementation sets both when the item count exceeds the nominal cap, before adding every target-line object back (`../obs/session_logs_show.py:467`).

   A turn containing three objects on its target line with `--limit 1` returns all three, yet reports `limits.hit: true` and `{records: 3, shown: 3, before: 0, after: 0}`. An isolated check confirmed this; the Stage A ledger already records this edge as a deferred minor.

   No evidence is lost, but callers cannot treat `limits.hit` alone as proof of omission. Document that distinction, or explicitly retain the ledger’s caveat.

The eight requested subjects were checked against the ledger, retained results, and frozen code:

| Subject | Assessment |
|---|---|
| Native ordinal and 269/269 agreement | Accurate. The probe compares the ordinal with `own_start_line - 2`; all 269 offsets are zero. A1 appropriately retains the parent-derived rule and names the unqualified cases and lost finals. |
| Missing Codex kind rows and live counts | All 23 inventory rows and the 2,096,004 total match the four sweep slices. A2 accurately retains searchable `unknown` records and explains the cost. |
| Resume tie clarification | Matches `_later`/`_direction` and the wholly copied original control. |
| Mismatch and index roots mismatch | Index behavior is accurate, including explicit-file independence. The mismatch definition needs finding 2’s qualification. |
| Response-only turns and `abort_reason` | Matches first-response refs, null triggers, queued inputs, derived-rule behavior, and Codex closing-reason emission. |
| Target-line exemption and `turn_cut` | Target blocks and changed target lines survive the cap. Finding 3 clarifies the coverage flag’s limit. |
| Coverage fields and bounded commands | Fields, matching before truncation, collapsed-copy versus final behavior, unread-alias time/cwd rules, and mention-listing bounds match Stage A. Finding 1 corrects task ordering. |
| Mid-parent and no-copied-start forks | Retained results show seven non-prefix samples and one without copied `task_started`; all 20 connected and isolated checks passed as described. |

A1 and A2 are adequately reasoned decisions to retain shipped behavior. Their rejected alternatives, reasons, costs, and later qualification requirements are clear. No requested amendment subject was set aside.

Verification performed:

- Manifest hash and all 18 retained entries verified; raw ledger hash matched. The portable ledger equals the raw ledger after storage-root substitution.
- Recomputed sweep totals, unknown-kind counts, elapsed total, peak RSS, reader revisions, and fork summaries from retained JSON.
- Confirmed §11 is identical to the base revision.
- Traced the requested failure paths through the frozen implementation and relevant tests.
- Ran three isolated, in-memory counterexample checks described above; all confirmed the findings.

The document correctly limits the live evidence to the earlier runs, distinguishes them from the final merged reader, and preserves Stage B’s gate. No files, task records, index, HEAD, or branches were changed. No processes remain running.

Verdict: **revise — Critical 0, Important 2, Minor 1**. The controller owns the next frozen revision; human approval remains required afterward.

Not checked: no full-suite rerun or new live-store sweep. Risk: the two unsupported contract promises should be corrected before approval.
