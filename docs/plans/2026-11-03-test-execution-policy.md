# hq Test Execution Policy Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan inline, task by task, with flow's independent reviews. Steps use checkbox syntax. Human review of this complete plan precedes implementation; external activation has separate gates.

**Goal:** Keep focused tests and local hygiene active while moving routine broad
regression verification to a forced, observable GitHub-hosted suite.

**Architecture:** A landed, unchanged tt copy decides before local budget allocation
or hosted execution. One suite driver preserves the four existing partitions and
durable evidence; local and portable hosted hygiene reuse the existing hook checks.

**Tech Stack:** Python standard library, existing pytest/xdist, just, shared tt and
host-budget, GitHub Actions. No new third-party library.

**Spec:** [Approved design](../specs/2026-11-03-test-execution-policy-design.md),
frozen hq revision `da5e8ace1327c4eea5ce77c8e1a6355eb65d31af`. Keith approved it
for planning; spec round 4 records the supplied gemini-4-argon acceptance.

## Global constraints

- Work in `.worktrees/hq-d33cdc`, branch `feat/hq-d33cdc-test-policy`; base main.
  Reuse and hydrate it. The user's baseline-test waiver applies to this adoption,
  including implementation Setup; it does not waive focused RED-to-GREEN, hygiene
  or the independent requirements of the prerequisite tasks.
- Keep policy absent/enabled through preparation and accepted hosted verification.
  Activation writes exactly automatic_broad=false and broad_targets=[test, ci-test].
  A skip is neither a pass, a test sample nor a latency obligation.
- tt classifies both broad entry points. Only the workflow sets hosted TT_FORCE=1.
  test-full alone provides the explicit local forced alias. Do not infer force,
  supply it in ci-test, or create an unbudgeted local fallback.
- Full local pre-commit/pre-push hygiene remains mandatory. Hosted hygiene excludes
  registry-dependent ops-check explicitly; never fabricate a sibling registry or
  add private credentials to the public workflow.
- Before activation, follow hq's enabled-policy code-commit checks, including its
  documented `just test` requirement. Those runs are commit verification, not
  baselines. After activation, use focused evidence and mandatory hygiene without
  broad reruns solely for commits, review rounds or task boundaries.
- New tests build subprocess environments as allowlists with temporary HOME/XDG paths,
  fake credentials when relevant, isolated Git configuration and no inherited
  GIT_* settings. Assert fixture top level and internal git-dir before its first
  write. Keep archive tests on fixture stores; do not touch live harness homes.
- No new selector, broad lint workload, scheduler, global instruction change,
  host pointer or persistent service. Publishing, account changes and hosted
  invocation require the concrete activation approval described in Task 4.

## Review focus

1. A skip still starts host-budget or a runner: Task 1 proves both marker files
   absent, and null skipped outcome fields, for test and ci-test.
2. Missing workflow force silently executes or skips: Tasks 1 and 3 prove direct
   and nested ci-test refusals with GITHUB_ACTIONS=true and policy off.
3. A green aggregate hides a missing partition, module or individual test: Task 1
   reconciles identities and exercises equal-count replacement, collection skips,
   duplicate partitions, missing files and interrupted execution.
4. Full local checks leak into hosted CI, or CI drops a staged safety check:
   Task 2 exercises the portable subset without any registry and each failure path.
5. Reports vanish after tt cleanup or only survive successful tests: Task 1 checks
   caller-owned bytes after wrapper exit, preserves failure evidence and rejects
   stale/nonempty output directories; Task 3 always uploads them.

## Existing prerequisites and execution records

| Plan step | Record | Dependencies |
| --- | --- | --- |
| 1: routes and evidence | hq-b8c340 | hq-0d26dc, hq-b01c0f |
| 2: hygiene and push hooks | hq-561c81 | hq-b8c340 |
| 3: hosted preparation | hq-b32d19 | hq-561c81 |
| 4: approved activation | hq-c7e52c | hq-b32d19 |

Do not duplicate hq-0d26dc or hq-b01c0f. Before Task 1, deliver or integrate them
using their existing records, in that order: explicit system Python first, then
budgeted local test/test-one recipes. They remain separately owned/scoped, with
their own trial arms and checks. If another session holds one, wait for that
delivery. If this executor delivers them, reuse the coordinated worktree, claim
each record before its changes, follow its requirements and release it afterward.
Do not apply this adoption's baseline waiver to those records. Add both as Task 1
dependencies; keep their original bodies/source/origin and do not reparent them.

