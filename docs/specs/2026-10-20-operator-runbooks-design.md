# Operator runbooks that preserve the operator's shell

Status: approved for planning by Keith after spec round 6, 2026-10-20.
The round-6 consent clarification is carried into the plan. Preparation/toolchain/
pilot/update-hold refinements were accepted in plan round 5 and approved by Keith;
the accepted Minor probe-order clarification is included. Execution awaits a fresh session.
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
   desktop checks below. Complete held Claude version/doctor probes for every
   host/home and wait for all probe processes to exit before step 2's final no-live
   check. Obtain this run's desktop restart consent before the
   first mutation. A refusal is a preflight stop with no timer/source change.
2. Refuse any remaining Claude/Codex session. Stop only the known personal/work
   Codex app-server daemons with their supported CLI, then require strict no-live
   checks on both hosts. Never broadly kill processes or exempt the caller PID.
3. Record/quiesce both hosts' timers, wait for their services, preserve preparation
   snapshots and refresh/verify the live backups. Recover every recorded host if
   this stage fails, including a first-host success followed by second-host failure.
4. After quiescence/strict no-live, freeze exact synchronized current targets and
   dry-run all four Titan copies and both Claude Europa copies before the familiar
   merge. Use each host's installer/runtime/evidence. Require the planned after
   string's exact UTF-8 bytes to equal the dry-applied copy; parsed non-pick content
   must equal the reviewed after-image and picks/absence the frozen current input.
   Seal those installer-produced bytes/hashes as this window's exact expectations.
   Any of the six failures takes the pre-merge abort on every recorded host.
5. Merge the immutable familiar feature revision once on Titan; reconcile an
   interruption between merge and record; verify source sync before each host's
   dependency installation/pin proof. Before each target's first live mutation,
   durably register its original/artifact, including Claude guard removal. Recheck
   frozen inputs and the live installer's plan after against the sealed dry output,
   then apply each shared target only on Titan and verify exact synchronized bytes
   on affected hosts. Both harnesses stay closed. Mark migration verified only
   after all targets, source/dependencies and exact evidence pass.
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
executable, `CODEX_HOME` and session ID. Its argv is `env`, `DISABLE_UPDATES=1`,
the explicit
`CODEX_HOME=<resolved-personal-home>` assignment, the validated executable,
`--no-daemon`, `resume`, and the captured native session ID. The operator receives
real values with no placeholders or environment preparation. The work-home command
similarly supplies `DISABLE_UPDATES=1`, its own explicit `CODEX_HOME` and the
validated executable.
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

### Human decisions when an agent invokes a command

An operator running a command directly may answer its terminal prompt. An agent's
tool shell cannot collect that answer. Before agent-run `restart-surfaces`, the
agent asks in the session, naming the hosts, recorded surfaces, expected desktop
impact and duration. Only an explicit user reply authorizes that invocation. Pass
it as a protected per-invocation decision argument recording the actual ask/reply,
session, action and current surface inventory; persist it with the result. A retry
asks again. No plain approval flag, inferred answer, old consent or agent-generated
attestation authorizes host use. The argument records consent; it does not create it.

Likewise, before `record-smoke` accepts human trust/permission attestations, the
operator supplies the relevant verdicts directly in their terminal or answers the
agent's explicit session question about those cases. Bind that answer to this
window, home, smoke evidence and recording invocation. The plan specifies the
argument schema and refusal/replay tests. A missing/declined answer leaves the
operation pending. It never falls back to prompting in an agent tool shell.

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
Remote helpers own bounded subprocesses and record their PIDs. After a complete
request, SSH EOF/EPIPE is not cancellation: the operation finishes or reaches its
own deadline, durably records completion, then attempts its reply. Cancellation is
an explicit request (or an actual signal/deadline), never inferred from pipe loss.
Local signal handling requests remote cancel and reconciles its result. Block
retry/recovery mutations until a new status query reconciles remote completion. Never claim remote cleanup
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

## Preparation refinements from plan review

Claude's live pick keys are owned by `.githooks/harness-state-clean`, not by the
cutover. `prepare` and run step 1 reuse that module's `CLAUDE_JSON_KEYS` through the
existing `runpy` loading pattern. Compare every other JSON key/value with the
reviewed native before-image. For pick-only drift, preserve the exact current
input; never assemble expected bytes by inserting picks into the reviewed image.
After quiescence, the six pre-merge dry-applied copies supply exact expected bytes.
Accept only parsed equality of all non-pick content with the reviewed after-image
and picks/absence with the frozen input. This preserves installer order/serialization,
including picks before/between other keys. Retain original reviewed images/provenance
and freeze effective window hashes before familiar/settings mutation. Existing
hooks/statusLine verification is unchanged; never rewrite rollback artifacts or
bypass their unknown-byte refusal.

