# SDD ledger — plan: docs/plans/2026-10-10-live-model-preservation.md
Execution: native inline; trial flow on.
Base: 00ff13950ac77ef2d3c3247a476f78749df8b5b8
Pre-flight: Task 1 → 5/6/8 facts consumed through harness-facts; compatible.
Pre-flight: Task 2 → 3/4/5 shared host lock and checkout mechanics; compatible.
Pre-flight: Task 3 → 4/5 CLI and record; compatible.
Pre-flight: Task 4/5 → 7/8 rollout hooks and capture; compatible.
Ruling: Run the probe supervisor through Codex exec with a 45-minute timeout instead of Claude background Bash — this harness has tracked exec sessions — cost if wrong: rerun the scratch probe.
Ruling: The trial requires flow review gates for each child despite executing-plans usual final-review-only cadence — obey the enrolled trial — cost: extra reviews.
Task 1: prerequisite failed: PostModelSwitch observes previous settings; same-resolved-model Default produces no event. No implementation starts.
Ruling: Supplement Opus→Default with Sonnet→Default — distinguish missing event on the same resolved model from event ordering on a real switch — cost if wrong: none to live homes.
Ruling: Draft the spec fallback using Stop capture and forget for both harnesses; omit PostModelSwitch wiring — explicit capture cannot satisfy the observed ordering — cost: picker resets require forget and Claude gains a turn-end capture window.
Ruling: Clarify invalid-live-file isolation in the revised spec — its old sentence contradicted its per-file refusal and the approved Task 3 test — cost if wrong: one malformed config does not prevent restoring the other.
Final: fixed probe cleanup claim — identified late Codex writer 2249705; terminated the exact recorded probe process; verified stopped and removed recreated residue; host-load reports no session processes.
Final: minor (deferred): probe supervisor checks for a serving tmux server rather than any existing stale socket; fix before reusing the script.
Verification: just test after facts change → 228 agents tests + 565 hook/tool tests passed; no code implementation began.
Task 1: complete (commits 00ff139..7f53166, tests: just test → 228 + 565 passed; reviewed cleanup accepted). Prerequisite false blocks Task 2 onward.
Final review for this increment: probe cleanup accepted after correction; revised spec accepted for human review; reviewer codex (model unknown).
Paused at human gate: revised spec review, then agent revises plan and obtains plan review before native implementation. Nothing left running; worktree clean.
Spec fallback human approval recorded (hq-a77096 spec round 2). Revised plan awaits separate human review; native inline preserved.
Plan self-review: capture/forget interfaces consistent across Tasks 3/5; acceptance cases 1/9/10 → Task 4, 2/11/12/14 → Task 5, 3-8/13/15 and Review Focus 1-5 → Task 3.
Plan Task 8 removed and corresponding task dropped; rollout Task 7 handles absent picks and requires a fresh branch review plus separate live merge approval.
Plan revision committed abe4795; user spec approval recorded; updated suite 228 + 565 passed. Parked for human revised-plan review; resume native inline at Task 2 after approval. No child/check remains running.
Task 2: RED just test → lock test failed with poll() == 0; 565 other hook/tool tests passed, 228 agent tests passed.
Task 2: Ruling: temporary fixtures also ignore __pycache__, matching the real checkout — importing the new shared module creates interpreter caches in those repositories — cost if wrong: caches are hidden from fixture status only. Apply the same rule in Task 3 fixture.
Task 2: Ruling: preserve unchanged codex-trust OSError propagation in this extraction — trust behavior is explicitly unchanged; later shell hooks run both tools — cost if wrong: standalone trust hooks retain their existing failure status.
Task 2: Ruling: preserve the existing index-lock check/add race — Git errors fail visibly and Stop retries; avoiding it requires changing the index protocol — cost if wrong: a racing Git operation can delay restaging until the next Stop.
Ruling: Record observed GREEN suite evidence directly instead of rerunning task-done solely to write the ledger — user requires no redundant suite reruns after passing — cost if wrong: ledger transcription is manual.
Task 2: complete (commits abe4795..6613456, tests: just test → 228 + 566 passed; fresh review accepted).
Task 3: RED just test → 39 expected missing-behavior failures, fixtures ran; implementation replaces empty CLI scaffold. Fixture bytecode ignore follows Task 2 ruling.
Task 3 review round 1: Important 1 — live-file absence/read/decode/write failures abort the other file and lose successful hook restaging; correction required.
Task 3: Ruling: failed forget has atomic individual writes but no cross-file transaction, as approved — failed resets report an error and require retry — cost if wrong: a record-write failure can remove the live pick before default is persisted.
Task 3 initial GREEN: just test → 228 + 606 passed. Review finding remains; added five regression cases for per-file failures.
Task 3 mutation RED: temporarily remove outer OSError catch so the pre-existing passing filesystem-error test sees its targeted traceback break; restore that boundary with the isolation correction.
Task 3 correction RED: just test → 6 failures (five isolation regressions + filesystem-error mutation), 605 hook/tool tests and 228 agent tests passed.
Task 3 fix: live missing/read/decode failures become Refused; restore target resolve/write stays inside per-file boundary; forget catches the new live refusal; global record/lock errors remain global. Outer OSError handler restored after mutation.
Task 3 correction GREEN: just test → 228 + 611 passed; fresh scoped review accepted with Minor 1, Important 0.
Final: minor (deferred): malformed UTF-8 in local/live-picks.json is refused safely but the diagnostic omits the record path and fix/delete guidance.
Task 3: complete (commits 6613456..89057ac, tests: just test → 228 + 611 passed; fresh correction review accepted).
Task 4 pilot: Git 2.56.0 runs post-checkout for both checkout -- and restore; scratch-only hook probe confirms approved coverage (git-restore-pilot.json).
Task 4 RED: new Git retention/error tests run before live-picks wiring; temporarily disable existing trust worktree skip to prove newly added isolation tests catch a targeted break of quiet worktree behavior. Restore it with hook wiring before GREEN.
Task 4 RED completed: Git retention/error/isolation tests failed as expected before pick-hook wiring and with targeted worktree-skip mutation. Mutation restored; hooks now run trust then picks.
Task 4: complete (commits 89057ac..36c55aa, tests: just test → 228 + 622 passed; fresh review accepted).
Task 5 RED: append Stop/reset/index-lock cases before refresh wiring; temporarily remove forget default assignment to prove new locked-reset cases catch stale-pick resurrection. Restore before GREEN.
Task 5 RED completed: Stop capture/restoration cases and locked-reset mutation failed; mutation restored. Refresh now runs plain capture before the index-lock check, then trust sync, pick restore and staging, and aggregates tool failures.
Task 5 initial GREEN: just test → 228 + 634 passed. Reviewer accepted with no new findings but excluded launch errors and lost tool diagnostics on later Git error.
Task 5: Ruling: re-grade excluded launch failures as Important — new capture dependency can block existing healthy trust recovery; failures must not suppress independent recovery — cost if wrong: a few lines of OSError handling.
Task 5: Ruling: preserve safe Git aborts but retain accumulated tool diagnostics — the promised error aggregation must remain visible after a Git failure — cost if wrong: additional stderr context only; no extra index operations.
Task 5 correction RED: just test → four new failure-continuation/diagnostic cases failed; 634 other hook/tool and 228 agent tests passed.
Task 5 fix: launch OSError becomes a labeled failed result so later tools and staging proceed; Git SystemExit is collected alongside tool stderr while aborting remaining Git operations safely.
Task 5: complete (commits 36c55aa..49d3430, tests: just test → 228 + 638 passed; fresh correction review accepted).
Task 6 docs drafted: README/guide/filter/trust-spec explain preservation, manual resets and shared lock; completed plan examples updated to verified per-file and launch-failure corrections. No behavioral code change.
Final review round 1: docs accepted; whole branch Important 1 and Minor 2 (one already recorded), reviewer codex/gpt-6-astra high. Git wrappers can return failed launch status after successful checkout; fix with RED→GREEN regressions and fresh scoped review.
Final: minor (deferred): rollout plan Step 2 prints only Claude model and omits modelSettings; when executing rollout snapshot every present owned field to satisfy Step 4.
Final correction round 1 RED: just test → all 12 new launch-failure cases failed; 638 other hook/tool and 228 agent tests passed. Fix three shell wrappers to invoke then exit 0; preserve stderr and post-rewrite stdin drain.
Final: fixed Git wrapper launch-failure status — test_a_pick_launch_failure_keeps_a_successful_checkout_successful and test_git_wrappers_keep_zero_status_when_pick_launch_fails RED→GREEN (12 cases); suite just test → 228 + 650 = 878 passed. Fresh scoped review follows.
Final scoped re-review round 2: accept; Critical 0 Important 0 Minor 0 new; reviewer codex/gpt-6-astra high. Original Important addressed. Previously deferred minors unchanged.
Task 6: complete (commits 49d3430..6e2bee2, tests: just test → 228 + 650 passed; ops-docs check passed; documentation accepted and final correction reviewed).
Task 7 pre-merge: branch leaves claude/ and codex/ tracked content unchanged; read-only baseline records every present owned field and absence (Claude model opus; modelSettings absent; Codex gpt-6.1-sol/high). Main tool-only commit 739c298 remains independent. No merge or live write performed.
Task 7 rollout approved and merged 83e07f4. Immediate fresh baseline Claude opus/modelSettings absent, Codex gpt-6-astra/xhigh (changed since approval-request baseline). Picks unchanged after merge; capture record exact; old trust lock safely unlinked. Main suite running at tree 9b08e1c86ee1fb9045c0ca6450567d2a272ada69.
Task 7: complete (rollout merge 83e07f4; just test in main → 228 + 650 = 878 passed; exact live picks/record verified; docs/facts/diff checks passed; fresh integration review codex/gpt-6-astra high accepted with no new findings).
Final combined review: Critical 0 Important 0 new; all Important corrections addressed; three deferred Minors retained. Verified merged tree 9b08e1c86ee1fb9045c0ca6450567d2a272ada69. Worktree and scratch evidence kept; execution ledger copied onto parent task before closure. No host pointer was repointed and no process remains.
