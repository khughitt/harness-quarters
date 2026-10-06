# The Rename to hq: Preparation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** draft 2026-10-06, for review.

**Goal:** Land the rename design's phase 1 steps 1 to 3 under the name `tack`: nothing a host runs names the checkout, the cutover tool is general enough for this rename, and the link tool has a functional name.

**Architecture:** Three changes, each behaviour-preserving and each reverting on its own. (1) The session-archive units call the tool through a `~/.local/bin` link that `links.toml` manages, as the hook commands already do. (2) `tools/rename-cutover` takes the renamed checkout and a list of other repositories in place of `--ai` and `--ops`, splits `apply` into `apply`, `retarget` and `link` so the runbook can commit between them, reads the link tool's path from its snapshot, refuses on a branch main lacks, accepts the rename's own alias retarget and group rewrite in its guard, and saves and restores files git cannot (the Codex trust files) with their modes. (3) `tools/tack-link` becomes `tools/harness-links`.

**Tech Stack:** Python 3 standard library, pytest through `uv run`, `just`, the `tasks` CLI 0.2.0, git worktrees, systemd user units.

**Spec:** `docs/specs/2026-10-06-rename-to-hq-design.md` (accepted at review round 5), §3.1 steps 1 to 3, with the parts of §3.2 step 1 and §4 that the cutover tool, not its runbook, carries.

## Scope: what this plan does not do

The spec's phase 1 has five steps. This plan does the first three. Step 4 (`session-episodes` resolves former roots and alias prefixes) uses the resolver that `tasks-7580d2` will define, and that task has no design yet. Step 5 (the consumers' prepared branches) and phase 2 (the rehearsal, the cutover, the second host) wait on that resolver and on what `flows-44890e` and `obs-ff4e76` choose. A plan written now would have to name interfaces nobody has designed. So those get a second plan, `docs/plans/<date>-rename-to-hq-cutover.md`, under the same task, written when `tasks-7580d2` has landed. The alternative, one plan now with those parts written against guessed interfaces, was rejected.

So these stay with that second plan, although the spec states them:

- the timers' quiescence, the user's attestations, and the systemd steps of rollback (`daemon-reload`, the timer re-enable, the enable link's comparison). Those are the runbook's: the tool must never touch the live user manager, because the rehearsal runs this same code (spec §4);
- the save of the broken-link set, the enable link's target and the archive units' listing. Those are also the runbook's, written into the snapshot directory beside the tool's own files;
- the probe of `systemctl reenable` on a linked unit (spec §3.2 step 7).

## Global Constraints

- The project is called `tack` throughout this plan. Only the link tool is renamed (Task 6); no identity, prefix, directory or registry key changes.
- All repository changes are made in `.worktrees/tack-8b7a28` (branch `feat/rename-hq`, exists, set up with `just setup`).
- No AI attribution in any commit. Conventional commit subjects. Never bypass a hook. A commit names its paths: `git commit -m … -- <paths>`.
- Shell state does not carry from one block to the next. Every `sh` block opens by sourcing `docs/plans/2026-10-06-rename-to-hq-preparation.env.sh`. It sets `TACK` (the main checkout), `WT` (the worktree), `BRANCH`, `STEP1` to `STEP7`, `STATE` (an ignored directory in the worktree for values a later block needs), `SECOND` (the second host's name, read back from `STATE`), `TASK1_COMMIT` and `TASK2_COMMIT` (read back from `STATE`), `t` (run a command, print its last line, keep its status, and on failure name the file holding the full output) and `need` (refuse when a named variable is empty). Each block is one `&&` chain: a failure stops everything after it.
- An inline `Run:` command runs in the worktree (`cd "$WT"` after sourcing the file) unless its step names another directory.
- No hostname and no machine-specific absolute path goes into a committed file. The second host's name lives only in `$STATE/second-host`.
- `just link --apply` runs from tack's main checkout only, and only in Task 3.
- Never `just --quiet`: in just 1.58 it suppresses the recipe's own output, so a preview prints nothing. Run `just link` and filter out the echoed recipe line.
- Nothing in this plan runs `rename-cutover` against live state. Its tests build sandboxes with their own `HOME`, `XDG_CONFIG_HOME` and `XDG_STATE_HOME`.
- Host steps wait for the user's approval at that moment. A task that reaches one parks with `tasks park … --waiting-on user --reason approval`.
- Tests: the focused run is `uv run -q --with pytest pytest tools/<file> -q`. `just test` runs before every commit that touches code. There is no CI and no pre-push suite here.

## Review Focus

Inputs the spec implies and a person will meet. Each has its test in the task that owns the code.

1. **The cutover run from its snapshot copy after the checkout has moved.** The runbook runs the copy in the snapshot, since the checkout's own path is gone. `link` and `verify` must find the link tool under the new root. `link` must refuse before `apply` has moved anything. Task 4: `test_the_whole_cutover_retargets_links_and_verifies` (the sandbox runs the snapshot copy) and `test_link_refuses_before_apply`.
2. **A `--keep` path that is missing, a link, absolute or outside the checkout.** It is refused at save, before the snapshot exists, never skipped. Task 5: `test_save_refuses_a_kept_path_that_is_not_a_file` and `test_save_refuses_a_kept_path_outside_the_checkout`.
3. **A repository named twice, or the checkout named as a repository.** Refused at save. Task 4: `test_save_refuses_a_repository_named_twice` and `test_save_refuses_the_checkout_named_as_a_repository`.
4. **A retarget aimed at a repository outside the snapshot while rollback is still possible.** Refused, with the file untouched; `--forward` allows it once rollback is over. Task 4: `test_retarget_refuses_a_repository_outside_the_snapshot`.
5. **The archive tool run through its link from another directory**, as the units will run it. It finds its package. Task 1: `test_the_tool_runs_through_a_link_from_any_directory`.

## Step records and the environment file

One step record per task, children of `tack-8b7a28`, created with this plan's draft. Their ids, and everything else a block needs, are in `docs/plans/2026-10-06-rename-to-hq-preparation.env.sh`, committed beside this plan. Every block starts by sourcing it:

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && echo "$STEP1 … $STEP7 on $BRANCH"
```

Each task's first step starts its record. A code task closes its record in its code commit.

**Order.** Tasks 1 and 2 come first, and Task 3 merges them in that order, because the units must not name the link before it exists on both hosts. Tasks 4 to 6 do not wait for Task 3: if the approval for the host step comes later, they run before it. Task 7 runs after all six: its merge brings the manifest entry to main in full, and `just link-check` passes only where Task 3 has installed the link.

---

### Task 1: The session-archive tool linked onto PATH

**Files:**
- Modify: `links.toml` (one `[required]` entry)
- Test: `tools/test_session_archive_units.py`

**Interfaces:**
- Produces: the link `~/.local/bin/session-archive` → `tools/session-archive`, declared in `links.toml [required]`. Task 2's units call it; Task 3 installs it.

- [ ] **Step 1: Start the record and write the failing tests**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && tasks start "$STEP1" >/dev/null && ~/.agents/bin/trial-arm tack-8b7a28
```

In `tools/test_session_archive_units.py`, add `import subprocess` after `import configparser`, add `TOOL = ROOT / "tools" / "session-archive"` after the `UNITS` line, and append:

```python
def test_the_tool_is_linked_onto_path():
    """The units call the tool through this link, so they never name the checkout."""
    required = tomllib.loads((ROOT / "links.toml").read_text())["required"]
    assert required["~/.local/bin/session-archive"] == "tools/session-archive"


def test_the_tool_runs_through_a_link_from_any_directory(tmp_path):
    link = tmp_path / "bin" / "session-archive"
    link.parent.mkdir()
    link.symlink_to(TOOL)
    result = subprocess.run(["/usr/bin/python3", str(link), "--help"], cwd=tmp_path, text=True,
                            capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "capture" in result.stdout and "prune" in result.stdout
```

- [ ] **Step 2: Run them to see the first fail**

Run: `uv run -q --with pytest pytest tools/test_session_archive_units.py -q`
Expected: `test_the_tool_is_linked_onto_path` fails with `KeyError: '~/.local/bin/session-archive'`. `test_the_tool_runs_through_a_link_from_any_directory` already passes: the tool finds its package from its own real path. It pins that behaviour, which the units are about to depend on.

- [ ] **Step 3: Add the entry**

In `links.toml`, directly after the line `"~/.local/bin/harness-state-refresh" = ".githooks/harness-state-refresh"`, add:

```toml
"~/.local/bin/session-archive" = "tools/session-archive"
```

- [ ] **Step 4: Run the focused tests, then the suite**

Run: `uv run -q --with pytest pytest tools/test_session_archive_units.py -q`
Expected: `7 passed`.

Run: `just test`
Expected: every suite passes. `tools/test_tack_link.py`'s real-manifest tests clone the committed tree, so they see the new entry only after the commit. Step 5 reruns them.

- [ ] **Step 5: Commit, then rerun the manifest tests against the commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && \
tasks done "$STEP1" "links.toml links ~/.local/bin/session-archive to tools/session-archive" >/dev/null && \
git commit -q -m "feat(links): link the session-archive tool onto PATH (tack-8b7a28)" -- links.toml tools/test_session_archive_units.py "tasks/$STEP1.md" && \
git rev-parse HEAD > "$STATE/task1-commit" && t uv run -q --with pytest pytest tools/test_tack_link.py -q
```

Expected: the last line reads `passed`, with no failures. The real-manifest tests clone this commit and validate the new entry's target.

---

### Task 2: The units call the linked tool

**Files:**
- Modify: `systemd/user/session-archive-capture.service`, `systemd/user/session-archive-prune.service`
- Test: `tools/test_session_archive_units.py`

**Interfaces:**
- Consumes: the `~/.local/bin/session-archive` link from Task 1.
- Produces: units whose only paths are `%h/.local/bin/session-archive` and `/usr/bin/python3`; no `Documentation=` line.

- [ ] **Step 1: Start the record and write the failing tests**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && tasks start "$STEP2" >/dev/null
```

In `tools/test_session_archive_units.py`, replace `test_service_runs_tool_with_path` (keep its `parametrize` decorator) with:

```python
def test_service_runs_the_linked_tool_with_path(name, command):
    service = unit(f"session-archive-{name}.service")["Service"]
    assert service["Type"] == "oneshot"
    assert service["ExecStart"] == f"/usr/bin/python3 %h/.local/bin/session-archive {command}"
    assert service["Environment"] == "PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin"
```

and append:

```python
def test_no_unit_names_the_checkout():
    """A rename moves the checkout; a unit that names its path stops working
    (docs/specs/2026-10-06-rename-to-hq-design.md §3.1)."""
    for path in sorted(UNITS.iterdir()):
        for line in path.read_text().splitlines():
            if line.startswith("#"):
                continue
            assert "%h/d/" not in line and "file://" not in line, f"{path.name}: {line}"
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run -q --with pytest pytest tools/test_session_archive_units.py -q`
Expected: 3 failed (both `ExecStart` cases, and `test_no_unit_names_the_checkout` naming `session-archive-capture.service: Documentation=file://%h/d/tack/…`).

- [ ] **Step 3: Change both service units**

In each of `systemd/user/session-archive-capture.service` and `systemd/user/session-archive-prune.service`:

- delete the line `Documentation=file://%h/d/tack/docs/specs/2026-09-30-session-archive-design.md`;
- insert as the file's first line: `# Design: docs/specs/2026-09-30-session-archive-design.md, in the repository that holds this unit.`
- in `ExecStart=`, replace `%h/d/tack/tools/session-archive` with `%h/.local/bin/session-archive`.

The capture unit then reads:

```ini
# Design: docs/specs/2026-09-30-session-archive-design.md, in the repository that holds this unit.
[Unit]
Description=Capture agent session transcripts into the session archive

[Service]
Type=oneshot
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python3 %h/.local/bin/session-archive capture
Nice=10
IOSchedulingClass=idle
```

The prune unit is the same, with its own `Description=` line and `prune` in place of `capture`. The timers are unchanged.

- [ ] **Step 4: Run the focused tests, verify the unit, then the suite**

Run: `uv run -q --with pytest pytest tools/test_session_archive_units.py -q && systemd-analyze --user verify systemd/user/session-archive-capture.service systemd/user/session-archive-prune.service`
Expected: `8 passed`; `systemd-analyze` prints nothing and exits 0. It checks the executable, `/usr/bin/python3`, not the script path it is given.

Run: `just test`
Expected: every suite passes.

- [ ] **Step 5: Commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && \
tasks done "$STEP2" "the session-archive units call %h/.local/bin/session-archive and name no checkout path" >/dev/null && \
git commit -q -m "feat(session-archive): units call the linked tool, never the checkout (tack-8b7a28)" -- systemd/user/session-archive-capture.service systemd/user/session-archive-prune.service tools/test_session_archive_units.py "tasks/$STEP2.md" && \
git rev-parse HEAD > "$STATE/task2-commit" && git log --oneline -1
```

---

### Task 3: Host step (gated): the link, then the units, on both hosts

Nothing that changes a host runs before the user approves it at that moment. One approval covers both hosts and both halves, and is asked once. The order is fixed: the link exists on both hosts before any host's units name it.

The worktree and its state directory are in this host's own storage and do not sync, so nothing that runs on the second host may source the environment file or enter `$WT`. Two scripts are written here and sent there; each uses only that host's registered main checkout. Every task record is written on this host.

- [ ] **Step 1: Write the scripts, record the second host, preview this host read-only, and park**

The second host's name comes from `tailscale status` or the user's memory note, and goes only into the ignored state directory:

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && tasks start "$STEP3" >/dev/null && \
need TASK1_COMMIT TASK2_COMMIT && printf '%s\n' "<the second host>" > "$STATE/second-host" && \
cat > "$STATE/host-link.sh" <<'EOF' &&
# The session-archive link on this host. No argument: preview only. "apply": apply and check.
export PATH="$HOME/.local/bin:$HOME/bin:$PATH"
cd "$(tasks root tack-8b7a28 --pretty)" || exit 1
grep -q '^"~/.local/bin/session-archive"' links.toml || { echo "links.toml has no session-archive entry yet (is the sync up to date?)"; exit 1; }
LOG="$(mktemp)"
if [ "$1" != apply ]; then
  just link > "$LOG" 2>&1; rc=$?
  grep -v -e '^ok' -e '^tools/' "$LOG"; echo "preview exit: $rc"; exit "$rc"
fi
just link --apply > "$LOG" 2>&1 || { tail -n 5 "$LOG"; echo "apply failed; full output in $LOG"; exit 1; }
just link-check > "$LOG" 2>&1 || { tail -n 5 "$LOG"; echo "link-check failed; full output in $LOG"; exit 1; }
~/.local/bin/session-archive --help > /dev/null || { echo "session-archive does not answer through its link"; exit 1; }
echo "converged; session-archive answers through its link"
EOF
cat > "$STATE/host-units.sh" <<'EOF' &&
# After the units change reached this host: reload, show what the capture unit runs,
# and run it once where its timer is enabled.
export PATH="$HOME/.local/bin:$HOME/bin:$PATH"
cd "$(tasks root tack-8b7a28 --pretty)" || exit 1
grep -q '%h/.local/bin/session-archive capture' systemd/user/session-archive-capture.service || { echo "the unit change has not arrived (is the sync up to date?)"; exit 1; }
[ -x ~/.local/bin/session-archive ] || { echo "~/.local/bin/session-archive is missing: run the link step first"; exit 1; }
systemctl --user daemon-reload || exit 1
systemctl --user show session-archive-capture.service -p ExecStart --value | grep -q '\.local/bin/session-archive capture' || { echo "systemd still runs the old command"; exit 1; }
for unit in capture prune; do echo "session-archive-$unit.timer: $(systemctl --user is-enabled session-archive-$unit.timer 2>&1)"; done
if [ "$(systemctl --user is-enabled session-archive-capture.timer 2>/dev/null)" = enabled ]; then
  systemctl --user start session-archive-capture.service || { journalctl --user -u session-archive-capture.service -n 20 --no-pager; exit 1; }
  echo "capture run: $(systemctl --user show session-archive-capture.service -p Result --value)"
else
  echo "capture timer not enabled here: no manual run"
fi
EOF
git -C "$TACK" merge-base --is-ancestor "$TASK1_COMMIT" "$BRANCH" && echo "scripts written; Task 1 at ${TASK1_COMMIT:0:7}, Task 2 at ${TASK2_COMMIT:0:7}"
```

Replace `<the second host>` with the name before running. Then park:

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && \
tasks park "$STEP3" "User approves the session-archive host step on both hosts, in this order: merge Task 1 to main; on this host and then the second host, preview the link (expected: one create, ~/.local/bin/session-archive) and apply it; merge Task 2 to main; on each host, daemon-reload and a manual capture run where its timer is enabled. Then Task 3 Step 2." --waiting-on user --reason approval >/dev/null && \
git commit -q -m "chore(tasks): park the session-archive host step for approval (tack-8b7a28)" -- "tasks/$STEP3.md"
```

- [ ] **Step 2: After the approval: merge Task 1, then the link on this host**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && tasks start "$STEP3" >/dev/null && need TASK1_COMMIT && \
cd "$TACK" && [ -z "$(git status --porcelain -- links.toml tools/test_session_archive_units.py)" ] && \
git merge --no-ff "$TASK1_COMMIT" -m "Merge branch '$BRANCH' (the session-archive link)" && bash "$STATE/host-link.sh"
```

Expected: exactly one line, `create	~/.local/bin/session-archive	…`, then `preview exit: 0`. A `skipped` line for an absent harness home is not a change. Anything else (a `refuse`, a `repoint`, a second `create`, a non-zero exit): stop and report; do not apply. Then:

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && bash "$STATE/host-link.sh" apply
```

Expected: `converged; session-archive answers through its link`.

- [ ] **Step 3: The link on the second host**

The file sync carries main's `links.toml` there. The script refuses until it has arrived; rerun it then. Over SSH with IPv4 forced:

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && need SECOND && ssh -4 -o BatchMode=yes "$SECOND" 'bash -s' < "$STATE/host-link.sh"
```

Expected: the same single `create` line and `preview exit: 0`. Then the same command with `'bash -s apply'` in place of `'bash -s'`, expecting `converged; session-archive answers through its link`.

- [ ] **Step 4: Merge Task 2, then the units on both hosts**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && need TASK2_COMMIT && \
cd "$TACK" && [ -z "$(git status --porcelain -- systemd tools/test_session_archive_units.py)" ] && \
git merge --no-ff "$TASK2_COMMIT" -m "Merge branch '$BRANCH' (the units call the linked tool)" && bash "$STATE/host-units.sh"
```

Expected on this host: `session-archive-capture.timer: enabled`, `session-archive-prune.timer: linked`, then after about a minute `capture run: success`. A failed run prints the unit's last journal lines. Stop and report it: the previous unit text is one `git revert` of the merge away, followed by `systemctl --user daemon-reload`.

Then on the second host, once the sync has carried the unit change (the script refuses until it has):

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && need SECOND && ssh -4 -o BatchMode=yes "$SECOND" 'bash -s' < "$STATE/host-units.sh"
```

Expected: the timers' states there, then either `capture run: success` or `capture timer not enabled here: no manual run`. If `systemctl --user` cannot reach the user manager over SSH, the user runs the script there in a terminal.

- [ ] **Step 5: Record**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && \
tasks done "$STEP3" "session-archive host step: link applied and units reloaded on both hosts; this host's capture: <result>; second host: <timer states, capture result or none>" >/dev/null && \
git commit -q -m "chore(tasks): the session-archive host step done (tack-8b7a28)" -- "tasks/$STEP3.md" && git log --oneline -1
```

---

### Task 4: The cutover tool takes a list of repositories

The September tool hardcodes exactly two repositories (`--ai`, `--ops`), retargets only in ops, checks claims only in ops, applies the links inside `apply`, and names `tack-link` in six places. This task replaces the tool's command line and snapshot layout. The tests are rewritten with it: every September test keeps its meaning, under the new options.

**Files:**
- Modify: `tools/rename-cutover` (replaced whole)
- Test: `tools/test_rename_cutover.py` (replaced whole)

**Interfaces:**
- Produces, as commands:
  - `rename-cutover save --snapshot DIR --checkout ROOT --repo ROOT [--repo ROOT …] --new-root PATH --old OLD --new NEW [--link-tool REL]` (the default for `--link-tool` is `tools/tack-link` until Task 6);
  - `rename-cutover apply --snapshot DIR` (`tasks rename`, the move of the checkout and its storage, `work-link --ensure .worktrees`, `tasks init --prefix NEW --force`);
  - `rename-cutover retarget --snapshot DIR --repo ROOT [--forward]`;
  - `rename-cutover link --snapshot DIR`;
  - `rename-cutover verify --snapshot DIR`;
  - `rename-cutover rollback --snapshot DIR`.

  Exit 0, or 1 with `rename-cutover: <step>: <why>`.
- Produces, as `meta.json`: `checkout` and each of `repos` as `{root, head, branch}`; `new_root`, `old`, `new`, `link_tool`, `home`, `config`, `state`, `worktrees_link`, `storage_old`, `storage_new`. `storage_new` is named after the new root's directory, as `work-link` names storage.
- Produces, as functions Task 5 builds on: `registry_view(path, old, new)`, `guard(meta, snap)`, `save(args)`, `rollback(args)`, `checkout_now(meta)`, `link_tool(root, meta)`, `run(*cmd, cwd=None)`, `class Stop`. The test module's `Sandbox(tmp, repos=("ops",))`, with `.save()`, `.save_args()`, `.forward()`, `.cutover(*args, check=True)`, `.commit(root, message)`, `.depend_on_checkout(root)`, `.fingerprint()`, and the fixtures `box` and `box2`.

- [ ] **Step 1: Start the record and replace the tests**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && tasks start "$STEP4" >/dev/null && echo started
```

Replace the whole of `tools/test_rename_cutover.py` with:

```python
"""rename-cutover saves, guards and restores a rename in a sandbox that shares no live state."""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

TOOLS = Path(__file__).parent
LINK_TOOL = "tools/tack-link"


def load_cutover():
    """Import tools/rename-cutover as a module, for unit-testing its functions directly.

    The file has no .py suffix, so the loader must be given explicitly."""
    path = TOOLS / "rename-cutover"
    loader = importlib.machinery.SourceFileLoader("rename_cutover", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def task_id(output):
    added = json.loads(output)
    return added.get("id") or added["task"]["id"]


class Sandbox:
    """The September rename's shape: checkout `ai` (prefix ai) becomes `tack`, and the
    cutover retargets in the repositories named by `repos` (ops, unless a test asks)."""

    def __init__(self, tmp, repos=("ops",)):
        self.tmp = tmp
        self.env = {**os.environ, "HOME": str(tmp / "home"), "XDG_CONFIG_HOME": str(tmp / "cfg"),
                    "XDG_STATE_HOME": str(tmp / "state"), "GIT_AUTHOR_NAME": "t",
                    "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        self.env.pop("WORK_ROOT", None)
        for d in ("home", "cfg", "state"):
            (tmp / d).mkdir()
        self.sync = tmp / "sync"
        self.old, self.new = "ai", "tack"
        self.checkout, self.new_root = self.sync / "ai", self.sync / "tack"
        self.repos = [self.sync / name for name in repos]
        self.ops = self.repos[0]
        self.snapshot = tmp / "snap"

    def run(self, *cmd, cwd=None, check=True, env=None):
        result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env or self.env, text=True,
                                capture_output=True)
        if check and result.returncode != 0:
            raise AssertionError(f"{cmd}: {result.stdout}{result.stderr}")
        return result

    def repo(self, path, prefix):
        path.mkdir(parents=True)
        self.run("git", "init", "-q", "-b", "main", path)
        self.run("tasks", "init", "--prefix", prefix, cwd=path)

    def commit(self, root, message):
        self.run("git", "add", "-A", cwd=root)
        self.run("git", "commit", "-qm", message, cwd=root)

    def build(self):
        self.repo(self.checkout, self.old)
        (self.checkout / "tools").mkdir()
        for name in ("tack-link", "rename-cutover"):
            shutil.copy2(TOOLS / name, self.checkout / "tools" / name)
        (self.checkout / "agents").mkdir()
        (self.checkout / "agents" / "README").write_text("x\n")
        (self.checkout / "links.toml").write_text('[required]\n"~/.agents" = "agents"\n')
        (self.checkout / ".gitignore").write_text(".worktrees\n")
        tid = task_id(self.run("tasks", "add", "one", "--process", "direct", cwd=self.checkout).stdout)
        self.run("tasks", "add", "two", "--process", "direct", cwd=self.checkout)
        self.run("tasks", "start", tid, cwd=self.checkout)
        self.run("tasks", "park", tid, "next", cwd=self.checkout)
        storage = self.sync.parent / ".dropbox-work" / self.checkout.name / ".worktrees"
        storage.mkdir(parents=True)
        (self.checkout / ".worktrees").symlink_to(f"../../.dropbox-work/{self.checkout.name}/.worktrees")
        self.commit(self.checkout, "init")
        for root in self.repos:
            self.repo(root, root.name)
            self.commit(root, "init")
        self.run(self.checkout / "tools" / "tack-link", "--apply")
        return self

    def cutover(self, *args, check=True):
        tool = self.snapshot / "rename-cutover" if (self.snapshot / "rename-cutover").exists() \
            else self.checkout / "tools" / "rename-cutover"
        return self.run(tool, *args, check=check)

    def save_args(self):
        args = ["save", "--snapshot", self.snapshot, "--checkout", self.checkout,
                "--new-root", self.new_root, "--old", self.old, "--new", self.new,
                "--link-tool", LINK_TOOL]
        for root in self.repos:
            args += ["--repo", root]
        return args

    def save(self, check=True):
        return self.cutover(*self.save_args(), check=check)

    def forward(self):
        """The whole cutover up to the runbook's commits: apply, retarget everywhere, link."""
        self.cutover("apply", "--snapshot", self.snapshot)
        for root in self.repos:
            self.cutover("retarget", "--snapshot", self.snapshot, "--repo", root)
        self.cutover("link", "--snapshot", self.snapshot)

    def depend_on_checkout(self, root):
        """A task in `root` that depends on a checkout task, both committed. Returns
        (checkout id, dependent id)."""
        target = task_id(self.run("tasks", "add", "depended on", "--process", "direct",
                                  cwd=self.checkout).stdout)
        self.commit(self.checkout, "a task to depend on")
        dependent = task_id(self.run("tasks", "add", "depends", "--process", "direct", cwd=root).stdout)
        self.run("tasks", "dep", dependent, "--on", target, cwd=root)
        self.commit(root, "depend on the checkout")
        return target, dependent

    def fingerprint(self):
        """Everything rollback must restore, as comparable data."""
        def tree(root):
            return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
                    if p.is_file() and ".git" not in p.parts}
        return {"checkout": tree(self.checkout), **{r.name: tree(r) for r in self.repos},
                "cfg": tree(self.tmp / "cfg" / "tasks"), "state": tree(self.tmp / "state" / "tasks"),
                "worktrees": os.readlink(self.checkout / ".worktrees"),
                "agents": os.path.realpath(self.tmp / "home" / ".agents")}


@pytest.fixture
def box(tmp_path):
    return Sandbox(tmp_path).build()


@pytest.fixture
def box2(tmp_path):
    """Two retargeted repositories, ops and lore."""
    return Sandbox(tmp_path, repos=("ops", "lore")).build()


# --- save ---------------------------------------------------------------------


def test_save_refuses_with_a_live_claim(box):
    tid = task_id(box.run("tasks", "add", "three", "--process", "direct", cwd=box.checkout).stdout)
    box.run("tasks", "start", tid, cwd=box.checkout)
    result = box.save(check=False)
    assert result.returncode == 1
    assert "live claim" in result.stderr


def test_save_refuses_a_dirty_tree(box):
    (box.ops / "stray").write_text("x\n")
    result = box.save(check=False)
    assert result.returncode == 1
    assert "not clean" in result.stderr


def test_save_refuses_a_dirty_tree_in_any_repository(box2):
    (box2.repos[1] / "stray").write_text("x\n")
    result = box2.save(check=False)
    assert result.returncode == 1
    assert f"{box2.repos[1]} is not clean" in result.stderr


def test_save_refuses_a_snapshot_path_inside_the_checkout(box):
    box.snapshot = box.checkout / "snap"
    result = box.save(check=False)
    assert result.returncode == 1
    assert "lies inside checkout" in result.stderr
    assert not (box.checkout / "snap").exists()


def test_save_resolves_new_roots_parent_through_a_symlink(box, tmp_path):
    alias = tmp_path / "alias"
    alias.symlink_to(box.sync)
    box.new_root = alias / "tack"
    box.save()
    meta = json.loads((box.snapshot / "meta.json").read_text())
    assert meta["new_root"] == str((box.sync / "tack").resolve())


def test_save_refuses_the_checkout_named_as_a_repository(box):
    box.repos.append(box.checkout)
    result = box.save(check=False)
    assert result.returncode == 1
    assert "never the checkout" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_repository_named_twice(box):
    box.repos.append(box.ops)
    result = box.save(check=False)
    assert result.returncode == 1
    assert "name each --repo once" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_link_tool_that_is_not_there(box):
    args = [str(a) for a in box.save_args()]
    args[args.index("--link-tool") + 1] = "tools/no-such-tool"
    result = box.cutover(*args, check=False)
    assert result.returncode == 1
    assert "no link tool at" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_branch_with_commits_main_lacks(box):
    """Merged after the rename, such a branch would bring old-prefix task files back."""
    box.run("git", "checkout", "-qb", "feature", cwd=box.checkout)
    (box.checkout / "agents" / "more").write_text("y\n")
    box.commit(box.checkout, "unmerged work")
    box.run("git", "checkout", "-q", "main", cwd=box.checkout)
    result = box.save(check=False)
    assert result.returncode == 1
    assert "feature" in result.stderr
    assert not box.snapshot.exists()


def test_save_accepts_a_branch_main_already_holds(box):
    box.run("git", "branch", "merged", cwd=box.checkout)
    box.save()


def test_save_refuses_a_dead_claim_in_any_retargeted_repository(box2):
    """`tasks dep` prunes dead claims from the project it writes in, so a dead claim in a
    retargeted repository would be dropped by retarget and then stop the guard. The
    claim is dead the moment it is written: its session's pid does not exist."""
    lore = box2.repos[1]
    tid = task_id(box2.run("tasks", "add", "orphaned claim", "--process", "direct", cwd=lore).stdout)
    ghost = {**box2.env, "TASKS_SESSION": "ghost", "TASKS_SESSION_PID": "999999"}
    box2.run("tasks", "start", tid, cwd=lore, env=ghost)
    box2.commit(lore, "start under a dead session")
    claims = json.loads(box2.run("tasks", "claims").stdout)["claims"]
    assert any(c["id"] == tid and not c["live"] for c in claims), claims
    result = box2.save(check=False)
    assert result.returncode == 1
    assert "a retargeted repository has claims" in result.stderr and tid in result.stderr
    assert not box2.snapshot.exists()


def test_save_records_every_repository(box2):
    box2.save()
    meta = json.loads((box2.snapshot / "meta.json").read_text())
    assert meta["checkout"]["root"] == str(box2.checkout)
    assert [r["root"] for r in meta["repos"]] == [str(r) for r in box2.repos]
    assert all(r["branch"] == "refs/heads/main" and len(r["head"]) == 40 for r in meta["repos"])
    assert meta["link_tool"] == LINK_TOOL


# --- apply, retarget, link, verify ---------------------------------------------


def test_apply_renames_and_moves_but_neither_retargets_nor_links(box):
    box.depend_on_checkout(box.ops)
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    assert not box.checkout.exists()
    assert any(p.name.startswith("tack-") for p in (box.new_root / "tasks").glob("*.md"))
    registry = (box.tmp / "cfg" / "tasks" / "projects.toml").read_text()
    assert f'tack = "{box.new_root}"' in registry and 'ai = "tack"' in registry
    assert (box.new_root / ".worktrees").resolve() == \
        (box.sync.parent / ".dropbox-work" / "tack" / ".worktrees").resolve()
    assert "retired_prefix" in box.run("tasks", "check", cwd=box.ops).stdout
    assert not os.path.exists(box.tmp / "home" / ".agents")     # still names the old path


def test_the_whole_cutover_retargets_links_and_verifies(box2):
    hexes = {}
    for root in box2.repos:
        target, dependent = box2.depend_on_checkout(root)
        hexes[root] = (target.split("-", 1)[1], dependent)
    box2.save()
    box2.cutover("apply", "--snapshot", box2.snapshot)
    for root in box2.repos:
        result = box2.cutover("retarget", "--snapshot", box2.snapshot, "--repo", root)
        hex_, dependent = hexes[root]
        assert f"retarget: {dependent}: ai-{hex_} -> tack-{hex_}" in result.stdout
        assert box2.run("tasks", "check", cwd=root).stdout == ""
    box2.cutover("link", "--snapshot", box2.snapshot)
    assert os.path.realpath(box2.tmp / "home" / ".agents") == str((box2.new_root / "agents").resolve())
    box2.cutover("verify", "--snapshot", box2.snapshot)


def test_verify_fails_while_a_repository_still_names_a_retired_id(box2):
    box2.depend_on_checkout(box2.repos[1])
    box2.save()
    box2.cutover("apply", "--snapshot", box2.snapshot)
    box2.cutover("retarget", "--snapshot", box2.snapshot, "--repo", box2.repos[0])
    box2.cutover("link", "--snapshot", box2.snapshot)
    result = box2.cutover("verify", "--snapshot", box2.snapshot, check=False)
    assert result.returncode == 1
    assert f"tasks check reports findings in {box2.repos[1]}" in result.stderr


def test_retarget_refuses_a_repository_outside_the_snapshot(box):
    """Rollback could not restore it; nothing is written there."""
    outside = box.sync / "relay"
    box.repo(outside, "relay")
    box.commit(outside, "init")
    _, dependent = box.depend_on_checkout(outside)
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    before = (outside / "tasks" / f"{dependent}.md").read_bytes()
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--repo", outside, check=False)
    assert result.returncode == 1
    assert "not in the snapshot" in result.stderr and "--forward" in result.stderr
    assert (outside / "tasks" / f"{dependent}.md").read_bytes() == before
    box.cutover("retarget", "--snapshot", box.snapshot, "--repo", outside, "--forward")
    assert box.run("tasks", "check", cwd=outside).stdout == ""


def test_link_refuses_before_apply(box):
    box.save()
    result = box.cutover("link", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "run apply first" in result.stderr


def test_apply_refuses_when_new_root_already_exists(box):
    box.save()
    box.new_root.mkdir()
    result = box.cutover("apply", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert box.checkout.exists()
    assert box.new_root.is_dir() and not (box.new_root / "tasks").exists()


def test_apply_refuses_when_storage_new_parent_already_exists(box):
    box.save()
    (box.sync.parent / ".dropbox-work" / "tack").mkdir(parents=True)
    result = box.cutover("apply", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert box.checkout.exists()
    assert not box.new_root.exists()


def test_the_storage_follows_the_checkout_directory_not_the_prefix(box):
    """work-link names storage after the directory; a new root whose name differs from
    the new prefix moves the storage to the directory's name."""
    box.new_root = box.sync / "renamed"
    box.save()
    meta = json.loads((box.snapshot / "meta.json").read_text())
    assert meta["storage_new"] == str((box.sync.parent / ".dropbox-work" / "renamed" / ".worktrees").resolve())
    box.forward()
    box.cutover("verify", "--snapshot", box.snapshot)


# --- rollback -----------------------------------------------------------------


def test_rollback_before_commit_restores_everything(box2):
    box2.depend_on_checkout(box2.repos[1])
    before = box2.fingerprint()
    box2.save()
    box2.forward()
    assert (box2.new_root / "tasks").is_dir() and not box2.checkout.exists()
    box2.cutover("rollback", "--snapshot", box2.snapshot)
    assert box2.fingerprint() == before
    for root in (box2.checkout, *box2.repos):
        assert box2.run("tasks", "check", cwd=root).stdout == ""
        assert box2.run("git", "status", "--porcelain", cwd=root).stdout == ""


def test_rollback_after_commit_restores_everything(box2):
    for root in box2.repos:
        box2.depend_on_checkout(root)
    before = box2.fingerprint()
    box2.save()
    box2.forward()
    box2.commit(box2.new_root, "rename")
    for root in box2.repos:
        box2.commit(root, "retarget")
    box2.cutover("rollback", "--snapshot", box2.snapshot)
    assert box2.fingerprint() == before
    assert all((box2.snapshot / f"rollback-{r.name}-1.patch").read_text().strip() for r in box2.repos)


def test_rollback_after_partial_apply(box):
    before = box.fingerprint()
    box.save()
    box.run("tasks", "rename", "ai", "tack", cwd=box.checkout)
    os.rename(box.checkout, box.new_root)      # interrupted before storage, init --force, links
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_rollback_after_rename_stopped_midway(box):
    """A rename stopped after moving its files leaves rename/ai.toml; rollback accepts
    this rename's own inventory and restores everything."""
    before = box.fingerprint()
    box.save()
    env = {**box.env, "TASKS_RENAME_STOP_AFTER": "files"}
    subprocess.run(["tasks", "rename", "ai", "tack"], cwd=box.checkout, env=env, text=True, capture_output=True)
    assert (box.tmp / "state" / "tasks" / "rename" / "ai.toml").exists()
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_rollback_stops_on_foreign_untracked_file(box):
    """The check runs before move_back: nothing has moved when it stops."""
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    (box.new_root / "tasks" / "note.md").write_text("mine\n")
    registry_before = (box.tmp / "cfg" / "tasks" / "projects.toml").read_text()
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "tasks/note.md" in result.stderr
    assert (box.new_root / "tasks" / "note.md").read_text() == "mine\n"
    assert box.new_root.exists() and not box.checkout.exists()
    assert (box.tmp / "cfg" / "tasks" / "projects.toml").read_text() == registry_before


def test_rollback_stops_on_an_untracked_file_in_any_repository(box2):
    box2.save()
    box2.cutover("apply", "--snapshot", box2.snapshot)
    (box2.repos[1] / "stray").write_text("mine\n")
    result = box2.cutover("rollback", "--snapshot", box2.snapshot, check=False)
    assert result.returncode == 1
    assert f"{box2.repos[1]} has untracked files" in result.stderr
    assert box2.new_root.exists() and not box2.checkout.exists()


def test_rollback_stops_on_a_nested_leftover(box):
    """git ls-files --others must see exactly tasks/<new>-<hex>.md, one level deep."""
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    nested = box.new_root / "tasks" / "x"
    nested.mkdir()
    (nested / "tack-deadbeef.md").write_text("mine\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "tasks/x/tack-deadbeef.md" in result.stderr
    assert box.new_root.exists() and not box.checkout.exists()


def test_rollback_stops_when_home_does_not_match_the_snapshot(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    other_home = box.tmp / "other-home"
    other_home.mkdir()
    env = {**box.env, "HOME": str(other_home)}
    result = box.run(box.snapshot / "rename-cutover", "rollback", "--snapshot", box.snapshot,
                     check=False, env=env)
    assert result.returncode == 1
    assert "environment does not match the snapshot" in result.stderr and "home" in result.stderr
    assert box.new_root.exists() and not box.checkout.exists()


def test_rollback_stops_when_a_repository_changed_branch(box2):
    box2.save()
    box2.cutover("apply", "--snapshot", box2.snapshot)
    box2.run("git", "checkout", "-qb", "other", cwd=box2.repos[1])
    result = box2.cutover("rollback", "--snapshot", box2.snapshot, check=False)
    assert result.returncode == 1
    assert "other" in result.stderr
    assert box2.new_root.exists() and not box2.checkout.exists()


def test_rollback_saves_a_patch_of_edits_since_save(box):
    """git reset --hard is destructive; a tracked edit made after save must survive as a patch."""
    box.save()
    config_file = box.ops / "tasks" / ".config.toml"
    config_file.write_text(config_file.read_text() + "# stray edit\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot)
    patch = box.snapshot / "rollback-ops-1.patch"
    assert "stray edit" in patch.read_text()
    assert f"changes since save kept in {patch}" in result.stderr
    assert box.run("git", "status", "--porcelain", cwd=box.ops).stdout == ""


def test_rollback_refuses_when_the_worktrees_link_is_a_real_file(box):
    """move_back must not delete a real file sitting where the managed symlink goes."""
    box.save()
    link = box.checkout / ".worktrees"
    link.unlink()
    link.write_text("mine\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "not a link" in result.stderr
    assert link.is_file() and not link.is_symlink() and link.read_text() == "mine\n"


def test_rollback_refuses_when_the_worktrees_link_is_a_real_directory(box):
    box.save()
    link = box.checkout / ".worktrees"
    link.unlink()
    link.mkdir()
    (link / "note.txt").write_text("mine\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "not a link" in result.stderr
    assert link.is_dir() and not link.is_symlink() and (link / "note.txt").read_text() == "mine\n"


def test_rollback_tolerates_empty_foreign_claims_files(box):
    """A `tasks` command run elsewhere during the window can create empty
    claims/<prefix>.{toml,lock} files; an empty claims file records no claim."""
    before = box.fingerprint()
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    claims = box.tmp / "state" / "tasks" / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    (claims / "ops.lock").write_text("")
    (claims / "ops.toml").write_text("")
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


# --- the guard ----------------------------------------------------------------


def test_guard_stops_on_foreign_registry_change(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    registry = box.tmp / "cfg" / "tasks" / "projects.toml"
    registry.write_text(registry.read_text().replace("[projects]\n", '[projects]\nzz = "/elsewhere"\n'))
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "guard" in result.stderr and "zz" in result.stderr
    assert box.new_root.exists()                      # nothing was moved back


def test_guard_rejects_an_inventory_for_another_root(box):
    """Same prefixes, a root that merely starts with the checkout's path: not ours."""
    box.save()
    env = {**box.env, "TASKS_RENAME_STOP_AFTER": "files"}
    subprocess.run(["tasks", "rename", "ai", "tack"], cwd=box.checkout, env=env, text=True, capture_output=True)
    inventory = box.tmp / "state" / "tasks" / "rename" / "ai.toml"
    inventory.write_text(inventory.read_text().replace(f'"{box.checkout}"', f'"{box.checkout}-other"'))
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1 and "inventory" in result.stderr
    assert inventory.exists()                         # the foreign inventory was not deleted


def test_guard_rejects_a_foreign_inventory(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    inventory = box.tmp / "state" / "tasks" / "rename" / "ai.toml"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text('source = "ai"\ntarget = "tack"\nroot = "/elsewhere"\n')
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1 and "inventory" in result.stderr


def test_guard_stops_on_a_nonempty_foreign_claims_file(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    claims = box.tmp / "state" / "tasks" / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    (claims / "ops.toml").write_text('[claim]\nid = "ops-000000"\n')
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "guard" in result.stderr and "claims/ops.toml" in result.stderr
    assert box.new_root.exists() and not box.checkout.exists()


def test_guard_stops_when_a_claims_file_is_emptied_live(box):
    """Only a file empty on both sides, or empty live with the saved copy absent, is
    tolerated; a saved claim found empty live is a change."""
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    saved_claims = box.snapshot / "state" / "claims"
    saved_claims.mkdir(parents=True, exist_ok=True)
    (saved_claims / "ops.toml").write_text('[claims.ops-000000]\nowner = "x"\n')
    live_claims = box.tmp / "state" / "tasks" / "claims"
    live_claims.mkdir(parents=True, exist_ok=True)
    (live_claims / "ops.toml").write_text("")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "guard" in result.stderr and "claims/ops.toml" in result.stderr
    assert box.new_root.exists() and not box.checkout.exists()


# --- move_back and save_reset_patch, directly ----------------------------------


def meta_for(checkout, new_root, storage_old=None, storage_new=None, link=None):
    return {"checkout": {"root": str(checkout)}, "new_root": str(new_root),
            "storage_old": str(storage_old) if storage_old else None,
            "storage_new": str(storage_new) if storage_new else None, "worktrees_link": link}


def test_move_back_stops_when_both_checkout_and_new_root_exist(tmp_path):
    cutover = load_cutover()
    checkout, new_root = tmp_path / "ai", tmp_path / "tack"
    checkout.mkdir()
    new_root.mkdir()
    with pytest.raises(cutover.Stop, match="both"):
        cutover.move_back(meta_for(checkout, new_root))
    assert checkout.is_dir() and new_root.is_dir()


def test_move_back_stops_when_neither_checkout_nor_new_root_exist(tmp_path):
    cutover = load_cutover()
    with pytest.raises(cutover.Stop, match="neither"):
        cutover.move_back(meta_for(tmp_path / "ai", tmp_path / "tack"))


def test_move_back_stops_when_both_storage_dirs_exist(tmp_path):
    cutover = load_cutover()
    checkout = tmp_path / "ai"
    checkout.mkdir()
    storage_old, storage_new = tmp_path / "dw" / "ai" / ".worktrees", tmp_path / "dw" / "tack" / ".worktrees"
    storage_old.mkdir(parents=True)
    storage_new.mkdir(parents=True)
    with pytest.raises(cutover.Stop, match="both"):
        cutover.move_back(meta_for(checkout, tmp_path / "tack", storage_old, storage_new, "../../dw/ai/.worktrees"))
    assert storage_old.parent.is_dir() and storage_new.parent.is_dir()


def test_move_back_stops_when_neither_storage_dir_exists(tmp_path):
    cutover = load_cutover()
    checkout = tmp_path / "ai"
    checkout.mkdir()
    storage_old, storage_new = tmp_path / "dw" / "ai" / ".worktrees", tmp_path / "dw" / "tack" / ".worktrees"
    with pytest.raises(cutover.Stop, match="neither"):
        cutover.move_back(meta_for(checkout, tmp_path / "tack", storage_old, storage_new, "../../dw/ai/.worktrees"))


def test_save_reset_patch_never_overwrites_an_earlier_patch(tmp_path):
    cutover = load_cutover()
    root = tmp_path / "repo"
    root.mkdir()
    git = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "a.txt").write_text("zero\n")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    head = subprocess.run([*git, "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()
    snap = tmp_path / "snap"
    snap.mkdir()
    (root / "a.txt").write_text("one\n")
    cutover.save_reset_patch(root, head, snap, "ai")
    first = snap / "rollback-ai-1.patch"
    first_content = first.read_text()
    assert "one" in first_content
    (root / "a.txt").write_text("two\n")
    cutover.save_reset_patch(root, head, snap, "ai")
    assert first.read_text() == first_content
    assert "two" in (snap / "rollback-ai-2.patch").read_text()


# --- the second host ----------------------------------------------------------


def test_second_host_adopts_the_rename(box):
    """A second host, sharing the synced checkout, adopts the first host's rename."""
    second = {**box.env, "XDG_CONFIG_HOME": str(box.tmp / "cfg2"), "XDG_STATE_HOME": str(box.tmp / "state2")}

    def run2(*cmd, cwd):
        return box.run(*cmd, cwd=cwd, env=second).stdout

    run2("tasks", "init", "--prefix", "ai", "--force", cwd=box.checkout)
    tid = task_id(run2("tasks", "add", "on the second host", "--process", "direct", cwd=box.checkout))
    run2("tasks", "start", tid, cwd=box.checkout)
    run2("tasks", "park", tid, "resume here", cwd=box.checkout)
    box.commit(box.checkout, "second host work")

    box.save()
    box.forward()
    box.commit(box.new_root, "rename")

    def first_host():
        return {str(p): p.read_bytes() for d in ("cfg", "state") for p in sorted((box.tmp / d).rglob("*"))
                if p.is_file()}

    first = first_host()
    run2("tasks", "rename", "ai", "tack", "--adopt", cwd=box.new_root)
    registry = (box.tmp / "cfg2" / "tasks" / "projects.toml").read_text()
    assert f'tack = "{box.new_root}"' in registry and 'ai = "tack"' in registry
    hex_ = tid.split("-", 1)[1]
    assert json.loads(run2("tasks", "show", f"ai-{hex_}", cwd=box.new_root))
    parked = json.loads(run2("tasks", "list", "--parked", cwd=box.new_root))
    assert f"tack-{hex_}" in [t["id"] for t in parked["tasks"]]
    assert first_host() == first
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run -q --with pytest pytest tools/test_rename_cutover.py -q`
Expected: 43 failed, 1 passed. The unit test of `save_reset_patch` passes; every other test fails on `--checkout`, `--repo` or `--link-tool` (argparse's `unrecognized arguments`) or on `meta_for`'s new layout.

- [ ] **Step 3: Replace the tool**

Replace the whole of `tools/rename-cutover` (keep it executable) with:

```python
#!/usr/bin/env python3
"""A project rename's cutover: save originals, apply, retarget, link, verify, roll back.

Written for docs/specs/2026-09-27-rename-to-tack-design.md and made general by
docs/specs/2026-10-06-rename-to-hq-design.md §3.1. Every path comes from the command line
or the snapshot's meta.json, and every tasks call inherits HOME, XDG_CONFIG_HOME and
XDG_STATE_HOME, so a sandbox rehearsal runs exactly this code. `tasks rename` is
irreversible; rollback restores the saved originals and stops, leaving the state for a
person, at the first check that fails.

The renamed project is the checkout; the other repositories are the ones the cutover
retargets in, and the only ones rollback resets. `apply` renames and moves, `retarget`
fixes one repository's dependencies on retired ids, `link` applies the home links, and
`verify` checks the result: the runbook commits between them.
"""
import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


class Stop(Exception):
    pass


def run(*cmd, cwd=None):
    result = subprocess.run([str(c) for c in cmd], cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise Stop(f"{' '.join(map(str, cmd))}: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def xdg(name, default):
    return Path(os.environ.get(name) or Path.home() / default)


def porcelain(root):
    return run("git", "-C", root, "status", "--porcelain", "--untracked-files=all").splitlines()


def branch_of(root):
    """`git symbolic-ref -q HEAD`: the current branch, or "" when detached."""
    result = subprocess.run(["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"], text=True,
                            capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def record(root):
    """A repository as save finds it: its path, its commit and its branch."""
    return {"root": str(root), "head": run("git", "-C", root, "rev-parse", "HEAD").strip(),
            "branch": branch_of(root)}


def load_meta(snap):
    return json.loads((Path(snap) / "meta.json").read_text())


def checkout_now(meta):
    """The checkout's path at this moment: the new root once apply has moved it."""
    new_root = Path(meta["new_root"])
    return new_root if new_root.exists() else Path(meta["checkout"]["root"])


def link_tool(root, meta):
    return Path(root) / meta["link_tool"]


def check_environment(command, meta):
    """A rehearsal snapshot and a live one both carry meta.json; refuse to run one
    against the other host's HOME/XDG dirs rather than silently touching the wrong state."""
    checks = {
        "home": Path.home().resolve() == Path(meta["home"]).resolve(),
        "config": (xdg("XDG_CONFIG_HOME", ".config") / "tasks").resolve() == Path(meta["config"]).resolve(),
        "state": (xdg("XDG_STATE_HOME", ".local/state") / "tasks").resolve() == Path(meta["state"]).resolve(),
    }
    bad = [name for name, ok in checks.items() if not ok]
    if bad:
        raise Stop(f"{command}: environment does not match the snapshot ({', '.join(bad)})")


def check_branches(meta):
    """The current branch of each repository, checked before any mutation: rollback must
    not reset a branch a person has since switched away from."""
    pairs = [(checkout_now(meta), meta["checkout"]["branch"])]
    pairs += [(Path(r["root"]), r["branch"]) for r in meta["repos"]]
    for root, expected in pairs:
        current = branch_of(root)
        if current != expected:
            raise Stop(f"rollback: {root} is on {current or '(detached)'}, "
                       f"expected {expected or '(detached)'}")


def link_report(tool):
    result = subprocess.run([str(tool)], text=True, capture_output=True)
    if result.returncode not in (0, 1):
        raise Stop(f"{tool.name}: {result.stderr.strip()}")
    return result.stdout


def project_prefix(root):
    return tomllib.loads((Path(root) / "tasks" / ".config.toml").read_text())["prefix"]


def unmerged_branches(root):
    """Local branches holding commits the current branch lacks. Merged after the rename,
    such a branch would bring old-prefix task files back."""
    current = branch_of(root)
    names = run("git", "-C", root, "for-each-ref", "--format=%(refname)", "refs/heads").split()
    return [name.removeprefix("refs/heads/") for name in names
            if name != current and run("git", "-C", root, "rev-list", "--count", f"HEAD..{name}").strip() != "0"]


def preconditions(checkout, repos, tool):
    claims = json.loads(run("tasks", "claims"))["claims"]
    retargeted = {project_prefix(root) for root in repos}
    # A `tasks dep` write prunes dead claims from the project it writes in, and the guard
    # compares every other project's claims file byte for byte: a repository the cutover
    # retargets in must hold no claim at all, live or dead.
    held = [c["id"] for c in claims if c.get("prefix") in retargeted]
    if held:
        raise Stop(f"save: a retargeted repository has claims (live or dead): {', '.join(held)}; "
                   f"end or clear them first")
    live = [c for c in claims if c.get("live")]
    if live:
        raise Stop("preconditions: live claim(s): " + ", ".join(c["id"] for c in live))
    for root in (checkout, *repos):
        if porcelain(root):
            raise Stop(f"preconditions: {root} is not clean")
    if run("git", "-C", checkout, "worktree", "list", "--porcelain").count("\nworktree ") != 0:
        raise Stop(f"preconditions: {checkout} has more than one worktree")
    ahead = unmerged_branches(checkout)
    if ahead:
        raise Stop(f"preconditions: {checkout} has branches with commits its current branch lacks: "
                   f"{', '.join(ahead)}")
    check = subprocess.run([str(tool), "--check"], text=True, capture_output=True)
    if check.returncode != 0:
        raise Stop(f"preconditions: link drift:\n{check.stdout}")


def save(args):
    checkout, snap = Path(args.checkout).resolve(), Path(args.snapshot)
    repos = [Path(r).resolve() for r in args.repo]
    if checkout in repos or len(set(repos)) != len(repos):
        raise Stop("save: name each --repo once, and never the checkout")
    tool = checkout / args.link_tool
    if not tool.is_file():
        raise Stop(f"save: no link tool at {tool}")
    config, state = xdg("XDG_CONFIG_HOME", ".config") / "tasks", xdg("XDG_STATE_HOME", ".local/state") / "tasks"
    worktrees = checkout / ".worktrees"
    link_text = os.readlink(worktrees) if worktrees.is_symlink() else None
    storage_old = (checkout / link_text).resolve() if link_text else None
    protected = {"checkout": checkout, "config": config, "state": state,
                 **{f"repo {root}": root for root in repos}}
    if storage_old:
        protected["storage_old"] = storage_old
    snap_resolved = snap.resolve()
    for which, path in protected.items():
        path = path.resolve()
        if snap_resolved == path or path in snap_resolved.parents:
            raise Stop(f"save: snapshot {snap} lies inside {which}")
    preconditions(checkout, repos, tool)
    new_root = Path(args.new_root)
    new_root = new_root.parent.resolve() / new_root.name
    # work-link names a checkout's storage after the checkout's directory, not its prefix.
    storage_new = storage_old.parent.parent / new_root.name / storage_old.name if storage_old else None
    meta = {
        "checkout": record(checkout), "repos": [record(root) for root in repos],
        "new_root": str(new_root), "old": args.old, "new": args.new, "link_tool": args.link_tool,
        "home": str(Path.home()), "config": str(config), "state": str(state),
        "worktrees_link": link_text,
        "storage_old": str(storage_old) if storage_old else None,
        "storage_new": str(storage_new) if storage_new else None,
    }
    snap.mkdir(parents=True, exist_ok=False)
    shutil.copytree(config, snap / "config", symlinks=True)
    shutil.copytree(state, snap / "state", symlinks=True)
    (snap / "links.txt").write_text(link_report(tool))
    shutil.copy2(Path(__file__).resolve(), snap / "rename-cutover")
    (snap / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"saved {snap}")


def registry_view(path, old, new):
    """The registry with the renamed project's own keys removed, for the guard."""
    data = tomllib.loads(path.read_text()) if path.exists() else {}
    projects = {k: v for k, v in data.get("projects", {}).items() if k not in (old, new)}
    aliases = {k: v for k, v in data.get("aliases", {}).items() if k != old and v != new}
    return {**{k: v for k, v in data.items() if k not in ("projects", "aliases")},
            "projects": projects, "aliases": aliases}


def files(root, skip):
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} - skip


def validate_inventory(path, meta):
    """An interrupted `tasks rename` leaves rename/<old>.toml. It belongs to this cutover
    only when its source, target and root are exactly this rename's."""
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as error:
        raise Stop(f"guard: {path} is not a readable rename inventory: {error}")
    expected = {"source": meta["old"], "target": meta["new"], "root": meta["checkout"]["root"]}
    for key, value in expected.items():
        found = data.get(key)
        same = found is not None and (Path(found).resolve() == Path(value).resolve() if key == "root" else found == value)
        if not same:
            raise Stop(f"guard: {path} is a rename inventory for {key} {found!r}, not {value!r}")


def claims_tolerated(path, live_root, saved_root):
    """A `tasks` command against a project this cutover does not own can create empty
    claims/<prefix>.{toml,lock} files. An empty claims file records no claim, so it is
    not a foreign change: tolerate it when the live copy is empty and the saved copy is
    absent or also empty. A non-empty file is a real claim and must still stop the guard."""
    if not path.startswith("claims/"):
        return False
    live = live_root / path
    if not (live.exists() and live.stat().st_size == 0):
        return False
    saved = saved_root / path
    return not saved.exists() or saved.stat().st_size == 0


def guard(meta, snap):
    old, new = meta["old"], meta["new"]
    config, state = Path(meta["config"]), Path(meta["state"])
    live = registry_view(config / "projects.toml", old, new)
    saved = registry_view(snap / "config" / "projects.toml", old, new)
    if live != saved:
        extra = sorted(set(live["projects"]) ^ set(saved["projects"]) | set(live["aliases"]) ^ set(saved["aliases"]))
        raise Stop(f"guard: the registry changed outside {old}/{new}: {', '.join(extra) or 'values'}")
    own = {f"claims/{p}.{ext}" for p in (old, new) for ext in ("toml", "lock")}
    inventory = state / "rename" / f"{old}.toml"
    if inventory.exists():
        validate_inventory(inventory, meta)
        own.add(f"rename/{old}.toml")
    for live_root, saved_root, skip in ((config, snap / "config", {"projects.toml", "projects.lock"}),
                                        (state, snap / "state", own)):
        live_files, saved_files = files(live_root, skip), files(saved_root, skip)
        changed = sorted(
            f for f in live_files ^ saved_files
            if not claims_tolerated(f, live_root, saved_root)) + sorted(
            f for f in live_files & saved_files
            if not f.endswith(".lock") and not filecmp.cmp(live_root / f, saved_root / f, shallow=False))
        if changed:
            raise Stop(f"guard: {live_root} changed outside {old}/{new}: {', '.join(changed)}")


def move_back(meta):
    """Move the checkout (and its worktree storage) back to their pre-rename paths.

    Each pair — (checkout, new_root) and, when there is one, (storage_old, storage_new) —
    must have exactly one side present; both or neither is an ambiguous state a person
    must resolve. Every check for both pairs, and for a real file/dir blocking the managed
    link, runs before either pair is touched."""
    checkout, new_root = Path(meta["checkout"]["root"]), Path(meta["new_root"])
    checkout_present, new_root_present = checkout.exists(), new_root.exists()
    if checkout_present and new_root_present:
        raise Stop(f"move back: both {checkout} and {new_root} exist")
    if not checkout_present and not new_root_present:
        raise Stop(f"move back: neither {checkout} nor {new_root} exists")
    move_checkout = new_root_present

    move_storage = False
    s_old = s_new = None
    if meta["storage_old"]:
        s_old, s_new = Path(meta["storage_old"]).parent, Path(meta["storage_new"]).parent
        old_present, new_present = s_old.exists(), s_new.exists()
        if old_present and new_present:
            raise Stop(f"move back: both {s_old} and {s_new} exist")
        if not old_present and not new_present:
            raise Stop(f"move back: neither {s_old} nor {s_new} exists")
        move_storage = new_present
        link = (new_root if move_checkout else checkout) / ".worktrees"
        if link.exists() and not link.is_symlink():
            raise Stop(f"move back: {link} is not a link")

    if move_checkout:
        os.rename(new_root, checkout)
    if meta["storage_old"]:
        if move_storage:
            os.rename(s_new, s_old)
        link = checkout / ".worktrees"
        if link.is_symlink():
            link.unlink()
        link.symlink_to(meta["worktrees_link"])


def validate_leftovers(meta):
    """The foreign-untracked check, run before any mutation: whichever checkout path
    exists may only have rename leftovers untracked — each exactly `tasks/<new>-<hex>.md`
    with its pre-rename original present at the saved head — and no other repository may
    have any. Returns the validated paths so the caller can delete them after the reset
    without listing again."""
    old, new, head = meta["old"], meta["new"], meta["checkout"]["head"]
    checkout = checkout_now(meta)
    untracked = run("git", "-C", checkout, "ls-files", "--others", "--exclude-standard").splitlines()
    for path in untracked:
        parts = Path(path).parts
        name = Path(path).name
        if not (len(parts) == 2 and parts[0] == "tasks" and name.startswith(f"{new}-")):
            raise Stop(f"leftovers: {path} is not a rename leftover")
        original = f"tasks/{old}-{name[len(new) + 1:]}"
        check = subprocess.run(["git", "-C", str(checkout), "cat-file", "-e", f"{head}:{original}"],
                               capture_output=True)
        if check.returncode != 0:
            raise Stop(f"leftovers: {path} has no restored original {original}")
    for repo in meta["repos"]:
        if run("git", "-C", repo["root"], "ls-files", "--others", "--exclude-standard").strip():
            raise Stop(f"leftovers: {repo['root']} has untracked files")
    return untracked


def restore_dir(saved, live):
    shutil.rmtree(live)
    shutil.copytree(saved, live, symlinks=True)


def save_reset_patch(root, head, snap, label):
    """`git reset --hard` is destructive; keep whatever it would discard as a patch.

    Covers commits made since save plus any working-tree edits, since diffing the
    working tree against the saved head captures both. Never overwrites an earlier
    patch: a rollback stopped and retried writes the next unused rollback-<label>-<n>.patch."""
    diff = run("git", "-C", root, "diff", "--binary", head)
    n = 1
    while (path := snap / f"rollback-{label}-{n}.patch").exists():
        n += 1
    path.write_text(diff)
    if diff.strip():
        print(f"rename-cutover: reset {root}: changes since save kept in {path}", file=sys.stderr)


def rollback(args):
    snap = Path(args.snapshot)
    meta = load_meta(snap)
    check_environment("rollback", meta)
    guard(meta, snap)
    check_branches(meta)
    leftovers = validate_leftovers(meta)
    move_back(meta)
    checkout = Path(meta["checkout"]["root"])
    resets = [(checkout, meta["checkout"]["head"], "checkout")]
    resets += [(Path(r["root"]), r["head"], Path(r["root"]).name) for r in meta["repos"]]
    for root, head, label in resets:
        save_reset_patch(root, head, snap, label)
        run("git", "-C", root, "reset", "-q", "--hard", head)
    for path in leftovers:
        (checkout / path).unlink()
    restore_dir(snap / "config", Path(meta["config"]))
    restore_dir(snap / "state", Path(meta["state"]))
    tool = link_tool(checkout, meta)
    run(tool, "--apply")
    if link_report(tool) != (snap / "links.txt").read_text():
        raise Stop("links: the fresh report differs from the saved one")
    for root, _, _ in resets:
        if run("tasks", "check", cwd=root).strip():
            raise Stop(f"check: tasks check reports findings in {root}")
        if porcelain(root):
            raise Stop(f"check: {root} is not clean")
    print("rolled back to " + ", ".join(f"{head[:7]} ({label})" for _, head, label in resets))


RETIRED_PREFIX_RE = re.compile(
    r'^depends on (?P<old_id>\S+) through retired prefix "(?P<prefix>[^"]*)"; it is now (?P<new_id>\S+)$')


def retarget_dependencies(root, old):
    """After `tasks init --prefix <new> --force`, a task elsewhere that depends on an
    old-prefix id still names it, and `tasks check` there reports each as a
    `retired_prefix` warning. Retarget each to the id the warning names as canonical, so
    that repository's `tasks check` comes back clean (`verify` requires that)."""
    output = run("tasks", "check", cwd=root)
    report = json.loads(output) if output.strip() else {"warnings": []}
    for warning in report.get("warnings", []):
        if warning.get("kind") != "retired_prefix":
            continue
        match = RETIRED_PREFIX_RE.match(warning.get("detail", ""))
        if not match:
            raise Stop(f"retarget: unparseable retired_prefix warning for {warning.get('id')}: "
                       f"{warning.get('detail')!r}")
        if match["prefix"] != old:
            continue
        old_id, new_id = match["old_id"], match["new_id"]
        run("tasks", "dep", warning["id"], "--rm", old_id, cwd=root)
        run("tasks", "dep", warning["id"], "--on", new_id, cwd=root)
        print(f"retarget: {warning['id']}: {old_id} -> {new_id}")


def apply(args):
    snap = Path(args.snapshot)
    meta = load_meta(snap)
    check_environment("apply", meta)
    checkout, new_root, old, new = Path(meta["checkout"]["root"]), Path(meta["new_root"]), meta["old"], meta["new"]
    if new_root.exists():
        raise Stop(f"apply: {new_root} already exists")
    if meta["storage_new"] and Path(meta["storage_new"]).parent.exists():
        raise Stop(f"apply: {Path(meta['storage_new']).parent} already exists")
    run("tasks", "rename", old, new, cwd=checkout)
    os.rename(checkout, new_root)
    if meta["storage_old"]:
        os.rename(Path(meta["storage_old"]).parent, Path(meta["storage_new"]).parent)
        (new_root / ".worktrees").unlink()
        run("work-link", "--root", new_root.parent, "--ensure", ".worktrees", cwd=new_root)
    run("tasks", "init", "--prefix", new, "--force", cwd=new_root)
    print(f"applied: {old} -> {new} at {new_root}")


def retarget(args):
    """One repository's retarget, run by the runbook before that repository's commit.
    A repository outside the snapshot is refused: rollback could not restore it. After
    the other host has adopted, rollback is over, and `--forward` allows one."""
    meta = load_meta(args.snapshot)
    check_environment("retarget", meta)
    root = Path(args.repo).resolve()
    if not args.forward and str(root) not in {r["root"] for r in meta["repos"]}:
        raise Stop(f"retarget: {root} is not in the snapshot; after the other host has adopted, "
                   f"pass --forward")
    retarget_dependencies(root, meta["old"])


def link(args):
    meta = load_meta(args.snapshot)
    check_environment("link", meta)
    new_root = Path(meta["new_root"])
    if not new_root.exists():
        raise Stop(f"link: {new_root} does not exist; run apply first")
    run(link_tool(new_root, meta), "--apply")
    print(f"linked from {new_root}")


def verify(args):
    meta = load_meta(args.snapshot)
    check_environment("verify", meta)
    new_root, old, new = Path(meta["new_root"]), meta["old"], meta["new"]
    check = subprocess.run([str(link_tool(new_root, meta)), "--check"], text=True, capture_output=True)
    if check.returncode != 0:
        raise Stop(f"verify: link drift after apply:\n{check.stdout}")
    for root in (new_root, *(Path(r["root"]) for r in meta["repos"])):
        if run("tasks", "check", cwd=root).strip():
            raise Stop(f"verify: tasks check reports findings in {root}")
    any_new = next(p.stem for p in (new_root / "tasks").glob(f"{new}-*.md"))
    run("tasks", "show", f"{old}-{any_new.split('-', 1)[1]}", cwd=new_root)
    if meta["storage_new"] and (new_root / ".worktrees").resolve() != Path(meta["storage_new"]).resolve():
        raise Stop("verify: .worktrees does not resolve to the moved storage")
    print("verified")


COMMANDS = {"save": save, "apply": apply, "retarget": retarget, "link": link, "verify": verify,
            "rollback": rollback}


def main(argv):
    parser = argparse.ArgumentParser(prog="rename-cutover")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("save")
    s.add_argument("--snapshot", required=True)
    s.add_argument("--checkout", required=True, help="the renamed project's checkout")
    s.add_argument("--repo", action="append", required=True,
                   help="a repository the cutover retargets in and rollback resets (repeatable)")
    s.add_argument("--new-root", required=True)
    s.add_argument("--old", required=True)
    s.add_argument("--new", required=True)
    s.add_argument("--link-tool", default="tools/tack-link",
                   help="the link tool's path inside the checkout")
    r = sub.add_parser("retarget")
    r.add_argument("--snapshot", required=True)
    r.add_argument("--repo", required=True)
    r.add_argument("--forward", action="store_true",
                   help="allow a repository outside the snapshot, once rollback is over")
    for name in ("apply", "link", "verify", "rollback"):
        sub.add_parser(name).add_argument("--snapshot", required=True)
    args = parser.parse_args(argv)
    try:
        COMMANDS[args.command](args)
    except Stop as stop:
        print(f"rename-cutover: {stop}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

What changed, for the reviewer: `record`, `checkout_now`, `link_tool`, `unmerged_branches` and the three new commands are new. `preconditions` takes every repository and refuses any claim in a retargeted one, any unclean tree, and any local branch with commits the current branch lacks. `rollback` resets the checkout and every repository, each with its own patch. `retarget_dependencies` is the September `retarget_ops_dependencies`, run per repository. `storage_new` follows the directory. `registry_view`, `guard`, `move_back`, `save_reset_patch` and `claims_tolerated` keep their logic.

- [ ] **Step 4: Run the focused tests, then the suite**

Run: `uv run -q --with pytest pytest tools/test_rename_cutover.py -q`
Expected: `44 passed`.

Run: `just test`
Expected: every suite passes.

- [ ] **Step 5: Commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && \
tasks done "$STEP4" "rename-cutover takes --checkout and repeated --repo; apply, retarget and link are separate; the link tool comes from the snapshot" >/dev/null && \
git commit -q -m "feat(rename-cutover): a list of repositories, a split apply, the link tool as an argument (tack-8b7a28)" -- tools/rename-cutover tools/test_rename_cutover.py "tasks/$STEP4.md" && git log --oneline -1
```

---

### Task 5: The guard knows this rename's shape, and the trust files are kept

Two things the September tool never met. This rename retargets an existing alias (`ai = "tack"` becomes `ai = "hq"`) and rewrites a group member (`tack` becomes `hq` in `agent-layer`). The tool as Task 4 leaves it reports both as foreign and stops (reproduced in a scratch registry at the spec's review round 3). And two Codex trust files cannot be restored by git: the trust tables in `codex/config.toml` pass through a clean filter and are in no commit, and `local/codex/trust.toml` is ignored.

**Files:**
- Modify: `tools/rename-cutover` (`registry_view`, new `registry_changes`, `guard`'s message, new `kept_paths`, `restore_kept`, `refresh_kept`, `check_kept`; `save`, `rollback`, `main`)
- Test: `tools/test_rename_cutover.py` (the `hq` shape and its tests)

**Interfaces:**
- Consumes: Task 4's tool and test module.
- Produces: `save --keep REL` (repeatable). `meta.json` gains `kept: [{path, mode}]`, and the snapshot gains `kept/<n>`. `rollback` restores each kept file after the resets, with its saved mode, and refreshes a filtered tracked one's index entry. It ends by comparing each kept file with its saved copy, byte for byte and mode for mode. The guard's message names entries as `projects.<k>`, `aliases.<k>`, `groups.<k>`. In the test module: `Sandbox(…, hq=True)`, the `hq` fixture, `KEPT`, and `.edit_trust()`.

- [ ] **Step 1: Start the record and add the tests**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && tasks start "$STEP5" >/dev/null && \
git apply - <<'PATCH' && echo applied
--- a/tools/test_rename_cutover.py
+++ b/tools/test_rename_cutover.py
@@ -30,11 +30,17 @@
     return added.get("id") or added["task"]["id"]
 
 
+KEPT = ("codex/config.toml", "local/codex/trust.toml")
+
+
 class Sandbox:
-    """The September rename's shape: checkout `ai` (prefix ai) becomes `tack`, and the
-    cutover retargets in the repositories named by `repos` (ops, unless a test asks)."""
+    """A rename in a sandbox that shares no live state. The September shape: checkout
+    `ai` (prefix ai) becomes `tack`, retargeting in `repos` (ops, unless a test asks).
+    The hq shape (`hq=True`): checkout `tack`, renamed once before from `ai` so the
+    registry holds `ai = "tack"`, in the group `agent-layer`, becomes `hq`; its Codex
+    trust files are a filtered tracked file and an ignored one, saved with --keep."""
 
-    def __init__(self, tmp, repos=("ops",)):
+    def __init__(self, tmp, repos=("ops",), hq=False):
         self.tmp = tmp
         self.env = {**os.environ, "HOME": str(tmp / "home"), "XDG_CONFIG_HOME": str(tmp / "cfg"),
                     "XDG_STATE_HOME": str(tmp / "state"), "GIT_AUTHOR_NAME": "t",
@@ -43,8 +49,9 @@
         for d in ("home", "cfg", "state"):
             (tmp / d).mkdir()
         self.sync = tmp / "sync"
-        self.old, self.new = "ai", "tack"
-        self.checkout, self.new_root = self.sync / "ai", self.sync / "tack"
+        self.hq = hq
+        self.old, self.new = ("tack", "hq") if hq else ("ai", "tack")
+        self.checkout, self.new_root = self.sync / self.old, self.sync / self.new
         self.repos = [self.sync / name for name in repos]
         self.ops = self.repos[0]
         self.snapshot = tmp / "snap"
@@ -66,14 +73,14 @@
         self.run("git", "commit", "-qm", message, cwd=root)
 
     def build(self):
-        self.repo(self.checkout, self.old)
+        self.repo(self.checkout, "ai")
         (self.checkout / "tools").mkdir()
         for name in ("tack-link", "rename-cutover"):
             shutil.copy2(TOOLS / name, self.checkout / "tools" / name)
         (self.checkout / "agents").mkdir()
         (self.checkout / "agents" / "README").write_text("x\n")
         (self.checkout / "links.toml").write_text('[required]\n"~/.agents" = "agents"\n')
-        (self.checkout / ".gitignore").write_text(".worktrees\n")
+        (self.checkout / ".gitignore").write_text(".worktrees\nlocal/\n")
         tid = task_id(self.run("tasks", "add", "one", "--process", "direct", cwd=self.checkout).stdout)
         self.run("tasks", "add", "two", "--process", "direct", cwd=self.checkout)
         self.run("tasks", "start", tid, cwd=self.checkout)
@@ -85,9 +92,33 @@
         for root in self.repos:
             self.repo(root, root.name)
             self.commit(root, "init")
+        if self.hq:
+            self.build_hq()
         self.run(self.checkout / "tools" / "tack-link", "--apply")
         return self
 
+    def build_hq(self):
+        """The earlier rename, done in place; the group; the two trust files."""
+        self.run("tasks", "rename", "ai", "tack", cwd=self.checkout)
+        self.commit(self.checkout, "the earlier rename")
+        self.run("tasks", "group", "set", "agent-layer", "tack", *(r.name for r in self.repos))
+        # The live checkout's filter keeps trust tables out of commits; this one keeps
+        # out any line starting with "trust".
+        self.run("git", "config", "filter.harness-state.clean", "sed '/^trust/d'", cwd=self.checkout)
+        (self.checkout / ".gitattributes").write_text("codex/config*.toml filter=harness-state\n")
+        (self.checkout / "codex").mkdir()
+        (self.checkout / "codex" / "config.toml").write_text('model = "m"\n')
+        self.commit(self.checkout, "a filtered config")
+        with (self.checkout / "codex" / "config.toml").open("a") as f:
+            f.write(f'trust = "{self.checkout}"\n')
+        # git calls a filtered file modified when only its size differs; staging it, as
+        # harness-state-refresh does, refreshes the entry and stages nothing new.
+        self.run("git", "add", "codex/config.toml", cwd=self.checkout)
+        (self.checkout / "local" / "codex").mkdir(parents=True)
+        (self.checkout / "local" / "codex" / "trust.toml").write_text(f'"{self.checkout}" = "trusted"\n')
+        (self.checkout / "local" / "codex" / "trust.toml").chmod(0o600)
+        assert self.run("git", "status", "--porcelain", cwd=self.checkout).stdout == ""
+
     def cutover(self, *args, check=True):
         tool = self.snapshot / "rename-cutover" if (self.snapshot / "rename-cutover").exists() \
             else self.checkout / "tools" / "rename-cutover"
@@ -97,6 +128,9 @@
         args = ["save", "--snapshot", self.snapshot, "--checkout", self.checkout,
                 "--new-root", self.new_root, "--old", self.old, "--new", self.new,
                 "--link-tool", LINK_TOOL]
+        if self.hq:
+            for rel in KEPT:
+                args += ["--keep", rel]
         for root in self.repos:
             args += ["--repo", root]
         return args
@@ -130,7 +164,18 @@
         return {"checkout": tree(self.checkout), **{r.name: tree(r) for r in self.repos},
                 "cfg": tree(self.tmp / "cfg" / "tasks"), "state": tree(self.tmp / "state" / "tasks"),
                 "worktrees": os.readlink(self.checkout / ".worktrees"),
-                "agents": os.path.realpath(self.tmp / "home" / ".agents")}
+                "agents": os.path.realpath(self.tmp / "home" / ".agents"),
+                "modes": {rel: oct((self.checkout / rel).stat().st_mode) for rel in KEPT
+                          if (self.checkout / rel).exists()}}
+
+    def edit_trust(self):
+        """What the runbook's step 4 does to the trust files at the new root."""
+        with (self.new_root / "codex" / "config.toml").open("a") as f:
+            f.write(f'trust = "{self.new_root}"\n')
+        trust = self.new_root / "local" / "codex" / "trust.toml"
+        with trust.open("a") as f:
+            f.write(f'"{self.new_root}" = "trusted"\n')
+        trust.chmod(0o644)
 
 
 @pytest.fixture
@@ -144,6 +189,12 @@
     return Sandbox(tmp_path, repos=("ops", "lore")).build()
 
 
+@pytest.fixture
+def hq(tmp_path):
+    """This rename's shape, retargeting in ops, lore and flows."""
+    return Sandbox(tmp_path, repos=("ops", "lore", "flows"), hq=True).build()
+
+
 # --- save ---------------------------------------------------------------------
 
 
@@ -682,3 +733,112 @@
     parked = json.loads(run2("tasks", "list", "--parked", cwd=box.new_root))
     assert f"tack-{hex_}" in [t["id"] for t in parked["tasks"]]
     assert first_host() == first
+
+
+# --- this rename's shape: an earlier alias, a group, the trust files ------------
+
+
+def test_registry_view_reads_the_renames_own_rewrites_as_equal(tmp_path):
+    cutover = load_cutover()
+    saved, live = tmp_path / "saved.toml", tmp_path / "live.toml"
+    saved.write_text('[projects]\nops = "/o"\ntack = "/t"\n[aliases]\nai = "tack"\n'
+                     '[groups]\nagent-layer = ["ops", "tack"]\n')
+    live.write_text('[projects]\nhq = "/h"\nops = "/o"\n[aliases]\nai = "hq"\ntack = "hq"\n'
+                    '[groups]\nagent-layer = ["hq", "ops"]\n')
+    assert cutover.registry_view(live, "tack", "hq") == cutover.registry_view(saved, "tack", "hq")
+
+
+@pytest.mark.parametrize("change, named", [
+    (lambda t: t.replace("[projects]\n", '[projects]\nzz = "/elsewhere"\n'), "projects.zz"),
+    (lambda t: t.replace("[aliases]\n", '[aliases]\nzz = "hq"\n'), "aliases.zz"),
+    (lambda t: t.replace('ai = "hq"', 'ai = "ops"'), "aliases.ai"),
+    (lambda t: t.replace('"flows", ', ""), "groups.agent-layer"),
+    (lambda t: t + 'other = ["ops"]\n', "groups.other"),
+])
+def test_the_guard_stops_on_any_other_registry_change(hq, change, named):
+    hq.save()
+    hq.cutover("apply", "--snapshot", hq.snapshot)
+    registry = hq.tmp / "cfg" / "tasks" / "projects.toml"
+    text = registry.read_text()
+    assert 'ai = "hq"' in text and '"flows", "hq"' in text
+    registry.write_text(change(text))
+    assert registry.read_text() != text
+    result = hq.cutover("rollback", "--snapshot", hq.snapshot, check=False)
+    assert result.returncode == 1
+    assert "guard: the registry changed" in result.stderr and named in result.stderr
+    assert hq.new_root.exists() and not hq.checkout.exists()
+
+
+def test_this_renames_cutover_and_rollback_before_commit(hq):
+    for root in hq.repos:
+        hq.depend_on_checkout(root)
+    before = hq.fingerprint()
+    hq.save()
+    hq.forward()
+    hq.edit_trust()
+    hq.cutover("verify", "--snapshot", hq.snapshot)
+    registry = (hq.tmp / "cfg" / "tasks" / "projects.toml").read_text()
+    assert 'ai = "hq"' in registry and 'tack = "hq"' in registry
+    assert '"hq"' in registry.split("[groups]")[1]
+    hq.cutover("rollback", "--snapshot", hq.snapshot)
+    assert hq.fingerprint() == before
+
+
+def test_this_renames_rollback_after_commit_restores_the_trust_files(hq):
+    for root in hq.repos:
+        hq.depend_on_checkout(root)
+    before = hq.fingerprint()
+    hq.save()
+    hq.forward()
+    hq.edit_trust()
+    hq.commit(hq.new_root, "rename")
+    for root in hq.repos:
+        hq.commit(root, "retarget")
+    hq.cutover("rollback", "--snapshot", hq.snapshot)
+    assert hq.fingerprint() == before
+    assert oct((hq.checkout / KEPT[1]).stat().st_mode).endswith("600")
+
+
+def test_this_renames_second_host_adopts(hq):
+    second = {**hq.env, "XDG_CONFIG_HOME": str(hq.tmp / "cfg2"), "XDG_STATE_HOME": str(hq.tmp / "state2")}
+    shutil.copytree(hq.tmp / "cfg", hq.tmp / "cfg2")       # the second host's registry, as it was
+    (hq.tmp / "state2").mkdir()
+    hq.save()
+    hq.forward()
+    hq.commit(hq.new_root, "rename")
+    hq.run("tasks", "rename", "tack", "hq", "--adopt", cwd=hq.new_root, env=second)
+    registry = (hq.tmp / "cfg2" / "tasks" / "projects.toml").read_text()
+    assert f'hq = "{hq.new_root}"' in registry
+    assert 'ai = "hq"' in registry and 'tack = "hq"' in registry
+    assert '"hq"' in registry.split("[groups]")[1] and '"tack"' not in registry.split("[groups]")[1]
+
+
+def test_save_refuses_a_kept_path_that_is_not_a_file(hq):
+    args = [str(a) for a in hq.save_args()]
+    args[args.index("--keep") + 1] = "codex/absent.toml"
+    result = hq.cutover(*args, check=False)
+    assert result.returncode == 1
+    assert "no regular file" in result.stderr
+    assert not hq.snapshot.exists()
+
+
+@pytest.mark.parametrize("path", ["/etc/hostname", "../outside.toml"])
+def test_save_refuses_a_kept_path_outside_the_checkout(hq, path):
+    args = [str(a) for a in hq.save_args()]
+    args[args.index("--keep") + 1] = path
+    result = hq.cutover(*args, check=False)
+    assert result.returncode == 1
+    assert "name a path inside the checkout" in result.stderr
+    assert not hq.snapshot.exists()
+
+
+def test_check_kept_names_a_mode_that_differs(tmp_path):
+    cutover = load_cutover()
+    checkout, snap = tmp_path / "c", tmp_path / "s"
+    (snap / "kept").mkdir(parents=True)
+    checkout.mkdir()
+    (checkout / "f").write_text("x\n")
+    (snap / "kept" / "0").write_text("x\n")
+    (checkout / "f").chmod(0o644)
+    with pytest.raises(cutover.Stop, match="mode 644, saved 600"):
+        cutover.check_kept(checkout, snap, {"kept": [{"path": "f", "mode": 0o600}]})
PATCH
```

The `hq` sandbox does what the live checkout has done. It is renamed once before, in place, so the registry holds `ai = "tack"`, and it is put in a group. Its filtered config's trust line is kept out of the commit by a clean filter. Its ignored trust file has mode 600. `.edit_trust()` is the runbook's step 4: a trust entry for the new path in both files, and a mode change on one.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run -q --with pytest pytest tools/test_rename_cutover.py -q`
Expected: 13 failed, 44 passed. The `registry_view` unit test fails on the alias and the group. Every test that builds the `hq` sandbox and saves fails on `--keep`. `test_check_kept_names_a_mode_that_differs` fails on the missing `check_kept`.

- [ ] **Step 3: Implement**

`git apply` is atomic: on any mismatch it applies nothing and says which hunk failed.

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && \
git apply - <<'PATCH' && echo applied
--- a/tools/rename-cutover
+++ b/tools/rename-cutover
@@ -19,6 +19,7 @@
 import os
 import re
 import shutil
+import stat
 import subprocess
 import sys
 import tomllib
@@ -143,6 +144,17 @@
         raise Stop(f"preconditions: link drift:\n{check.stdout}")
 
 
+def kept_paths(checkout, paths):
+    """Files git cannot restore (a clean filter keeps their live content out of every
+    commit, or they are ignored), named relative to the checkout so they follow its move."""
+    for rel in paths:
+        if Path(rel).is_absolute() or ".." in Path(rel).parts:
+            raise Stop(f"save: --keep {rel}: name a path inside the checkout, relative to it")
+        if not (checkout / rel).is_file() or (checkout / rel).is_symlink():
+            raise Stop(f"save: --keep {rel}: no regular file at {checkout / rel}")
+    return list(paths)
+
+
 def save(args):
     checkout, snap = Path(args.checkout).resolve(), Path(args.snapshot)
     repos = [Path(r).resolve() for r in args.repo]
@@ -164,6 +176,7 @@
         path = path.resolve()
         if snap_resolved == path or path in snap_resolved.parents:
             raise Stop(f"save: snapshot {snap} lies inside {which}")
+    kept = kept_paths(checkout, args.keep)
     preconditions(checkout, repos, tool)
     new_root = Path(args.new_root)
     new_root = new_root.parent.resolve() / new_root.name
@@ -176,23 +189,46 @@
         "worktrees_link": link_text,
         "storage_old": str(storage_old) if storage_old else None,
         "storage_new": str(storage_new) if storage_new else None,
+        "kept": [{"path": rel, "mode": stat.S_IMODE((checkout / rel).stat().st_mode)} for rel in kept],
     }
     snap.mkdir(parents=True, exist_ok=False)
     shutil.copytree(config, snap / "config", symlinks=True)
     shutil.copytree(state, snap / "state", symlinks=True)
     (snap / "links.txt").write_text(link_report(tool))
+    for n, rel in enumerate(kept):
+        (snap / "kept").mkdir(exist_ok=True)
+        shutil.copy2(checkout / rel, snap / "kept" / str(n))
     shutil.copy2(Path(__file__).resolve(), snap / "rename-cutover")
     (snap / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
     print(f"saved {snap}")
 
 
 def registry_view(path, old, new):
-    """The registry with the renamed project's own keys removed, for the guard."""
+    """The registry as the guard compares it: the renamed project's own entries removed,
+    and the rename's own rewrites of other entries read the same on both sides.
+    `tasks rename` retargets an alias that named the old prefix (`ai = "tack"` becomes
+    `ai = "hq"`) and rewrites a group member from the old prefix to the new; reading the
+    old prefix as the new one makes exactly those equal. Every other difference remains."""
     data = tomllib.loads(path.read_text()) if path.exists() else {}
+
+    def renamed(prefix):
+        return new if prefix == old else prefix
+
     projects = {k: v for k, v in data.get("projects", {}).items() if k not in (old, new)}
-    aliases = {k: v for k, v in data.get("aliases", {}).items() if k != old and v != new}
-    return {**{k: v for k, v in data.items() if k not in ("projects", "aliases")},
-            "projects": projects, "aliases": aliases}
+    aliases = {k: renamed(v) for k, v in data.get("aliases", {}).items() if k not in (old, new)}
+    groups = {k: sorted(renamed(m) for m in members) for k, members in data.get("groups", {}).items()}
+    rest = {k: v for k, v in data.items() if k not in ("projects", "aliases", "groups")}
+    return {**rest, "projects": projects, "aliases": aliases, "groups": groups}
+
+
+def registry_changes(live, saved):
+    """The names of the entries that differ, for the guard's message."""
+    tables = ("projects", "aliases", "groups")
+    names = {k for k in (live.keys() | saved.keys()) - set(tables) if live.get(k) != saved.get(k)}
+    for table in tables:
+        names |= {f"{table}.{k}" for k in live[table].keys() | saved[table].keys()
+                  if live[table].get(k) != saved[table].get(k)}
+    return sorted(names)
 
 
 def files(root, skip):
@@ -234,8 +270,7 @@
     live = registry_view(config / "projects.toml", old, new)
     saved = registry_view(snap / "config" / "projects.toml", old, new)
     if live != saved:
-        extra = sorted(set(live["projects"]) ^ set(saved["projects"]) | set(live["aliases"]) ^ set(saved["aliases"]))
-        raise Stop(f"guard: the registry changed outside {old}/{new}: {', '.join(extra) or 'values'}")
+        raise Stop(f"guard: the registry changed outside {old}/{new}: {', '.join(registry_changes(live, saved))}")
     own = {f"claims/{p}.{ext}" for p in (old, new) for ext in ("toml", "lock")}
     inventory = state / "rename" / f"{old}.toml"
     if inventory.exists():
@@ -338,6 +373,40 @@
         print(f"rename-cutover: reset {root}: changes since save kept in {path}", file=sys.stderr)
 
 
+def restore_kept(checkout, snap, meta):
+    """Copy each kept file back as it was saved, mode included. Run after the reset,
+    which leaves an ignored file alone and rewrites a filtered one only when it sees a
+    change, so neither can be trusted to have restored it."""
+    for n, entry in enumerate(meta["kept"]):
+        live = checkout / entry["path"]
+        live.parent.mkdir(parents=True, exist_ok=True)
+        shutil.copyfile(snap / "kept" / str(n), live)
+        os.chmod(live, entry["mode"])
+
+
+def refresh_kept(checkout, meta):
+    """A filtered file whose size differs from its index entry shows as modified until
+    the entry is refreshed, even when its filtered content is unchanged. Stage each kept
+    file that is tracked and filtered-equal, as harness-state-refresh does: that writes
+    the blob already in the index. A real change is left for the clean check to report."""
+    for entry in meta["kept"]:
+        path = entry["path"]
+        tracked = subprocess.run(["git", "-C", str(checkout), "ls-files", "--error-unmatch", "--", path],
+                                 capture_output=True).returncode == 0
+        if tracked and subprocess.run(["git", "-C", str(checkout), "diff", "--quiet", "--", path]).returncode == 0:
+            run("git", "-C", checkout, "add", "--", path)
+
+
+def check_kept(checkout, snap, meta):
+    for n, entry in enumerate(meta["kept"]):
+        live = checkout / entry["path"]
+        if not filecmp.cmp(live, snap / "kept" / str(n), shallow=False):
+            raise Stop(f"check: {live} differs from its saved copy")
+        if stat.S_IMODE(live.stat().st_mode) != entry["mode"]:
+            raise Stop(f"check: {live} has mode {stat.S_IMODE(live.stat().st_mode):o}, "
+                       f"saved {entry['mode']:o}")
+
+
 def rollback(args):
     snap = Path(args.snapshot)
     meta = load_meta(snap)
@@ -354,6 +423,8 @@
         run("git", "-C", root, "reset", "-q", "--hard", head)
     for path in leftovers:
         (checkout / path).unlink()
+    restore_kept(checkout, snap, meta)
+    refresh_kept(checkout, meta)
     restore_dir(snap / "config", Path(meta["config"]))
     restore_dir(snap / "state", Path(meta["state"]))
     tool = link_tool(checkout, meta)
@@ -365,6 +436,7 @@
             raise Stop(f"check: tasks check reports findings in {root}")
         if porcelain(root):
             raise Stop(f"check: {root} is not clean")
+    check_kept(checkout, snap, meta)
     print("rolled back to " + ", ".join(f"{head[:7]} ({label})" for _, head, label in resets))
 
 
@@ -470,6 +542,9 @@
     s.add_argument("--new", required=True)
     s.add_argument("--link-tool", default="tools/tack-link",
                    help="the link tool's path inside the checkout")
+    s.add_argument("--keep", action="append", default=[],
+                   help="a file inside the checkout that git cannot restore, saved and "
+                        "restored as a live file with its mode (repeatable)")
     r = sub.add_parser("retarget")
     r.add_argument("--snapshot", required=True)
     r.add_argument("--repo", required=True)
PATCH
```

Two points for the reviewer:

- **The guard reads the old prefix as the new one on both sides**, after removing the renamed project's own keys. So a retargeted alias and a rewritten group member compare equal. Everything else still stops it: a new alias pointing at the new prefix, an alias moved elsewhere, a member removed, a group added. The September filter `v != new` silently ignored any alias pointing at the new prefix; that is gone.
- **`refresh_kept`.** git calls a filtered file modified when its size differs from the index entry, without running the filter. Restoring `codex/config.toml` with its trust tables would leave the checkout "not clean", and rollback would stop on its own restore. Staging a tracked kept file whose filtered diff is empty writes the blob already in the index, as `.githooks/harness-state-refresh` does. A real change is left for the clean check. The live host meets the same mark (`M claude/settings.json` on main today), and the cutover's runbook clears it before save.

- [ ] **Step 4: Run the focused tests, then the suite**

Run: `uv run -q --with pytest pytest tools/test_rename_cutover.py -q`
Expected: `57 passed`.

Run: `just test`
Expected: every suite passes.

- [ ] **Step 5: Commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && \
tasks done "$STEP5" "the guard accepts the rename's own alias retarget and group rewrite and nothing else; save --keep restores files git cannot, with their modes" >/dev/null && \
git commit -q -m "feat(rename-cutover): the guard knows a rename's own registry changes; kept trust files (tack-8b7a28)" -- tools/rename-cutover tools/test_rename_cutover.py "tasks/$STEP5.md" && git log --oneline -1
```

---

### Task 6: The link tool is `harness-links`

**Files:**
- Rename: `tools/tack-link` → `tools/harness-links`; `tools/test_tack_link.py` → `tools/test_harness_links.py`
- Modify: `justfile` (`link`, `link-check`; the recipes keep their names), `tools/rename-cutover` (the `--link-tool` default), `tools/test_rename_cutover.py`, `README.md`, `AGENTS.md`

**Interfaces:**
- Produces: `tools/harness-links [--check | --apply]`, the same behaviour, printing `harness-links:` in its usage and error lines and staging under `.<name>.harness-links`. `rename-cutover save` defaults `--link-tool` to `tools/harness-links`. The cutover plan's runbook passes it explicitly.

- [ ] **Step 1: Start the record and rename**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && tasks start "$STEP6" >/dev/null && \
git mv tools/tack-link tools/harness-links && git mv tools/test_tack_link.py tools/test_harness_links.py && \
sed -i 's/tack-link/harness-links/g; s/tack_link/harness_links/g' tools/harness-links tools/test_harness_links.py tools/test_rename_cutover.py justfile README.md AGENTS.md && \
sed -i 's|default="tools/tack-link"|default="tools/harness-links"|' tools/rename-cutover && \
git grep -n -e tack-link -e tack_link -- ':!docs/specs' ':!docs/plans' ':!tasks' ; git diff --stat HEAD
```

Expected: `git grep` prints nothing. Dated specs, plans and task records keep the old name (spec §1). The diff stat lists the seven files: the two renames, `justfile`, `tools/rename-cutover`, `tools/test_rename_cutover.py`, `README.md`, `AGENTS.md`. The rename is the change, so no test fails first. The suites are the proof that nothing else moved.

- [ ] **Step 2: Run the focused tests, then the suite, then the recipes**

Run: `uv run -q --with pytest pytest tools/test_harness_links.py tools/test_rename_cutover.py -q`
Expected: `104 passed`.

Run: `just test`
Expected: every suite passes.

Run: `just link 2>&1 | head -3`
Expected: the recipe's echoed line `tools/harness-links`, then `harness-links: run from the main checkout, not a worktree`. That is the worktree refusal, now under the new name.

- [ ] **Step 3: Commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && \
tasks done "$STEP6" "tools/tack-link is tools/harness-links; just link and just link-check keep their names" >/dev/null && \
git commit -q -m "refactor(links): tools/tack-link becomes tools/harness-links (tack-8b7a28)" -- tools/harness-links tools/test_harness_links.py tools/tack-link tools/test_tack_link.py justfile tools/rename-cutover tools/test_rename_cutover.py README.md AGENTS.md "tasks/$STEP6.md" && git log --oneline -1
```

---

### Task 7: Review, merge, and hand over to the cutover plan

- [ ] **Step 1: Whole-branch review**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && tasks start "$STEP7" >/dev/null && git log --oneline main..HEAD
```

A fresh-context reviewer on the most capable model reads the spec, this plan and `git diff main...HEAD`. The question above the others: can any path through `rollback` touch a repository, a file or a registry entry that `save` did not record, or skip one it did. Note the round on `tack-8b7a28` (`review: impl round <n> — …`). Then run corrective rounds, each one fix dispatch and one scoped re-review, while the re-review reproduces Critical or Important findings, up to five. Each fixed finding gets a test that fails first.

- [ ] **Step 2: Record the status in the spec and this plan, and close the step, in the worktree**

In `docs/specs/2026-10-06-rename-to-hq-design.md`, replace the status line's sentence `Its plan is not yet written.` with `Phase 1 steps 1 to 3 landed 2026-10-06 by docs/plans/2026-10-06-rename-to-hq-preparation.md; steps 4 and 5 and phase 2 get their own plan once tasks-7580d2 has landed.` In this plan, set the status line to `executed 2026-10-06`, with the review rounds and anything that departed from the plan. Then:

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$WT" && \
tasks done "$STEP7" "reviewed and merged; both hosts converge" >/dev/null && \
tasks note tack-8b7a28 "phase 1 steps 1 to 3 delivered (docs/plans/2026-10-06-rename-to-hq-preparation.md): the units call ~/.local/bin/session-archive on both hosts; rename-cutover is general (a repositories list, a split apply, a guard that knows the alias retarget and group rewrite, kept trust files); tools/harness-links" >/dev/null && \
git commit -q -m "docs: the rename's preparation landed (tack-8b7a28)" -- docs/specs/2026-10-06-rename-to-hq-design.md docs/plans/2026-10-06-rename-to-hq-preparation.md "tasks/$STEP7.md" tasks/tack-8b7a28.md && git log --oneline -1
```

The record is closed before the merge it names. If Step 3 fails, the failure goes in a note on `tack-8b7a28`, and the merge is fixed before anything else.

- [ ] **Step 3: Merge, and check links on both hosts**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$TACK" && \
[ -z "$(git status --porcelain -- tools justfile README.md AGENTS.md links.toml systemd docs)" ] && \
git merge --no-ff "$BRANCH" -m "Merge branch '$BRANCH' (the rename's preparation)" && t just test && just link-check > /dev/null && echo "this host converges"
```

Then the second host, read-only, once the sync has carried the merge:

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && need SECOND && ssh -4 -o BatchMode=yes "$SECOND" 'export PATH="$HOME/.local/bin:$HOME/bin:$PATH"; cd "$(tasks root tack-8b7a28 --pretty)" && test -x tools/harness-links && just link-check > /dev/null 2>&1 && echo "second host converges"'
```

Expected: both hosts converge. `harness-links` owns no link and no link targets it, so the rename changes no home.

- [ ] **Step 4: Remove the worktree and hand over to the cutover plan**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/tack-8b7a28/docs/plans/2026-10-06-rename-to-hq-preparation.env.sh" && cd "$TACK" && \
WT_REAL="$(cd "$WT" && pwd -P)" && [ -z "$(git -C "$WT" status --porcelain)" ] && \
! readlink -f ~/bin/* ~/.local/bin/* ~/.config/systemd/user/* 2>/dev/null | grep -qF "$WT_REAL" && \
tt-report && git worktree unlock "$WT" && git worktree remove "$WT" && git branch -d "$BRANCH" && \
tasks park tack-8b7a28 "When tasks-7580d2 has landed its resolver, write docs/plans/<date>-rename-to-hq-cutover.md for spec §3.1 steps 4 and 5 and phase 2 (the rehearsal; the runbook with its timers, attestations and systemd steps; the second host; verification), taking what flows-44890e and obs-ff4e76 chose." --reason dependency >/dev/null && \
git commit -q -m "chore(tasks): park tack-8b7a28 on tasks-7580d2 for the cutover plan" -- tasks/tack-8b7a28.md && git log --oneline -3
```

The worktree is removed because the cutover refuses a checkout with more than one worktree, and the cutover plan will create its own. Its state directory goes with it. The second host's name is no longer needed.
