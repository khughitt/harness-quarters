# Operator runbooks that preserve the operator's shell

Status: proposed; awaiting user review. Task: hq-c6c847; Bash work: dots-55f537.
This amends the execution arrangement of the approved relay cutover, not its
runtime pin, guard policy, migration images, or trust requirements. Implementation
requires approval of this design and then its implementation plan.

## Problem and requested outcome

The operator stopped after Titan's section 1. A long series of pasted commands
required maintaining a private environment inside interactive Bash, despite the
operator using Zsh. An unrelated failed command caused that Bash to exit, leaving
the operator in Zsh without its variables. Continuing then produced misleading
errors instead of a clear stopped phase.

The user wants short executable phases, Codex helping with Claude changes and
Claude helping with Codex checks, Zsh-native operator instructions, and more
predictable Bash failure/history behavior. They explicitly support a script for
the interval when both harnesses must close.

Success means one command for that interval, clear failure/recovery messages, no
interactive shell setup to retain, and agents doing the subsequent mechanical
work. Human hook-trust decisions, permission prompts, and desktop-use approval
remain human actions.

## Verified starting state

- The interrupted window reached Titan section 1 only. Europa had no window
  record. Neither host entered section 2; familiar and all hook targets remained
  native. Original and expected-image checksums matched.
- With explicit user approval, the exact reviewed section 1 abort restored
  Titan's recorded timer state. Original backups again have their original names;
  refreshed snapshots and the original timer record remain in the recorded
  `section1-abort.*` directory. The reaper finished successfully. No cutover is live.
- Both hosts have Claude 2.1.304 evidence. Codex evidence is 0.163.0. The installer
  accepted the fresh evidence on disposable copies, without changing them.
- Familiar's approved feature revision removes the native `hook` command. Updating
  that shared checkout while a harness still calls it would break native hooks.
  Therefore the initial familiar transition still requires both harnesses closed.
- After familiar and one harness have migrated, the controller can use that
  migrated harness to prepare/apply the other harness's hooks while the other is
  closed. The current plan's stronger all-harness/plain-shell restriction must be
  explicitly amended before this is allowed; it is not waived by this proposal.

## Proposed flow

| Phase | Who runs it | Required closed sessions | Result |
| --- | --- | --- | --- |
| Prepare | Current Codex agent | None for read-only preparation | Tested script, checked inputs and rollback ready for review |
| Bootstrap | Operator launches one foreground command from Zsh | Claude and Codex, both hosts | Familiar migrated on both hosts; Codex hooks applied to both Titan homes |
| Resume | Operator opens/resumes Codex and accepts its own hook review | Claude stays closed | Controller runs on migrated hooks; no hand-written trust hashes |
| Claude migration | Resumed Codex agent | Claude, both hosts | Both shared Claude targets dry-run, applied once on Titan, verified on both hosts |
| Validate and finish | Agents plus operator for interactive choices | Only the target of a destructive smoke, as already required | Both harnesses' smokes and scheduled reconciliation verified; original timer states restored |

Codex-first is the controller's recommendation: it lets the operator resume the
existing session and context. A fresh Claude session can then help run/observe
Codex checks. That handoff is useful for independent observation, but is not an
excuse to rewrite a running controller's hook files. No per-harness selection flag
or generic workflow engine is needed.

The initial script is project-specific. Subsequent agents use the existing
`relay-cutover`, `relay install`, and timer tools; the operator does not paste their
command bodies. The revised runbook describes outcomes, handoffs, and the few
human interactions, with a detailed reference section for investigation.

## Bootstrap command and boundary

Add `tools/relay-cutover-bootstrap`, using Python's standard library and existing
helper commands. Its executable shebang owns its interpreter; the user's command
is valid Zsh and does not enter Bash:

```zsh
.worktrees/relay-cutover/tools/relay-cutover-bootstrap run
```

This command is prospective until implementation, review, and rehearsal finish.
It runs on Titan and drives the approved Europa operations over SSH. It uses
explicit main-checkout executables on each host and never repoints a launcher,
service, config include, or home into a worktree. Remote worktrees are not assumed
to exist. The task worktree stays until cutover verification and cleanup finish.

The bootstrap performs the already-reviewed operations in this order:

1. Resolve paths and validate private prepared inputs, source revisions, exact
   installed/evidenced versions, relay runtime, subscribers, expected images and
   native before-images on both hosts. Refuse unexplained existing window state.
2. Refuse any remaining Claude/Codex session. Stop only the known personal/work
   Codex app-server daemons with their supported CLI, then require strict no-live
   checks on both hosts. Never broadly kill processes or exempt the caller PID.
3. Record/quiesce both hosts' timers, wait for their services, preserve preparation
   snapshots and refresh/verify the live backups. Recover every recorded host if
   this stage fails, including a first-host success followed by second-host failure.
4. Merge the immutable familiar feature revision once on Titan; reconcile an
   interruption between merge and record; wait for verified source synchronization
   before each host's dependency installation. Install each host's dependencies
   with the established root-only Git policy and prove the relay dependency pin.
