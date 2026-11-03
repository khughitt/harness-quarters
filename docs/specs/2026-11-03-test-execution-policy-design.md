# hq test execution policy and hosted verification

Status: revised after spec round 2; proposed for human review. Task: hq-d33cdc.
Implementation and external activation have not started. This design does not
authorize a push, workflow activation, account change, home relinking or global
instruction change.

## Intent and authority

Keep focused implementation tests local, reduce repeated broad work on development
hosts, and run routine regression verification on GitHub-hosted runners after a
push. Preserve test coverage and disclose what the hosted environment cannot run.

The user described this goal in the originating shared-policy session, including
tt ownership, hosted suites and policy-aware instructions. The approved authority
is ops-8bfa85: spec revision `1ce9abe7c9d4f9f5ad6dd8b39e764a597e96eaec`,
`docs/specs/2026-10-29-test-execution-policy-design.md`; plan revision
`ddcfdab5dbb6b60d6891d0aa84283a766275b69c` at
`docs/plans/2026-10-29-test-execution-policy.md` in ops. Read both
through that task's document links. The ops pilot ops-68729d is done and records
accepted hosted runs before and after activation. The original session is
`codex:01a1874f-c2d8-7320-ae81-7114e37e343f`; the adoption task records the human
turn locations and separates that intent from agent implementation choices.

The user's instruction in this session explicitly waives baseline tests for this
task, including later implementation Setup. Hydration, focused implementation
checks, mandatory hygiene and truthful reporting remain required. No baseline
pass is claimed. This exception does not change the policy of other tasks.

## Verified current state

- hq is a personal, in-tree project with its own Git top level and default branch
  main. origin is `khughitt/harness-quarters`; read-only GitHub inspection on
  2026-11-03 reports PUBLIC visibility. There is no workflow, pre-push hook,
  `.tt.toml`, `tools/tt`, focused recipe or broad static-check target today.
- `just setup` installs repository hooks and the required harness-state filter,
  and creates the untracked local configuration directory. It installs no Python
  packages and must never link hosted home directories to this checkout.
- `just test` checks capability-fact validity, then runs four pytest invocations:
  agents; hooks/tools except the two relay-cutover files; those files under xdist
  except the signal test; and that signal test serially. Preserve this partition
  and its selectors. Static inventory contains 57 test_*.py modules: agents/bin 2,
  hooks 7 and tools 48; conftest.py is not a test module. This is not a collected
  or executed test count.
- The Python pre-commit hook already contains mandatory work only: staged local
  state refusal, working-tree ops-check and ops-docs, then capability and manifest
  checks against one exported staged tree. None becomes policy-skippable.
- Open hq-b01c0f owns budgeted local test/test-one execution. Open hq-0d26dc owns
  the system-interpreter correction for pidfd-dependent test paths. The plan must
  coordinate these records before editing the same recipes; reuse their landed
  behavior, or schedule their scoped work first in the shared task workspace.
  This design neither closes them nor waives their independent checks.
- Ops main has tt version 10, last changed at
  `646c7cf7c08e11e8adcf43ddf844a3f059162735`. Its reporting and latency launchers
  resolve to main. Done obs-a171dd records reader schema 17/parser 2 delivery;
  current obs code accepts skipped outcomes. Delivered session instructions already
  contain the policy-off verification rules. Refresh these observations at rollout.
- No open hq test-latency or halt records were returned at preparation. Refresh
  before activation; absence now is no future retirement proof.

## Approaches and decisions

1. **Adopt tt and one portable hosted suite: recommended agent choice.** Reuse the
   shared policy implementation and hq's existing suite partitions. Add no test
   selector, dependency or policy parser. Local broad requests can skip while
   focused work and hygiene continue.
2. **Skip local suites without hosted coverage: rejected.** Smaller preparation,
   but it loses the routine regression coverage the user requested.
3. **Use a self-hosted runner: rejected.** It retains development-host contention
   and adds a persistent host service rather than using the approved hosted path.

The remaining choices below are the agent's proposals, not recorded user approvals.
Later discovery of unrelated regressions is an accepted shared-policy trade-off;
CI queues, cancellation, outages and quota failures can leave a head unverified.

## Command and hook boundaries

Adopt the latest landed `tools/tt` through ops's `bin/vendored adopt tt` from the
worktree (or its documented `--into` form); keep its bytes and executable mode
unchanged. Let the distributor refresh `tools/README.md` as it normally does.

The broad targets are `test` and `ci-test`, the local and hosted entry points to
the same suite. Do not invent lint/type workloads or a fast-suite selector. The
proposed interfaces are:

| Route | Behavior |
| --- | --- |
| `just test` | tt target test decides first; if running, use the local worker budget and the existing complete suite |
| `just test-one <pytest arguments>` | protected tt target test-one, through host-budget, preserving argument boundaries and runner status; require arguments |
| `just test-full` | untimed alias for `TT_FORCE=1 just test`; exactly one broad record |
| `just check-hygiene` | protected local tt target, executing the full existing pre-commit validation path, including staged-tree checks |
| `just ci-hygiene` | protected tt target hook-ci-hygiene, running staged-local-state refusal, ops-docs check and staged-tree fact/manifest validation; no registry-dependent ops-check |
| `just ci-test` | tt target ci-test decides first, then the same suite partitions with bounded hosted workers and no development-host allocator; does not set TT_FORCE |

