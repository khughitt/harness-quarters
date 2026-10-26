Accept revision 9 of hq-28baf9: **Critical 0, Important 0, Minor 0**. Both corrective changes match the frozen implementation. Human design approval remains pending; the controller should record this acceptance and continue that review gate before integration.

Reviewer: **codex/gpt-6.1-sol**. Fresh `timeout 2 relay model --harness codex --pretty` returned exactly `codex/gpt-6.1-sol`, exit 0.
Reviewer session: `01a17809-0309-7ee3-8a5e-5fdf7ec43bdc`.

Reviewed hq commit `6356a82549dd8235768262c9cea894f4940d6637`, path `docs/specs/2026-10-23-session-evidence-reader-design.md`, using `git show`. Its SHA-256 matches `ddcb9065a9e55a729f0963dc583d714e6b50f1c975f94ee457174eeafe7a1ce8`. I compared the corrective diff from `20c86291631e5a423d822cf5acee20f07b60fcd8` and checked connected statements against obs `062b73e`.

- **Prior Important 1 is resolved.** `.worktrees/hq-28baf9/docs/specs/2026-10-23-session-evidence-reader-design.md:615` correctly distinguishes session searches, the task evidence group, and additional mention groups. In `../obs/session_logs_query.py:516`, evidence entries load together. Lines 525–527 group and stream the additional entries separately using the store grouping rules. Neither that path nor `../obs/session_logs_read.py:298` compares those entries with the already loaded evidence group.

  I hand-traced the reported counterexample: A is evidence-selected; same-directory B repeats A’s opening UUIDs and task-id text, then adds a later turn, without its own task evidence. A and B enter different loads, so B’s opening remains unmarked. The mention predicate at query lines 537–546 retains B, and its copied answer can become its own completed turn and final. Loading both together would let resume detection mark B’s shared opening instead. Revision 9 states this consequence explicitly without promising it occurs for every mention.

  The retained session-search guarantee also holds: `_session_files` selects `own` candidates, and `components(..., "session")` returns one group. The grouping change does not promote other candidate relations.

- **Prior Minor 2 is resolved.** `.worktrees/hq-28baf9/docs/specs/2026-10-23-session-evidence-reader-design.md:308` correctly limits `abort_reason` to Codex interrupted turns closed by `turn_aborted`.

  I hand-traced the frozen CM fixture’s two interruptions, ending at CM:52 and CM:54. `_claude_spans` closes both with `_INTERRUPT` but never assigns `closing`; `_Span.closing` remains `None`. Consequently, `_turn` omits `abort_reason` for both. The sole `closing` assignment is the Codex event path at `../obs/session_logs_turns.py:217`. Codex’s `turn_aborted` reader supplies its string reason or `None`, and `_turn` emits that value only for an interrupted span with a closing event. Other Codex turns omit the field.

The connected copy and task-selection text introduces no conflicting guarantee. Mention evidence remains distinct from ownership evidence, and the correction concerns detection boundaries rather than emission order. The earlier review’s accepted R26, mirror and ambiguous-final decisions remain unchanged.

Verification was source inspection and hand-tracing, not a runtime replay or test-suite run. I read the relevant frozen search and turn tests; their expectations are consistent with these corrections. The controller-reported 1,672-test baseline remains prior evidence, not a result produced by this review.

I changed no files, task records, index, HEAD or branches; wrote no report file; pushed nothing; and started no surviving process. `host-load --section session` reported nothing left running. The controller retains branch `docs/hq-28baf9-reader-spec` in `.worktrees/hq-28baf9` and owns integration after human approval.

Not checked: no repeated census, historical six-root sweep, earlier whole-spec audit or full suite.
Remaining risk: copied opening answers can survive the disclosed evidence/mention boundary; this documentation amendment preserves that runtime behavior.
