# Codex Trust Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Codex's `[projects."<path>"]` trust tables survive every git command that overwrites the live `codex/config.toml`, with no manual step.

**Architecture:** A new tool, `.githooks/codex-trust`, saves the live trust tables into the untracked `local/codex/trust.toml` and inserts the missing ones back before the live file's first table header. The Stop hook `harness-state-refresh` runs `codex-trust sync` at every turn end. New `post-checkout`, `post-merge` and `post-rewrite` wrappers run `codex-trust hook <name>`, which restores and restages the file right after a git command, in the main checkout only.

**Tech Stack:** Python 3 stdlib (`tomllib`, `fcntl`, `runpy`), POSIX sh wrappers, pytest through `uv run --with pytest`, git 2.55.

**Spec:** `docs/specs/2026-09-29-codex-trust-restore-design.md` (approved 2026-09-29, amended while planning: insertion point, restaging, rebases).

## Global Constraints

- Only `codex/config.toml` is touched. `local/codex/config.work.toml` is untracked and out of scope.
- The saved copy is `local/codex/trust.toml`, and its lock is `local/codex/trust.toml.lock`. `local/` is never staged: the pre-commit hook refuses it.
- `capture` never removes a saved table, and nothing prunes the saved copy.
- A `restore` never changes the filter's output of the live file, and so never changes what git stages.
- Neither tool writes a file whose content would not change. The Stop hook runs every turn, and Dropbox syncs every write.
- The branch stages explicit paths only. It never runs `git add -A`, `git add -u` or `git add .`. After every branch commit, the config blob must equal the one at the branch's base:

  ```bash
  test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse "$(git merge-base HEAD main)":codex/config.toml)"
  ```

  Each task's commit step runs this check, and a mismatch stops the task.
- No comment or doc names an absolute host path.
- Each task has a step record (a child of `tack-de8d97`). Run `tasks start <step>` before the task. `tasks done <step> "<what landed>"` goes in the task's own commit, with `git add tasks/<step>.md`. Stage task records by name: an unrelated uncommitted record may sit under `tasks/`.
- Focused test runs: `uv run -q --with pytest pytest .githooks/test_codex_trust.py -q -k <name>` (from the worktree root). Before each commit: `just test`. This justfile has no `test-fast` or `test-one`.

## Review Focus

1. **A restore that changes what git stages.** A blank line the filter keeps (text appended after the last table) makes the file really modified. The Stop hook then never stages it, and a rebase refuses to start. `restore` checks the invariant itself with the filter's `clean_toml` and writes nothing when it would break. Pinned by `test_restore_leaves_what_git_stages_unchanged` and `test_a_file_with_no_header_and_no_final_newline_is_refused` (Task 1).
2. **A rebase that replays a config commit after a restore.** The rebase's in-memory index drops a restage made mid-rebase, and the replay stops with "local changes would be overwritten". Pinned by `test_a_rebase_that_replays_a_config_commit_keeps_trust` and `test_a_rebase_stopped_on_a_conflict_continues_after_the_stop_hook` (Task 3).
3. **A turn end that changes nothing.** It must not rewrite the saved copy or the live file. Pinned by `test_a_sync_that_changes_nothing_writes_nothing` (Task 1).
4. **Turn ends of concurrent sessions.** Racing restores would insert a table twice, and Codex refuses a duplicate table. Pinned by `test_concurrent_syncs_leave_one_copy_of_each_table` (Task 1).
5. **The home link and the file mode.** `~/.codex/config.toml` must stay a link, and the live file must stay `0600`. Pinned by `test_restore_keeps_a_home_link_and_the_file_mode` (Task 1).

---

### Task 1: codex-trust saves and restores trust tables

**Files:**
- Modify: `.githooks/harness-state-clean` (name the trust pattern `PROJECT_TRUST`)
- Create: `.githooks/codex-trust` (executable)
- Create: `.githooks/test_codex_trust.py`

**Interfaces:**
- Consumes: `harness-state-clean`'s module globals `TOML_HEADER` (header regex; `group(1)` is the table name), the new `PROJECT_TRUST` (full-match pattern over a table name) and `clean_toml(text) -> str` (the filter's TOML path), read with `runpy.run_path`.
- Produces: the CLI `codex-trust capture | restore | sync`, run by path from any cwd, acting on the checkout it lives in. Exit 0 on success. On failure, exit non-zero with `codex-trust: <message>` on stderr. Python functions that Task 3 extends: `restore() -> bool` (True when it wrote), `locked()` (context manager: checks `local/codex/` and the live file, then holds the flock), `git(*args) -> str`, `git_path(name) -> Path`, `linked_worktree() -> bool`, `fail(message)`, `USAGE`, `main(argv)`.

- [ ] **Step 1: Name the filter's trust pattern.** In `.githooks/harness-state-clean`, replace

```python
# Tables dropped whole, header and blank lines up to the next header included. Codex
# appends a [projects."<path>"] table each time a directory is trusted: that is host
# state naming every checkout, kept in the live file and out of the index.
TOML_TABLES = (re.compile(r"tui\.model_availability_nux"), re.compile(r"projects\..+"))
```

with

```python
# Codex appends a [projects."<path>"] table each time a directory is trusted: that is
# host state naming every checkout, kept in the live file and out of the index.
# codex-trust saves what this pattern drops and puts it back after a checkout.
PROJECT_TRUST = re.compile(r"projects\..+")
# Tables dropped whole, header and blank lines up to the next header included.
TOML_TABLES = (re.compile(r"tui\.model_availability_nux"), PROJECT_TRUST)
```

Run: `uv run -q --with pytest pytest .githooks/test_harness_state_clean.py -q`
Expected: all pass (no behaviour change).

