# Rename receipt consumption — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Status: proposed, revision 1; awaiting human plan review. Owner: hq-74f102.

**Goal:** Finish forward cutovers without a stale receipt, preserving rollback,
commit warnings and the current hosted coverage contract.

**Architecture:** `apply` commits the rename before moving and, for a detached
checkout, commits the relocated config afterward. The existing guards and verify
gain explicit receipt checks. Reuse the current sandbox suite; record real-hook
compatibility as a local rehearsal rather than a new collected integration test.

**Tech Stack:** Python standard library, tasks CLI, Git, just; existing pytest
front door and work-link. No dependency or tasks implementation changes.

**Spec:** docs/specs/2026-11-09-rename-receipt-design.md, approved revision 2 at
hq commit f975b51ceb554f9df229d10d22b6f10314c436ab; sha256
355f81998253019b544ee39147f6b49f30673a21bfa542b7a0c11d077699db24.
Spec round 2 and Keith's approval are saved in
docs/notes/2026-11-09-rename-receipt-spec-round-2-report.md.

## Global constraints

- Work in `.worktrees/hq-74f102`, branch `fix/hq-74f102-rename-receipt`, based
  on `main`. Inline execution is recommended: one cohesive code task and one
  acceptance rehearsal, followed by independent whole-branch review.
- Preserve the approved spec unchanged. Its receipt identity/digest invariants,
  rollback window, source preservation and warning policy remain binding.
- Both tasks commit calls pass explicit `--json`, including with
  `TASKS_FORMAT=pretty`. Successful warnings are printed, never executed.
- Real-hook acceptance is a one-off local recorded rehearsal. Add no collected
  local-only test and do not change the three hosted omissions in
  docs/test-execution.md. This is a test on disposable stores, not a live rename.
- Setup re-enters using-git-worktrees, confirms hydration and validates this
  checkout's `.tt.toml`. Run focused baseline
  `just test-one tools/test_rename_cutover.py`, recording command, exit and count;
  deliberately omit broad tests under `automatic_broad = false`.
- Before code edits, initialize the execution workspace at
  `$WORK_ROOT/hq/hq-74f102/plans/rename-receipt/`, owned by the open parent.
  Record its creation and frozen plan revision immediately. Resolve lore through
  `tasks projects`, then use its explicit bin/plan-workspace-init on the empty
  directory before any other write there; use bin/plan-task-start and
  bin/plan-task-done with that explicit workspace and canonical plan path. No
  worktree-local execution workspace. Keep ledger, raw logs and rehearsal there.
- Every fixture/rehearsal subprocess uses an environment built key by key:
  PATH, owned temporary HOME/XDG dirs, fake USER, isolated Git config and explicit
  Git author/committer values. No inherited GIT_* state or credentials. Assert
  top-level and absolute git-dir containment before the first repository write.
- Use existing layout and helpers. No compatibility methods for removed manual
  commit steps, no general runner framework or unrelated refactor. `just
  check-hygiene` is mandatory before commits. Task and retention writes use tasks.
- No push, live home-link apply or live cutover is authorized by this plan.

## Review focus

1. Pretty-format environment must not break JSON parsing: Task 1 tests both
   commit boundaries with TASKS_FORMAT=pretty and verifies explicit --json.
2. A hook can fail before or after the move: Task 1 asserts the two distinct
   states and successful rollback, retaining raw failures.
3. Old rollback cases must still exercise uncommitted/interrupted renames:
   Task 1 constructs those states directly instead of keeping obsolete helpers.
4. Original state can contain an unchanged unrelated inventory: Task 1 validates
   only changed/new inventories and preserves originals on rollback.
5. A passing sandbox without the real hook says nothing about hook compatibility:
   Task 2 runs the normal hook against frozen hq inputs and records its result.

## Step records

| Step | Task | Depends on |
| --- | --- | --- |
| 1 — tool and regression tests | hq-155ccf | approved plan |
| 2 — recorded local rehearsal | hq-5e90dd | hq-155ccf |

---

### Task 1: Commit cutover writes and enforce receipt ownership

**Files:** Modify `tools/rename-cutover` and `tools/test_rename_cutover.py`.
The tool's docstring becomes the current operator contract and cites the new
amendment; historical approved designs/runbooks remain historical.

**Interfaces:** Consume existing `run(*cmd, cwd=None) -> str`, `Stop`,
`load_meta`, `Sandbox.run`, `Sandbox.save`, `Sandbox.cutover` and fingerprint
helpers. Add `commit_tasks(root: Path, *args: str) -> None`: run
`tasks --json commit <args>` in root, validate object plus list-of-string warnings,
and write every warning verbatim to stderr identifying the command. It returns
only after valid output; nonzero commands still raise through `run`.

