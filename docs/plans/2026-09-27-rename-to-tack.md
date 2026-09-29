# Rename ai to tack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the `ai` project to `tack` everywhere it is a live name, with every host converging through one tracked link manifest.

**Architecture:** Phase 1 (Tasks 1–2) makes the home links declarative (`links.toml` + `tools/tack-link`) and takes the checkout path out of hook commands; it renames nothing. Phase 2 (Tasks 3–8) adds a cutover tool whose `save`, `apply`, `rollback` and `verify` run identically in a sandbox rehearsal and live, prepares the name edits on branches, rehearses, cuts over, and hands each other host its adoption steps.

**Tech Stack:** Python 3.12+ stdlib scripts (`tomllib`, `pathlib`, `subprocess`), pytest via `uv run --with pytest`, `just`, git, the `tasks` CLI, ops's `work-link`.

**Spec:** `docs/specs/2026-09-27-rename-to-tack-design.md` (approved at `d0c0ece`).

## Global Constraints

- Every probe, test and rehearsal that runs `tasks` sets temporary `HOME`, `XDG_CONFIG_HOME` **and** `XDG_STATE_HOME`; a config-only sandbox writes into the live state directory.
- `tasks rename` is never reversed by a command; rollback restores saved originals.
- The whole cutover window (save → verified or rolled back) has no other tasks writer: no other harness session on the host, no live claim in any project (`tasks claims`), none held by the cutover session. The fresh harness sessions of the verification step are controlled exceptions: they are started only to observe loading and hooks, and make no task writes.
- After `link --apply`, the saved link report is compared with a fresh `tack-link` report, never with the apply output (apply may describe repairs).
- Links never resolve into a worktree: `tack-link` refuses to run from one.
- Never overwrite a real file or directory at a link path.
- Dated specs, plans and notes keep saying `ai`; only live names change.
- No compatibility link `ai -> tack`.
- The live cutover (Task 7) is gated on tasks-7f1596 and on Task 6's rehearsal passing.
- Paths shown to the user are relative to the main checkout; no `/home/…` or Dropbox paths in code comments or docs.

## Review Focus

1. A link path that is a dangling symlink (the checkout moved) must be `repoint`, never `skipped` or `refuse` — Task 1 test `test_dangling_agents_link_is_repointed`.
2. A harness home that is itself a symlink must be treated as absent, not followed — Task 1 test `test_symlinked_harness_home_is_skipped`.
3. `apply` interrupted between the move and `init --force` leaves the registry pointing at a missing root; `rollback` must still restore — Task 4 test `test_rollback_after_partial_apply`.
4. An untracked file in the checkout that is not a rename leftover (e.g. a new note) must stop the rollback, not be deleted — Task 3 test `test_rollback_stops_on_foreign_untracked_file`.
5. A registry change to another project during the window must stop the rollback before any restore — Task 3 test `test_guard_stops_on_foreign_registry_change`.

---

## File Structure

- Create `links.toml` — the manifest: `[required]` links and `[harness.<name>]` groups.
- Create `tools/tack-link` — reads the manifest, reports, checks, applies.
- Create `tools/test_tack_link.py` — sandboxed tests for `tack-link`.
- Create `tools/rename-cutover` — `save`, `apply`, `rollback`, `verify` for the one-off rename, parameterised by roots so the rehearsal and the live run share code.
- Create `tools/test_rename_cutover.py` — sandboxed tests, including the rehearsal scenarios.
- Modify `justfile` — `link`, `link-check` recipes; `test` also runs `tools/`.
- Modify `claude/settings.json`, `claude/settings.work.json`, `codex/hooks.json`, `codex/hooks.work.json` — hook command `~/.local/bin/harness-state-refresh`.
- Modify `README.md` — "Home links" section; later the rename note.
- Branch `tack-names` (ai): `identity.toml`, `agents/skills/flow/SKILL.md`, `agents/skills/session-logs/SKILL.md`, `README.md`.
- Branch `tack-prefix` (ops, its own task): `identity-mirror.toml`, `bin/ops-projects`, `bin/ops-profile`, and the tests that assert the constants.

---

### Task 1: Link manifest and `tack-link`

**Files:**
- Create: `links.toml`, `tools/tack-link`, `tools/test_tack_link.py`
- Modify: `justfile`, `README.md`

**Interfaces:**
- Produces: `tools/tack-link [--check | --apply]`. Output, one line per entry, tab-separated: `<state>\t<link as ~/…>\t<detail>`, states `ok`, `create`, `repoint`, `refuse`, `skipped` (once per absent harness home, link column is the home). Exit: report mode 1 if any `refuse` else 0; `--check` 1 if any `create`/`repoint`/`refuse`; `--apply` 1 and no writes if any `refuse`. Refuses from a worktree with exit 2 and the message `tack-link: run from the main checkout, not a worktree`.

- [ ] **Step 0: Track the three empty Claude directories**