Keep one definition of the suite commands, shared between local and hosted entry
points. Any internal recipe exists only to share that definition and is marked
private. All pytest invocations use the interpreter settled by hq-0d26dc; verify
pidfd support before the first run. Preserve serial signal handling and the xdist
exclusion. Local xdist consumes hq-b01c0f's grant, never the machine's CPU count
without a budget. A policy skip launches neither a suite nor host-budget.

Hosted execution is a separate explicit entry point: a standard runner has no
configured host-budget policy or user manager. It sets two workers initially;
missing local host-budget remains an error, with no automatic unbudgeted fallback.
Only the workflow sets TT_FORCE=1 for hosted execution; ci-test never supplies
its own override. With policy off, local ci-test without force records a skip
and starts no unbudgeted child. With GITHUB_ACTIONS=true and no force it refuses,
so forgetting the workflow setting cannot produce a green skipped or silently
forced run. The local deliberate full-run route remains test-full, with its budget.

The hosted hygiene subset reuses the existing hook's local_layer, docs_check and
staged_checks validations, retaining their failure handling and single staged-tree
export. It does not call the full pre-commit main path. Full check-hygiene stays
mandatory in local pre-commit and pre-push behavior. The hosted entry point records
under the protected hook-ci-hygiene target so neither suite classification can skip
it. No change to the shared reference checker, registry stub or private ops checkout
is needed. Cross-project reference validity, and ops-check's other checks, remain
local evidence rather than claimed hosted coverage. In an isolated environment
without the sibling registry, current ops-check reports eight missing references;
the existing hook validations chosen for the portable subset pass. This observation
establishes the boundary, not a completed hosted check.

Reuse ops's existing pre-push template for ref validation and the uncovered-ref
warning, rather than writing another ref/policy parser. Declare `ci_remote` as
origin and `ci_suite_refs` as `refs/heads/*`, matching the workflow below. Both
hook-pre-push routes run mandatory hygiene and then request the same `just test`;
there is no different fast selector here. The hook names remain protected.
Preserve the template's inherited-Git-variable clearing, ref-byte forwarding,
SSH keepalive behavior and errors. Do not repoint a host launcher or change SSH
configuration as part of this adoption. The existing Python pre-commit hook
retains its behavior; the hygiene recipe calls its validation, without recursion.

Initially the policy remains absent/enabled. After accepted hosted coverage and
separate activation approval, commit only the actual broad target classification:

```toml
automatic_broad = false
broad_targets = ["test", "ci-test"]
```

tt owns validation and decisions. Focused checks and all mandatory work run with
either policy state. A local skip records null execution outcomes and is never
described as passing. Force preserves failing child status. A hosted would-be
skip without TT_FORCE=1 fails, including nested calls.

## Hosted workflow and coverage

Prepare one `.github/workflows/ci.yml`, one Linux job on a standard GitHub-hosted
Ubuntu runner. Trigger on every branch push (`branches: ['**']`, including slash
names) and manual dispatch; do not add a duplicate internal pull-request trigger.
Use per-workflow/ref concurrency with cancellation of superseded runs, read-only
contents permission and checkout without persistent credentials. Full history is
required by existing historical filter/pick tests. No tag-suite coverage is claimed.

Pin tool versions and action revisions during implementation from authoritative
sources. Install just, uv, pytest/xdist, zsh, a Node version supporting the existing
TypeScript extension tests, and a pinned public tasks CLI. Existing isolated fixture
PATHs use system directories: make just and the chosen Node available there in
the disposable runner, and verify their versions at those exact paths. Keep the
system Python executable consistent with shebang-launched tools. No live harness,
API credential, desktop, host service or installed pi/relay runtime is required.
Git fixtures use isolated config and allowlisted subprocess environments.

Run `just setup`, `just ci-hygiene` and `just ci-test`. Set TT_FORCE=1 explicitly
at workflow job scope, never inside ci-test or the shared suite definition. Retain
a finite job timeout chosen from the preparation pilot; the activation packet
names that actual limit and the allowed number of remote attempts.

The workflow creates a caller-owned evidence directory outside tt's temporary
TT_JUNIT_DIR and passes its location to the suite. Preserve four distinct reports
(agents, hooks/tools, parallel relay and serial signal), their skip identities and
the collected test inventory in that directory. The shared suite may write there
directly or copy reports there before returning to tt; choose one route in the
plan and use the same suite definition locally and remotely. Never upload from
TT_JUNIT_DIR after tt exits: tt removes it in finally. Retain available reports on
failure as well as success; absent/unrun partitions remain explicitly unverified.
An evidence-write failure is a failed check, and report cleanup must not mask a
suite failure. Upload the caller-owned evidence with an always-run workflow step
and reconcile all four reports against collected identities before accepting
coverage; a nonzero aggregate alone cannot conceal omitted partitions. Do not
suppress a failed prerequisite or discard a module to obtain a green run.

