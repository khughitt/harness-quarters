## Review: implementation plan for hq-3b9c4c (Tasks 18–19, frozen at 50282b9)

Revise first. Tasks 18–19 match the approved design and the current code. But the plan promises explicit test environments for every subprocess, and Task 18 doesn't carry that through to the Codex stub. I also have two minors. Approval is still yours; the task's agent would fix these in a new frozen revision. I agree with the ruling to file the obs task during execution, and with inline execution.

**What I checked:** the plan diff from cfaed41 to 50282b9, the full text of Tasks 16–19, and these against:
- hq's current `inputs.py`, `decide.py`, `prune.py`, `config.py`, `testing.py`, `conftest.py` and the affected tests;
- the reader at 889000e;
- obs's justfile, AGENTS.md and `tools/retention_readiness.py`;
- the step tasks hq-886d78 (blocked, parent hq-3b9c4c) and hq-b60102 (depends on hq-886d78), and tasks-2591d3, which exists as an idea.

**Claims that hold:**
- **Probe adapter.** The interfaces Task 19 relies on are identical at 889000e and HEAD: `_facts(source, relpath, ctx, held)`, `Context`'s fields, `capture_file` and `Manifest`. So the probe can call each reader's own production `_facts` without any compatibility code in hq.
- **Harness mapping.** Mapping `source.kind` to the obs harness name is correct: both `claude` and `claude-work` have kind `claude`.
- **The integration tests isolate condition 3.**
  - The rewrite test captures the rewritten bytes into an empty archive and keeps the old obs evidence, so condition 2 passes.
  - The inode test uses `copy2` then `replace`, which keeps the mtime to the nanosecond, and asserts that the inode really changed.
- **The CLI malformed-row test is possible.** `cmd_prune` already records `ObsUnavailable` in the report and exits 1, and `fake_obs` already exists.
- **obs test routes are right.** `test-one` takes several modules, `test-fast` is the full unittest suite, and `gate` is `check` plus `test`.

**Important:**

1. **The environment rule isn't met for in-process tests that spawn the Codex stub.** The Global Constraints say "Every test/probe subprocess receives an environment built key by key". Task 18 only fixes `testing.run_tool` and the direct `Popen` in `test_child_cwd_restores_before_late_open_and_append`.
   - Tests that Task 18 itself edits (`test_session_archive_prune_codex.py`, `prune_links`, `prune_run`) call production code in-process. That code starts the stub with `{**os.environ, "CODEX_HOME": …}` (`prune.py:215`, `probe.py:82`).
   - The `stub_codex` fixture (`tools/conftest.py:37`) only adds to the pytest process's real environment, so the stub inherits all of it.
   - The executor would have to either widen scope on the fly or quietly break the plan's own constraint.
   - Fix options:
     - Have `stub_codex` swap in a minimal `os.environ` for the test: PATH with the stub directory, a temporary HOME, `USER=test`, the `STUB_CODEX_*` controls and fake credentials. Then add `tools/conftest.py` to Task 18's file list.
     - Or narrow the constraint to the subprocesses tests start directly, and file the in-process gap as a follow-up.

   I recommend the first, since Task 18 already edits those tests.

**Minor:**

2. **The hq branch integration isn't stated.** Task 19 Step 5 integrates the obs branch but never says how `fix/hq-3b9c4c-strict-readiness` reaches main. hq-624351 Step 1 checks "the paired acceptance revisions recorded by Task 19", so the Task 18 commit given to `--strict-rev` must stay reachable. Fix: say hq integrates by merge commit, as hq's history already does, not by rebase or squash. Otherwise, rerun the paired probe against the commit that actually lands.
3. **List fields on frozen `ObsFile`.** Task 18 Interfaces adds `not_ready: list[str]` and `identity_conflicts: list[str]` to a frozen dataclass. Its generated `__hash__` would then raise, and the record isn't truly immutable. Fix: use `tuple[str, ...]` and adjust the test assertion (`== ("future_reason",)`).

**Note for whoever records the review** (I wrote none): `review: plan round 2 — verdict: revise; findings: important 1, minor 2; reviewer: claude-code/claude-opus-5-5`
