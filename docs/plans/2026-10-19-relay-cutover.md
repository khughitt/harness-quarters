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
- `relay install` refuses symlinked targets and relative paths, so every target below is
  the absolute path of the real hq file. Its Codex installer also requires the file to be
  named `hooks.json`, which `codex/hooks.work.json` is not (Task 5 moves it).
- Familiar's `node_modules` is Dropbox-ignored (`user.com.dropbox.ignored`): each host
  has its own install, and syncing familiar's source does not install its dependencies.
  europa's has no `relay` today.
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
  tracked, so the tracked/untracked split differs from the brief's. The Codex work
  home's file moves to `codex/work/hooks.json`, the only name relay's installer accepts.
- The work variant already carries the native ops guard, so migrating it to relay is
  a replacement rather than the "separate explicit addition" the brief anticipated.
- OpenCode is installed but not cut over: relay's plugin cannot load on OpenCode v2
  (relay-d0a8df), and familiar's server plugin is already disabled there.
- Retiring the native ops entry point is filed in ops (Task 9) instead of being done here.
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
  Tasks 1, 2 and 5 (new files nothing references yet, and the content-identical repoint
  of `~/.codex-work/hooks.json`).
- The operator applies from an ordinary shell with no session of the target harness
  on either host; agents prepare and check, never apply from inside a harness.
- One writer per harness: `--retire familiar` in the same apply that adds relay. No
  dual writing, no import of familiar's `agents.json`, no compatibility layer.
- Keep old state untouched until verified: `~/.local/state/familiar` is copied aside
  before the window and not deleted by this plan.
- Rollback restores the captured settings and familiar's revision and starts fresh
  sessions; it never merges registries. Familiar is one shared checkout, so rollback
  covers every harness already touched. It fetches nothing: each host keeps a copy of
  its pre-merge familiar `node_modules`, and source comes back by `git revert`.
- Every live edit is preceded by the same sequence on copies (a dry run), and every
  touched target, guard removal included, has before- and after-images that `restore`
  reads, whether or not relay applied.
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
   every touched harness, then reverts the merge and restores each host's saved
   dependencies; Task 7 rehearses that sequence offline.
6. **A failure between guard removal and relay's apply** (a failed plan check, an
   installer refusal): no relay artifact exists, yet the native guard is gone. Task 4's
   `restore` puts the guard back from its own images; Task 7 rehearses failure right
   after removal and right after plan verification.

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
  error, is a template defect). `T` is an absolute temporary directory (`T=$(mktemp -d)`).
  Repeat for `--harness codex` against `cp codex/hooks.json "$T/hooks.json"` (the Codex
  installer accepts only that file name).
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

### Task 4: `tools/relay-cutover`: preflight, guard removal, restore, verify

**Files:**
- Create: `tools/relay-cutover`
- Test: `tools/test_relay_cutover.py`

**Interfaces:**
- Consumes: Task 1's runtime path and launcher, Task 2's rendered subscriber file, Task
  3's evidence files (`~/d/ops/docs/runbooks/relay-guard-evidence-<harness>.json`).
