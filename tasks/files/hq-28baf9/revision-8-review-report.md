Revise revision 8 of hq-28baf9: **Critical 0, Important 1, Minor 1**. The two earlier Important findings are addressed, but two amended statements still differ from shipped behavior. The controller should correct those documentation contracts in a new frozen revision. Human design approval remains pending.

Reviewer: **codex/gpt-6.1-sol**, verified this turn with `timeout 2 relay model --harness codex --pretty`.
Reviewer session: `01a177fe-1f53-7df1-ab0a-3cc862ef152d`.

Reviewed hq commit `20c86291631e5a423d822cf5acee20f07b60fcd8`, path `docs/specs/2026-10-23-session-evidence-reader-design.md`, through `git show`. Its SHA-256 matches `ae1cee2c89c1f9f8cbb9ca8c7829218cdf6b718b19c26cbda1590407c7038d5c`. I compared revision 7 at `669b3d6b5c1be88efd583970ef2b703470047e9a` and checked the relevant implementation against obs `062b73e`.

**Important**

1. **The new task-search grouping promise includes files the reader processes separately.**

   Location: `.worktrees/hq-28baf9/docs/specs/2026-10-23-session-evidence-reader-design.md:613`.

   The spec says all selected files of a session or task search share one detection group. In `../obs/session_logs_query.py:516`, `_task_stream` loads evidence-selected files together. Additional `--mentions` files instead pass through separate store groups at lines 525–527. Copy detection never compares files across that boundary.

   Concrete case: evidence selects Claude session A. Session B, in the same project directory, copies A’s opening prompt containing the task id and its answer, then adds a later turn. B has no task stamp or indexed task command. Under `--task --mentions`, B’s copied opening text remains unmarked, selects B as a textual mention, and can appear as B’s own turn and final.

   An in-memory control using the shipped pipeline confirmed this: separate evidence/mention processing produced two B turns, including the copied opening final. Loading A and B together marked B’s opening records `resume_history` and produced only B’s continuation turn.

   **Fix:** limit the one-group statement to session searches and the task’s evidence-selected files. State that additional mention files use separate store groups, with no copy detection across that boundary.

   **If retained without qualification:** consumers can rely on a deduplication guarantee the reader does not provide and attribute copied answers to mention-only sessions. This needs a documentation correction; no runtime change is required by this amendment.

**Minor**

2. **Claude interrupted turns omit `abort_reason`; they do not carry `null`.**

   Location: `.worktrees/hq-28baf9/docs/specs/2026-10-23-session-evidence-reader-design.md:306`.

   The revised field table says Claude carries `abort_reason: null` on interrupted turns with closing records. However, Claude’s span builder never assigns `span.closing`. Only Codex’s closing-event path does so, and `../obs/session_logs_turns.py:388` emits `abort_reason` only when that field is populated.

   Replaying the CM fixture confirmed that both interrupted turns—ending at CM:52 and CM:54—omit `abort_reason`, despite ending at interrupt markers.

   **Fix:** describe Codex interrupted turns as carrying the recorded reason or `null`; describe Claude turns as omitting the field.

   **If retained:** consumers following the field table can mistake a normal Claude omission for malformed output. The round-3 suggestion was inaccurate on this point; revision 8 should follow the observed implementation.

**Earlier findings and retained decisions**

- **R26 reverse-subset case: addressed.** Sections 8.3 and 14.7 correctly show continuing original A being classified as the copy of abandoned B. A3 explicitly retains the heuristic. **Why:** preserve its completed-resume interpretation. **Cost:** shared history and finals can receive the wrong attribution. The census is expressly not evidence of historical direction or failure frequency.
- **Unknown legacy mirrors: addressed.** Section 6.1 now limits its exclusion claim to mapped metadata mirrors. A2 explicitly allows unknown records to duplicate content, consume limits and inflate raw aggregates without claiming duplication was measured.
- **Outside-root sample: addressed.** The sorted sample is correctly capped at 20, alongside the full count.
- **Scope terminology: addressed in part.** “Store-wide” now has a consistent definition. Multiple `own` files in a session search do share detection. Finding 1 covers the remaining overstatement about task mentions.
- **Alias window: addressed.** The rule uses the effective lower bound, including the default window.
- **Unreachable derived-rule clause: removed.**
- **Target window: addressed.** The formula matches `_target_turn`, including target-line restoration, noncontiguous indices and the distinction between end counts and total omissions.
- **Ambiguous final-pattern outcome: addressed as an explicit limit.** A4 accurately retains `not_found` for no eligible final. **Why:** ambiguous turns suppress finals. **Cost:** that outcome does not prove no matching answer was recorded. The record-query inspection route and no-pattern behavior are stated correctly.
- **Earlier explicit-file M4: addressed.** Section 6.7 no longer says identity necessarily comes from records.
- **A1 and Stage B remain bounded.** The native ordinal is still unadopted; parent-unavailable forks remain ambiguous. Section 11 is byte-identical to revision 7.

**Checks and limits**

I read the complete frozen spec, the round-3 report, the census and contract scripts, their JSON outputs, and the relevant reader paths. All eight original amendment topics were included in the review.

The census method preserves the inputs used by `_named`, `_timed_turns`, `_later` and `_direction`; pair counting stays within project directories. Its reported totals support the revised claims: 2,961 files, 360 directories, 20 shared-UUID pairs, 13 one-sided timed-record pairs and 12 strict UUID-subset pairs. All observed one-sided and strict-subset pairs had decisive native links; those categories overlap.

Verification completed:

- Five supplied predicate controls passed.
- Four supplied contract cases passed, including the real XK ambiguous-final case.
- Six additional compression-equivalence controls passed.
- The additional task-grouping counterexample and two Claude interrupted-turn checks reproduced findings 1 and 2.
- Five attached/canonical evidence pairs matched. All six entries in `$WORK_ROOT/hq/hq-28baf9/MANIFEST.sha256` verified against the supplied manifest hash.
- Census script/source hashes matched; the relevant obs modules had no differences from `062b73e`.

I set aside repeating the older sweep’s historical count audit: revision 8 does not alter those measurements. No files, task records, index, HEAD or branches were changed; no report file was written, nothing was pushed, and no review process remains running. The controller retains `.worktrees/hq-28baf9` and owns correction, re-review and integration of `docs/hq-28baf9-reader-spec` after human approval.

Not checked: no full-suite repeat, six-root sweep or new live census; the 1,672-test baseline remains controller-reported evidence.
Remaining risk: timing-only ownership, unknown-event duplication and ambiguous-final omissions remain deliberate limits, accurately disclosed apart from the two corrections above.
