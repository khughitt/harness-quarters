# Hosted verification and policy activation packet

Status: preparation only. No verification push, hosted result, accepted coverage or
policy activation exists. The policy file is absent and local broad testing remains
enabled. Owner: hq-d33cdc; preparation: hq-b32d19; activation: hq-c7e52c.

## Frozen inputs and requested next action

Design: da5e8ace1327c4eea5ce77c8e1a6355eb65d31af,
docs/specs/2026-11-03-test-execution-policy-design.md.
Plan: 192a6e854a71be95a4660571ebb0490592825f00,
docs/plans/2026-11-03-test-execution-policy.md.
Preparation code/workflow revision: c4a93f3a58a67451ec34cd605b74470e0251551e.
The packet's own frozen revision is the commit named in the approval request.

Recommend authorizing one verification push of the reviewed preparation branch
feat/hq-d33cdc-test-policy to origin, so actual hosted coverage can be inspected.
This request does not authorize activation, automatic retries, account changes or
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
| Python | runner /usr/bin/python3; pidfd_open checked, uv downloads disabled |
| zsh / libatomic1 | runner apt repositories; installed versions recorded |
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

## Pilot and verification limits

The local release build reports tasks 0.4.0 (fa58ab31), SHA-256
ee4dea224770eb40d35d049802a9832a1086f784e4c9d1d4d7013452b5fca7c0.
The end-to-end fixture pilot passed both success and deliberate failure cases:
2 passed in 8.95 seconds. It executed the actual workflow evidence-preparation
shell, real portable staged validators, a real pinned tasks registry roundtrip,
four miniature partitions, identity reconciliation, wrapper cleanup and surviving
failure artifacts. Success collected/reported six cases, executed five and retained
one intentional fixture skip. The failing fixture preserved setup and partial XML
with nonzero status. Its earlier missing-authority fixture failure remains retained.
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

Proposed total: one feature verification push, then one main activation push only
after observed coverage acceptance and explicit activation authorization. No remote
retry is included. The first approval covers only the verification push above.

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
metadata, source-pin checks, pilot fixtures and report bytes remain there. The task
record binds their retention checkpoint. No raw host-specific output is published
in this packet. The feature branch remains unmerged pending the rollout gates.
