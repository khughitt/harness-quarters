# Local Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the work harness configs, Codex's project trust and Codex's approval rules out of tack's tracked tree. Every harness home on this host keeps loading them.

**Architecture:** A gitignored `local/` directory in the checkout holds the files a home links to but the repository must not publish. Dropbox syncs it to every host. The `harness-state` clean filter drops Codex `[projects.*]` tables from the index. tack-link checks targets only for the groups it will act on. `just setup` bootstraps a public clone. The pre-commit hook refuses anything staged under `local/`. The work projects leave the `AGENTS.md` block through the ops task `ops-651ebd`. This plan only regenerates the block once that task lands.

**Tech Stack:** Python 3 (stdlib) hooks and tools, pytest through `uv run --with pytest`, `just`, git.

**Spec:** `docs/specs/2026-09-28-local-layer-design.md` (approved at `3292772`).

## Global Constraints

- `local/` is never tracked. `.gitignore` excludes it, and the pre-commit hook refuses a staged path under it.
- The branch never restages or rewrites `codex/config.toml`. The trust tables leave the index only through `git add --renormalize -- codex/config.toml` in the main checkout, after the merge.
- The branch stages explicit paths only. It never runs `git add -A`, `git add -u` or `git add .`. Any of these would restage `codex/config.toml` through the new filter as soon as its stat changes. After every branch commit, the config blob must equal the one at the branch's base with main:

  ```bash
  test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse "$(git merge-base HEAD main)":codex/config.toml)"
  ```

  Each task's commit step runs this check, and a mismatch stops the task.
- The branch never installs `local/`. The main checkout's live files are copied into the main checkout's `local/` before the merge (Task 5).
- tack-link never creates a missing target, and never checks targets of a skipped group.
- `just setup` never creates work configs. It creates only `local/codex/rules/` and the git configuration.
- No comment or doc names a work term or an absolute host path.
- Tests: `just test` (runs `python3 -m pytest agents/bin -q` and `uv run -q --with pytest pytest .githooks tools -q`).

## Review Focus

1. A trust table that is the last table in the file (no header follows) must be dropped through end of file, and the file must stay valid TOML. Test in Task 1.
2. Tables whose names merely contain `projects` (`[projects_extra]`, `[mcp_servers.projects]`) must survive the filter. Test in Task 1.
3. A missing target in a group whose home is absent or a symlink must not be checked. Otherwise a personal-only public clone could not run `just link`. Test in Task 2.
4. `git add -f local/...` is the only way into the index, and the hook must refuse it, including when the path is staged as the new side of a rename. Test in Task 4.
5. `just setup` run twice, or run in a worktree, must succeed and change nothing the second time. Test in Task 3.

---

### Task 1: The clean filter drops Codex project trust

**Files:**
- Modify: `.githooks/harness-state-clean` (docstring; `TOML_TABLES`)
- Test: `.githooks/test_harness_state_clean.py` (replace `test_toml_keeps_hook_trust_hashes_and_project_trust`; add three tests)

**Interfaces:**
- Consumes: the existing `clean_toml(text)` table-drop mechanism (`TOML_TABLES`: drops the header and every line up to the next header).
- Produces: `TOML_TABLES` gains `re.compile(r"projects\..+")`. No new functions.

- [ ] **Step 1: Write the failing tests.** Replace `test_toml_keeps_hook_trust_hashes_and_project_trust` with the four tests below:

```python
def test_toml_keeps_hook_trust_hashes():
    text = ("[hooks.state.\"/codex/hooks.json:stop:1:0\"]\n"
            "trusted_hash = \"sha256:19c3\"\n")
    assert clean("codex/config.toml", text) == text


def test_toml_drops_project_trust_tables_and_keeps_what_follows():
    text = ("[features]\n"
            "multi_agent = true\n"
            "\n"
            "[projects.\"/work/repo\"]\n"
            "trust_level = \"trusted\"\n"
            "\n"
            "[projects.'/other']\n"
            "trust_level = \"trusted\"\n"
            "\n"
            "[hooks.state.\"/codex/hooks.json:stop:1:0\"]\n"
            "trusted_hash = \"sha256:19c3\"\n")
    assert clean("codex/config.work.toml", text) == (
        "[features]\n"
        "multi_agent = true\n"
        "\n"
        "[hooks.state.\"/codex/hooks.json:stop:1:0\"]\n"
        "trusted_hash = \"sha256:19c3\"\n")


def test_toml_drops_a_trailing_project_trust_table_to_end_of_file():
    text = ("[features]\n"
            "multi_agent = true\n"
            "\n"
            "[projects.\"/last\"]\n"
            "trust_level = \"trusted\"\n")
    cleaned = clean("codex/config.toml", text)
    assert cleaned == "[features]\nmulti_agent = true\n\n"
    import tomllib
    assert tomllib.loads(cleaned) == {"features": {"multi_agent": True}}


def test_toml_keeps_tables_that_only_mention_projects():
    text = ("[projects_extra]\n"
            "a = 1\n"
            "\n"
            "[mcp_servers.projects]\n"
            "command = \"x\"\n")
    assert clean("codex/config.toml", text) == text
```

- [ ] **Step 2: Run them and confirm the two drop tests fail.**

Run: `uv run -q --with pytest pytest .githooks/test_harness_state_clean.py -q`
Expected: `test_toml_drops_project_trust_tables_and_keeps_what_follows` and `test_toml_drops_a_trailing_project_trust_table_to_end_of_file` FAIL, because the tables are kept. The other two pass.

- [ ] **Step 3: Implement.** In `.githooks/harness-state-clean`, change `TOML_TABLES` to:

```python
# Tables dropped whole, header and blank lines up to the next header included. Codex
# appends a [projects."<path>"] table each time a directory is trusted: that is host
# state naming every checkout, kept in the live file and out of the index.
TOML_TABLES = (re.compile(r"tui\.model_availability_nux"), re.compile(r"projects\..+"))
```

In the module docstring, change "Everything else the harness writes (plugin toggles, marketplace sources, hook trust hashes, project trust) stays tracked" to "Project trust (`[projects.*]`) is host state and is dropped too. Everything else the harness writes (plugin toggles, marketplace sources, hook trust hashes) stays tracked."

- [ ] **Step 4: Run the tests and confirm they pass.**

Run: `uv run -q --with pytest pytest .githooks/test_harness_state_clean.py -q`
Expected: all pass.

- [ ] **Step 5: Confirm the branch did not restage the live config.** Run `git status --short codex/config.toml`. Expected: empty. If git shows `M` because the filter changed, do not stage it: the removal is committed in the main checkout after the merge (Task 5).

- [ ] **Step 6: Commit.**

```bash
git add .githooks/harness-state-clean .githooks/test_harness_state_clean.py
git commit -m "feat(githooks): keep Codex project trust out of the index"
test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse "$(git merge-base HEAD main)":codex/config.toml)"
```

### Task 2: tack-link checks targets only for active groups

**Files:**
- Modify: `tools/tack-link` (`load`, new `check_targets`, `main`)
- Test: `tools/test_tack_link.py`

**Interfaces:**
- Consumes: `Entry(link, target, home)`, `is_real_dir(path)`, `ManifestError`.
- Produces:
  - `load(root) -> (entries, homes)`: structural checks only, with no target existence check.
  - `check_targets(root: Path, entries: list[Entry]) -> None` raises `ManifestError` for the first entry that is active (`entry.home is None or is_real_dir(entry.home)`) and whose target does not exist. For a target under `root / "local"`, the message adds the remedy.
  - `main` calls `check_targets` right after `load`, and both errors exit 2 as today.

- [ ] **Step 1: Write the failing tests.** Append to `tools/test_tack_link.py`:

```python
def test_missing_target_in_an_absent_home_is_not_checked(world):
    root, home = world
    (root / "links.toml").write_text(MANIFEST + '\n[harness.work]\nhome = "~/.work"\n'
                                     '[harness.work.links]\n"settings.json" = "local/work.json"\n')
    result = link(root, home)
    assert result.returncode == 0, result.stderr
    assert states(result)["~/.work"] == "skipped"


def test_missing_target_in_a_symlinked_home_is_not_checked(world, tmp_path):
    root, home = world
    (tmp_path / "elsewhere").mkdir()
    (home / ".work").symlink_to(tmp_path / "elsewhere")
    (root / "links.toml").write_text(MANIFEST + '\n[harness.work]\nhome = "~/.work"\n'
                                     '[harness.work.links]\n"settings.json" = "local/work.json"\n')
    assert link(root, home).returncode == 0


def test_missing_local_target_in_an_active_home_names_the_remedy(world):
    root, home = world
    (home / ".work").mkdir()
    (root / "links.toml").write_text(MANIFEST + '\n[harness.work]\nhome = "~/.work"\n'
                                     '[harness.work.links]\n"settings.json" = "local/work.json"\n')
    result = link(root, home, "--apply")
    assert result.returncode == 2
    assert "local/work.json" in result.stderr
    assert "another host's `local/`" in result.stderr and "just setup" in result.stderr
    assert not (home / ".work" / "settings.json").exists()
    assert not (home / ".agents").exists()          # nothing is written on this error


def test_local_target_resolves_like_any_other(world):
    root, home = world
    (home / ".work").mkdir()
    (root / "local").mkdir()
    (root / "local" / "work.json").write_text("{}\n")
    (root / "links.toml").write_text(MANIFEST + '\n[harness.work]\nhome = "~/.work"\n'
                                     '[harness.work.links]\n"settings.json" = "local/work.json"\n')
    assert link(root, home, "--apply").returncode == 0
    assert (home / ".work" / "settings.json").resolve() == (root / "local" / "work.json").resolve()
```

Also extend `test_missing_target_is_rejected`. A missing target that is not under `local/` must not carry the remedy:

```python
def test_missing_target_is_rejected(world):
    root, home = world
    (root / "links.toml").write_text('[required]\n"~/.x" = "nope"\n')
    result = link(root, home)
    assert result.returncode == 2
    assert "nope" in result.stderr
    assert "just setup" not in result.stderr
```

- [ ] **Step 2: Run them and confirm the two skip tests fail.**

Run: `uv run -q --with pytest pytest tools/test_tack_link.py -q`
Expected: `test_missing_target_in_an_absent_home_is_not_checked` and `test_missing_target_in_a_symlinked_home_is_not_checked` FAIL with exit 2 ("does not exist"). `test_missing_local_target_in_an_active_home_names_the_remedy` FAILs on the remedy text.

- [ ] **Step 3: Implement.** In `tools/tack-link`:

Remove this loop from `load()`:

```python
    for entry in entries:
        if not entry.target.exists():
            raise ManifestError(f"{entry.link}: target {entry.target} does not exist")
```

Add after `is_real_dir`:

```python
def active(entry):
    return entry.home is None or is_real_dir(entry.home)


def check_targets(root, entries):
    """Every target this host will link to exists. A skipped group's targets are not
    checked: a public clone has no local/, and a host without a work home needs none."""
    for entry in entries:
        if not active(entry) or entry.target.exists():
            continue
        message = f"{entry.link}: target {entry.target} does not exist"
        if (root / "local") in entry.target.parents:
            message += ("; local/ is untracked: copy it from another host's `local/`, "
                        "or run `just setup` for the directories it creates")
        raise ManifestError(message)
```

In `plan()`, replace `if entry.home is not None and not is_real_dir(entry.home):` with `if not active(entry):`.

In `main()`, validate right after loading:

```python
    try:
        entries, homes = load(root)
        check_targets(root, entries)
    except (ManifestError, KeyError, tomllib.TOMLDecodeError) as error:
```

