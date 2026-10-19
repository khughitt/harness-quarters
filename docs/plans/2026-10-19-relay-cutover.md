# Relay operator cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace familiar's native hook entries and the native ops guard with relay
v0.1.1 on the Linux hosts' Claude Code and Codex homes, through a prepared, rehearsed
runbook the operator applies one harness at a time, with exact rollback.

**Architecture:** hq pins relay's runtime per host (as it pins pi) and tracks the
subscriber config as a template; a small `tools/relay-cutover` checks preconditions,
removes the native guard entry and compares live settings with the reviewed images.
`relay install` makes every relay edit and its rollback artifact. The reviewed
after-images of the tracked settings are committed on this branch; the live apply
happens only in the operator window, from an ordinary shell, and is verified against
them.

**Tech Stack:** Python 3 (hq tools, pytest via `uv run`), Node ≥22 (relay CLI),
npm lockfile pinning, systemd user timers, Codex hook trust.

**Spec:** ops `docs/specs/2026-09-16-relay-design.md` §8 (approved after `d7e2c33`);
brief "A" in ops `docs/plans/2026-09-16-relay-bootstrap.md` (approved after
`bc53c51`); relay `docs/runbooks/hook-install-rollback.md`; familiar
`docs/install.md` on `feat/relay-identity`. Task: hq-539508; release goal relay-1231bf.

## Inventory this plan argues from (titan, 2026-10-19)

- `~/.claude/settings.json` → hq `claude/settings.json` (tracked); `~/.claude-work/settings.json`
  → hq `local/claude/settings.work.json` (untracked; the brief's tracked work file
  moved there). `~/.codex/hooks.json` → hq `codex/hooks.json` and `~/.codex-work/hooks.json`
  → hq `codex/hooks.work.json` (both tracked now; the brief calls the first untracked).
  Hook trust is in hq `codex/config.toml` `[hooks.state]` and `local/codex/config.work.toml`.
- **europa reads the same hq, familiar and ops checkouts through Dropbox**: editing
  `claude/settings.json` cuts both hosts over at once. europa has Claude Code 2.1.280,
  `/usr/bin/node` v26.11.1, no Codex, no OpenCode, the same `familiar-reap.timer`.
- Familiar entries: 8 Claude events (main and work), 5 Codex events per home. The native
  ops guard `~/d/ops/hooks/claude-pretooluse` (PreToolUse `Bash`) is in **both** Claude
  files; Codex has none. Ops `claim-guard`, `claude-sessionstart`, `claude-provenance`,
  `capture-notice`, `claude-posttooluse`, lore `claude-profile` and hq
  `harness-state-refresh` stay native and untouched.
- `relay` is installed nowhere; no `~/.config/relay`, no `~/.local/state/relay` on
  either host. `node` on PATH is nvm's (titan); `/usr/bin/node` exists on both hosts.
- `relay install` refuses symlinked targets, so every target below is the real hq file.
- OpenCode v2.0.32 is installed on titan, with familiar's server plugin already
  commented out; relay's plugin is v1-only and is dropped by v2 (relay-d0a8df).
- Ops guard evidence: Claude 2.1.282 / Codex 0.157.0 at relay `c513320`; installed
  are 2.1.302 / 0.163.0. The installer does not version-check guard evidence.
- `familiar-reap.service` runs `%h/d/familiar/bin/familiar reap` (dotfiles unit);
  after the familiar merge that command prunes relay and reconciles presentation, so
  the unit itself does not change. Niri spawns `familiar-niri watch` and the
  `niri-desktop` quickshell at startup from `~/d/familiar`.

## Departures from brief A

- The runbook lives in hq `docs/runbooks/relay-cutover.md`, not ops: the targets, the
  tool and this task are hq's since the ai→hq move; ops keeps the guard and its evidence.
  Rejected: ops, which would split the procedure from the files and tool it drives.
