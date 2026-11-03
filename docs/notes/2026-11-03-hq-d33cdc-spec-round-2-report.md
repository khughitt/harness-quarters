# hq test policy design: spec round 2

Full review supplied by the user. Reviewer identity supplied: `gemini-4-argon`;
the harness was not supplied and is not inferred. The controller recorded the
review round before revising the design and persisted this supplied report;
no reviewer-written file was supplied.

Verdict: Revise before planning (2 Important findings, 2 Minor notes).

Reviewed frozen commit `366e89c2f56cee6b9cd8918d62cb088960206bdc` (unchanged at
worktree HEAD `3bec69b8d2b5276f16943aca42f722f51abe37be`) of
`2026-11-03-test-execution-policy-design.md` for task hq-d33cdc against authority
ops-8bfa85, pilot ops-68729d, prerequisites hq-b01c0f and hq-0d26dc, and the
`.worktrees/hq-d33cdc` tree.

## Important findings

1. Hosted just check-hygiene fails in tools/ops-check when lore and ops are absent
   from the runner's tasks registry (design line 88, lines 110–111, line 143,
   lines 164–165).

   The design defines just check-hygiene as executing the existing
   pre-commit:33–46 validation path (hygiene_check → ops-check:526–565), requires
   .github/workflows/ci.yml to run mandatory hygiene (just check-hygiene), and
   prohibits private sibling checkouts (ops) in the public workflow.

   In references() of ops-check, a project prefix preceding a backticked path
   (lore or ops) resolves to that project only when prefix in projects (loaded
   from $XDG_CONFIG_HOME/tasks/projects.toml). Without lore and ops registered
   and present on disk, ops-check falls back to (root, "") (hq itself) and exits
   1 on 8 cross-project references in README.md:188 (lines 188, 213, 214, 242,
   353, 354 for lore; line 395 for ops) and AGENTS.md:35 (line 35 for lore).

   Fix: Specify how hosted CI runs hygiene without a private ops checkout —
   either by running the portable subset of pre-commit checks in CI (ops-docs
   check + staged-tree harness-facts and harness_state.py checks, while full
   check-hygiene remains a protected always-run local target in hook-pre-commit
   and hook-pre-push as in ops and lore), or by defining how cross-project
   reference checking behaves when projects.toml is absent on the runner.

2. just ci-test setting TT_FORCE=1 alongside broad_targets = ["test"] prevents
   hosted-skip refusal on the CI entry point (design line 80, line 89,
   lines 115–123, lines 143–144, line 188).

   The design states that test is the only target in broad_targets = ["test"]
   (line 80, lines 115–118) and that just ci-test sets TT_FORCE=1 inside the
   recipe itself ("explicit TT_FORCE=1, the same suite partitions, bounded
   hosted workers and no development-host allocator", line 89; "Set TT_FORCE=1
   explicitly at job scope as well as in the CI entry point", lines 143–144),
   while also requiring that "A hosted would-be skip without TT_FORCE=1 fails,
   including nested calls" (lines 122–123, line 188).

   Because just ci-test cannot call just test (which requires local host-budget
   with no unbudgeted fallback), just ci-test is a separate recipe. In tt v10
   (execution_decision), hosted skip refusal (GITHUB_ACTIONS == "true") triggers
   only when TT_FORCE is unset, target in policy["broad_targets"], and not
   policy["automatic_broad"]. If just ci-test either sets TT_FORCE=1 in the
   justfile or runs under target ci-test with broad_targets = ["test"], invoking
   GITHUB_ACTIONS=true just ci-test without TT_FORCE=1 in the workflow environment
   will never fail, and running just ci-test locally under automatic_broad = false
   would bypass policy and run an unbudgeted broad suite.

   Fix: Include ci-test in broad_targets = ["test", "ci-test"] and set TT_FORCE=1
   in .github/workflows/ci.yml (not inside the just ci-test recipe), matching the
   other host-budget adoptions under ops-8bfa85 (atoms, sci, beliefs, ns).

## Minor notes

3. Static test-module count is 57, not 58 (design line 41).

   agents/bin (2), .githooks (7), and tools (48) contain 57 test_*.py modules; the
   58th file matching *test.py in those directories is conftest.py.

4. Four-partition report retention cannot rely on TT_JUNIT_DIR after tt exits
   (design lines 91–93, lines 146–148).

   tools/tt deletes its temporary TT_JUNIT_DIR in finally before returning. For
   the workflow to upload/retain and reconcile all four runner reports while
   sharing one suite definition between just test and just ci-test, the shared
   suite definition or ci-test will need a caller-owned evidence directory (or
   distinct per-partition report paths outside TT_JUNIT_DIR).

Reviewer: `gemini-4-argon`.
