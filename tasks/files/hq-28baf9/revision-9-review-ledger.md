# hq-28baf9 revision 9 amendment ledger

Current frozen spec: hq 6356a82549dd8235768262c9cea894f4940d6637,
docs/specs/2026-10-23-session-evidence-reader-design.md, revision 9,
SHA-256 ddcb9065a9e55a729f0963dc583d714e6b50f1c975f94ee457174eeafe7a1ce8.
Human design review remains pending. No implementation plan was drafted; that request
was explicitly cancelled by the user. No reader or live-surface behavior changed.

This ledger supersedes the pending/deferred state of the historical attached
amendment-review-ledger.md, which remains preserved. No Minor finding remains deferred.

## Rulings in revision 9

- Ruling: A1 retains the parent-turn-id fork boundary and does not adopt the native ordinal. Why: the 269 positive agreement cases do not qualify invalid/conflicting markers, malformed offsets or forks without own turns. Cost: parent-unavailable forks remain ambiguous and their own finals unavailable. References: revision 9 sections 8.3 and 14.7; inherited from revisions 6–7.
- Ruling: A2 retains all 23 measured unmapped Codex kinds as unknown; the mirror-exclusion claim is limited to mapped metadata mirrors. Why: counts do not establish role, mirroring or pairing semantics. Cost: about 2.1 million unknown records can match, may duplicate response content, consume limits and inflate raw match aggregates; duplication was not measured. References: revision 9 sections 6.1, 8.2 and 14.7; revised from revision 7 by 20c8629.
- Ruling: A3 retains R26's timing fallback with its explicit reverse-subset limit rather than changing the reader to tie one-sided pairs. Why: it preserves the completed-resume interpretation, but the same shape admits an abandoned copy followed by the original continuing; the new census did not qualify timing-only direction because all 13 observed one-sided pairs had native links. Cost: shared opening history and finals can be attributed to the wrong file; no failure frequency is established. References: revision 9 sections 8.3 and 14.7, introduced at 20c8629.
- Ruling: A4 retains final-pattern not_found as no eligible final, even if an ambiguous turn holds matching assistant text. Why: ambiguous turns suppress finals and record search can inspect the text without asserting ownership. Cost: not_found does not prove no matching answer was recorded; a possibly own final can be hidden. References: revision 9 sections 6.5 and 14.7, introduced at 20c8629.

## Review history and dispositions

1. Revision 6 e8ff370: codex/gpt-6.1-sol, session 01a177b0-3ff7-7c70-ba3e-a29aded078e0, revise (Important 2, Minor 1). Full spec-review-report.md attached. Incorrect task emission order and overbroad mismatch protection corrected at 669b3d6; target-limit coverage caveat documented.
2. Revision 7 669b3d6: fresh codex/gpt-6.1-sol, session 01a177bb-346d-7d91-a630-ded5e7ff4e4c, accept (Minor 1). Full spec-correction-review-report.md attached. Earlier explicit-file M4 wording deferred there, corrected in revision 8.
3. Revision 7 669b3d6 overall review: supplied as claude-code/claude-opus-5-5, revise (Important 2, Minor 7). Full overall-design-review-portable.md attached; exact raw bytes retained under the task evidence record. R26 reverse-case attribution now disclosed with Why/Cost after a live census; default-role uniqueness now limited and duplicate-hit risk explicit. All seven Minor points addressed: capped outside-root sample, actual abort-field behavior, scope/detection clarification, effective alias window, removed derived-marker clause, exact target window, intended ambiguous-final outcome. The proposed Claude null value was corrected to omission after source tracing; it is not the shipped value. Prior M4 corrected too.
4. Revision 8 20c8629: fresh codex/gpt-6.1-sol, session 01a177fe-1f53-7df1-ab0a-3cc862ef152d, revise (Important 1, Minor 1). Full revision-8-review-report.md attached. Earlier Important issues accepted as addressed. The task detection grouping overstatement and Claude abort_reason null statement corrected at 6356a82.
5. Revision 9 6356a82: fresh codex/gpt-6.1-sol, session 01a17809-0309-7ee3-8a5e-5fdf7ec43bdc, accept (Critical 0, Important 0, Minor 0). Full revision-9-review-report.md attached. Both corrective contracts accepted; no further corrective round required.

## Evidence and checks

- Original baseline just test: 1672 passed (231 agents, 1051 hooks/tools, 389 parallel relay, 1 isolated relay). No full-suite repeat after documentation-only edits.
- New R26 census: 2961 native Claude main files, 360 project directories, 3131911097 bytes, 94.72 seconds, zero unparsed lines, 20 shared-UUID pairs, 13 one-sided timed-record pairs all with decisive native links, 12 strict UUID-subset pairs all linked; overlapping categories. Two aliases and subagent/archive/pruned files excluded; size-on-open bounds, not a simultaneous snapshot. Counts do not establish historical direction or reverse-case frequency.
- Attached subset-census.py, subset-pilot.json and subset-census.json preserve method, five assert controls, live pilot and full counts. Reader source hashes match obs 062b73e.
- Attached contract-probes.py and contract-probes.json preserve four passing controls: late target, whole-target-line exemption without omission, noncontiguous target indices and XK final-pattern not_found versus record found.
- Round 4 independently replayed those controls, six compression-equivalence cases, task-grouping counterexample and two Claude interrupted-turn cases. Round 5 used source inspection and hand-tracing, not a suite rerun.
- Documentation, task and diff checks passed after each frozen correction. Stage B section 11 remains byte-identical to the earlier revision and its readout gate is unchanged.
- Review-guidance feedback filed as lore-6b5f19; it asks reviewers to reverse one-sided inference examples and test guarantees against fallback categories.

## Retention and next step

The locked task worktree and both inherited/new evidence containers remain owned by
open hq-28baf9 under its retained-item records. Raw hostname-bearing review bytes stay
preserved behind a portable derivative until the executing layout check admits them
or an open owner accepts transfer. Full returned reviews and this ledger are attached;
no full transcript text was retained by the census.

User reviews frozen revision 9, then the agent handles requested changes or integrates
the branch locally after approval. No push, live home link, launcher or service change
is authorized by this amendment. No review, census or check remains running.