- The work Claude settings are untracked (`local/`), and both Codex hooks files are
  tracked, so the tracked/untracked split differs from the brief's.
- The work variant already carries the native ops guard, so migrating it to relay is
  a replacement rather than the "separate explicit addition" the brief anticipated.
- OpenCode is installed but not cut over: relay's plugin cannot load on OpenCode v2
  (relay-d0a8df), and familiar's server plugin is already disabled there.
- Retiring the native ops entry point is filed in ops (Task 8) instead of being done here.
- Guard evidence is re-probed at v0.1.1 (Task 3), because the recorded evidence predates
  both the release and the installed harness versions.

## Global Constraints

- Relay dependency: `git+https://github.com/khughitt/relay.git#v0.1.1`, commit
  `4ceec5d2ad22b136b37ee360e7a4ed00949f28d9`: familiar's pin, so every relay writer
  on the host (hook entries, `familiar observe`, `familiar reap`) runs v0.1.1.
- Hook entries use `--node /usr/bin/node`, never an nvm path.
- In scope: Claude Code (two homes) on titan and europa; Codex (two homes) on titan.
  Out of scope and recorded as awaiting: OpenCode (relay-d0a8df), Darwin (relay-848c0f),
  Codex nested code-mode routes (ops-daf2cd), the `--with ask` route.
- No live host change outside the operator window, except the inert per-host installs of
  Task 1 and Task 2 (new files nothing references yet).
- The operator applies from an ordinary shell with no session of the target harness
  on either host; agents prepare and check, never apply from inside a harness.
- One writer per harness: `--retire familiar` in the same apply that adds relay. No
  dual writing, no import of familiar's `agents.json`, no compatibility layer.
- Keep old state untouched until verified: `~/.local/state/familiar` is copied aside
  before the window and not deleted by this plan.
- Rollback restores the captured settings and familiar's revision and starts fresh
  sessions; it never merges registries. Familiar is one shared checkout, so rollback
  covers every harness already applied.
- Guards fail closed; the ops guard subscribes to `before-tool` on `Bash` only.
- Codex trust hashes come from Codex's own review, never written by hand.

## Review Focus

1. **A host whose relay runtime or subscriber file is missing when the synced settings
   land.** A missing subscriber file refuses every Bash call there; a missing relay.js
   silently disables the guard. Task 4's preflight checks both on every host, and
   `--host europa` runs it there.
2. **Live settings that drift between preparation and the window** (a model pick written
   into settings, a hook added by other work). Task 4's `verify` compares only `hooks`
   and `statusLine` with the reviewed image and fails on any difference, naming it.
3. **Codex hooks left untrusted after the apply.** Untrusted hooks do not run, so
   observation and the guard are silently off. The window's Codex smoke must observe a
   guard refusal in each home before trust is committed.
4. **Harness versions drifting from the guard evidence** (europa's 2.1.280; Claude
   auto-updates). Task 4's preflight fails when a host's `--version` differs from the
   evidence, and names the probe rerun or the update.
5. **A partial rollback after the familiar merge.** Restored native familiar entries
   need the old familiar, and relay observers need the new one. The runbook rolls back
   every applied harness, then reverts the merge; Task 6 rehearses that sequence.

---

### Task 1: Pin relay's runtime per host

**Files:**
- Create: `relay/package.json`, `relay/package-lock.json`, `relay/bin/relay`
- Modify: `justfile` (recipe `relay-install`), `links.toml` (`[required]`
  `"~/.local/bin/relay" = "relay/bin/relay"`), `AGENTS.md` Layout (one line on `relay/`)
- Test: `tools/test_relay_pin.py`

**Interfaces:**
- Produces: `RELAY_INSTALL_ROOT` (default `~/.local/share/relay`); the runtime path
  `$RELAY_INSTALL_ROOT/v0.1.1/node_modules/relay/bin/relay.js`; `relay/bin/relay ARGS…`
  execs `/usr/bin/node <that path> ARGS…`, exits 127 with
  `relay v0.1.1 is not installed: run just relay-install in the hq checkout` when absent.

