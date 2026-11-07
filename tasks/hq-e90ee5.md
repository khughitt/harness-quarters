---
id: hq-e90ee5
title: Adopt current ops documentation citations
status: done
priority: 2
size: s
complexity: low
process: direct
owner: docs/hq-e90ee5-pre-push-citation
created: 2026-11-05T11:40:40Z
updated: 2026-11-07T12:41:17Z
started: 2026-11-07T12:38:27Z
completed: 2026-11-07T12:40:04Z
closed: 2026-11-07T12:40:04Z
depends: [ops-713299]
tags: [docs]
source: ops-7f0b75
---

Follow-up from the approved ops public-document curation, ops-7f0b75. The private archive is records commit a83536d369734fcf0cb2ad6b8c876e8f7d5dadb3, under ops/<original path>; the migration receipt is ops/docs/notes/2026-11-05-public-docs-migration-receipt.md. Current references are authored in ops on docs/ops-7f0b75-public-docs; wait for its separately approved paired integration, ops-713299, before adoption.

Refresh and disposition the current citations found in: .githooks/pre-push. Replace authored historical-current guidance pointers with the appropriate ops subject reference (tooling, project-guides, CLI conventions, key vocabulary, operations, execution evidence or a runbook). Keep genuine historical evidence tied to the private archive revision rather than rewriting its meaning. Preserve frozen fixtures byte-for-byte with explicit historical locators. For tools/cli.toml, tools/cli_surface.py or tools/keys.toml, adopt one compatible landed snapshot with normal conformance checks; do not hand-edit or broadcast tables. Family-copy comments follow that family's staged adoption, not a premature family publish. tt/ops-docs broadcast copies belong to the paired ops rollout and are not this task's edits.

Done: each named current match has a valid subject/private locator or explicit historical/non-applicable disposition; required hygiene and affected focused checks pass under checkout-local policy. Attach this receipt to any future publication prerequisite; an open task is ownership, not proof that citations are already fixed. No push, publication, live global-instruction delivery, host change or unrelated docs migration is authorized. Where generated output is involved, update its owning source and regenerate under the normal activation gate.

## Notes

- 2026-11-05T11:40:40Z (add): created
- 2026-11-07T12:38:27Z (docs/hq-e90ee5-pre-push-citation): started
- 2026-11-07T12:38:50Z (docs/hq-e90ee5-pre-push-citation): trial: flow-trial-1 — enrolled — flow off
- 2026-11-07T12:38:52Z (docs/hq-e90ee5-pre-push-citation): arm: flow-trial-1 — unit tack-e90ee5 — flow off
- 2026-11-07T12:39:57Z (docs/hq-e90ee5-pre-push-citation): Focused baseline (policy-off checkout, .tt.toml automatic_broad = false): ran 'just test-one tools/test_test_execution.py -k test_pre_push' before edits (7 passed in 2.62s); deliberately omitted broad 'just test' / 'just ci-test' per .tt.toml policy.
- 2026-11-07T12:39:59Z (docs/hq-e90ee5-pre-push-citation): flow-trial-1: flow off (unit tack-e90ee5)
- 2026-11-07T12:40:00Z (docs/hq-e90ee5-pre-push-citation): rework: none
- 2026-11-07T12:40:02Z (docs/hq-e90ee5-pre-push-citation): scope-drift: none
- 2026-11-07T12:40:04Z (docs/hq-e90ee5-pre-push-citation): done
- 2026-11-07T12:40:04Z (docs/hq-e90ee5-pre-push-citation): Replaced historical 'Design: ops docs/specs/2026-09-28-test-ci-act-design.md §3.3.' citation on line 14 of .githooks/pre-push with current subject reference 'Reference: ops docs/tooling.md' matching ops/.githooks/pre-push (historical spec archived in ops private records commit a83536d369734fcf0cb2ad6b8c876e8f7d5dadb3 under ops/docs/specs/2026-09-28-test-ci-act-design.md). Verified with 'just test-one tools/test_test_execution.py -k test_pre_push' (7 passed) and mandatory 'just check-hygiene' (exit 0).
- 2026-11-07T12:41:17Z (main): Merged docs/hq-e90ee5-pre-push-citation (9318a4d9) to main via fast-forward; ran tt-report (focused test-one: 2 runs, 7 passed; check-hygiene: 1 pass; broad test skipped per .tt.toml policy); verified only regenerable local/ directories and __pycache__/.pytest_cache existed in worktree, no host pointers resolved into .worktrees/hq-e90ee5, and removed worktree and branch. Nothing pushed; no surviving processes (verified via host-load --section session).
