# Rename receipt design — spec review round 1

Reviewer: claude-code/claude-opus-5-5, identity supplied in the relayed review.
Reviewed repository: hq. Commit: 92f1152cc04a373082be3c3a5e209466e6e4fb86.
Reviewed path: docs/specs/2026-11-09-rename-receipt-design.md.
Reviewed sha256: 1ed9037e360eb205f12c451be99294d2d818e3d513b100be81ce641a76f6bff1.
Task: hq-74f102. Verdict: revise. Findings: Important 1, Minor 1; suggestion 1.

Persistence: no plan workspace existed at review. The reviewer wrote no task note
or report file; the user relayed the full review and the controller saved it here.
No report write failure was reported. Review text follows.

## Full review

**Verdict: revise.** The approach is sound and the code backs it up. I'd fix two gaps before approving, and there's one simplification worth taking.

I reviewed the frozen revision: hq commit 92f1152c, `docs/specs/2026-11-09-rename-receipt-design.md`. Its sha256 matches the one recorded on the task. Reviewer: claude-code/claude-opus-5-5. I wrote no task note; whoever resumes hq-74f102 records this as `review: spec round 1`.

**What checks out against the code**
- **The receipt route works before the move.** `validate_rename_receipt` compares the receipt's records path with the project's current one, and checks the frozen config digest (tasks `src/commands/commit.rs:392`). Before the move both still match. After it, the in-tree path differs and the detached `init --force` has rewritten the config. So the spec's reasoning for committing before the move is correct.
- **A refused commit fails loudly.** A deferred commit (something already staged, detached HEAD) or one the hook refuses makes `tasks commit` exit non-zero and keeps the receipt (`commit.rs:379`). `run()` in the tool turns that into `Stop`. The spec's extra check that the receipt is gone is a sound backstop.
- **"Git may already have committed" is accurate.** The receipt is removed only after the commit lands (`commit.rs:382`).
- **The commit scope matches the old printed command.** For a detached checkout, `rename_commit_paths` limits the commit to `<old>` and `<new>`. In-tree, it commits `tasks/` only.
- **The printed config commit is valid.** A `tasks/.config.toml` path target is exempt from the retired-prefix check, needs `-m` (the spec gives one), and `-C` is a real global flag.
- **Rollback covers the new failure points.** `move_back` handles a checkout that never moved. Rollback replaces the state directory whole, so a leftover receipt goes. The in-tree reset and the scoped restore in the records repository both undo the new commit.

**Findings**

1. **Important: in-tree, `apply` now runs the project's own pre-commit hook before the runbook has edited its guides, and nothing tests that.**
   - The hq rename runbook (`docs/specs/2026-10-06-rename-to-hq-design.md` step 4) edits identity and guides "the pre-commit hook checks" before its single commit at step 8.
   - Under this design, the in-tree commit happens right after `tasks rename`. The hook then runs `ops-check` and `ops-docs check` against a tree with the new prefix and the old guides.
   - Reading the code, I expect it to pass: identity comes from `identity.toml`, and old ids resolve through the retired prefix. I have not shown that it does.
   - The sandbox projects have no such hooks, and the only hook test is an injected refusal. If the hook does refuse, every in-tree cutover stops in `apply`. That is safe (rollback works) but makes the cutover unusable.
   - Fix: add an acceptance case that runs the in-tree commit with a real hooks path (for example, a sandbox copy of hq with `core.hooksPath=.githooks`), or say in the spec what the hook is expected to accept at that point.

2. **Minor, but it silently drops instructions: `apply` ignores the warnings `tasks commit` prints when it succeeds.**
   - A successful commit can still warn. When the predecessor's config lives in a separate repository, it warns "predecessor config is in a separate repository; run `tasks commit --project …`" (`commit.rs:229`). It also warns about recovered staged changes left uncommitted.
   - `run()` discards stdout, and `verify` only looks at the paths the cutover owns, so nothing would ever surface these.
   - Fix: say that `apply` parses the output and stops on, or at least prints, any warning, as `committed_check` already does for `retarget`. Add a test for it.

3. **Suggestion: have `apply` run the scoped config commit itself instead of printing it.**
   - The config change comes from `apply`'s own `init --force`. Once `apply` already runs one commit with hooks, also printing a second one leaves an operator step with no clear reason, and the spec doesn't give one.
   - Running it keeps one rule: `apply` commits what it writes, and the runbook commits its own edits.
   - If there is a reason to keep it manual (for example, where a hook refusal should stop), the spec should state it.

The rest is fine:
- Doing both the save-time refusal and the guard relaxation is small and justified. A leftover `rename/<old>.toml` still needs the relaxation.
- The amendment names the sections it changes.
- The rejected alternatives are reasoned.

Approving the frozen revision as it stands is your call. If you'd rather have a revision 2 first, it should address findings 1 and 2.
