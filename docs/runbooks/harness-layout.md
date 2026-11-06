# Harness layout activation

This is the one-time transition from the five root directories to `harnesses/`
and `external/`. It preserves native homes and session stores. Build and review
happen in the task worktree; activation happens in the registered **main checkout**.
The implementation plan is `docs/plans/2026-11-05-harness-layout.md`.

## Authority and preparation

Obtain explicit activation approval for the exact accepted commit, the main base,
the hosts sharing the checkout and records, a no-writer window, and the conditional
recovery below. Plan approval alone is insufficient. All affected sessions must
stop saving settings from old-path capture through link reconciliation. Do not
kill sessions or stop services without that authority. If the controller is itself
a writer, hand these commands to an ordinary operator shell after it exits.
An adopted host may resume only when every other affected host has adopted or is
kept quiescent by explicit agreement. A host receiving Dropbox files is not yet
adopted.

Use a Bash operator shell with `set -euo pipefail`. In that shell, set these to the frozen values from the activation record (not a
moving branch name). `MAIN` is the path printed by `tasks root hq-b77d0c --pretty`;
`BUILD` is its `.worktrees/hq-b77d0c` directory. `SNAP` must be a new private
persistent directory under `$WORK_ROOT/hq/hq-b77d0c/`; never use `/tmp` for it.

```sh
MAIN=$(tasks root hq-b77d0c --pretty)
BUILD="$MAIN/.worktrees/hq-b77d0c"
# Set BEFORE, REVIEWED and SNAP to the approved record's exact values.
: "${BEFORE:?}" "${REVIEWED:?}" "${SNAP:?}" "${WORK_ROOT:?}"
cd "$MAIN"
test "$(git rev-parse HEAD)" = "$BEFORE"
git -C "$BUILD" merge-base --is-ancestor "$REVIEWED" HEAD
git -C "$BUILD" diff --quiet "$REVIEWED" HEAD -- tools/harness-layout-picks docs/runbooks/harness-layout.md
git merge-base --is-ancestor "$BEFORE" "$REVIEWED"
git diff --cached --quiet
git -C "$BUILD" diff --quiet
git -C "$BUILD" diff --cached --quiet
umask 077
mkdir -m 700 "$SNAP"
git status --porcelain=v1 --untracked-files=all
```

Later task-record commits may descend from the accepted build; the helper and
runbook used from `BUILD` must still match `REVIEWED`, as checked above. Main
advances only to the frozen `REVIEWED` commit.

Account for every dirty path. Only the four harness configs may carry the approved
unfiltered edits. The known initiating-host edit is agy's `agentMode: auto`; do not
turn it into a tracked default or a filtered key. Stop on unexplained differences.
Resolve `just`, `harness-state-refresh`, `hq`, and `relay` on PATH and verify the
registered main destinations. Audit registered projects and private work configs
for active old-path references without printing their values. Record any external
change needed in the activation request before acting.

Inventory each old tree with `git status --ignored --porcelain=v1
--untracked-files=all -- agy claude codex pi ponytail`. Assign each ignored/untracked
entry an explicit destination or a reason it is regenerable. Known examples are
Claude mod generated types, mod `tsconfig.json`, and probe `__pycache__`. Preserve
unique content; do not archive or delete the entire old tree. Prepare the exact
rollback path list from the reviewed diff, excluding tasks, specs, plans and review
reports. Include both old and new names for renames and all changed runtime
manifests, tools and current reference documents. Retain that reviewed list as
`$SNAP/runtime-paths.txt`, one path per line. Also freeze `carry-paths.txt` and
`discard-paths.txt` as main-relative regular-file lists for the ignored inventory.
Keep empty files for empty lists; do not put directories or globs in them.

## Snapshot and change detection

Extract the four tested scripts from this accepted runbook into the private
snapshot directory, preserving their exact source. The labelled Python blocks
below are also the test inputs.

