# Relay operator cutover

Prepared 2026-10-19. This is the Task 8 operator window; preparation and rehearsals
have **not** activated relay. Run the numbered sections in order, from ordinary
shells on Titan and Europa, with an observer shell for the smoke checks. Any failed
check stops the window and invokes rollback. Do not run the live commands inside
Claude or Codex. Desktop restarts below need the operator's permission at that moment.

Claude's personal and work homes run on both hosts. Codex's two homes run only on
Titan. The four settings targets and familiar source are shared through Dropbox:
**edit each settings target once on Titan**, then wait for and verify Europa's copy.
Dependencies, registries, backups, and private expected images are host-local.
Nothing here repoints a home, launcher, service, or config include into a worktree.
Keep `.worktrees/relay-cutover/` until Task 9 is complete.

## Pins, targets, and writers

Use these immutable familiar commits, never the moving feature branch:

```bash
PRE_FAMILIAR=00f4899ae523d613d21f44bfc2c456aac67f8e5f
FEATURE_TIP=a16f4daa59b04e32f1010764d6f94401ca4eed8b
```

The relay dependency is `git+https://github.com/khughitt/relay.git#v0.1.1`, release
commit `4ceec5d2ad22b136b37ee360e7a4ed00949f28d9`. Hook commands use `/usr/bin/node`.
Every writer must use v0.1.1 before hooks activate worker rows:

| Writer on each host | Runtime |
| --- | --- |
| Installed hook entries | `$HOME/.local/share/relay/v0.1.1/node_modules/relay/bin/relay.js` |
| `familiar observe` | That host's `$HOME/d/familiar/node_modules/relay` |
| `familiar reap` | That host's `$HOME/d/familiar/node_modules/relay` |

Tasks' relay identity is off on both hosts (no per-user identity config at writing).
Do not enable it during this window. The subscriber file is
`$HOME/.config/relay/subscribers.json` (0600, containing directory 0700).
`ops-guard` subscribes to `before-tool` on `Bash` only and fails closed.
`--retire familiar` removes the old hooks in the same install that adds relay;
there is no dual writing, registry import, or registry merge.

| Harness/event | outer H | subscriber budget | matching worst case |
| --- | --- | --- | --- |
| Claude, Codex PreToolUse | 600 s | 37000 ms | ops-guard 30000 + familiar 2000 = 32000 |
| other mapped events | 600 s | 37000 ms | familiar 2000 |
| Claude SessionEnd | 60 s | 37000 ms | familiar-teardown 200 |
| Codex SessionEnd | 3 s | 800 ms | familiar-teardown 200 |

`relay install` revalidates these budgets. No `--with ask` route is installed.
Awaiting separate work: OpenCode (`relay-d0a8df`), Darwin (`relay-848c0f`), and Codex
nested code-mode routes (`ops-daf2cd`). The smoke below uses the evidenced Bash route.

All target arguments must be absolute, resolved once with `realpath`. The resolved
values, rather than home symlinks or subsequent resolutions, are used by install,
verify, guard snapshots, and restore. The exact staged files are:

| Variable / shared target | Before SHA256 at writing (both hosts) | Expected image |
| --- | --- | --- |
| `C`, `~/d/hq/claude/settings.json` | `ecea0cdbd6214797fb96d32237e15cd0c5a1d26dcbef1246fd551bcdb577e656` | `.worktrees/relay-cutover/claude/settings.json` |
| `CW`, `~/d/hq/local/claude/settings.work.json` | `c2420fb82c37506ead6f4e9d213d6cf56f268632a60a0ac14960014b419888a8` | `$CUTOVER/claude-work.after.json` (private) |
| `X`, `~/d/hq/codex/hooks.json` | `15ba003d9831e9dd69c96741783a15e5594d12eb0654b40c6ed164012824c5f7` | `.worktrees/relay-cutover/codex/hooks.json` |
| `XW`, `~/d/hq/codex/work/hooks.json` | `a4ec2044d13abd18fd81fe1bc6448f3c484b461677adb090beb28d2ad5a82786` | `.worktrees/relay-cutover/codex/work/hooks.json` |

Expected-image SHA256s in that order: `c7eb65f32e03dde0ae67d709012fbc1748bb69167a99b129bcda7e6bc2c3b775`,
`d7340e1afa0c4e5007179444b8ed4aea6dd6cc8de0063a16da980aeb9ac797ca`,
`84164406e7e36979c1ada0f1ea41ee6d5521d6a37da5df7a730934e668bc9213`, and
`3fce9c99c553a32b5d71f6380aaf0c5b2ced1d8c872de81cf3c3bbb78eefe45f`.
A changed before hash requires agent inspection and refreshed images before the window;
never overwrite live picks or trust to make a hash match. `verify` compares hooks and
statusLine; it intentionally does not replace unrelated settings.