- [ ] **Step 1: Write the failing tests** in `tools/test_relay_pin.py`, after
  `tools/test_pi_launcher.py`'s fake-install pattern:
  - `test_lock_pins_the_release_commit`: `package-lock.json`'s
    `packages["node_modules/relay"]["resolved"]` ends with
    `#4ceec5d2ad22b136b37ee360e7a4ed00949f28d9`, and `package.json`'s
    `dependencies.relay` is `git+https://github.com/khughitt/relay.git#v0.1.1`.
  - `test_launcher_runs_the_pinned_runtime`: a fake `relay.js` under a temp root prints
    its argv; `relay/bin/relay list --json` prints `list`, `--json`.
  - `test_launcher_refuses_a_missing_install`: exit 127 and the message above.
- [ ] **Step 2: Run** `uv run -q --with pytest pytest tools/test_relay_pin.py -q`.
  Expected: 3 failures (files absent).
- [ ] **Step 3: Create the pin.** `package.json` is `{"name":"hq-relay-pin","private":true,
  "dependencies":{"relay":"git+https://github.com/khughitt/relay.git#v0.1.1"}}`; generate the
  lock with `npm install --package-lock-only --ignore-scripts` in `relay/`. The version key
  for the install directory is the tag after `#`. Write `relay/bin/relay` (bash) and the
  `relay-install` recipe as `pi-install`'s twins: copy both files into `$dest`, then
  `npm ci --prefix "$dest" --ignore-scripts --no-fund --no-audit`.
- [ ] **Step 4: Run** the tests. Expected: 3 passed. Then `just test`: all pass.
- [ ] **Step 5: Install on titan** (inert): `just relay-install`, then
  `relay/bin/relay --version` prints `0.1.1`. Do not run `just link --apply` from the
  worktree; Task 4 applies the `~/.local/bin/relay` link from main.
- [ ] **Step 6: Commit** `feat(relay): pin the relay v0.1.1 runtime per host`.

### Task 2: Track the subscriber config

**Files:**
- Create: `relay/subscribers.template.json`
- Modify: `justfile` (recipe `relay-subscribers`)
- Test: `tools/test_relay_subscribers.py`

**Interfaces:**
- Consumes: Task 1's runtime path.
- Produces: `just relay-subscribers` renders `@HOME@` to `$HOME` and installs the result
  at `~/.config/relay/subscribers.json` (directory 0700, file 0600), refusing to
  overwrite a different existing file unless `FORCE=1`; the rendered file is what every
  hook entry's `--subscribers` names.

The template holds exactly three subscribers (familiar's `setup relay` output without
`familiar-opencode`, which waits on relay-d0a8df, plus the ops guard):

| name | role | harnesses | kinds | tools | argv | timeoutMs |
| --- | --- | --- | --- | --- | --- | --- |
| `ops-guard` | guard | claude-code, codex | before-tool | Bash | `/usr/bin/python3`, `@HOME@/d/ops/hooks/relay-guard` | 30000 |
| `familiar` | observer | claude-code, codex | session-start, prompt, before-tool, activity, idle, needs-input, needs-approval, turn-end, turn-error, reconcile | – | `@HOME@/d/familiar/bin/familiar`, `observe` | 2000 |
| `familiar-teardown` | observer | claude-code, codex | session-end | – | as above | 200 |

- [ ] **Step 1: Write the failing tests:** `test_template_renders_home` (rendering with
  `HOME=/h` yields argv `/h/d/ops/hooks/relay-guard` and `/h/d/familiar/bin/familiar`, no `@HOME@`
  left); `test_template_matches_the_table` (names, roles, kinds, tools, timeouts as above);
  `test_recipe_installs_private_modes` (recipe run with a temp `HOME`: dir 0700, file 0600);
  `test_recipe_refuses_a_different_file` (existing different file: nonzero exit, file unchanged).