- [ ] **Step 2: Write the failing tests.** Create `.githooks/test_codex_trust.py`:

```python
"""codex-trust saves Codex project trust in local/ and puts back what a checkout dropped."""
import shutil
import stat
import subprocess
import tomllib
from pathlib import Path

import pytest

HOOKS = Path(__file__).parent
HOOK_FILES = ("harness-state-clean", "codex-trust")
CONFIG = "codex/config.toml"
BASE = "[features]\nhooks = true\n"
TUI = "[tui]\nx = 1\n"
A = '[projects."/work/a"]\ntrust_level = "trusted"\n'
B = '[projects."/work/b"]\ntrust_level = "trusted"\n'


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], check=check, text=True,
                          capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A main checkout shaped like this one: the filter, the hooks, a tracked config, local/."""
    repo = tmp_path / "tack"
    (repo / ".githooks").mkdir(parents=True)
    for name in HOOK_FILES:
        shutil.copy2(HOOKS / name, repo / ".githooks" / name)
    (repo / "codex").mkdir()
    (repo / "local" / "codex").mkdir(parents=True)
    (repo / ".gitattributes").write_text("codex/config*.toml filter=harness-state\n")
    (repo / ".gitignore").write_text("local/\n")
    (repo / CONFIG).write_text(BASE)
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    git(repo, "config", "filter.harness-state.clean", ".githooks/harness-state-clean %f")
    git(repo, "config", "core.hooksPath", ".githooks")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def live(repo):
    return repo / CONFIG


def saved(repo):
    return repo / "local" / "codex" / "trust.toml"


def projects(path):
    return sorted(tomllib.loads(path.read_text()).get("projects", {}))


def trust(repo, *args):
    """Run codex-trust as the hooks do: by path, from another directory."""
    return subprocess.run([str(repo / ".githooks" / "codex-trust"), *args], cwd=repo.parent,
                          text=True, capture_output=True)


def clean(repo, text):
    return subprocess.run([str(repo / ".githooks" / "harness-state-clean"), CONFIG],
                          input=text, check=True, text=True, capture_output=True).stdout


def test_capture_into_a_missing_saved_copy_saves_the_live_tables(repo):
    live(repo).write_text(BASE + "\n" + A + "\n" + B)

    result = trust(repo, "capture")

    assert result.returncode == 0, result.stderr
    assert saved(repo).read_text() == A + "\n" + B
    assert live(repo).read_text() == BASE + "\n" + A + "\n" + B


def test_capture_keeps_saved_tables_the_live_file_lacks(repo):
    saved(repo).write_text(A)
    live(repo).write_text(BASE + "\n" + B)

    assert trust(repo, "capture").returncode == 0

    assert saved(repo).read_text() == A + "\n" + B


def test_capture_takes_the_live_text_of_a_saved_table(repo):
    saved(repo).write_text(A + "\n" + B)
    untrusted = A.replace('"trusted"', '"untrusted"')
    live(repo).write_text(BASE + "\n" + untrusted)

    assert trust(repo, "capture").returncode == 0

    assert saved(repo).read_text() == untrusted + "\n" + B


def test_capture_with_nothing_to_save_creates_no_saved_copy(repo):
    result = trust(repo, "capture")

    assert result.returncode == 0, result.stderr
    assert not saved(repo).exists()


def test_a_sync_that_changes_nothing_writes_nothing(repo):
    live(repo).write_text(BASE + "\n" + A)
    saved(repo).write_text(A)
    before = [(p.stat().st_ino, p.stat().st_mtime_ns) for p in (live(repo), saved(repo))]

    result = trust(repo, "sync")

    assert result.returncode == 0, result.stderr
    assert [(p.stat().st_ino, p.stat().st_mtime_ns) for p in (live(repo), saved(repo))] == before


def test_restore_inserts_the_missing_tables_before_the_first_header(repo):
    saved(repo).write_text(A + "\n" + B)
    live(repo).write_text('personality = "p"\n\n' + BASE + "\n" + A)

    result = trust(repo, "restore")

    assert result.returncode == 0, result.stderr
    assert live(repo).read_text() == 'personality = "p"\n\n' + B + "\n" + BASE + "\n" + A
    assert projects(live(repo)) == ["/work/a", "/work/b"]


def test_restore_leaves_what_git_stages_unchanged(repo):
    before = '# harness\npersonality = "p"\n\n# features\n' + BASE + "\n[notice]\nx = 1\n"
    live(repo).write_text(before)
    saved(repo).write_text(A + "\n" + B)

    assert trust(repo, "restore").returncode == 0

    assert projects(live(repo)) == ["/work/a", "/work/b"]
    assert clean(repo, live(repo).read_text()) == clean(repo, before)


def test_restore_appends_to_a_file_with_no_header(repo):
    live(repo).write_text('personality = "p"\n')
    saved(repo).write_text(A)

    assert trust(repo, "restore").returncode == 0

    assert live(repo).read_text() == 'personality = "p"\n' + A
    assert clean(repo, live(repo).read_text()) == clean(repo, 'personality = "p"\n')


def test_a_file_with_no_header_and_no_final_newline_is_refused(repo):
    live(repo).write_text('personality = "p"')
    saved(repo).write_text(A)

    result = trust(repo, "restore")

    assert result.returncode != 0
    assert "no final newline" in result.stderr
    assert live(repo).read_text() == 'personality = "p"'


def test_restore_twice_inserts_nothing_the_second_time(repo):
    saved(repo).write_text(A)

    assert trust(repo, "restore").returncode == 0
    first = live(repo).read_text()
    assert trust(repo, "restore").returncode == 0

    assert live(repo).read_text() == first == A + "\n" + BASE


def test_restore_matches_tables_by_project_not_header_text(repo):
    saved(repo).write_text(A)
    spaced = '[ projects."/work/a" ]\ntrust_level = "untrusted"\n'
    live(repo).write_text(BASE + "\n" + spaced)

    assert trust(repo, "restore").returncode == 0

    assert live(repo).read_text() == BASE + "\n" + spaced


def test_a_last_table_without_a_trailing_newline_round_trips(repo):
    live(repo).write_text(BASE + "\n" + A.rstrip("\n"))
    assert trust(repo, "capture").returncode == 0
    live(repo).write_text(BASE)

    assert trust(repo, "restore").returncode == 0

    assert saved(repo).read_text() == A
    assert live(repo).read_text() == A + "\n" + BASE


def test_a_malformed_saved_copy_fails_and_leaves_the_live_file_unchanged(repo):
    saved(repo).write_text('[projects."/work/a"\ntrust_level =\n')

    result = trust(repo, "restore")

    assert result.returncode != 0
    assert "local/codex/trust.toml is not valid TOML" in result.stderr
    assert live(repo).read_text() == BASE


def test_a_saved_copy_holding_more_than_trust_is_refused(repo):
    saved(repo).write_text(A + "\n[features]\nhooks = false\n")

    result = trust(repo, "restore")

    assert result.returncode != 0
    assert "holds more than project trust: features" in result.stderr
    assert live(repo).read_text() == BASE


def test_trust_outside_project_tables_is_refused(repo):
    live(repo).write_text('projects = { "/work/a" = { trust_level = "trusted" } }\n' + BASE)

    result = trust(repo, "capture")

    assert result.returncode != 0
    assert "outside" in result.stderr
    assert not saved(repo).exists()


def test_restore_keeps_a_home_link_and_the_file_mode(repo, tmp_path):
    live(repo).chmod(0o600)
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").symlink_to(live(repo))
    saved(repo).write_text(A)

    assert trust(repo, "restore").returncode == 0

    assert (home / "config.toml").is_symlink()
    assert projects(home / "config.toml") == ["/work/a"]
    assert stat.S_IMODE(live(repo).stat().st_mode) == 0o600


def test_a_linked_worktree_is_refused(repo, tmp_path):
    other = tmp_path / "other"
    git(repo, "worktree", "add", "-q", "-b", "other", str(other))
    (other / "local" / "codex").mkdir(parents=True)

    result = trust(other, "capture")

    assert result.returncode != 0
    assert "linked worktree" in result.stderr


def test_a_missing_local_directory_names_just_setup(repo):
    shutil.rmtree(repo / "local")

    result = trust(repo, "capture")

    assert result.returncode != 0
    assert "just setup" in result.stderr


def test_an_unknown_operation_prints_the_usage(repo):
    result = trust(repo, "prune")

    assert result.returncode != 0
    assert "usage: codex-trust" in result.stderr


def test_concurrent_syncs_leave_one_copy_of_each_table(repo):
    saved(repo).write_text(A + "\n" + B)
    runs = [subprocess.Popen([str(repo / ".githooks" / "codex-trust"), "sync"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for _ in range(8)]

    for run in runs:
        _, err = run.communicate()
        assert run.returncode == 0, err

    text = live(repo).read_text()
    assert text.count('[projects."/work/a"]') == 1
    assert text.count('[projects."/work/b"]') == 1
    assert projects(live(repo)) == ["/work/a", "/work/b"]
```