## 0. Agent preparation, before the window

On **each host**, start Bash and resolve paths. Preparation preflights intentionally
return nonzero while sessions run; inspect all their checks. From §1 onward, use
`set -euo pipefail` so a failed command stops the shell. For rollback, open a fresh
plain Bash shell, source its saved environment, and enable those same shell options. `type -P` bypasses shell aliases,
including aliases that bypass permissions. These saved variables contain paths and pins,
not credentials. Keep installer plans, complete diffs, artifacts, settings copies,
and state under the private root; never paste their contents into a public report.

```bash
bash
umask 077
HQ=$(realpath "$HOME/d/hq")
HQT="$HQ/tools/relay-cutover"
R=$(realpath "$HQ/relay/bin/relay")
F=$(realpath "$HOME/d/familiar/bin/familiar")
CUTOVER="$HOME/.local/state/hq/relay-cutover"
IMAGE="$CUTOVER/images"
mkdir -p "$CUTOVER"
chmod 700 "$CUTOVER"
C=$(realpath "$HQ/claude/settings.json")
CW=$(realpath "$HQ/local/claude/settings.work.json")
X=$(realpath "$HQ/codex/hooks.json")
XW=$(realpath "$HQ/codex/work/hooks.json")
CLAUDE=$(type -P claude)
PRE_FAMILIAR=00f4899ae523d613d21f44bfc2c456aac67f8e5f
FEATURE_TIP=a16f4daa59b04e32f1010764d6f94401ca4eed8b
SUBSCRIBERS="$HOME/.config/relay/subscribers.json"
ECLAUDE="$HOME/d/ops/docs/runbooks/relay-guard-evidence-claude-code.json"
ECODEX="$HOME/d/ops/docs/runbooks/relay-guard-evidence-codex.json"
declare -p HQ IMAGE HQT R F CUTOVER C CW X XW CLAUDE PRE_FAMILIAR FEATURE_TIP \
  SUBSCRIBERS ECLAUDE ECODEX > "$CUTOVER/operator-env.sh"
chmod 600 "$CUTOVER/operator-env.sh"
printf '%s\n' "$C" "$CW" "$X" "$XW" > "$CUTOVER/targets.txt"
sha256sum "$C" "$CW" "$X" "$XW" > "$CUTOVER/live-before.sha256"
printf 'relay=%s\nfamiliar=%s\n' "$R" "$F"
"$R" --version
"$HQT" familiar-source --head "$PRE_FAMILIAR"
"$HQT" familiar-check --expect native
"$HQT" preflight --harness claude-code
```

On Titan also resolve `CODEX=$(type -P codex)`, append `declare -p CODEX` to
`"$CUTOVER/operator-env.sh"`, and run `"$HQT" preflight --harness codex`.
Expected: relay resolves to main's launcher, familiar to main's `bin/familiar`,
`relay 0.1.1`, and familiar source/native checks print `ok`. All preflight checks
pass except `no-live` while agents run. An absent familiar on remote PATH is harmless
here because `F` names its resolved main executable explicitly; never invoke an
unexamined PATH copy instead. Validate the four saved hashes against the table.

Observed at preparation: Titan failed only `no-live`; Europa passed `no-live`,
runtime and subscribers but failed evidence: installed Claude 2.1.280, evidence
2.1.302. **Operator**, before starting the window, runs `"$CLAUDE" update` on Europa
(or any host that fails evidence), then reruns preflight. Only exact evidenced
`2.1.302 (Claude Code)` passes. If update yields another version, stop and hand back
to the agent to rerun Task 3's ops probe. Do not update from this agent or weaken the
version check. Titan's evidenced Codex is `codex-cli 0.163.0`.

The preparation retained on **both hosts**:

```bash
# Already done during Task 7; do not overwrite these snapshots.
# For an initial preparation only, with neither destination present:
cp -a "$HOME/.local/state/familiar" "$CUTOVER/familiar-state"
cp -a "$HOME/d/familiar/node_modules" "$CUTOVER/familiar-node_modules.pre"
```

Both dependency copies contain 3865 entries, digest
`96e39f1b4abbfdc65e1e27a641f52398fb7227ef006f05bbbd4d2022c638e4db`;
source and copied tree digests matched on each host. State snapshots matched their
sources too, but are preliminary while native sessions run. Refresh them in §1.
The retained dependencies run the reverted source without any fetch.

The private expected image was copied over SSH to Europa during preparation;
both hosts have SHA256 `d7340e1afa0c4e5007179444b8ed4aea6dd6cc8de0063a16da980aeb9ac797ca`,
file mode 0600 under a 0700 root. Check on **each host**:

```bash
stat -c '%a %n' "$CUTOVER" "$CUTOVER/claude-work.after.json"
sha256sum "$CUTOVER/claude-work.after.json"
```

Expected modes `700`, `600`, and the hash above. If the image must be refreshed,
the agent transfers it from Titan with the following commands, then checks both hashes:

```bash
scp -4 -q -o BatchMode=yes "$CUTOVER/claude-work.after.json" \
  europa:.local/state/hq/relay-cutover/claude-work.after.json
ssh -4 -o BatchMode=yes europa \
  'chmod 600 ~/.local/state/hq/relay-cutover/claude-work.after.json; sha256sum ~/.local/state/hq/relay-cutover/claude-work.after.json'
```

Expected: hashes equal; never publish the private image or its full diff.

Worktrees are host-local: Europa does **not** have Titan's reviewed worktree.
During preparation the agent also copied the three public images into
`$CUTOVER/images/` on **each host**. The worktree paths in the table are provenance,
not Europa dependencies. To refresh these snapshots, on Titan only:

```bash
mkdir -p "$IMAGE/claude" "$IMAGE/codex/work"
cp -p "$HQ/.worktrees/relay-cutover/claude/settings.json" "$IMAGE/claude/settings.json"
cp -p "$HQ/.worktrees/relay-cutover/codex/hooks.json" "$IMAGE/codex/hooks.json"
cp -p "$HQ/.worktrees/relay-cutover/codex/work/hooks.json" "$IMAGE/codex/work/hooks.json"
chmod 600 "$IMAGE/claude/settings.json" "$IMAGE/codex/hooks.json" "$IMAGE/codex/work/hooks.json"
ssh -4 -o BatchMode=yes europa 'umask 077; mkdir -p ~/.local/state/hq/relay-cutover/images/claude ~/.local/state/hq/relay-cutover/images/codex/work'
scp -4 -q -o BatchMode=yes "$IMAGE/claude/settings.json" europa:.local/state/hq/relay-cutover/images/claude/settings.json
scp -4 -q -o BatchMode=yes "$IMAGE/codex/hooks.json" europa:.local/state/hq/relay-cutover/images/codex/hooks.json
scp -4 -q -o BatchMode=yes "$IMAGE/codex/work/hooks.json" europa:.local/state/hq/relay-cutover/images/codex/work/hooks.json
```

The agent retained `$CUTOVER/expected-images.sha256` on each host, with the four
reviewed image hashes above (paths relative to CUTOVER). On **each host**, after
preparation and again immediately before the live window:

```bash
(cd "$CUTOVER" && sha256sum -c expected-images.sha256)
```

Expected: all four images `OK`. All operator commands below consume these local
snapshots or main's synced tools, never Europa worktree files. Refreshing images
requires agent review; do not regenerate them during the live window.

## 1. Operator: quiesce both hosts and refresh snapshots

End **every Claude and Codex session** on Titan and Europa. Close IDE/desktop clients
that reconnect to Codex. In a plain shell on Titan, stop each home’s Codex daemon:

```bash
source "$HOME/.local/state/hq/relay-cutover/operator-env.sh"
set -euo pipefail
env -u CODEX_HOME "$CODEX" app-server daemon stop
CODEX_HOME="$HOME/.codex-work" "$CODEX" app-server daemon stop
"$HQT" preflight --harness claude-code
"$HQT" preflight --harness codex
```

Expected: daemon stopped/already stopped; `no-live: ok` for both. If preflight lists
PIDs, inspect **only those PIDs** with `ps -p <comma-separated-PIDs> -o pid,ppid,comm,args`
and `readlink /proc/<PID>/exe`. Record each identified target PID before stopping it;
close its owning client, or send `kill -TERM <recorded-target-PID>` from this plain
shell if it is a confirmed remaining daemon/app-server. Wait for exit, inspect any
survivor, and rerun strict preflight. Do not kill unrelated node processes or use
`pkill` patterns. No privilege escalation is needed. The scanner always checks comm
and readable exe links; unreadable exe plus nonmatching comm is a visibility limit.

On **each host**, using its own shell and saved environment:

```bash
source "$HOME/.local/state/hq/relay-cutover/operator-env.sh"
set -euo pipefail
"$HQ/tools/quiesce-timers" record --state "$CUTOVER/timers.json" familiar-reap.timer
"$HQ/tools/quiesce-timers" stop --state "$CUTOVER/timers.json"
"$HQ/tools/quiesce-timers" wait --state "$CUTOVER/timers.json" --timeout 3600 --poll 30
"$HQT" preflight --harness claude-code
"$HQT" familiar-source --head "$PRE_FAMILIAR"
"$HQT" familiar-check --expect native
sha256sum -c "$CUTOVER/live-before.sha256"
(cd "$CUTOVER" && sha256sum -c expected-images.sha256)
# Preserve preparation snapshots; refresh after all native writers are quiescent.
test ! -e "$CUTOVER/familiar-state.preparation"
test ! -e "$CUTOVER/familiar-node_modules.preparation"
mv "$CUTOVER/familiar-state" "$CUTOVER/familiar-state.preparation"
mv "$CUTOVER/familiar-node_modules.pre" "$CUTOVER/familiar-node_modules.preparation"
cp -a "$HOME/.local/state/familiar" "$CUTOVER/familiar-state"
cp -a "$HOME/d/familiar/node_modules" "$CUTOVER/familiar-node_modules.pre"
chmod 700 "$CUTOVER/familiar-state" "$CUTOVER/familiar-node_modules.pre"
diff -qr "$HOME/.local/state/familiar" "$CUTOVER/familiar-state"
diff -qr "$HOME/d/familiar/node_modules" "$CUTOVER/familiar-node_modules.pre"
```

Titan additionally reruns Codex preflight. To perform Europa's block over SSH use
`ssh -4 -o BatchMode=yes europa 'bash -s'` and pass that exact block on stdin; variable
expansion must happen on Europa, not Titan. Expected: timer's original enablement,
activity and service recorded; `stopped familiar-reap.timer`; `every service is
inactive`; **every** applicable preflight check green; hashes all `OK`; both diffs
empty. A state file already present means an earlier window needs reconciliation,
not overwrite. A running service is allowed to finish; `wait` never kills it.

## 2. Familiar source once, dependencies and surfaces on each host

On Titan only, after §1 is green on both hosts:

```bash
"$HQT" familiar-source --head "$PRE_FAMILIAR"
touch "$CUTOVER/familiar-step2.started"
git -C "$HOME/d/familiar" merge --no-ff --no-edit "$FEATURE_TIP"
MERGE=$(git -C "$HOME/d/familiar" rev-parse HEAD)
printf '%s\n' "$MERGE" > "$CUTOVER/familiar-merge.sha"
ssh -4 -o BatchMode=yes europa \
  "umask 077; printf '%s\\n' '$MERGE' > ~/.local/state/hq/relay-cutover/familiar-merge.sha"
```

Expected: clean two-parent merge; MERGE is the newly recorded full SHA. Never merge
the moving branch name. On **each host**, wait for source synchronization:

```bash
MERGE=$(cat "$CUTOVER/familiar-merge.sha")
"$HQT" familiar-source --head "$MERGE"
# If source is still syncing, wait and rerun the preceding check until it passes.
# Do not run familiar or install dependencies before it passes on this host.
(cd "$HOME/d/familiar" && npm ci --allow-git=root) > "$CUTOVER/familiar-install.log" 2>&1
"$HQT" familiar-check --expect relay
/usr/bin/node -e 'const fs=require("fs"); const root=process.argv[1]; const p=JSON.parse(fs.readFileSync(root+"/node_modules/relay/package.json")); const l=JSON.parse(fs.readFileSync(root+"/package-lock.json")); if(p.version!=="0.1.1" || !l.packages["node_modules/relay"].resolved.endsWith("#4ceec5d2ad22b136b37ee360e7a4ed00949f28d9")) process.exit(1); console.log("familiar relay 0.1.1 at approved commit")' "$HOME/d/familiar"
```

Expected: source `ok`, npm exit 0, `familiar-check: relay ok`, approved dependency
message. `--allow-git=root` is per command: Europa's npm 12 defaults to no Git
installs; never relax global policy. Familiar-theme retains its existing SSH pin,
so working Git credentials are also required. Complete install logs stay private.

The operator now authorizes the brief desktop restart on **each host**. Identify
and record only the two current surface PIDs:

```bash
pgrep -af '[f]amiliar-niri watch|[q]s .*familiar/integrations/niri-desktop'
```

Expected: one watcher and one `qs` niri-desktop process, or a specifically explained
absence. Inspect the recorded command lines, then `kill -TERM <watcher-PID> <qs-PID>`
using only the confirmed PIDs and wait for them to exit. Start the exact two
`spawn-sh-at-startup` commands from the host's niri config via niri's tracked spawn:

```bash
niri msg action spawn-sh -- "$HOME/d/familiar/bin/familiar-niri watch"
niri msg action spawn-sh -- "qs -d -p $HOME/d/familiar/integrations/niri-desktop"
pgrep -af '[f]amiliar-niri watch|[q]s .*familiar/integrations/niri-desktop'
```

