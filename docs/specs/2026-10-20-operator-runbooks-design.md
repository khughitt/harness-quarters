# Operator runbooks that preserve the operator's shell

Status: revised proposal after spec round 4; awaiting user review.
Bootstrap/runbook: hq-c6c847. Independent Bash work: dots-55f537.
Independent instruction work: lore-4c1787.
This amends the execution arrangement of the approved relay cutover, not its
runtime pin, guard policy, migration images, or trust requirements. Implementation
requires approval of this design and then its implementation plan.

## Problem and requested outcome

The operator stopped after Titan's section 1. A long series of pasted commands
required maintaining a private environment inside interactive Bash, despite the
operator using Zsh. An unrelated failed command caused that Bash to exit, leaving
the operator in Zsh without its variables. Continuing then produced misleading
errors instead of a clear stopped phase.

The user wants short executable phases, agents helping with the other harness's
work, Zsh-native operator instructions, and more
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
  `section1-abort.l0b7qF` directory. The reaper finished successfully. No cutover is live.
- Both hosts have Claude 2.1.304 evidence. Codex evidence is 0.163.0. The installer
  accepted the fresh evidence on disposable copies, without changing them.
- Familiar's approved feature revision removes the native `hook` command. Updating
  that shared checkout while a harness still calls it would break native hooks.
  Therefore the initial familiar transition still requires both harnesses closed.
- Applying only Codex first would make its first guarded controller session apply
  Claude while recovery also needs the shared familiar rollback. The revised
  recommendation applies all four reviewed targets in one closed-harness script.
  Agents assist each other's verification afterward; no agent applies hook changes.

## Proposed flow

| Phase | Who runs it | Required closed sessions | Result |
| --- | --- | --- | --- |
| Prepare | Current Codex agent | None for read-only preparation | Tested script, checked inputs and rollback ready for review |
| Bootstrap | Operator launches one foreground command from Zsh | Claude and Codex, both hosts | Familiar migrated on both hosts; all four shared hook targets applied and recorded |
| Resume | Operator uses the printed explicit Codex command and reviews personal-home hook trust | No mutation of running harness configuration | Controller proves its own current relay row before doing further work |
| Validate | Codex assists Claude checks; Claude can assist Codex checks | Sessions follow the existing smoke's lifecycle | Live smokes, both Codex homes' human trust reviews, permissions and projection checks completed |
| Finish | Agent invokes the same tool's `finish` | No destructive hook/source operation | Recorded timer states restored; scheduled reconciliation and final evidence verified |

All-target bootstrap is the controller's recommendation over Codex-first apply.
The cost is a few more minutes with both harnesses closed. It preserves the
approved rule against applying from inside a harness, puts every target under one
recovery record, and avoids an unfamiliar guard refusing a controller's partial
Claude migration. This replaces agent-led application with agent-led checks;
approval of the revised design must cover that tradeoff. Codex can still resume
the existing session and context. No harness-order flag or workflow engine is needed.

The script is project-specific and reuses `relay-cutover`, `relay install`, and
timer tools. Agents run verification and finalization, not settings changes.
The operator does not paste their command bodies. The runbook describes outcomes,
handoffs and human interactions, with a detailed investigation reference.

## Bootstrap command and boundary

