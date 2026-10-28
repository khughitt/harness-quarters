Ready to merge for hq-3b9c4c and obs-5bd975: this review found **0 Critical, 0 Important, and 0 Minor findings**. The controller can record acceptance, finish task closeout, and perform the authorized local integration. This verdict covers repository changes, with live rollout still owned by hq-624351.

Reviewer identity: **codex/gpt-6-astra**, verified during this review by `timeout 2 relay model --harness codex --pretty` (exit 0).

### Strengths

- **The complete response is validated before deletion begins.** `.worktrees/hq-3b9c4c/tools/session_archive/inputs.py:34` checks envelope, required fields, numeric types, readiness consistency, fingerprints, observations and harness identity. `load_obs_state` returns only after every row passes. The CLI constructs its context afterward, so a malformed later row cannot expose an earlier unit to deletion. The CLI regression at `.worktrees/hq-3b9c4c/tools/test_session_archive_prune_run.py:261` verifies failure, unchanged transcript bytes and no quarantine.

- **Historical link paths remain distinct.** `.worktrees/hq-3b9c4c/tools/session_archive/inputs.py:94` retains exact path strings and rejects every duplicate; `.worktrees/hq-3b9c4c/tools/session_archive/prune.py:81` uses the same exact lookup. The link/target regression uses two distinct keys with different missing states, directly exercising the original failure.

- **Fresh identity and indexed bytes both constrain eligibility.** `_facts` takes device/inode from the descriptor used to hash the live file. `.worktrees/hq-3b9c4c/tools/session_archive/decide.py:77` requires matching harness, complete indexed span, live version, device/inode and indexed/live/archive digests, plus matching Codex identity. The production-path tests at `.worktrees/hq-3b9c4c/tools/test_session_archive_readiness.py:45` and `:58` isolate equal-byte inode replacement and preserved-stat rewrites respectively.

- **Forward-compatible evidence stays conservative without stopping unrelated work.** Unknown harness identities remain opaque after common validation; they cannot certify known sources. Unknown reasons are accepted as non-ready evidence. Missing evidence remains `unindexed`; other unusable valid evidence remains `index-stale`.

- **The coordinated probe now tests production wiring.** `obs worktree: tools/retention_readiness.py:234` uses each extracted reader’s own capture, manifest, context and `_facts`, with actual archive read-back and the original producer snapshot. It preserves the historical baseline and avoids introducing a compatibility interface into HQ.

- **Existing preservation protocols remain connected.** I traced the Codex locked recheck, Claude quarantine re-verification, changed-byte recapture, no-replace restoration, and failed-delete preservation. The changed `_read_file` interface is adapted at every located caller; the old tail shortcut is removed.

### Issues

- **Critical: 0**
- **Important: 0**
- **Minor: 0**

No corrective round or newly deferred minor is required.

### Controller rulings assessed

- **Accept: explicit `LC_ALL=C.UTF-8`.** **Why:** it makes the child-environment regression deterministic while preserving the native environment synchronization needed for `env=None` children. **Cost:** the test/probe host needs that locale. Applies to Task 18 implementation through `8d26e25` and the coordinated probe at `49388f6`.

- **Accept: reuse the successful complete gate.** **Why:** the raw HQ log contains all four required segments, and the runtime/test bytes at reviewed HEAD `9c070fc` match implementation commit `8d26e25`. The approved plan expressly permits reuse for subsequent record-only work. **Cost:** completion relies on the retained gate evidence instead of a duplicate helper-generated run. Reference: approved plan `0154323`, Task 19 Step 5; recorded ruling and lore-07bd6b.

- **Accept: include the discovered `tasks` executable directory plus `os.defpath`.** **Why:** actual OBS indexing requires `tasks`; the helper builds a fresh environment with temporary HOME/XDG paths, fake credentials and isolated Git configuration. **Cost:** the probe requires installed `tasks` and permits other executables from that directory. Reference: `obs worktree: tools/retention_readiness.py:38`, commit `49388f6`, implementing plan `0154323` Task 19.

### Verification and limits

I personally inspected both frozen diffs, the frozen requirements, connected producer/consumer code, regression assertions, raw verification logs and paired acceptance output. Both range whitespace checks passed. Both worktrees remained clean at their supplied review heads.

Controller-run evidence inspected:

- HQ full gate: **1,793 passed** across 231 + 1,170 + 391 + 1; the final isolated segment additionally reports 154 deselected.
- HQ focused reader/decision/CLI checks: **214 passed**; protocol/probe checks: **76 passed**.
- OBS focused checks: **21 passed**; full gate: **1,633 passed**.
- Paired acceptance: **11 cases**, with only `current` and `claude_current` eligible against strict revision `8d26e255ef974467c0c8102fa65ce44892eca3c0`. The raw and attached JSON documents are identical.
- OBS adapter code at reviewed HEAD `56fbc21` matches tested implementation `49388f6`; HQ code likewise matches its tested consumer commit.

I did not rerun tests or the probe. No unresolved code uncertainty justified duplicating those checks.

### Declined to judge

- **Successor-link retention and races:** existing tests characterize broken links and stranded quarantine entries; the approved scope explicitly leaves their policy to hq-1639fd and hq-9e64f4. This review does not clear those rollout gates.
- **Live installation, installed Codex behavior, real-store pruning and timer enablement:** these require hq-624351’s separate rollout checks and authorization.
- **Archive replay, aliasing, deduplication and additional source enablement:** these remain separately scoped dependencies; the retained historical probe characterizations do not establish their readiness.
- **Ancillary full-suite warnings:** optional Swagger support, task-tag warnings and database ResourceWarnings were not investigated as part of these consumer/probe changes.

### Assessment

**Ready to merge: Yes.** The implementation satisfies the approved strict-consumer requirements and the five review focus points, with production-path acceptance evidence and preserved deletion safeguards.

No task note or report file was written, no repository changes were made, and nothing was pushed. Both branches remain in their supplied worktrees for controller-owned local integration; `host-load --section session` reported nothing left running.

Skipped: repeated suites and live-host checks. Remaining risk: repository acceptance does not authorize pruning before the separate successor-link and rollout gates are resolved.
