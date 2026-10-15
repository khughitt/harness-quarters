---
id: hq-3cdd68
title: Verify staged deletion and rename protection for capability facts
status: done
priority: 2
size: s
complexity: mid
process: direct
owner: staged-facts-tree
created: 2026-10-08T23:10:34Z
updated: 2026-10-15T02:02:58Z
started: 2026-10-15T01:12:50Z
completed: 2026-10-15T02:02:58Z
depends: []
tags: []
source: "tasks-56b450:followup:fact-file-lifecycle"
agent: codex/gpt-6.1-sol
---

Question: should the staged-facts gate protect the validated reader's default file when the canonical fact file is deleted or renamed? The existing ACMR staged-path filter skips deletion/rename-away; the claim-guard change deliberately preserved that behavior. This is pre-existing protection to investigate, not a rollout regression.

Where to start: .githooks/pre-commit facts_check/main, .githooks/test_pre_commit_facts.py and tools/harness-facts default-file selection. Evidence: tasks-56b450; tasks:docs/notes/2026-10-08-claim-guard-execution-ledger.md, Task 2/final canonical-deletion rulings.

Bound: inspect source and run disposable staged cases for deletion alone, rename without a reader update, and a deliberate move accompanied by the reader's default-path update. Keep all projects/config/state isolated and never mutate live facts, homes or reader endpoints. Distinguish the current working file, index blob and staged reader behavior. No general pre-commit rewrite.

Expected result: a small evidence table and a precise disposition: existing behavior is sufficient, or a scoped remedy that refuses broken staged reader/data combinations while permitting a valid coordinated move. File any implementation separately if an unresolved policy choice needs a reviewed design.

## Notes

- 2026-10-08T23:10:35Z (main): concerns: tasks-56b450 extension — investigate the pre-existing canonical fact deletion/rename gap without expanding the completed mirror-removal scope.
- 2026-10-15T01:12:50Z (main): started
  provenance: {"harness_session":"claude-code:12f40a0d-b227-408f-9d37-d05d8a87e20c","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-15T01:12:56Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-15T01:12:57Z (main): arm: flow-trial-1 — unit tack-3cdd68 — flow on
- 2026-10-15T01:13:05Z (main): gate: scoped — adopted
- 2026-10-15T01:14:38Z (staged-facts-tree): resumed
  provenance: {"harness_session":"claude-code:12f40a0d-b227-408f-9d37-d05d8a87e20c","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-15T01:14:45Z (staged-facts-tree): gate: implementing .worktrees/staged-facts-tree
- 2026-10-15T01:32:11Z (staged-facts-tree): review: impl round 1 — verdict: accept; findings: minor 5; reviewer: claude-code/claude-opus-5-5
- 2026-10-15T01:38:58Z (staged-facts-tree): review: impl round 2 — verdict: accept; findings: minor 3; reviewer: claude-code/claude-opus-5-5
- 2026-10-15T01:48:28Z (staged-facts-tree): review: impl round 3 — verdict: accept; findings: minor 3; reviewer: claude-code/claude-opus-5-5
- 2026-10-15T02:01:55Z (staged-facts-tree): review: impl round 4 — verdict: accept; findings: minor 3; reviewer: claude-code/claude-opus-5-5
- 2026-10-15T02:01:56Z (staged-facts-tree): gate: verified tree:a520690b48e7f387e1f332823aa1f5d1e165f0d4 — checks: just test 709 passed; .githooks suite 178 passed; real git commits in disposable hq clones through the new hook refuse deletion and index-only deletion and rename without reader and reader default moved without file and invalid content and allow the coordinated move and partial or -a commits follow the committed index; new tests seen failing before each fix; review: minor addressed skip-worktree entries omitted from export, minor addressed temp path not stripped under symlinked TMPDIR, minor addressed intent-to-add entries exported though not committed, minor addressed write-tree locked the real index, minor addressed git step failures shown as tracebacks, minor addressed sparse index hint noise, minor addressed export cleanup unasserted, minor deferred no suite test that the copy follows GIT_INDEX_FILE, minor deferred refusal does not say HEAD may already be broken, minor deferred missing index file traceback when run by hand, minor deferred manual run from a subdirectory reports reader not staged; reviewer: claude-code/claude-opus-5-5
- 2026-10-15T02:02:27Z (staged-facts-tree): gate: verified tree:a520690b48e7f387e1f332823aa1f5d1e165f0d4 — checks: just test 709 passed, .githooks suite 178 passed, real git commits in disposable hq clones through the new hook refuse deletion and index-only deletion and rename without reader and reader default moved without file and invalid content and allow the coordinated move, partial and -a commits follow the committed index, each new test seen failing before its fix; review: minor addressed skip-worktree entries omitted from export, minor addressed temp path not stripped under symlinked TMPDIR, minor addressed intent-to-add entries exported though not committed, minor addressed write-tree locked the real index, minor addressed git step failures shown as tracebacks, minor addressed sparse index hint noise, minor addressed export cleanup unasserted, minor deferred no suite test that the copy follows GIT_INDEX_FILE, minor deferred refusal does not say HEAD may already be broken, minor deferred missing index file traceback when run by hand, minor deferred manual run from a subdirectory reports reader not staged; reviewer: claude-code/claude-opus-5-5
- 2026-10-15T02:02:57Z (staged-facts-tree): retro: the disposable real-commit table settled the question in one run and doubled as the regression harness for the fix. Each fresh-context re-review surfaced a deeper git subtlety (skip-worktree, then intent-to-add, then the index lock), so exporting the committed tree through write-tree on a copied index came from the reviews, not the first design. A gate note's checks field must not contain ';' — I wrote a malformed gate first and superseded it.
- 2026-10-15T02:02:58Z (staged-facts-tree): done
  provenance: {"harness_session":"claude-code:12f40a0d-b227-408f-9d37-d05d8a87e20c","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-15T02:02:58Z (staged-facts-tree): Gap confirmed: the ACMR filter let commits delete, rename away, or index-only delete the fact file and move the reader default without the file. pre-commit now runs the staged tools/harness-facts check over the tree the commit will hold (write-tree of a copied index), refusing those while allowing a coordinated move. Deferred test: hq-aea33f.
  provenance: {"harness_session":"claude-code:12f40a0d-b227-408f-9d37-d05d8a87e20c","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