- [ ] **Step 1: Add the smallest failing tests, then observe RED.** Use existing
  Sandbox stores for real command integration and module-level monkeypatches for
  exact warning/report boundary checks. Add these named assertion contracts:

  ```python
  def test_commit_tasks_forces_json(monkeypatch, tmp_path):
      cutover, calls = load_cutover(), []
      monkeypatch.setenv("TASKS_FORMAT", "pretty")
      def run(*cmd, cwd=None):
          calls.append((cmd, cwd))
          return '{"warnings": []}'
      monkeypatch.setattr(cutover, "run", run)
      cutover.commit_tasks(tmp_path, "--project", "tack")
      assert calls == [(("tasks", "--json", "commit", "--project", "tack"), tmp_path)]
  ```

| Test / parameter cases | Required assertions |
| --- | --- |
| `test_apply_commits_before_move`, in-tree/detached | At the receipt commit the original checkout exists; receipt consumed before move; after apply no receipt or dirty rename paths; detached config is committed with its new path |
| `test_commit_tasks_forces_json`, both call vectors | Exact command begins tasks --json commit; TASKS_FORMAT=pretty cannot change the parse; no positional target on rename commit, only tasks/.config.toml and the required -m on relocation |
| `test_commit_tasks_surfaces_warnings`, each boundary | Both predecessor separate-repository and staged-recovery example warnings, including recovery commands, appear on stderr; execution continues; no suggested command runs |
| `test_commit_tasks_rejects_malformed_reports` | Non-JSON, non-object, missing/non-list warnings and non-string members raise Stop at that boundary |
| `test_apply_hook_refusal_rolls_back`, receipt/relocation | Real refusing fixture hook gives nonzero; receipt failure leaves original checkout and receipt; relocation failure leaves moved checkout, consumed receipt and dirty config; both restore fingerprint on rollback |
| `test_later_bare_commit_after_cutover`, both layouts | After apply, edit an existing renamed task, then bare tasks --json commit --project tack succeeds and no stale receipt reappears |
| `test_receipt_presence_refused`, save/apply/verify | Existing receipt, including dangling symlink or unreadable entry, is named and left alone; save creates no snapshot, apply performs no rename, verify cannot succeed |
| `test_guard_inventory_types`, source/target/root | Malformed non-string values produce Stop, never TypeError; changed foreign inventory still refuses without mutation |
| `test_guard_preserves_unchanged_saved_inventory` | Saved unrelated inventory unchanged at rollback is restored unchanged; valid newly changed inventory is accepted; foreign changed inventory refuses |

  For unreadability, simulate a denied read deterministically if permissions do
  not enforce it under the runner; presence checks themselves must not open it.
  Run relevant nodes through `just test-one <file>::<test>` as introduced, keeping
  actual RED output in the workspace. Do not demand that every new test fail for
  the same missing helper; each behavior gets a targeted break if already covered.

- [ ] **Step 2: Implement the shared commit report handling and apply order.**
  Add `commit_tasks` with the above contract, patterned on `committed_check`'s
  explicit output validation. In `apply`: refuse existing target receipt, rename,
  receipt commit from original root, require receipt absent, move/relink/repoint,
  then detached config commit from new root. Report applied only after both
  commits finish. Keep the exact relocation subject from the spec. Remove the
  manual commit printout and document partial failure states in the docstring.

- [ ] **Step 3: Implement presence and guard checks.** In `save`, refuse the
  target receipt before making the snapshot; repeat in `apply`. In `verify`,
  refuse a remaining target receipt before success. Count symlink/directory
  entries as present too. In `guard`, compare saved/live inventory bytes first
  and validate only changed/new live inventories; `validate_inventory` checks
  strings before path conversion. Keep unrelated-state comparisons unchanged.

- [ ] **Step 4: Update fixture callers and old assertions together.** Remove
  `Sandbox.commit_rename`, `commit_line` and stored `applied` stdout when no
  longer needed; make `apply()` return the command result directly. Remove
  redundant post-apply rename commits. In `build_hq`, consume the earlier
  ai→tack rename's receipt through the real tasks commit route. Rework tests
  asserting an uncommitted rename or surviving receipt after successful apply:
  invoke tasks rename directly, inject the known stop/failing hook before commit,
  or stop after move before relocation commit, depending on their stated case.
  Preserve tests for stopped rename stages, trust restoration, attachments,
  retry after partial restore, outside-project drafts and second-host adoption.
  A detached config-only commit must leave another project's staged/untracked
  material out; an already-staged file may correctly refuse the commit.

- [ ] **Step 5: Verify GREEN and commit.** Run
  `just test-one tools/test_rename_cutover.py` and `just check-hygiene`; all
  selected tests must pass with nonzero count. Save counts, tested revision and
  any skips/limits. Commit code/tests as
  `fix(rename-cutover): consume receipts before moving checkouts`.
  Complete Task 1 using saved focused evidence and the execution completion
  contract; Task 2 uses this actual full commit, not a guessed SHA.

**Expected:** apply owns both commits, later bare commits work, all receipt/guard
failure cases preserve rollback, and the focused sandbox suite passes. Real hq
hook compatibility remains Task 2's independent acceptance obligation.

### Task 2: Record real-hook acceptance before guide edits