```sh
python3 - "$BUILD/docs/runbooks/harness-layout.md" "$SNAP" <<'PYCODE'
from pathlib import Path
import sys
text, destination = Path(sys.argv[1]).read_text(), Path(sys.argv[2])
for name in ('guard', 'compare-patches', 'repair-anchors', 'align-agy'):
    source = text.split(f'<!-- script:{name} -->\n```python\n', 1)[1].split('\n```', 1)[0]
    path = destination / (name + '.py')
    with path.open('x') as out:
        out.write(source + '\n')
    path.chmod(0o600)
PYCODE
configs=(claude/settings.json codex/config.toml pi/settings.json agy/settings.json)
state=(local/live-picks.json local/live-picks-pi.json local/live-picks-agy.json local/codex/trust.toml)
private=(local/claude/settings.work.json local/codex/config.work.toml)
home_paths=("$HOME/.claude/settings.json" "$HOME/.claude/agents" "$HOME/.claude/commands"
  "$HOME/.claude/mods" "$HOME/.claude/plans" "$HOME/.claude-work/statusline-command.sh"
  "$HOME/.codex/config.toml" "$HOME/.codex/hooks.json" "$HOME/.codex-work/hooks.json"
  "$HOME/.pi/agent/settings.json" "$HOME/.pi/agent/extensions/harness-state.ts"
  "$HOME/.gemini/antigravity-cli/settings.json" "$HOME/.gemini/config/hooks.json"
  "$HOME/.gemini/config/skills.json" "$HOME/.local/bin/pi" "$HOME/.config/ponytail/config.json")
mapfile -t carry < "$SNAP/carry-paths.txt"
mapfile -t discard < "$SNAP/discard-paths.txt"
guarded=()
mkdir -m 700 "$SNAP/raw-before"
for rel in "${configs[@]}" "${state[@]}" "${private[@]}" "${carry[@]}" "${discard[@]}"; do
  guarded+=("$MAIN/$rel")
  test ! -L "$rel"
  if test -e "$rel"; then
    test -f "$rel"
    cp --parents --preserve=mode,timestamps -- "$rel" "$SNAP/raw-before/"
  fi
done
detached="$HOME/.gemini/antigravity-cli/settings.json"
if test ! -L "$detached" && test -f "$detached"; then
  cp --preserve=mode,timestamps -- "$detached" "$SNAP/detached-agy.json"
fi
git show "$BEFORE:agy/settings.json" > "$SNAP/agy-base.json"
python3 "$SNAP/guard.py" save "$SNAP/checkpoint-0.json" "${guarded[@]}" "${home_paths[@]}"
python3 "$SNAP/guard.py" check "$SNAP/checkpoint-0.json"
```

The snapshots include raw configs, saved records, trust, private work configs,
detached agy bytes and every inventoried ignored file. The checkpoint records
absence and link strings too. Keep separate versions before and after capture;
never overwrite an earlier snapshot. The two cache files slated for disposal are
cheap to snapshot too, and their approved disposition remains explicit.

The extracted `$SNAP/guard.py` contains this literal block. It records hashes, kinds, modes
and symlink text, and checks them again before the next mutation. Checkpoints are
immutable: use a new name after each *verified intentional* change, never overwrite
a failed checkpoint to make it pass. Supply every guarded config, record, trust
file and home link, including absent paths. Run `python3 "$SNAP/guard.py" save
"$SNAP/checkpoint-0.json" <explicit paths...>` and `python3 "$SNAP/guard.py" check
"$SNAP/checkpoint-0.json"`. Tests execute this block verbatim.

<!-- script:guard -->
```python
import hashlib, json, os, stat, sys
from pathlib import Path
mode, checkpoint, *names = sys.argv[1:]
def observe(name):
    path = Path(name)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {'kind': 'absent'}
    if stat.S_ISLNK(info.st_mode):
        return {'kind': 'link', 'target': os.readlink(path)}
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit('guard refuses a non-file input: ' + name)
    return {'kind': 'file', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'mode': stat.S_IMODE(info.st_mode), 'mtime_ns': info.st_mtime_ns}
if mode == 'save':
    if not names:
        raise SystemExit('guard needs explicit paths')
    with open(checkpoint, 'x') as out:
        json.dump({name: observe(name) for name in names}, out, indent=2)
elif mode == 'check' and not names:
    expected = json.loads(Path(checkpoint).read_text())
    changed = [name for name, before in expected.items() if observe(name) != before]
    if changed:
        raise SystemExit('inputs changed; stop and retain evidence: ' + ', '.join(changed))
else:
    raise SystemExit('usage: guard.py save CHECKPOINT PATH... | check CHECKPOINT')
```

