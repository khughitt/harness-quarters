# Rename receipt design — spec review round 2

Reviewer: claude-code/claude-opus-5-5, supplied in the relayed review.
Reviewed repository: hq. Commit: f975b51ceb554f9df229d10d22b6f10314c436ab.
Reviewed path: docs/specs/2026-11-09-rename-receipt-design.md.
Reviewed sha256: 355f81998253019b544ee39147f6b49f30673a21bfa542b7a0c11d077699db24.
Task: hq-74f102. Verdict: accept. Findings: minor 2.

Persistence: no plan workspace existed at review. The user relayed the full review;
the controller saved it here. No report write attempt or refusal was reported.
The user's approval for planning follows the review below.

## Full review

Verdict: accept. Revision 2 resolves all three round-1 items. Two small gaps remain, and the implementation plan can carry both without a revision 3.

I reviewed hq commit f975b51c; its sha256 matches the task note. Reviewer: claude-code/claude-opus-5-5. The agent that resumes hq-74f102 should record this as review: spec round 2 — verdict: accept; findings: minor 2. Approving the design is still your call.

Round-1 items

- Real-hook check: resolved. The in-tree success case now runs hq's normal pre-commit hook, not --ci or a stand-in. It runs before anyone edits the identity file or guides, with an isolated registry, HOME and Git. If it fails, the design comes back for amendment instead of getting a workaround.
- Warnings: resolved. apply will print every warning from a successful commit, and output it can't parse stops apply.
- Config commit: adopted. apply now makes the detached config commit itself. The spec states what a failure after the move leaves behind (the rename is committed, the config may not be), and rollback still covers it. I checked that an in-tree config holds no checkout path, so in-tree needs no matching commit.

Remaining minors for the plan

1. Pass --json on both tasks commit calls. tasks prints JSON by default, but setting TASKS_FORMAT=pretty switches it off (src/output/mod.rs:25). In that case the new check on the output would stop apply after the rename commit already succeeded. Recovery is a rollback, but the failure is avoidable. The tool already passes --json to tasks projects and tasks resolve.
2. Say whether the real-hook case is a permanent test or a one-off recorded rehearsal. The spec's "record actual hook output" reads like a rehearsal. As a permanent test it would need the ops checkout reachable through the registry, which ops-check requires. The guide already treats ops-check as unusable in hosted CI, and hosted CI accepts exactly three listed local-only tests. The plan should either keep it a recorded rehearsal or add it to that list in docs/test-execution.md.

The real-hook check is still unproven: it runs during implementation.

## Human approval

Keith: approved for planning