- [ ] **Step 3: Run the tests to see them fail.**

Run: `uv run -q --with pytest pytest .githooks/test_codex_trust.py -q`
Expected: every test errors in the fixture with `FileNotFoundError` on `codex-trust` (the file does not exist).

- [ ] **Step 4: Write the tool.** Create `.githooks/codex-trust` and `chmod +x` it:

```python
#!/usr/bin/env python3
"""Keep Codex project trust across git commands that overwrite codex/config.toml.

The harness-state clean filter keeps Codex's [projects."<path>"] trust tables out of
the index, so a git command that writes a new blob of codex/config.toml over the live
file drops them. This tool saves them in local/codex/trust.toml, untracked and carried
between hosts by Dropbox, and puts back the ones a checkout dropped:

    capture   merge the live file's trust tables into the saved copy
    restore   insert each saved table whose project the live file lacks
    sync      capture, then restore

capture never removes a saved table: a dropped list must not shrink the saved one, and
nothing prunes it. To forget a directory, delete its table from both files. restore
inserts before the live file's first table header, which leaves the filter's output,
and so what git stages, unchanged. The Stop hook harness-state-refresh runs sync. The
tool works on the checkout it lives in and refuses a linked worktree, whose
codex/config.toml is not live. docs/specs/2026-09-29-codex-trust-restore-design.md.
"""
import contextlib
import fcntl
import os
import runpy
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LIVE_NAME = "codex/config.toml"
SAVED_NAME = "local/codex/trust.toml"
LIVE = REPO / LIVE_NAME
SAVED = REPO / SAVED_NAME
LOCK = SAVED.with_name("trust.toml.lock")
USAGE = "usage: codex-trust capture | restore | sync"
# The filter decides what a checkout drops; reading its patterns keeps the saved tables
# exactly the dropped ones.
FILTER = runpy.run_path(str(HERE / "harness-state-clean"))
TOML_HEADER = FILTER["TOML_HEADER"]
PROJECT_TRUST = FILTER["PROJECT_TRUST"]
CLEAN_TOML = FILTER["clean_toml"]


def fail(message):
    sys.exit(f"codex-trust: {message}")


def git(*args):
    result = subprocess.run(["git", "-C", str(REPO), *args], text=True, capture_output=True)
    if result.returncode != 0:
        fail(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def git_path(name):
    return Path(git("rev-parse", "--path-format=absolute", "--git-path", name))


def linked_worktree():
    return (git("rev-parse", "--path-format=absolute", "--git-dir")
            != git("rev-parse", "--path-format=absolute", "--git-common-dir"))


def parse(text, name):
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        fail(f"{name} is not valid TOML: {error}")


def trust_tables(text, name):
    """The [projects."<path>"] tables in text, as {path: table text} in file order.

    A table runs from its header to the next header, trailing blank lines dropped. Trust
    written any other way (an inline table, dotted keys) is refused: the filter would
    not drop it, and restore could not put it back.
    """
    blocks = []
    for line in text.splitlines(keepends=True):
        header = TOML_HEADER.match(line)
        if header:
            blocks.append([line] if PROJECT_TRUST.fullmatch(header.group(1)) else None)
        elif blocks and blocks[-1] is not None:
            blocks[-1].append(line)
    tables = {}
    for block in (block for block in blocks if block is not None):
        table = "".join(block).rstrip("\n") + "\n"
        paths = list(parse(table, name).get("projects", {}))
        if len(paths) != 1:
            fail(f"{name}: {block[0].strip()} does not name one project")
        if paths[0] in tables:
            fail(f"{name}: project {paths[0]!r} has more than one table")
        tables[paths[0]] = table
    if set(parse(text, name).get("projects", {})) != set(tables):
        fail(f'{name} declares project trust outside [projects."<path>"] tables')
    return tables


def render(tables):
    """Table texts separated by one blank line."""
    return "\n".join(tables)


def read_saved():
    if not SAVED.exists():
        return {}
    text = SAVED.read_text()
    other = set(parse(text, SAVED_NAME)) - {"projects"}
    if other:
        fail(f"{SAVED_NAME} holds more than project trust: {', '.join(sorted(other))}")
    return trust_tables(text, SAVED_NAME)


def write(path, text):
    """Replace path by one rename, keeping its mode: the live config is private (0600)."""
    mode = path.stat().st_mode & 0o7777 if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as out:
            out.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def insert(live, tables):
    """live with tables before its first table header, or at its end when it has none.

    The filter drops everything from a trust header to the next header, so the inserted
    tables and the blank line that ends them leave its output unchanged. Text appended
    after the last table would not: the blank line before it is kept. A file with no
    header and no final newline is refused: the newline a table needs before it would
    change what git stages.
    """
    offset = 0
    for line in live.splitlines(keepends=True):
        if TOML_HEADER.match(line):
            return live[:offset] + tables + "\n" + live[offset:]
        offset += len(line)
    if live and not live.endswith("\n"):
        fail(f"{LIVE_NAME} has no table header and no final newline; add the newline")
    return live + tables


def capture():
    merged = read_saved() | trust_tables(LIVE.read_text(), LIVE_NAME)
    text = render(merged.values())
    if text != (SAVED.read_text() if SAVED.exists() else ""):
        write(SAVED, text)


def restore():
    """Insert the saved tables the live file lacks; True when it wrote."""
    live = LIVE.read_text()
    present = trust_tables(live, LIVE_NAME)
    missing = [table for path, table in read_saved().items() if path not in present]
    if not missing:
        return False
    result = insert(live, render(missing))
    parse(result, f"{LIVE_NAME} with the restored tables")
    if CLEAN_TOML(result) != CLEAN_TOML(live):
        fail(f"restoring would change what git stages from {LIVE_NAME}; nothing written")
    write(LIVE.resolve(), result)
    return True


@contextlib.contextmanager
def locked():
    """Hold the host's lock: two restores racing would each insert a table, and Codex
    refuses a file with a duplicate table."""
    if not SAVED.parent.is_dir():
        fail("local/codex/ is missing; run `just setup`")
    if not LIVE.is_file():
        fail(f"{LIVE_NAME} is missing")
    with open(LOCK, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def main(argv):
    args = argv[1:]
    if not (len(args) == 1 and args[0] in ("capture", "restore", "sync")):
        fail(USAGE)
    if linked_worktree():
        fail(f"{REPO} is a linked worktree; its {LIVE_NAME} is not live")
    with locked():
        if args[0] in ("capture", "sync"):
            capture()
        if args[0] in ("restore", "sync"):
            restore()


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 5: Run the tests to see them pass.**

Run: `uv run -q --with pytest pytest .githooks/test_codex_trust.py -q`
Expected: all pass. If `test_concurrent_syncs_leave_one_copy_of_each_table` fails, the lock is not held around both the read and the write. Fix the lock, not the test.

- [ ] **Step 6: Commit.**

```bash
just test
git add .githooks/harness-state-clean .githooks/codex-trust .githooks/test_codex_trust.py
git commit -m "feat(githooks): codex-trust saves and restores Codex project trust"
test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse "$(git merge-base HEAD main)":codex/config.toml)"
```

---

### Task 2: The Stop hook syncs trust at every turn end

**Files:**
- Modify: `.githooks/harness-state-refresh` (docstring; `main`)
- Modify: `.githooks/test_harness_state_refresh.py` (fixture only)
- Modify: `.githooks/test_codex_trust.py` (`HOOK_FILES`; new helpers and tests)

**Interfaces:**
- Consumes: `codex-trust sync` (Task 1), run by path as a sibling of `harness-state-refresh`.
- Produces: `harness-state-refresh` runs `codex-trust sync` after its `index.lock` check and before its staging step. When the sync fails, the staging still runs, and then the hook exits non-zero with the sync's stderr. Task 3's tests use the helpers `trusted(repo, *tables)`, `commit_config(repo, text, message)`, `status(repo)` and `refresh(repo)`.

- [ ] **Step 1: Write the failing tests.** In `.githooks/test_codex_trust.py`, change `HOOK_FILES` to

```python
HOOK_FILES = ("harness-state-clean", "codex-trust", "harness-state-refresh")
```

and append:

```python
def trusted(repo, *tables):
    """Codex trusted tables and its turn ended: they are live, saved, and git's mark is clear.

    The tables go before the first header, where the filter's output stays equal to HEAD.
    """
    live(repo).write_text("".join(table + "\n" for table in tables) + live(repo).read_text())
    assert trust(repo, "capture").returncode == 0
    git(repo, "add", "--", CONFIG)