- [ ] **Step 2: Run** `uv run -q --with pytest pytest tools/test_relay_subscribers.py -q`. Expected: 4 failures.
- [ ] **Step 3: Write the template and the recipe** (`sed "s|@HOME@|$HOME|g"`, `install -d -m 700`,
  `install -m 600`, `cmp -s` before refusing).
- [ ] **Step 4: Run** the tests, then `just test`. Expected: all pass.
- [ ] **Step 5: Validate against relay itself** (budgets for every mapped event):
  `just relay-subscribers` on titan, then a disposable copy
  `cp claude/settings.json "$T/settings.json"` and
  `relay/bin/relay install --harness claude-code --subscribers ~/.config/relay/subscribers.json --target "$T/settings.json" --retire familiar --node /usr/bin/node --json`
  (no `--apply`; `--evidence` comes in Task 3, so this run must refuse only for the
  guard's missing evidence: any other refusal, such as `INVALID_CONFIG` or a budget
  error, is a template defect). Repeat for `--harness codex` against a copy of `codex/hooks.json`.
- [ ] **Step 6: Commit** `feat(relay): track the host subscriber config`.

### Task 3: Re-probe the ops guard at v0.1.1 on the installed harnesses (ops)

Work in an ops worktree `.worktrees/relay-guard-v011`; this step's hq task tracks it,
and the ops commit message names what it records. The probe needs a clean relay checkout: add a
detached relay worktree at the tag, `git -C <relay> worktree add --detach
.worktrees/v0.1.1 v0.1.1`, and `npm ci` there.

**Files (ops):**
- Modify: `docs/runbooks/relay-guard-evidence-claude-code.json`,
  `docs/runbooks/relay-guard-evidence-codex.json`, `docs/runbooks/relay-guard-probes.md`
  ("Current evidence" section).

- [ ] **Step 1: Record versions:** `claude --version`, `codex --version`; both must be the
  versions installed on titan at the start of the run.
- [ ] **Step 2: Run the probes** per the ops runbook, once per harness:
  `python3 bin/relay-guard-probe --harness claude-code --relay <relay-wt>/bin/relay.js --guard "$PWD/hooks/relay-guard" --out "$OUT"`,
  then `--harness codex`. Expected: allow, deny and context `passed: true`, and the
  evidence `version` equal to Step 1's.
- [ ] **Step 3: Copy** each `evidence.json` over the runbook's file; update the runbook's
  current-evidence paragraph (date, versions, relay `4ceec5d`, latencies); keep the
  pending code-mode and unproven-surface lines.
- [ ] **Step 4: Check acceptance:** Task 2 Step 5's two plan runs with
  `--evidence <ops>/docs/runbooks/relay-guard-evidence-<harness>.json` now exit 0 and
  print a plan.
- [ ] **Step 5: Commit in ops** `docs(runbooks): relay guard evidence at relay v0.1.1`;
  merge to ops main locally (personal checkout, documentation only); remove the ops and
  relay worktrees per the global rules.

### Task 4: `tools/relay-cutover`: preflight, native-guard removal, verify

**Files:**
- Create: `tools/relay-cutover`
- Test: `tools/test_relay_cutover.py`

**Interfaces:**
- Consumes: Task 1's runtime path and launcher, Task 2's rendered subscriber file, Task
  3's evidence files (`~/d/ops/docs/runbooks/relay-guard-evidence-<harness>.json`).