Hashes detect observed changes; they cannot prevent another host from writing
between checks. The approved no-writer window is required even while holding
`local/harness-state.lock`. On a changed input, stop all further activation steps,
retain both versions and request a fresh window; do not retry blindly.

The extracted `$SNAP/compare-patches.py` contains this block. Clean blob hashes can
change when the accepted revision changes unrelated tracked content. Compare the
normalized patches without their `index` hash headers; preserve every path,
hunk header, context line and changed line. Any remaining difference stops the
transition for inspection, even when it might only be a shifted context line.

<!-- script:compare-patches -->
```python
import re, sys
from pathlib import Path
def normalized(path):
    return [line for line in Path(path).read_bytes().splitlines(keepends=True)
            if not re.fullmatch(rb'index [0-9a-f]+\.\.[0-9a-f]+(?: [0-7]{6})?\n?', line)]
if normalized(sys.argv[1]) != normalized(sys.argv[2]):
    raise SystemExit('carried unfiltered diff differs; stop and inspect retained patches')
```

## Initiating host

Use `set -e` in the operator shell and check each command's stderr. Git hooks
report failures while returning success, so Git exit status alone is insufficient.
Run each numbered group only after the preceding checks and snapshots are verified.

1. With old anchors still owned, capture and restore live state:

   ```sh
   .githooks/codex-trust sync
   .githooks/live-picks sync
   test -L "$HOME/.gemini/antigravity-cli/settings.json"
   test "$(readlink -f "$HOME/.gemini/antigravity-cli/settings.json")" = "$MAIN/agy/settings.json"
   git diff --binary -- claude/settings.json codex/config.toml pi/settings.json agy/settings.json > "$SNAP/unfiltered.patch"
   ```

   Verify the known agy edit and every other unfiltered change against the approved
   inventory. Snapshot the resulting records/trust/configs as a second version.
   Save a new checkpoint after verifying the capture preserved the unfiltered
   content and picks. Require no settings save through the merge/link interval.

2. After checking that checkpoint, clear **only named dirty config paths** using
   `git restore --source="$BEFORE" --worktree -- <approved dirty config paths>`.
   This deliberate clearing is part of the activation approval, not routine cleanup.
   Never stash or restore unrelated files. Confirm the index is clean and the
   configs' cleaned contents match `BEFORE`. Check unchanged inputs against their
   previous checkpoint; take the next checkpoint for the intentionally restored
   files and verify it immediately before the incompatible-key interval.

3. Preview and rekey the records, then immediately advance main:

   ```sh
   "$BUILD/tools/harness-layout-picks" --root "$MAIN" --direction forward
   "$BUILD/tools/harness-layout-picks" --root "$MAIN" --direction forward --apply
   git merge --ff-only "$REVIEWED"
   ```

   The helper requires the real `local/` directory and the existing state lock
   created by `live-picks sync`. It refuses a linked worktree, unknown/colliding
   keys, invalid JSON and symlink records. All records are validated before writes;
   each changed file is independently replaced. Output names keys, never values.
   Already migrated files are no-ops. If interrupted, inspect snapshots and the
   printed `rekeyed` lines before a bounded same-direction retry. Do not invoke
   old live-picks between rekey and merge. On a merge failure, inspect actual HEAD
   and record keys and use only the authorized pre-merge recovery below.

4. Confirm the real post-merge hooks restored picks/trust under the new keys,
   then reapply the exact preserved unfiltered diff:

   ```sh
   git apply --check --directory=harnesses "$SNAP/unfiltered.patch"
   git apply --directory=harnesses "$SNAP/unfiltered.patch"
   ```

   Require that the patch names only the four old config paths. Do not copy raw old
   configs onto new tracked files. Git applies the configured clean filter before
   patching: the rehearsal includes JSON tail and TOML first-table edits with picks
   and trust already populated. The apply can strip those live fields; the explicit
   sync below restores them. A patch conflict stops activation with snapshots intact.