def commit_config(repo, text, message):
    live(repo).write_text(text)
    git(repo, "add", "--", CONFIG)
    git(repo, "commit", "-q", "-m", message)


def status(repo):
    return git(repo, "status", "--porcelain").stdout


def refresh(repo):
    """Run the Stop hook as a harness does: from another directory, payload on stdin."""
    return subprocess.run([str(repo / ".githooks" / "harness-state-refresh")], cwd=repo.parent,
                          input='{"hook_event_name":"Stop"}', text=True, capture_output=True)


def test_the_stop_hook_saves_new_trust(repo):
    live(repo).write_text(A + "\n" + BASE)

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert saved(repo).read_text() == A
    assert status(repo) == ""


def test_the_stop_hook_restores_trust_after_a_hard_reset(repo):
    trusted(repo, A)
    live(repo).write_text(TUI + "\n" + live(repo).read_text())
    git(repo, "reset", "-q", "--hard")
    assert projects(live(repo)) == []

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert projects(live(repo)) == ["/work/a"]
    assert status(repo) == ""


def test_the_stop_hook_restores_trust_after_a_stash_round_trip(repo):
    trusted(repo, A)
    live(repo).write_text(TUI + "\n" + live(repo).read_text())
    git(repo, "stash", "-q")
    git(repo, "stash", "pop", "-q")
    assert projects(live(repo)) == []

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert projects(live(repo)) == ["/work/a"]
    diff = git(repo, "diff", "--", CONFIG).stdout
    assert "+[tui]" in diff
    assert "projects" not in diff