- Produces, all exiting 0 on success and 1 with one `relay-cutover: <check>: <why>` line
  per failure:
  - `relay-cutover preflight --harness {claude-code,codex} [--host HOST]`: checks
    `no-live` (no process of the harness: `comm` `claude`/`codex`, or an executable under
    `~/.local/share/claude/versions/`), `runtime` (pinned relay.js exists and
    `/usr/bin/node relay.js --version` is `0.1.1`), `subscribers` (installed file equals
    the rendered template byte for byte, modes 0700/0600), `evidence` (harness
    `--version` equals the evidence file's `version`; on a host without the harness it
    reports `absent` and passes). `--host` re-runs the same checks there with
    `ssh -4 -o BatchMode=yes HOST ~/d/hq/tools/relay-cutover preflight --harness H`.
  - `relay-cutover retire-native-guard --target FILE --backup DIR`: writes
    `DIR/<basename>.before-guard` (exact bytes, mode kept), then atomically removes the one
    PreToolUse group whose hooks are exactly `~/d/ops/hooks/claude-pretooluse`; refuses
    when that group is absent, appears twice, or shares its group with another hook;
    refuses a symlinked target.
  - `relay-cutover verify --target FILE --expect FILE`: compares `hooks` and `statusLine`
    of both JSON files; on difference prints a unified diff of the two canonical
    (`sort_keys`, indent 2) renderings.

- [ ] **Step 1: Write the failing tests** with fixtures copied from today's
  `claude/settings.json` and `codex/hooks.json` shapes and an injected process list:
  `test_no_live_flags_claude_by_comm_and_version_exe`, `test_no_live_passes_on_unrelated`,
  `test_runtime_reports_missing_relay`, `test_subscribers_reports_mode_0644`,
  `test_subscribers_reports_content_drift`, `test_evidence_reports_version_mismatch`
  (expects the message to name both versions and "rerun the ops relay-guard probe or
  update the harness"), `test_evidence_absent_harness_passes`,
  `test_retire_removes_only_the_native_guard_group` (every other group byte-equal after a
  `json` round trip), `test_retire_writes_exact_before_image`,
  `test_retire_refuses_absent_duplicate_shared_and_symlink`,
  `test_verify_ignores_model_and_effort_keys`, `test_verify_diff_names_the_changed_event`.
- [ ] **Step 2: Run** `uv run -q --with pytest pytest tools/test_relay_cutover.py -q`. Expected: all fail.
- [ ] **Step 3: Implement** in the style of `tools/rename-cutover` (`Stop` exception, `run`,
  argparse subcommands); process rows from `/proc/*/comm` and `/proc/*/exe`, injectable
  through a module function the tests replace. Write JSON with `indent=2` and a trailing
  newline, matching relay's installer, so later installs diff cleanly.
- [ ] **Step 4: Run** the tests, then `just test`. Expected: all pass.
- [ ] **Step 5: Pilot on titan:** `tools/relay-cutover preflight --harness claude-code`
  and `--harness codex`. Expected: only `no-live` fails, because this session is live.
  Read every line.
- [ ] **Step 6: Commit** `feat(tools): relay-cutover preflight, native guard removal and verify`.
- [ ] **Step 7: Land the inert prefix and prepare both hosts.** europa sees only what is
  on hq main (the worktree is titan-local storage). Merge this branch as it stands
  (Tasks 1, 2 and 4 plus this plan; no settings change) into hq main locally with
  `--no-ff`. Then on titan and, over `ssh -4 -o BatchMode=yes europa`, on europa:
  `just relay-install`, `just relay-subscribers`, `just link --apply` (adds only
  `~/.local/bin/relay`; read `just link` first), and `relay --version` prints `0.1.1`.
  Then `preflight --harness claude-code --host europa`. Expected: `evidence` fails while
  europa's Claude is older than the evidence (the runbook's §0 has the operator update
  it); everything else but `no-live` passes.

### Task 5: Prepare the reviewed settings images

**Files:**
- Modify: `claude/settings.json`, `codex/hooks.json`, `codex/hooks.work.json`,
  `tools/test_claim_guard_wiring.py`
- Create: `tools/test_relay_wiring.py`
- Untracked image: `$CUTOVER/claude-work.after.json`, where
  `CUTOVER=~/.local/state/hq/relay-cutover` (0700, host-local, titan)

