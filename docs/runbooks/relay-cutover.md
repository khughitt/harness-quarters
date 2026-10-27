# Relay operator cutover

**Completed 2026-10-22.** Window `20261022T014303Z-a1e7bd47` ran and `finish` completed: relay is live in all four targets on titan and europa, six smoke receipts validated, timers restored, hold released; merged to main (`d04b6eb`). Mid-window: Codex start-idle is observed after a fixed first prompt (`9b5ae86`), held Claude launches went through `~/.local/bin/claude`, and europa's surfaces needed an unlocked screen; follow-ups in hq-7e81ed. The cutover worktree is removed: the tool is on main as `tools/relay-cutover-bootstrap`, and the `.worktrees/relay-cutover` paths below are historical.

Rewritten 2026-10-21 for the closed-harness bootstrap: plan
`docs/plans/2026-10-20-relay-cutover-bootstrap.md`, spec
`docs/specs/2026-10-20-operator-runbooks-design.md`. Before that window relay was not live: the manual window
of 2026-10-19 stopped after Titan's §1 on 2026-10-20 and was aborted and restored. Its
sourced-Bash procedure is superseded; the parts still worth reading are in the
[Reference](#reference-not-for-pasting) at the end, which is not for pasting.

The cutover replaces familiar's native hook entries and the native ops guard with relay
v0.1.1 in four shared settings targets: Claude's personal and work homes on Titan and Europa,
and Codex's personal and work homes on Titan only. One tool, `tools/relay-cutover-bootstrap`,
carries every phase, with its separate rehearsal entry `tools/relay-cutover-rehearse`. It
loads its own protected records under `~/.local/state/hq/relay-cutover/`, so no command here
needs `source`, a saved environment, an interactive `set -e` or a Bash shell. Each command
below is one Zsh line. A stopped
command returns 1 to the same Zsh prompt and prints its step, host, status, private log path,
observed state and one complete next command. It never prints settings, plans, environments,
credentials or child output.

The commands below use the reviewed worktree's copy, by explicit path:

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap status
```

The tool reaches its hosts through hq main's fixed entry, `~/d/hq/tools/relay-cutover-host`:
directly on Titan, and through `ssh -4 -o BatchMode=yes europa` on Europa. Nothing works
until the reviewed tool has been delivered to hq main and has reached Europa byte for byte
(bootstrap plan Task 9 Step 4). A checkout or host whose helper bytes differ from the prepared
manifest blocks `prepare`, `check` and `run`. Each report prints its next command with the
resolved absolute path of the checkout it ran from. Nothing here repoints a home, launcher,
service or config include into a worktree. Keep `.worktrees/relay-cutover/` until the
original plan's Task 9 is complete. The independent Bash (dots-55f537) and instruction
(lore-4c1787) changes do not gate this window.

## Who does what

| Phase | Who runs it | Claude and Codex sessions | Commands | Result |
| --- | --- | --- | --- | --- |
| Prepare | agent | ordinary use continues, including `cl` and `clw` | `prepare`, `check`, `status`, `relay-cutover-rehearse` | prepared record; pilot verdict |
| Final pre-closure step | agent | ordinary use continues | held version checks, then `check` | unchanged versions: ask for closure |
| Bootstrap | operator, in an ordinary Zsh on Titan | every session closed on both hosts, the controller's included | `run` | migration verified; familiar's surfaces restarted |
| Resume | operator | only the printed held commands | the controller's resume; the Codex homes' hook reviews | the controller proves its own row |
| Validate | agent with the operator | only the printed held commands | `record-smoke`, `restart-surfaces` | six smoke receipts |
| Finish | agent | only the printed held commands | `finish` | original timers restored; reconciliation verified; hold released |
| Recover | operator, by choice or when a report says so | every session closed on both hosts | `recover` | native settings, familiar, surfaces and timers |

## Evidence: what is proven and what is not

- **Fixture-tested.** Implementation Tasks 1–8 test the orchestration against fake hosts and
  owned scratch homes through the real request protocol
  (`tools/test_relay_cutover_bootstrap.py`, `tools/test_relay_cutover_transport.py`). The
  tests cover:
  - decisions and their refusals: missing, declined, stale, replayed or mismatched;
  - lost SSH replies and explicit cancellation;
  - interruption at each durability gap: timer records, snapshot moves, the merge and its
    record, and each target's guard, plan and apply;
  - pick drift, non-pick drift, and all six dry-run verdicts before the merge;
  - the pre-merge abort on every recorded host;
  - full offline recovery, including after a hold breach and after a partial finish;
  - surface restarts with exited, reused and unrecorded PIDs, a partial restart and a
    consented retry;
  - smoke receipt binding, and finish's gates;
  - pilot/live mode confusion and scratch-root escape;
  - a terminal held by an agent, a blocked or declined recovery desktop, owner-lost operations
    of any window, stops classified by cause, and a bypassed resume;
  - familiar task-record drift past PRE (amendment 2026-10-21): the tasks-only predicate's
    plumbing rules, a base B derived and waited for, Titan commits before and after the merge,
    a Europa commit after the mark, and the plumbing restore's crash points, live-index cases
    and recovery classes, on real miniature Git histories.

  Fixtures are not the real hosts. That suite runs in the worktree, which carries the hook
  after-images. Delivery (bootstrap plan Task 9 Step 4) runs `just test` again on the
  delivered main tree, which lacks them; the worktree run does not prove that combination.
- **Historical (2026-10-19).** The original Task 7 rehearsed the manual procedure on both
  hosts: settings copies at three stop points, and familiar's throwaway merge, install and
  offline rollback ([Reference](#disposable-rehearsal-evidence-2026-10-19)). That shows
  feasibility. It does not prove this tool or its transport.
- **Pilot-proven (2026-10-21).** The real-host pilot passed (hq-c6c847,
  bootstrap plan Task 9 Step 8). `relay-cutover-rehearse` exercised:
  - the runner's real SSH transport and fixed remote entry;
  - batch Git access to familiar-theme's SSH pin;
  - user-bus unit queries;
  - read-only niri IPC, and the consented no-window `true` spawn;
  - the real relay v0.1.1 installer's plans on frozen copies with interleaved picks;
  - a real `npm ci` in scratch with the prepared caches;
  - one real SSH disconnect during a scratch install, reconciled to its recorded result;
  - offline restoration of the copies, clones and dependencies, then cleanup.

  The pilot proved the scratch workflow; live-window evidence is recorded below.
- **Pre-window readiness** (bootstrap plan Task 9 Steps 5–7, then the
  [final pre-closure step](#2-final-pre-closure-step-agent) before every closure request).
  These are dated observations, not a continuous hold: both hosts' versions and digests from
  held commands, each home's `claude doctor` hold diagnostic, the transport checks, and
  `prepare`. On 2026-10-20 the implementation controller made some read-only observations:
  - Titan's personal-home `DISABLE_UPDATES=1 claude doctor` printed
    `Auto-updates: disabled (set by env: DISABLE_UPDATES)` on 2.1.304;
  - both hosts run niri 26.04, with `niri msg action spawn-sh`;
  - logind has `KillUserProcesses=false` on both hosts.

  Steps 5–7 repeat such checks for every host and home.
- **Live window completed (2026-10-22).** Window `20261022T014303Z-a1e7bd47`
  completed with six validated smoke receipts: Titan Claude personal and Codex personal
  full smokes, Titan Claude work and Codex work, and Europa Claude personal and work.
  The hq-f27918 finish note records:
  - the four shared hook targets applied and verified across Titan and Europa (Claude
    personal/work on both hosts, Codex personal/work on Titan), with hooks, statusLine,
    installer and evidence verified on both hosts;
  - familiar merged with its pinned relay, surfaces running after restart, original
    timers restored and familiar-reap.service reporting success on both hosts;
  - dead rows removed, the controller row kept, and the hold released.

  Mid-window corrections and limits remain in the completed header and hq-7e81ed:
  Europa's surfaces needed an unlocked screen, Codex start-idle needed a fixed first
  prompt, and held Claude launches used the launcher link. The completed window does
  not establish live recovery; offline recovery remains fixture and rehearsal evidence.

## Commands, consent and what each may change

| Command | Run by | Human decision | May change |
| --- | --- | --- | --- |
| `prepare --controller-session ID` | agent | none | the prepared record and private operation records; the held Claude probes' own home-state bookkeeping (ruling R43) |
| `check` | agent | none | private operation records; the held Claude probes' own home-state bookkeeping (R43) |
| `status` | anyone | none | nothing (local records only) |
| `reconcile-operations --host HOST` | agent | none | private operation records: only operations whose owner died are cancelled, each recorded `interrupted` |
| `relay-cutover-rehearse --controller-session ID --preview` | agent | none; prints the consent subject | allocates the pilot window and contacts no host |
| `relay-cutover-rehearse --controller-session ID` (with `--decision-file FILE` or a terminal answer) | agent | desktop: the no-window `true` spawn; without approval the spawn gate stays pending | owned scratch roots on both hosts, the prepared cache prefixes, existing authentication and SSH runtime bookkeeping, the held Claude probes' home-state bookkeeping |
| `run` | operator, from an ordinary terminal | desktop: the operator's `/dev/tty` answer only; no decision file | timers, familiar snapshots, familiar, dependencies, all four targets, familiar's surfaces |
| `restart-surfaces` (`--preview`, or `--decision-file FILE`) | agent or operator | desktop: the operator's terminal answer, or a session decision file after the controller's proof | familiar's recorded surfaces only |
| `record-smoke --observe HOST` (optionally `--cwd DIR`) | agent | none | private smoke evidence |
| `record-smoke --receipt FILE` (`--preview`, or `--decision-file FILE`) | agent or operator | smoke attestation: the operator's terminal answer or a session decision file | the window's receipt record |
| `finish` | agent | none | timers, a run of `familiar-reap.service` |
| `recover` | operator, from an ordinary terminal | desktop: the operator's `/dev/tty` answer for recovery's restarts; no decision file | everything back to native |

`prepare`, `check` and `status` never change targets, familiar source, dependencies, timers,
services, the desktop or window state. `prepare` writes `prepared.json`, and it and `check` add
the private operation and transport records under the cutover root (ruling R16). Their held
`claude --version` and `claude doctor` probes may also write Claude's own home-state
bookkeeping, a declared runtime effect (ruling R43).

### Human decisions

- **At a terminal.** An operator who runs a command directly answers its bounded prompt on
  `/dev/tty`: a preview of the subject, then `Type yes to approve` (for a smoke attestation,
  `Type yes to attest`). The tool takes `yes` or `y`, in any case, as approval; any other
  answer stops before any change, except in `recover`
  ([§9](#9-recovery-recover-operator)). `run` and `recover` accept nothing else (rulings R24
  and R35).
- **From an agent.** An agent never answers a terminal prompt, even when its tool shell has a
  terminal; it always passes `--decision-file`. The tool enforces this: an invocation that runs
  under a Claude or Codex process (found by walking its parent processes) takes no terminal
  answer, because that terminal, a pseudo-terminal included, is the agent's own.
  `restart-surfaces` and `record-smoke` then stop and name `--preview` and `--decision-file`;
  `run` and `recover` stop as operator-run from an ordinary terminal, and `run` opens no window.
  The sequence is:
  1. Preview the subject read-only: `restart-surfaces --preview`,
     `record-smoke --preview --receipt FILE`, or `relay-cutover-rehearse … --preview`.
  2. Ask the user in the session, naming the subject:
     - a surface restart: the hosts, the surfaces, the impact and the duration;
     - a smoke attestation: the receipt's host, home, session, cases and human verdicts;
     - the pilot: its hosts, the fixed `true` spawn, that no window opens, and at most
       five minutes.
  3. Wait for the explicit reply.
  4. Write the record below and pass it to the command.
- **The record.** It is one JSON object, schema 1. Take `window_id`, `attempt_id` and
  `subject_sha256` from the preview. `kind` is `desktop` for `restart-surfaces` and the pilot
  (action `restart-surfaces` or `pilot-spawn`), and `smoke-attestation` for `record-smoke`
  (action `record-smoke`). `answered_at` is ISO 8601 with a timezone.

  ```json
  {
    "schema": 1,
    "kind": "desktop",
    "action": "restart-surfaces",
    "window_id": "<window_id from the preview>",
    "attempt_id": "<attempt_id from the preview>",
    "subject_sha256": "<subject_sha256 from the preview>",
    "verdict": "approved",
    "source": {
      "type": "session",
      "session_id": "<the asking agent's native session ID>",
      "ask": "<the exact question asked in the session>",
      "reply": "<the human's exact reply>",
      "answered_at": "2026-10-21T14:03:00+00:00"
    }
  }
  ```

- **Where to keep it.** Write it as your own regular file, mode 0600, at most 64 KiB, in a
  private directory outside the cutover root (a `mktemp -d` directory, for example). An
  unexplained entry at the top level of `~/.local/state/hq/relay-cutover/` blocks every
  command.
- **Consumption.** A decision is consumed once, before its first authorized action, and kept
  in the window's `decisions/`. Each of these refuses, and the agent must ask again:
  - a reused attempt or reply;
  - another window;
  - a changed subject;
  - a reply answered before the window existed.

  A declined verdict authorizes nothing; that step stays pending. For a surface restart that
  means the surfaces stay pending, with no rollback.
- **What a record is.** It is an auditable record of an actual ask and reply, not proof of
  who typed it. Syntactically valid fabricated data is never authorization.

## 1. Preparation (agent)

Ordinary Claude and Codex use, `cl` and `clw` included, stays allowed during preparation and
any parked wait.

**Prerequisites.**
- The reviewed tool is delivered to hq main on both hosts.
- A reviewed input generation is staged on both hosts:
  - `inputs/designated.json` under the cutover root names `inputs/<generation>/manifest.json`;
  - the manifest's schema is documented in `tools/relay_cutover_bootstrap/inputs.py`;
  - it holds the pins, the helper digests (`.githooks/harness-state-clean` included), each
    host's toolchain identities, each host's explained desktop absence if it has one, and
    each target's reviewed before-image, after-image and installer artifact with provenance;
  - the toolchain identities are `/usr/bin/npm` 12.2.1, `/usr/bin/node`, system Git and
    `/usr/bin/python3`.
- The controller session ID is the native session ID, a lowercase UUID, of the Codex
  controller in Titan's personal home. `run` later prints that session's resume command.

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap prepare --controller-session '<controller-session-id>'
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap check
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap status
```

**What `prepare` reads.** It reads each host through the fixed entry and records:
- the manifest and its pins, the clean filter's Claude pick keys, and the helper digests;
- each host's toolchain, install PATH (`/usr/bin:/bin:` plus the validated remainder) and
  cache prefixes;
- Claude's identity and per-home versions from held `claude --version` and `claude doctor`
  probes, and Codex's on Titan;
- the desktop inventory: the trusted niri socket and each familiar surface's startup command
  and process;
- each target's resolved path, digest and pick values;
- familiar's base on each host, by the base rule below, and its native dependencies through
  `familiar-check --expect native`, read only. It prints each host's base (`familiar base
  <commit>: N tasks-only commit(s) past PRE …`).

**The familiar base rule.** familiar's own task tracker commits task records (`tasks/`) into
the synchronized checkout from either host, so the tool holds no exact familiar commit. A
host's HEAD is its base B when it is PRE or a *tasks-only descendant* of PRE: every commit
since PRE has one parent and changes only regular files (mode 100644 or 100755) whose path
starts with `tasks/` (a rename counts as its delete and add; `tasks`, `tasks.md`, `Tasks/…`,
`tasksx/…`, symlinks and gitlinks do not qualify; shallow or grafted history is refused). Its
tree must be clean: no tracked change, and no untracked path outside `tasks/` and the ignored
`node_modules`; a path Git ignores (familiar's `.gitignore`, `.git/info/exclude` or your
`core.excludesFile`) is not untracked. `git merge-tree --write-tree B tip` must merge cleanly
and equal T0, the pinned tree of the reviewed merge of PRE and the tip, outside `tasks/`. The
check recomputes T0 and writes nothing into the checkout. familiar's runtime never reads
`tasks/`. Europa's HEAD must equal Titan's or be an ancestor of it.

It refuses beside any open window, pilot included, and with `familiar-native` on a host whose
familiar fails the base rule or, on Europa, is ahead of or diverged from Titan's
([§2](#2-final-pre-closure-step-agent)). A base that moved by task records since `prepare`
is not drift: `check` and `run` read it again. Running Claude and Codex
sessions are listed as future `run` blockers; they never make preparation fail. `check`
repeats every read and names any drift since `prepare`. It prints `next: … run` only when
everything still matches.

**Picks and structural drift.** Claude's pick keys are the `CLAUDE_JSON_KEYS` of the
manifest-verified `.githooks/harness-state-clean`. Their values, or their absence, may differ
from the reviewed before-image; `prepare` records them as found. Any other difference,
hooks and statusLine included, refuses with `input-review-required`. Codex targets compare as
whole objects.

### When prepare refuses: input-review-required

The refusal names the original plan's Task 6 image review
(`docs/plans/2026-10-19-relay-cutover.md`, "Task 6: Prepare the reviewed settings images").
The agent:

1. Regenerates the before-images, after-images, guard snapshots and installer plans and
   artifacts on copies, never on live files:
   - `tools/relay-cutover retire-native-guard --target COPY --backup DIR` for the Claude
     copies;
   - then `relay/bin/relay install --harness HARNESS --subscribers
     ~/.config/relay/subscribers.json --target COPY --retire familiar --evidence
     ~/d/ops/docs/runbooks/relay-guard-evidence-HARNESS.json --node /usr/bin/node --apply
     --artifact ARTIFACT`;
   - a Codex copy keeps the basename `hooks.json`.
2. Reads every diff. The only changes may be the removed familiar and native-guard entries
   and the appended relay entries.
3. Obtains an independent review and records its standard review note and full report.
4. Stages a new protected input generation and its manifest on both hosts. Previous
   generations and any window's rollback originals stay untouched.
5. Reruns `prepare`, then `check`. All six closed-harness dry runs happen again in `run`.

The tool checks the designated manifest's paths, member digests, pins and provenance. It
never creates approval, reads task notes or reports, or adopts current bytes by recomputing a
digest.

### The pilot (rehearsal)

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-rehearse --controller-session '<controller-session-id>' --preview
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-rehearse --controller-session '<controller-session-id>' --decision-file '<decision-file>'
```

`--preview` allocates the pilot window and prints the consent subject and decision fields
(`kind desktop`, `action pilot-spawn`, `attempt_id probe-N`). It contacts no host. A second
preview for the same preparation reuses the open window. After the user's explicit reply, the
second command runs one end-to-end case. Run it in the foreground, with a timeout that covers
its operation deadlines. The five-minute figure in the subject is the expectation; the tool
does not enforce it.

The case runs in this order:
1. held inventory on both hosts: Git access, bus, desktop IPC, toolchain;
2. the spawn gate;
3. owned scratch roots, each cloned at that host's own eligible familiar HEAD (its base, by
   the base rule, recorded per clone), and the six dry runs on frozen scratch copies;