def test_the_stop_hook_restores_trust_during_a_merge_stopped_on_a_conflict(repo):
    (repo / "u").write_text("base\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "u")
    git(repo, "switch", "-q", "-c", "side")
    (repo / "u").write_text("side\n")
    git(repo, "add", "u")
    commit_config(repo, TUI + "\n" + BASE, "side")
    git(repo, "switch", "-q", "main")
    (repo / "u").write_text("main\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "main")
    trusted(repo, A)

    assert git(repo, "merge", "-q", "side", check=False).returncode == 1
    assert projects(live(repo)) == []

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert projects(live(repo)) == ["/work/a"]
    (repo / "u").write_text("both\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "--no-edit")
    committed = git(repo, "show", "HEAD:" + CONFIG).stdout
    assert "[tui]" in committed
    assert "projects" not in committed
    assert status(repo) == ""


def test_a_failed_sync_still_clears_the_marks_and_fails_the_hook(repo):
    saved(repo).write_text("[projects\n")
    live(repo).write_text('model = "gpt-6"\n' + BASE)

    result = refresh(repo)

    assert result.returncode != 0
    assert "codex-trust:" in result.stderr
    assert git(repo, "diff-files", "--quiet", "--", CONFIG, check=False).returncode == 0
```

- [ ] **Step 2: Run the tests to see them fail.**

Run: `uv run -q --with pytest pytest .githooks/test_codex_trust.py -q -k stop_hook`
Expected: `test_the_stop_hook_saves_new_trust` fails (no saved copy), and the three restore tests fail with `projects == []`.

- [ ] **Step 3: Call the sync from the Stop hook.** In `.githooks/harness-state-refresh`, add after `PATTERNS`:

```python
TRUST = Path(__file__).resolve().with_name("codex-trust")
```

and replace `main` with:

```python
def main():
    sys.stdin.read()
    lock = Path(checked("rev-parse", "--path-format=absolute", "--git-path", "index.lock").strip())
    if lock.exists():
        return
    trust = subprocess.run([str(TRUST), "sync"], text=True, capture_output=True)
    marked = checked("diff-files", "--name-only", "--", *PATTERNS).split()
    stale = [path for path in marked if filtered_equal(path)]
    if stale:
        checked("add", "--", *stale)
    if trust.returncode != 0:
        sys.exit(trust.stderr.strip())
```

Append to the module docstring:

```
It first runs `codex-trust sync`, which saves Codex's project trust into
local/codex/trust.toml and puts back the tables a checkout dropped. The staging below
then clears the mark that restore's insert leaves. A failed sync still lets the marks
clear, then fails the hook with the sync's message.
```

- [ ] **Step 4: Give the refresh tests' fixture what the sync needs.** In `.githooks/test_harness_state_refresh.py`, replace the fixture body's setup lines

```python
    repo = tmp_path / "ai"
    (repo / ".githooks").mkdir(parents=True)
    (repo / "claude").mkdir()
    for name in ("harness-state-clean", "harness-state-refresh"):
        shutil.copy2(HOOKS / name, repo / ".githooks" / name)
    (repo / ".gitattributes").write_text("claude/settings*.json filter=harness-state\n")
```

with

```python
    repo = tmp_path / "ai"
    (repo / ".githooks").mkdir(parents=True)
    (repo / "claude").mkdir()
    (repo / "codex").mkdir()
    (repo / "local" / "codex").mkdir(parents=True)
    for name in ("harness-state-clean", "harness-state-refresh", "codex-trust"):
        shutil.copy2(HOOKS / name, repo / ".githooks" / name)
    (repo / ".gitattributes").write_text("claude/settings*.json filter=harness-state\n"
                                         "codex/config*.toml filter=harness-state\n")
    (repo / ".gitignore").write_text("local/\n")
    (repo / "codex" / "config.toml").write_text("[features]\nhooks = true\n")
```

Change the fixture docstring to `"""A checkout shaped like this one: the filter, the refresh, codex-trust, and filtered configs."""`.

- [ ] **Step 5: Run the tests to see them pass.**

Run: `uv run -q --with pytest pytest .githooks/test_codex_trust.py .githooks/test_harness_state_refresh.py -q`
Expected: all pass.

- [ ] **Step 6: Commit.**

```bash
just test
git add .githooks/harness-state-refresh .githooks/test_harness_state_refresh.py .githooks/test_codex_trust.py
git commit -m "feat(githooks): the Stop hook saves and restores Codex project trust"
test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse "$(git merge-base HEAD main)":codex/config.toml)"
```

---

### Task 3: Git hooks restore trust right after a checkout, merge or rebase

**Files:**
- Modify: `.githooks/codex-trust` (docstring; `USAGE`; `hook` operation; `main`)
- Create: `.githooks/post-checkout`, `.githooks/post-merge`, `.githooks/post-rewrite` (executable)
- Modify: `.githooks/test_codex_trust.py` (`HOOK_FILES`; new tests)

**Interfaces:**
- Consumes: `restore() -> bool`, `locked()`, `git()`, `git_path()`, `linked_worktree()`, `fail()` (Task 1); the test helpers `trusted`, `commit_config`, `status` and `refresh` (Task 2).
- Produces: `codex-trust hook post-checkout|post-merge|post-rewrite`. It exits 0 silently in a linked worktree, and exits 0 from `post-checkout` while `rebase-merge` or `rebase-apply` exists. Otherwise it restores, and when that wrote, restages `codex/config.toml` if its filtered diff is empty and `index.lock` is absent.

- [ ] **Step 1: Write the failing tests.** In `.githooks/test_codex_trust.py`, change `HOOK_FILES` to

```python
HOOK_FILES = ("harness-state-clean", "codex-trust", "harness-state-refresh",
              "post-checkout", "post-merge", "post-rewrite")
```

and append:

```python
def side_with_config(repo, text=TUI + "\n" + BASE):
    git(repo, "switch", "-q", "-c", "side")
    commit_config(repo, text, "side")
    git(repo, "switch", "-q", "main")


def test_a_merge_that_replaces_the_config_keeps_trust(repo):
    side_with_config(repo)
    trusted(repo, A)

    git(repo, "merge", "-q", "side")

    assert live(repo).read_text() == A + "\n" + TUI + "\n" + BASE
    assert status(repo) == ""


def test_a_branch_switch_keeps_trust_both_ways(repo):
    side_with_config(repo)
    trusted(repo, A)

    git(repo, "switch", "-q", "side")
    assert live(repo).read_text() == A + "\n" + TUI + "\n" + BASE
    git(repo, "switch", "-q", "main")

    assert live(repo).read_text() == A + "\n" + BASE
    assert status(repo) == ""


@pytest.mark.parametrize("command", [("checkout", "--"), ("restore",)])
def test_a_checkout_of_the_file_keeps_trust(repo, command):
    trusted(repo, A)
    live(repo).write_text(TUI + "\n" + live(repo).read_text())

    git(repo, *command, CONFIG)

    assert live(repo).read_text() == A + "\n" + BASE
    assert status(repo) == ""


def test_a_rebase_that_replays_a_config_commit_keeps_trust(repo):
    git(repo, "switch", "-q", "-c", "side")
    (repo / "u").write_text("side\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "side")
    git(repo, "switch", "-q", "main")
    commit_config(repo, TUI + "\n" + BASE, "main config")
    trusted(repo, A)

    result = git(repo, "rebase", "side", check=False)

    assert result.returncode == 0, result.stderr
    assert live(repo).read_text() == A + "\n" + TUI + "\n" + BASE
    assert "projects" not in git(repo, "show", "HEAD:" + CONFIG).stdout
    assert status(repo) == ""


def test_a_rebase_stopped_on_a_conflict_continues_after_the_stop_hook(repo):
    (repo / "u").write_text("base\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "u")
    git(repo, "switch", "-q", "-c", "side")
    (repo / "u").write_text("side\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "side")
    git(repo, "switch", "-q", "main")
    (repo / "u").write_text("main\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "main")
    commit_config(repo, TUI + "\n" + BASE, "main config")
    trusted(repo, A)
    assert git(repo, "rebase", "side", check=False).returncode != 0
    assert projects(live(repo)) == []

    assert refresh(repo).returncode == 0
    assert projects(live(repo)) == ["/work/a"]
    (repo / "u").write_text("both\n")
    git(repo, "add", "u")
    result = git(repo, "-c", "core.editor=true", "rebase", "--continue", check=False)

    assert result.returncode == 0, result.stderr
    assert live(repo).read_text() == A + "\n" + TUI + "\n" + BASE
    assert status(repo) == ""


def test_a_rebase_that_only_fast_forwards_leaves_trust_to_the_stop_hook(repo):
    side_with_config(repo)
    trusted(repo, A)

    git(repo, "rebase", "-q", "side")
    assert projects(live(repo)) == []
    assert refresh(repo).returncode == 0

    assert live(repo).read_text() == A + "\n" + TUI + "\n" + BASE
    assert status(repo) == ""


def test_a_linked_worktree_is_left_alone(repo, tmp_path):
    side_with_config(repo)
    trusted(repo, A)
    other = tmp_path / "other"
    git(repo, "worktree", "add", "-q", str(other), "side")
    other_config = other / CONFIG
    other_config.write_text("[notice]\nx = 1\n\n" + other_config.read_text())

    result = git(other, "checkout", "-q", "--", CONFIG)

    assert result.stderr == ""
    assert other_config.read_text() == TUI + "\n" + BASE
    assert git(other, "status", "--porcelain").stdout == ""
    assert projects(live(repo)) == ["/work/a"]


def test_a_switch_to_a_branch_without_the_hooks_waits_for_the_switch_back(repo):
    git(repo, "switch", "-q", "-c", "old")
    git(repo, "rm", "-q", ".githooks/post-checkout", ".githooks/post-merge",
        ".githooks/post-rewrite")
    commit_config(repo, TUI + "\n" + BASE, "old")
    git(repo, "switch", "-q", "main")
    trusted(repo, A)

    git(repo, "switch", "-q", "old")
    assert projects(live(repo)) == []
    git(repo, "switch", "-q", "main")

    assert live(repo).read_text() == A + "\n" + BASE
    assert status(repo) == ""


def test_an_unknown_git_hook_prints_the_usage(repo):
    result = trust(repo, "hook", "pre-push")

    assert result.returncode != 0
    assert "usage: codex-trust" in result.stderr
```

- [ ] **Step 2: Run the tests to see them fail.**

Run: `uv run -q --with pytest pytest .githooks/test_codex_trust.py -q`
Expected: every test errors in the fixture with `FileNotFoundError` on `post-checkout`.

- [ ] **Step 3: Write the wrappers.** Create the three files and `chmod +x` them.

`.githooks/post-checkout`:

```sh
#!/bin/sh
# Put back the Codex project trust this checkout dropped (.githooks/codex-trust).
exec "$(dirname "$0")/codex-trust" hook post-checkout
```

`.githooks/post-merge`:

```sh
#!/bin/sh
# Put back the Codex project trust this merge dropped (.githooks/codex-trust).
exec "$(dirname "$0")/codex-trust" hook post-merge
```

`.githooks/post-rewrite`:

```sh
#!/bin/sh
# Put back the Codex project trust this rebase dropped (.githooks/codex-trust). Git
# feeds the rewritten commits on stdin; drain them so it never writes to a closed pipe.
cat >/dev/null
exec "$(dirname "$0")/codex-trust" hook post-rewrite
```

- [ ] **Step 4: Add the hook operation.** In `.githooks/codex-trust`:

Replace `USAGE` with:

```python
GIT_HOOKS = ("post-checkout", "post-merge", "post-rewrite")
USAGE = "usage: codex-trust capture | restore | sync | hook post-checkout|post-merge|post-rewrite"
# A rebase runs post-checkout after checking out the new base, then replays commits
# from its in-memory index, which drops a restage made there; the file keeps its new
# size, and the replay of a commit that touches it stops with "local changes would be
# overwritten". post-rewrite restores when the rebase ends.
REBASE_STATE = ("rebase-merge", "rebase-apply")
```

Add after `restore`:

```python
def restage():
    """Stage the restored file when its filtered diff is empty, as harness-state-refresh does.

    The insert changes the file's size, and git calls a file of another size modified
    without running the filter; a rebase refuses to start on that mark. While another
    git process holds the index, the next turn end's refresh stages it instead.
    """
    if git_path("index.lock").exists():
        return
    diff = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "--", LIVE_NAME],
                          text=True, capture_output=True)
    if diff.returncode not in (0, 1):
        fail(f"git diff {LIVE_NAME}: {diff.stderr.strip()}")
    if diff.returncode == 0:
        git("add", "--", LIVE_NAME)


def rebasing():
    return any(git_path(state).exists() for state in REBASE_STATE)
```

Replace `main` with:

```python
def main(argv):
    args = argv[1:]
    if not (len(args) == 1 and args[0] in ("capture", "restore", "sync")
            or len(args) == 2 and args[0] == "hook" and args[1] in GIT_HOOKS):
        fail(USAGE)
    if linked_worktree():
        if args[0] == "hook":
            return
        fail(f"{REPO} is a linked worktree; its {LIVE_NAME} is not live")
    if args[0] == "hook":
        if args[1] == "post-checkout" and rebasing():
            return
        with locked():
            if restore():
                restage()
        return
    with locked():
        if args[0] in ("capture", "sync"):
            capture()
        if args[0] in ("restore", "sync"):
            restore()
```

In the module docstring, add the operation to the list:

```
    hook <name>   restore from a git hook, then restage the file
```

Replace its sentence "The Stop hook harness-state-refresh runs sync." with "The Stop hook harness-state-refresh runs sync; the post-checkout, post-merge and post-rewrite hooks run hook, which skips a linked worktree silently and, from post-checkout, a rebase in progress."

- [ ] **Step 5: Run the tests to see them pass.**

Run: `uv run -q --with pytest pytest .githooks -q`
Expected: all pass. If `test_a_rebase_that_replays_a_config_commit_keeps_trust` fails with "local changes would be overwritten", `post-checkout` is restoring during the rebase. Check `rebasing()`.

- [ ] **Step 6: Commit.**

```bash
just test
git add .githooks/codex-trust .githooks/post-checkout .githooks/post-merge .githooks/post-rewrite .githooks/test_codex_trust.py
git commit -m "feat(githooks): restore Codex project trust after a checkout, merge or rebase"
test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse "$(git merge-base HEAD main)":codex/config.toml)"
```

---

### Task 4: Docs say trust is restored, and how to forget a directory

**Files:**
- Modify: `README.md` (the filter paragraph under setup)
- Modify: `.githooks/harness-state-clean` (module docstring)
- Modify: `docs/specs/2026-09-28-local-layer-design.md` (§3.2, first bullet)

**Interfaces:**
- Consumes: the behaviour of Tasks 1–3.
- Produces: docs only.

- [ ] **Step 1: README.** Replace the text from "Codex's project trust, the `[projects."<path>"]` tables it appends to" through "Dropbox's file history is the fallback when a merge already dropped them." with:

```markdown
Codex's project trust, the `[projects."<path>"]` tables it adds to
`codex/config*.toml`, is host state and stays out of the index the same way. So any git
command that writes a new blob of `codex/config.toml` over the live file drops the whole
list, on every host at once, since the checkout is shared through Dropbox.
`.githooks/codex-trust` puts it back. At every turn end the Stop hook below saves the
live tables into `local/codex/trust.toml`, never removing one, and inserts the ones the
live file lacks before its first table header. The `post-checkout`, `post-merge` and
`post-rewrite` hooks insert them right after a switch, a checkout of the file, a merge
or a rebase, in the main checkout only. Where no hook runs (`git stash`,
`git reset --hard`, a merge stopped on a conflict, a rebase that only fast-forwards, a
fresh clone that has a saved copy), the list is back at the next turn end. A Codex session started before
then asks again. While the main checkout is on a branch older than these hooks, nothing
restores the list until the checkout switches back. A table Codex added since the last
turn end is not saved yet. Nothing prunes the saved copy: to forget a directory, delete
its table from both `local/codex/trust.toml` and `codex/config.toml` before the next
turn end.
```

Keep the paragraph's remainder, from "After the local-layer rollout, other worktrees" on, as it is.

- [ ] **Step 2: Filter docstring.** In `.githooks/harness-state-clean`, replace "Project trust (`[projects.*]`) is host state and is dropped too." with "Project trust (`[projects.*]`) is host state and is dropped too; `codex-trust` saves it in local/ and puts it back after a checkout drops it."

- [ ] **Step 3: Local-layer spec.** In `docs/specs/2026-09-28-local-layer-design.md` §3.2, replace the bullet

```markdown
- A checkout of the file (a fresh clone, `git checkout -- codex/config.toml`) drops
  the trust list, and Codex asks again per directory.
```

with

```markdown
- A checkout of the file (a fresh clone, `git checkout -- codex/config.toml`) drops
  the trust list, and Codex asks again per directory. Since `tack-de8d97`,
  `.githooks/codex-trust` restores it (`docs/specs/2026-09-29-codex-trust-restore-design.md`).
```

- [ ] **Step 4: Check and commit.**

```bash
tools/ops-docs check
just test
git add README.md .githooks/harness-state-clean docs/specs/2026-09-28-local-layer-design.md
git commit -m "docs: Codex project trust is restored automatically"
test "$(git rev-parse HEAD:codex/config.toml)" = "$(git rev-parse "$(git merge-base HEAD main)":codex/config.toml)"
```

Expected: `tools/ops-docs check` prints nothing and exits 0.

---

### Task 5: Roll out in the main checkout

Runs after the branch is merged into `main` in the main checkout (superpowers:finishing-a-development-branch). No Codex session may be open in any home during Step 3.

**Files:** none tracked. `local/codex/trust.toml` is created, untracked.

**Interfaces:**
- Consumes: the merged `.githooks/codex-trust` in the main checkout.
- Produces: the first saved copy of the live trust list.

- [ ] **Step 1: Capture by hand, right after the merge and before any other git command in the main checkout.**

```bash
.githooks/codex-trust capture
```

Expected: exit 0, and `local/codex/trust.toml` exists.

- [ ] **Step 2: Check the saved copy against the live file.**

```bash
diff <(grep '^\[projects\.' codex/config.toml | sort) <(grep '^\[projects\.' local/codex/trust.toml | sort)
python3 -c 'import tomllib; print(len(tomllib.load(open("local/codex/trust.toml", "rb"))["projects"]))'
```

Expected: `diff` prints nothing. The count equals `grep -c '^\[projects\.' codex/config.toml`.

- [ ] **Step 3: Live check.** First confirm that the live file carries no real change. The checkout below discards one, and the saved copy protects only trust tables:

```bash
git diff --quiet -- codex/config.toml
```

If this exits non-zero, stop: show the user `git diff -- codex/config.toml` and leave the live check to them. Otherwise, drop the list the way a checkout does, and watch the hook put it back:

```bash
touch codex/config.toml
git checkout -- codex/config.toml
grep -m1 '^\[' codex/config.toml
git status --porcelain -- codex/config.toml
diff <(grep '^\[projects\.' codex/config.toml | sort) <(grep '^\[projects\.' local/codex/trust.toml | sort)
```

Expected: the first header is a `[projects.` one, because restore inserts before the first header. `git status` prints nothing, and `diff` prints nothing. The checkout also drops the model pick and Codex's bookkeeping, as any checkout of the file does. The next `/model` in Codex sets the pick again.

- [ ] **Step 4: Close the task.** In the main checkout:

```bash
tasks done tack-de8d97 "codex-trust saves Codex project trust in local/codex/trust.toml and restores it from the Stop hook and the post-checkout, post-merge and post-rewrite hooks; rolled out and live-checked"
tasks check
git add tasks/tack-de8d97.md tasks/tack-5ac94e.md
git commit -m "chore(tasks): close tack-de8d97"
```

Close the Task 5 step record first (`tasks done <step> "…"`): `tasks done` refuses a parent with an open child. Then run `tt-report`, and remove the worktree: `git worktree unlock .worktrees/codex-trust-restore` and `git worktree remove .worktrees/codex-trust-restore`. No host pointer resolves into it: the `~/.local/bin` link resolves into the main checkout.