5. Move each inventoried needed ignored/untracked entry to its mapped new path.
   Require source bytes to match its snapshot, destination absence, then compare
   bytes/hash after the move. Remove only individually named disposable files;
   use `rmdir` on empty parents, never recursive removal of the old roots.
   Reconcile and verify:

   ```sh
   just link --apply
   .githooks/codex-trust sync
   .githooks/live-picks sync
   just link-check
   tools/harness-facts check
   python3 .githooks/harness_state.py check
   just check-hygiene
   git diff --cached --quiet
   git diff --binary --relative=harnesses -- harnesses/claude/settings.json harnesses/codex/config.toml harnesses/pi/settings.json harnesses/agy/settings.json > "$SNAP/unfiltered-after.patch"
   python3 "$SNAP/compare-patches.py" "$SNAP/unfiltered.patch" "$SNAP/unfiltered-after.patch"
   for old in agy claude codex pi ponytail; do test ! -e "$old"; test ! -L "$old"; done
   git show "$BEFORE:codex/hooks.json" | cmp - harnesses/codex/hooks.json
   git show "$BEFORE:codex/work/hooks.json" | cmp - harnesses/codex/work/hooks.json
   ```

   Compare parsed picks, project trust, existing `[hooks.state]` values and private
   paths against snapshots without logging values. Do not synthesize trust hashes.
   Native link names stay the same. Record the tested revision, commands, exits and
   assertions. Only release this host when other affected hosts are adopted or
   explicitly kept quiescent. Keep snapshots owned by the open activation task.

## Post-sync host with detached agy settings

Take the same approved window and snapshots on this host. Verify its current main
is the accepted revision, its configs/records are the expected synced generation,
and records are forward-rekeyed if necessary. A detached regular settings file
with stale anchors causes `harness-links --apply` to refuse; `live-picks sync`
cannot adopt it either. Do not relax first-run checks.

Use the extracted `$SNAP/repair-anchors.py`, and run
`python3 "$SNAP/repair-anchors.py" "$MAIN"`. It checks **both** anchors before
changing either. Existing correct links are no-ops; any foreign link or real file
stops the operation. The `reverse` argument is only for approved rollback.

<!-- script:repair-anchors -->
```python
import os, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve(strict=True)
reverse = sys.argv[2:] == ['reverse']
if sys.argv[2:] not in ([], ['reverse']):
    raise SystemExit('unexpected direction')
pairs = []
for name in ('hooks.json', 'skills.json'):
    link = Path.home() / '.gemini/config' / name
    old, new = root / 'agy' / name, root / 'harnesses/agy' / name
    source, target = (new, old) if reverse else (old, new)
    if not link.is_symlink():
        raise SystemExit('anchor is not an owned symlink: ' + str(link))
    actual = Path(os.readlink(link))
    if not actual.is_absolute():
        actual = link.parent / actual
    actual = actual.parent.resolve() / actual.name
    if actual not in (source, target) or not target.is_file():
        raise SystemExit('anchor ownership or target check failed: ' + str(link))
    pairs.append((link, os.readlink(link), target))
for link, before, target in pairs:
    if not link.is_symlink() or os.readlink(link) != before:
        raise SystemExit('anchor changed; stop and retain snapshots')
    if link.resolve() == target:
        continue
    temporary = link.with_name(link.name + '.layout-new')
    if temporary.exists() or temporary.is_symlink():
        raise SystemExit('temporary anchor already exists; inspect it')
    temporary.symlink_to(target)
    try:
        os.replace(temporary, link)
    finally:
        temporary.unlink(missing_ok=True)
```

Before adoption, align unfiltered content across both possible mtime-selected
bases. Use the extracted `$SNAP/align-agy.py`, then run
`python3 "$SNAP/align-agy.py" "$MAIN" "$SNAP/agy-base.json"
"$SNAP/detached-agy.json"`. The last input is the immutable raw detached snapshot.
It must still equal the live detached file. The old base must come from the pinned
pre-move revision. This bounded top-level three-way merge refuses overlapping
changes to a setting; nested objects are one setting, so disjoint nested edits
may require explicit operator resolution rather than guessing.