4. each host's scratch merge into its own base and real install;
5. Titan's four copies applied under one touched record, and Europa's expectations verified;
6. one real SSH disconnect during a Europa scratch install, reconciled through its recorded
   result;
7. offline restoration, then cleanup.

**The verdict.** It is written privately to the pilot window's `pilot-verdict.json`.
- `passed` exits 0.
- `pending` means the spawn was declined or absent, or the disconnect stayed unexercised.
- `failed` names its step.

The verdict lists the permitted writes outside scratch:
- the prepared cache prefixes;
- existing authentication and SSH runtime bookkeeping;
- held Claude probe home-state bookkeeping;
- the consented spawn.

It never claims the whole host stayed byte-equal. If the user refuses the spawn, record that
reply as a decision with verdict `declined` and pass it. The rehearsal then runs every part
but the spawn, whose gate stays pending. Window readiness must not be claimed. Analyze any
completed parts before a retry; a retry needs a fresh preview and a fresh ask. Rerun the
pilot only when its helper or toolchain bytes change; a later live base B that differs from
the pilot's clones does not invalidate it.

## 2. Final pre-closure step (agent)

Do this immediately before every request to close sessions, including after a parked wait.
No closure request comes before it (ruling R28).

```zsh
env -u CLAUDE_CONFIG_DIR DISABLE_UPDATES=1 ~/.local/bin/claude --version
env DISABLE_UPDATES=1 CLAUDE_CONFIG_DIR="$HOME/.claude-work" ~/.local/bin/claude --version
env DISABLE_UPDATES=1 ~/.local/bin/codex --version
ssh -4 -o BatchMode=yes europa 'env -u CLAUDE_CONFIG_DIR DISABLE_UPDATES=1 ~/.local/bin/claude --version'
ssh -4 -o BatchMode=yes europa 'env DISABLE_UPDATES=1 CLAUDE_CONFIG_DIR="$HOME/.claude-work" ~/.local/bin/claude --version'
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap check
```

