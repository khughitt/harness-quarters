Accept revision 7 for human review. All three previous findings are addressed; I found no remaining Critical or Important issue in the corrections. One Minor inconsistency remains in connected explicit-file wording. hq-28baf9 stays with the controller for its disposition and the required human approval.

Reviewer: `codex/gpt-6.1-sol`, verified this turn with `timeout 2 relay model --harness codex --pretty`.
Reviewer session: `01a177bb-346d-7d91-a630-ded5e7ff4e4c`.

Reviewed frozen hq commit `669b3d6b5c1be88efd583970ef2b703470047e9a`, path `docs/specs/2026-10-23-session-evidence-reader-design.md`, and its corrective diff from `e8ff3707051c164a8fd522117c2e6096cd1426ea`. Spec line references below name that frozen revision. Implementation references name obs commit `062b73e`.

| Previous finding | Disposition and check |
|---|---|
| **I1 — evidence-first emission promise** | **Addressed**, §6.4, lines 597–600. `_task_stream` sorts the combined evidence and mention-only `kept` files through `_sorted` (`../obs/session_logs_query.py:549`). With stamped file mtime 100 and mention-only file mtime 200, default activity sorting emits the mention first; `--sessions --limit 1` omits the stamped session. The amended text states this consequence. §9.4’s evidence-strength tiers remain consistent: they rank evidence entries, not emitted files. |
| **I2 — overbroad filename mismatch protection** | **Addressed**, §5.2, lines 389–394 and 407–409. A Claude main transcript renamed from UUID A to UUID B is an `own` candidate for B: placement takes the filename stem, and normalization retains B with `file_name_unconfirmed` when main-line records say A (`../obs/session_logs_place.py:311`, `../obs/session_logs_place.py:342`, `../obs/session_logs_records.py:483`). A native Codex filename for B whose first metadata records unrelated A becomes `mismatch` and is excluded from B’s readable `own` files. The amended protection is correctly scoped. |
| **M3 — `turn_cut` without omission** | **Addressed**, §4.6, line 339, and §7.2, lines 721–733. For three objects on the target line with cap 1, `_target_turn` retains indices 0, 1 and 2, emits all three, and reports `limits.hit: true` with `{records: 3, shown: 3, before: 0, after: 0}` (`../obs/session_logs_show.py:459`). A changed target line follows the same exemption; `_record_view` retains its current records, `_item` marks them changed, and the outcome remains `unknown` with `line_changed`. |

**Minor finding**

**M4 — the explicit-file subsection still claims identity comes from records.** Spec §6.7, lines 693–694, says: “The file’s identity comes from its records as in §5.2.” That conflicts with the corrected UUID filename authority in §5.2, lines 389–394.

For an explicit Claude main file named UUID B whose records contain UUID A, normalization returns B with `file_name_unconfirmed`. A reader consulting only §6.7 could expect A. This wording predates the corrective diff, but it is directly connected to I2’s correction.

Smallest correction: replace “comes from its records as in §5.2” with “follows §5.2.” This requires no behavior change. It is Minor because §5.2 now gives the precise rule and explicitly discloses the renamed-file risk; it does not block human review.

Verification and limits:

- Read the corrective diff, affected spec sections, connected identity/order/bounds claims, frozen implementation paths, and relevant placement, normalization, search and show tests.
- Hand-traced the five requested cases above. Existing tests support Codex mismatch handling, task mentions, sorting, target-line survival and changed-line marking; I did not execute them.
- `git diff --check` passed. The corrective commit changes only the spec, task record and prior review attachment.
- Independently confirmed §11 is byte-identical to base `4f32e64`.
- Set aside the already reviewed live-count audit, native-ordinal qualification, unknown-kind inventory, resume/fork evidence and retained manifest. These corrections do not depend on new retained bytes, so I did not reread `$WORK_ROOT/obs/obs-d98663/live` or repeat that audit.
- The controller-reported baseline of 1,672 passing tests was not rerun or independently verified in this pass.

Verdict: **accept — Critical 0, Important 0, Minor 1**. The controller owns M4’s disposition; human approval remains required. No files, task records, index, HEAD or branches were changed; nothing was pushed. The task worktree remains intact, and `host-load --section session` reported nothing left running.

Not checked: no full-suite rerun, live-store scan or repeated retained-evidence audit. Remaining risk: §6.7’s abbreviated wording can mislead explicit-file users until corrected.