<!-- script:align-agy -->
```python
import json, sys, tomllib
from pathlib import Path
root, base_path, snapshot = map(Path, sys.argv[1:])
root = root.resolve(strict=True)
current = root / 'harnesses/agy/settings.json'
detached = Path.home() / '.gemini/antigravity-cli/settings.json'
if current.is_symlink() or detached.is_symlink():
    raise SystemExit('alignment requires regular current and detached files')
before_current, before_detached = current.read_bytes(), detached.read_bytes()
if before_detached != snapshot.read_bytes():
    raise SystemExit('detached settings changed after snapshot')
spec = tomllib.loads((root / 'harnesses.toml').read_text())['harnesses']['agy']['live_state']
keys = set(spec['clean_keys'])
base, new, home = [json.loads(b) for b in (base_path.read_bytes(), before_current, before_detached)]
if not all(isinstance(value, dict) for value in (base, new, home)):
    raise SystemExit('settings must be JSON objects')
missing = object()
merged = {}
for key in dict.fromkeys([*new, *home, *base]):
    if key in keys:
        continue
    old, left, right = (data.get(key, missing) for data in (base, new, home))
    if left != old and right != old and left != right:
        raise SystemExit('unfiltered settings conflict; stop and retain both versions')
    value = right if right != old else left
    if value is not missing:
        merged[key] = value
sys.path.insert(0, str(root / '.githooks'))
import harness_state
with harness_state.Checkout('layout-alignment').locked():
    if current.read_bytes() != before_current or detached.read_bytes() != before_detached:
        raise SystemExit('settings changed during alignment')
    for path, data, before in ((current, new, before_current), (detached, home, before_detached)):
        if path.read_bytes() != before:
            raise SystemExit('settings changed during alignment; stop and retain snapshots')
        result = {**merged, **{k: v for k, v in data.items() if k in keys}}
        harness_state.write(path, json.dumps(result, indent=2) + '\n')
```

Now run `.githooks/live-picks sync`, confirm the home settings path is again a
symlink and every detached edit/pick plus new tracked setting survived, then
`just link --apply` and the initiating host's verification. Do not manipulate
mtimes to choose a base. The original detached snapshot remains unchanged.
On refusal, keep the host quiescent and retain all versions for a new decision.

## Conditional recovery

Before main advances: confirm `HEAD == BEFORE`, inspect every record and the
helper's completed lines, then use the accepted helper with `--direction reverse`
(preview, then `--apply`). Already-old records remain untouched. Reapply
`$SNAP/unfiltered.patch` without `--directory`, after `git apply --check` succeeds.
Run old-path trust/pick sync and link checks, compare the original diff and saved
state, and stop. A failed merge that actually advanced HEAD needs the next route.

After main advances: use the separately approved corrective-commit route, never
`git reset`. Remain quiescent. Snapshot current raw state and unfiltered deltas
again. Clear only the named carried config diffs against `REVIEWED`, reverse-rekey
records immediately before restoring the old runtime, and run:

```sh
# runtime-paths.txt was frozen with the activation request, includes both sides
# of renames, and excludes task/spec/plan/review history.
git --literal-pathspecs restore --source="$BEFORE" --staged --worktree --pathspec-from-file="$SNAP/runtime-paths.txt"
git commit -m 'fix: restore prior harness runtime layout'
```

Restore retained unique entries to old paths with absence/hash checks; keep the
new snapshots. Remove their now-empty new parents with `rmdir`, stopping on any
unaccounted entry. Reapply only the verified unfiltered patch at old paths. Run
`repair-anchors.py "$MAIN" reverse` before any detached agy adoption, reconcile
links from main, then trust/pick sync and the old-layout equivalent of the checks.
Record both forward and corrective commits and preserve newer task/review evidence.
Any newly conflicting setting or unreviewed runtime change stops this route for
operator resolution. Do not remove the build worktree or snapshots until all host
adoption/recovery work and retained evidence have an explicit owner.
