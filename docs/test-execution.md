# Test execution

The execution policy is currently absent, so broad tests run locally. The first
hosted verification failed; coverage has not been accepted and policy is not activated.

| Command | Behavior |
| --- | --- |
| `just test` | tt decides, then host-budget runs the complete suite |
| `just test-one <pytest arguments>` | Protected focused route through tt and host-budget; requires arguments |
| `just test-full` | Sets TT_FORCE=1 for just test; records one broad run |
| `just ci-test` | tt decides, then runs the same suite with explicit positive PYTEST_XDIST_AUTO_NUM_WORKERS |
| `just check-hygiene` | Protected complete local pre-commit validation |
| `just ci-hygiene` | Protected portable validation, recorded as hook-ci-hygiene |

The hosted route sets neither force nor a local budget fallback. A hosted workflow
must set TT_FORCE=1 itself. Both test and ci-test are the broad targets when policy
is eventually activated. A policy skip starts neither a runner nor host-budget,
records null outcomes, and supplies no correctness evidence. A hosted would-be
skip without force is an error, including through nested wrappers.

All test processes use the system Python, pytest 9.2.0 and pytest-xdist 3.8.0.
The suite first validates capability facts, then collects all tests under agents/bin,
.githooks and tools, and executes these partitions:

1. agents/bin.
2. .githooks and tools, excluding the two relay-cutover modules.
3. Both relay-cutover modules under xdist, excluding the process-signal test.
4. The process-signal test serially.

Local xdist uses the worker grant. The suite driver takes no selectors; focused
selection belongs to test-one. The fixed suite ignores PYTEST_ADDOPTS so ambient
selectors and worker flags cannot alter its inventory or partitions.
Full local pre-commit hygiene remains mandatory.

## Hygiene and push hooks

The default pre-commit hook refuses staged local/ state, runs ops-check and
ops-docs check against the working tree, then exports the staged tree once for
harness-facts and harness_state.py validation. The staged manifest, attributes,
cleaned config blobs and repository filter configuration are all checked.

The explicit --ci mode omits only ops-check. It keeps staged-local-state refusal,
guide identity validation and both staged checks over that same exporter. It
needs no private sibling checkout or tasks registry. Cross-project references,
layout, conflicts, scratch and vendored-copy hygiene remain full local checks;
portable hygiene does not claim them as hosted coverage.

Both hook-pre-push and hook-pre-push-fast compose check-hygiene then test, with
no differently selected suite or outer composite timing. A hygiene failure stops
before the broad request. The unchanged shared hook validates ref input, clears
inherited Git-local variables, forwards the ref bytes and refuses a zero SSH
keepalive. It declares origin and refs/heads/* to match the prepared all-branch
workflow; tags and other remotes have no declared hosted suite. A policy-off
uncovered push warns without forcing a local suite. These declarations are not
proof that a remote job ran. Hosted verification and policy activation remain
separate acceptance gates.

## Evidence

Set HQ_TEST_EVIDENCE_DIR to an absolute, empty caller-owned directory to retain
reports after tt exits. A nonempty directory is refused, preserving earlier bytes.
Without it, local evidence lives in TT_JUNIT_DIR and tt removes it after reading
timings. The shared driver copies completed caller-owned JUnit reports into that
temporary directory before exit, so local timing collection still works.

The output contains inventory.json, coverage.json and four JUnit reports:
pytest-agents.xml, pytest-hooks-tools.xml, pytest-relay-parallel.xml and
pytest-relay-signal.xml. Inventory records collection errors and module skips;
coverage reports unique collected/reported/executed identities, per-test skips,
excluded modules, skipped module count and problems. Collection omissions,
missing reports, cross-partition overlap, replaced identities and empty execution
fail verification. Multiple call/teardown reports for one test count once.

A failed partition stops later partitions and preserves available evidence;
unrun partitions are unverified. Report failures fail an otherwise successful
suite and never replace an existing runner failure. A cancelled or interrupted
attempt is unverified. Retain caller-owned evidence for inspection; do not upload
from TT_JUNIT_DIR after the wrapper returns.

The prepared workflow uses ubuntu-24.04, two pytest workers and a finite 60-minute
job limit. It pins uv 0.13.7, just 1.59.0, Node 26.13.0, Rust 1.99.1 and public
tasks commit fa58ab31acd757f59798537b6957e540fdccb9fb. System Python, zsh and
libatomic1 come from the runner; actual versions are recorded. Setup explicitly
fetches historical commit 6b434eb206c4464c062137e3600dcd303a543f68, which the
rollback tests need but advertised branch history does not contain. It installs
public work-link from dotfiles commit 2a686c0c4915ba0daae9f6455cfe45233780fc33,
checking SHA-256 6400d9a8431d3af3777d5038716d4322d283ebd127c574c06d7516dd1a784ff4.
The runner explicitly installs and reports attr, required by work-link's worktree
storage route, together with curl for the verified download.
These setup corrections await an authorized verification retry. The disposable
runner installs tools at the exact /usr/bin paths its fixtures use. It runs setup,
portable hygiene and the same complete suite, with TT_FORCE=1 at job scope.
All branch pushes and manual dispatch are covered, with no duplicate PR trigger.

The always-run artifact upload retains HQ_TEST_ARTIFACT_DIR for seven days. Its
setup-report.txt records setup; the initially empty suite/ child is
HQ_TEST_EVIDENCE_DIR and holds the inventory, coverage and four reports. A failed
setup or partial run retains available evidence and remains unverified.

The proposed hosted omissions are these exact integration checks:

- tools/test_relay_subscribers.py::test_template_validates_against_registered_relay_budgets
- tools/test_agy_hooks.py::test_relay_v030_agy_dispatch_with_rendered_subscribers_and_ops_relay_guard
- tools/test_harness_links.py::test_registered_owner_targets_match_portable_fixture_shapes

The third is an additional proposal beyond the approved design's two omissions.
Portable owner fixtures exercise the existing link behavior tests without private
checkouts; the added local integration check also copies the real registered
targets and compares their shapes. No module is excluded. This boundary awaits
an observed hosted run and user acceptance. The local preparation pilot exercises
four miniature partitions and failure retention, not Ubuntu or hosted coverage.
The separate mods and live capability probes are outside just test.