Expected: two replacements using the merged source. These are the normal persistent
host surfaces, not detached rehearsal jobs. Record their new PIDs in the window log.
If the local config's two startup commands differ, stop for agent inspection.

## 3. Claude: dry run on both hosts, then apply each shared target once

Define these functions in the operator shells on both hosts with `set -euo pipefail` active. They keep full plans
private, extract the actual installer after-image, and compare it with the reviewed
image before any live apply. A nonzero return stops the sequence.

```bash
plan_target() {
  local target=$1 harness=$2 expected=$3 stem=$4 evidence
  if [[ $harness == claude-code ]]; then evidence=$ECLAUDE; else evidence=$ECODEX; fi
  "$R" install --harness "$harness" --subscribers "$SUBSCRIBERS" \
    --target "$target" --retire familiar --evidence "$evidence" --node /usr/bin/node \
    > "$stem.plan.json" 2> "$stem.plan.stderr" || return
  jq -er '.changes[0].after' "$stem.plan.json" > "$stem.after.json" || return
  "$HQT" verify --target "$stem.after.json" --expect "$expected" \
    > "$stem.verify.log" 2>&1
}
dry_target() {
  local id=$1 target=$2 harness=$3 expected=$4 copy evidence dir
  dir="$CUTOVER/dry/$id"
  mkdir -p "$dir" || return
  if [[ $harness == codex ]]; then copy="$dir/hooks.json"; evidence=$ECODEX
  else copy="$dir/settings.json"; evidence=$ECLAUDE; fi
  cp -p "$target" "$copy" || return
  chmod 600 "$copy" || return
  copy=$(realpath "$copy") || return
  if [[ $harness == claude-code ]]; then
    "$HQT" retire-native-guard --target "$copy" --backup "$dir" || return
  fi
  plan_target "$copy" "$harness" "$expected" "$dir/install" || return
  "$R" install --harness "$harness" --subscribers "$SUBSCRIBERS" \
    --target "$copy" --retire familiar --evidence "$evidence" --node /usr/bin/node \
    --apply --artifact "$dir/artifact.json" > "$dir/apply.log" 2>&1 || return
  "$HQT" verify --target "$copy" --expect "$expected" > "$dir/applied-verify.log" 2>&1
}
apply_target() {
  local id=$1 target=$2 harness=$3 expected=$4 evidence artifact
  if [[ $harness == claude-code ]]; then evidence=$ECLAUDE; else evidence=$ECODEX; fi
  mkdir -p "$CUTOVER/live" || return
  artifact="$CUTOVER/live/$id.json"
  test ! -e "$CUTOVER/live/$id.original" || return
  cp -p "$target" "$CUTOVER/live/$id.original" || return
  chmod 600 "$CUTOVER/live/$id.original" || return
  # Register before the first write, including an interrupted guard-only change.
  printf '%s\t%s\t%s\n' "$id" "$target" "$artifact" >> "$CUTOVER/live/touched.tsv"
  if [[ $harness == claude-code ]]; then
    "$HQT" retire-native-guard --target "$target" --backup "$CUTOVER/live" || return
  fi
  plan_target "$target" "$harness" "$expected" "$CUTOVER/live/$id" || return
  "$R" install --harness "$harness" --subscribers "$SUBSCRIBERS" \
    --target "$target" --retire familiar --evidence "$evidence" --node /usr/bin/node \
    --apply --artifact "$artifact" > "$CUTOVER/live/$id.apply.log" 2>&1 || return
  "$HQT" verify --target "$target" --expect "$expected" \
    > "$CUTOVER/live/$id.applied-verify.log" 2>&1
}
```

On **both hosts**, with their local expected images available:

```bash
dry_target claude "$C" claude-code "$IMAGE/claude/settings.json"
dry_target claude-work "$CW" claude-code "$CUTOVER/claude-work.after.json"
```

Expected: all commands exit 0, both plan and applied verification logs empty. If a
verify fails, inspect locally; do not print the private settings or complete plan.
Only then, on **Titan**, after rechecking both hosts have no live Claude:

```bash
"$HQT" preflight --harness claude-code
"$HQT" preflight --harness claude-code --host europa
sha256sum -c "$CUTOVER/live-before.sha256"
apply_target claude "$C" claude-code "$IMAGE/claude/settings.json"
apply_target claude-work "$CW" claude-code "$CUTOVER/claude-work.after.json"
```

Expected: all checks green, live guard before/after snapshots and `claude.json` /
`claude-work.json` artifacts retained, verification empty. The artifacts' `path`
fields equal the resolved target values exactly. Do not repeat apply on Europa:
wait for Dropbox, then in Europa's shell rerun until both verifications exit 0:

```bash
"$HQT" verify --target "$C" --expect "$IMAGE/claude/settings.json" > "$CUTOVER/claude-live-verify.log" 2>&1
"$HQT" verify --target "$CW" --expect "$CUTOVER/claude-work.after.json" > "$CUTOVER/claude-work-live-verify.log" 2>&1
```

Run the full Claude smoke below on Titan personal, then short work-home smoke
(start, denial, exit). On Europa the operator opens one personal session, performs
the denial, and exits, repeats for the work home, and the agent later reads that
host's registry over SSH. Do not open smoke sessions until both shared targets verify.

## 4. Codex: Titan's two homes

No Codex invocation or install is required on Europa. On Titan, define the same
functions if this is a new shell, then:

```bash
dry_target codex "$X" codex "$IMAGE/codex/hooks.json"
dry_target codex-work "$XW" codex "$IMAGE/codex/work/hooks.json"
"$HQT" preflight --harness codex
apply_target codex "$X" codex "$IMAGE/codex/hooks.json"
apply_target codex-work "$XW" codex "$IMAGE/codex/work/hooks.json"
```

Expected: dry, plan, apply and verify exit 0; `codex.json` / `codex-work.json` artifacts
retained. On each first Codex launch, inspect and approve that home's hook review
(`/hooks` if prompted there). Codex writes its own trust hashes; never hand-edit them
or use `--dangerously-bypass-hook-trust`. Run the full personal smoke and short
work-home smoke (start, denial, exit). If the work home is not trusted, this step is
incomplete even when the personal home passes.

## Smoke: operator input and observer checks

This section is a **live operator test**, not a Task 7 rehearsal result. Use a fresh
scratch repo per harness/home on the host being tested. In its operator terminal:

```bash
SMOKE=$(mktemp -d)
git -C "$SMOKE" init -q
git -C "$SMOKE" config user.name 'Relay smoke'
git -C "$SMOKE" config user.email 'relay-smoke@example.invalid'
printf '%s\n' "$SMOKE" > "$CUTOVER/smoke-cwd.txt"
cd "$SMOKE"
# Claude personal (both hosts):
env -u CLAUDE_CONFIG_DIR "$CLAUDE" --permission-mode manual
# For Claude work, use this instead, in a new scratch repo:
# CLAUDE_CONFIG_DIR="$HOME/.claude-work" "$CLAUDE" --permission-mode manual
# Codex personal (Titan):
# env -u CODEX_HOME "$CODEX" --no-daemon --sandbox workspace-write --ask-for-approval on-request
# Codex work (Titan), in a new scratch repo:
# CODEX_HOME="$HOME/.codex-work" "$CODEX" --no-daemon --sandbox workspace-write --ask-for-approval on-request
```

Use the actual executable paths saved in §0, never `cl`, `clw`, `cor`, `cowor`,
`--approve-for-me`, bypass flags, or a `never` approval policy. Claude's explicit
`manual` overrides its personal `auto` setting. Codex's explicit `on-request` and
workspace sandbox allow a real approval request; `--no-daemon` keeps the tested PID
owned by this terminal. Do not use nested code-mode to issue the denial command.

In the observer shell, on that **same host**, load the saved environment. Read the
JSON without inferring status from familiar's picture:

```bash
SMOKE=$(cat "$CUTOVER/smoke-cwd.txt")
"$R" list --json > "$CUTOVER/smoke-list.json"
jq '.snapshot.agents // {} | to_entries[] | {id:.key,state:.value.state,sessionId:.value.sessionId,pid:.value.process.pid,cwd:.value.cwd}' "$CUTOVER/smoke-list.json"
```

Match `cwd` to the scratch repo and record its ID, sessionId and non-null process PID.
On Europa the observer can run this through `ssh -4 -o BatchMode=yes europa 'bash -s'`
with the same block after sourcing its local environment. Persist each step's JSON
under a distinct private filename. Expected transitions and literal inputs:

| Step | Operator action / prompt | Expected evidence |
| --- | --- | --- |
| Start | Launch and complete initial trust, without a prompt yet | One matching root row, `idle` |
| Allow / working | Ask: `Use the shell tool once to run touch allowed.marker; sleep 10, then stop.` Approve if prompted; observe during the sleep | Row `working`; `test -f "$SMOKE/allowed.marker"` succeeds |
| Deny | Ask: `Use Bash once to run exactly git commit --allow-empty -m 'probe' -m 'Co-Authored-By: Claude <noreply@anthropic.com>' && touch denied.marker. If refused, stop and quote the refusal; do not retry or rewrite it.` | Ops `relay-guard: refusing` attribution reason in native result; `git -C "$SMOKE" rev-list --all --count` prints `0`; denied.marker absent |
| Approval | Claude: ask it to run `sleep 7` via Bash in manual mode and leave the permission dialog unanswered. Codex: explicitly ask it to request `require_escalated` permission for `touch "$HOME/.local/state/hq/relay-cutover/approval.marker"` outside the workspace; leave the dialog unanswered | Row `needs-approval` while the **human** prompt remains open; then answer it |
| Turn end | Let that turn finish | Row `done` |
| Claude idle | Leave the completed Claude session idle for at least 60 s | Claude idle prompt produces `needs-input`; Codex has no such requirement |
| Recovery | During the live session, run the recovery commands below, without sending another prompt | Live sessionId reappears in intent.json after familiar reap |
| Exit | `/exit` | Root row removed; that sessionId absent from familiar intent.json |
| Abrupt death | Open a second session; record its row PID, ID and sessionId; `kill -9 <that-recorded-harness-PID>` from the observer | Dead row remains before reconciliation; `"$R" reap` removes it; `"$R" list --json` confirms absence |

A denial that succeeds, merely encounters a Git identity error, or is never attempted
is a failed smoke. A prompt answered by an agent/auto-review is not human approval
coverage. If an existing permission allow rule prevents the Claude `sleep` dialog,
stop and inspect the effective rule rather than claiming `needs-approval` was tested.
The short home/Europa smoke requires only start, the same denial, and `/exit`.

Projection recovery, in the observer shell on the tested host, with `SID` set to
that row's literal sessionId:

```bash
SID='<recorded-sessionId>'
RECOVERY="$CUTOVER/intent.$(date -u +%Y%m%dT%H%M%SZ).before-recovery.json"
mv "$HOME/.local/state/familiar/intent.json" "$RECOVERY"
"$F" reap > "$CUTOVER/projection-recovery.log" 2>&1
jq -e --arg sid "$SID" 'has($sid)' "$HOME/.local/state/familiar/intent.json"
```

Expected: exit 0 and `true`, without another harness event. Retain the moved file;
do not replace the recovered projection with the stale one. After normal exit, the following must print `true`:

```bash
jq -e --arg sid "$SID" 'has($sid) | not' "$HOME/.local/state/familiar/intent.json"
```
After abrupt death and `relay reap`, run `"$F" reap` to clear familiar's stale intent,
and verify both row and intent entry absent. No registry is imported into familiar.

## 5. Restore timers and check scheduled reconciliation

End smoke sessions on both hosts. On **each host**, in a plain shell:

```bash
"$HQ/tools/quiesce-timers" restore --state "$CUTOVER/timers.json"
systemctl --user start familiar-reap.service
systemctl --user show -p Result -p ExecMainStatus familiar-reap.service
journalctl --user -u familiar-reap.service -n 20 --no-pager
"$R" list --json > "$CUTOVER/final-list.json"
```

Expected: `every timer matches its record`; service `Result=success`,
`ExecMainStatus=0`; journal successful. Each recorded abrupt-death row is absent from
`final-list.json` and its intent entry is absent. If a service is still running, wait
for its completion and recheck its result. Restoring returns a previously inactive
timer to inactive, too; do not unconditionally enable it.

## 6. Hand back to the agent

Return the window log, MERGE, per-home smoke verdicts, retained artifact paths,
timer/service results, both hosts' final registry summaries, and replacement surface
PIDs. Task 9 validates final diffs, trust and links, and records outcomes. Keep all
backups and `.worktrees/relay-cutover/`; do not merge or clean up hq as part of this
runbook. No live success is implied by the rehearsal results below.

## Rollback: any failure from §2 onward

End every new Claude/Codex session on both hosts, stop both Codex home daemons as in
§1, and verify `no-live`. Keep timers quiesced until source/dependencies/settings
agree again. Use the **Titan** shell (or reload its saved `operator-env.sh`). Restore
**every shared settings target touched**, in reverse order; a guard removed without
relay apply is covered. The log is registered before the first write:

```bash
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
```

Expected: every touched target byte-equal to its original; all four hashes `OK`.
Artifacts are passed only when present. A restore refusal means current bytes do
not match a recorded image: stop for agent inspection, never force-copy over them.
Retain all artifacts. On Europa, wait until `sha256sum -c
"$CUTOVER/live-before.sha256"` also reports every target `OK`.

If familiar §2 ran, on Titan:

```bash
if [[ -f "$CUTOVER/familiar-merge.sha" ]]; then
  MERGE=$(cat "$CUTOVER/familiar-merge.sha")
  git -C "$HOME/d/familiar" revert -m 1 --no-edit "$MERGE"
  REVERT=$(git -C "$HOME/d/familiar" rev-parse HEAD)
  printf '%s\n' "$REVERT" > "$CUTOVER/familiar-revert.sha"
  ssh -4 -o BatchMode=yes europa \
    "umask 077; printf '%s\\n' '$REVERT' > ~/.local/state/hq/relay-cutover/familiar-revert.sha"
else
  # Only if the initial merge failed before committing; inspect its state first.
  git -C "$HOME/d/familiar" status --short
  git -C "$HOME/d/familiar" merge --abort
  REVERT=$PRE_FAMILIAR
  printf '%s\n' "$REVERT" > "$CUTOVER/familiar-revert.sha"
  ssh -4 -o BatchMode=yes europa \
    "umask 077; printf '%s\\n' '$REVERT' > ~/.local/state/hq/relay-cutover/familiar-revert.sha"
fi
```

Expected: one merge-revert commit recorded as REVERT, or the uncommitted merge
aborted back to PRE_FAMILIAR. On **each host**, only after source has fully synced:

```bash
REVERT=$(cat "$CUTOVER/familiar-revert.sha")
"$HQT" familiar-source --head "$REVERT"
# If still syncing, wait and rerun the source check before the following commands.
test -d "$CUTOVER/familiar-node_modules.pre"
rm -rf "$HOME/d/familiar/node_modules"
cp -a "$CUTOVER/familiar-node_modules.pre" "$HOME/d/familiar/node_modules"
"$HQT" familiar-check --expect native
diff -qr "$HOME/d/familiar/node_modules" "$CUTOVER/familiar-node_modules.pre"
git -C "$HOME/d/familiar" diff --quiet "$PRE_FAMILIAR" HEAD
```

Expected: source `ok`, `familiar-check: native ok`, dependency comparison empty and
Git tree equal to PRE_FAMILIAR. **No npm, fetch, or network dependency recovery.**
Restart each host's two familiar surfaces by the recorded PID procedure in §2,
restore timers on both hosts, check service success, and start fresh native sessions.
The saved familiar state stays untouched as evidence; no old state or registry is
merged. Leave `$HOME/.local/state/relay` in place, unused. A later retry re-merges by
reverting REVERT, not by merging FEATURE_TIP again; prepare a new reviewed window
and fresh snapshots/artifacts before doing so.

## Disposable rehearsal evidence (2026-10-19)

No live hooks, installed harnesses, main familiar revision, live timers, desktop
surfaces, home links, or trust were changed by these rehearsals.

On Titan, a one-Claude pilot exercised retire → plan → verify → apply → verify →
restore successfully. Then all four settings copies were rehearsed at three stop
points: (a) after native guard retirement, (b) after plan verification, and (c) after
all applies and final verifies. After each case **all four copies were byte-equal**
to their captured originals. Full artifacts and private logs remain below
`$CUTOVER/rehearsal/`. Codex copies used the required basename `hooks.json`.
An initial plan stopped on a different basename; its partial changes were restored
and every copy compared equal before the corrected run. No JSONC target is in scope.

On **each host**, a throwaway clone detached at PRE_FAMILIAR cleanly merged
FEATURE_TIP, ran actual `npm ci --allow-git=root` with `/usr/bin/npm` **12.2.1**, and
`bin/familiar observe --help` exited 0. The installed relay lock resolution was the
approved `4ceec5d2ad22b136b37ee360e7a4ed00949f28d9`. Each clone then reverted its merge,
restored its copied pre-merge dependencies inside `unshare -rn` (network isolated),
and `bin/familiar hook --help` exited 0. `git diff --quiet "$PRE_FAMILIAR" HEAD` and
the dependency tree digest comparison passed on both hosts. This exercised Europa's
actual npm12 policy **and** credentials, not only Titan's interactive npm11.
The controlled Titan rehearsal also selected installed npm12 through its explicit
minimal PATH. Its first merge was correctly refused because that PATH omitted tasks;
the retry included the installed tasks directory and passed the normal identity hook.

Retained evidence: `$CUTOVER/familiar-rehearsal-v2/` on each host, containing the
clone, old dependencies, command logs, and safe `result.json`; preliminary old state
and dependencies at `$CUTOVER/familiar-state` / `familiar-node_modules.pre` on each
host; Titan settings results at `$CUTOVER/task7/settings-results.json`. All are under
0700 host-local roots; private artifacts and expected images are 0600. Dependency
backup executable modes are preserved. Refresh mutable state during §1.
Preflight still requires the operator's live-session quiescence and Europa Claude
version correction. Real interactive smokes remain unrun until that window.