The handoff, including surfaces-pending, explicitly says not to change/save Claude
model or effort defaults in either home/on either host until finish reports complete.
If that happens anyway, pick changes can pass hook checks but unknown bytes still
block full recovery for inspection; no automatic pick-rewriting recovery branch.

For non-pick drift, `prepare` refuses with `input-review-required` and names the
original plan's Task 6 procedure: regenerate images, guard snapshots and installer
plans/artifacts on copies, obtain review, retain its actual task note/full report,
then stage a new protected input generation and expected-image manifest on both
hosts. Preserve previous generations and active-window rollback originals. The
tool validates the designated manifest's paths, member hashes, pins and baseline;
it does not interpret review-note bindings or expose structural-review flags.
Never adopt current bytes by merely recomputing hashes. Rerun preparation and
all six closed-harness dry runs against the reviewed inputs.

Preparation records system `/usr/bin/npm` 12.2.1, `/usr/bin/node`, system Git and
`/usr/bin/python3` paths/versions/digests per host. Install with `/usr/bin` first in
an explicit PATH so npm's env-node shebang cannot choose nvm. Include the clean
filter and per-host toolchain identities in the manifest; reject drift.
Retain the startup authentication/user-bus/cache environment, with explicit PATH
and Python bytecode suppression (`-B` at entry, PYTHONDONTWRITEBYTECODE for children).
Pilot application/config/state/dependency/temp writes remain scratch-contained.
The plan names the exceptions: validated prepared host-local cache prefixes,
existing authentication/SSH runtime bookkeeping and the consented no-window niri
spawn. Cache paths overlapping Dropbox/live checkouts/state are blockers. Report cache
exceptions rather than claim no writes anywhere outside scratch.

### Claude update hold and readiness