5. Dry-run both Codex targets, verify plans against their reviewed images, then
   apply through relay with the existing artifacts and verify exact expectations.
   Shared targets are edited only once on Titan. Claude remains closed and native.
6. Print that bootstrap completed, which timers remain paused, and the short
   instruction to resume Codex and review hook trust. Do not restore timers before
   the remaining migration and reconciliation checks have completed.

Desktop surfaces need attention during the familiar transition. The script names
what will restart on each host and requests permission at that checkpoint. Approval
of the design does not grant desktop access. A refusal/failure stops the phase and
offers recovery; it does not silently skip a required restart or open windows.

The resumed controller verifies the bootstrap receipt, actual live Codex hooks,
familiar dependency on both hosts, and version evidence before changing Claude.
It checks that Claude is closed on both hosts immediately before the shared apply.
It preserves the native non-familiar groups, guards and status lines specified by
the existing cutover images. It does not touch Codex hooks while running in Codex.

## State, failures and recovery

The command loads its own protected data on every invocation. It requires no
caller variables, no `source`, and no interactive `set -e`. Use a small JSON record
under the existing private cutover root for paths, immutable pins, recorded timer
states, verified checkpoints and existing artifact locations. Do not source or
translate `operator-env.sh`; keep that old file only as retained recovery evidence.

Reuse the existing snapshot/artifact formats and byte-gated restoration helpers.
The record is durable before its associated mutation; after interruption, inspect
actual Git state, artifact presence and target bytes to determine the next safe
action. A recorded step alone never proves that its mutation completed. Use the
existing directory-fsync/atomic-write pattern where needed, rather than creating
a second general transaction framework.

Expose `check`, `run`, `status`, and `recover`. `check`/`status` are read-only and
name blockers. `run` checks existing state and refuses blind repetition; it can
continue only after validating the already-completed checkpoints. `recover` is an
explicit ordinary-shell action with the required harnesses closed, preserves
evidence, and uses the reviewed section 1 abort or full rollback as appropriate.

Every failed operation prints its named step, host, exit status, private log path,
observed completed state, and one recovery/status command. It must not print
private plans, settings, credentials, full environments or arbitrary command text.
No failure sends the operator into another shell or leaves a sourced partial
environment. Failures stop the script and return nonzero to the existing Zsh.

The script attempts the existing section 1 timer/snapshot abort when failure occurs
before familiar mutation. Failures after familiar mutation leave evidence intact
and require explicit full recovery, rather than guessing whether an external
operation partially succeeded. Recovery first re-quiesces both hosts, restores
every touched target in reverse order, reconciles/reverts familiar's actual Git
state and restores each host's retained dependencies offline. If any verification
or restoration fails, stop and identify what remains; never claim a complete abort.

Normal completion still requires scheduled reconciliation and the original timer
state on each host. The agent cannot finish/park the rollout while silently leaving
timers paused. Any handoff explicitly names the paused state and recovery command.
There are no detached monitors or background scripts; subprocesses are bounded,
tracked and reaped. A timer intentionally restored to normal service is identified
as restored host state, not an orphaned test process.

## Preserved cutover requirements

- Relay remains v0.1.1 at `4ceec5d2ad22b136b37ee360e7a4ed00949f28d9`, with
  `--node /usr/bin/node`. Familiar PRE remains
  `00f4899ae523d613d21f44bfc2c456aac67f8e5f`; its approved feature tip remains
  `a16f4daa59b04e32f1010764d6f94401ca4eed8b`.
- Exact version evidence is required; a changed installed version stops the phase
  for fresh proof. No automatic harness updates, pin changes or relaxed evidence.
- One writer per harness; native familiar retirement and relay addition stay in
  the same install. No registry import, merge or compatibility layer.
- Every live change is first tested on copies. Guard-only interruptions retain
  before/after images; restoration refuses unknown bytes.
- Preserve live model picks and trust state. Codex performs its own interactive
  trust review for each home; no trust hash is synthesized or edited by the script.
- No source/settings change from a running target harness. The common bootstrap
  requires all native writers closed; later changes require the target harness
  closed on every affected host. A currently running migrated controller may apply
  the other harness only after the approved plan explicitly adopts this boundary.
- OpenCode, Darwin, nested code-mode proof and `--with ask` remain excluded.

## Bash configuration in dotfiles

The new operator workflow uses Zsh. Bash remains supported for other work and
Claude's tool shell, whose interpreter is a separate concern.

Disposable PTYs verified that interactive `set -euo pipefail` plus a nonexistent
executable exits Bash with 127 and no Bash termination notice. Ordinary same-shell
Up recall works; Up is prefix search. Leading-space commands disappear because
`HISTCONTROL=ignoreboth:erasedups` includes `ignorespace`. Two Bash instances sharing
a fake history file also reproduced missed imports and accidental self-duplication
with the current `history -a; history -n`. These are configuration findings; the
actual user's history and private files were not read.