In the module docstring, append: "A target is checked only when its entry applies (a required link, or a group whose home is a real directory). A missing one is an error, never created."

- [ ] **Step 4: Run all tack-link tests.**

Run: `uv run -q --with pytest pytest tools/test_tack_link.py -q`
Expected: all pass. That includes `test_real_manifest_validates_in_a_fresh_clone`, which still reads the unchanged `links.toml` of `HEAD`.

- [ ] **Step 5: Commit.**

```bash
git add tools/tack-link tools/test_tack_link.py
git commit -m "feat(tack-link): check targets only for groups this host links"
test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse "$(git merge-base HEAD main)":codex/config.toml)"
```

### Task 3: Move the work configs and Codex rules to `local/`; `just setup`

**Files:**
- Modify: `.gitignore`, `links.toml`, `justfile`, `README.md`
- Remove from the index and from this worktree: `claude/settings.work.json`, `codex/config.work.toml`, `codex/rules/default.rules`
- Test: `tools/test_tack_link.py` (real-manifest tests)

**Interfaces:**
- Consumes: `check_targets` (Task 2).
- Produces: the `just setup` recipe, and the `links.toml` targets `local/claude/settings.work.json`, `local/codex/config.work.toml` and `local/codex/rules`. Task 5 relies on these exact paths.

- [ ] **Step 1: Write the failing tests.** Append to `tools/test_tack_link.py`:

```python
def fresh_clone(tmp_path):
    repo = Path(__file__).resolve().parent.parent
    clone = tmp_path / "clone"
    run("clone", "-q", str(repo), str(clone))
    return clone


def just_setup(clone):
    assert shutil.which("just"), "just is required for the setup tests"
    return subprocess.run(["just", "setup"], cwd=clone, text=True, capture_output=True)


def test_real_manifest_with_codex_needs_setup_first(tmp_path):
    clone = fresh_clone(tmp_path)
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir()
    before = link(clone, home)
    assert before.returncode == 2
    assert "local/codex/rules" in before.stderr and "just setup" in before.stderr
    assert just_setup(clone).returncode == 0
    after = link(clone, home)
    assert after.returncode == 0, after.stderr
    assert states(after)["~/.codex/rules"] == "create"


def test_real_manifest_work_home_without_local_names_the_file(tmp_path):
    clone = fresh_clone(tmp_path)
    home = tmp_path / "home"
    (home / ".claude-work").mkdir(parents=True)
    assert just_setup(clone).returncode == 0
    result = link(clone, home)
    assert result.returncode == 2
    assert "local/claude/settings.work.json" in result.stderr


def test_setup_is_idempotent_and_creates_only_the_rules_directory(tmp_path):
    clone = fresh_clone(tmp_path)
    assert just_setup(clone).returncode == 0
    second = just_setup(clone)
    assert second.returncode == 0, second.stderr
    assert sorted(p.relative_to(clone / "local").as_posix()
                  for p in (clone / "local").rglob("*")) == ["codex", "codex/rules"]
    config = lambda key: run("-C", str(clone), "config", key).stdout.strip()
    assert config("core.hooksPath") == ".githooks"
    assert config("filter.harness-state.clean") == ".githooks/harness-state-clean %f"
    assert run("-C", str(clone), "status", "--porcelain").stdout == ""   # local/ is ignored
```

These tests clone `HEAD`, so they fail until this task's changes are committed. Commit them with the changes in Step 6. Step 2 checks them against the working tree through a temporary commit.

- [ ] **Step 2: Make the tree changes.**

`.gitignore`, add a line:

```
local/
```

`links.toml`: change these three targets and leave everything else alone:

```toml
[harness.claude-work.links]
"settings.json" = "local/claude/settings.work.json"
...
[harness.codex.links]
"rules" = "local/codex/rules"
...
[harness.codex-work.links]
"config.toml" = "local/codex/config.work.toml"
```

Add a header comment line to `links.toml`: "Targets under local/ are untracked (Dropbox carries them between hosts); `just setup` creates the directories a public clone needs."