**Interfaces:**
- Consumes: Task 4's `retire-native-guard`; Task 1–3's runtime, subscribers, evidence.
- Produces: the three committed after-images and the work image that the window's
  `verify` compares against.

- [ ] **Step 1: Write the failing tests.** `tools/test_relay_wiring.py` parses each hook
  command with `shlex.split`. A relay command has argv `[/usr/bin/node,
  <…>/.local/share/relay/v0.1.1/node_modules/relay/bin/relay.js, hook, --harness, H,
  --outer-ms, N, --subscribers, <…>/.config/relay/subscribers.json, EVENT]`, with the
  version segment read from `relay/package.json`.
  - `test_claude_relay_events`: exactly one relay entry for each of SessionStart
    (`startup|resume`), UserPromptSubmit, PreToolUse (`*`), Notification (`idle_prompt`),
    Notification (`permission_prompt`), Stop, StopFailure, SessionEnd; `--outer-ms` 600000
    and `timeout` 600, except SessionEnd 60000 and 60.
  - `test_codex_relay_events` for both Codex files: SessionStart, SubagentStart,
    UserPromptSubmit, PreToolUse (`*`), PermissionRequest, Stop, SubagentStop at 600000/600;
    SessionEnd 3000/3.
  - `test_no_familiar_hook_or_native_guard`: no command contains `familiar hook` or
    `claude-pretooluse` in any of the three files.
  - `test_native_entries_kept_in_order`: per event, the non-relay commands equal, for
    Claude: SessionStart `[claude-sessionstart, claude-provenance, claude-profile,
    capture-notice]`, PostModelSwitch `[claude-provenance]`, Stop `[claim-guard --harness
    claude-code, harness-state-refresh]`, PostToolUse and PostToolUseFailure
    `[claude-posttooluse]`; Codex main: SessionStart `[claude-profile, capture-notice]`,
    SubagentStop and Stop as `test_claim_guard_wiring.py` says; Codex work: the same
    without `capture-notice` (full `~/d/…` strings in the test).
  - `test_statusline_unchanged`: `~/d/familiar/bin/familiar statusline`, refreshInterval 2.
  - In `tools/test_claim_guard_wiring.py`, the Stop `others` become
    `['~/.local/bin/harness-state-refresh', <the relay Stop entry>]`, matched with the
    shared relay-command parser.
- [ ] **Step 2: Run** `uv run -q --with pytest pytest tools/test_relay_wiring.py tools/test_claim_guard_wiring.py -q`.
  Expected: the new tests fail on today's files.
- [ ] **Step 3: Generate the images in the worktree** (real files, not the home links),
  with `R=relay/bin/relay`, `S=~/.config/relay/subscribers.json` and
  `E=~/d/ops/docs/runbooks/relay-guard-evidence-<harness>.json`:
  1. `tools/relay-cutover retire-native-guard --target claude/settings.json --backup "$CUTOVER/prep"`
  2. `$R install --harness claude-code --subscribers "$S" --target claude/settings.json --retire familiar --evidence "$E" --node /usr/bin/node --apply --artifact "$CUTOVER/prep/claude.json"`
  3. The same Codex install for `codex/hooks.json` and for `codex/hooks.work.json`
     (artifacts `codex.json`, `codex-work.json`).
  4. The work variant from a copy:
     `cp -p <main>/local/claude/settings.work.json "$CUTOVER/claude-work.after.json"`, then steps 1–2 on that copy.
  Read every diff (`git diff`, and `diff` of the work copy against its original); the
  only changes are the familiar and native-guard removals and the appended relay entries.
- [ ] **Step 4: Run** the wiring tests, then `just test`. Expected: all pass. The
  untracked work image has no test; Step 3's diff reading and the window's `verify`
  cover it.
- [ ] **Step 5: Commit** `feat(hooks): relay v0.1.1 replaces familiar and the native ops guard`.
  This commit changes nothing live: the home links resolve to main's files.