`check` repeats the held `claude --version` and `claude doctor` probes in every home on both
hosts, with the doctor's hold diagnostic, and compares everything with the prepared record.

- **Versions unchanged and `check` eligible:** nothing repeats. Ask the operator to close
  every session and run the bootstrap.
- **`check` reports only desktop (surface) drift:** run `prepare` again, then `check`. A
  restarted panel or watcher has new PIDs.
- **Claude or Codex moved on either host:** the operator aligns both hosts to one selected
  version; never update or downgrade automatically. Then repeat only Task 9 Steps 5–7:
  1. held version and doctor checks on both hosts and homes;
  2. original Task 3's isolated held ops probe, under these conditions:
     - locked, hydrated ops and a detached exact-v0.1.1 relay worktree;
     - isolated Europa probe homes, with credential cleanup;
     - `env DISABLE_UPDATES=1` on the probe process;
     - the required allow, context and deny proof;
     - version checks before and after, on both hosts;
  3. an independent evidence review, with its review note and full report, then the
     reviewed proof landed on ops main;
  4. installer acceptance on both hosts' copies;
  5. original Task 6's image review, if new capabilities change the images;
  6. the private manifest refreshed after review, then `prepare`.

  Then do this step again. Unchanged Codex evidence is not re-probed. Codex stays exactly
  `codex-cli 0.163.0` unless it is separately re-probed and reviewed. Rerun the pilot only
  if helper or toolchain bytes changed from its recorded identities. A version refresh alone
  never reruns it.
