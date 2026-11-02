---
id: hq-cffc71
title: Default harness sessions to small runner worker counts so unbudgeted runs cannot take the whole host
status: doing
priority: 1
size: s
complexity: mid
process: direct
owner: hq-cffc71-worker-defaults
created: 2026-11-01T23:43:00Z
updated: 2026-11-02T00:48:45Z
started: 2026-11-02T00:02:05Z
depends: []
tags: [hooks]
agent: claude-code/claude-opus-5-5
origin: user
---

Hub goal: ops-4adbbe.

Problem: host-budget only protects a job that asks for it. A runner started bare (`pytest -n auto`, `cargo build`, `cargo test`, nextest, Go tests, BLAS-backed numeric code) sizes itself from the full CPU count. On titan that is 32 workers per invocation, and several agents can do it at once.

Do: give every agent harness session a conservative default for the worker variables host-budget already manages, so an unwrapped run starts small instead of starting at full width. Candidates: PYTEST_XDIST_AUTO_NUM_WORKERS, CARGO_BUILD_JOBS, RUST_TEST_THREADS, NEXTEST_TEST_THREADS, GOMAXPROCS, and possibly the BLAS/OpenMP library variables (see the caveat). A starting value is 4. Deliver it through hq's declared harness settings (claude/settings.json `env`, and Codex's and the other harnesses' equivalents), so it reaches every session's tool shell.

Known facts: host-budget `run` overwrites these variables with the granted values (bin/host-budget, the WORKER_VARS and LIBRARY_VARS env.update), so a budgeted job still gets its full grant.
Caveat to settle: ops AGENTS.md notes that `nproc` honours OMP_NUM_THREADS. Setting OMP_NUM_THREADS harness-wide changes what `nproc` reports to every tool in the session; check whether any tool sizes itself from `nproc` (host-budget reads `nproc --all`) before including the library variables.

Done when a fresh session's Bash shell shows the defaults, a bare `pytest -n auto` starts the default number of workers, and `host-budget run` still grants its computed count.

## Notes

- 2026-11-01T23:43:00Z (add): created
  provenance: {"harness_session":"claude-code:029eacc3-b922-4a57-bd6b-7fcb7ca9ead1","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"user"}
- 2026-11-02T00:02:05Z (main): started
  provenance: {"harness_session":"claude-code:cc9d0598-86ea-48e9-8298-c41d9389039b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T00:02:24Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-11-02T00:02:27Z (main): arm: flow-trial-1 — unit tack-cffc71 — flow off
- 2026-11-02T00:03:54Z (hq-cffc71-worker-defaults): resumed
  provenance: {"harness_session":"claude-code:cc9d0598-86ea-48e9-8298-c41d9389039b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-02T00:16:50Z (hq-cffc71-worker-defaults): caveat settled: library vars excluded. titan's /etc/environment pins OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1 (so nproc reports 1 there); a harness-wide 4 would raise them. host-budget counts CPUs from /proc/stat, not nproc. OPS_BUDGET/OPS_WORKERS also left unset: they mark a host-budget grant.
- 2026-11-02T00:16:53Z (hq-cffc71-worker-defaults): scope: defaults (PYTEST_XDIST_AUTO_NUM_WORKERS, CARGO_BUILD_JOBS, RUST_TEST_THREADS, NEXTEST_TEST_THREADS, GOMAXPROCS = 4) go in claude/settings.json env, codex/config.toml shell_environment_policy.set, and pi/bin/pi (keeps a value it was given); tools/test_worker_defaults.py holds them equal. Not covered: agy (no env setting found in agy 1.4.12 settings; binary not hq-launched), and the work homes (local/claude/settings.work.json, local/codex/config.work.toml are untracked host settings, left for the user).
- 2026-11-02T00:29:41Z (hq-cffc71-worker-defaults): baseline: host-budget run -- just test at worktree creation, exit 0, 25 min; last stages 1417 + 391 + 1 passed (earlier stage counts lost to a tail pipe). Edits landed mid-run, so a second full run on the edited tree is the commit gate.
- 2026-11-02T00:48:42Z (hq-cffc71-worker-defaults): verification: gate host-budget run -- just test on a2ebc48c, exit 0: 268 + 1421 + 391 + 1 passed (tools stage +4 = tools/test_worker_defaults.py). RED->GREEN on the new test (4 failed, then 19 passed with test_pi_launcher). Bare pytest -n auto: 'created: 4/4 workers' with the default, 32/32 without. host-budget run replaced an inherited 2 with its grant (1 at the time, host busy). Fresh claude -p --settings <worktree claude/settings.json> shell showed all five = 4 and OMP_NUM_THREADS=1 (host value); codex exec -c shell_environment_policy.set=<worktree value> showed all five = 4. The main-home check (no override) runs after the merge.
- 2026-11-02T00:48:44Z (hq-cffc71-worker-defaults): merge blocked: main's working codex/config.toml has uncommitted Codex hook trust_hash/trusted_content_hash changes (written 2026-11-01 15:35, after the 13:19 hooks.json commit 6273c206), not this task's. The branch also edits that file, so git merge refuses. README warns against stashing harness configs. Recommended: commit those hashes on main as their own chore(codex) commit, then merge hq-cffc71-worker-defaults. Alternatives: the user commits them; or stash/merge/pop (live file briefly loses the hashes). Retained: .worktrees/hq-cffc71 (locked, branch hq-cffc71-worker-defaults at a2ebc48c, unmerged); session scratch discarded; host-load --section session: nothing left running.
- 2026-11-02T00:48:45Z (hq-cffc71-worker-defaults): parked (waiting on user, decision): On the user's go-ahead: in main, commit codex/config.toml's hook trust hashes as chore(codex), merge hq-cffc71-worker-defaults, run env check in a fresh Claude and Codex session from main, then tasks done and remove .worktrees/hq-cffc71
  provenance: {"harness_session":"claude-code:cc9d0598-86ea-48e9-8298-c41d9389039b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
