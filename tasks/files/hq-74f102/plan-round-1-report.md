# Plan review round 1

Reviewer: claude-code/claude-opus-5-5 (supplied in relayed review).
Reviewed: hq commit be04346961dfae9cd1950d2800c8cd6794e4bbe1, docs/plans/2026-11-09-rename-receipt.md.
SHA256: 492ba5799dbc33e95cb69a977f54018309a66edceec034ef70a57a259b622f6c.
Persistence: full review relayed by user; controller saved it after initializing the execution workspace. No reviewer write failure was reported.

Verdict: revise, for one concrete defect. The fix is a one-word name change. A recorded Ruling: at execution is enough; it doesn't need another review round. The rest of the plan is sound.

I reviewed hq commit be043469 at docs/plans/2026-11-09-rename-receipt.md; its sha256 matches the task note. Reviewer: claude-code/claude-opus-5-5. Note to record: review: plan round 1 — verdict: revise; findings: Important 1, Minor 2.

Defect (Important)
1. The rehearsal's rename target is not a valid prefix. Task 2 Step 2 runs tasks --json rename hq receiptprobe. tasks only accepts prefixes of 2–8 characters, lowercase letters then letters or digits (is_valid_prefix, tasks src/model.rs:267). It checks this on a rename target (src/registry.rs:369, 409). receiptprobe is 12 characters, so the rename would be refused before the hook ever runs. Use something like hqprobe.

Minors
2. Run the real hook once on the unrenamed copy first. Step 1 allows replacing hq's task records with two synthetic ones. That can make the hook fail for reasons of its own making: ops-check resolves guide references, and the guides cite real task ids. Step 3 then has to tell fixture gaps apart from an ordering conflict, with nothing to compare against. Either keep the real committed records (they are already in the pinned commit), or require the baseline commit to pass the same normal hook before the rename. Then a failure after the rename clearly comes from the rename.
3. Merge main before Task 2, not after. Main has moved, and the only change is tools/family.toml, which ops-docs reads. The plan's freshness rule would then force a second rehearsal after the merge. Merging before Task 2 means the rehearsal runs once, against the hook inputs that will actually ship.

Checked and fine
- --json is a global flag (tasks src/cli.rs), so tasks --json commit … parses. The commit output is a top-level object whose warnings field is always present, so treating a missing warnings field as malformed won't fire on a clean commit. Task 1's whole-cutover tests run the real command, so this shape is also checked end to end.
- GIT_TRACE passes through tasks' git call, so it does prove the hook ran. The hook's own output may be lost when the commit succeeds, which the plan already accepts.
- The plan carries both spec round-2 minors (--json on both commits, a local rehearsal with no new hosted-CI omission) into Task 1 and Task 2. The five review-focus items each have an assertion. Inline execution is reasonable for one script and its fixture.
- Optional, not required: the rehearsal calls tasks directly rather than tools/rename-cutover apply. That meets the spec's wording; running apply itself would cover more, but needs the link tool's inputs.
