# Test execution

The execution policy is currently absent, so broad tests run locally. Hosted
verification is being prepared; it has not been activated or observed.

| Command | Behavior |
| --- | --- |
| `just test` | tt decides, then host-budget runs the complete suite |
| `just test-one <pytest arguments>` | Protected focused route through tt and host-budget; requires arguments |
| `just test-full` | Sets TT_FORCE=1 for just test; records one broad run |
| `just ci-test` | tt decides, then runs the same suite with explicit positive PYTEST_XDIST_AUTO_NUM_WORKERS |

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

The proposed hosted boundary omits two sibling-dependent tests, one in each of
tools/test_relay_subscribers.py and tools/test_agy_hooks.py, with no modules
excluded. This is intended coverage awaiting an observed hosted run and user
acceptance, not current hosted proof. The separate mods and live capability probes
are outside just test.
