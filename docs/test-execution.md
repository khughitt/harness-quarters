# Test execution

Type: guide; document types 1. Run focused checks, mandatory hygiene and deliberate
full-suite verification. See [architecture](architecture.md) for setup and
[capabilities](harness-capabilities.md) for the separate live probe boundary.

The invoking checkout's `.tt.toml` sets `automatic_broad = false` with
`broad_targets = ["test", "ci-test"]`. Run fresh focused checks for changed behavior
and mandatory hygiene; broad suites run deliberately or in the hosted workflow.
Only a landed policy in registered main retires its local broad latency obligations.

| Command | Behavior |
| --- | --- |
| `just test` | Records a policy skip before requesting host-budget or starting tests |
| `just test-one <pytest arguments>` | Protected focused route through tt and host-budget; requires arguments |
| `just test-full` | Sets TT_FORCE=1 for just test; records one broad run |
| `just ci-test` | Skips locally; with TT_FORCE=1 runs the same suite with explicit positive PYTEST_XDIST_AUTO_NUM_WORKERS |
| `just check-hygiene` | Protected complete local pre-commit validation |
| `just ci-hygiene` | Protected portable validation, recorded as hook-ci-hygiene |

The hosted route sets neither force nor a local budget fallback. A hosted workflow
must set TT_FORCE=1 itself. Both test and ci-test are broad targets. A policy skip
starts neither a runner nor host-budget,
records null outcomes, and supplies no correctness evidence. A hosted would-be
skip without force is an error, including through nested wrappers.

All test processes use the system Python, pytest 9.2.0 and pytest-xdist 3.8.0.
The suite first validates capability facts, then collects all tests under agents/bin,
.githooks and tools, and executes these two partitions serially:

1. agents/bin.
2. .githooks and tools.

Both partitions run serially; the local `just test` recipe enforces the `host-budget`
route, while `tools/test-suite` validates a positive integer
`PYTEST_XDIST_AUTO_NUM_WORKERS`. The suite driver takes no selectors; focused
selection belongs to test-one. The fixed suite ignores PYTEST_ADDOPTS so ambient
selectors and worker flags cannot alter its inventory or partitions.
Full local pre-commit hygiene remains mandatory.

## Hygiene and push hooks

The default pre-commit hook refuses staged local/ state, runs ops-check and
ops-docs check against the working tree, then exports the staged tree once for
harness-facts and harness_state.py validation. The staged manifest, attributes,
cleaned config blobs and repository filter configuration are all checked. The
same export checks the staged Codex developer instructions and hook routes.

The explicit --ci mode omits ops-check, the lore-dependent Codex check and the
HOME-dependent hook-routes check. It keeps staged-local-state refusal,
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

The output contains inventory.json, coverage.json and two JUnit reports:
pytest-agents.xml and pytest-hooks-tools.xml. Inventory records collection errors and module skips;
coverage reports unique collected/reported/executed identities, per-test skips,
excluded modules, skipped module count and problems. Collection omissions,
missing reports, cross-partition overlap, replaced identities and empty execution
fail verification. Multiple call/teardown reports for one test count once.

A failed partition stops later partitions and preserves available evidence;
unrun partitions are unverified. Report failures fail an otherwise successful
suite and never replace an existing runner failure. A cancelled or interrupted
attempt is unverified. Retain caller-owned evidence for inspection; do not upload
from TT_JUNIT_DIR after the wrapper returns.

The workflow uses ubuntu-24.04, sets PYTEST_XDIST_AUTO_NUM_WORKERS="2" (satisfying the
suite driver's positive-integer check while both partitions run serially) and a finite 60-minute
job limit. It pins uv 0.13.7, just 1.59.0, Node 26.13.0, Rust 1.99.1 and public
tasks commit 7838de53af433fd367c15c0891d6c8a7e780f330. System Python, zsh and
libatomic1 come from the runner; actual versions are recorded. Setup explicitly
fetches historical commit 6b434eb206c4464c062137e3600dcd303a543f68, which the
rollback tests need but advertised branch history does not contain. It installs
public work-link from dotfiles commit 2a686c0c4915ba0daae9f6455cfe45233780fc33,
checking SHA-256 6400d9a8431d3af3777d5038716d4322d283ebd127c574c06d7516dd1a784ff4.
The runner explicitly installs and reports attr, required by work-link's worktree
storage route, together with curl for the verified download.
The disposable runner installs
tools at the exact /usr/bin paths its fixtures use. It runs setup,
portable hygiene and the same complete suite, with TT_FORCE=1 at job scope.
The job prepares three relay installations under a temporary `HQ_TEST_RELAY_ROOT`.
The v0.5.0 hook and qualification tests use the frozen lock from hq commit
`0bfce24bdc62a91e0376dd39123f074f354310e8`. The SessionStart notice tests use v0.6.0
from the frozen lock of hq commit `614907c5def98349a90274f1ff884d6fbfe188b1`. The
standalone launcher and schema-3 tests use v0.7.0 from the checkout's `just relay-install`.
The preflight tests exercise every version. A missing installation there fails the tests.
All branch pushes and manual dispatch are covered, with no duplicate PR trigger.

The always-run artifact upload retains HQ_TEST_ARTIFACT_DIR for seven days. Its
setup-report.txt records setup; the initially empty suite/ child is
HQ_TEST_EVIDENCE_DIR and holds the inventory, coverage and two reports. A failed
setup or partial run retains available evidence and remains unverified.

The accepted hosted omissions are these exact local integration checks:

- tools/test_harness_links.py::test_registered_owner_targets_match_portable_fixture_shapes
- tools/test_hook_routes_equivalence.py::test_real_replay_leaves_host_untouched, when a required owner command is absent

The equivalence test runs the installed index-repair owner and the copied hq refresh
against independent disposable checkouts. It also checks one real mixed-notice
dispatch, the private PID namespace and absence of host process handles in the
fixture registry and supervisor. The remaining equivalence tests call the pinned
hosted relay for budget admission, then use fixture transport observations for
command output and evidence checks. They require no namespace privileges.

Portable owner fixtures exercise link behavior without private checkouts. The local
integration check uses the local project registry to copy real owner targets and
compare their shapes. The hosted suite includes agy relay dispatch, the pinned
budget check in `tools/test_hook_routes_relay.py`, and the qualification and
preflight cases. No module is excluded. The local preparation pilot exercises
two miniature partitions and failure retention.
The separate mods and live capability probes are outside just test.
