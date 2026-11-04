# Hosted verification and policy activation packet

Status: hosted coverage is accepted, including all three local integration skips.
The worktree now prepares `.tt.toml` with automatic broad runs disabled; registered
main remains enabled. Activation, main integration and publication await explicit
authorization after independent review. Owner: hq-d33cdc; preparation: hq-b32d19;
activation: hq-c7e52c.

## Frozen inputs and requested next action

Design: da5e8ace1327c4eea5ce77c8e1a6355eb65d31af,
docs/specs/2026-11-03-test-execution-policy-design.md.
Plan: 192a6e854a71be95a4660571ebb0490592825f00,
docs/plans/2026-11-03-test-execution-policy.md.
Original preparation code/workflow revision: c4a93f3a58a67451ec34cd605b74470e0251551e.
The first verification push was authorized from packet revision
0cf37c0784de88a2df825b8f15b4a26cd3d98aa0. The second was authorized from
954ad406156d12c6321747036e83d88df198bc5f and published as
855c814bc4805c7d682c81f847bcb79c7cc953c2; their covered source is identical.
The user accepted the observed coverage in packet revision
9b9c88ee6044a7af386919e10133c25b6b790e2a, including the added third integration
omission. The packet's next frozen revision is named in the activation request.

Recommend authorizing the reviewed conditional rollout below: integrate the
enabled preparation, then the policy-off change, and make one main verification
push. Both previous single-push approvals are spent. No rollout, main push, further
remote retry, account change or paid runner substitution is authorized yet.

## Prepared execution

The workflow is .github/workflows/ci.yml in khughitt/harness-quarters. One standard
ubuntu-24.04 job covers all branch pushes, including nested names, and manual
dispatch; there is no duplicate PR trigger. Permissions are contents:read, both
checkouts disable persisted credentials, history is complete, and workflow/ref
concurrency cancels superseded attempts. Job timeout: 60 minutes, two pytest
workers and two Cargo jobs. The workflow supplies TT_FORCE=1 at job scope;
ci-test itself supplies neither force nor the development-host allocator.

| Input | Pin or source |
| --- | --- |
| uv | 0.13.7 |
| just | 1.59.0 |
| pytest / pytest-xdist | 9.2.0 / 3.8.0, shared suite definition |
| Node | 26.13.0 |
| Rust / Cargo | 1.99.1, locked release build |
| tasks | public fa58ab31acd757f59798537b6957e540fdccb9fb |
| historical hook commit | public 6b434eb206c4464c062137e3600dcd303a543f68, explicitly fetched |
| work-link | public dotfiles 2a686c0c4915ba0daae9f6455cfe45233780fc33 |
| work-link SHA-256 | 6400d9a8431d3af3777d5038716d4322d283ebd127c574c06d7516dd1a784ff4 |
| Python | runner /usr/bin/python3; pidfd_open checked, uv downloads disabled |
| zsh / libatomic1 / curl / attr | runner apt repositories; installed versions recorded |
| actions/checkout | 3d3c42e5aac5ba805825da76410c181273ba90b1 |
| astral-sh/setup-uv | 11f9893b081a58869d3b5fccaea48c9e9e46f990 |
| extractions/setup-just | 53165ef7e734c5c07cb06b3c8e7b647c5aa16db3 |
| actions/setup-node | 820762786026740c76f36085b0efc47a31fe5020 |
| actions/upload-artifact | 043fb46d1a93c77aae656e7c1c64a875d1fc6a0a |

Upstream action metadata and public tasks source were checked read-only. Setup
installs uv, just, Node and tasks at the exact /usr/bin paths used by fixtures in
the disposable runner. GIT_CONFIG_GLOBAL is a temporary runner-owned file and
GIT_CONFIG_NOSYSTEM=1. No private sibling checkout or fabricated project registry
is installed. Run order is just setup, just ci-hygiene, then just ci-test.
Full local check-hygiene remains protected and mandatory in commit/push hooks.

The explicit historical fetch is needed even with fetch-depth=0: the still-public
pinned object is outside current advertised ancestry. The published work-link
script is hash-checked before installation; no private checkout or fixture
replacement is introduced. Its bytes match the locally deployed tool. Anonymous
exact-SHA acquisition was proven from an isolated empty Git repository, and a
focused rename case passed with the public tool under the worktree's ignored bin.
The attr package is explicitly installed and reported because work-link needs its
command when ensuring worktree administration storage; host availability alone
does not establish that runner prerequisite.