Use the supported process environment `DISABLE_UPDATES=1` to block automatic and
manual updates, without editing the four targets, `~/.claude.json` or shared
launchers. See the [official update controls](https://code.claude.com/docs/en/setup#disable-auto-updates)
and [environment reference](https://code.claude.com/docs/en/env-vars).
This scoped process hold runs only from bootstrap through finish. Ordinary Claude
use, including `cl`/`clw` and review sessions, remains allowed during preparation,
pilot and any parked wait. Individual agent diagnostics/probes use the flag
beforehand, without creating a continuing restriction on ordinary use.

As the last action before every request to close sessions, including after a wait,
the agent checks both hosts' installed versions against reviewed evidence and
prepared identities with held commands. If unchanged, no preparation repeats. If
moved, repeat only implementation-plan Task 9 Steps 5–7 (version/doctor checks,
original Task 3's isolated held ops probe with required cases and independent
review, reviewed proof delivery and both-host installer acceptance, refreshed
inputs/preparation), then check again before asking for closure. Rerun the pilot
only if its helper/toolchain bytes changed, with their normal checks/review/delivery
first. Version refresh alone never repeats runner-doc rewriting, implementation
review/delivery or the pilot; the new evidence still needs its own review/delivery.
New capabilities changing images still require original Task 6 image review.
2.1.304 is the current baseline, not a permanent hardcoded requirement. Host
alignment remains an operator action, never an automatic update/downgrade.

The operator closes all Claude/Codex sessions for bootstrap. Before timers pause,
`run` first completes exact held version/doctor probes for each host/home, waits
for every probe to exit, then performs the final strict no-live check without
caller-child exemptions. A mismatch or unproven doctor update-hold diagnostic refuses
without mutation. Record selected versions, binary digests and dated diagnostics.
Only from bootstrap through finish must known live Claude processes match that
identity/hold key; preparation may observe ordinary unheld sessions as later
no-live blockers. Inspect only the hold key for owned PIDs, never full environments.
A recorded manifest flag is not proof of a continuous hold.

From bootstrap until finish, every handoff explicitly says to avoid `cl` and `clw`,
unheld Claude/IDE clients, update/install commands and external installers; use the
printed held personal/work/smoke commands. Codex's printed launches carry the flag
for tool children; the remote helper sets it for its children. The parent shell
policy remains unchanged, ordinary launches after finish use their prior policy,
and already-held sessions remain held until exit. Never unset user/admin policy.

Unexpected version drift after bootstrap is a hold breach: stop new smokes, name
paused timers and require ordinary-shell full recovery before a fresh Steps 5–7
pass and final held check. Keep this conservative path rather than introducing
evidence replacement in an active window.

> Note (2026-10-21, ruling R47): a hold breach follows the verified migration, so the
> recovery reverts a committed merge, and a recovered committed merge ends the window:
> familiar stays at the recovery revert and the tool merges only from PRE. No fresh
> Steps 5–7 pass reopens that window; a later attempt needs newly reviewed pins and
> inputs, as the plan says.
Stale Claude evidence blocks forward progress, never restoration: recovery uses
strict no-live, pinned relay and byte/Git/dependency proofs without launching the
changed Claude or requiring its version to equal obsolete evidence. Restore native
state and original timers before re-probing; no automatic in-window proof adoption.

## Preserved cutover requirements

- Relay remains v0.1.1 at `4ceec5d2ad22b136b37ee360e7a4ed00949f28d9`, with
  `--node /usr/bin/node`. Familiar PRE remains
  `00f4899ae523d613d21f44bfc2c456aac67f8e5f`; its approved feature tip remains
  `a16f4daa59b04e32f1010764d6f94401ca4eed8b`.
- Exact version evidence is required with the scoped hold from bootstrap through
  finish. Changed versions repeat the reviewed probe loop before a new window;
  stale Claude evidence must not prevent rollback. No automatic harness updates,
  pin changes or relaxed evidence.
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
mutation, explained-absence and bad-socket cases, helper mismatch, interleaved pick layout,
installer/dry-copy byte disagreement and all-six verdict ordering before merge,
refusal to reopen a harness after a failed apply, a recorded surface PID exiting before
restart, changed context/unrecorded surfaces, partial restart and consented retry,
verified-migration surface failure without mandatory rollback, incomplete smoke
receipts, and a `finish` failure after restoring one or both timers. Assert
actual final files, Git parents, retained artifacts and timer states, not just
command spelling. Existing pin, restore and wiring tests remain in place.

Provide the separate `tools/relay-cutover-rehearse` entry for the smallest
end-to-end pilot. It creates protected owned throwaway roots on both hosts and
uses the runner's real SSH transport/remote helper with a distinct `pilot` request
mode and validated scratch-root identifiers. The remote helper dispatches an
explicit mode-specific schema: pilot application mutations must resolve within
those owned roots (including symlink resolution), with only the prepared cache/
runtime exceptions described above; live mode derives its fixed roots locally
and rejects supplied root/helper overrides. No caller environment selects pilot
mode for live `run`/`recover`.

One pilot attempt checks actual batch Git access, bus queries and desktop IPC;
with invocation-specific consent, spawn the harmless no-window command `true`
through the exact same niri IPC spawn path as the surface launcher on each host.
Require the IPC acknowledgement and record its verdict; fixtures separately test
replacement-process liveness because `true` exits immediately. Preserve any
explicit explained-absence exemption rather than inventing a desktop on that host.
Clone familiar at PRE, freeze current copied targets with interleaved picks and
pass the same six dry runs before the scratch merge/install. Use prepared system
npm 12.2.1/node and host credentials; then apply/verify Titan's four separate target
copies under one touched record and verify remote shared-image expectations; then
recover the copied targets and both clones/dependencies offline through the
verdict. Keep Codex execution on Titan. Do not stop real timers, restart actual
surfaces or edit live targets in the pilot. Real unit queries plus fixture timer
mutations cover those branches separately; the no-window spawn proves the actual
IPC launch route, not a live surface restart or persistent-process health check.
Preserve private logs, source/target/dependency equality and exact pin evidence. If the runner cannot
execute that narrow pilot over its real transport, it is not ready for the window.
Live `run`/`recover` must not accept arbitrary host roots/helpers from environment
overrides. Test rejection of pilot/live mode confusion and scratch-path escape on
both hosts. Also exercise one real SSH disconnect during a separate scratch install:
close only the local client, reconcile the remote operation through completion/
deadline and its durable result, and never infer cancellation from the lost pipes.


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

## Amendment 2026-10-21: familiar task-record drift

Approved direction: Keith, 2026-10-21, after the real-host `prepare` refused because familiar
had moved two task-record commits past PRE (adding only `tasks/fam-ff5351.md`). Familiar's
own task tracker commits into the same repository, from any checkout and during smokes, so
no exact familiar commit can be held through a window. Revised after design review rounds 7
to 11. Familiar's runtime does not read `tasks/`.

**Tasks-only descendant.** Y is a tasks-only descendant of X when X is an ancestor of Y and
every commit in `X..Y` has exactly one parent and, against that parent, changes only raw
entries whose path begins with the bytes `tasks/` and whose every non-zero mode is 100644 or
100755. Y equal to X qualifies. It is computed with plumbing only (`rev-list`, `rev-list
--min-parents=2`, `diff-tree -r --no-renames --raw -z`) under `GIT_NO_REPLACE_OBJECTS=1`, and
refused on a shallow repository or one with `info/grafts`. A rename or copy is seen as its
delete and add and fails only when one side lies outside `tasks/`; symlinks, gitlinks,
`tasks` itself, `tasks.md`, `Tasks/…`, `tasksx/…` and root commits fail.

**Pins and fixed merge options.** PRE (`00f4899ae523d613d21f44bfc2c456aac67f8e5f`) and the
immutable tip (`a16f4daa59b04e32f1010764d6f94401ca4eed8b`) stay pinned, and T0 is pinned as
the tree of the reviewed clean merge of PRE and tip: `f492e3437577c4b79db379e4cc1fb6771f35b3bb`
(computed 2026-10-21 on Titan with git 2.56). Every `merge-tree` and `merge` call carries
`-c merge.renames=true -c diff.renames=true -c merge.directoryRenames=conflict`, and every
mutating familiar git call (`merge`, `read-tree`, `update-index`, `commit-tree`, `update-ref`)
also carries `-c core.hooksPath=/dev/null`; the merge
itself is `git -c branch.<current>.mergeOptions= merge -s ort --no-ff --no-edit --no-verify
--no-autostash`. A non-zero `merge-tree` exit is a refusal. Read-only `merge-tree` runs with a
temporary object directory and the real objects as an alternate, so readiness writes nothing
into the synchronized repository; the `diff-tree` that compares its output with T0 runs
under the same object environment. "Equal outside `tasks/`" means `diff-tree -r --no-renames
--raw -z` lists only paths beginning with `tasks/`.

- **Base.** B is a tasks-only descendant of PRE with a clean tree (no tracked change, no
  untracked path outside `tasks/` and the ignored `node_modules`). `merge-tree --write-tree B
  tip` must exit 0 and equal T0 outside `tasks/`; any conflict, the tip/base `tasks/` path
  overlap included, refuses at `prepare`, before any closure. A fresh window keeps this
  strict rule, so a recovered window's R is never a base (R47 holds).
- **Readiness.** `prepare` and `check` recompute T0 and compare it with the pin, apply the
  base rule to each host's own HEAD and report B with its proof. Europa's HEAD equal to, or an
  ancestor of, Titan's is ready; diverged or ahead is a `familiar-native` blocker naming the
  commit. B moving between `prepare` and `run` while eligible is not drift.
- **Run.** After the second strict no-live check, `run` derives B on Titan (base rule and
  merge check again) and saves it in the window. A new read-only host operation,
  `familiar-sync` (each poll runs one child; deadline `SYNC_SECONDS + CHILD_SECONDS + 60`), then waits for Europa HEAD =
  B; a timeout, divergence or Europa ahead is a clean pre-merge abort. Only then does either
  host's `snapshot-refresh` run (its 900 s budget unchanged), checking HEAD = B without
  waiting. The pre-merge gate rechecks Titan HEAD = B; the mark records B; `familiar-merge`
  receives B, rechecks HEAD = B and the base rule on the host, merges with the fixed options
  and proves M: parents exactly `[B, tip]`, tree equal to `merge-tree --write-tree B tip`, and
  equal to T0 outside `tasks/`.
- **After the mark.** Every source proof accepts a tasks-only descendant of the expected
  commit with a clean tree in place of exact HEAD equality: Europa's install sync wait (of
  M), `familiar-verify` in `run`, `restart-surfaces` and `finish` (of M), and the dependency
  restore's sync wait (of R). Europa's proofs also require Europa HEAD equal to, or an
  ancestor of, the Titan HEAD the controller observed in the same step. Finish records the
  observed HEAD.
- **Finding M and R.** Without a record, the restore requires `merge-base --is-ancestor B HEAD`, then
  walks `rev-list --first-parent --parents B..HEAD`: exactly one entry has more than one parent; that is M, and its parents must be
  `[recorded B, tip]`. Above M, R is the entry whose `diff-tree` touches a path outside `tasks/`;
  more than one such entry is refused for inspection. When HEAD is in the `reverted` class, the
  walk's R is the restore's R; a recorded R that differs is recorded as abandoned and no
  restore runs. B is saved before the merge request, so a merge never exists without it. A window
  record with no recorded base is refused for inspection, never assumed to be PRE.
- **Recovery classes.** `at-base`: no MERGE_HEAD or REVERT_HEAD and HEAD a tasks-only
  descendant of the recorded B; it records the restoration point as the recorded B.
  `merge-in-progress`: HEAD = B and MERGE_HEAD = tip. `merged`: HEAD = P, a tasks-only
  descendant of M, M's parents exactly `[recorded B, tip]` and M equal to T0 outside `tasks/`
  (also required before reconciliation promotes a discovered merge). `reverted`: HEAD a
  tasks-only descendant of R, R with one parent P that is a tasks-only descendant of M and R's
  tree equal to B's outside `tasks/`; R's `tasks` entry is otherwise unconstrained, though R's changes against P inside `tasks/`
  meet the tasks-only mode rule (100644/100755), so a tracker commit
  of R's content through the live index can serve as R without loosening anything outside
  `tasks/`.
- **Restore without `git revert`.** The restore builds R by plumbing: R's tree is B's tree
  with its `tasks` entry replaced by P's (added when B has none, removed when P has none; two
  absent entries are equal), assembled from `ls-tree -z B` minus `tasks` plus `ls-tree -z P
  -- tasks` through `mktree -z`, and written with `commit-tree -p P`; R's OID is recorded
  durably on the host before any index or working-tree change. The live index is never
  evidence (Dropbox synchronizes it). "The working tree equals T" means: a temporary
  `GIT_INDEX_FILE` loaded with `read-tree T` gives `diff --quiet T` exit 0, and under that index
  `ls-files -z --others` lists nothing outside `tasks/` and `node_modules/`. For the restore's
  branch choice, its final proof and every after-the-mark clean-tree proof, equality is judged
  outside `tasks/`: tracked changes under `tasks/` (a tracker write deferred because the index
  held foreign staged changes) are carried, never evidence; P, R and R′ share HEAD's `tasks`
  entry, so the two-way `read-tree -m -u` keeps them. The restore refuses
  for inspection while `.git/index.lock` exists and never deletes the lock. With HEAD = P (R's
  recorded parent):
  - working tree equals P: rebuild the index (`read-tree P`, then `update-index -q
    --refresh`), run `read-tree -m -u P R`, then `update-ref HEAD R P` (compare-and-swap);
  - working tree equals R: rebuild the index from R the same way, then `update-ref HEAD R P`;
  - anything else is refused for inspection.
  When HEAD is no longer R's parent and R is not an ancestor of HEAD (a tolerated Titan tasks
  commit landed after a crash before `update-ref`), R is recorded as abandoned. When HEAD is
  in the `merged` class, a fresh R′ is built on HEAD (B's tree with HEAD's `tasks` entry): a
  working tree equal to HEAD proceeds as in the HEAD = P case; a working tree equal to R′
  rebuilds the index from R′ and runs `update-ref HEAD R′ HEAD`; anything else is refused for
  inspection. On every path the final proof is HEAD equal to R (or R′) or a tasks-only
  descendant of it, with the working tree equal to HEAD. R keeps familiar's task
  records as they stand, and cannot conflict.
- **Ending the cutover.** `_ended` ends the cutover only when recovery's class was `merged`
  or `reverted`; an `at-base` or `merge-in-progress` recovery does not end it.
- **Freeze.** Committing to familiar on Europa during the window is forbidden (concurrent ref
  writes are a Dropbox conflict) and is detected after the mark. On Titan, a familiar commit
  between B's derivation and the merge aborts the run before the merge; after the merge it is
  tolerated. Handoffs and the runbook say both, beside the Claude pick freeze.
- **Pilot.** Each host's scratch clone is cloned at that host's own eligible HEAD, recorded
  per clone. A later live B that differs from the pilot's does not invalidate the pilot; only
  helper or toolchain bytes do. The pilot reruns after this change because helper bytes change.