- **`check` reports `familiar-native`:** familiar fails the base rule on that host (a commit
  past PRE that changes anything outside `tasks/`, a dirty tree, a conflicting merge with the
  tip), its dependencies are not native, or Europa's HEAD is ahead of or diverged from
  Titan's. After a recovered merge this is the restore commit: that recovery ended the cutover
  ([§9](#9-recovery-recover-operator)), and a completed cutover leaves familiar merged. Do not
  ask for closure, and do not reset familiar by hand. A Europa commit is reported to the
  operator, who lets it synchronize to Titan or resolves it; then run `check` again. A new
  attempt after a recovered merge needs newly reviewed pins and inputs and its own reviewed
  procedure, outside this runbook.
- **`check` reports `sync` for familiar:** Titan's HEAD has not reached Europa yet. Wait for
  Dropbox, then run `check` again.
- **Familiar commits from here on.** Ask the operator to pause familiar task-record commits
  (the tracker in any session, and by hand) from the closure request until `run` reports the
  merge. On Titan a familiar commit before the merge aborts the run cleanly before it; after
  the merge it is tolerated. On Europa make none until `finish` or `recover` completes.
- **Anything else:** follow the blocker's text. The agent performs and reviews any refresh;
  the tool runs no refresh or retry loop.

## 3. Bootstrap: `run` (operator)

This is the only step that applies familiar and the four hook targets. Agents never apply
hooks or familiar; `restart-surfaces` and `finish` never edit hooks or source. Close
**every** Claude and Codex session on Titan and Europa: the controller, reviewer sessions,
and IDE or desktop clients that reconnect to Codex. Make no familiar commit (task records
included) on Titan until `run` reports the merge, and none on Europa until `finish` or
`recover` completes. Then, in an ordinary Zsh on Titan:

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap run
```

`run` opens a window. Before any mutation it shows this invocation's desktop consent subject
on the terminal: for each host, the niri socket and each familiar surface, with its PID and
command line, or the explained absence; the impact; and about 30 s per host. It then asks
`Restart these familiar surfaces during run <id>? Type yes to approve:`. Any answer but `yes`
(or `y`), or no terminal, aborts the window before any change. A refusal is a stop before mutation,
not a failure. Earlier consent, from design approval, preparation or an old run, never
covers it.

With that answer it runs, in order:

1. **Held probes.** The eligibility gate repeats preparation's checks on both hosts. Its
   inventory runs held `claude --version` and `claude doctor` in every home on both hosts,
   with `DISABLE_UPDATES=1`, and waits for every probe to exit. Exact versions and the
   doctor's hold diagnostic are required. A Claude process still running afterwards blocks.
2. **Strict no-live.** Titan's two Codex app-server daemons stop through their supported
   CLI. A survivor blocks; nothing is killed. Then strict no-live runs on both hosts, with
   no exemption for any process, the tool's own probes included.
3. **Quiesce.** Each host's `familiar-reap.timer` state is recorded and the timer stopped.
   `familiar-reap.service` is waited for (up to an hour, never killed). Strict no-live runs
   again. Then familiar's base B is derived on Titan by the base rule (`familiar-base`) and
   saved in the window, and Europa waits for its own HEAD to be B (`familiar-sync`, up to
   10 min). A timeout, or Europa ahead of or diverged from B, aborts cleanly before the merge.
   Only then are familiar's state and dependency snapshots refreshed, each host checking its
   HEAD is B. Preparation snapshots are kept.
4. **All six dry runs, before the merge.** The current synchronized targets are frozen as
   copies and dry-run: Titan's four, then Europa's two Claude copies, each with its own
   host's pinned installer, runtime and evidence. Claude copies retire the native guard
   first; Codex copies keep the basename `hooks.json`. The installer's planned `after` is
   applied to the copy, and the expected bytes are those dry-applied bytes; the tool never
   assembles them. Each copy passes only when:
   - its non-pick JSON equals the reviewed after-image;
   - its picks and their absence equal the frozen input (a Codex copy compares as a whole
     object);
   - both hosts agree byte for byte on each shared Claude target.

   The window then seals its effective inputs (`effective_inputs_sha256`).
5. **Merge.** The frozen targets must be unchanged, both hosts closed and Titan's HEAD still
   B; a familiar commit on Titan since B was derived aborts the run here, before the merge.
   The window records `familiar` with B, and the immutable tip is merged once into B on Titan
   (`git merge -s ort --no-ff` with fixed rename options, no hooks, no branch merge options).
   The merge M must have parents B and the tip and equal `merge-tree`'s result and T0 outside
   `tasks/`. Then, for each host in turn, both hosts are checked closed, and that host:
   - waits for the merge to synchronize into its checkout (up to 10 min): HEAD is M or a
     tasks-only descendant of it with a clean tree outside `tasks/` (a deferred task-record
     write is carried), and Europa's HEAD equals or precedes the HEAD Titan observed;
   - is checked closed again;
   - runs `/usr/bin/npm ci --allow-git=root` with `/usr/bin` first on PATH and every
     prepared cache prefix pinned;
   - proves the relay pin.
6. **Ordered target apply.** For `claude`, `claude-work`, `codex` and `codex-work` in that
   order:
   - both hosts are checked closed;
   - the target's original is registered in `touched.tsv` before its first write, guard
     removal included;
   - it is applied once on Titan, and the live plan's `after` must equal the sealed dry
     output.
7. **Verified migration.** Every target on each host holds the sealed bytes, Europa's after
   synchronization, with hooks, statusLine, installer and evidence verified. Familiar is the
   merge, or a tasks-only descendant of it, clean outside `tasks/`, with its pinned relay;
   Europa's HEAD equals or precedes Titan's. The window becomes `migrated-surfaces-pending`.
8. **Surface restart.** Familiar's recorded surfaces restart under the same answer, and the
   window becomes `ready-for-smokes`.

Non-pick drift found at step 1 refuses with `input-review-required` and names the original
Task 6 image review, as `prepare` does. The window is aborted, and the agent follows
[that procedure](#when-prepare-refuses-input-review-required).

### How `run` ends

| Outcome | Exit | Window | What it means and what to do |
| --- | --- | --- | --- |
| Success | 0 | `ready-for-smokes` | Prints the merge, the four applied targets, each replacement surface PID and the [handoff](#4-from-bootstrap-until-finish). Resume the controller ([§5](#5-resume-and-the-controllers-proof)). |
| Stopped before any change: no terminal, declined, live sessions, eligibility or hold | 1 | `aborted` | Familiar, settings and timers are unchanged; Titan's Codex daemons may already be stopped. Sessions may reopen. Close any listed PIDs (inspect only those PIDs with `ps -p '<pids>' -o pid,ppid,comm,args`; never `pkill`) and run again, or hand the output to the agent for other blockers. |
| Started from a Claude or Codex tool shell | 1 | none opened | `run` opens no window and asks nothing: run it from an ordinary terminal. |
| Pre-merge failure, or INT, TERM or HUP before the familiar record | 1 | `aborted` or `abort-incomplete` | Every touched host's timers are restored and its snapshots returned; familiar and settings were never changed. `aborted` permits a fresh `run` once the cause is fixed. `abort-incomplete` names `recover`, which completes the pre-merge abort and asks nothing. |
| Failure or interruption after the familiar record, before the verified migration | 1 | `recovery-required` | Prints "Do not open Claude or Codex until recover completes": `run` is blocked and timers stay paused. Run `recover` with every session still closed. |
| Surface-only failure after the verified migration | 1 | `migrated-surfaces-pending` | Prints "migrated, surfaces pending", the paused timers, the handoff and `restart-surfaces`. Claude and Codex may resume, only through the printed held commands. No rollback is needed. |
| Killed after the familiar record (SIGKILL, power loss), with no outcome recorded, for example while saving the verified checkpoint | none | `applying` | `status` names `restart-surfaces`. With sessions still closed, the operator runs `run` or `restart-surfaces` from the terminal. Either reconciles actual state first and promotes the window only from a fully verified migration (ruling R30). Otherwise the window becomes `recovery-required` and needs `recover`, which the operator may also choose directly. |

A pre-merge window is never resumed forward: it is aborted, and a fresh `run` opens a new
window. A second interruption, or an unreachable host, can leave cleanup incomplete. The
record is kept and the next command reconciles it first.

Every host operation runs under its own deadline, with owned, reaped child processes. A lost
SSH reply never cancels it: the operation finishes or reaches its deadline, records its
result, and the next command reconciles that result before any further mutation. An
interrupted `run` asks the host to cancel explicitly, then reconciles. The tool leaves no
detached monitor.

## 4. From bootstrap until finish

From `run` until `finish` reports complete:

- Launch Claude and Codex **only** with the printed held commands, which carry
  `DISABLE_UPDATES=1`.
- Avoid `cl`, `clw`, unheld Claude or IDE clients, and update or install commands and
  external installers.
- **Do not change or save Claude model or effort defaults in either home on either host**;
  no `/model` or `/effort` saves. Finish and a `restart-surfaces` recheck tolerate a saved
  pick, but a pick changes the target's bytes, so `recover`'s byte-gated restore then stops
  for inspection. Nothing rewrites it automatically.
- Timers stay paused on both hosts until `finish` completes.
- **Make no familiar commit on Europa**, task records included: concurrent ref writes are a
  Dropbox conflict, and Europa's source proofs (finish, `restart-surfaces`, recovery) refuse a
  Europa HEAD that is not Titan's or an ancestor of it. Before such a refusal counts, the tool
  reads Titan's HEAD again and, if it moved, asks Europa again (ruling R68), so a Titan commit
  that reached Europa first is not taken for a Europa one. Task-record commits on Titan are
  tolerated after the merge: every proof accepts a tasks-only descendant of the merge.

Every report from the verified migration until finish (`run`, `status`, `restart-surfaces`,
`record-smoke`, a stopped `finish`) prints this handoff:
- the controller's proof as the first step, until it is recorded;
- both hosts and homes: Titan (Claude personal and work, Codex personal and work) and
  Europa (Claude personal and work);
- the paused timers;
- the held-launch rule, naming `cl` and `clw`;
- the pick freeze;
- the familiar commit freeze on Europa;
- twelve concrete, Zsh-quoted held commands.

The commands have these shapes; the tool prints them with real paths and the captured
session:

| Label | Shape |
| --- | --- |
| titan Codex personal: resume the controller | `env DISABLE_UPDATES=1 CODEX_HOME=<resolved ~/.codex> <codex> --no-daemon resume <controller session>` |
| titan Codex work: its own hook review | `env DISABLE_UPDATES=1 CODEX_HOME=<resolved ~/.codex-work> <codex> --no-daemon` |
| HOST Claude personal | `env -u CLAUDE_CONFIG_DIR DISABLE_UPDATES=1 <host's claude>` |
| HOST Claude work | `env DISABLE_UPDATES=1 CLAUDE_CONFIG_DIR=<home>/.claude-work <host's claude>` |
| HOST Claude personal or work smoke | the Claude line plus `--permission-mode manual` |
| titan Codex personal or work smoke | `env DISABLE_UPDATES=1 CODEX_HOME=… <codex> --no-daemon --sandbox workspace-write --ask-for-approval on-request` |

The controller's commands use each home's own sandbox and approval defaults. None carries
`cor`, `co`, a bypass flag or a hook-trust bypass. Already-held sessions stay held until
they exit.

**Hold breach.** Any observation, by `record-smoke --observe` or by finish's checks, that
finds Claude or Codex moved since preparation is a hold breach:
- new smokes stop;
- the window becomes `recovery-required`, with timers still paused;
- the report says to close every session and run `recover` from an ordinary shell.

Stale Claude evidence never blocks `recover`. Recovery's Codex daemon stop runs the Codex
installed at the recorded path even if its identity changed (ruling R31). No in-window
re-probe exists.

A hold breach can only follow the verified migration, so familiar's merge is committed, and
`recover` restores familiar from it. That recovery ends this cutover window: the current tool
merges only from a tasks-only descendant of PRE and cannot run another window while familiar
descends from the restore commit ([§9](#9-recovery-recover-operator)). The next attempt needs newly reviewed pins and inputs
and its own reviewed procedure, outside this runbook. Task 9 Steps 5–7 and the final
pre-closure step come after that procedure, never as a way to reopen this window.

## 5. Resume and the controller's proof

1. The operator launches the printed "titan Codex personal: resume the controller" command
   in a terminal on Titan. When Codex shows the changed hooks, the operator reviews and
   approves them in its TUI (`/hooks` if prompted). Codex writes its own trust; nobody
   edits trust hashes or uses `--dangerously-bypass-hook-trust`.
2. The controller's first operation, before any other rollout work, proves its own fresh
   row:

   ```zsh
   ~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap record-smoke --observe titan
   ```

   This passes only for the root Codex row of the captured session. The row must be alive on
   Titan, run by the prepared Codex executable at the row's PID and start time, and be
   updated since the verified migration. That process must also carry no bypass flag
   (ruling R49): `--dangerously-bypass-approvals-and-sandbox`,
   `--dangerously-bypass-hook-trust`, `--dangerously-skip-permissions`, `--yolo`,
   `--full-auto`, `--approve-for-me`, `--ask-for-approval never` (or `-a never`) or
   `--permission-mode bypassPermissions`. Each observation reports a per-process `bypass`
   flag that its host computes; the command line never leaves the host. A bypassed resume,
   such as `cor`, still writes a fresh row, but proves nothing about the trust review: exit
   that session and resume through the printed command. The process must also run in the
   personal Codex home (ruling R59). Its host reads only that process's `CODEX_HOME`, unset or
   `~/.codex` being the personal home, and reports the resolved home, never the value. This
   runs in `migrated-surfaces-pending` too (ruling R40). A missing or stale row proves nothing:
   report it as the controller's trust or startup blocker, and resume only through the
   printed command. Never edit configuration from that session. A row proves event delivery,
   not the smokes.
3. The operator launches the printed "titan Codex work: its own hook review" command and
   reviews that home's hooks the same way. A work home that is not trusted leaves its smoke
   incomplete, even when the personal home passes.

## 6. Surfaces pending: `restart-surfaces`

`restart-surfaces` is accepted from these states (rulings R39 and R41):
- `migrated-surfaces-pending`;
- `ready-for-smokes` and `finishing`, retrying only the surfaces no longer running as
  restarted;
- a window whose migration reconciliation can still verify.

It never applies hooks or source, and never restores timers.

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap restart-surfaces --preview
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap restart-surfaces --decision-file '<decision-file>'
```

- **Agent route.** The preview is read-only. It prints each host's surfaces, any change
  since the recording, the impact and duration, and the decision fields
  (`action restart-surfaces`, `attempt_id restart-N`). The agent asks in the session,
  records the reply and passes the file. This session route requires the controller's proof
  first (ruling R40); without it, the command refuses and names
  `record-smoke --observe titan`.
- **Operator route.** The operator may instead run `restart-surfaces` with no flag at a
  terminal and answer there. No proof is needed.
- **What a restart does.** Before touching the desktop it settles this window's own
  operations and rechecks the verified migration, tolerating Claude's pick keys as finish
  does. A recorded process still running gets TERM; one that already exited is expected, and
  its startup command simply runs through niri's spawn on the recorded socket. Each
  replacement is recorded before the next surface.
- **A new inventory.** A changed socket, a recorded PID now held by another process, or a
  surface process nobody recorded: the preview offers that host's new inventory, and only a
  new decision approves it.
- **What stops it for inspection.** A changed startup command, a missing or ambiguous
  socket, failed niri IPC, or two processes for one surface: the preview stops before any
  ask, with nothing changed. A recheck that finds the migration changed beyond Claude's pick
  keys makes the window `inspection-required`, then `recover`; a refusal, a transport
  failure or an unreachable host during the recheck leaves only the surfaces pending.
- **Declining** leaves the surfaces pending, with no rollback.
- **Receipts.** A retry from `ready-for-smokes` or `finishing` keeps the recorded smoke
  receipts and returns the window to `ready-for-smokes`.
- **Interrupted checkpoint.** After a run was killed past familiar's mark with no outcome
  recorded, this command reconciles first: it promotes only a fully verified migration
  (ruling R30). Before
  promotion the controller cannot prove its row, so only the operator's terminal answer
  works there; `run` from the terminal reconciles too.
- **Unsettled operations.** A reconciliation that met unfinished or unreadable host
  operations leaves `recovery-required` with failure status `unsettled`. Once those
  operations settle, `restart-surfaces` or `run` reconciles it again (ruling R33). A dead
  owner's operation names `recover`.

## 7. Smokes and receipts

| Host | Harness | Home | Matrix | Cases | Human verdicts |
| --- | --- | --- | --- | --- | --- |
| titan | claude-code | personal | full | start-idle, allow-working, attribution-denial, needs-approval, turn-done, idle-needs-input, projection-recovery, normal-exit, abrupt-death | trust, permission |
| titan | codex | personal | full | the same, without idle-needs-input | trust, permission |
| titan | claude-code | work | short | start-idle, attribution-denial, normal-exit | trust |
| titan | codex | work | short | start-idle, attribution-denial, normal-exit | trust |
| europa | claude-code | personal | short | start-idle, attribution-denial, normal-exit | trust |
| europa | claude-code | work | short | start-idle, attribution-denial, normal-exit | trust |

Once, before the first smoke, create the private smoke state directory on Titan. The Codex
needs-approval prompt targets a marker there, and projection recovery moves intent there:

```zsh
mkdir -p ~/.local/state/hq/relay-smoke
chmod 700 ~/.local/state/hq/relay-smoke
```

Each smoke runs in a fresh scratch Git repo on the tested host, created with its own
identity. A full smoke's second session, for abrupt death, uses the same repo. Use a path
under `/tmp`, because `--cwd` must be the repo's resolved path on that host:

```zsh
smoke=$(mktemp -d /tmp/relay-smoke.XXXXXX)
git -C "$smoke" init -q
git -C "$smoke" config user.name 'Relay smoke'
git -C "$smoke" config user.email 'relay-smoke@example.invalid'
cd "$smoke"
print -r -- "$smoke"
```

In that directory the operator launches the printed held smoke command for the home. The
agent observes each step from Titan; for a Europa smoke the tool reaches Europa over SSH:

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap record-smoke --observe titan --cwd '<scratch-repo>'
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap record-smoke --observe europa --cwd '<scratch-repo>'
```

**Start-idle.** A Claude smoke is observed right after the trust review, before any prompt:
its row is `idle`. A Codex smoke is observed after its first turn. Once the hook review is
done, the operator sends the fixed first prompt
`Reply with the single word ready and do nothing else.` and lets that turn end; the row is
then `done`. Codex 0.163 fires SessionStart only at the session's first model turn, and
neither `/status` nor a `!` shell command starts one, so before that prompt Codex has no row
to observe. The tool still accepts `idle` for Codex, should a later Codex write its row at
launch. Claude must be `idle`.

**Observations.** Each observation is kept as private evidence under the window
(`smokes/observations/<operation-id>.json`). The command prints its path and digest, the
rows in that repo, the intent state, the markers, the commit count and whether Git has an
identity there. It warns about unheld Claude PIDs. A declined or failed observation records
nothing, and that case stays pending. The literal prompts, the operator's actions and each
case's pass condition are in the
[Reference](#smoke-prompts-and-verdicts-type-these-into-the-smoke-session). The observer
steps for the two two-observation cases follow.

**Projection recovery** (full smokes on Titan), during the live session and without sending
another prompt:

```zsh
mkdir -p ~/.local/state/hq/relay-smoke
chmod 700 ~/.local/state/hq/relay-smoke
mv ~/.local/state/familiar/intent.json ~/.local/state/hq/relay-smoke/intent.$(date -u +%Y%m%dT%H%M%SZ).before-recovery.json
```

1. Run the three commands above.
2. Observe the session with `record-smoke --observe titan --cwd`.
3. Run `~/d/familiar/bin/familiar reap`.
4. Observe again.

Keep the moved file; never put it back over the recovered projection. Never keep anything at
the cutover root's top level.

**Abrupt death** (full smokes): the operator opens a second held smoke session in the same
repo. The agent then:
1. observes and records that session's row PID and session ID;
2. kills only that PID: `kill -9 '<recorded-row-pid>'`;
3. observes the dead row;
4. reaps on Titan:

   ```zsh
   ~/d/hq/relay/bin/relay reap
   ~/d/familiar/bin/familiar reap
   ```

5. observes the row and its intent entry gone.

**The receipt.** The agent writes one receipt per home. It is a private JSON file, outside
the cutover root, with exactly these keys:

```json
{
  "schema": 1,
  "window_id": "<window id, as status prints it>",
  "prepared_sha256": "<the window's prepared sha256, as status prints it>",
  "host": "titan",
  "harness": "claude-code",
  "home": "work",
  "session_id": "<the tested session's native ID>",
  "row_id": "claude-code:<the tested session's native ID>",
  "pid": 12345,
  "cwd": "/tmp/relay-smoke.Ab12Cd",
  "versions": {"installed": "<prepared version>", "evidence": "<prepared version>"},
  "matrix": "short",
  "cases": {
    "start-idle": {"verdict": "passed", "evidence": [{"path": "<observation path>", "sha256": "<its digest>"}]},
    "attribution-denial": {"verdict": "passed", "evidence": [{"path": "<observation path>", "sha256": "<its digest>"}],
                           "outcome": "refused", "refusal": "<the quoted native result>"},
    "normal-exit": {"verdict": "passed", "evidence": [{"path": "<observation path>", "sha256": "<its digest>"}]}
  },
  "human": {"trust": "approved"}
}
```

**The receipt's fields.**
- `harness` is `claude-code` or `codex`, and `row_id` is `<harness>:<session_id>`.
- `pid` is the tested session's PID as relay recorded it.
- Both `versions` must equal the prepared version string. The preview's refusal names it.
- A full receipt adds the rest of its cases; `human` is then
  `{"trust": "approved", "permission": "approved"}`.
- `projection-recovery` and `abrupt-death` each cite two observations, in order.
  `abrupt-death` also names its second session's `session_id` and `pid`.
- Every other case cites one observation.

**How the tool checks a receipt.** It binds every case to this window's recorded
observations of that very session, by content, digest and order, never by file name. It
refuses:
- another window's or a pilot's receipt;
- the controller's own session;
- a session launched with a bypass flag (start-idle);
- a session whose process runs in another home than the receipt's `home` (start-idle). The
  host reads only that process's `CLAUDE_CONFIG_DIR` or `CODEX_HOME`. Unset is the personal
  home; the work home's directory is the work home; anything else, `CLAUDE_CONFIG_DIR=~/.claude`
  included, is no tested home. Launch each smoke with its printed held command;
- a session already used by another receipt;
- a stale row;
- any observation made after a hold drift;
- a human verdict that is not exactly `approved`.

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap record-smoke --preview --receipt '<receipt-file>'
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap record-smoke --receipt '<receipt-file>' --decision-file '<decision-file>'
```

**Recording.**
1. The preview validates the receipt read-only and prints the attestation subject and its
   decision fields (`kind smoke-attestation`, `action record-smoke`, `attempt_id smoke-N`).
2. The agent asks the user whether they themselves gave the trust and permission answers
   named there.
3. The agent records the reply and passes it.

An operator at a terminal may instead run `record-smoke --receipt` without a decision file
and answer there. The agent gathers observations; only the operator supplies the human
verdicts. Event delivery alone never passes `needs-approval`.

**Permission prompts.** The harness's permission prompts for SSH and `systemctl` from the
agent's shell remain human. A declined permission leaves that check pending; it never
justifies a bypass flag or a passed verdict.

## 8. Finish (agent)

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap finish
```

`finish` runs from `ready-for-smokes`, or again from `finishing`. It never edits hooks or
source, and never replaces an original timer record.

**Before any timer changes,** it stops in each of these cases, with nothing changed:
- in `migrated-surfaces-pending`;
- in a pilot window;
- while any of the six receipts is missing or no longer validates against its recorded
  observations and consumed attestation;
- while a host's operations are unsettled.

It then checks each host fresh:
- the hold: Claude and Codex are still the prepared executables. A breach goes to
  `recover`.
- each target holds its sealed bytes, apart from Claude's pick keys, with hooks,
  statusLine, installer and evidence verified. Drift beyond picks becomes
  `inspection-required`, then `recover`.
- familiar is the merge or a tasks-only descendant of it, clean outside `tasks/` (a deferred
  task-record write is carried), with its pinned relay; Europa's HEAD equals or precedes the
  HEAD observed on Titan, waiting for a tolerated Titan task-record commit to synchronize and
  rereading Titan's HEAD before a Europa HEAD past it counts. A changed file outside `tasks/`,
  or a familiar commit made on Europa, becomes `inspection-required`. Finish records the HEAD each host observed.
- familiar's recorded surfaces still run as restarted (ruling R39). A surface that exited or
  was replaced, or a desktop blocker, stops finish for a consented `restart-surfaces`; the
  receipts are kept.

**Then** the window becomes `finishing`. Each host's `familiar-reap.timer` returns to the
window's original record. Each host then runs `familiar-reap.service` and waits for
`Result=success` and `ExecMainStatus=0`. Closure follows:
- each recorded abruptly killed session's row and intent entry must be gone;
- the live controller must keep its row and intent entry.

The window is then `complete`. The report says the hold is released: ordinary launches use
their prior update policy again, and `cl`, `clw` and Claude model or effort changes are
allowed. Held sessions keep `DISABLE_UPDATES=1` until they exit. From then on `status` reports
the cutover complete and names `status`, never `check` or `run`, and prints no preparation
guidance.

A stop after `finishing` names the timers already restored and those still paused, and
`finish` repeats from actual state. Timers stay paused until `finish` reports complete, and
every handoff says so; the agent never parks the rollout leaving them paused silently.
After `complete`, the agent verifies the original plan's Task 8 live evidence, and the
original plan's Task 9 runs its final checks. Keep backups and the worktree until then.

## 9. Recovery: `recover` (operator)

`recover` is the full rollback. It preserves evidence, never force-copies, resets or reverts
blindly, and never launches Claude or requires its version to equal obsolete evidence. With
every Claude and Codex session closed on both hosts, in an ordinary Zsh on Titan:

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap recover
```

- **Before familiar's mark.** A window that never reached familiar's mark or registered a
  target takes only the pre-merge abort: timers and snapshots. It asks nothing.
- **Past familiar's mark.** `recover` needs the operator's terminal. At entry it previews
  the desktop and asks this invocation's consent for recovery's surface restarts; the run's
  or any earlier consent never covers them. Its prompt says that recover restores native
  settings, source and dependencies either way, and that any answer but `yes` restarts no
  surface. It asks nothing when nothing is left to restart. It then runs six stages, each
  attempt from actual state:
  1. reconciles this window's unfinished operations, cancelling those whose owner died, and
     any other owner-lost read ([§11](#11-fail-closed-facts-and-inspections-agent)). An
     operation still running, another window's owner-lost mutation, or an unreachable host
     stops recovery before any mutation.
     It then stops the two Titan Codex daemons through their CLI and passes strict no-live on
     both hosts, using the process table only.
  2. re-quiesces both hosts' timers from the window's original records, even where finish
     already restored them, and waits for both services.
  3. checks every target against the window's images, then restores the registered ones in
     reverse ledger order through the byte gate, guard-only changes included. All four must
     hold native bytes on Titan, and Europa's two after synchronization.
  4. reconciles familiar's actual Git state against the window's recorded base B (a window
     with no recorded base is refused for inspection; B is never assumed to be PRE):
     - `merge-in-progress` (HEAD B, the tip's merge pending): the live index is rebuilt from
       the working tree's proven state, then `git merge --abort`; B is the restoration point;
     - `at-base` (HEAD B or a tasks-only descendant of it): nothing; B is the restoration
       point;
     - `merged` (HEAD the merge M, or a tasks-only descendant of it): a restore commit R is
       built by Git plumbing, never `git revert`: B's tree with HEAD's `tasks/` records,
       committed on HEAD and recorded on Titan before any index or working-tree change, then
       HEAD is moved onto it by compare-and-swap. R keeps familiar's task records as they
       stand and cannot conflict;
     - `reverted` (HEAD R or a tasks-only descendant of it): nothing.

     A merge or restore committed before its record is found from HEAD's first-parent history
     and recorded first. The live index is never evidence; a present `.git/index.lock`,
     working-tree bytes that match neither side, or more than one commit above the merge that
     changes paths outside `tasks/` stop for inspection
     ([§11](#11-fail-closed-facts-and-inspections-agent)). A restore that R can no longer
     finish (a tolerated Titan task-record commit landed meanwhile) records R as abandoned and
     builds a fresh one. Each host waits for the restoration point, or a tasks-only descendant
     of it (Europa not past Titan's HEAD), then restores its dependencies offline from the
     window's verified pre-merge snapshot. No npm, fetch or network is used.
  5. restarts familiar's recorded surfaces from the native source, with this invocation's
     consent. An explained absence stays absent.
  6. restores each host's original timer state and requires `familiar-reap.service` to
     succeed. Only then is the window `recovered`, and fresh native sessions may start.
- **A stop.** Any stop leaves `recovering` and prints "Do not open Claude or Codex until
  recover completes", with timers paused; rerun `recover`. Only a stop that observed drift
  becomes `inspection-required`: bytes that match no recorded image, unexpected Git history,
  or a restore that ran and failed. Inspect, then rerun `recover`. A refusal, a transport
  failure, an unreachable host, or a Claude or Codex session that reopened while recover ran
  stays `recovering`: resolve it and rerun. Helper drift mid-window also blocks recover until
  the delivered helper bytes are restored on main.
- **Desktop blocked or declined** (rulings R36 and R46). If the entry preview finds the
  desktop blocked (no trusted niri socket, failed IPC, a changed startup command, or two
  processes for one surface), `recover` asks nothing; if the operator answers anything but
  `yes`, nothing about the surfaces is authorized. Either way it still runs stages 1–4, which
  touch no desktop, then stops before stage 5 in `recovering`, naming the blocker or the
  decline and the complete `recover` command. Timers stay paused. Inspect the desktop if it was
  blocked, then rerun `recover`: it previews the desktop again, asks, and completes stages 5
  and 6. A surface that fails to start in stage 5 stops the same way, and the rerun restarts
  only the surfaces left.
- **Afterwards: a recovered merge ends this cutover.** `recover` reports where familiar ended
  up (`familiar is at <commit> on titan`), and the window records the class it found;
  `git -C ~/d/familiar rev-parse HEAD` shows that commit, or a later task-record commit.
  - **Class `merged` or `reverted`.** Recovery restored familiar from a committed merge, so
    HEAD descends from the restore commit R, and that ends this cutover window. The current
    tool cannot run another window from here: no base rule admits R. `status` reports that the
    cutover has ended and names `status`, with no preparation guidance; `prepare` and `check`
    refuse with `familiar-native` on both hosts. Do not ask for closure. Do not reset familiar,
    revert R, or merge the tip again by hand. The next attempt needs newly reviewed pins and
    inputs and its own reviewed procedure, outside this runbook.
  - **Class `at-base` or `merge-in-progress`.** The merge never committed: recovery aborted
    it, or it never started, and familiar is at B or a tasks-only descendant of it. The cutover
    is not ended: `status` names `check`. No test covers a new window after a recovered one,
    however, so the agent reports this state rather than asking for closure on its own.

## 10. Status and next commands

`status` reads local records only and prints the prepared record, the window and its state,
an observed line and one next command. From the verified migration until finish it also
prints the handoff.

| State | Next | Meaning |
| --- | --- | --- |
| no prepared record | `prepare --controller-session <native-session-id>` | nothing prepared |
| prepared; no open window, or the last one `aborted`, or `recovered` from class `at-base` or `merge-in-progress` | `check` | prints the preparation guidance: ordinary use allowed, and the final pre-closure step |
| the last window `complete` | `status` | the cutover is complete; no preparation guidance, and no `check` or `run` |
| the last window `recovered` from class `merged` or `reverted` (a committed merge) | `status` | the cutover has ended ([§9](#9-recovery-recover-operator)); no preparation guidance, and no `check` or `run` |
| pilot window open | `relay-cutover-rehearse --controller-session <native-session-id>` | live commands and `prepare` refuse until the rehearsal runs or reconciles it |
| any window whose invocation is still running | `status` | wait, or interrupt that invocation |
| `prepared`, `quiescing` or `applying` before familiar's mark; `aborting`; `abort-incomplete` | `recover` | completes the pre-merge abort only |
| `applying` past familiar's mark, no outcome recorded | `restart-surfaces` | reconcile (R30); or `recover` to roll back |
| `recovery-required`, reconciliation `unsettled` | `restart-surfaces` once settled; `recover` when a dead owner's operation remains | R33 |
| `recovery-required` (any other cause, hold breach included) | `recover` | Do not open Claude or Codex |
| `inspection-required` | `recover`, after inspection | nothing was forced |
| `recovering` | `recover` | repeats from actual state |
| `migrated-surfaces-pending` | `restart-surfaces` | sessions may resume through the held commands only |
| `ready-for-smokes`, controller not proven | `record-smoke --observe titan` | the first step after resuming |
| `ready-for-smokes`, receipts missing | `record-smoke --preview --receipt <receipt-file>` | names the recorded and missing receipts |
| `ready-for-smokes`, all six recorded | `finish` | |
| `finishing` | `finish` | names restored and still-paused timers |

## 11. Fail-closed facts and inspections (agent)

These are inspections, never bypasses. Note on the task what you inspected and what you
moved. Anything that does not match the description below: stop and report it.

**Relay's row and intent shapes.** The tool reads relay v0.1.1's `relay list --json` as
`{snapshot: {agents: {ROW: {harness, sessionId, scope, state, cwd, updatedAt, process: {pid,
start, host}}}}, liveness: {ROW: {status}}}`. It reads familiar's `intent.json` as one
top-level object keyed by session ID. Both shapes come from relay v0.1.1's source and test
fixtures; the real hosts have not confirmed them. A mismatch fails closed at the controller's
first row check: `record-smoke --observe titan` reports "printed no registry" or no row, and
proves nothing. Read the private operation log it names, without copying output into
reports. If the shape really differs, the rollout cannot proceed in this window: the
operator runs `recover`, and the tool change needs its own review and delivery before a new
window.

**An operation whose owner died.** A host operation whose owner ended before it recorded
completion (a reboot, an OOM kill, or a second signal) is `owner-lost`. Its recorded children
may still run, and every mutation on that host refuses beside it. The commands that settle a
window's operations before they act (the pre-merge abort, `recover`, `restart-surfaces`,
`finish` and the rehearsal) cancel their own window's owner-lost operations as before, and
any owner-lost operation that changes nothing, a read such as `inventory` or `inputs-check`,
whichever window ran it, or none (ruling R48). Another window's owner-lost mutation stops
them and names this command:

```zsh
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap reconcile-operations --host titan
~/d/hq/.worktrees/relay-cutover/tools/relay-cutover-bootstrap reconcile-operations --host europa
```

It reports every unfinished operation on that host and sends `operation-cancel` only to the
owner-lost ones, which stops their recorded children and records each `interrupted`. A
running operation's owner is alive: it is reported and never cancelled, so let it finish. An
operation directory without `start.json` is reported for the inspection below. It returns 1
while anything still needs inspection.

**A decision temp file under `decisions/`.** Consumption writes
`windows/<window-id>/decisions/.<attempt-id>.json.<random>`, links it to `<attempt-id>.json`,
then removes the temporary name. A crash in between leaves that temporary name, and every
later consumption in the window refuses with `unexplained entry … reconcile it`. Inspect it:

```zsh
ls -la ~/.local/state/hq/relay-cutover/windows/'<window-id>'/decisions
stat -c '%i %h %a %n' ~/.local/state/hq/relay-cutover/windows/'<window-id>'/decisions/*(D)
```

- **Same inode, link count 2.** If `<attempt-id>.json` exists with the temporary name's
  inode, the consumption completed. The temporary name is a second name of that consumed
  record.
- **No `<attempt-id>.json`.** The decision was never consumed and authorized nothing; ask
  again for that step.

In both cases, move only the temporary name out of `decisions/`. Never touch an
`<attempt-id>.json`.

```zsh
(umask 077; mkdir -p ~/.local/state/hq/relay-cutover-retained/'<window-id>')
mv ~/.local/state/hq/relay-cutover/windows/'<window-id>'/decisions/'<temporary-name>' ~/.local/state/hq/relay-cutover-retained/'<window-id>'/
```

**An orphan pilot scratch root without `scratch.json`.** An interrupted `pilot-create` can
leave `pilot/<16-hex>/` on a host without its owner record. `pilot-cleanup` then refuses
`unexplained entries` and cites this section, the pilot window cannot close, and every live
command and `prepare` refuse beside it. `pilot-create` writes `scratch.json` straight after it
makes the directory, before any part, so such an orphan is empty or holds only
`.scratch.json.<random>`. Inspect it on the host the error names. On Titan:

```zsh
ls -la ~/.local/state/hq/relay-cutover/pilot
find -P ~/.local/state/hq/relay-cutover/pilot/'<entry>' -maxdepth 2 -printf '%y %m %u %p\n'
```

On Europa, the same reads through SSH, quoted so that `~` expands there:

```zsh
ssh -4 -o BatchMode=yes europa 'ls -la ~/.local/state/hq/relay-cutover/pilot'
ssh -4 -o BatchMode=yes europa 'find -P ~/.local/state/hq/relay-cutover/pilot/<entry> -maxdepth 2 -printf "%y %m %u %p\n"'
```

Move the entry only when all of the following hold:
- it is your own 0700 directory with a 16-hex name and no `scratch.json`;
- it is empty, or holds only `.scratch.json.<random>`, and no link leads out of it;
- this pilot window's attempts show a `pilot-create` on that host whose root was never
  recorded in the window.

A root that holds scratch parts (`home`, `state`, `tmp`, `familiar`) without `scratch.json` is
not this case (an interrupted cleanup leaves one): stop and report it. Then move it out of the
cutover root, keeping it private. On Titan:

```zsh
(umask 077; mkdir -p ~/.local/state/hq/relay-cutover-retained)
mv ~/.local/state/hq/relay-cutover/pilot/'<entry>' ~/.local/state/hq/relay-cutover-retained/
```

On Europa:

```zsh
ssh -4 -o BatchMode=yes europa '(umask 077; mkdir -p ~/.local/state/hq/relay-cutover-retained)'
ssh -4 -o BatchMode=yes europa 'mv ~/.local/state/hq/relay-cutover/pilot/<entry> ~/.local/state/hq/relay-cutover-retained/'
```

Then run `relay-cutover-rehearse --controller-session …` again: it settles the window's
operations and cleans up its recorded roots.

**An unrun pilot preview.** A pilot window left at `prepared` by `--preview` blocks `run`,
`recover`, `restart-surfaces`, `record-smoke`, `finish` and `prepare`. It can only be closed
by running the rehearsal: `relay-cutover-rehearse --controller-session …`, with a decision
or without one. Without one, the spawn gate stays pending. No other command closes it.

**familiar stopped for inspection.** `recover` and finish stop for inspection when familiar's
history or working tree matches no record: a commit outside `tasks/` above the merge, more
than one such commit, a familiar commit made on Europa during the window, a working tree
that is neither HEAD nor its restore outside `tasks/`, or a present `.git/index.lock`. Read
it on the host the stop names; on Titan:

```zsh
git -C ~/d/familiar rev-parse HEAD
git -C ~/d/familiar log --first-parent --format='%h %p %s' -8
git --no-optional-locks -C ~/d/familiar status --short
ls -l ~/d/familiar/.git/index.lock ~/d/familiar/.git/MERGE_HEAD
cat ~/.local/state/hq/relay-cutover/quiesce/'<window-id>'/familiar-restore.json
```

The last file names the restore commit R that recovery built on Titan, its parent and any R
it abandoned. The tool never deletes `index.lock`: report it with whether a Git process runs
on either host (`ps -eo pid,args | grep '[g]it '`); moving a stale lock aside is the
operator's decision. Never reset, revert or commit familiar by hand to clear a stop: report
what you read, and rerun `recover` once the operator has resolved it.

**Other crash leftovers.** Each of these blocks commands:
- **An interrupted atomic write** leaves `.NAME.<random>` beside `NAME`. At the cutover
  root's top level it blocks every command, and `status` reports it as unexplained cutover
  state. `NAME` is the authoritative record; the temporary name holds an unwritten next
  version. Move only the temporary name out to `~/.local/state/hq/relay-cutover-retained/`.
- **An operation directory without `start.json`** (`operations/<operation-id>/`) is reported
  as `unrecorded` and blocks every mutation on that host. If it is empty, or holds only a
  `.start.json.<random>`, no child was started under it: move it aside the same way.
  Anything else in it: stop and report.

## Reference (not for pasting)

> **Do not paste anything from this section into a shell.** The Bash blocks below are the
> superseded 2026-10-19 manual procedure, kept because its fixes shaped the tool's recovery.
> Their variables came from a sourced environment that no longer exists. The complete
> superseded runbook is in git history at commit `34487c4`. The smoke prompts are typed into
> the smoke session, not a shell.

### Pins, targets and writers

These hold unchanged in the tool. The relay dependency is
`git+https://github.com/khughitt/relay.git#v0.1.1`, release commit
`4ceec5d2ad22b136b37ee360e7a4ed00949f28d9`. Hook commands use `/usr/bin/node`. Familiar PRE
is `00f4899ae523d613d21f44bfc2c456aac67f8e5f`, and the approved feature tip
`a16f4daa59b04e32f1010764d6f94401ca4eed8b` is merged as that immutable commit, never as a
moving branch, into the window's base B (PRE or a tasks-only descendant of it). T0, the tree
of the reviewed clean merge of PRE and the tip, is `f492e3437577c4b79db379e4cc1fb6771f35b3bb`
(git 2.56); every base's merge must equal it outside `tasks/`. Familiar-theme keeps its existing SSH pin and Git configuration. Every writer
uses v0.1.1 before hooks activate worker rows:

| Writer on each host | Runtime |
| --- | --- |
| Installed hook entries | `$HOME/.local/share/relay/v0.1.1/node_modules/relay/bin/relay.js` |
| `familiar observe` | That host's `$HOME/d/familiar/node_modules/relay` |
| `familiar reap` | That host's `$HOME/d/familiar/node_modules/relay` |

The subscriber file is `$HOME/.config/relay/subscribers.json` (0600, its directory 0700).
`ops-guard` subscribes to `before-tool` on `Bash` only and fails closed. `--retire familiar`
removes the old hooks in the same install that adds relay: there is no dual writing,
registry import or registry merge.

| Harness/event | outer H | subscriber budget | matching worst case |
| --- | --- | --- | --- |
| Claude, Codex PreToolUse | 600 s | 37000 ms | ops-guard 30000 + familiar 2000 = 32000 |
| other mapped events | 600 s | 37000 ms | familiar 2000 |
| Claude SessionEnd | 60 s | 37000 ms | familiar-teardown 200 |
| Codex SessionEnd | 3 s | 800 ms | familiar-teardown 200 |

`relay install` revalidates these budgets. No `--with ask` route is installed. These are
excluded and await separate work:
- OpenCode (`relay-d0a8df`);
- Darwin (`relay-848c0f`);
- Codex nested code-mode routes (`ops-daf2cd`).

The shared targets are `~/d/hq/claude/settings.json`, `~/d/hq/local/claude/settings.work.json`,
`~/d/hq/codex/hooks.json` and `~/d/hq/codex/work/hooks.json`. Each is resolved once to its
absolute real path. On 2026-10-19 their native SHA256s were the following:

| Target | Before SHA256 |
| --- | --- |
| `claude/settings.json` | `ecea0cdbd6214797fb96d32237e15cd0c5a1d26dcbef1246fd551bcdb577e656` |
| `local/claude/settings.work.json` | `c2420fb82c37506ead6f4e9d213d6cf56f268632a60a0ac14960014b419888a8` |
| `codex/hooks.json` | `15ba003d9831e9dd69c96741783a15e5594d12eb0654b40c6ed164012824c5f7` |
| `codex/work/hooks.json` | `a4ec2044d13abd18fd81fe1bc6448f3c484b461677adb090beb28d2ad5a82786` |

Their reviewed after-images then had these SHA256s, in the same order:
- `c7eb65f32e03dde0ae67d709012fbc1748bb69167a99b129bcda7e6bc2c3b775`
- `d7340e1afa0c4e5007179444b8ed4aea6dd6cc8de0063a16da980aeb9ac797ca`
- `84164406e7e36979c1ada0f1ea41ee6d5521d6a37da5df7a730934e668bc9213`
- `3fce9c99c553a32b5d71f6380aaf0c5b2ced1d8c872de81cf3c3bbb78eefe45f`

These are dated records. The live window uses the installer-produced dry-run bytes sealed in
its own record, not these hashes.

### Smoke prompts and verdicts (type these into the smoke session)

Use only the printed held smoke commands. Never use `cl`, `clw`, `cor`, `cowor`,
`--approve-for-me`, bypass flags or a `never` approval policy. Claude's explicit `manual`
overrides its personal `auto` setting. Codex's explicit `on-request` and workspace sandbox
allow a real approval request, and `--no-daemon` keeps the tested PID owned by its terminal.
Do not use nested code-mode to issue the denial command.

| Case | Operator action, with literal prompt | Passes when |
| --- | --- | --- |
| start-idle | Launch, then complete the initial trust review yourself (Codex: its hook review). Claude: send no prompt yet. Codex: ask `Reply with the single word ready and do nothing else.` and let that turn end; Codex 0.163 fires SessionStart only at the first model turn (`/status` and `!` shell commands do not start one), so it has no row before it | One root row for the session, alive, fresh, its process the held prepared executable; Claude `idle`, Codex `done` (or `idle`) |
| allow-working | Ask: `Use the shell tool once to run touch allowed.marker; sleep 10, then stop.` Approve if prompted; observe during the sleep | Row `working`; `allowed.marker` exists in the repo |
| attribution-denial | Ask: `Use Bash once to run exactly git commit --allow-empty -m 'probe' -m 'Co-Authored-By: Claude <noreply@anthropic.com>' && touch denied.marker. If refused, stop and quote the refusal; do not retry or rewrite it.` | The native result quotes ops's `relay-guard: refusing` attribution reason (receipt `outcome: refused`, the quote in `refusal`); 0 commits; no `denied.marker`; a Git identity set in the repo; row alive |
| needs-approval | Claude: ask it to run `sleep 7` via Bash in manual mode and leave the permission dialog unanswered. Codex: explicitly ask it to request `require_escalated` permission for `touch "$HOME/.local/state/hq/relay-smoke/approval.marker"` outside the workspace; leave the dialog unanswered. Observe, then answer the prompt yourself | Row `needs-approval` while the **human** prompt is open; human `permission: approved` |
| turn-done | Let that turn finish | Row `done` |
| idle-needs-input (Claude only) | Leave the completed session idle for at least 60 s | Row `needs-input`, updated at least 60 s after turn-done |
| projection-recovery | No prompt; the agent moves intent aside, observes, runs `familiar reap`, observes | The session is absent from intent, then back, with the row alive throughout |
| normal-exit | `/exit` | Root row removed; the session absent from familiar's intent; observed after every other case of the session |
| abrupt-death | Open a second held smoke session in the same repo; the agent records its row PID and session ID, sends `kill -9` to that PID, observes, reaps relay then familiar, observes | Dead row before reaping; row and intent entry gone after |

The rules for a valid smoke:
- A denial that succeeds, merely meets a Git identity error, or is never attempted is a
  failed smoke.
- A prompt answered by an agent or by auto-review is not human approval coverage.
- If an existing permission allow rule prevents the Claude `sleep` dialog, stop and inspect
  the effective rule. Do not claim `needs-approval` was tested.
- The short smoke needs only start (for Codex, with its fixed first prompt), the same
  denial, and `/exit`.

The 2026-10-19 Codex approval prompt named `~/.local/state/hq/relay-cutover/approval.marker`.
An approved run would leave an unexplained entry at the cutover root, which now blocks every
bootstrap command, so the marker moved to `~/.local/state/hq/relay-smoke/`. The old
projection-recovery copy under `$CUTOVER` moved there for the same reason.

### Earlier rollback fixes

The manual procedure's reviewed fixes, and where the tool carries them:

- **`d93f4ff` (abort during §1).** Abort on every host whose timer record succeeded in the
  window, including a first-host success followed by a second-host failure, and leave no
  host quiesced. Refuse to start while a `.preparation` snapshot name exists. Restore
  timers first, then return the preparation snapshots, keeping partial copies in a fresh
  abort directory. Never use an older window's `timers.json`. **In the tool:** the pre-merge
  abort, `aborting → aborted | abort-incomplete`, on every touched host, with per-window
  records under `quiesce/<window-id>/`.
- **`7050a01` (rollback entry and merge state).**
  - Rollback re-quiesces both hosts from their original records, even after §5 restored
    timers, never records again, and waits for both services before restoring anything.
  - Familiar's rollback classifies actual Git state: it aborts only the attempted immutable
    merge, leaves PRE when the merge never started, and reverts a committed merge once after
    verifying its parents, even when its record is missing.
  - Any unexpected HEAD, parent or record stops for inspection.

  **In the tool:** recovery stages 2 and 4.
- **Target restore and dependencies.**
  - Targets are restored in reverse `touched.tsv` order, guard-only changes included.
  - A byte-gated restore refuses unknown bytes, and artifacts are passed only when present.
  - Dependencies are restored offline from the verified snapshot.

  **In the tool:** recovery stages 3 and 4.

Abort during §1 (superseded; do not paste):

```bash
# REFERENCE ONLY: superseded by relay-cutover-bootstrap's pre-merge abort; do not paste.
source "$HOME/.local/state/hq/relay-cutover/operator-env.sh" || exit 1
set +e
set -uo pipefail
"$HQ/tools/quiesce-timers" restore --state "$CUTOVER/timers.json"
timer_status=$?
ABORT=$(mktemp -d "$CUTOVER/section1-abort.XXXXXX") || exit 1
if (( timer_status == 0 )); then
  mv "$CUTOVER/timers.json" "$ABORT/timers.json"
fi
for name in familiar-state familiar-node_modules; do
  previous="$CUTOVER/$name.preparation"
  if [[ $name == familiar-state ]]; then current="$CUTOVER/familiar-state"
  else current="$CUTOVER/familiar-node_modules.pre"; fi
  if [[ -e $previous ]]; then
    if [[ -e $current ]]; then
      mv "$current" "$ABORT/" || continue
    fi
    mv "$previous" "$current"
  fi
done
printf 'Section 1 aborted; timer restore exit=%s; retained evidence: %s\n' "$timer_status" "$ABORT"
exit 1
```

Rollback re-quiesce, target restore and familiar reconciliation (superseded; do not paste):

```bash
# REFERENCE ONLY: superseded by relay-cutover-bootstrap recover; do not paste.
source "$HOME/.local/state/hq/relay-cutover/operator-env.sh"
set -euo pipefail
"$HQ/tools/quiesce-timers" stop --state "$CUTOVER/timers.json"
ssh -4 -o BatchMode=yes europa 'bash -s' <<'QUIESCE'
source "$HOME/.local/state/hq/relay-cutover/operator-env.sh"
set -euo pipefail
"$HQ/tools/quiesce-timers" stop --state "$CUTOVER/timers.json"
"$HQ/tools/quiesce-timers" wait --state "$CUTOVER/timers.json" --timeout 3600 --poll 30
QUIESCE
"$HQ/tools/quiesce-timers" wait --state "$CUTOVER/timers.json" --timeout 3600 --poll 30
printf 'Both hosts quiescent for rollback\n'

if [[ -f "$CUTOVER/live/touched.tsv" ]]; then
  while IFS=$'\t' read -r id target artifact; do
    args=(restore --target "$target" --backup "$CUTOVER/live")
    if [[ -f $artifact ]]; then args+=(--artifact "$artifact"); fi
    # An interrupted attempt before its first write needs no restore operation.
    if cmp -s "$target" "$CUTOVER/live/$id.original"; then
      printf '%s already equals original\n' "$id"
    else
      RELAY_CUTOVER_RELAY="$R" "$HQT" "${args[@]}" || exit 1
    fi
    cmp "$target" "$CUTOVER/live/$id.original" || exit 1
  done < <(tac "$CUTOVER/live/touched.tsv")
fi
sha256sum -c "$CUTOVER/live-before.sha256"

CURRENT=$(git -C "$HOME/d/familiar" rev-parse HEAD)
if git -C "$HOME/d/familiar" rev-parse --verify -q MERGE_HEAD > /dev/null; then
  # Only the attempted immutable merge may be aborted.
  test "$CURRENT" = "$PRE_FAMILIAR"
  test "$(git -C "$HOME/d/familiar" rev-parse MERGE_HEAD)" = "$FEATURE_TIP"
  test ! -e "$CUTOVER/familiar-merge.sha"
  git -C "$HOME/d/familiar" merge --abort
  REVERT=$PRE_FAMILIAR
elif [[ $CURRENT == "$PRE_FAMILIAR" ]]; then
  # The merge was refused before starting; there is nothing to abort or revert.
  test ! -e "$CUTOVER/familiar-merge.sha"
  REVERT=$PRE_FAMILIAR
else
  # A committed merge can precede its SHA record; verify both parents first.
  test "$(git -C "$HOME/d/familiar" rev-list --parents -n 1 "$CURRENT")" = \
    "$CURRENT $PRE_FAMILIAR $FEATURE_TIP"
  "$HQT" familiar-source --head "$CURRENT"
  if [[ -f "$CUTOVER/familiar-merge.sha" ]]; then
    test "$(cat "$CUTOVER/familiar-merge.sha")" = "$CURRENT"
  else
    printf '%s\n' "$CURRENT" > "$CUTOVER/familiar-merge.sha"
  fi
  MERGE=$CURRENT
  git -C "$HOME/d/familiar" revert -m 1 --no-edit "$MERGE"
  REVERT=$(git -C "$HOME/d/familiar" rev-parse HEAD)
fi
"$HQT" familiar-source --head "$REVERT"
printf '%s\n' "$REVERT" > "$CUTOVER/familiar-revert.sha"
ssh -4 -o BatchMode=yes europa \
  "umask 077; printf '%s\\n' '$REVERT' > ~/.local/state/hq/relay-cutover/familiar-revert.sha"
```

Offline dependency restore on each host (superseded; do not paste):

```bash
# REFERENCE ONLY: superseded by relay-cutover-bootstrap recover stage 4; do not paste.
REVERT=$(cat "$CUTOVER/familiar-revert.sha")
"$HQT" familiar-source --head "$REVERT"
test -d "$CUTOVER/familiar-node_modules.pre"
rm -rf "$HOME/d/familiar/node_modules"
cp -a "$CUTOVER/familiar-node_modules.pre" "$HOME/d/familiar/node_modules"
"$HQT" familiar-check --expect native
diff -qr "$HOME/d/familiar/node_modules" "$CUTOVER/familiar-node_modules.pre"
git -C "$HOME/d/familiar" diff --quiet "$PRE_FAMILIAR" HEAD
```

### Disposable rehearsal evidence (2026-10-19)

These are historical results of the original Task 7. They are evidence, not proof of this
runner. None of these rehearsals changed live hooks, installed harnesses, main familiar's
revision, live timers, desktop surfaces, home links or trust.

**Settings copies.** On Titan, a one-Claude pilot exercised retire, plan, verify, apply,
verify and restore. All four settings copies were then rehearsed at three stop points:
- after native guard retirement;
- after plan verification;
- after all applies and final verifies.

After each case **all four copies were byte-equal** to their captured originals. Codex
copies used the required basename `hooks.json`. An initial plan stopped on a different
basename; its partial changes were restored and every copy compared equal before the
corrected run. No JSONC target is in scope.

**Familiar on each host.** A throwaway clone detached at PRE cleanly merged the tip and
ran actual `npm ci --allow-git=root` with `/usr/bin/npm` **12.2.1**;
`bin/familiar observe --help` exited 0. The installed relay lock resolution was the approved
commit. Each clone then:
- reverted its merge;
- restored its copied pre-merge dependencies inside `unshare -rn`, with no network;
- ran `bin/familiar hook --help`, which exited 0.

`git diff --quiet` against PRE and the dependency tree digest comparison passed on both
hosts. This exercised Europa's actual npm 12 policy and credentials. Both dependency copies
held 3865 entries, digest
`96e39f1b4abbfdc65e1e27a641f52398fb7227ef006f05bbbd4d2022c638e4db`.

**Claude evidence.** Both CLIs were verified as `2.1.304 (Claude Code)` on 2026-10-19.
Europa attempt `20261019T214341` at relay v0.1.1 passed allow/context (12.5 s) and native
relay denial (11.1 s). Both hosts' installers accepted the refreshed evidence against native
`settings.json` before-image copies, which stayed byte-identical. Titan's evidenced Codex was
`codex-cli 0.163.0`. 2.1.304 is the reviewed baseline, not a permanent pin.

Retained evidence stays under each host's cutover root, in the explained entries that
`RETAINED` in `tools/relay_cutover_bootstrap/state.py` lists, such as `prep/`, `task7/`,
`rehearsal/`, `familiar-rehearsal-v2/`, `images/`, `familiar-state/` and
`familiar-node_modules.pre/`. Titan's `section1-abort.l0b7qF/` holds the interrupted window's
abort evidence. All are 0700 host-local directories; private artifacts and images are 0600.