## Observed first hosted attempt

The single approved push succeeded at
8d140cce7ea4d6cec0ddf6953a7250f7ed89480b. Its installed local pre-push hook
passed all 2,778 tests and full hygiene, with exact identity reconciliation.
[Run 41716936974](https://github.com/khughitt/harness-quarters/actions/runs/41716936974)
attempt 1 then failed on that exact SHA. The standard ubuntu-24.04 job ran for
7m56s (20:55:01–21:02:57 UTC); setup, pinned builds, hydration, portable hygiene
and failure-artifact upload succeeded. Only the forced suite step failed.

The retained artifact collected 2,778 cases across 59 modules, reported 2,386
and executed 2,372 unique identities, including 80 failures. All 80 failures are
rename-cutover cases whose apply command cannot find work-link. Fourteen cases
skipped: the three proposed integrations plus eleven historical hook cases whose
6b434eb object is absent. Agents passed; hooks/tools failed; 392 relay cases were
unrun, and only the two completed partitions have XML. No module was excluded or
skipped during collection. This is failed, incomplete coverage, never acceptance.

Artifact 13269109652 and the complete run logs were downloaded as immutable ZIPs
and safely extracted into the parent workspace. The artifact expires on GitHub at
2026-11-10T21:02:53Z; local raw copies are retained independently. The workflow
correction addresses both observed setup omissions, preserving all
existing tests and the original three proposed integration omissions. Its actual
hosted result is recorded in the completed second attempt below.

The local full gate also reproduced a pre-existing relay test-fixture startup
race: a child was classified before its supplied environment was fully visible.
The shared fixture readiness helper now waits for every expected child environment
entry before the original assertions, with a deterministic regression test. The
production process reader and home classification behavior are unchanged; no
assertion or case is removed. Current local verification is recorded on hq-c7e52c.

## Observed second hosted attempt and coverage decision

The separately approved second push succeeded at
855c814bc4805c7d682c81f847bcb79c7cc953c2. Its installed local hook passed all
2,781 tests and full hygiene before publication. No additional baseline was run.
[Run 41741765690](https://github.com/khughitt/harness-quarters/actions/runs/41741765690)
attempt 1 then completed successfully on that exact revision. The standard
ubuntu-24.04 job ran for **19m21s**, from 2026-11-03T23:46:28Z to
2026-11-04T00:05:49Z. Every setup, build, hydration, portable hygiene, forced
suite and artifact step passed. No user installation was needed.

All four reports reconcile against one inventory: **2,781 collected and reported,
2,778 executed and passed, three skipped**. No failure, error, excluded module,
skipped module, missing identity, duplicate partition identity or reconciliation
problem exists. The 59 collected test modules are represented.

| Partition | Reported | Passed | Skipped |
| --- | ---: | ---: | ---: |
| agents | 268 | 268 | 0 |
| hooks/tools | 2,120 | 2,117 | 3 |
| relay parallel | 392 | 392 | 0 |
| relay signal | 1 | 1 | 0 |

The only skips are the three exact nodeids in **Accepted hosted coverage
boundary** below: relay subscriber budget validation, agy dispatch through the
registered ops relay guard, and authentic registered owner-target shape validation.
All require the local tasks project registry. The user accepted the added third omission
alongside the original two. Those three checks passed in the
current local 2,781-test run, but their live local integration is outside hosted
coverage. No module is omitted, and no further omission is proposed.

Artifact 13282592504, named
hq-tests-855c814bc4805c7d682c81f847bcb79c7cc953c2-1, contains setup evidence,
inventory, coverage and all four XML reports. Its GitHub retention expires at
2026-11-11T00:05:45Z. The 101,119-byte artifact ZIP and 147,403-byte complete
logs ZIP were downloaded, CRC-checked and safely extracted in the parent-owned
workspace. The controller independently re-read inventory/XML coverage, checked
all skip identities and zero failures/errors, verified setup pins and rehashed all
33 retained raw/API/archive member files against the receipt. Immutable raw evidence
and reconciliation are discoverable from hq-c7e52c and hq-d33cdc.

Coverage decision: the user accepted this observed boundary, including all three
local integration skips, after reading frozen packet9b9c88ee. That acceptance
authorizes policy-off preparation and review; it does not authorize a push or main
integration. The branch-local policy is not activation in registered main.

## Pilot and verification limits

The local release build reports tasks 0.4.0 (fa58ab31), SHA-256
ee4dea224770eb40d35d049802a9832a1086f784e4c9d1d4d7013452b5fca7c0.
The end-to-end fixture pilot passed both success and deliberate failure cases:
2 passed in 8.25 seconds (retained attempt 3). It executed the actual workflow evidence-preparation
shell, real portable staged validators, a real pinned tasks registry roundtrip,
four miniature partitions, identity reconciliation, wrapper cleanup and surviving
failure artifacts. Success collected/reported six cases, executed five and retained
one intentional fixture skip. The failing fixture preserved setup and partial XML
with nonzero status. After the outer pytest process exited, the controller copied
and reconciled 11 artifact files into caller-owned evidence outside pytest cleanup;
a receipt records both cases and exact byte hashes. Earlier attempt 2 passed, but
ambient failed-only pytest retention deleted its fixture artifacts; only its log
remains. That lost attempt does not count as retained raw proof. Attempt 3 uses
explicit all retention plus independent copied evidence. The earlier
missing-authority fixture failure remains retained.
This validates the local fixture path only. Runner apt, actions, Ubuntu runtime
and the complete hosted path are established separately by the second run above.

Changed behavior: 71 focused tests passed in 60.74 seconds with the published tasks
build on the command PATH; after byte-exact restoration of 11 targeted faults,
all 71 passed again in 45.82 seconds. The exact-key pilot rejects the malformed
configuration export that a coarse substring check alone accepts. Actionlint and
both actual hygiene routes passed.
Initial preparation production suite: 2,778 passed (268 agents, 2,118 hooks/tools,
391 parallel
relay and one serial signal test), with collected=reported=executed=2,778, four
reports and no skips, excluded modules or reconciliation problems. No extra
adoption baseline was run, as requested. Policy was enabled during preparation.

The 60-minute limit replaces the provisional 30 minutes because an actual local
two-worker full run exceeded 30 minutes before relay verification finished. It is
a finite bound, not a prediction of hosted duration; a hosted timeout is unverified.

## Accepted hosted coverage boundary

Expected module exclusions: zero. Three exact local integration checks may skip:

1. tools/test_relay_subscribers.py::test_template_validates_against_registered_relay_budgets
2. tools/test_agy_hooks.py::test_relay_v030_agy_dispatch_with_rendered_subscribers_and_ops_relay_guard
3. tools/test_harness_links.py::test_registered_owner_targets_match_portable_fixture_shapes

The third is an accepted addition beyond the design's two omissions. Existing
functional harness-link tests now use portable structural owner fixtures; the new
local check preserves authentic registered target copying and shape validation.
All 61 link tests passed locally, including that authentic check. An isolated
registry run of the entire module plus the other two integration nodes produced
60 passed and precisely these three skips, with no module excluded. That local boundary evidence and the completed second hosted run support the
recorded acceptance. Missing history, unexpected
skips (including permission/root behavior), extra omissions or failed collection
need explicit disposition before activation. Mods and live capability probes
remain outside the declared suite.

## Remote evidence and acceptance

Each attempt uploads hq-tests-<revision>-<attempt>, even after failure, with seven
days' retention and an error when no files exist. The caller-owned artifact parent
contains setup-report.txt and an initially empty suite/ child. Reconcile suite/'s
inventory.json, coverage.json and pytest-agents.xml, pytest-hooks-tools.xml,
pytest-relay-parallel.xml, pytest-relay-signal.xml. TT_JUNIT_DIR is temporary and
cannot serve as the upload source after tt exits.

The controller must record the completed run's exact revision, outcome, duration,
nonzero unique execution count, every test/module skip and any excluded module;
all four reports must reconcile against the same collected identities. Retrieve
and durably retain raw evidence before the hosted retention window closes. A
queued, cancelled, zero-test or incomplete attempt is unverified. User acceptance explicitly covers the observed second-run boundary, including
the third omission; a changed boundary needs its own disposition.

## Reader delivery, visibility and spend

Read-only preflight found tt-report and tt-latency launched from the registered
ops main checkout at 6cbb15e67de7649564141551a15ca990c21fafe1. They understand
policy skips with null outcomes and exclude skipped runs from latency evidence.
The obs-index user service resolves its source to registered obs main at
2d95d8adc68bae385fb1675357cb84efa1de2d11: current schema 19, tt parser 2 and
explicit skipped-run reporting. Schema has advanced beyond prerequisite schema 17;
the skip contract remains present. Both delivered personal AGENTS links resolve
to lore's assembled instructions containing the policy-off rules. No launcher,
service, instruction link or host installation was changed for this verification.
Refresh these actual paths and behavior before activation.

GitHub read-only metadata currently identifies the repository as public. Standard
GitHub-hosted usage for public repositories is free under the
[GitHub Actions billing rules](https://docs.github.com/en/actions/concepts/billing-and-usage).
Refresh visibility and standard-runner classification immediately before each
authorized write. If private, unknown allowance/no-paid-overage protection blocks
activation; obtain evidence or a new user decision. Never change billing settings
or select a paid runner by inference. Use the profile's khughitt token per command
after checking gh auth status; do not switch the globally active account.

## Conditional activation and rollback

Both feature verification pushes and coverage acceptance are complete. The next
request is authorization of this concrete rollout after independent review:

1. Refresh the named khughitt account, public visibility, standard runner, delivered
   policy instructions and actual timing readers. Stop if spend protection changes.
2. Integrate preparation commit79140b92527cff5bdae81cc508d669c9b04588c3 into
   main while policy is absent/enabled; record the actual enabled timestamp and
   revision. This brings the reviewed workflow and push hook into main.
3. Integrate the reviewed policy-off revision named in the approval request. Its
   `.tt.toml` has automatic_broad=false and broad_targets=["test", "ci-test"].
   Record the actual disabled timestamp/revision on the adoption task.
4. Make exactly one main push to origin with the installed mandatory hygiene hook,
   then inspect that exact completed forced hosted run and retain/reconcile all
   reports. No automatic remote retry is included. A failed, cancelled, incomplete
   or missing run remains unresolved and returns for disposition.
5. From registered main inspect every latency host/target, retire only disabled
   obligations with the landed revision, preserve unrelated halts/diagnosis and
   report status to ops-39bff6 with existing ops-56aab7 linked.

This authorization would change the live main checkout's hooks and test cadence.
No home routing, service, account or billing configuration change is included.

Prepared local evidence includes real-checkout skips and hosted refusals plus
functional policy fixtures. The initial actual-checkout policy assertions first
failed twice under default execution, then passed within a 74-test focused run.
Independent review reproduced that those assertions also rejected the supported
policy-on rollback. They were removed; their exact source and RED/GREEN evidence
remain retained. The functional tests exercise enabled, absent and disabled policy
without requiring the deployment to remain in one state.

Six separate real-checkout smoke commands prove both normal broad skips, direct
hosted missing-force refusal for each target and nested hosted refusal for each.
Both skips recorded null outcomes and started no host-budget child. Existing
fixture checks prove real focused execution, forced child status17 propagation
and surviving success/failure reports. Corrective verification passed 42 tests
with policy enabled, 42 with policy absent and 106 focused tests in the final
policy-off checkout. Local and portable staged hygiene and diff checks passed;
raw results are recorded on hq-c7e52c before the scoped review.

No broad suite is rerun solely for policy-off preparation or corrective review.
The next expected inventory remains 2,781 identities with the same three accepted
local integration skips. Only the final completed main run can establish its actual
count and outcome. No latency obligation is retired from an unmerged branch, and
retirement never claims performance verification.

Rollback restores automatic_broad=true and the enabled local cadence, with focused
checks and mandatory hygiene plus policy-required broad checks. Record the actual
enabled-regime time/revision; keep hosted verification unless separately changed.
Publication of a rollback remains subject to its actual authorization. Neither an
unmerged feature policy nor an unobserved remote run retires latency obligations.

## Supporting records

The open parent owns the locked .worktrees/hq-d33cdc and persistent workspace
$WORK_ROOT/hq/hq-d33cdc/plans/2026-11-03-test-execution-policy/. Its progress.md
holds rulings with Why/Cost, review rounds and task completions; raw logs, setup
metadata and source-pin checks remain there. The current pilot evidence is
task-3-pilot-evidence-attempt-3/ (success/, failure/ and receipt.json), verified
after the outer process exited; attempt-2 fixture bytes were lost as stated above.
The task
record binds their retention checkpoint. No raw host-specific output is published
in this packet. The feature branch remains unmerged pending the rollout gates.