hq-b01c0f introduces the missing documented focused route. Until it does, its
executor records the focused-route gap and uses the existing documented route,
rather than inventing a bootstrap runner or calling an unrecorded test command.
Its worker-budget proof must observe background.slice and the granted worker count
under host-load. hq-0d26dc must prove os.pidfd_open under the recipe's interpreter.

On approved execution, create and immediately record the external workspace
`$WORK_ROOT/hq/hq-d33cdc/plans/2026-11-03-test-execution-policy/`, owned by open
hq-d33cdc. Use the current host's declared WORK_ROOT; missing/inaccessible storage
fails visibly. Do not create `.superpowers/sdd`, symlink it, or move old workspaces.
Record the initial frozen plan repository/path/revision and keep this mapping
across revisions. The task directory is a namespace, not a second scratch identity.

Resolve lore's checkout through `tasks projects`. From the code worktree use its
explicit `bin/plan-task-start WORKSPACE PLAN N` and
`bin/plan-task-done WORKSPACE PLAN N BASE -- just test-one <focused arguments>`.
Read the generated brief, preserve BASE, and pass explicit external output paths
to task-brief/review-package. Each review gets a distinct package/report name and
ledger entry; children cite the parent's workspace without duplicate retention.
Keep every attempt log. Completion needs meaningful focused evidence, hygiene,
committed implementation and the required independent review, not just exit 0.

At park/done, apply retention 1: versioned objects, complete manifests outside
their containers, exact committed checkpoints and explicit open owners. Worktree
removal does not remove the external workspace. Preserve ledger rulings/deferred
minors on the task before separate, checked evidence disposal.

## File and interface map

| File | Responsibility |
| --- | --- |
| justfile | Public test/hygiene routes; policy before budget; composition only |
| tools/tt, tools/README.md | Unchanged landed vendor distribution |
| tools/test-suite | Single partition definition, runner orchestration and evidence reconciliation |
| tools/pytest_evidence.py | Collected node identities and matching JUnit testcase properties |
| tools/test_test_execution.py | Real just/tt contract fixtures and small pytest evidence fixtures |
| .githooks/pre-commit | Existing full local validation plus an explicit portable CI mode |
| .githooks/pre-push | Landed shared ref/coverage template |
| .githooks/test_pre_commit.py, .githooks/test_pre_commit_facts.py | Portable-mode safety and staged-tree regression checks |
| .github/workflows/ci.yml, tools/test_ci_workflow.py | Hosted setup, force, triggers, evidence upload and workflow contract |
| AGENTS.md, README.md, docs/test-execution.md | Current commands, coverage limits and activation state |
| .gitignore | Regenerable .tt/, .pytest_cache/ and .ci-tools/ |
| .tt.toml | Activation only; the exact two broad targets |

## Frozen setup choices for implementation

Use ubuntu-24.04's system `/usr/bin/python3` consistently, including every
`uv run --python /usr/bin/python3 -m pytest` invocation and shebang child. Check
its version and os.pidfd_open; do not substitute a managed Python lacking pidfd.
Pin uv 0.13.7, just 1.59.0, pytest 9.2.0, pytest-xdist 3.8.0 and Node 26.13.0.
The latter matches the current host and supports the existing native TypeScript
extension. Build the public tasks CLI with Rust 1.99.1, Cargo.lock and
`--locked --release`, at `fa58ab31acd757f59798537b6957e540fdccb9fb`.
GitHub confirmed that commit is published. The installed local tasks d4f2ed4
was unavailable remotely (HTTP 422); it is not the CI pin or equivalent evidence.
Exercise tasks-dependent fixtures with the pinned CI binary during the pilot.
An incompatibility is a named portability blocker, not permission to omit tests.

Pin actions to these already adopted revisions, verifying upstream before use:

| Action | Commit |
| --- | --- |
| actions/checkout | 3d3c42e5aac5ba805825da76410c181273ba90b1 |
| astral-sh/setup-uv | 11f9893b081a58869d3b5fccaea48c9e9e46f990 |
| extractions/setup-just | 53165ef7e734c5c07cb06b3c8e7b647c5aa16db3 |
| actions/setup-node | 820762786026740c76f36085b0efc47a31fe5020 |
| actions/upload-artifact | 043fb46d1a93c77aae656e7c1c64a875d1fc6a0a |

System apt capabilities are zsh and libatomic1; record actual package versions in
the setup report. Install just, uv, Node and the built tasks executable into the
disposable runner's system executable directories because fixtures use restricted
PATHs. This is a workflow instruction, never a host-install instruction. Disable
implicit Python installation in uv and Node package-manager caching. No pi/relay
install or private sibling checkout is needed.

Sources: [Node release](https://nodejs.org/en/blog/release/v26.13.0),
[uv release](https://github.com/astral-sh/uv/releases/tag/0.13.7),
[pytest release](https://docs.pytest.org/en/stable/announce/release-9.2.0.html),
[xdist release](https://pypi.org/project/pytest-xdist/3.8.0/),
[pytest identity properties](https://pytest.org/en/stable/how-to/output.html#record-property).
Record any necessary pin correction as a plan deviation with evidence; never
quietly float to latest or guess a fixing version.

### Task 1: Add policy-aware test routes and durable suite evidence

**Files:** justfile, tools/tt, tools/README.md, tools/test-suite,
tools/pytest_evidence.py, tools/test_test_execution.py, .gitignore,
AGENTS.md, README.md and docs/test-execution.md.

**Interfaces:**
- `test-one +args` invokes tt test-one → host-budget → the pinned pytest on the
  system interpreter. Forward every argument intact; zero args refuses.
- `test` invokes tt test → host-budget → private `_test-suite` recipe.
  `ci-test` invokes tt ci-test → that same recipe, requiring an explicit positive
  PYTEST_XDIST_AUTO_NUM_WORKERS; it sets neither force nor a budget fallback.
- `_test-suite` calls tools/test-suite, whose CLI takes no selectors. Define
  `run_suite(root: Path, evidence: Path) -> int` and
  `verify_evidence(evidence: Path) -> dict`; malformed evidence raises ValueError.
- Caller-owned `HQ_TEST_EVIDENCE_DIR`, when supplied, must be absolute and empty;
  default local output is tt's required TT_JUNIT_DIR. Write reports directly to
  the selected directory. If caller-owned, copy available finished JUnit reports
  into TT_JUNIT_DIR before tt returns so its normal timing reader also sees them.
  Preserve caller bytes; do not copy after wrapper cleanup or reuse stale evidence.
- Keep one constant partition list: agents; hooks/tools with the two existing
  ignores; those two relay files with `-n auto -k not test_signal_while_recording_start_cancels`;
  transport with the serial signal selector. Preserve the exact expression as one
  argument. Facts validation runs first; each test run uses `-q -rs`.
- The plugin's pytest_collection_modifyitems appends `(nodeid, item.nodeid)` to
  item.user_properties. During one additional serial collect-only pass over all
  three roots, pytest_sessionfinish writes inventory.json with nodeids and
  collection_problems, whose entries hold nodeid, outcome (skipped/error) and
  reason. pytest_collectreport captures those collection failures. Execution
  passes emit properties, not another global inventory. Any collection problem
  prevents coverage acceptance, even when the surviving tests pass.
  Load it explicitly with `-p pytest_evidence` and the root's tools directory on
  the child PYTHONPATH. Only the collect-only child receives HQ_TEST_COLLECT_ONLY=1;
  the driver supplies the resolved evidence directory to every child. Do not use
  record_testsuite_property, whose xdist support differs from item properties.
- Emit pytest-agents.xml, pytest-hooks-tools.xml, pytest-relay-parallel.xml,
  pytest-relay-signal.xml and
  coverage.json. Reconcile the inventory's identities against properties across
  the four reports. Coalesce multiple phase reports for one testcase within its
  partition; reject overlap between partitions, replacement identities with equal
  counts, missing cases/reports, collection omissions and empty execution. Report
  collected/reported unique counts, excluded modules, per-test skip identity/reason,
  skipped module count and problems. Keep all available evidence after failure.
  The pytest- filename prefix is required by tt's existing JUnit reader; test
  that it reads all four reports without an unknown-runner warning.

- [ ] Write contract tests first: test_off_never_requests_budget_or_runner,
  test_ci_off_skips_locally_and_refuses_hosted_without_force,
  test_nested_hosted_without_force_refuses,
  test_focused_args_are_literal, test_focused_requires_arguments,
  test_full_alias_preserves_child_failure,
  test_four_partitions_cover_inventory, test_equal_count_replacement_is_rejected,
  test_collection_skip_is_visible, test_phase_errors_are_one_identity and
  test_reports_survive_wrapper_exit_on_failure. Use temporary policy files with
  both broad targets and real just/tt; stub only budget/runner processes. Include
  filenames/arguments with spaces, quotes, dollar signs and glob characters.
- [ ] Run `just test-one tools/test_test_execution.py -q` and observe failures
  for the missing wrapper/routes/evidence behavior after the prerequisites exist.
  The new `world` fixture provides policy(enabled), run(recipe, *args, env=None),
  rows() and markers(); its env argument holds explicit fake-value overrides.
  One required behavioral assertion is:

  ```python
  def test_ci_off_skips_locally_and_refuses_hosted_without_force(world):
      world.policy(False)
      assert world.run("ci-test").returncode == 0
      assert world.rows()[-1]["execution"] == "skipped"
      assert world.run("ci-test", env={"GITHUB_ACTIONS": "true"}).returncode != 0
      assert world.markers() == []
  ```

- [ ] Adopt tt via the resolved ops checkout's `bin/vendored adopt tt --into`
  this worktree. Implement the interfaces with existing subprocess, JSON and XML
  libraries. Keep the vendor copy unmodified. Stop after a failed partition;
  preserve its status even if report copying/reconciliation also fails. A report
  failure after otherwise successful tests fails the command. Never fabricate
  empty XML for unrun partitions. Add an evidence-write-failure fixture.
- [ ] Repeat the focused command. Use a small real pytest fixture with a parameter
  ID containing punctuation, a skip, and call/teardown errors; include a two-worker
  fixture so JUnit properties survive xdist. Verify local budget enforcement and
  serial signal selection without running the real relay suite as a bootstrap.
- [ ] Update current command docs and enable `.tt/` fallback-log ignoring. Keep
  policy absent; describe CI as prepared, not active. Run required enabled-policy
  commit checks, independent flow review and commit `feat: record hq test policy and suite evidence`.

### Task 2: Preserve full local hygiene and add portable CI checks

**Files:** .githooks/pre-commit, .githooks/pre-push, justfile,
.githooks/test_pre_commit.py, .githooks/test_pre_commit_facts.py,
tools/test_test_execution.py, AGENTS.md, README.md, docs/test-execution.md.

**Interfaces:** Extend existing `main(argv)` with exactly `--ci` selecting
local_layer → docs_check → staged_checks. No args keeps the existing full
local_layer → hygiene_check → docs_check → staged_checks order; other args fail.
`ci-hygiene` records tt hook-ci-hygiene calling that mode. `check-hygiene` records
tt check-hygiene calling the no-arg hook. No recursive just/pre-commit calls.
Adopt the shared pre-push template unchanged at its landed source revision.
Both hook-pre-push routes compose check-hygiene then test; do not time an outer
composite again. Declare origin and refs/heads/* to match the prepared workflow;
do not describe these declarations as proof of completed remote execution.

- [ ] Add test_ci_mode_needs_no_registry_and_skips_only_ops_check,
  test_ci_mode_refuses_staged_local_state,
  test_ci_mode_checks_staged_facts_and_manifest,
  test_ci_mode_refuses_deleted_or_renamed_reader,
  test_default_mode_still_runs_full_hygiene and test_unknown_mode_refuses.
  Reuse existing hook loaders/fixtures, not a second staged-tree exporter.
  Assert one export, short-circuiting, actual filter-config validation and failure
  status with no registry/private checkout in the CI fixture.
- [ ] Run `just test-one .githooks/test_pre_commit.py .githooks/test_pre_commit_facts.py -q`
  and observe RED. Implement the small mode dispatch and recipe composition.
  Reuse the existing world fixture for this boundary:

  ```python
  def test_ci_mode_needs_no_registry_and_skips_only_ops_check(world):
      repo, env, _ = world
      (repo / "tools/ops-check").write_text("raise SystemExit(99)\n")
      result = subprocess.run([str(HOOK), "--ci"], cwd=repo, env=env)
      assert result.returncode == 0
      assert subprocess.run([str(HOOK)], cwd=repo, env=env).returncode != 0
  ```

- [ ] Extend real hook fixtures for covered feature/x, mixed covered/uncovered
  refs, tags, other remotes, malformed input and deletion-only input. Check the
  template's SSH keepalive refusal, unchanged stdin bytes and clearing of inherited
  Git variables. A policy-off uncovered push warns and starts no suite; hygiene
  failure prevents even the broad request. No host SSH edits.
- [ ] Run that focused hook command and `just test-one tools/test_test_execution.py -q`.
  Document the portable subset's coverage limits and current hook behavior.
  Run required enabled-policy checks, independent review, and commit
  `feat: separate hosted hygiene from local repository checks`.
  When this hook boundary integrates, record on hq-d33cdc exactly
  `policy: enabled at <RFC3339-UTC> revision <full-sha>` using the actual revision/time.

### Task 3: Prepare the hosted workflow and activation packet

**Files:** .github/workflows/ci.yml, tools/test_ci_workflow.py,
docs/test-execution.md and docs/notes/2026-11-03-hq-test-policy-activation.md.
Operational raw evidence lives in the parent's external workspace, not public docs.

**Interfaces:** One ubuntu-24.04 job, all branch pushes (`['**']`), manual dispatch,
no duplicate PR trigger, contents:read, full history, checkout credentials disabled,
workflow/ref concurrency with cancellation. Job env explicitly sets TT_FORCE=1,
PYTEST_XDIST_AUTO_NUM_WORKERS=2, CARGO_BUILD_JOBS=2 and GIT_CONFIG_NOSYSTEM=1.
Export temporary GIT_CONFIG_GLOBAL and absolute HQ_TEST_EVIDENCE_DIR via GITHUB_ENV
from a shell step; runner context is not valid in job-level env. Evidence is fresh
per run/attempt; the always-run upload has a unique revision/attempt name,
retention-days=7 and if-no-files-found=error. A cancelled job is unverified.

- [ ] Write workflow contract tests for nested branch coverage, no internal PR
  duplication, explicit job force and workers, pins, full-history setup, the
  portable hygiene command, ci-test with no recipe force and unconditional report
  upload. Run `just test-one tools/test_ci_workflow.py -q` for RED. Use stdlib
  assertions and real just fixtures; add no YAML dependency for these checks.
  Pin the two critical settings as well as executing Task 1's missing-force fixture:

  ```python
  def test_explicit_hosted_force_and_nested_branch_trigger():
      text = (ROOT / ".github/workflows/ci.yml").read_text()
      assert 'TT_FORCE: "1"' in text
      assert "branches: ['**']" in text
      assert "cancel-in-progress: true" in text
  ```

- [ ] Implement pinned setup above. Build tasks at the published pin inside the
  disposable checkout's ignored .ci-tools directory; verify each required tool via
  the exact system path fixtures use. Run just setup, just ci-hygiene and
  just ci-test. Set a provisional 30-minute timeout; confirm or reduce it from the
  preparation pilot before requesting remote approval, recording the actual limit.
- [ ] Before any extended run, use a disposable clean fixture to exercise all
  four partitions, collection/reconciliation, portable hygiene, wrapper cleanup
  and surviving artifact bytes end to end. Include one task-dependent case using
  the pinned tasks build and a failing case. Run it under the local host budget;
  never repoint a launcher or install a CI tool onto this host's PATH. Preserve
  pilot output and versions in the external workspace. Then run the policy-required
  checks on real changed behavior, and `actionlint .github/workflows/ci.yml`.
- [ ] Verify actual all-root collection and each planned module boundary. Expected
  omissions remain the two exact sibling-dependent tests from the approved spec,
  one in each of two modules, zero modules excluded. Missing history/zsh, root-only
  permission omissions, inaccessible pins or extra omissions require disposition
  and observed coverage acceptance, never silent exclusions. No actual hosted
  result exists until Task 4; distinguish the local fixture pilot from remote proof.
- [ ] Merge main if it moved before whole-branch review, rerun policy-appropriate
  checks and record the merge in the external ledger. Dispatch a fresh whole-branch
  review of code plus raw pilot evidence; resolve Important/Critical findings in
  scoped fix/re-review rounds, up to five. Record deferred minors and rulings.
- [ ] Commit `ci: prepare forced hosted hq verification` with policy still enabled.
  Freeze the activation packet: code/workflow revision, exact setup and refs,
  reader/instruction delivery, pilot results, omissions, evidence retention,
  timeout, visibility/spend protection, rollback and proposed push count. Recommend
  one verification push to feat/hq-d33cdc-test-policy and, only after accepted
  coverage, one activation push to main; no automatic remote retries. This is a
  proposal, not authorization. Park for the user's concrete external approval.

### Task 4: Verify hosted coverage and activate policy after approval

**Files:** .tt.toml, AGENTS.md, README.md, docs/test-execution.md,
the activation packet; task notes and immutable remote evidence.

**Interfaces:** Only accepted hosted coverage permits the policy-off commit.
Activation uses `automatic_broad = false` and
`broad_targets = ["test", "ci-test"]`; registered main is the latency authority.
The task and parent stay open across approval/coverage gates and own their evidence.

- [ ] Check gh auth status and use the profile's named khughitt token for each
  authorized write. Refresh public visibility, standard runner classification,
  readers' actual launch paths and instruction delivery. If private, record allowance
  when available and enforced no-paid-overage; unknown protection blocks activation.
  Never change account settings or substitute a paid runner without approval.
- [ ] Make only the approved verification push. Observe its exact SHA and completed
  result, retrieve the four reports/inventory/coverage artifact and inspect nonzero
  executed counts, failures, skips and excluded modules. Attach small evidence or
  retain raw bytes under the external workspace with retention records. Report
  actual duration and the completed revision; a queued/cancelled/zero-test run is
  not accepted coverage. A failure leaves policy enabled and the next action parked;
  spend no unapproved retry. Two unexplained live failures always go to the user.
- [ ] Obtain the user's acceptance of the observed hosted coverage before changing
  policy. Then write the exact policy file and update current-state docs. Re-run
  focused policy fixtures and hygiene; demonstrate real focused execution, normal
  skips for both broad entry points, no budget child, and forced failure propagation
  with the fixture rather than deliberately failing the production suite.
- [ ] Review the full activation diff after any moved-base merge. Integrate/push
  only within the approved conditional activation scope; otherwise present that
  frozen commit for the missing external approval. Observe the final main push's
  completed forced suite and reconcile its artifacts. The activation run must
  still execute with policy off; a skip, absent run or failed run remains unresolved.
- [ ] Record `policy: disabled at <RFC3339-UTC> revision <full-sha>` on hq-d33cdc
  at actual activation. From registered main inspect all current test-latency and
  halt tasks, every host/target obligation, and retire only disabled timing duties
  with the landed revision; preserve other diagnosis and unrelated halts. Never
  claim performance verification for retirement. Report explicit status to ops-39bff6
  and link existing ops-56aab7 for the shared regret review; create no duplicate.
- [ ] If rollback is needed, restore automatic_broad=true and the local cadence,
  integrate under the applicable scope, and record the exact enabled-regime note
  with its real full SHA/time. Keep hosted coverage unless separately changed.
  Finish flow reviews, retros, truthful verification and retained-item accounting.
  Close only after the final hosted result and incident dispositions are resolved;
  otherwise park the open task with its exact remaining action and owner.

## Review and execution handoff

The four new step records are direct children with this plan and exact Task N
headings; each is scoped, trial-armed when started, and runs in the parent workspace.
Task 1 depends on the two existing prerequisites, then Tasks 2–4 are sequential.
No child starts until this plan is approved. Writing-plans self-review covers spec
coverage, interfaces, focused checks, all five Review Focus cases and proportion;
human review is still required. Native execution avoids repeated implementation
handoffs over the shared recipes; independent flow and whole-branch reviews remain.
The rejected alternative is one implementation worker per step, with extra context
handoffs and no useful implementation parallelism here.