`justfile`: add at the top:

```just
# Once per clone: git hooks and the harness-state filter, and the untracked local/
# directories a public clone needs. Work configs under local/ come from another host.
setup:
    git config core.hooksPath .githooks
    git config filter.harness-state.clean '.githooks/harness-state-clean %f'
    mkdir -p local/codex/rules
```

Remove the tracked files. This deletes the worktree's copies only; the main checkout's live files are handled in Task 5:

```bash
git rm -q claude/settings.work.json codex/config.work.toml codex/rules/default.rules
```

- [ ] **Step 3: Update `README.md`.**
  - **Setup:** replace the two `git config` lines with `just setup`, and say what it does (the list in the recipe comment).
  - **Filter paragraph:** add project trust (`[projects.*]` in `codex/config*.toml`) to what the filter keeps out of the index. A checkout of the file drops the list, and Codex asks again per directory.
  - **Layout:** add a `local/` bullet. It is untracked and synced by Dropbox, not git. It holds `claude/settings.work.json`, `codex/config.work.toml` and `codex/rules/`. The `~/.claude-work`, `~/.codex-work` and `~/.codex/rules` links point into it. Change the `claude/` and `codex/` bullet so the `.work.` variants are named under `local/`.
  - **Pre-commit paragraph:** add that the hook refuses a staged path under `local/` (Task 4).
  - **Home links:** add that a group's targets are checked only where its home is a real directory, and that a missing `local/` target names the remedy.
  - **After "Renamed from ai",** add a section "Local layer (2026-09)". It says: on a host that shares this checkout, once Dropbox has synced `local/`, run `just link --apply` once with no Codex or work-home session open.

- [ ] **Step 4: Run the tests against a temporary commit.** The real-manifest tests clone `HEAD`, so they need the changes committed. The script resets only a commit it actually created, and it keeps the test status:

```bash
bash -c '
set -u
base=$(git rev-parse HEAD)
git add -- .gitignore links.toml justfile README.md tools/test_tack_link.py
if ! git commit -qm "wip: local layer"; then
  echo "temporary commit refused; HEAD untouched at $base" >&2
  exit 1
fi
uv run -q --with pytest pytest tools -q
status=$?
git reset -q --soft "$base"
test "$(git rev-parse HEAD)" = "$base" || { echo "HEAD is not back at $base" >&2; exit 1; }
exit $status
'
```

Expected: exit 0. All tests pass, including the three new real-manifest tests and `test_real_manifest_validates_in_a_fresh_clone`, and `HEAD` is back at `base` with the changes still staged. A non-zero exit means either the tests failed or the commit was refused. In both cases `HEAD` has not moved past `base`.

- [ ] **Step 5: Run `tools/ops-docs check`** (the README contract): `python3 tools/ops-docs check`. Expected: exit 0, no output.

- [ ] **Step 6: Commit.**

```bash
git add -- .gitignore links.toml justfile README.md tools/test_tack_link.py
git status --short        # staged: the five files above plus the three `D` removals from Step 2; nothing else
git commit -m "feat: move work configs and Codex rules to the untracked local layer

just setup bootstraps a clone: hooks, filter, and local/codex/rules."
test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse "$(git merge-base HEAD main)":codex/config.toml)"
```

### Task 4: pre-commit refuses anything staged under `local/`

**Files:**
- Modify: `.githooks/pre-commit` (new `local_layer()` check, `main`, docstring)
- Test: `.githooks/test_pre_commit.py`

**Interfaces:**
- Consumes: none.
- Produces: `local_layer() -> int`. It returns `fail(...)` when `git diff --cached --name-only --diff-filter=ACMR -- local` lists anything, and 0 otherwise. `main()` returns `local_layer() or projects_block() or docs_check()`.

- [ ] **Step 1: Write the failing tests.** Append to `.githooks/test_pre_commit.py`, using the existing `world` fixture and helpers:

```python
def test_refuses_a_force_added_local_file(world):
    repo, env, _ = world
    (repo / ".gitignore").write_text("local/\n")
    (repo / "local").mkdir()
    (repo / "local" / "settings.work.json").write_text("{}\n")
    sh(repo, "git", "add", "-f", "local/settings.work.json")
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "local/settings.work.json" in result.stderr


def test_refuses_a_rename_into_local(world):
    repo, env, _ = world
    (repo / "settings.work.json").write_text("{}\n")
    sh(repo, "git", "add", "settings.work.json")
    sh(repo, "git", "commit", "-q", "-m", "tracked")
    (repo / "local").mkdir()
    sh(repo, "git", "mv", "settings.work.json", "local/settings.work.json")
    result = run_hook(repo, env)
    assert result.returncode == 1
    assert "local/settings.work.json" in result.stderr


def test_passes_when_nothing_under_local_is_staged(world):
    repo, env, _ = world
    (repo / "notes.md").write_text("x\n")
    sh(repo, "git", "add", "notes.md")
    assert run_hook(repo, env).returncode == 0
```

- [ ] **Step 2: Run them and confirm the two refusal tests fail.**

Run: `uv run -q --with pytest pytest .githooks/test_pre_commit.py -q`
Expected: both refusal tests FAIL (exit 0).

- [ ] **Step 3: Implement.** In `.githooks/pre-commit`, add before `main`:

```python
def local_layer():
    """local/ holds host and work state that must never be tracked; only `git add -f`
    can stage it, and this refuses that."""
    names = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR",
                            "--", "local"], check=True, text=True, capture_output=True).stdout.split()
    if names:
        return fail("staged paths under local/, which is untracked host and work state: "
                    + ", ".join(names) + "; unstage them with `git restore --staged`")
    return 0
```

Change `main()` to `return local_layer() or projects_block() or docs_check()`. Add a paragraph to the module docstring: "It refuses any staged path under local/, the untracked layer (docs/specs/2026-09-28-local-layer-design.md)."

- [ ] **Step 4: Run the tests and confirm they pass.**