### Task 6: Runbook and rehearsal

**Files:**
- Create: `docs/runbooks/relay-cutover.md`
- Modify: `README.md` (link to the runbook beside the pi section)

**Interfaces:**
- Consumes: everything above. Produces the operator procedure Task 7 runs.

The runbook lists the exact staged files with their before sha256 (taken at writing and
re-taken by the operator), command paths, the relay pin and familiar's merge source
(`feat/relay-identity` at its tip sha), every relay writer with the relay it runs
(hook entries: the pinned runtime; `familiar observe` and `familiar reap`: familiar's
own `node_modules/relay`; both v0.1.1, as relay's worker-rows activation requires; tasks'
relay identity is off on both hosts), and this budget table (relay's derivation, which
`relay install` re-validates):

| Harness/event | outer H | subscriber budget | matching worst case |
| --- | --- | --- | --- |
| Claude, Codex PreToolUse | 600 s | 37000 ms | ops-guard 30000 + familiar 2000 = 32000 |
| other mapped events | 600 s | 37000 ms | familiar 2000 |
| Claude SessionEnd | 60 s | 37000 ms | familiar-teardown 200 |
| Codex SessionEnd | 3 s | 800 ms | familiar-teardown 200 |

Ordered procedure (the runbook's numbered sections, each with its expected output):

0. *Agent, before the window:* both hosts pass `preflight` except `no-live`; record
   familiar main's sha (`PRE_FAMILIAR`); copy `~/.local/state/familiar` to
   `$CUTOVER/familiar-state` on each host; confirm the Mac does not link its Claude
   or Codex settings into the synced hq checkout (the open question below). *Operator:*
   `claude update` on any host whose `evidence` check fails, or the agent reruns Task 3.
1. *Operator, plain shell on titan:* end every Claude and Codex session on titan and
   europa; `tools/quiesce-timers record --state "$CUTOVER/timers.json" familiar-reap.timer`,
   `stop`, `wait` (and the same on europa over ssh); `preflight` on both hosts, now all green.
2. Familiar: `git -C ~/d/familiar merge --no-ff feat/relay-identity`, `npm ci` there,
   `~/d/familiar/bin/familiar observe --help` exits 0; restart `familiar-niri watch` and
   the `niri-desktop` quickshell (kill the recorded pids, start the two niri
   `spawn-sh-at-startup` commands from a shell).
3. Claude, both homes: `retire-native-guard`, `relay install …` without `--apply`
   (its JSON plan must match the prepared image: write `jq -r '.changes[0].after'` to
   `$CUTOVER/live/<name>.plan.json` and `verify` it against the image),
   then `--apply --artifact "$CUTOVER/live/claude.json"` (and `claude-work.json`);
   `verify --expect` the committed image / work image. Smoke on titan (below); on europa,
   the operator opens one session, runs the denial step and exits, and the agent reads
   `relay list --json` there over ssh.
4. Codex, both homes: install plan, apply with artifacts, `verify`; start `codex`, approve
   the hook review; smoke; repeat a short smoke (start, denial, exit) in the work home.
5. `tools/quiesce-timers restore` on both hosts; `systemctl --user start familiar-reap.service`;
   journal shows success; the abrupt-death row from the smoke is gone from `relay list`.
6. Hand back to the agent (Task 8).

Smoke per harness, in a scratch git repo (`mktemp -d`, `git init`), each step with the
expected `relay list --json` state: start (`idle`) · prompt and `touch` an allow marker
(`working`, marker exists) · the probe's attribution commit (refused with the ops reason,
no commit) · a permission prompt (`needs-approval`) · turn end (`done`) · idle prompt
after 60 s, Claude only (`needs-input`) · `/exit` (row removed, familiar intent cleared)
· a second session killed with `kill -9` (row stays; `relay reap` removes it) ·
projection recovery (move `intent.json` aside during a live session; `familiar reap`
restores the live agent's entry).

Rollback, any failure from step 2 on, with sessions ended: for each applied harness in
reverse, `relay rollback --artifact …`; for Claude, `cmp` with the post-guard snapshot,
then `cp -p` the `.before-guard` image back; then `git -C ~/d/familiar revert -m 1 --no-edit
<merge>` and `npm ci`; restart the familiar surfaces; `quiesce-timers restore`; fresh
sessions. `~/.local/state/relay` is left in place, unused. A later retry re-merges by
reverting the revert.

- [ ] **Step 1: Write the runbook** as above, with literal commands and expected output for
  every step.
- [ ] **Step 2: Rehearse on disposable copies on titan:** copy the four live targets into
  `$CUTOVER/rehearsal/`, run steps 3–4's commands against the copies (not the window's
  stop, merge or trust steps), `verify` each, then the full rollback; every restored file
  must `cmp` equal to its original. Settings files are JSON; no JSONC target is in
  scope, so no JSONC rehearsal.