**Files:** Create only task-owned rehearsal inputs, driver and raw logs in the
external execution workspace. Attach a portable evidence report to this child
task, then cite it from hq-74f102. No new collected test or CI omission.

**Interfaces:** Consume Task 1's committed candidate and sandbox isolation
contract. Produce a revision-bound report with source commits, commands, actual
exit statuses, hook output, guide/identity comparisons and explicit verdict.
Use one task-owned `real-hook-rehearsal.py` driver: `run` prepares and exercises
the case, while `verify` checks its saved status, source revisions, log presence,
hook trace, receipt absence, committed records and guide bytes without rerunning
the hook. Run the latter through plan-task-done after preserving the report;
it must exit nonzero on a missing or contradictory assertion.

- [ ] **Step 1: Prepare one disposable local case.** Record candidate HEAD and
  resolve ops via tasks projects. Materialize candidate hq and committed ops
  sources in separate fresh repositories under the rehearsal directory, without
  shared Git config, index, worktrees or mutable host inputs. Use Git export/clone
  from pinned commits; do not copy local/ or harness live picks. hq's real
  `.githooks`, identity, guides, manifest, attributes and checker/probe inputs
  remain byte-identical to the candidate. Its rehearsal tasks records may be
  replaced with two synthetic records before the baseline commit, keeping the
  real in-tree config shape and pre-commit inputs. If the normal checker needs
  other registered reference owners, materialize their committed sources in the
  same isolated registry, recording each commit; never point it at live stores.
  Run `just setup` in the hq copy and the declared hydration route for any other
  copied repository in which code will run. Keep ops reachable through the
  isolated registry for adopted-copy validation. Save a clean rehearsal baseline.

- [ ] **Step 2: Exercise the exact pre-move commit boundary once.** Save bytes
  and hashes of identity.toml, README.md and AGENTS.md. In the old rehearsal
  checkout run `tasks --json rename hq receiptprobe`, then
  `tasks --json commit --project receiptprobe` from the same old root, exactly
  matching Task 1's receipt command. Run its actual normal pre-commit hook
  (`core.hooksPath=.githooks`), including ops-check, ops-docs and both staged
  checks, with no --ci, stand-in, hook bypass or edits to identity/guides. Capture
  the command's complete stdout/stderr and status. Set GIT_TRACE to a task-owned
  trace file so Git records the actual .githooks/pre-commit invocation even when
  tasks captures successful Git output. Assert exit 0, target receipt
  absent, renamed tasks committed and identity/guides byte-identical. Confirm
  the configured hook and record the resulting commit and command output; an
  unchanged-file claim is supported by bytes, not by a clean marker alone.

- [ ] **Step 3: Inspect the verdict and preserve evidence.** PASS requires all
  Step 2 assertions, with actual normal-hook execution. If preparation fails,
  distinguish missing fixture context from a hook rejection caused by rename
  ordering. Supply only demonstrated missing sandbox inputs and rerun; do not
  weaken checks. A demonstrated ordering conflict stops for the spec amendment
  required by revision 2. Record raw evidence under the persistent workspace and
  attach a small portable report with real exit status and exact candidate.
  Follow raw/portable retention fallback for any layout refusal. Do not mark
  this obligation passed from the ordinary synthetic sandbox tests. Run the
  driver's verify mode through plan-task-done while the sandbox is still present.
  After the report and needed raw evidence are preserved and checked, discard regenerable
  sandbox repositories with an explicit disposition; retain the small driver,
  input revision inventory and logs, not duplicate checkouts indefinitely.

**Expected:** a documented normal-hook pass at the pre-guide-edit boundary for
the candidate implementation, or a precise blocking conflict returned for design
amendment. This is local evidence and makes no hosted coverage claim.

## Completion and integration

Self-check this plan against every approved spec paragraph before freezing it.
After human plan approval, record the planned gate with both child tasks filed;
do not start either child before that approval.

After both tasks finish, check branch freshness with
`git merge-base --is-ancestor main HEAD`. If main has moved, merge it, resolve
conflicts and rerun affected focused checks/hygiene; rerun the real-hook rehearsal
if its tool or hook inputs changed. Record merge and evidence in the ledger.
Dispatch one fresh whole-branch review against the actual frozen candidate SHA,
approved spec, plan and saved evidence, using a unique report path in the external
workspace. Reviews follow the user-defined severity, corrective-round caps and
saved-evidence rules. No extra reviewer for bookkeeping or the rehearsal command.
Record review rounds before dispositions; deferred findings need an open owner.

Close with policy-appropriate focused evidence, mandatory hygiene, review and
retention accounting. The implementing agent may merge the reviewed branch
locally into main under the personal profile; no push. Keep plan-ledger rulings,
review reports and needed raw rehearsal evidence discoverable from hq-74f102
before worktree cleanup. All surviving processes/items and unmerged branch state
are accounted for at park/done. Generic whole-suite requirements do not override
the invoking checkout's valid policy-off setting.