- Produces, all exiting 0 on success and 1 with one `relay-cutover: <check>: <why>` line
  per failure. Every `--target` must be absolute and not a symlink.
  - `relay-cutover preflight --harness {claude-code,codex} [--host HOST]`: checks
    `no-live` (no process of the harness: `comm` `claude`/`codex`, or an executable under
    `~/.local/share/claude/versions/`), `runtime` (pinned relay.js exists and
    `/usr/bin/node relay.js --version` is `0.1.1`), `subscribers` (installed file equals
    the rendered template byte for byte, modes 0700/0600), `evidence` (harness
    `--version` equals the evidence file's `version`; on a host without the harness it
    reports `absent` and passes). `--host` re-runs the same checks there with
    `ssh -4 -o BatchMode=yes HOST ~/d/hq/tools/relay-cutover preflight --harness H`.
  - `relay-cutover familiar-source --head SHA [--host HOST]`: source readiness only, run
    before installing dependencies. `git --no-optional-locks -C ~/d/familiar rev-parse
    HEAD` equals SHA, and every file of SHA, `package-lock.json` included, matches the
    working tree. Git indexes are excluded from Dropbox sync, so a synced host's own index
    is stale and is never read or written: the comparison runs through an isolated index,
    `GIT_INDEX_FILE=$(mktemp)` (removed on exit), populated by `git read-tree SHA`, then
    `git diff --quiet SHA` under that index. `node_modules` is untracked and ignored.
    It never runs familiar.
  - `relay-cutover familiar-check --expect {relay,native} [--host HOST]`: dependency
    readiness, run after installing or restoring them. `relay`:
    `~/d/familiar/node_modules/relay/package.json` version is `0.1.1` and
    `~/d/familiar/bin/familiar observe --help` exits 0. `native`: no
    `node_modules/relay` and `familiar hook --help` exits 0.
  - `relay-cutover retire-native-guard --target FILE --backup DIR`: reads the target,
    computes the bytes without the one PreToolUse group whose hooks are exactly
    `~/d/ops/hooks/claude-pretooluse`, persists **both** `DIR/<name>.before-guard` (exact
    bytes, mode kept) and `DIR/<name>.after-guard` (each by temporary file, fsync and
    rename, then an fsync of DIR), and only then atomically replaces the target (temporary
    file in the target's directory, fsync, rename). `<name>` is the target's path with
    `/` replaced by `_`. Refuses, before writing anything, when that group is absent,
    appears twice, or shares its group with another hook, and when either image already
    exists. A failure while persisting the images leaves the target untouched; a
    failure after the replacement leaves a target `restore` recognises.
  - `relay-cutover restore --target FILE --backup DIR [--artifact FILE]`: returns the
    target to its pre-cutover bytes from whatever state a failure left it in, in order:
    (1) the artifact exists and the target equals its `after` for this path: run
    `relay/bin/relay rollback --artifact FILE`; (2) the target equals `.after-guard`:
    atomically write `.before-guard`'s bytes; (3) the target now equals `.before-guard`,
    or, with no guard images, the artifact's `before`: exit 0; otherwise stop with exit 1,
    writing nothing further, naming which image the bytes match (none, or which).
  - `relay-cutover verify --target FILE --expect FILE`: compares `hooks` and `statusLine`
    of both JSON files; on difference prints a unified diff of the two canonical
    (`sort_keys`, indent 2) renderings.

- [ ] **Step 1: Write the failing tests** with fixtures copied from today's
  `claude/settings.json` and `codex/hooks.json` shapes, an injected process list and a
  fake relay launcher (a script whose `rollback` writes the artifact's `before`):
  `test_no_live_flags_claude_by_comm_and_version_exe`, `test_no_live_passes_on_unrelated`,
  `test_runtime_reports_missing_relay`, `test_subscribers_reports_mode_0644`,
  `test_subscribers_reports_content_drift`, `test_evidence_reports_version_mismatch`
  (expects the message to name both versions and "rerun the ops relay-guard probe or
  update the harness"), `test_evidence_absent_harness_passes`,
  `test_familiar_source_head_and_working_tree` (HEAD mismatch and a modified tracked file
  each fail; untracked `node_modules` is ignored; familiar is never executed),
  `test_familiar_source_ignores_a_stale_live_index` (a repository whose index predates
  SHA, with HEAD and every new file synced: passes; the live index file is byte-identical
  afterwards; then a changed source file fails),
  `test_familiar_check_relay_and_native_sides`,
  `test_retire_removes_only_the_native_guard_group` (every other group equal after a
  `json` round trip), `test_retire_writes_exact_before_and_after_images`,
  `test_retire_persists_both_images_before_replacing` (an injected failure on the second
  image write leaves the target byte-identical; a rerun then refuses because an image
  exists), `test_retire_failure_after_replace_is_restorable` (an injected failure
  between the target's rename and the command's return: exit nonzero, then `restore`
  returns the target to the before-image),
  `test_retire_refuses_absent_duplicate_shared_symlink_relative_and_rerun`,
  `test_restore_after_guard_removal_only` (no artifact: target back to before-guard),
  `test_restore_after_relay_apply` (fake rollback runs, then the guard image is restored),
  `test_restore_after_failed_apply` (artifact written, target still at after-guard),
  `test_restore_without_guard_images` (Codex: artifact rollback alone),
  `test_restore_refuses_unknown_bytes_and_writes_nothing`,
  `test_verify_ignores_model_and_effort_keys`, `test_verify_diff_names_the_changed_event`.
- [ ] **Step 2: Run** `uv run -q --with pytest pytest tools/test_relay_cutover.py -q`. Expected: all fail.
- [ ] **Step 3: Implement** in the style of `tools/rename-cutover` (`Stop` exception, `run`,
  argparse subcommands); process rows from `/proc/*/comm` and `/proc/*/exe`, injectable
  through a module function the tests replace; the relay launcher path overridable by
  `RELAY_CUTOVER_RELAY` for the tests. Write JSON with `indent=2` and a trailing newline,
  matching relay's installer, so later installs diff cleanly.
- [ ] **Step 4: Run** the tests, then `just test`. Expected: all pass.
- [ ] **Step 5: Pilot on titan:** `tools/relay-cutover preflight --harness claude-code`,
  `--harness codex`, `familiar-source --head "$(git -C ~/d/familiar rev-parse HEAD)"` and
  `familiar-check --expect native`. Expected: only `no-live` fails,
  because this session is live. Read every line.
- [ ] **Step 6: Commit** `feat(tools): relay-cutover preflight, guard removal, restore and verify`.

### Task 5: Give the Codex work home a target the installer accepts, and prepare both hosts

relay's Codex installer accepts only a file named `hooks.json`. Move the work home's
hooks to `codex/work/hooks.json`, a content-identical rename. Codex keys hook trust by
the home path (`/home/keith/.codex-work/hooks.json:…`), so the move changes no trust.

**Files:**
- Move: `codex/hooks.work.json` → `codex/work/hooks.json`
- Modify: `links.toml` (`[harness.codex-work.links] "hooks.json" = "codex/work/hooks.json"`),
  `tools/test_claim_guard_wiring.py` (parametrize on the new path),
  `tools/test_capture_notice_wiring.py` (`test_codex_work_home_has_no_capture_notice`
  reads the new path), `README.md` (the two mentions at today's lines 183 and 314)

- [ ] **Step 1: Update the tests first:** `test_both_codex_homes_guard_root_and_worker`
  reads `codex/work/hooks.json` for `codex-work` and asserts the manifest maps it;
  `test_codex_work_home_has_no_capture_notice` reads the new path. Run
  `uv run -q --with pytest pytest tools/test_claim_guard_wiring.py tools/test_capture_notice_wiring.py -q`.
  Expected: both fail (`FileNotFoundError`, manifest mismatch).
- [ ] **Step 2: Move and remap:** `git mv`, the `links.toml` line, README. Run the tests,
  then `just test`. Expected: all pass. The manifest assertion is the worktree's check;
  `tools/harness-links` refuses to run outside the main checkout, so its preview and
  convergence check happen on main in Step 5.
- [ ] **Step 3: Commit** `refactor(codex): name the work home's hooks file hooks.json`.
- [ ] **Step 4: Land the inert prefix on main.** europa sees only hq main (the worktree is
  titan-local storage). Merge this branch as it stands (the plan, Tasks 1, 2, 4 and 5;
  the settings bytes are unchanged) into hq main locally with `--no-ff`. Main's
  `codex/config.toml` modification stays uncommitted and untouched.
- [ ] **Step 5: Prepare both hosts.** On titan and, over `ssh -4 -o BatchMode=yes europa`,
  on europa, from `~/d/hq` (main): `just link` previews exactly `~/.local/bin/relay` added
  and, on titan only, `~/.codex-work/hooks.json` repointed (anything else: stop); then
  `just link --apply`, and `just link-check` reports convergence; `just relay-install`,
  `just relay-subscribers`; `relay --version` prints `0.1.1`;
  `readlink -f ~/.codex-work/hooks.json` ends in `codex/work/hooks.json` on titan.
  The repoint changes no bytes Codex reads; start no Codex session to test it.
- [ ] **Step 6: Preflight both hosts:** `preflight --harness claude-code --host europa` and
  the titan runs. Expected: `evidence` fails on europa while its Claude is older than the
  evidence (the runbook's §0 has the operator update it); everything else but `no-live`
  passes.

### Task 6: Prepare the reviewed settings images

**Files:**
- Modify: `claude/settings.json`, `codex/hooks.json`, `codex/work/hooks.json`,
  `tools/test_claim_guard_wiring.py`
- Create: `tools/test_relay_wiring.py`
- Untracked image: `$CUTOVER/claude-work.after.json`, where
  `CUTOVER=~/.local/state/hq/relay-cutover` (0700, host-local, titan)

**Interfaces:**
- Consumes: Task 4's `retire-native-guard`; Tasks 1–3's runtime, subscribers, evidence.
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
  - In `tools/test_capture_notice_wiring.py`, `test_codex_appends_capture_notice_after_trusted_entries`
    expects SessionStart `['~/d/lore/hooks/claude-profile', COMMAND, <the relay
    SessionStart entry>]`, matched with the shared parser; its comment now says the
    cutover re-trusts every shifted index, so new entries still go last.
  - In `tools/test_claim_guard_wiring.py`, the Stop `others` become
    `['~/.local/bin/harness-state-refresh', <the relay Stop entry>]`, matched with the
    shared relay-command parser.
- [ ] **Step 2: Run** `uv run -q --with pytest pytest tools/test_relay_wiring.py tools/test_claim_guard_wiring.py tools/test_capture_notice_wiring.py -q`.
  Expected: the new tests fail on today's files.
- [ ] **Step 3: Generate the images in the worktree**, with absolute paths throughout:
  `W=$(pwd -P)` at the worktree root, `R=$W/relay/bin/relay`,
  `S=$HOME/.config/relay/subscribers.json`,
  `E=$HOME/d/ops/docs/runbooks/relay-guard-evidence-<harness>.json`:
  1. `"$W/tools/relay-cutover" retire-native-guard --target "$W/claude/settings.json" --backup "$CUTOVER/prep"`
  2. `"$R" install --harness claude-code --subscribers "$S" --target "$W/claude/settings.json" --retire familiar --evidence "$E" --node /usr/bin/node --apply --artifact "$CUTOVER/prep/claude.json"`
  3. The same Codex install for `"$W/codex/hooks.json"` and `"$W/codex/work/hooks.json"`
     (artifacts `codex.json`, `codex-work.json`).
  4. The work variant from a copy: `cp -p ~/d/hq/local/claude/settings.work.json
     "$CUTOVER/claude-work.after.json"`, then steps 1–2 with
     `--target "$CUTOVER/claude-work.after.json"` (artifact `claude-work.json`).
  Read every diff (`git diff`, and `diff` of the work copy against its original); the
  only changes are the familiar and native-guard removals and the appended relay entries.
- [ ] **Step 4: Run** the wiring tests, then `just test`. Expected: all pass. The
  untracked work image has no test; Step 3's diff reading and the window's `verify`
  cover it.
- [ ] **Step 5: Commit** `feat(hooks): relay v0.1.1 replaces familiar and the native ops guard`.
  This commit changes nothing live: the home links resolve to main's files.

### Task 7: Runbook and rehearsal

**Files:**
- Create: `docs/runbooks/relay-cutover.md`
- Modify: `README.md` (link to the runbook beside the pi section)

**Interfaces:**
- Consumes: everything above. Produces the operator procedure Task 8 runs.

The runbook lists the exact staged files with their before sha256 (taken at writing and
re-taken by the operator), command paths, the relay pin, familiar's merge source as a
commit (`FEATURE_TIP`, the `feat/relay-identity` tip recorded at writing; the window
merges that sha, never the moving branch name), every relay writer with the relay it
runs (hook entries: the pinned runtime; `familiar observe` and `familiar reap`: each
host's own familiar `node_modules/relay`; both v0.1.1, as relay's worker-rows activation
requires; tasks' relay identity is off on both hosts), and this budget table (relay's
derivation, which `relay install` re-validates):

| Harness/event | outer H | subscriber budget | matching worst case |
| --- | --- | --- | --- |
| Claude, Codex PreToolUse | 600 s | 37000 ms | ops-guard 30000 + familiar 2000 = 32000 |
| other mapped events | 600 s | 37000 ms | familiar 2000 |
| Claude SessionEnd | 60 s | 37000 ms | familiar-teardown 200 |
| Codex SessionEnd | 3 s | 800 ms | familiar-teardown 200 |

Targets, all absolute: `~/d/hq/claude/settings.json`, `~/d/hq/local/claude/settings.work.json`,
`~/d/hq/codex/hooks.json`, `~/d/hq/codex/work/hooks.json` (resolved with `realpath` once,
and the resolved path used everywhere so `restore` and relay's artifact agree).

Ordered procedure (the runbook's numbered sections, each with its expected output):

0. *Agent, before the window:* both hosts pass `preflight` except `no-live`, and
   `familiar-source --head "$PRE_FAMILIAR"` and `familiar-check --expect native`; record
   `PRE_FAMILIAR` (familiar main's sha) and
   `FEATURE_TIP`; on each host copy `~/.local/state/familiar` to `$CUTOVER/familiar-state`
   and `cp -a ~/d/familiar/node_modules "$CUTOVER/familiar-node_modules.pre"` (the
   retained runnable install: with the reverted source, it runs the old familiar without
   fetching). *Operator:* `claude update` on any host whose
   `evidence` check fails, or the agent reruns Task 3.
1. *Operator, plain shell on titan:* end every Claude and Codex session on titan and
   europa; `tools/quiesce-timers record --state "$CUTOVER/timers.json" familiar-reap.timer`,
   `stop`, `wait` (and the same on europa over ssh); `preflight` on both hosts, now all green.
2. Familiar, both hosts: on titan, `git -C ~/d/familiar merge --no-ff "$FEATURE_TIP"` and
   record `MERGE`; then on **each** host: `familiar-source --head "$MERGE"` until it
   passes (europa waits for Dropbox; source only, nothing runs familiar), then `npm ci`
   in `~/d/familiar`, then `familiar-check --expect relay`; restart that host's `familiar-niri
   watch` and `niri-desktop` quickshell (kill the recorded pids, start the two niri
   `spawn-sh-at-startup` commands from a shell).
3. Claude, both homes, first as a dry run on copies in `$CUTOVER/dry/` (retire, plan,
   `verify` the plan against the image: `jq -r '.changes[0].after'` into a file), then
   live: `retire-native-guard --backup "$CUTOVER/live"`, `relay install …` without
   `--apply` and `verify` its plan, then `--apply --artifact "$CUTOVER/live/claude.json"`
   (and `claude-work.json`); `verify --expect` the committed image / work image. Smoke on
   titan (below); on europa, the operator opens one session, runs the denial step and
   exits, and the agent reads `relay list --json` there over ssh.
4. Codex, both homes: the same dry run, then plan, apply with artifacts, `verify`; start
   `codex`, approve the hook review; smoke; repeat a short smoke (start, denial, exit) in
   the work home.
5. `tools/quiesce-timers restore` on both hosts; `systemctl --user start familiar-reap.service`;
   journal shows success; the abrupt-death row from the smoke is gone from `relay list`.
6. Hand back to the agent (Task 9).

Smoke per harness, in a scratch git repo (`mktemp -d`, `git init`), each step with the
expected `relay list --json` state: start (`idle`) · prompt and `touch` an allow marker
(`working`, marker exists) · the probe's attribution commit (refused with the ops reason,
no commit) · a permission prompt (`needs-approval`) · turn end (`done`) · idle prompt
after 60 s, Claude only (`needs-input`) · `/exit` (row removed, familiar intent cleared)
· a second session killed with `kill -9` (row stays; `relay reap` removes it) ·
projection recovery (move `intent.json` aside during a live session; `familiar reap`
restores the live agent's entry).

Rollback, any failure from step 2 on, with sessions ended. Settings: for **every**
target that section 3 or 4 touched, in reverse order, `relay-cutover restore --target T
--backup "$CUTOVER/live" [--artifact A]` (the artifact only when it exists); `restore`
covers a guard removed with no relay apply. Familiar, when step 2 ran: on titan
`git -C ~/d/familiar revert -m 1 --no-edit "$MERGE"` and record `REVERT`; on each host,
once `familiar-source --head "$REVERT"` passes, `rm -rf ~/d/familiar/node_modules &&
cp -a "$CUTOVER/familiar-node_modules.pre" ~/d/familiar/node_modules` (no npm, no
network), then `familiar-check --expect native`;
restart that host's familiar surfaces. Then `quiesce-timers restore` on both hosts and
fresh sessions. `~/.local/state/relay` is left in place, unused. A later retry re-merges
by reverting the revert.

- [ ] **Step 1: Write the runbook** as above, with literal commands and expected output for
  every step.
- [ ] **Step 2: Rehearse settings on disposable copies on titan:** copy the four live
  targets into `$CUTOVER/rehearsal/`, and run section 3–4's commands and the rollback
  against the copies, three times: (a) stop right after `retire-native-guard`,
  (b) stop right after plan verification, (c) complete every apply and `verify`. After
  each, `restore` every touched copy, and every copy must `cmp` equal to its original.
  Settings files are JSON; no JSONC target is in scope, so no JSONC rehearsal.
- [ ] **Step 3: Rehearse familiar's merge and offline rollback** in a throwaway clone:
  `git clone ~/d/familiar "$T/fam"`, `git -C "$T/fam" switch --detach "$PRE_FAMILIAR"`,
  `cp -a ~/d/familiar/node_modules "$T/fam.nm.pre"`; `merge --no-ff "$FEATURE_TIP"` is
  clean; `npm ci` there and `bin/familiar observe --help` exits 0; then
  `revert -m 1 --no-edit HEAD`, restore `node_modules` from `$T/fam.nm.pre` inside
  `unshare -rn` (no network), and `bin/familiar hook --help` exits 0;
  `git diff --quiet "$PRE_FAMILIAR" HEAD`. Record both rehearsals' results in the runbook.
- [ ] **Step 4: Preflight both hosts** (Task 4's commands): everything green except
  `no-live`, and `evidence` on europa until its Claude is updated (runbook §0).
- [ ] **Step 5: Commit** `docs(runbooks): relay operator cutover`.

### Task 8: Operator window (gate: the user runs it)

- [ ] **Step 1:** `tasks park hq-539508 "operator runs docs/runbooks/relay-cutover.md §1–5 from a plain shell" --waiting-on user --reason approval`,
  naming the expected duration (about 45 minutes) and that it ends every Claude and
  Codex session on both hosts, including the agent's own.
- [ ] **Step 2:** on resume, read the operator's report and the live state:
  `relay list --json` and `familiar-check` on both hosts, `verify` for the four targets,
  the journal of `familiar-reap.service`. A failed step means rollback was run or must
  be; record which.

### Task 9: Close-out

- [ ] **Step 1: Bring the reviewed tests to main with the live settings.** On hq main,
  `git checkout feat/relay-cutover -- tools/test_relay_wiring.py tools/test_claim_guard_wiring.py tools/test_capture_notice_wiring.py`;
  `just test` passes against the live settings (it would fail on main's old wiring test).
  Commit those tests with `claude/settings.json`, `codex/hooks.json`,
  `codex/work/hooks.json` and only the `[hooks.state]` trust hunks Codex wrote in
  `codex/config.toml` (staged with `git apply --cached` of the selected hunks; unrelated
  pending trust changes stay as they were). Then merge `feat/relay-cutover` locally;
  identical changes merge cleanly, and any overlapping hunk resolves to main's live bytes.
- [ ] **Step 2: File the ops follow-up** "Retire the native claude-pretooluse entry point
  now that no settings install it" (`--project ops --source hq-539508`): move `check()`
  into an ordinary module that `relay-guard` imports; update ops README, the `justfile`
  `py_compile` list and tests. Retirement is ops code with its own review, so it is filed
  rather than done on this branch.
- [ ] **Step 3: Reconcile the release goal:** note on relay-1231bf what is cut over
  (Linux titan/europa, Claude and Codex, guard on Bash) and what awaits (OpenCode
  relay-d0a8df, Darwin relay-848c0f with fam-f088b1, Codex code-mode ops-daf2cd);
  `tasks done hq-539508` with the evidence summary; remove the worktree per the
  global rules (ignored files, `tt-report`, no host pointer resolves into it). The
  `$CUTOVER` directories and saved `node_modules` copies stay until you release them.

## Resolved question

The Mac does not link its Claude or Codex settings into the synced hq checkout (the user,
2026-10-19), so the window leaves it alone; its cutover waits on relay-848c0f.