- [ ] **Step 3: Rehearse the familiar merge and revert** in a throwaway clone
  (`git clone ~/d/familiar "$T/fam"`): `merge --no-ff feat/relay-identity` is clean, and
  after `revert -m 1 --no-edit HEAD` the tree equals `PRE_FAMILIAR`'s
  (`git diff --quiet PRE_FAMILIAR HEAD`). Record both rehearsals' results in the runbook.
- [ ] **Step 4: Preflight both hosts** (Task 4's commands): everything green except
  `no-live`, and `evidence` on europa until its Claude is updated (runbook §0).
- [ ] **Step 5: Commit** `docs(runbooks): relay operator cutover`.

### Task 7: Operator window (gate: the user runs it)

- [ ] **Step 1:** `tasks park hq-539508 "operator runs docs/runbooks/relay-cutover.md §1–5 from a plain shell" --waiting-on user --reason approval`,
  naming the expected duration (about 45 minutes) and that it ends every Claude and
  Codex session on both hosts, including the agent's own.
- [ ] **Step 2:** on resume, read the operator's report and the live state:
  `relay list --json` on both hosts, `verify` for the four targets, the journal of
  `familiar-reap.service`. A failed step means rollback was run or must be; record which.

### Task 8: Close-out

- [ ] **Step 1: Commit on hq main** the live files, which now equal the branch images in
  `hooks`/`statusLine`: `claude/settings.json`, `codex/hooks.json`, `codex/hooks.work.json`,
  plus only the `[hooks.state]` trust hunks Codex wrote in `codex/config.toml` (stage
  them with `git apply --cached` of the selected hunks, leaving unrelated pending trust
  changes as they were). Then merge `feat/relay-cutover` locally; identical changes merge
  cleanly, and any overlapping hunk resolves to main's live bytes.
- [ ] **Step 2: File the ops follow-up** "Retire the native claude-pretooluse entry point
  now that no settings install it" (`--project ops --source hq-539508`): move `check()`
  into an ordinary module that `relay-guard` imports; update ops README, the `justfile`
  `py_compile` list and tests. Retirement is ops code with its own review, so it is filed
  rather than done on this branch.
- [ ] **Step 3: Reconcile the release goal:** note on relay-1231bf what is cut over
  (Linux titan/europa, Claude and Codex, guard on Bash) and what awaits (OpenCode
  relay-d0a8df, Darwin relay-848c0f with fam-f088b1, Codex code-mode ops-daf2cd);
  `tasks done hq-539508` with the evidence summary; remove the worktree per the
  global rules (ignored files, `tt-report`, no host pointer resolves into it).

## Open question for the review

The Mac (Darwin) portion waits on relay-848c0f. If the Mac's `~/.claude/settings.json`
or `~/.codex/hooks.json` links into this synced hq checkout, Task 7 step 3 would cut it
over too, with `/home/keith` paths that do not exist there. The plan assumes it does
not; please confirm, or the plan adds a Darwin-safe variant before the window.