Add `tools/relay-cutover-bootstrap`, using Python's standard library and existing
helper commands. Its executable shebang owns its interpreter; the user's command
is valid Zsh and does not enter Bash:

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap run
```

This command is prospective until implementation, review, and rehearsal finish.
It runs on Titan and drives the approved Europa operations over SSH. It uses
explicit main-checkout executables on each host and never repoints a launcher,
service, config include, or home into a worktree. Remote worktrees are not assumed
to exist. The task worktree stays until cutover verification and cleanup finish.

Before the window, land any new/changed remote helpers in a reviewed inert prefix
on hq main, as Task 5 did, without merging hook after-images or activating services.
Prepare a private manifest of the tested helper SHA256s: the bootstrap/remote
entry, `tools/relay-cutover`, `tools/quiesce-timers`, `relay/bin/relay`, subscriber
template and referenced installer/evidence inputs. `check` compares these bytes
in the controller worktree, Titan main and Europa main. Record source commits;
check familiar HEAD/merge parents and tracked source separately. A commit name
alone does not prove the executing helper bytes match. Missing/mismatched helpers
block the window; do not rely on Dropbox having a worktree or finishing early.

The bootstrap performs the already-reviewed operations in this order:

1. Resolve paths and validate private prepared inputs, the helper manifest, exact
   installed/evidenced versions, relay runtime, subscribers, expected images and
   native before-images on both hosts. Run the SSH, credentials, user-bus and
   desktop checks below. Obtain this run's desktop restart consent before the
   first mutation. A refusal is a preflight stop with no timer/source change.
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
5. Dry-run all four targets on Titan copies and both Claude targets on Europa
   copies, using each host's own installer, runtime and evidence. Before each live
   mutation durably register that target, its captured original and artifact path in the shared ordered
   touched-target record, including Claude guard removal before relay apply.
   Verify each plan against its reviewed image, apply through relay with an
   artifact, and verify the applied image. Edit each shared target only on Titan;
   verify every affected host's synchronized bytes, familiar source/dependencies
   and exact evidence. Durably record the verified migration checkpoint only
   after all these checks pass. Claude and Codex stay closed during application.
6. Restart the previously approved familiar surfaces using their validated local
   desktop contexts; verify replacement processes or the approved absent state.
   A surface-only failure after the verified migration leaves “migrated, surfaces
   pending”, with a consented surface-only retry; it does not force rollback.
   Print the observed state, exact resume commands below, and paused timer state.
   Do not restore timers before smoke/reconciliation prerequisites are complete.

### SSH and desktop checks before mutation

`check` probes Europa through the same noninteractive, `BatchMode` SSH entry and
remote helper that `run` will use. The login shell is Zsh. Use a fixed, safely
quoted helper entry and structured request data/argv; do not interpolate arbitrary
paths, scripts or environment assignments into remote shell strings. No interactive
Bash setup or assumed shell startup file supplies prerequisites.

- Resolve and validate the remote HOME, UID, explicit PATH/executable locations,
  `XDG_RUNTIME_DIR` and accessible systemd user bus. Query the actual units through
  that bus. Preserve required nonsecret identity such as USER for tools using it.
- Prove noninteractive Git authentication for familiar-theme's existing SSH pin
  through that same transport and Git/SSH configuration. A working SSH agent is
  one supported route, not a requirement when another configured authentication
  route works. Do not create keys, forward agents implicitly or log key material.
  Probe the actual pinned source access; a local install's credentials do not
  establish Europa readiness.
- Inspect both familiar surfaces on each host and record their exact expected
  startup commands and PIDs. Resolve a trusted desktop-session `NIRI_SOCKET` and
  prove read-only niri IPC using that explicit socket. An inherited socket is
  not assumed; a missing or ambiguous context while surfaces are present blocks
  before mutation. Never use sudo or guess another user's socket.
- Preserve the runbook's specifically explained absence: a host with neither
  configured/running surface may have an explicit per-host absence reason and
  process-inventory receipt. Do not spawn absent surfaces. A missing socket,
  partially missing surface or failed IPC is not itself evidence of that absence;
  stop for inspection unless that configuration is explicitly explained.
- In `run`, name what will restart on which hosts and obtain consent before
  mutation, for this foreground invocation only. Revalidate the recorded socket,
  commands and process identities immediately before restart. A recorded PID
  exiting is expected: start its recorded command. A PID reused by another process
  is not that recorded surface. A changed socket/command or an unrecorded new
  surface process stops the restart for inspection; never kill or restart a new
  target silently. Validate replacement processes after spawning. A retry asks
  again, inventories any replacements already started by a partial attempt, and
  starts only missing recorded surfaces. Design approval,
  preparation probes and an old run's consent grant no desktop access.

Task 7 already ran Europa's real throwaway familiar merge/install/offline rollback
over `ssh -4 -o BatchMode=yes europa 'umask 077; python3 -'`: the retained Task 7
report's “Familiar disposable rehearsal on both hosts” records npm12 install 9.9s,
approved relay pin and offline dependency equality. That establishes historical
feasibility, not the new runner's transport or today's environment. Repeat the
defined pilot below through the implemented runner's own entry before use.

### Resume and proof that hooks run

Preparation captures the selected Codex executable and the controller's native
personal-home session ID. `run` prints a complete Zsh-quoted command with concrete
executable, `CODEX_HOME` and session ID. Its argv is `env`, the explicit
`CODEX_HOME=<resolved-personal-home>` assignment, the validated executable,
`--no-daemon`, `resume`, and the captured native session ID. The operator receives
real values with no placeholders or environment preparation. The work-home command
similarly supplies its own explicit `CODEX_HOME` and the validated executable.
Do not use `cor`, `co`, sandbox/approval
bypass flags or hook-trust bypass flags; their effect on hook review is not proven
by the capability facts. No manual trust hash or approval shortcut is permitted.

The controller's first operation is a read-only `relay list --json` check for its
own row. Match native session identity, harness, host and current process/liveness;
require a fresh startup/tool observation, not a stale row from an earlier attempt.
A missing/stale row stops further rollout work: report the trust/startup blocker
and use the printed safe trust/resume path, not configuration edits from that
session. A row proves event delivery, not the entire guard or smoke matrix.
Next verify the receipt, all four live images on their affected hosts, familiar
dependency and version evidence, then run the existing allow/context/denial and
lifecycle smokes. Codex's work home needs its own human TUI hook review and smoke;
print an explicit work-home command with `CODEX_HOME` and no bypass flags too.

Resumed controller sessions use each home's default sandbox and approval policy.
Dedicated smoke sessions retain the runbook's explicit manual-permission/sandbox
flags so human approval remains observable. Expect human permission prompts for
observer checks over SSH and `finish`'s SSH/user-systemd
operations. A declined permission leaves the named check/finalization pending; it
does not justify a bypass flag or an automatic passed verdict.

Record smoke results through `record-smoke --receipt <private-file>`. The plan
defines the receipt schema for the existing full-personal and short-work/Europa
matrices: window ID, host, harness/home, native session ID, tested versions, each
required case's verdict and private evidence paths, plus the operator's attestation
for human trust/permission decisions. The agent gathers observations; the operator
supplies those human verdicts. The tool checks window/home/session binding, exact
versions, all required cases and readable evidence, then durably stores the receipt
in the protected window record. It never invents human approval from event delivery.
Missing, failed, stale or incomplete receipts block `finish`; it rechecks live
images/source/dependencies and surfaces as well. A receipt records the smoke
verdict and its evidence, not a general hook-trust bypass.

## State, failures and recovery

The command loads its own protected data on every invocation. It requires no
caller variables, no `source`, and no interactive `set -e`. Use a small JSON record
under the existing private cutover root for paths, immutable pins, recorded timer
states, verified checkpoints and existing artifact locations. Do not source or
translate `operator-env.sh`; keep that old file only as retained recovery evidence.

Explained retained state includes `section1-abort.l0b7qF/`, `operator-env.sh`,
`prep/`, `task7/`, `rehearsal/`, `familiar-rehearsal/`,
`familiar-rehearsal-v2/`, preparation manifests, the image directory and retained
original backups. Inventory and preserve them; they are not an active new window.
An old top-level `timers.json`, `.preparation` backup name, familiar step-2/merge
marker or live artifact without the matching active record is a blocker needing
reconciliation, not permission to overwrite it. A known active record is usable
only after its files and actual host state match its recorded checkpoint.

Reuse the existing snapshot/artifact formats and byte-gated restoration helpers.
One active window record covers all four targets and both hosts. Its referenced
ordered `touched.tsv` is durably appended before every target's first possible
mutation, including guard-only changes; agents do not make later unregistered
hook edits. Original copies, expected after-images and artifact paths remain
available even when relay apply never ran. After interruption, inspect
actual Git state, artifact presence and target bytes to determine the next safe
action. A recorded step alone never proves that its mutation completed. Use the
existing directory-fsync/atomic-write pattern where needed, rather than creating
a second general transaction framework.

Expose `check`, `run`, `status`, `restart-surfaces`, `record-smoke`, `finish`, and
`recover`. `check`/`status` are read-only and name blockers. Ordinary pre-merge
failures/signals automatically abort the timer/snapshot window; a completed abort
permits a fresh `run`, not continuation of that old window. After SIGKILL or an
incomplete abort, reconcile first and complete the section 1 abort via `recover`
before a fresh run. There is no pre-merge forward-resume path. Any failed or
interrupted familiar mutation/apply before the verified migration checkpoint
requires `recover`, not forward retry. If only the checkpoint write was interrupted,
reconcile actual artifacts, all four images on both hosts, source/dependencies and
evidence before classifying the migration as verified. Never infer it from a step
number or successful local apply.

After that verified checkpoint, surface-only failure/interruption is “migrated,
surfaces pending”. `status` identifies missing/blocked surfaces and prints the
complete `restart-surfaces` command plus safe resume commands. Opening a harness
through the prescribed trust/resume path is allowed in this state; the warning
against opening mixed native/migrated hooks does not apply. `restart-surfaces`
rechecks the verified migration and desktop inventory, obtains fresh host-use
consent, and retries only the recorded surface operations. It may run from a
controller with permission; it never applies hooks/source or restores timers.
`recover` remains available if the operator chooses full rollback. Drift in
settings/source/dependencies or ambiguous mutation completion is not a surface-only
failure and retains the recovery/inspection gate.

`run` reports an already verified migration without repeating writes, directing
pending surfaces to their explicit retry. `finish` verifies completed surfaces
and the recorded smoke prerequisites, restores original timers, runs/checks scheduled reconciliation and records closure;
it never edits hooks/source and may run from a verified migrated controller.
`recover` is an
explicit ordinary-shell action with the required harnesses closed, preserves
evidence, and uses the reviewed section 1 abort or full rollback as appropriate.

Every failed operation prints its named step, host, exit status, private log path,
observed completed state, and one recovery/status command. It must not print
private plans, settings, credentials, full environments or arbitrary command text.
No failure sends the operator into another shell or leaves a sourced partial
environment. Failures stop the script and return nonzero to the existing Zsh.
For failed/interrupted migration before verification, explicitly print “Do not
open Claude or Codex”, say that `run` is blocked, and print the complete `recover`
command. For verified migration with surface-only failure, print “migrated, surfaces
pending”, paused timers, the surface retry and safe resume commands; do not print
the mixed-migration warning. `status` distinguishes fresh `run` after complete
abort, incomplete abort/full `recover`, surface retry, trust/smoke handoff and
stopped pending inspection; no generic “try again” advice.

Handle INT, TERM and HUP as a failed current step. Record interruption state,
cancel and reap owned subprocess groups, then perform the same automatic section 1
abort if familiar mutation has not begun. A second interruption or unavailable
host may interrupt cleanup; preserve the record and report incomplete recovery.
After familiar mutation use the explicit full-recovery path until migration is
verified; an interruption confined to surfaces after that checkpoint stays pending
for the consented surface retry. SIGKILL cannot run
cleanup, so the next command reconciles durable records with actual state first.
Remote helpers own bounded subprocesses and record their PIDs; a lost SSH connection
does not prove a remote operation stopped. Block retry/recovery mutations until a
new status query reconciles remote process completion. Never claim remote cleanup
when the host is unreachable or leave an intentional detached monitor.

The script attempts the existing section 1 timer/snapshot abort when failure occurs
before familiar mutation. Failures during familiar mutation or apply before the
verified checkpoint leave evidence intact and require explicit full recovery,
rather than guessing whether an external operation partially succeeded. Surface-only
failures after verification follow the pending/retry path above. Full recovery
preserves the complete runbook order:

1. Require every Claude/Codex session closed on both hosts, stop both Titan Codex
   daemons with the supported commands, and pass strict no-live checks.
2. Re-quiesce both hosts using their original timer records, even if `finish`
   already restarted one or both timers; wait for both services before restoring
   any settings/source/dependencies. Never replace the original records.
3. Restore every registered touched target in reverse order, including guard-only
   interruptions; verify originals on both hosts. Unknown bytes stop recovery.
4. Reconcile/revert familiar's actual Git state, including a merge completed before
   its record was written; wait for verified source synchronization, restore each
   host's retained dependencies offline, and verify native source/dependencies.
5. Re-probe familiar surfaces and desktop IPC and request new permission for this
   recovery's restarts. Previously explained absent surfaces remain absent. Restart
   recorded surfaces and verify them. Earlier run consent does not cover recovery.
6. Restore each host's original timer state and verify service success before
   reporting native recovery complete or allowing fresh native sessions.

If a recovery prerequisite, desktop approval, restoration or verification fails,
stop and identify the remaining recorded state and next `recover`/inspection
action. Never claim a complete abort or tell the user to reopen a harness early.

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
- Scope stays Claude's two homes on Titan and Europa, and Codex's two homes on
  Titan only. Shared Codex files may be checked for synchronization on Europa;
  do not install/start Codex there or treat it as an affected Codex home.
- One writer per harness; native familiar retirement and relay addition stay in
  the same install. No registry import, merge or compatibility layer.
- Every live change is first tested on copies. Guard-only interruptions retain
  before/after images; restoration refuses unknown bytes.
- Preserve live model picks and trust state. Codex performs its own interactive
  trust review for each home; no trust hash is synthesized or edited by the script.
- Keep the existing never-apply-from-inside-a-harness rule. The ordinary-shell
  bootstrap applies all four hook targets with every Claude/Codex session closed
  on both hosts. Agents perform later verification/finalization, never hook/source
  changes. Full recovery also requires both harnesses closed.
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
  exit code. Preserve the actual process status. Status-zero exits stay quiet;
  intentional nonzero `exit` and Ctrl-D carrying a previous failing status also
  print the factual notice. It does not claim every such exit was caused by
  `errexit`. Do not print commands/variables or add an overlapping ERR trap.
- Keep `HISTCONTROL=ignoreboth:erasedups` and the existing prefix Up/Down bindings.
  Leading-space commands therefore remain intentionally absent from Bash history.
  Unlike Zsh's trim-and-retain hook, they cannot be recalled by Up or Ctrl-R.
  Removing `ignorespace` would retain them for plain Up/Ctrl-R but still would not
  make an unindented prefix match their leading blanks. The controller recommends
  preserving this privacy behavior now that the operator workflow needs no Bash
  paste, rather than adding whitespace-normalization machinery or changing what
  is recorded. Such a retention change needs a separate explicit choice.
- Replace the faulty cross-shell import sequence with append then clear/reload
  using Bash's history builtins, proven with two PTYs. Only clear after append
  succeeds: a write failure must preserve in-memory history and report the error.
  Reload failure must also be visible; the successfully appended disk history
  remains recoverable. The history file is retained, not rewritten or deduplicated.
  Previously stored legitimate duplicates may be visible after reload, and
  rereading a large file has a cost; no history database, new dependency, or
  whitespace-normalization framework is introduced.
  Retained `erasedups` can remove entries while accepting a command in memory, but
  reload restores the file's stored duplicates; no persistent deduplication is
  promised and the file is not rewritten to simulate it.
- Explain prefix Up versus substring Ctrl-R briefly. Do not claim the actual
  incident's missing command was definitely caused by indentation or another shell.

The diagnostic belongs behind the existing interactive-only guard. Test both
noninteractive Bash and Claude's shell-snapshot creation: the latter sources
interactive bashrc even though the later tool command is noninteractive. A
disposable Claude home must create/load its real snapshot and execute a harmless
tool command with the intended exit/status/stderr behavior; an ordinary
noninteractive source test does not establish snapshot compatibility. The
snapshot test needs a real Claude model/tool run with credentials. The dotfiles
plan must define authorized credential copying into the private disposable home,
restrict file permissions, keep secrets out of commands/logs, and remove credential
copies and the disposable home on success, failure and signals. Verify cleanup
without printing credentials; use no live home as the test target. Existing
literal configuration assertions must be adjusted, with real PTY/snapshot behavior
supplying the meaningful tests.
Dotfiles work uses its own worktree, preserves unrelated edits, and activates only
after reviewed changes and the required checks are concrete.

## General guidance in lore

The proposed instruction amendment belongs to lore-4c1787, through lore's
shell/process fragments and assembler. Declare the user's interactive shell as
Zsh explicitly in `instructions/fragments/shell.md`, the canonical user-instruction
source for this preference; later explicit user overrides still take precedence.
Dotfiles configures that shell; a harness's tool interpreter or inherited `SHELL`
does not replace the declaration.

- Operator commands always target the user's declared interactive shell: Zsh here.
  The shell used by an agent's tool does not select the operator's shell.
- Never ask the operator to enable interactive errexit and maintain a sourced
  environment across a long runbook. Executable tools own failure handling and
  load their state themselves.
- Prefer one checked command per unavoidable manual phase. Agents perform
  mechanical checks where harness/host-use constraints permit; document handoffs
  without weakening the project's apply/closure requirements.
- A failure leaves a clear observed status and a short resume/recovery command.
  Persistent host changes are restored or explicitly handed over, never hidden.

The feedback entries `lore-881f7a` and `lore-8ce941` remain untriaged. The separate
lore-4c1787 task implements the user's original request for durable guidance,
recorded in hq-c6c847's body. Round 2 was an external reviewer's review relayed by
the user; it asked that the owning task be named. This does not promote, close or
triage those reports. Lore owns its implementation/review.
Do not edit generated instructions by hand or alter the vendored skill submodule.
Publishing live instruction or home-config changes remains separately approved
after a concrete reviewed result.

## Independent delivery gates

The next cutover window depends on hq-c6c847's implemented, reviewed and rehearsed
bootstrap plus its actual live prerequisites. It does not depend on dots-55f537 or
lore-4c1787: the bootstrap already avoids interactive Bash and does not require new
global instructions. Those two user-requested improvements have their own worktrees,
checks, reviews and activation approvals. Parent task notes and the replacement
plan must reflect these independent gates; do not hold the rollout for shell polish.

## Verification and completion

Before any new live window, exercise the bootstrap on disposable copies and test
its orchestration with explicit scratch roots/fake host commands. Cover both-host
success; each host's failure; active target rejection; source-sync refusal;
interruptions before/after timer records, backup moves, familiar merge/record, and
each of the four targets' guard/plan/apply operations; unknown target drift; and
full offline recovery. Include INT/TERM/HUP during timer and synchronization waits,
remote disconnection with an operation still running, restart refusal before any
mutation, explained-absence and bad-socket cases, helper mismatch, refusal to
reopen a harness after a failed apply, a recorded surface PID exiting before
restart, changed context/unrecorded surfaces, partial restart and consented retry,
verified-migration surface failure without mandatory rollback, incomplete smoke
receipts, and a `finish` failure after restoring one or both timers. Assert
actual final files, Git parents, retained artifacts and timer states, not just
command spelling. Existing pin, restore and wiring tests remain in place.

Provide the separate `tools/relay-cutover-rehearse` entry for the smallest
end-to-end pilot. It creates protected owned throwaway roots on both hosts and
uses the runner's real SSH transport/remote helper with a distinct `pilot` request
mode and validated scratch-root identifiers. The remote helper dispatches an
explicit mode-specific schema: pilot mutations must resolve within those owned
roots (including symlink resolution); live mode derives its fixed roots locally
and rejects supplied root/helper overrides. No caller environment selects pilot
mode for live `run`/`recover`.

One pilot attempt checks actual batch Git access, bus queries and desktop IPC;
with invocation-specific consent, spawn the harmless no-window command `true`
through the exact same niri IPC spawn path as the surface launcher on each host.
Require the IPC acknowledgement and record its verdict; fixtures separately test
replacement-process liveness because `true` exits immediately. Preserve any
explicit explained-absence exemption rather than inventing a desktop on that host.
Merge/install familiar
in throwaway clones using the actual per-host npm and credentials; dry/apply/verify
all four copied settings targets on Titan under one touched record, exercise the
copied Claude targets on Europa and verify remote shared-image expectations; then
recover the copied targets and both clones/dependencies offline through the
verdict. Keep Codex execution on Titan. Do not stop real timers, restart actual
surfaces or edit live targets in the pilot. Real unit queries plus fixture timer
mutations cover those branches separately; the no-window spawn proves the actual
IPC launch route, not a live surface restart or persistent-process health check.
Preserve private logs, source/target/dependency equality and exact pin evidence. If the runner cannot
execute that narrow pilot over its real transport, it is not ready for the window.
Live `run`/`recover` must not accept arbitrary host roots/helpers from environment
overrides. Test rejection of pilot/live mode confusion and scratch-path escape on
both hosts.

Confirm failure returns to the original Zsh prompt and requires no exported caller
state. A missing current relay row and bypassed resume command are explicit failing
acceptance cases. Private output and copied credential cleanup retain existing
protections. Each project's declared focused/fast/full route and hooks still apply.

Bash PTYs cover normal recall, intentional leading-space omission, prefix/substring distinction,
two-shell import without accidental self-duplication, append/reload failures with
history preservation, stored duplicates, preserved nonzero exits with a factual
notice (including explicit nonzero exit and Ctrl-D after failure), quiet status-zero
exit, unchanged noninteractive sourcing and Claude's actual snapshot path.

The revised runbook and original execution plan must agree on the new phase gates
before use. Preserve the earlier review/rehearsal evidence and interruption fixes.
Design/plan approval authorizes implementation only; the new live bootstrap is
not run from this Codex session. The operator invokes the reviewed command after
closing both harnesses. Desktop consent comes before mutation in that run; trust
reviews occur after successful bootstrap in each Codex home.

## Calls made for review

All-four-target bootstrap, standard-library Python orchestration callable from
Zsh, explicit full recovery for unverified migration and a consented surface-only
retry after verified migration, a factual nonzero Bash EXIT
notice, preserving `ignorespace`, and guarded builtin clear/reload are controller
recommendations. They replace Codex-first application and the proposed history
privacy change. The cost is a few more minutes offline; agents assist verification
instead of applying another harness, and indented Bash commands remain omitted.
A generic workflow framework, automatic trust acceptance, shell replacement and
a third harness remain out of scope.

References: the existing `docs/plans/2026-10-19-relay-cutover.md` and
`docs/runbooks/relay-cutover.md`; familiar's command table at the pinned feature
revision; dotfiles' `bashrc`, `bash_profile` and `shell/history`;
[Bash set options](https://www.gnu.org/software/bash/manual/html_node/The-Set-Builtin.html),
[history search commands](https://www.gnu.org/software/bash/manual/html_node/Commands-For-History.html),
and [history facilities](https://www.gnu.org/software/bash/manual/html_node/Bash-History-Facilities.html).
