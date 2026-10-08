---
id: hq-3cdd68
title: Verify staged deletion and rename protection for capability facts
status: todo
priority: 2
size: s
complexity: mid
process: direct
created: 2026-10-08T23:10:34Z
updated: 2026-10-08T23:10:35Z
depends: []
tags: []
source: "tasks-56b450:followup:fact-file-lifecycle"
agent: codex/gpt-6.1-sol
---

Question: should the staged-facts gate protect the validated reader's default file when the canonical fact file is deleted or renamed? The existing ACMR staged-path filter skips deletion/rename-away; the claim-guard change deliberately preserved that behavior. This is pre-existing protection to investigate, not a rollout regression.

Where to start: .githooks/pre-commit facts_check/main, .githooks/test_pre_commit_facts.py and tools/harness-facts default-file selection. Evidence: tasks-56b450; tasks docs/notes/2026-10-08-claim-guard-execution-ledger.md, Task 2/final canonical-deletion rulings.

Bound: inspect source and run disposable staged cases for deletion alone, rename without a reader update, and a deliberate move accompanied by the reader's default-path update. Keep all projects/config/state isolated and never mutate live facts, homes or reader endpoints. Distinguish the current working file, index blob and staged reader behavior. No general pre-commit rewrite.

Expected result: a small evidence table and a precise disposition: existing behavior is sufficient, or a scoped remedy that refuses broken staged reader/data combinations while permitting a valid coordinated move. File any implementation separately if an unresolved policy choice needs a reviewed design.

## Notes

- 2026-10-08T23:10:35Z (main): concerns: tasks-56b450 extension — investigate the pre-existing canonical fact deletion/rename gap without expanding the completed mirror-removal scope.
