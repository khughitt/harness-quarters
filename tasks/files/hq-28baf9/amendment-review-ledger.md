# hq-28baf9 amendment review ledger

Direct documentation work; no new implementation plan. Base hq 4f32e64.
Revision 6: e8ff3707051c164a8fd522117c2e6096cd1426ea.
Revision 7: 669b3d6b5c1be88efd583970ef2b703470047e9a.
Spec: docs/specs/2026-10-23-session-evidence-reader-design.md.

## Decisions

- Ruling: A1 retains R11 and the parent-turn-id fork boundary in revisions 6 and 7; reject enabling the native ordinal from the 269 positive agreement cases alone. Why: invalid, conflicting, malformed-offset and no-own-turn cases remain unqualified; retaining the shipped rule keeps the amendment honest about delivered behavior. Cost: parent-unavailable forks remain ambiguous and own finals unavailable, even when the native field could eventually settle ownership.
- Ruling: A2 retains R15 and explicitly lists all 23 measured unmapped Codex kinds as unknown in revisions 6 and 7; reject role inference from names/counts alone. Why: the sweep does not qualify role, mirroring or call/result semantics. Cost: about 2.1 million Codex records remain unknown and their JSON can match default pattern searches.

## Review rounds

1. Reviewer codex/gpt-6.1-sol, session 01a177b0-3ff7-7c70-ba3e-a29aded078e0, reviewed frozen e8ff370. Verdict revise: Important 2, Minor 1. Full report spec-review-report.md, attached to the task. I1 evidence-first file emission and I2 harness-general mismatch protection were unsupported; M3 turn_cut could accompany no omission. Controller verified against obs 062b73e and corrected all three in 669b3d6.
2. Fresh reviewer codex/gpt-6.1-sol, session 01a177bb-346d-7d91-a630-ded5e7ff4e4c, reviewed frozen 669b3d6 and its corrective diff. Verdict accept: Critical 0, Important 0, Minor 1. I1/I2/M3 addressed. Full report spec-correction-review-report.md, attached to the task. No additional corrective round is required.

## Deferred minor

- minor (deferred): M4, revision 7 section 6.7 lines 693–694 says explicit-file identity comes from records as in section 5.2; section 5.2 correctly states that UUID-named Claude main files keep filename identity with file_name_unconfirmed when records disagree. The abbreviated wording can mislead a reader consulting only section 6.7. Small correction for a later revision: replace the identity phrase with follows section 5.2. Tracked on open hq-28baf9 pending the user's frozen design review.
- Ruling: M4 remains minor (deferred) for the human review of 669b3d6. Why: the authoritative referenced section 5.2 states the precise rule and renamed-file limit, and the independent reviewer accepts this revision; minor-only findings do not launch another corrective round. Cost: section 6.7 retains misleading shorthand until the next revision. This is not a runtime fix or a claim that the wording is correct.

## Verification and gate

- New-worktree setup: just setup; baseline just test 1672 passed (231 agents, 1051 hooks/tools, 389 parallel relay, 1 isolated relay).
- Documentation-only changes. No new tests, runtime edits, store scans, root/skill/link changes or trial measurement changes.
- All 23 unknown-kind rows and the total checked against the four retained slices. Source manifest and all 18 entries verified. Section 11 gate is byte-identical to base 4f32e64.
- git diff --check, tools/ops-check, tools/ops-docs check and tasks check passed after both spec commits.
- Review 1 hand-traced the requested contracts and ran three in-memory counterexamples. Review 2 hand-traced the corrective contracts; neither reviewer reran the full suite or live sweep.
- Human review is still required before integration. Frozen revision 7 SHA-256: d5e388d0b0c5eb7197ecf332944eff0e7fbd1dc75db64ac1341473f88052eccb.
