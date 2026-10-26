# hq-28baf9 final amendment ledger

Approved design: revision 9, hq 6356a82549dd8235768262c9cea894f4940d6637.
Delivered text: revision 10, hq e4f3d69ca2bae73b0c6463076d35a913f2be0de6,
docs/specs/2026-10-23-session-evidence-reader-design.md, SHA-256
0502d9c6f68d8d670e993e1b7ab5561681c3b0ded62d16bad7a2bc9231104cde.
Revision 10 implements the acceptance's two optional clarifications without changing
a decision. Fresh final review accepted it with no findings. Local integration is the
closing session's next action; no Stage B execution or live-surface activation is approved.

This supersedes pending/deferred states in earlier attached ledgers. They and all full
review reports remain preserved. No Minor finding remains deferred.

## Rulings in revision 10

- Ruling: A1 retains the parent-turn-id fork boundary; native ordinal adoption is rejected for this amendment. Why: 269 positive agreements do not qualify invalid/conflicting ordinals, malformed offsets or forks without own turns. Cost: parent-unavailable forks remain ambiguous with own finals unavailable. References: sections 8.3 and 14.7, retained from revisions 6–9.
- Ruling: A2 retains all 23 measured unmapped Codex kinds as unknown; mirror exclusion covers mapped metadata only. Why: counts do not qualify roles, mirror relationships or pairing semantics. Cost: about 2.1 million unknown records may match, duplicate response content, consume limits and inflate raw aggregates; duplication remains unmeasured. References: sections 6.1, 8.2 and 14.7, qualified at 20c8629.
- Ruling: A3 retains R26's timing fallback with the reverse-subset warning instead of forcing every one-sided pair to tie. Why: preserve completed-resume recovery while the same shape admits an abandoned copy followed by original continuation; linked agreement is corroboration, not proof for unlinked history. Cost: shared opening history and finals can be attributed to the wrong file; no failure frequency is established. References: sections 8.3 and 14.7, introduced at 20c8629 and clarified at e4f3d69.
- Ruling: A4 retains final-pattern not_found as no eligible final, even when an ambiguous turn holds matching assistant text. Why: ambiguous turns suppress finals; record search can inspect the text without asserting ownership. Cost: not_found does not prove no matching answer was recorded. References: sections 6.5 and 14.7, introduced at 20c8629.
- Ruling: A5 retains separate task-evidence and mention detection rather than introducing a combined pass. Why: this amendment records the delivered two-pass pipeline and does not qualify or implement joining its groups. Cost: copied opening answers in mention-only files can be misattributed or counted again when their source is evidence-selected; Stage B's usage skill must disclose the limit. References: sections 6.4 and 14.7, explicit ruling added at e4f3d69 for the already accepted limit.

## Review and approval record

1. Revision 6 e8ff370, codex/gpt-6.1-sol: revise, Important 2 and Minor 1. Task ordering/mismatch corrections and target-cap caveat delivered at 669b3d6; full spec-review-report.md attached.
2. Revision 7 669b3d6, fresh codex/gpt-6.1-sol: accept, Minor 1. Full spec-correction-review-report.md attached; deferred explicit-file M4 later corrected.
3. Revision 7 overall review supplied as claude-code/claude-opus-5-5: revise, Important 2 and Minor 7. Full portable report attached, raw bytes preserved. R26 reverse-case limit, qualified mirror guarantee, coverage/scope/window/field clarifications and M4 addressed through revisions 8–9.
4. Revision 8 20c8629, fresh codex/gpt-6.1-sol: revise, Important 1 and Minor 1. Full revision-8-review-report.md attached. Task detection split and Claude abort field corrected at 6356a82. The suggested Claude null value was contradicted by actual spans: Claude omits abort_reason.
5. Revision 9 6356a82, fresh codex/gpt-6.1-sol: accept, no findings. Full revision-9-review-report.md attached.
6. Revision 9 supplied acceptance, claude-code/claude-opus-5-5: accept, Minor 2 optional additions. Full revision-9-acceptance-report.md attached. Its supplied round label was 5; task note numbering uses next available round 6. Direction evidence quoted accurately and A5 Why/Cost added.
7. Human: Keith approved revision 9 for planning with the optional nondecision-changing clarifications. This is not Stage B execution approval; the accidental implementation-plan request remains cancelled.
8. Revision 10 e4f3d69, fresh codex/gpt-6.1-sol, session 01a17840-b148-7961-afd5-a15509761881: accept, Critical 0, Important 0, Minor 0. Full final-review-report.md attached, including whole-branch diff inspection and scoped source/evidence checks. No corrective work remains.

## Verification and limits

- Original baseline and fresh final just test both exited 0 with 1672 passed: 231 agent tests, 1051 hook/tool tests, 389 parallel relay tests and 1 isolated relay test. The isolated selector deselected 153 tests already covered by its companion segment.
- Fresh docs/task/diff checks passed. Stage B section 11 is byte-identical to the accepted revision and branch base. Covered code tree remains 431a4a64a12bdb1934887133dc3e420991d6af65; only docs/task records and attachments changed.
- Original new census: 2961 native Claude main files, 360 project directories, 20 shared-UUID pairs, 13 one-sided timed-record pairs, all native-linked; 12 strict UUID-subset pairs, all linked. Categories overlap. Two aliases and subagent/archive/pruned files excluded; size-on-open bounds are not a simultaneous snapshot.
- Direction follow-up: 2965 then-current main files, 20 shared-UUID pairs, 13 one-sided native-linked pairs. Native chose the side with new records in all 13, but the independent timing comparison found 12 agreements, 1 tie and 0 reversals: 12/12 agreement among decided cases, not 13 timing decisions. It does not establish historical direction or reverse-case frequency.
- The first direction pilot stopped in synthetic self-check because current obs had changed its private API through other work. No store scan occurred then. Exact obs062b73e modules were exported, hash-verified, used for passing pilot/full controls, and independently reviewed. The 55 regenerable modules were then discarded; their source manifest is attached and retained.
- Five predicate-control groups and four contract cases passed; reviews added compression-equivalence, task-grouping, Claude-interruption and timing-tie checks. No repeated historical six-root sweep was needed. No runtime code was changed by this task.
- Review-guidance feedback is lore-6b5f19. No deferred Minor remains.

## Retention and integration

All full reports and this ledger are task attachments. Historical worktree paths inside
those frozen reports refer to their named commits; the current spec is the path above.
The review workspace is removable only after its attachment copies are byte-verified.

Both evidence containers and their separately recorded raw fallbacks were transferred
without moving to open hq-c5fd83, whose four receiving records were verified before
the sending records were released. The old 18-entry manifest is
5bf30ddd1c34123fdd2f9dec293074e9eddf55497ffbf619da9cb9b684289671; the new 10-entry
manifest is c9e23a3b6e956333a1d99a8209933c7c8090eb4d8d028f805810c5e161c8e8f6.
That task owns raw restoration after the executing layout exemption ships; it must
preserve still-referenced measurements before any container cleanup. No raw copy was lost.

The closing session owns only the worktree's immediate integration and checked removal.
tt-report exited 0. Ignored pytest/tool caches are regenerable; redundant review-workspace
copies are already preserved as attachments. Before removal, check live host pointers
and merge ancestry. Existing live settings, other worktrees and current obs work stay
untouched. Nothing is pushed and no persistent process is created.
