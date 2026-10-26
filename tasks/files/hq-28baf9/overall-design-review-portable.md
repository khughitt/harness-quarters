My verdict is **revise**: I found two Important issues and seven Minor ones. I reviewed the frozen revision 7 (hq 669b3d6, sha256 d5e388d0…, which matches the task's frozen-review note) and checked it against obs's merged reader code, which hasn't changed since 062b73e. I changed nothing. Your design review of this revision is still pending. The two codex rounds didn't raise either Important issue.

**Important**

1. **R26 now gets one case backward (§8.3 rule 3).** Revision 7 says a file with no unshared user or assistant record can't pass the timing test. That correctly settles the common case: an original that was wholly copied, plus a resume that added records. But the reverse case looks the same from shared uuids:
   - Original A has records r1–r3.
   - A resume or fork B is opened, copies r1–r3, and adds nothing.
   - The user goes back to A, which continues with r4.

   Now B can't pass the test and A can (r4 is later than all of B), so A is ruled the copy. A's opening records become `resume_history` copies of B, and their turns and finals move from A to the abandoned file. Revision 5 called this a tie, so it came out `ambiguous`. The code does exactly this (`session_logs_sessions.py:103-124`). The ledger's reasoning for R26 only considers the complete-resume case.

   I didn't measure how often Claude Code leaves a resume or fork file that adds no user or assistant record. The fixtures give no tiebreak either: copied records carry their own file's `sessionId`.

   Fix: either state this limit, with its Why and Cost, in §8.3 and §14.7, or keep the tie when the subset file has no other ordering signal. Count live subset pairs before choosing.

2. **§6.1 now promises something the amendment doesn't support.** §6.1 says excluding `metadata` means "the Codex event items that repeat response text never double a match." But A2 keeps several kinds as `unknown`, and `unknown` is matched by default: `exec_command_end` (76k), `agent_reasoning` (44k), `patch_apply_end` (73k), `mcp_tool_call_end` and `web_search_end`. By their names, these likely repeat command output and reasoning summaries. A2 itself says their mirror relationships are unvalidated, so the guarantee is at best unproven. Doubled hits would distort counts done with `jq` (SL6) and use up `--limit`.

   I couldn't confirm the duplication: none of the recent rollouts I sampled contain `exec_command_end`, which probably comes from older Codex versions.

   Fix: limit §6.1's sentence to the mirrors that §8.2 actually maps. Add to A2's Cost that `unknown` hits may duplicate response content.

**Minor**

- **Outside-root paths are a sample.** §4.6 says the paths of rows outside the roots are reported. The code keeps a sorted sample of 20 (`OUTSIDE_SAMPLE`), so the spec should say it's capped, as it does for the `files` lists.
- **`abort_reason` is unclear for Claude.** §4.4 defines it as Codex's `turn_aborted.reason`, but the code emits it on any interrupted turn that has a closing record. Say which harnesses carry it, and that Claude's value is `null`.
- **"Store search" isn't a defined scope.** §4.6 `sort_basis` and §6.4 use it, but §6.5 names the scope "store-wide". It's also unclear whether a `--session` search with several `own` files is grouped for duplicate detection.
- **The alias rule assumes `--since`.** §6.5 says "target's mtime is before `--since`", but the default 30-day window has no `--since`. It should say "before the window's start".
- **One §9.1 clause can never apply.** "The derived rule never closes on `turn_duration`": any file containing a `turn_duration` uses the marker rule.
- **The `turn_cut` window isn't specified.** §7.2 doesn't say how the retained window sits around the target line, so `before`/`after` can't be reproduced from the spec alone.
- **Ambiguous turns can still give `not_found` under `--final`.** This dates from revision 5, but it sits next to the new reasoning about copies. The new collapsed-copy rule makes text hidden in copies block `not_found`. An ambiguous turn from a fork with no readable parent may hold the fork's own matching final, yet an empty `--final` answer can still be `not_found`. Either block it with a basis or state that it's intended.
- I agree with the deferred M4 (§6.7's "as in §5.2" shorthand).

**What checks out**

- The 23-row `unknown` table sums to 2,096,004.
- The A1 version counts add up to 269 (127 + 142).
- The ordinal "physical line minus 2" arithmetic is consistent.
- The R19, R20, R26 and R30 text matches the code.
- The live index on $HOST has 0 of 26,315 rows outside the configured roots, so §6.5's "`--home claude-work` can answer `not_found`" still holds.

The task (hq-28baf9) is parked waiting on you. Its codex session holds the claim, so I wrote no task note, since reviewers write none. If you count this as round 3, its note would be: `review: spec round 3 — verdict: revise; findings: Important 2, Minor 7; reviewer: claude-code/claude-opus-5-5`.

Nothing was pushed or committed. I stopped one background probe and nothing of mine is still running. Branch `docs/hq-28baf9-reader-spec` stays unmerged and locked in `.worktrees/hq-28baf9`; it gets merged locally once you approve the spec or ask for a revision.