Known capability boundaries from current code:

| Case | Hosted treatment |
| --- | --- |
| `tools/test_relay_subscribers.py::test_template_validates_against_registered_relay_budgets` | Existing skip when no registered relay checkout is present |
| `tools/test_agy_hooks.py::test_relay_v030_agy_dispatch_with_rendered_subscribers_and_ops_relay_guard` | Existing skip without registered ops and relay checkouts; ops is private |
| History-dependent manifest and live-picks tests | Fetch full hq history; unexpected history skip blocks coverage acceptance |
| Relay-cutover transport/bootstrap | Install zsh; module-level or parameterized omissions for missing zsh block acceptance |
| Permission/refusal tests | Run as an unprivileged runner user; root-only skips are not accepted as equivalent coverage |
| `just mods` and live capability probes | Separate manual facilities, outside today's just test; no claim of hosted CLI/probe coverage |

The two sibling-dependent tests are proposed known omissions, one test in each of
two modules, with zero modules excluded. Their actual count and all other skips
must be observed before activation. No private-repository token or private sibling
checkout is introduced to a public workflow. Changing either integration's behavior
still requires relevant focused local integration evidence. If more omissions or
nonportable behavior appear, record them and obtain coverage acceptance; never
label an attempted workflow as offloaded or silently extend the accepted gap.

Read-only GitHub inspection confirms this repository, tasks and relay are public.
[GitHub billing documentation](https://docs.github.com/en/actions/concepts/billing-and-usage)
checked 2026-11-03 says standard hosted runners in public repositories are free.
Refresh visibility and runner classification in the activation packet. No paid
runner, account-setting change or private dependency access is proposed. If the
repository becomes private, the packet must instead document its current allowance
when available and enforced no-paid-overage setting; exact remaining balance is
not required. Unknown spend protection blocks that changed activation path.

## Verification and staged rollout

1. Human reviews this frozen design, then a separate implementation plan. Complete
   the plan's fresh review and prerequisite recipe coordination before code edits.
2. Hydrate the isolated workspace and honor this task's baseline waiver. Exercise
   new command/hook behavior with focused RED-to-GREEN fixtures through test-one;
   no broad rerun is implied by that waiver, and other mandatory checks still apply.
3. Prove policy-on execution, focused execution, literal argument forwarding,
   skip-before-budget with no child, null skipped records, a forced child failure,
   and direct/nested hosted refusal without force for both test and ci-test. Pin
   ci-test's local policy-off skip and absence of a recipe-level force override.
   Prove full local hook hygiene, the portable CI subset with no registry/private
   siblings, hygiene failure propagation, slash-branch coverage and
   uncovered/tag/other-remote warnings. Retained partition reports must still exist
   after tt exits on success and failure, and reconcile against collected identities.
   Use temporary policy-off fixtures until activation; do not switch the live
   checkout early.
4. Before an extended run, exercise the prepared setup and verdict path on a small
   disposable case, including interpreter/tool availability and coverage reporting.
   Then verify the unchanged suite inventory. Record any full local execution as
   deliberate verification, never a baseline required by this task.
5. Review the whole branch after merging any moved base. Prepare a concrete external
   packet: frozen workflow revision, exact refs/setup, reader delivery, local
   evidence, expected usage, timeout/attempt bound, actual omissions, the portable
   hosted hygiene boundary and rollback.
   The user approves publishing and remote invocation separately. Stop here if
   approval has not been given; code and policy remain enabled locally.
6. After an approved hosted run completes with nonzero tests, reconcile counts and
   obtain acceptance of its observed coverage. Only then prepare/land policy-off
   under the approved activation scope, prove a local focused execution and recorded
   skip, and verify a covered push still runs remotely with force.
7. From registered main, inspect every current timing incident and host/target.
   Retire only disabled obligations with the actual landed policy revision; retain
   diagnosis and unrelated halts. Disabled is not applicable, not performance-verified.
   Report actual adoption status to ops-39bff6. ops-56aab7 already owns the shared
   thirty-day regret review; do not create a duplicate or a scheduler.

On integration of the new hook boundary, and on rollback, write on hq-d33cdc:
`policy: enabled at <RFC3339-UTC> revision <full-sha>`, using the actual integration
time and revision. On activation also record the disabled time and full revision.
Never substitute branch policy for registered-main incident disposition.

Rollback sets automatic_broad=true (or removes the policy), updates the guide's
cadence and records the enabled-regime floor; it does not claim a regression was
fixed. Retain remote coverage unless separately changed. Update AGENTS.md and
README.md with current command, hook, force, ref and coverage behavior when the
corresponding implementation lands. Live global instructions are already delivered
by lore and are not edited here.

The builder may choose small recipe factoring, fixture layout, exact pinned tool
versions, timeout and report transport consistent with these contracts. New test
selection, private sibling credentials, weakened hygiene, paid compute or removal
of existing tests would require a new decision.