Recommended small changes, subject to this design's review:

- Put an explicit `bash` label in its prompt. Keep failure semantics: do not
  globally turn off intentional `errexit` or make scripts continue after failures.
- Add one interactive EXIT diagnostic for nonzero status, naming Bash and its
  exit code. Preserve the actual process status. Clean exits stay quiet. Do not
  print the failed command or variables. Do not add a second overlapping ERR trap.
- Retain the existing Up/Down prefix bindings. Retain indented commands by changing
  history control to `ignoredups:erasedups`; unlike the old Bash setting, a leading
  space will no longer suppress storage. This matches the user's existing Zsh
  retention policy but is an explicit privacy-related behavior change.
- Replace the faulty cross-shell import sequence with append then clear/reload
  using Bash's history builtins, proven with two PTYs. Only clear after append
  succeeds: a write failure must preserve in-memory history and report the error.
  Reload failure must also be visible; the successfully appended disk history
  remains recoverable. The history file is retained, not rewritten or deduplicated.
  Previously stored legitimate duplicates may be visible after reload, and
  rereading a large file has a cost; no history database, new dependency, or
  whitespace-normalization framework is introduced.
- Explain prefix Up versus substring Ctrl-R briefly. Do not claim the actual
  incident's missing command was definitely caused by indentation or another shell.

The diagnostic belongs behind the existing interactive-only guard. Noninteractive
Bash scripts/tools keep their existing behavior. Existing literal configuration
assertions must be adjusted, but real PTY behavior supplies the meaningful tests.
Dotfiles work uses its own worktree, preserves unrelated edits, and activates only
after reviewed changes and the required checks are concrete.

## General guidance in lore

The proposed instruction amendment is small and owned by lore's shell/process
fragments, then regenerated through its assembler:

- Operator commands always target the user's declared interactive shell: Zsh here.
  The shell used by an agent's tool does not select the operator's shell.
- Never ask the operator to enable interactive errexit and maintain a sourced
  environment across a long runbook. Executable tools own failure handling and
  load their state themselves.
- Prefer one checked command per unavoidable manual phase. Agents perform
  mechanical commands where harness/host-use constraints permit; document handoffs
  and require only the target harness to close when that is sufficient.
- A failure leaves a clear observed status and a short resume/recovery command.
  Persistent host changes are restored or explicitly handed over, never hidden.

The feedback entries `lore-881f7a` and `lore-8ce941` remain untriaged; implementation
is an explicitly approved user-requested change, not self-triage of those reports.
Do not edit generated instructions by hand or alter the vendored skill submodule.
Publishing live instruction or home-config changes remains separately approved
after a concrete reviewed result.

## Verification and completion

Before any new live window, exercise the bootstrap on disposable copies and test
its orchestration with explicit scratch roots/fake host commands. Cover both-host
success; each host's failure; active target rejection; source-sync refusal;
interruptions before/after timer records, backup moves, familiar merge/record, and
each Codex plan/apply; unknown target drift; and full offline recovery. Assert
actual final files, Git parents, retained artifacts and timer states, not just
command spelling. Existing pin, restore and wiring tests remain in place.

A smallest end-to-end rehearsal precedes any extended run. Confirm that failure
returns to the original Zsh prompt and requires no exported caller state. Private
outputs and copied credential cleanup retain the existing cutover protections.
Each project's declared focused/fast/full test route and hooks still apply.

Bash PTYs cover normal and indented paste recall, prefix/substring distinction,
two-shell import without accidental self-duplication, append/reload failures with
history preservation, preserved nonzero exits with a clear notice, quiet successful
exit, and unchanged noninteractive sourcing.

The revised runbook and original execution plan must agree on the new phase gates
before use. Preserve the earlier review/rehearsal evidence and interruption fixes.
Design/plan approval authorizes implementation only; the new live bootstrap is
not run from this Codex session. The operator invokes the reviewed command after
closing both harnesses and makes trust/desktop decisions at their checkpoints.

## Calls made for review

Codex-first bootstrap, standard-library Python orchestration callable from Zsh,
explicit full recovery after familiar mutation, a single Bash EXIT notice, retained
leading-space history, and builtin clear/reload are controller recommendations.
The alternative of preserving the old long interactive Bash procedure is rejected:
it preserves the demonstrated operator failure mode. A generic workflow framework,
automatic trust acceptance, shell replacement, and a third harness are out of scope.

References: the existing `docs/plans/2026-10-19-relay-cutover.md` and
`docs/runbooks/relay-cutover.md`; familiar's command table at the pinned feature
revision; dotfiles' `bashrc`, `bash_profile` and `shell/history`;
[Bash set options](https://www.gnu.org/software/bash/manual/html_node/The-Set-Builtin.html),
[history search commands](https://www.gnu.org/software/bash/manual/html_node/Commands-For-History.html),
and [history facilities](https://www.gnu.org/software/bash/manual/html_node/Bash-History-Facilities.html).
