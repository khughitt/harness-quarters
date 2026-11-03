# Hosted verification and policy activation packet

Status: one authorized verification push and failed hosted attempt completed.
Coverage is unaccepted, and no activation exists. The policy file is absent and
local broad testing remains enabled. Owner: hq-d33cdc; preparation: hq-b32d19;
activation: hq-c7e52c. A local setup correction awaits a separately approved retry.

## Frozen inputs and requested next action

Design: da5e8ace1327c4eea5ce77c8e1a6355eb65d31af,
docs/specs/2026-11-03-test-execution-policy-design.md.
Plan: 192a6e854a71be95a4660571ebb0490592825f00,
docs/plans/2026-11-03-test-execution-policy.md.
Original preparation code/workflow revision: c4a93f3a58a67451ec34cd605b74470e0251551e.
The first verification push was authorized from packet revision
0cf37c0784de88a2df825b8f15b4a26cd3d98aa0. The retry correction is the workflow
in this packet's next frozen revision, named in its approval request.
The packet's own frozen revision is the commit named in the approval request.

Recommend authorizing one additional verification push of the corrected branch
feat/hq-d33cdc-test-policy to origin, so actual hosted coverage can be inspected.
The first approved push is spent. This new request does not authorize activation,
automatic further retries, account changes or
paid runner substitution. A failed, cancelled or incomplete run leaves policy
enabled and returns for disposition. Later coverage acceptance is a separate gate.

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
2026-11-10T21:02:53Z; local raw copies are retained independently. The local
workflow correction addresses both observed setup omissions, preserving all
existing tests and the original three proposed integration omissions. Its actual
hosted result remains unverified until a new push is authorized and completed.

The local full gate also reproduced a pre-existing relay test-fixture startup
race: a child was classified before its supplied environment was fully visible.
The shared fixture readiness helper now waits for every expected child environment
entry before the original assertions, with a deterministic regression test. The
production process reader and home classification behavior are unchanged; no
assertion or case is removed. Current local verification is recorded on hq-c7e52c.

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
This validates the local fixture path; runner apt, actions, Ubuntu runtime and a
complete hosted run remain unverified.

Changed behavior: 71 focused tests passed in 60.74 seconds with the published tasks
build on the command PATH; after byte-exact restoration of 11 targeted faults,
all 71 passed again in 45.82 seconds. The exact-key pilot rejects the malformed
configuration export that a coarse substring check alone accepts. Actionlint and
both actual hygiene routes passed.
Full production suite: 2,778 passed (268 agents, 2,118 hooks/tools, 391 parallel
relay and one serial signal test), with collected=reported=executed=2,778, four
reports and no skips, excluded modules or reconciliation problems. No extra
adoption baseline was run, as requested. Policy remains enabled.

The 60-minute limit replaces the provisional 30 minutes because an actual local
two-worker full run exceeded 30 minutes before relay verification finished. It is
a finite bound, not a prediction of hosted duration; a hosted timeout is unverified.

## Proposed hosted coverage boundary

Expected module exclusions: zero. Three exact local integration checks may skip:

1. tools/test_relay_subscribers.py::test_template_validates_against_registered_relay_budgets
2. tools/test_agy_hooks.py::test_relay_v030_agy_dispatch_with_rendered_subscribers_and_ops_relay_guard
3. tools/test_harness_links.py::test_registered_owner_targets_match_portable_fixture_shapes

The third is an additional proposal beyond the design's two omissions. Existing
functional harness-link tests now use portable structural owner fixtures; the new
local check preserves authentic registered target copying and shape validation.
All 61 link tests passed locally, including that authentic check. An isolated
registry run of the entire module plus the other two integration nodes produced
60 passed and precisely these three skips, with no module excluded. This is local
boundary evidence, not acceptance of hosted coverage. Missing history, unexpected
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
queued, cancelled, zero-test or incomplete attempt is unverified. User acceptance
must explicitly cover the observed boundary, including the third proposed omission.

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

Original proposal: one feature verification push, then one main activation push only
after observed coverage acceptance and explicit activation authorization. No remote
retry was included, and that verification approval is now spent. This packet
requests one additional feature verification push only; the remaining coverage,
activation, integration and main-publication gates remain separate.

After accepted coverage and activation authorization, first integrate the reviewed
preparation into main while policy is absent/enabled and record its actual enabled
regime timestamp/revision. Then prepare and review .tt.toml with
automatic_broad=false and broad_targets=["test", "ci-test"], update current docs,
and prove focused execution, both normal skips, no budget child on skips, hosted
missing-force refusal and forced failure propagation. Merge any moved base before
review. Integrate the reviewed activation and make the separately authorized main
push, whose forced completed reports must also reconcile. Record actual disabled
time and landed revision; inspect every registered-main latency host/target and
retire only disabled timing obligations, never as performance-verified. Keep
unrelated halts/diagnosis and report status to ops-39bff6 with ops-56aab7 linked.

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