`claude/agents`, `claude/commands` and `claude/plans` are empty and untracked today, so a
fresh clone lacks them and the manifest's target check would refuse every host. Keep the
links (today's behaviour on every host) and track the directories:

```bash
mkdir -p claude/agents claude/commands claude/plans
touch claude/agents/.gitkeep claude/commands/.gitkeep claude/plans/.gitkeep
printf '%s\n' 'claude/plans/*' '!claude/plans/.gitkeep' >> .gitignore
```

`claude/plans` receives Claude Code's plan files at runtime; they stay out of git.

- [ ] **Step 1: Write `links.toml`**

```toml
# Every link from a home directory into this checkout. `just link` reports what it would
# change; `just link --apply` converges this host. Required links go on every host;
# a harness group applies only where that harness's home is a real directory.

[required]
"~/.agents" = "agents"
"~/.config/AGENTS.md" = "AGENTS.md"
"~/.local/bin/harness-state-refresh" = ".githooks/harness-state-refresh"

[harness.claude]
home = "~/.claude"
[harness.claude.links]
"CLAUDE.md" = "AGENTS.md"
"settings.json" = "claude/settings.json"
"agents" = "claude/agents"
"commands" = "claude/commands"
"plans" = "claude/plans"
"skills/flow" = "agents/skills/flow"
"skills/session-logs" = "agents/skills/session-logs"

[harness.claude-work]
home = "~/.claude-work"
[harness.claude-work.links]
"CLAUDE.md" = "AGENTS.md"
"settings.json" = "claude/settings.work.json"
"statusline-command.sh" = "claude/statusline-command.sh"

[harness.codex]
home = "~/.codex"
[harness.codex.links]
"AGENTS.md" = "AGENTS.md"
"config.toml" = "codex/config.toml"
"hooks.json" = "codex/hooks.json"
"rules" = "codex/rules"

[harness.codex-work]
home = "~/.codex-work"
[harness.codex-work.links]
"AGENTS.md" = "AGENTS.md"
"config.toml" = "codex/config.work.toml"
"hooks.json" = "codex/hooks.work.json"

[harness.opencode]
home = "~/.config/opencode.local"
[harness.opencode.links]
"AGENTS.md" = "AGENTS.md"
```

- [ ] **Step 2: Write the failing tests** — `tools/test_tack_link.py`

```python
"""tack-link converges home links from links.toml and never overwrites data."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).with_name("tack-link")

MANIFEST = '''
[required]
"~/.agents" = "agents"
"~/.local/bin/refresh" = "hooks/refresh"

[harness.claude]
home = "~/.claude"
[harness.claude.links]
"CLAUDE.md" = "AGENTS.md"
"skills/flow" = "agents/skills/flow"

[harness.codex]
home = "~/.codex"
[harness.codex.links]
"AGENTS.md" = "AGENTS.md"
'''


def run(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True)


@pytest.fixture
def world(tmp_path):
    """A checkout with the tool and targets, and an empty HOME with a Claude home only."""
    root = tmp_path / "checkout"
    (root / "tools").mkdir(parents=True)
    shutil.copy2(TOOL, root / "tools" / "tack-link")
    (root / "links.toml").write_text(MANIFEST)
    (root / "agents" / "skills" / "flow").mkdir(parents=True)
    (root / "hooks").mkdir()
    (root / "hooks" / "refresh").write_text("#!/bin/sh\n")
    (root / "AGENTS.md").write_text("# rules\n")
    run("init", "-q", str(root))
    run("-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    run("-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    return root, home


def link(root, home, *args, tool=None):
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run([str(tool or root / "tools" / "tack-link"), *args], env=env,
                          text=True, capture_output=True)


def states(result):
    return {line.split("\t")[1]: line.split("\t")[0] for line in result.stdout.splitlines()}


def test_new_host_gets_required_links_and_installed_harnesses_only(world):
    root, home = world
    result = link(root, home)
    assert result.returncode == 0, result.stderr
    assert states(result) == {
        "~/.agents": "create", "~/.local/bin/refresh": "create",
        "~/.claude/CLAUDE.md": "create", "~/.claude/skills/flow": "create",
        "~/.codex": "skipped"}
    assert not (home / ".agents").exists()          # report mode writes nothing

    applied = link(root, home, "--apply")
    assert applied.returncode == 0, applied.stderr
    assert (home / ".agents").resolve() == (root / "agents").resolve()
    assert (home / ".local/bin/refresh").resolve() == (root / "hooks/refresh").resolve()
    assert (home / ".claude/skills/flow").resolve() == (root / "agents/skills/flow").resolve()
    assert link(root, home, "--check").returncode == 0


def test_link_through_another_spelling_is_ok(world, tmp_path):
    root, home = world
    alias = tmp_path / "d"
    alias.symlink_to(root.parent)
    (home / ".agents").symlink_to(alias / "checkout" / "agents")
    assert states(link(root, home))["~/.agents"] == "ok"


def test_dangling_agents_link_is_repointed(world, tmp_path):
    root, home = world
    (home / ".agents").symlink_to(tmp_path / "moved-away" / "agents")
    result = link(root, home, "--apply")
    assert states(result)["~/.agents"] == "repoint"
    assert (home / ".agents").resolve() == (root / "agents").resolve()


def test_real_file_is_refused_and_nothing_is_written(world):
    root, home = world
    (home / ".claude" / "CLAUDE.md").write_text("mine\n")
    result = link(root, home, "--apply")
    assert result.returncode == 1
    assert states(result)["~/.claude/CLAUDE.md"] == "refuse"
    assert (home / ".claude" / "CLAUDE.md").read_text() == "mine\n"
    assert not (home / ".agents").exists()


def test_symlinked_harness_home_is_skipped(world, tmp_path):
    root, home = world
    (tmp_path / "elsewhere").mkdir()
    (home / ".codex").symlink_to(tmp_path / "elsewhere")
    assert states(link(root, home))["~/.codex"] == "skipped"


def test_check_fails_on_drift(world):
    root, home = world
    assert link(root, home, "--check").returncode == 1


def test_nested_entry_is_rejected(world):
    root, home = world
    (root / "links.toml").write_text(MANIFEST + '\n[harness.agents]\nhome = "~/.agents"\n'
                                     '[harness.agents.links]\n"x" = "AGENTS.md"\n')
    result = link(root, home)
    assert result.returncode == 2
    assert "lies under" in result.stderr


def test_real_manifest_validates_in_a_fresh_clone(tmp_path):
    """The committed links.toml resolves every target in a clone, with Claude alone installed."""
    repo = Path(__file__).resolve().parent.parent
    clone = tmp_path / "clone"
    run("clone", "-q", str(repo), str(clone))
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    result = link(clone, home)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "refuse" not in result.stdout


def test_missing_target_is_rejected(world):
    root, home = world
    (root / "links.toml").write_text('[required]\n"~/.x" = "nope"\n')
    result = link(root, home)
    assert result.returncode == 2
    assert "nope" in result.stderr


def test_refuses_from_a_worktree(world, tmp_path):
    root, home = world
    wt = tmp_path / "wt"
    run("-C", str(root), "worktree", "add", "-q", str(wt))
    result = link(root, home, tool=wt / "tools" / "tack-link")
    assert result.returncode == 2
    assert "not a worktree" in result.stderr
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run -q --with pytest pytest tools/test_tack_link.py -q`
Expected: every test fails or errors because `tools/tack-link` does not exist.

- [ ] **Step 4: Implement `tools/tack-link`** (then `chmod +x tools/tack-link`)

```python
#!/usr/bin/env python3
"""Converge this host's home links into the checkout from links.toml.

Report mode prints one line per entry and writes nothing; --check exits 1 on any
drift; --apply writes, and only when no entry is refused. A link counts as ok when it
resolves to its target by any spelling; a dangling or foreign link is repointed; a real
file or directory at a link path is refused, never overwritten. Required links go on
every host (their parent directory is created); a harness group applies only where its
home is a real directory. Run from the main checkout: links must never resolve into a
worktree. Design: docs/specs/2026-09-27-rename-to-tack-design.md.
"""
import argparse
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent


class ManifestError(Exception):
    pass


@dataclass(frozen=True)
class Entry:
    link: Path
    target: Path
    home: Path | None      # None for a required link


def git(*args):
    result = subprocess.run(["git", "-C", str(HERE), *args], text=True, capture_output=True)
    if result.returncode != 0:
        sys.exit(f"tack-link: git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def checkout_root():
    git_dir = Path(git("rev-parse", "--absolute-git-dir"))
    common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir"))
    if git_dir.resolve() != common.resolve():
        print("tack-link: run from the main checkout, not a worktree", file=sys.stderr)
        sys.exit(2)
    return Path(git("rev-parse", "--show-toplevel"))


def expand(path):
    return Path(os.path.expanduser(path))


def load(root):
    data = tomllib.loads((root / "links.toml").read_text())
    entries = [Entry(expand(link), root / rel, None) for link, rel in data.get("required", {}).items()]
    homes = []
    for name, table in data.get("harness", {}).items():
        home = expand(table["home"])
        homes.append(home)
        entries += [Entry(home / link, root / rel, home) for link, rel in table["links"].items()]
    for entry in entries:
        if not entry.target.exists():
            raise ManifestError(f"{entry.link}: target {entry.target} does not exist")
    links = [entry.link for entry in entries]
    for managed in links:
        for path in [*links, *homes]:
            if path != managed and managed in path.parents:
                raise ManifestError(f"{path} lies under the managed link {managed}")
    for home in homes:
        if home in links:
            raise ManifestError(f"harness home {home} is a managed link")
    return entries, homes


def is_real_dir(path):
    return path.is_dir() and not path.is_symlink()


def state(entry):
    if entry.link.is_symlink():
        if entry.link.exists() and entry.link.resolve() == entry.target.resolve():
            return "ok", ""
        return "repoint", f"was {os.readlink(entry.link)}"
    if entry.link.exists():
        kind = "directory" if entry.link.is_dir() else "file"
        return "refuse", f"a real {kind} is there"
    return "create", ""


def show(path):
    home = Path.home()
    return f"~/{path.relative_to(home)}" if home in path.parents else str(path)


def plan(entries, homes):
    rows, skipped = [], set()
    for entry in entries:
        if entry.home is not None and not is_real_dir(entry.home):
            if entry.home not in skipped:
                skipped.add(entry.home)
                rows.append(("skipped", entry.home, f"{show(entry.home)} absent", None))
            continue
        name, detail = state(entry)
        rows.append((name, entry.link, detail, entry))
    return rows


def apply(rows):
    for name, _, _, entry in rows:
        if name not in ("create", "repoint"):
            continue
        entry.link.parent.mkdir(parents=True, exist_ok=True)
        staging = entry.link.with_name(f".{entry.link.name}.tack-link")
        if staging.is_symlink():
            staging.unlink()
        staging.symlink_to(entry.target)
        os.replace(staging, entry.link)


def main(argv):
    parser = argparse.ArgumentParser(prog="tack-link", description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exit 1 on any drift")
    mode.add_argument("--apply", action="store_true", help="converge the links")
    args = parser.parse_args(argv)
    root = checkout_root()
    try:
        entries, homes = load(root)
    except (ManifestError, KeyError, tomllib.TOMLDecodeError) as error:
        print(f"tack-link: links.toml: {error}", file=sys.stderr)
        return 2
    rows = plan(entries, homes)
    for name, path, detail, _ in rows:
        print(f"{name}\t{show(path)}\t{detail}".rstrip("\t"))
    refused = any(row[0] == "refuse" for row in rows)
    if args.check:
        return 1 if any(row[0] in ("create", "repoint", "refuse") for row in rows) else 0
    if args.apply and not refused:
        apply(rows)
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 5: Run the tests**

Run: `uv run -q --with pytest pytest tools/test_tack_link.py -q`
Expected: all pass. Output lines for `ok` have no trailing tab (the `.rstrip("\t")`); `states()` splits on the first two fields only.

- [ ] **Step 6: Add the recipes and README section**

`justfile`, after `docs`:

```make
# Report the home links links.toml wants on this host; `just link --apply` converges them.
link *args:
    tools/tack-link {{args}}

# Exit non-zero when this host's home links drift from links.toml.
link-check:
    tools/tack-link --check

# The agents/bin, .githooks and tools tests.
test:
    python3 -m pytest agents/bin -q
    uv run -q --with pytest pytest .githooks tools -q
```

(replace the existing `test` recipe and its comment). `README.md`, a new section after the per-clone setup:

```markdown
## Home links

Every link from a harness home into this checkout is listed in `links.toml`:
`[required]` links go on every host; each `[harness.<name>]` group applies only where
that harness's home is a real directory. `just link` reports what would change,
`just link --apply` converges this host, and `just link-check` exits non-zero on drift.
Run `just link --apply` once on each host after pulling a change to `links.toml`, and on
a new host after installing a harness. It never overwrites a real file (`refuse`) and
refuses to run from a worktree.
```

- [ ] **Step 7: Run the suite and commit** (the fresh-clone test is deselected until the commit exists: `-k "not fresh_clone"`)

Run: `just test` with `-k "not fresh_clone"` added to the tools line for this one run — Expected: all pass.

```bash
git add links.toml tools/tack-link tools/test_tack_link.py justfile README.md .gitignore claude/*/.gitkeep
git commit -m "feat(links): declare the home links in links.toml and converge them with just link"
uv run -q --with pytest pytest tools/test_tack_link.py -q -k fresh_clone
```

The fresh-clone test clones the committed `HEAD`, so it passes only after this commit;
run it once more here. Expected: pass.

```bash
```

---

### Task 2: Hook commands through a managed link; converge this host

**Files:**
- Modify: `claude/settings.json`, `claude/settings.work.json`, `codex/hooks.json`, `codex/hooks.work.json`, `.githooks/harness-state-refresh` (docstring), `README.md` (filter paragraph)

**Interfaces:**
- Consumes: `tools/tack-link --apply` from Task 1, the `[required] "~/.local/bin/harness-state-refresh"` entry.
- Produces: hook command string `~/.local/bin/harness-state-refresh` in all four files (Tasks 5 and 7 rely on it not naming the checkout).

- [ ] **Step 1: Replace the command in the four files**

```bash
sed -i 's|~/d/ai/.githooks/harness-state-refresh|~/.local/bin/harness-state-refresh|' \
  claude/settings.json claude/settings.work.json codex/hooks.json codex/hooks.work.json
grep -c '~/.local/bin/harness-state-refresh' claude/settings.json claude/settings.work.json codex/hooks.json codex/hooks.work.json
```
Expected: `1` for each file; `grep -rn 'd/ai/.githooks' claude codex` prints nothing.

- [ ] **Step 2: Note the link in the script's docstring and the README**

In `.githooks/harness-state-refresh`, append to the paragraph ending "…both harnesses report without blocking." the sentence: "The hooks call it through `~/.local/bin/harness-state-refresh`, a link `links.toml` manages, so the command never names the checkout." In `README.md`'s filter paragraph, replace "wired in `claude/settings*.json` and `codex/hooks*.json`" with "wired in `claude/settings*.json` and `codex/hooks*.json` through the `~/.local/bin` link in `links.toml`".

- [ ] **Step 3: Run the suite, commit, merge**

Run: `just test` — Expected: all pass.

```bash
git add claude codex .githooks README.md
git commit -m "feat(hooks): call the harness-state refresh through a managed ~/.local/bin link"
```

Merge to main the way this repository's live config requires (the live `claude/settings*.json` and `codex/config*.toml` differ from HEAD by filtered keys): from the main checkout, `git merge --ff-only <branch>`; if refused for those files, back them up, `git update-ref` main to the branch tip, `git reset -q --` the refused live files, `git checkout HEAD --` every other changed file, and add the new hook command to the live Claude files with a JSON edit that keeps their model keys. Then `git diff --quiet -- claude codex` must succeed.

- [ ] **Step 4: Converge this host from the main checkout**

Run: `just link` in the main checkout.
Expected: every entry `ok` (a link counts as ok by resolved target, so the `~/d/ai/…` and absolute Dropbox spellings both pass) except `create ~/.local/bin/harness-state-refresh`. Any `refuse`: stop and report.
Run: `just link --apply`, then `just link-check` — Expected: exit 0.

- [ ] **Step 5: Re-trust the Codex hooks and verify both harnesses**

The command string changed, so Codex asks to review the Stop hook in each home. Start Codex from this checkout in tmux, review the hook (its command must read `~/.local/bin/harness-state-refresh`), trust it; Codex writes the new `trusted_hash` into `codex/config.toml`. Then, as in ai-fb0e2a: append a blank line to `claude/settings.json` (size-only mark), run one Codex turn, confirm `git status --short claude/` is empty; repeat with `claude -p "Reply with the single word ok."`. Remove the blank line and run `~/.local/bin/harness-state-refresh </dev/null`. Kill the tmux session; `host-load --section session` reports nothing left.

- [ ] **Step 6: Commit the trust hash and tell the other hosts**

```bash
git add codex/config.toml   # only the new hooks.state block; stage it alone if other hunks exist
git commit -m "chore(codex): trust the Stop hook at its managed link"
```

Record on ai-4b1878: `tasks note ai-4b1878 "phase 1 live on <host>; each other host runs just link --apply in its checkout and trusts the Codex Stop hook once"`. Each other host's run is the user's step; Task 7's preconditions ask for confirmation that it is done.

---

### Task 3: Cutover tool — `save`, guard, `rollback`

**Files:**
- Create: `tools/rename-cutover`, `tools/test_rename_cutover.py`

**Interfaces:**
- Consumes: `tools/tack-link` (report and `--apply`), `tasks claims`, `tasks check`, git.
- Produces: `tools/rename-cutover save --snapshot DIR --ai ROOT --ops ROOT --new-root PATH [--old ai --new tack]` writing `DIR/meta.json`, `DIR/config/` (copy of `$XDG_CONFIG_HOME/tasks`), `DIR/state/` (copy of `$XDG_STATE_HOME/tasks`), `DIR/links.txt` (a `tack-link` report), `DIR/rename-cutover` (a copy of itself, run from there after the move). `tools/rename-cutover rollback --snapshot DIR`. Exit 0 on success; on a failed check, exit 1 with `rename-cutover: <step>: <why>` and no further steps. `meta.json` keys: `ai`, `ops`, `new_root`, `old`, `new`, `ai_head`, `ops_head`, `config`, `state`, `worktrees_link`, `storage_old`, `storage_new`, `home`.

- [ ] **Step 1: Write the failing tests** — `tools/test_rename_cutover.py`

The fixture builds a sandbox: `HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME` under `tmp_path`; a Dropbox-like root `sync/` with an `ai` checkout (a copy of this repository's `tools/`, a minimal `links.toml` with one required link `"~/.agents" = "agents"`, `agents/`, `tasks/` initialised with `tasks init --prefix ai`, two tasks one of them parked) and an `ops` checkout initialised with `tasks init --prefix ops`; `sync/../.dropbox-work/ai/.worktrees/` and a `.worktrees` link `../../.dropbox-work/ai/.worktrees` inside `sync/ai` (resolving to `tmp_path/.dropbox-work`); `tools/tack-link --apply` run once. Every subprocess gets the sandbox env.

```python
"""rename-cutover saves, guards and restores a rename in a sandbox that shares no live state."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

TOOLS = Path(__file__).parent


class Sandbox:
    def __init__(self, tmp):
        self.tmp = tmp
        self.env = {**os.environ, "HOME": str(tmp / "home"), "XDG_CONFIG_HOME": str(tmp / "cfg"),
                    "XDG_STATE_HOME": str(tmp / "state"), "GIT_AUTHOR_NAME": "t",
                    "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        self.env.pop("WORK_ROOT", None)
        for d in ("home", "cfg", "state"):
            (tmp / d).mkdir()
        self.sync = tmp / "sync"
        self.ai, self.ops, self.new_root = self.sync / "ai", self.sync / "ops", self.sync / "tack"
        self.snapshot = tmp / "snap"

    def run(self, *cmd, cwd=None, check=True):
        result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=self.env, text=True,
                                capture_output=True)
        if check and result.returncode != 0:
            raise AssertionError(f"{cmd}: {result.stdout}{result.stderr}")
        return result

    def repo(self, path, prefix):
        path.mkdir(parents=True)
        self.run("git", "init", "-q", path)
        self.run("tasks", "init", "--prefix", prefix, cwd=path)

    def build(self):
        self.repo(self.ai, "ai")
        (self.ai / "tools").mkdir()
        for name in ("tack-link", "rename-cutover"):
            shutil.copy2(TOOLS / name, self.ai / "tools" / name)
        (self.ai / "agents").mkdir()
        (self.ai / "agents" / "README").write_text("x\n")
        (self.ai / "links.toml").write_text('[required]\n"~/.agents" = "agents"\n')
        (self.ai / ".gitignore").write_text(".worktrees\n")
        first = json.loads(self.run("tasks", "add", "one", "--process", "direct", cwd=self.ai).stdout)
        tid = first.get("id") or first["task"]["id"]
        self.run("tasks", "add", "two", "--process", "direct", cwd=self.ai)
        self.run("tasks", "start", tid, cwd=self.ai)
        self.run("tasks", "park", tid, "next", cwd=self.ai)
        storage = self.sync.parent / ".dropbox-work" / "ai" / ".worktrees"
        storage.mkdir(parents=True)
        (self.ai / ".worktrees").symlink_to("../../.dropbox-work/ai/.worktrees")
        self.run("git", "add", "-A", cwd=self.ai)
        self.run("git", "commit", "-qm", "init", cwd=self.ai)
        self.repo(self.ops, "ops")
        self.run("git", "add", "-A", cwd=self.ops)
        self.run("git", "commit", "-qm", "init", cwd=self.ops)
        self.run(self.ai / "tools" / "tack-link", "--apply")
        return self

    def cutover(self, *args, check=True):
        tool = self.snapshot / "rename-cutover" if (self.snapshot / "rename-cutover").exists() \
            else self.ai / "tools" / "rename-cutover"
        return self.run(tool, *args, check=check)

    def save(self):
        return self.cutover("save", "--snapshot", self.snapshot, "--ai", self.ai, "--ops", self.ops,
                            "--new-root", self.new_root)

    def fingerprint(self):
        """Everything rollback must restore, as comparable data."""
        def tree(root):
            return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
                    if p.is_file() and ".git" not in p.parts}
        return {"ai": tree(self.ai), "ops": tree(self.ops),
                "cfg": tree(self.tmp / "cfg" / "tasks"), "state": tree(self.tmp / "state" / "tasks"),
                "worktrees": os.readlink(self.ai / ".worktrees"),
                "agents": os.path.realpath(self.tmp / "home" / ".agents")}


@pytest.fixture
def box(tmp_path):
    return Sandbox(tmp_path).build()


def test_save_refuses_with_a_live_claim(box):
    tid = json.loads(box.run("tasks", "add", "three", "--process", "direct", cwd=box.ai).stdout)
    tid = tid.get("id") or tid["task"]["id"]
    box.run("tasks", "start", tid, cwd=box.ai)
    result = box.cutover("save", "--snapshot", box.snapshot, "--ai", box.ai, "--ops", box.ops,
                         "--new-root", box.new_root, check=False)
    assert result.returncode == 1
    assert "live claim" in result.stderr


def test_save_refuses_a_dirty_tree(box):
    (box.ops / "stray").write_text("x\n")
    result = box.cutover("save", "--snapshot", box.snapshot, "--ai", box.ai, "--ops", box.ops,
                         "--new-root", box.new_root, check=False)
    assert result.returncode == 1
    assert "not clean" in result.stderr


def test_rollback_before_commit_restores_everything(box):
    before = box.fingerprint()
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    assert (box.new_root / "tasks").is_dir() and not box.ai.exists()
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before
    assert box.run("tasks", "check", cwd=box.ai).stdout == ""
    assert box.run("git", "status", "--porcelain", cwd=box.ai).stdout == ""


def test_rollback_after_commit_restores_everything(box):
    before = box.fingerprint()
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    box.run("git", "add", "-A", cwd=box.new_root)
    box.run("git", "commit", "-qm", "rename", cwd=box.new_root)
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_rollback_stops_on_foreign_untracked_file(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    (box.new_root / "tasks" / "note.md").write_text("mine\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "tasks/note.md" in result.stderr
    assert (box.ai / "tasks" / "note.md").read_text() == "mine\n"


def test_guard_stops_on_foreign_registry_change(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    registry = box.tmp / "cfg" / "tasks" / "projects.toml"
    registry.write_text(registry.read_text().replace("[projects]\n", '[projects]\nzz = "/elsewhere"\n'))
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "guard" in result.stderr and "zz" in result.stderr
    assert box.new_root.exists()                      # nothing was moved back


def test_rollback_after_rename_stopped_midway(box):
    """A rename stopped after moving its files leaves rename/ai.toml; rollback accepts
    this rename's own inventory and restores everything."""
    before = box.fingerprint()
    box.save()
    env = {**box.env, "TASKS_RENAME_STOP_AFTER": "files"}
    subprocess.run(["tasks", "rename", "ai", "tack"], cwd=box.ai, env=env, text=True, capture_output=True)
    assert (box.tmp / "state" / "tasks" / "rename" / "ai.toml").exists()
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_guard_rejects_an_inventory_for_another_root(box):
    """Same prefixes, a root that merely starts with the checkout's path: not ours."""
    box.save()
    env = {**box.env, "TASKS_RENAME_STOP_AFTER": "files"}
    subprocess.run(["tasks", "rename", "ai", "tack"], cwd=box.ai, env=env, text=True, capture_output=True)
    inventory = box.tmp / "state" / "tasks" / "rename" / "ai.toml"
    text = inventory.read_text()
    inventory.write_text(text.replace(f'"{box.ai}"', f'"{box.ai}-other"'))
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
```

`TASKS_RENAME_STOP_AFTER=files` is the tasks CLI's own stop point: the rename exits after
moving the task files, leaving its inventory, deterministically.

(`test_rollback_after_partial_apply` and the verify tests are added in Task 4.)

- [ ] **Step 2: Run to verify they fail**

Run: `uv run -q --with pytest pytest tools/test_rename_cutover.py -q`
Expected: every test errors (`tools/rename-cutover` missing).

- [ ] **Step 3: Implement `save`, the guard and `rollback`** — `tools/rename-cutover` (then `chmod +x`)

```python
#!/usr/bin/env python3
"""The ai -> tack cutover: save originals, apply the rename, roll back, verify.

One-off tool for docs/specs/2026-09-27-rename-to-tack-design.md. Every path comes from
the command line or the snapshot's meta.json, and every tasks call inherits HOME,
XDG_CONFIG_HOME and XDG_STATE_HOME, so a sandbox rehearsal runs exactly this code.
`tasks rename` is irreversible; rollback restores the saved originals and stops, leaving
the state for a person, at the first check that fails.
"""
import argparse
import filecmp
import json
import os
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


def link_report(root):
    result = subprocess.run([str(Path(root) / "tools" / "tack-link")], text=True, capture_output=True)
    if result.returncode not in (0, 1):
        raise Stop(f"tack-link: {result.stderr.strip()}")
    return result.stdout


def preconditions(ai, ops, old):
    live = [c for c in json.loads(run("tasks", "claims"))["claims"] if c.get("live")]
    if live:
        raise Stop("preconditions: live claim(s): " + ", ".join(c["id"] for c in live))
    for root in (ai, ops):
        if porcelain(root):
            raise Stop(f"preconditions: {root} is not clean")
    if run("git", "-C", ai, "worktree", "list", "--porcelain").count("\nworktree ") != 0:
        raise Stop(f"preconditions: {ai} has more than one worktree")
    check = subprocess.run([str(Path(ai) / "tools" / "tack-link"), "--check"], text=True,
                           capture_output=True)
    if check.returncode != 0:
        raise Stop(f"preconditions: link drift:\n{check.stdout}")


def save(args):
    ai, ops, snap = Path(args.ai).resolve(), Path(args.ops).resolve(), Path(args.snapshot)
    preconditions(ai, ops, args.old)
    config, state = xdg("XDG_CONFIG_HOME", ".config") / "tasks", xdg("XDG_STATE_HOME", ".local/state") / "tasks"
    worktrees = ai / ".worktrees"
    link_text = os.readlink(worktrees) if worktrees.is_symlink() else None
    storage_old = (ai / link_text).resolve() if link_text else None
    meta = {
        "ai": str(ai), "ops": str(ops), "new_root": str(Path(args.new_root).absolute()),
        "old": args.old, "new": args.new, "home": str(Path.home()),
        "ai_head": run("git", "-C", ai, "rev-parse", "HEAD").strip(),
        "ops_head": run("git", "-C", ops, "rev-parse", "HEAD").strip(),
        "config": str(config), "state": str(state), "worktrees_link": link_text,
        "storage_old": str(storage_old) if storage_old else None,
        "storage_new": str(storage_old.parent.parent / args.new / storage_old.name) if storage_old else None,
    }
    snap.mkdir(parents=True, exist_ok=False)
    shutil.copytree(config, snap / "config", symlinks=True)
    shutil.copytree(state, snap / "state", symlinks=True)
    (snap / "links.txt").write_text(link_report(ai))
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
    expected = {"source": meta["old"], "target": meta["new"], "root": meta["ai"]}
    for key, value in expected.items():
        found = data.get(key)
        same = found is not None and (Path(found).resolve() == Path(value).resolve() if key == "root" else found == value)
        if not same:
            raise Stop(f"guard: {path} is a rename inventory for {key} {found!r}, not {value!r}")


def guard(meta, snap):
    old, new = meta["old"], meta["new"]
    config, state = Path(meta["config"]), Path(meta["state"])
    if registry_view(config / "projects.toml", old, new) != registry_view(snap / "config" / "projects.toml", old, new):
        live = registry_view(config / "projects.toml", old, new)
        saved = registry_view(snap / "config" / "projects.toml", old, new)
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
        changed = sorted(live_files ^ saved_files) + sorted(
            f for f in live_files & saved_files
            if not f.endswith(".lock") and not filecmp.cmp(live_root / f, saved_root / f, shallow=False))
        if changed:
            raise Stop(f"guard: {live_root} changed outside {old}/{new}: {', '.join(changed)}")


def move_back(meta):
    ai, new_root = Path(meta["ai"]), Path(meta["new_root"])
    if new_root.exists() and not ai.exists():
        os.rename(new_root, ai)
    elif not ai.exists():
        raise Stop(f"move back: neither {ai} nor {new_root} exists")
    if meta["storage_old"]:
        s_old, s_new = Path(meta["storage_old"]).parent, Path(meta["storage_new"]).parent
        if s_new.exists() and not s_old.exists():
            os.rename(s_new, s_old)
        link = ai / ".worktrees"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(meta["worktrees_link"])


def remove_leftovers(meta):
    ai, old, new = Path(meta["ai"]), meta["old"], meta["new"]
    for line in porcelain(ai):
        path = line[3:]
        name = Path(path).name
        if not (line.startswith("?? ") and path.startswith("tasks/") and name.startswith(f"{new}-")):
            raise Stop(f"leftovers: {path} is not a rename leftover ({line[:2].strip()})")
        original = ai / "tasks" / f"{old}-{name[len(new) + 1:]}"
        if not original.is_file():
            raise Stop(f"leftovers: {path} has no restored original {original.name}")
    for line in porcelain(ai):
        (ai / line[3:]).unlink()
    if porcelain(Path(meta["ops"])):
        raise Stop(f"leftovers: {meta['ops']} is not clean after the reset")


def restore_dir(saved, live):
    shutil.rmtree(live)
    shutil.copytree(saved, live, symlinks=True)


def rollback(args):
    snap = Path(args.snapshot)
    meta = json.loads((snap / "meta.json").read_text())
    ai = Path(meta["ai"])
    guard(meta, snap)
    move_back(meta)
    run("git", "-C", ai, "reset", "-q", "--hard", meta["ai_head"])
    run("git", "-C", meta["ops"], "reset", "-q", "--hard", meta["ops_head"])
    remove_leftovers(meta)
    restore_dir(snap / "config", Path(meta["config"]))
    restore_dir(snap / "state", Path(meta["state"]))
    run(ai / "tools" / "tack-link", "--apply")
    if link_report(ai) != (snap / "links.txt").read_text():
        raise Stop("links: the fresh report differs from the saved one")
    for root in (ai, Path(meta["ops"])):
        if run("tasks", "check", cwd=root).strip():
            raise Stop(f"check: tasks check reports findings in {root}")
        if porcelain(root):
            raise Stop(f"check: {root} is not clean")
    print(f"rolled back to {meta['ai_head'][:7]} (ai) and {meta['ops_head'][:7]} (ops)")


def main(argv):
    parser = argparse.ArgumentParser(prog="rename-cutover")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("save")
    s.add_argument("--snapshot", required=True)
    s.add_argument("--ai", required=True)
    s.add_argument("--ops", required=True)
    s.add_argument("--new-root", required=True)
    s.add_argument("--old", default="ai")
    s.add_argument("--new", default="tack")
    for name in ("apply", "rollback", "verify"):
        sub.add_parser(name).add_argument("--snapshot", required=True)
    args = parser.parse_args(argv)
    try:
        {"save": save, "rollback": rollback, **COMMANDS}[args.command](args)
    except Stop as stop:
        print(f"rename-cutover: {stop}", file=sys.stderr)
        return 1
    return 0


COMMANDS = {}

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

The `worktree list --porcelain` count: the first worktree line has no leading newline, so any `\nworktree ` means a second worktree.

- [ ] **Step 4: Run the tests** — the `save` and guard tests pass; the rollback tests still fail until `apply` exists (Task 4). Run: `uv run -q --with pytest pytest tools/test_rename_cutover.py -q -k "save or guard"` — Expected: `test_save_refuses_with_a_live_claim`, `test_save_refuses_a_dirty_tree` pass; `test_guard_stops_on_foreign_registry_change` fails only at the `apply` call.

- [ ] **Step 5: Commit**

```bash
git add tools/rename-cutover tools/test_rename_cutover.py
git commit -m "feat(tools): rename-cutover saves originals and restores them behind a guard"
```

---

### Task 4: Cutover tool — `apply` and `verify`

**Files:**
- Modify: `tools/rename-cutover`, `tools/test_rename_cutover.py`

**Interfaces:**
- Consumes: Task 3's `meta.json`, `Stop`, `run`, `link_report`, `COMMANDS`.
- Produces: `rename-cutover apply --snapshot DIR` (spec phase 2 steps 2, 3, 6: `tasks rename`, move checkout and storage, `work-link --ensure .worktrees`, `tasks init --prefix <new> --force`, `tack-link --apply`); `rename-cutover verify --snapshot DIR` (a fresh `tack-link --check` exits 0, `tasks check` clean in both roots, `tasks show <an old-prefix id>` resolves, the `.worktrees` link resolves to the moved storage). The content edits (spec steps 4–5) and the commit are the runbook's, in Task 7.

- [ ] **Step 1: Add the failing tests**

```python
def test_apply_renames_moves_and_relinks(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    assert not box.ai.exists()
    assert (box.new_root / "tasks").is_dir()
    assert any(p.name.startswith("tack-") for p in (box.new_root / "tasks").glob("*.md"))
    registry = (box.tmp / "cfg" / "tasks" / "projects.toml").read_text()
    assert f'tack = "{box.new_root}"' in registry and 'ai = "tack"' in registry
    assert os.path.realpath(box.tmp / "home" / ".agents") == str((box.new_root / "agents").resolve())
    assert (box.new_root / ".worktrees").resolve() == (box.sync.parent / ".dropbox-work" / "tack" / ".worktrees").resolve()
    box.cutover("verify", "--snapshot", box.snapshot)


def test_rollback_after_partial_apply(box):
    before = box.fingerprint()
    box.save()
    box.run("tasks", "rename", "ai", "tack", cwd=box.ai)
    os.rename(box.ai, box.new_root)              # interrupted before storage, init --force, links
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before
```

The sandbox's `work-link` must anchor inside `tmp_path`: `work-link` puts the anchor at `<root>/../.dropbox-work` with `--root` the synced root; `apply` calls it with `--root <new_root.parent>`, and the fixture's link text `../../.dropbox-work/ai/.worktrees` from `sync/ai` resolves to `tmp_path/.dropbox-work`, the anchor for `--root tmp_path/sync`. Unset `WORK_ROOT` in the sandbox env (`self.env.pop("WORK_ROOT", None)`) so the anchor is a plain directory.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run -q --with pytest pytest tools/test_rename_cutover.py -q`
Expected: `apply`/`verify` tests fail with `invalid choice` or a KeyError on `COMMANDS`.

- [ ] **Step 3: Implement**

```python
def apply(args):
    snap = Path(args.snapshot)
    meta = json.loads((snap / "meta.json").read_text())
    ai, new_root, old, new = Path(meta["ai"]), Path(meta["new_root"]), meta["old"], meta["new"]
    run("tasks", "rename", old, new, cwd=ai)
    os.rename(ai, new_root)
    if meta["storage_old"]:
        os.rename(Path(meta["storage_old"]).parent, Path(meta["storage_new"]).parent)
        (new_root / ".worktrees").unlink()
        run("work-link", "--root", new_root.parent, "--ensure", ".worktrees", cwd=new_root)
    run("tasks", "init", "--prefix", new, "--force", cwd=new_root)
    run(new_root / "tools" / "tack-link", "--apply")
    print(f"applied: {old} -> {new} at {new_root}")


def verify(args):
    snap = Path(args.snapshot)
    meta = json.loads((snap / "meta.json").read_text())
    new_root, old = Path(meta["new_root"]), meta["old"]
    check = subprocess.run([str(new_root / "tools" / "tack-link"), "--check"], text=True, capture_output=True)
    if check.returncode != 0:
        raise Stop(f"verify: link drift after apply:\n{check.stdout}")
    for root in (new_root, Path(meta["ops"])):
        if run("tasks", "check", cwd=root).strip():
            raise Stop(f"verify: tasks check reports findings in {root}")
    any_old = next(p.stem for p in (new_root / "tasks").glob(f"{meta['new']}-*.md"))
    run("tasks", "show", f"{old}-{any_old.split('-', 1)[1]}", cwd=new_root)
    if meta["storage_new"] and (new_root / ".worktrees").resolve() != Path(meta["storage_new"]).resolve():
        raise Stop("verify: .worktrees does not resolve to the moved storage")
    print("verified")


COMMANDS = {"apply": apply, "verify": verify}
```

- [ ] **Step 4: Run the tests**

Run: `uv run -q --with pytest pytest tools/test_rename_cutover.py -q`
Expected: all pass, including both rollback points and the partial-apply rollback.

- [ ] **Step 5: Commit**

```bash
git add tools/rename-cutover tools/test_rename_cutover.py
git commit -m "feat(tools): rename-cutover applies and verifies the rename"
```

---

### Task 5: Prepare the name edits on branches

**Files (branch `tack-names` in ai, off main after Task 4):**
- Modify: `identity.toml` (`name = "tack"`), `agents/skills/flow/SKILL.md:16-18,159` and `agents/skills/session-logs/SKILL.md:11-12` ("the `ai` checkout" → "the `tack` checkout", "in `ai`" → "in `tack`"), `README.md` (title and the rename note below)

**Files (branch `tack-prefix` in ops — filed as its own ops task, a dependency of ai-4b1878):**
- Modify: `identity-mirror.toml` (`[ai]` → `[tack]`, `name = "tack"`, `path = "tack"`), `bin/ops-projects:58` (`TARGET_PREFIX = "tack"`, docstring at 285 "in the tack project"), `bin/ops-profile:361-364,403-407` (`"tack"` for `"ai"`, messages "tack is not registered…").
- Modify tests whose registry fixtures feed the changed lookups: in `tests/test_ops_profile.py` and `tests/test_ops_projects.py`, every fixture registry or identity keyed `ai` that a fragment lookup or the target lookup reads becomes `tack` (`self.ai = self.base / "tack"`, `roots = {"tack": …}`, `'[tack]\nname = "tack"…'`, and the messages asserting "ai is registered…" / "identity-mirror.toml [ai]" become `tack`). Fixture names that no changed lookup reads (e.g. `tests/test_sessionstart.py`) stay as they are.

**Interfaces:**
- Produces: two unmerged branches; Task 7 merges `tack-names` after `apply` and `tack-prefix` in ops, then runs ops's `just projects`.

- [ ] **Step 1: File the ops piece**

```bash
tasks add "Point ops at the renamed tack project: identity-mirror entry and the two prefix constants" --project ops -p 2 --size s --complexity low --process direct --agent claude-code/claude-opus-5-5 --source "ai:docs/specs/2026-09-27-rename-to-tack-design.md" -b "Why: ai is renamed to tack (spec §3 step 5 in that checkout). ops-projects TARGET_PREFIX and ops-profile reg[\"ai\"] read the registry's [projects] directly, so the tasks alias does not reach them. Done: branch tack-prefix changes identity-mirror.toml [ai] to [tack], TARGET_PREFIX to tack, ops-profile's reg lookups and messages to tack; ops tests pass on the branch; not merged — the cutover (ai-4b1878 Task 7) merges it. Check: just test in ops."
tasks dep ai-4b1878 --on <the printed ops id>
```

- [ ] **Step 2: Build an isolated future registry**

Both branches must validate against the state after the rename, which the live registry
does not have yet: ops's pre-commit runs `just check` (including `ops-projects check`,
which needs `tack` registered, its `AGENTS.md` block current, and its `identity.toml`
naming it `tack`), and ai's pre-commit renders the block through the registered ops
checkout. Neither may run against a live registry changed early, and every tasks call
runs under scratch `HOME`, `XDG_CONFIG_HOME` and `XDG_STATE_HOME`. Resolve the live paths
first, then switch the environment:

```bash
AI=$(readlink -f ~/d/ai); OPS=$(readlink -f ~/d/ops); LIVE_REG=$HOME/.config/tasks/projects.toml
F=<scratchpad>/future; mkdir -p $F/home $F/cfg/tasks $F/state
git clone -q "$AI" $F/tack && git -C $F/tack switch -qc tack-names
git clone -q "$OPS" $F/ops && git -C $F/ops switch -qc tack-prefix
git -C $F/tack config core.hooksPath .githooks
git -C $F/tack config filter.harness-state.clean '.githooks/harness-state-clean %f'
git -C $F/ops config core.hooksPath .githooks
python3 - "$F" "$LIVE_REG" <<'EOF'
import pathlib, sys, tomllib
f, live_path = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
live = tomllib.loads(live_path.read_text())
projects = dict(live["projects"])
projects["ai"], projects["ops"] = str(f / "tack"), str(f / "ops")
aliases = live.get("aliases", {})
lines = ["[projects]", *(f'{k} = "{v}"' for k, v in sorted(projects.items())), "", "[aliases]",
         *(f'{k} = "{v}"' for k, v in sorted(aliases.items()))]
(f / "cfg/tasks/projects.toml").write_text("\n".join(lines) + "\n")
EOF
export HOME=$F/home XDG_CONFIG_HOME=$F/cfg XDG_STATE_HOME=$F/state
(cd $F/tack && tasks rename ai tack)   # makes tack the key and ai its alias in the future registry only
grep -E '^(tack|ai) = ' $F/cfg/tasks/projects.toml   # Expected: tack = "<F>/tack" and ai = "tack"
```

Steps 3–5 run in this environment, with `$F`, `$AI` and `$OPS` as set here. The other
projects' entries point at their live checkouts and are only read.

- [ ] **Step 3: Make both repositories' edits, no generation or gate yet**

- In `$F/ops`: the `tack-prefix` edits above (identity mirror, both constants, the tests).
- In `$F/tack`: the `tack-names` edits above (`identity.toml` `name = "tack"`, the skill
  prose, the README title) and the README rename note:

```markdown
## Renamed from ai

This project was `ai` until 2026-09. Old `ai-<hex>` task ids resolve through the tasks
alias. On a host that synced the rename, run once in this checkout, with no harness
session open: `<adoption command from tasks-7f1596>`, `just link --apply`, and
`work-link --ensure .worktrees` after moving `.dropbox-work/ai` to `.dropbox-work/tack`.
Until then that host's harness sessions start without instructions, skills or hooks.
```

Write the adoption command exactly as tasks-7f1596 ships it; if it has not landed, stop
here and park with this step as the next action.

- [ ] **Step 4: Generate the block, then run the gates and commit**

```bash
(cd $F/ops && bin/ops-projects write)      # regenerates $F/tack/AGENTS.md from the tack mirror
(cd $F/ops && just test && just check)     # Expected: pass (identity names agree now)
git -C $F/ops add -A && git -C $F/ops commit -qm "refactor: point ops at the renamed tack project"
git -C $F/tack add -A -- . ':!tasks'       # the clone's renamed task files are the cutover's
git -C $F/tack commit -qm "docs: name the project tack"
```

Both commits run their repository's pre-commit gate against the future registry:
Expected pass. The `tasks/` changes stay uncommitted in the clone.

- [ ] **Step 5: Bring the branches home** — restore the environment (`export HOME=<your home>`; unset `XDG_CONFIG_HOME` and `XDG_STATE_HOME`), then `git -C "$AI" fetch -q $F/tack tack-names:tack-names` and `git -C "$OPS" fetch -q $F/ops tack-prefix:tack-prefix`. The live registry and state were never touched: `git -C "$AI" status` and `tasks check` in ai unchanged. Keep `$F` for Task 6.

- [ ] **Step 6: Record** — `tasks note ai-4b1878 "branches ready: tack-names (ai), tack-prefix (ops), validated against an isolated future registry"`.

---

### Task 6: Rehearsal (gated on tasks-7f1596)

**Files:**
- Modify: `tools/test_rename_cutover.py`

**Interfaces:**
- Consumes: the adoption command tasks-7f1596 ships (read `tasks --help` and its README section; write the exact invocation into the test below and into Task 5's README note).

- [ ] **Step 1: Add the second-host test** — a second `XDG_CONFIG_HOME`/`XDG_STATE_HOME` pair registers the same sandbox checkout as `ai` before the first host's `apply` (its own `tasks init --prefix ai --force` from the checkout, and one parked task started under the second pair); after the first host's `apply` and commit, the second pair runs the adoption command at `new_root`; assert: `tack` is its live key at `new_root`, `ai = "tack"` is its alias, `tasks show ai-<hex>` resolves under it, its parked task survives (`tasks list --parked` under the second pair lists it), and the first pair's registry and state are untouched (fingerprint of the first pair's `cfg`/`state` unchanged across the adoption).

- [ ] **Step 2: Run the whole suite in the sandbox** — `uv run -q --with pytest pytest tools -q`. Expected: all pass: both rollback points (`test_rollback_before_commit_restores_everything`, `test_rollback_after_commit_restores_everything`), partial-apply rollback, the planted foreign registry entry, the foreign untracked file, and the second-host adoption.

- [ ] **Step 3: Rehearse Task 7 against a copy of the real corpus**

A complete, isolated run of Task 7 steps 2–6, twice. The sandbox shares nothing live:

1. Layout: `R=<scratchpad>/rehearsal`; `R/home`, `R/cfg`, `R/state` for `HOME`,
   `XDG_CONFIG_HOME`, `XDG_STATE_HOME`; `R/sync/` mirrors the Dropbox root; `WORK_ROOT`
   unset. `cp -a ~/d/ai R/sync/ai` and `cp -a ~/d/ops R/sync/ops` (full checkouts with
   their `tack-names` / `tack-prefix` branches; no worktrees, per Task 7's precondition).
2. Storage: the copied `.worktrees` links are relative (`../../.dropbox-work/<name>/.worktrees`),
   so they resolve under `R/.dropbox-work`; create `R/.dropbox-work/ai/.worktrees` and
   `R/.dropbox-work/ops/.worktrees` and confirm `readlink -f R/sync/ai/.worktrees` is under `R`.
3. The rest of the corpus: for every other project in the live registry, copy only its
   `tasks/` directory (and `tasks/.config.toml`) to `R/sync/<same relative path>` and write
   `R/cfg/tasks/projects.toml` with every live entry rewritten to its `R/sync` copy and every
   live alias kept, so cross-project dependencies in ai and ops resolve. `tasks check` in
   `R/sync/ai` and `R/sync/ops` must be clean before starting.
4. Links: `R/sync/ai/tools/tack-link --apply` with `HOME=R/home` (after creating the harness
   homes that exist live, empty).
5. Run A (rollback before commit): `rename-cutover save` (snapshot `R/snapA`, new root
   `R/sync/tack`), `apply`, `git merge tack-names` in `R/sync/tack`, `git merge tack-prefix`
   in `R/sync/ops`, `just projects` and `just test` and `just check` in `R/sync/ops`,
   `verify`, a fresh `tack-link` report equal to `R/snapA/links.txt`; then `rollback`.
   Expected: exit 0, `git status` empty and `tasks check` clean in both copies, registry
   and state equal to the snapshot's.
6. Run B (rollback after commit): the same through the commits of Task 7 step 6 in both
   copies (their pre-commit gates run against `R/cfg`); then `rollback`. Same expectations.
7. Not rehearsed: the fresh harness sessions of Task 7 step 5 (they read the live
   harness homes). The second-host adoption is covered by Step 1's test.

Record `tasks note ai-4b1878 "rehearsal passed <date>: runs A and B, second host"`; commit
the test from Step 1; delete `R`.

### Task 7: Live cutover on this host

Run from a Claude Code session started in the ops checkout. Not a subagent task: every step is a live action on this host; stop at the first failure and run `rollback`.

- [ ] **Step 1: Preconditions** — the user confirms: every other host ran Task 2's `just link --apply`; no other harness session is open on this host. Check: `tasks claims` lists no live claim (end or park any first); no ops claim, live or dead (a dead one would be pruned by apply's own ops retarget, then trip the rollback guard on a change the cutover itself made); `git -C ~/d/ai worktree list` shows one worktree; `just link-check` in ai exits 0; ai and ops clean; tasks-7f1596 is done; Task 6 passed.
- [ ] **Step 2: Save** — `~/d/ai/tools/rename-cutover save --snapshot ~/.local/share/tack-cutover/<date> --ai ~/d/ai --ops ~/d/ops --new-root <Dropbox>/tack`. From here on run the snapshot's copy: `~/.local/share/tack-cutover/<date>/rename-cutover`. This snapshot is durable, not scratch: it must survive until every other host has adopted (Task 8), which can outlast a scratchpad's lifetime.
- [ ] **Step 3: Apply** — `~/.local/share/tack-cutover/<date>/rename-cutover apply --snapshot ~/.local/share/tack-cutover/<date>`.
- [ ] **Step 4: Name edits** — `git -C ~/d/tack merge --no-edit tack-names`; `git -C ~/d/ops merge --no-edit tack-prefix`; in ops `just projects` (regenerates the project lists, including `~/d/tack/AGENTS.md`); `just test` in ops passes.
- [ ] **Step 5: Verify before committing** — `rename-cutover verify --snapshot …`; then a fresh `~/d/tack/tools/tack-link` report must equal `~/.local/share/tack-cutover/<date>/links.txt` (report lines name link paths, not targets, so they do not change with the root; the comparison uses a fresh report after apply, never the apply output); then the spec §5 sweep: `just link-check` clean in tack, and `find ~ -maxdepth 6 -type l` finds no link that resolves into a missing path or names `ai`. Controlled exception to the session freeze: start one fresh Claude Code session and one Codex session in `~/d/tack`, each with a no-write prompt ("Reply with the single word ok."), and confirm: the profile line and global instructions load, the flow and session-logs skills are listed, and a size-only mark on `claude/settings.json` is cleared by each session's Stop. No task writes from those sessions. Any failure: `rollback`.
- [ ] **Step 6: Commit** — in tack: `git add -A && git commit -m "refactor: rename the ai project to tack"` (task files, config, `AGENTS.md`); in ops: `git add -A && git commit -m "chore: regenerate project lists for tack"` if `just projects` changed files. Codex re-trust is not needed (hook command strings did not change); confirm with one more Codex turn.
- [ ] **Step 7: Close the cutover step** — `tasks done ai-04f531 "<what landed>"` from `~/d/tack`, committed; `tasks note ai-4b1878 "renamed on <host>; other hosts adopt per README (ai-2a14e9)"`. The parent stays open until Task 8. Keep the snapshot at `~/.local/share/tack-cutover/<date>` until every other host has adopted.

### Task 8: Other hosts adopt

The user's step on each other host, at their next login, with no harness session open there: the README's "Renamed from ai" steps. Confirm per host with `tasks note ai-2a14e9 "adopted on <host>"`. After the last host: `tasks done ai-2a14e9 "<hosts>"`, then `tasks done ai-4b1878 "<what landed>"` (it refuses while a child is open), both committed; the snapshot can then be deleted.
