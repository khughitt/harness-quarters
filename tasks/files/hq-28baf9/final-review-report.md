Accept revision 10 of hq-28baf9: **Critical 0, Important 0, Minor 0**. The two clarifications accurately record existing behavior and measured limits. Revision 9 was approved for planning; revision 10 implements its optional, nonbehavioral additions. The controller owns the fresh suite result, task closeout and local integration. This acceptance authorizes no Stage B execution.

Reviewer: **codex/gpt-6.1-sol**. Fresh `timeout 2 relay model --harness codex --pretty` returned exactly `codex/gpt-6.1-sol`, exit 0.
Reviewer session: `01a17840-b148-7961-afd5-a15509761881`.

I reviewed frozen hq commit `e4f3d69ca2bae73b0c6463076d35a913f2be0de6`, path `docs/specs/2026-10-23-session-evidence-reader-design.md`, using `git show`. Its SHA-256 matches `0502d9c6f68d8d670e993e1b7ab5561681c3b0ded62d16bad7a2bc9231104cde`. I compared revision 9 at `6356a82549dd8235768262c9cea894f4940d6637` and read the complete documentation diff against base `4f32e64`.

- **A3’s direction figures are supported.** At `.worktrees/hq-28baf9/docs/specs/2026-10-23-session-evidence-reader-design.md:1715`, the spec correctly distinguishes the original native-choice counter from the follow-up timing comparison. In obs `062b73e`, `_direction` returns immediately when one native link decides the pair, so the original counter alone cannot establish timing agreement.

  The new script independently evaluates `_later` in both directions for each one-sided, decisively linked pair. Equal predicates count as a timing tie; otherwise it compares the timing-selected copy with the native-selected copy. The result records 13 such pairs: 12 agreements, one tie and zero reversals. Thus “12 of 12” among decided cases is correct. The separate 2,965-file measurement does not replace the original 2,961-file census.

  **Decision retained:** keep R26’s timing fallback and reverse-subset warning. **Why:** preserve completed-resume recovery while acknowledging that the same record shape admits the reverse history. **Cost:** shared opening history and finals can receive the wrong attribution. Revision 10 adds positive agreement evidence without claiming historical proof or a measured failure frequency.

- **A5 accurately records the existing detection boundary.** At `.worktrees/hq-28baf9/docs/specs/2026-10-23-session-evidence-reader-design.md:1754`, the new Why/Cost entry agrees with §6.4 and the frozen implementation.

  In `../obs/session_logs_query.py:516`, evidence-selected files load together. Additional mention files pass through store groups separately at lines 525–527. `../obs/session_logs_read.py:298` marks copies only among the files passed to that load; later emission does not compare the two groups.

  Consequently, a mention-only file B can retain an opening copied from evidence-selected A, including its completed turn and final. The mention predicate can select B through that retained task-id text. The wording correctly says this **can** happen. Section 9.4 still states that textual mentions never establish ownership.

  **Decision recorded:** retain separate evidence and mention detection. **Why:** document the delivered pipeline without introducing a new combined detection pass. **Cost:** copied answers can be misattributed or counted again across the boundary; Stage B’s usage skill must disclose this limit.

- **Approval and rollout status are accurate.** The frozen acceptance attachment records revision 9’s approval for planning and two optional additions. Revision 10 does not imply fresh approval of runtime changes. Section 11 is byte-identical to both revision 9 and the branch base, retaining its readout gate.

Verification completed:

- The source manifest matches retained `SOURCE.json`; all **55** exported root Python modules match both obs `062b73e` and their recorded SHA-256 hashes.
- Seven attached/canonical artifact pairs match byte for byte. Pilot and full direction results name the correct script hash and pinned reader hashes; their per-root counters sum to their totals.
- Five original census/contract evidence files remain byte-identical to revision 9.
- The five supplied synthetic control groups passed against the frozen source. An additional native-link timing-tie control passed, directly exercising the new tie counter.
- `git diff --check 4f32e64 e4f3d69` passed.

For unchanged whole-spec assertions, I reused the attached revision-8 whole review and revision-9 corrective acceptance. Those cover the earlier coverage, identity, turn, target-window, unknown-kind and fork-boundary amendments. I did not claim a fresh independent audit of their historical sweep counts. The new source inspection used `062b73e`, not current obs main, which contains unrelated work.

I changed no files, task records, index, HEAD or branches; wrote no report file; pushed nothing; and left no process running. `host-load --section session` reported nothing left running. The controller retains `docs/hq-28baf9-reader-spec` in `.worktrees/hq-28baf9` and owns local integration after its final checks.

Not checked: no full-suite run, live census or six-root sweep; the controller’s fresh suite result remains separate evidence.
Remaining risk: timing-only attribution, unknown-record duplication, ambiguous-final omissions and the evidence/mention boundary remain deliberate, disclosed runtime limits.
