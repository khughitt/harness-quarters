---
id: hq-7cf7c1
title: "Test suite subprocesses inherit the calling session's editor and pager environment, so exported editor variables fail the rebase-continue test"
status: doing
priority: 2
size: s
complexity: low
process: direct
owner: main
created: 2026-10-23T16:54:42Z
updated: 2026-10-24T12:21:06Z
started: 2026-10-24T12:21:06Z
depends: []
tags: [feedback, friction, "from:hq"]
---

Why: The reported rebase-continue failure is consistent with the current helper at aefbde9: .githooks/test_codex_trust.py git() invokes subprocess.run without env, and test_a_rebase_stopped_on_a_conflict_continues_after_the_stop_hook uses -c core.editor=true. An inherited GIT_EDITOR takes precedence. Other subprocess entry points in this same test module (trust, clean, refresh, and both Popen sites) also inherit the session. The report records a clean rerun with the editor exports removed; this scope pass checked code and history, rather than reproducing the failure.

Done: Give every subprocess in this module a fixture-owned environment built key by key: PATH, HOME in a temporary directory, the explicit variables the hook reads, and fake values for any credential. Exclude caller editor/pager exports and inherited git routing/config variables; isolate global/system git configuration. Before the first fixture repository write, assert that both git's top level and absolute git directory belong to the intended fixture. Preserve the existing trust, filter, locking and rebase assertions. Add a focused regression with synthetic editor/pager overrides, git routing/config contamination and a fake credential proving that the child remains isolated and rebase --continue succeeds. Establish RED and GREEN safely inside a disposable environment from the first run. Run the documented just test route before committing and record its segment counts.

Where: .githooks/test_codex_trust.py git/repo/trust/clean/refresh plus test_concurrent_syncs_leave_one_copy_of_each_table and test_codex_trust_waits_for_the_host_lock_live_picks_shares. Read the hooks it copies to identify their required environment. Keep changes within this fixture family; .githooks/test_live_picks.py and test_harness_state_refresh.py have similar helpers but a suite-wide conversion is outside this report's bounded fix. hq-27de48 separately owns tools/session_archive/testing.py. Do not change production hook behavior or add a generic subprocess framework.

## Original captured report

Running the repository suite from an agent session whose environment exports terminal-program variables (editor and pager overrides set to noninteractive values) produced one failure in a git-rebase-with-stop-hook test: a rebase continue that the test drives with a core.editor command-line setting failed, and the error named an editor false. Root cause: the test's git helper starts subprocesses with the inherited environment, and a GIT_EDITOR export outranks that core.editor setting, so the continue tried to open editor false and died. Expected: the suite passes whatever the calling session's terminal-program variables are. Suggested direction: the test's subprocess helper builds its environment key by key (at minimum unsetting editor and pager exports and inherited git variables) rather than passing the environment through. Verified in a fresh worktree before any change: the single test passes again with the three editor variables removed from the environment.

## Notes

- 2026-10-24T11:57:51Z (main): scope: scoped; checked aefbde9 and .githooks/test_codex_trust.py history (latest 71458ae): git/trust/clean/refresh and two Popen sites inherit the caller; the rebase test relies on core.editor=true. Scoped a P2/s/low/direct fix for this fixture family: explicit child environments, temporary HOME and isolated git config/routing, fixture-root assertions and synthetic contamination regression. Preserved the captured report; hq-27de48 remains separate. No production-hook or suite-wide refactor. Pre-write just test passed in an isolated environment: 231 + 1037 + 389 + 1 tests; this does not reproduce or fix the exported-editor failure.
- 2026-10-24T12:21:06Z (main): started
  provenance: {"harness_session":"codex:01a16ddb-03dc-7d82-b033-7af16f6371d3","harness_session_source":"CODEX_THREAD_ID"}