Run: `uv run -q --with pytest pytest .githooks -q`
Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
git add .githooks/pre-commit .githooks/test_pre_commit.py
git commit -m "feat(githooks): refuse staged paths under local/"
test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse "$(git merge-base HEAD main)":codex/config.toml)"
```

### Task 5: Roll out on this host

This task changes the live checkout. Before the copy step, the user confirms that no Codex session is open in any home and no work-home session is open, on every host sharing the checkout. The executor asks and waits for that answer. The executor is a personal-home Claude session, which neither step touches.

**Files:** the main checkout (`/` of the repository, not the worktree).

- [ ] **Step 1: Sync the branch with main.** main moves while the branch is open (other sessions commit and merge there). In `.worktrees/local-layer`:

```bash
git -c filter.harness-state.clean=cat rebase main
git merge-base --is-ancestor main HEAD
test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse main:codex/config.toml)"
git diff --name-only main HEAD | sort
```

The rebase runs with the clean filter switched off. The worktree's copies of `codex/config*.toml` still carry trust tables in their blobs, so under the new filter they read as modified, and a plain rebase stops on them. Replaying commits does not re-clean files, so switching the filter off changes no commit's content. If the rebase stops on a conflict, run `git rebase --abort` and resolve it with the filter on: a `git add` under `clean=cat` would stage unfiltered config.

Expected: the rebase succeeds. The ancestry check exits 0, and the blob check passes, because the branch never changes that file, so after the rebase it equals main's. The diff lists only the files this plan touches: `.gitignore`, `.githooks/harness-state-clean`, `.githooks/test_harness_state_clean.py`, `.githooks/pre-commit`, `.githooks/test_pre_commit.py`, `tools/tack-link`, `tools/test_tack_link.py`, `links.toml`, `justfile`, `README.md`, the three removed files, the plan and spec, and `tasks/` records.
- [ ] **Step 2: Full suite, then the sessions.** Run `just test` in `.worktrees/local-layer`. Expected: all pass. Only now ask the user to close the Codex and work-home sessions on every host, and wait for the confirmation.
- [ ] **Step 3: Recheck ancestry, then copy the live files into the main checkout's `local/`.** main may have moved while the user was closing sessions. From the main checkout, run `git merge-base --is-ancestor main local-layer`. If it fails, repeat Steps 1 and 2 before copying anything. Then exclude `local/` in main, which stays harmless once the merged `.gitignore` covers it, and copy:

```bash
grep -qx '/local/' .git/info/exclude || echo '/local/' >> .git/info/exclude
mkdir -p local/claude local/codex
cp -a claude/settings.work.json local/claude/
cp -a codex/config.work.toml local/codex/
cp -a codex/rules local/codex/
cmp claude/settings.work.json local/claude/settings.work.json
cmp codex/config.work.toml local/codex/config.work.toml
diff -r codex/rules local/codex/rules
git status --porcelain --ignored -- local | grep -qx '!! local/'
```

Expected: no output from `cmp` or `diff`, and the last line exits 0 because `local/` is ignored.
- [ ] **Step 4: Merge.** Merge immediately after Step 3. If `git merge-base --is-ancestor main local-layer` now fails, stop: repeat Steps 1 and 2. The Step 3 copies stay valid, because no session writes them now. If `git status --short -- claude/settings.work.json codex/config.work.toml codex/rules` lists any of them, the merge would refuse to delete a modified file. Their live content is already verified in `local/` (Step 3), so run `git restore -- claude/settings.work.json codex/config.work.toml codex/rules` first. Then run `git merge --ff-only local-layer`. Expected: fast-forward, and `test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse HEAD@{1}:codex/config.toml)"` passes: the merge did not change the config blob. Then `ls claude/settings.work.json codex/config.work.toml codex/rules 2>&1` reports all three missing, and the `local/` copies are still present.
- [ ] **Step 5: Repoint.** `just link --apply`, then `just link-check`. Expected: exit 0. Then:

```bash
readlink -f ~/.claude-work/settings.json ~/.codex-work/config.toml ~/.codex/rules
```

Expected: all three resolve under the main checkout's `local/`.
- [ ] **Step 6: Drop trust from the index.**

```bash
git add --renormalize -- codex/config.toml
git show :codex/config.toml | grep -c '^\[projects'     # 0
grep -c '^\[projects' codex/config.toml                 # unchanged from before
git diff --cached --stat                                # only codex/config.toml
git commit -m "chore(codex): keep project trust out of the index" -- codex/config.toml
```

- [ ] **Step 7: Acceptance.**
  - `git ls-files local codex/rules` prints nothing.
  - `just setup` is a no-op, and `git status --short` is clean.
  - In a fresh clone of main after `just setup`, `git status --porcelain` is empty. Before this task's trust-removal commit, the clone showed `codex/config.toml` as modified, because the new filter strips tables that `HEAD` still carried.
  - The work-term grep over the tree matches only the generated projects block in `AGENTS.md`.
- [ ] **Step 8: Live check (user).** The user starts one Codex session and one work-home Claude session. The work plugins are listed, and Codex does not re-prompt for trust in a trusted checkout. Record the result with `tasks note tack-4cd688`.
- [ ] **Step 9: Push** main.

### Task 6: Regenerate the projects block after `ops-651ebd`

Blocked on `ops-651ebd` (ops: private profiles).

- [ ] **Step 1:** In the ops checkout, `just projects`. It rewrites the block in tack's `AGENTS.md`.
- [ ] **Step 2:** In tack, confirm `git diff AGENTS.md` removes only the private-profile entries. The work-term grep over the tree then matches nothing.
- [ ] **Step 3:** In a work checkout, `ops-profile session` prints "### Projects under this profile" with those entries.
- [ ] **Step 4: Commit** `chore(agents): regenerate the projects block without private-profile projects`, and push.
