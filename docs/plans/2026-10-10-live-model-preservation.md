# Live Model Preservation Implementation Plan

Status: revised plan approved 2026-10-10 by the user (plan review round 1 on
`hq-a77096`). The user approved the Stop-only
capture and `forget` fallback spec after Task 1 disproved post-write picker events.
Task: `hq-a77096`; design task: `hq-14d183`. Execution method: native inline
(chosen 2026-10-10), with flow gates required by the enrolled trial.

Tasks 1–5 are complete; Task 6 documentation is implemented and awaits the final
fresh branch review. Task 7 rollout remains separately gated. Remaining work captures at Stop, never captures from `PostModelSwitch`,
and resets only through `forget`. There is one separately approved rollout merge.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model picks in the live harness configs survive every Git command that rewrites them, while a deliberate return to the default through `forget` stays the default.

**Architecture:** A new tool, `.githooks/live-picks`, saves each tracked live file's pick in untracked `local/live-picks.json` and restores it into a file that holds none of its owned fields. It runs from the existing Stop refresh (capture before the index-lock skip, restore after), and from the `post-checkout`/`post-merge`/`post-rewrite` hooks after `codex-trust`. Mechanics `codex-trust` keeps privately today move to `.githooks/harness_state.py`, including one host lock both tools take.

**Tech Stack:** Python 3 standard library (`json`, `tomllib`, `fcntl`, `runpy`), POSIX shell hooks, Git, pytest via `just test`.

**Spec:** `docs/specs/2026-10-10-live-model-preservation-design.md` (fallback approved 2026-10-10 after Task 1). Read it before any task.

## Global Constraints

- Owned files are exactly `claude/settings.json` and `codex/config.toml`; owned fields are the filter's: `model`, `modelSettings` (JSON) and top-level `model`, `model_reasoning_effort` (TOML). Read them from `harness-state-clean`, never restate them.
- The record is `local/live-picks.json`; the shared host lock is `local/harness-state.lock`.
- Restore writes only a file holding none of its owned fields, and only when the result parses to the live values plus the saved ones and has the same clean-filter output as the live file.
- Only `forget` may record `default`, for either file. Plain capture preserves a saved pick when all owned fields are absent; there is no explicit-capture CLI flag.
- Both harnesses capture at Stop. Claude picker Default may be restored: deliberate resets use `forget`. A pick made after the last Stop has a capture window until the next Stop.
- Linked worktrees: Git hooks skip silently; every other operation refuses.
- A Git hook reports failures on stderr and exits 0. `harness-state-refresh` exits non-zero on any step's failure, after finishing the steps it can.
- No step reads or writes a live harness home or the main checkout's configs, except Task 7 rollout, after the user approves its merge.
- Tests run only through `just test` (no `just test-fast`/`test-one` here; AGENTS.md names `just test`), and use temporary repositories.

## Review Focus

1. A Claude settings file holding non-ASCII text (a status line glyph): restore must keep it byte-identical in meaning and filter output. Test in Task 3.
2. A nested `modelSettings` object: capture and restore must round-trip it whole. Test in Task 3.
3. A Codex `model` line carrying a trailing comment: it is a one-line key and must round-trip as written. Test in Task 3.
4. A Codex config with no final newline and no table header: prepending must still parse and keep the filter output. Test in Task 3.
5. A live file reached through a home symlink: restore writes the target, keeps the link and the file mode. Test in Task 3.

---

## File Structure

| File | Responsibility |
|---|---|
| `.githooks/harness_state.py` (create) | Git helpers, linked-worktree and rebase checks, atomic mode-keeping write, restage, the shared host lock |
| `.githooks/codex-trust` (modify) | Uses `harness_state`; trust logic unchanged; lock moves to the shared one |
| `.githooks/live-picks` (create) | Record, capture, restore, sync, forget, hook |
| `.githooks/post-checkout`, `post-merge`, `post-rewrite` (modify) | Run `codex-trust hook`, then `live-picks hook` |
| `.githooks/harness-state-refresh` (modify) | Plain capture at Stop first, then the index-lock skip, trust sync, pick restore, staging |
| `.githooks/test_live_picks.py` (create) | All `live-picks` behaviour, direct and through Git and the refresh |
| `.githooks/test_codex_trust.py`, `test_harness_state_refresh.py` (modify) | Fixtures copy the new files; shared-lock test |
| `.gitignore` (modify) | `__pycache__/`: importing `harness_state` writes bytecode in `.githooks/` |
| `facts/capabilities.toml` (modify) | Two probed facts from Task 1 |
| `README.md`, `AGENTS.md`, `.githooks/harness-state-clean`, `docs/specs/2026-09-29-codex-trust-restore-design.md` (modify) | Docs |

---

### Task 1: Probe the pick lifecycle in scratch homes

**Complete — do not rerun.** Commit `7f53166`; task `hq-f51af7` is closed. Evidence:
`tasks/files/hq-f51af7/hq-probe-evidence-portable.txt`. No credentials are retained.

- [x] Claude Code 2.1.296: `model-pick-event=false`. Sonnet to Opus and Sonnet to
  Default hook snapshots contained the previous pick. Opus to Default resolved to
  the same model and fired no event.
- [x] Claude Code: `model-reset-clears-pick=true`. Default removed both owned fields.
- [x] Codex 0.162.1: `model-reset-clears-pick=false` for the tested other-model,
  other-effort and default-reasoning actions; the model menu offered no reset entry.
- [x] Record facts, validate with `tools/harness-facts check`, and run `just test`:
  228 agent tests and 565 hook/tool tests passed.
- [x] Fresh cleanup review accepted after the surviving Codex writer was stopped.
  The scratch tree, private tmux server and copied credentials are gone.

**Interfaces:** Produces `model-pick-event` and `model-reset-clears-pick` for Task 6,
read only through `tools/harness-facts get`. False Claude event ordering selected the
fallback approved in the spec; it no longer blocks this revised plan.

The old supervisor did not reap a surviving Codex descendant and checked only for a
serving tmux socket. Do not reuse it without fixing those limits; no further probe is
needed by this plan.

---

### Task 2: Shared hook module and one host lock

**Files:**
- Create: `.githooks/harness_state.py`
- Modify: `.githooks/codex-trust` (replace `git`, `git_path`, `linked_worktree`, `write`, `restage`, `rebasing`, `locked`, and the `REBASE_STATE`/`GIT_HOOKS`/`LOCK` constants)
- Modify: `.githooks/test_codex_trust.py` (fixture; new test)
- Modify: `.githooks/test_harness_state_refresh.py` (fixture: the refresh runs `codex-trust`, which now imports the module)
- Modify: `.gitignore`

**Interfaces:**
- Produces, in `harness_state`: `HERE`, `REPO`, `LOCAL`, `LOCK` (`Path`), `GIT_HOOKS` (tuple of str), `write(path: Path, text: str) -> None`, and `class Checkout(tool: str)` with `fail(message) -> NoReturn` (exits with `"<tool>: <message>"`), `git(*args) -> str`, `git_path(name) -> Path`, `linked_worktree() -> bool`, `rebasing() -> bool`, `restage(name: str) -> None`, `locked()` (context manager; fails naming `just setup` when `local/` is missing).

- [x] **Step 1: Write the failing test**

In `.githooks/test_codex_trust.py`, add `import fcntl` and `import time` to the imports, and add:

```python
def test_codex_trust_waits_for_the_host_lock_live_picks_shares(repo):
    with open(repo / "local" / "harness-state.lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        run = subprocess.Popen([str(repo / ".githooks" / "codex-trust"), "sync"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(0.5)
        assert run.poll() is None
    _, err = run.communicate(timeout=10)

    assert run.returncode == 0, err
```

- [x] **Step 2: Run it to verify it fails**

Run: `just test`
Expected: FAIL in `test_codex_trust_waits_for_the_host_lock_live_picks_shares` (`assert run.poll() is None`: the old lock is `local/codex/trust.toml.lock`, so sync finishes at once).

- [x] **Step 3: Create the module**

`.githooks/harness_state.py`:

```python
"""Mechanics shared by the tools that keep host state in this checkout's live harness configs.

codex-trust and live-picks both rewrite codex/config.toml, so they take one host lock,
local/harness-state.lock, around every read-modify-write of a live file or a saved copy.
Separate locks would let a trust restore and a pick restore read the same starting file
and each overwrite the other's insert. Each tool works on the checkout it lives in and
names itself in its failures. Design:
docs/specs/2026-10-10-live-model-preservation-design.md §3.3.
"""
import contextlib
import fcntl
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LOCAL = REPO / "local"
LOCK = LOCAL / "harness-state.lock"
GIT_HOOKS = ("post-checkout", "post-merge", "post-rewrite")
# A rebase runs post-checkout after checking out the new base, then replays commits
# from its in-memory index, which drops a restage made there; the file keeps its new
# size, and the replay of a commit that touches it stops with "local changes would be
# overwritten". post-rewrite restores when the rebase ends.
REBASE_STATE = ("rebase-merge", "rebase-apply")


def write(path, text):
    """Replace path by one rename, keeping its mode: the live configs are private (0600)."""
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


class Checkout:
    """This checkout's git state as one tool sees it: failures carry the tool's name."""

    def __init__(self, tool):
        self.tool = tool

    def fail(self, message):
        sys.exit(f"{self.tool}: {message}")

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(REPO), *args], text=True, capture_output=True)
        if result.returncode != 0:
            self.fail(f"git {' '.join(args)}: {result.stderr.strip()}")
        return result.stdout.strip()

    def git_path(self, name):
        return Path(self.git("rev-parse", "--path-format=absolute", "--git-path", name))

    def linked_worktree(self):
        return (self.git("rev-parse", "--path-format=absolute", "--git-dir")
                != self.git("rev-parse", "--path-format=absolute", "--git-common-dir"))

    def rebasing(self):
        return any(self.git_path(state).exists() for state in REBASE_STATE)

    def restage(self, name):
        """Stage a restored file when its filtered diff is empty, as harness-state-refresh does.

        The insert changes the file's size, and git calls a file of another size modified
        without running the filter; a rebase refuses to start on that mark. While another
        git process holds the index, the next turn end's refresh stages it instead.
        """
        if self.git_path("index.lock").exists():
            return
        diff = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "--", name],
                              text=True, capture_output=True)
        if diff.returncode not in (0, 1):
            self.fail(f"git diff {name}: {diff.stderr.strip()}")
        if diff.returncode == 0:
            self.git("add", "--", name)

    @contextlib.contextmanager
    def locked(self):
        """Hold the host lock every tool that rewrites a live harness config takes."""
        if not LOCAL.is_dir():
            self.fail("local/ is missing; run `just setup`")
        with open(LOCK, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
```

- [x] **Step 4: Point `codex-trust` at the module**

In `.githooks/codex-trust`:

1. Add `import harness_state`. Remove the imports `fcntl`, `subprocess`, `tempfile` and `from pathlib import Path`, which nothing uses after this step. Keep `contextlib` (`locked`), `os` (`keep_private` calls `os.chmod`), `runpy`, `sys` and `tomllib`. After the edit, `grep -nE '\b(fcntl|subprocess|tempfile|Path)\b' .githooks/codex-trust` prints nothing outside comments.
2. Replace `HERE = Path(__file__).resolve().parent` and `REPO = HERE.parent` with:
   ```python
   CHECKOUT = harness_state.Checkout("codex-trust")
   HERE = harness_state.HERE
   REPO = harness_state.REPO
   ```
3. Delete `LOCK = ...`, `GIT_HOOKS = ...`, and the `REBASE_STATE` comment and constant. Use `harness_state.GIT_HOOKS` in `main`.
4. Replace the bodies of `fail`, `git`, `git_path`, `linked_worktree`, `write`, `restage`, `rebasing` with delegation, keeping the names so the rest of the file is unchanged:
   ```python
   fail = CHECKOUT.fail
   git = CHECKOUT.git
   git_path = CHECKOUT.git_path
   linked_worktree = CHECKOUT.linked_worktree
   rebasing = CHECKOUT.rebasing
   write = harness_state.write


   def restage():
       CHECKOUT.restage(LIVE_NAME)
   ```
5. Replace `locked` with:
   ```python
   @contextlib.contextmanager
   def locked():
       """Hold the host lock live-picks shares: both rewrite codex/config.toml."""
       if not SAVED.parent.is_dir():
           fail("local/codex/ is missing; run `just setup`")
       if not LIVE.is_file():
           fail(f"{LIVE_NAME} is missing")
       with CHECKOUT.locked():
           yield
   ```
6. In the module docstring, after the sentence ending "and Codex's config is private.", add: `Every operation holds local/harness-state.lock, the host lock live-picks also takes.`

- [x] **Step 5: Ignore bytecode and update the refresh fixture**

Append `__pycache__/` to `.gitignore`. Add `"harness_state.py"` to `HOOK_FILES` in
`.githooks/test_codex_trust.py` after creating the module. In `.githooks/test_harness_state_refresh.py`, change the fixture's copy loop to:

```python
    for name in ("harness-state-clean", "harness-state-refresh", "codex-trust",
                 "harness_state.py"):
```

- [x] **Step 6: Run the tests**

Run: `just test`
Expected: PASS, including every existing `test_codex_trust.py` and `test_harness_state_refresh.py` test unchanged.

- [x] **Step 7: Commit**

```bash
git add .githooks/harness_state.py .githooks/codex-trust .githooks/test_codex_trust.py .githooks/test_harness_state_refresh.py .gitignore
git commit -m "refactor(hooks): share codex-trust's mechanics and take one host lock"
```

---

### Task 3: `live-picks` capture, restore, sync and forget

Implementation note: examples include the verified per-file failure isolation fix
from review round 1 and its regression cases.

**Files:**
- Create: `.githooks/live-picks` (mode 755)
- Create: `.githooks/test_live_picks.py`

**Interfaces:**
- Consumes: `harness_state` (Task 2).
- Produces: the CLI `live-picks capture | restore | sync | forget <file> | hook post-checkout|post-merge|post-rewrite` (`hook` is wired in Task 4 but implemented here), exiting 0 on success and non-zero with `live-picks: <message>` otherwise; the record format of spec §3.1.

- [x] **Step 1: Write the test file, fixture, and an empty CLI scaffold**

Create a temporary `.githooks/live-picks` scaffold containing only the following,
and `chmod 755 .githooks/live-picks`. This has no behavior and is replaced in Step 3;
it lets the fixture run so the tests fail on absent behavior rather than missing files.

```python
#!/usr/bin/env python3
raise SystemExit("live-picks: not implemented")
```

`.githooks/test_live_picks.py`:

```python
"""live-picks saves the model picks in local/ and puts back what a git command dropped."""
import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

HOOKS = Path(__file__).parent
HOOK_FILES = ("harness-state-clean", "harness_state.py", "codex-trust", "live-picks",
              "harness-state-refresh", "post-checkout", "post-merge", "post-rewrite")
CLAUDE = "claude/settings.json"
CODEX = "codex/config.toml"
BASE = "[features]\nhooks = true\n"
TUI = "[tui]\nx = 1\n"
PICK = 'model = "gpt-6.1-sol"\nmodel_reasoning_effort = "high"\n'
PICK_LINES = ['model = "gpt-6.1-sol"\n', 'model_reasoning_effort = "high"\n']
A = '[projects."/work/a"]\ntrust_level = "trusted"\n'


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], check=check, text=True,
                          capture_output=True)


def write_claude(repo, **settings):
    data = {"theme": "dark-ansi", **settings}
    (repo / CLAUDE).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


@pytest.fixture
def repo(tmp_path):
    """A main checkout shaped like this one: the filter, the hooks, both configs, local/."""
    repo = tmp_path / "hq"
    (repo / ".githooks").mkdir(parents=True)
    for name in HOOK_FILES:
        shutil.copy2(HOOKS / name, repo / ".githooks" / name)
    (repo / "claude").mkdir()
    (repo / "codex").mkdir()
    (repo / "local" / "codex").mkdir(parents=True)
    (repo / ".gitattributes").write_text("claude/settings*.json filter=harness-state\n"
                                         "codex/config*.toml filter=harness-state\n")
    (repo / ".gitignore").write_text("local/\n__pycache__/\n")
    write_claude(repo)
    (repo / CODEX).write_text(BASE)
    git(tmp_path, "init", "-q", "-b", "main", str(repo))
    git(repo, "config", "filter.harness-state.clean", ".githooks/harness-state-clean %f")
    git(repo, "config", "core.hooksPath", ".githooks")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def picks(repo, *args):
    """Run live-picks as the hooks do: by path, from another directory."""
    return subprocess.run([str(repo / ".githooks" / "live-picks"), *args], cwd=repo.parent,
                          text=True, capture_output=True)


def record_path(repo):
    return repo / "local" / "live-picks.json"


def record(repo):
    path = record_path(repo)
    return json.loads(path.read_text()) if path.exists() else None


def claude(repo):
    return json.loads((repo / CLAUDE).read_text())


def codex(repo):
    return tomllib.loads((repo / CODEX).read_text())


def clean(repo, name, text):
    return subprocess.run([str(repo / ".githooks" / "harness-state-clean"), name],
                          input=text, check=True, text=True, capture_output=True).stdout


def status(repo):
    return git(repo, "status", "--porcelain").stdout


def save(repo, **entries):
    record_path(repo).write_text(json.dumps(entries) + "\n")


CLAUDE_SET = {"state": "set", "values": {"model": "opus"}}
CODEX_SET = {"state": "set", "lines": PICK_LINES}


def saved_both(repo):
    save(repo, **{CLAUDE: CLAUDE_SET, CODEX: CODEX_SET})


def test_capture_saves_the_pick_each_file_holds(repo):
    write_claude(repo, model="opus")
    (repo / CODEX).write_text(PICK + BASE)

    result = picks(repo, "capture")

    assert result.returncode == 0, result.stderr
    assert record(repo) == {CLAUDE: CLAUDE_SET, CODEX: CODEX_SET}


def test_capture_with_no_pick_anywhere_creates_no_record(repo):
    assert picks(repo, "capture").returncode == 0

    assert record(repo) is None


def test_capture_of_a_file_holding_no_pick_keeps_the_saved_one(repo):
    saved_both(repo)

    assert picks(repo, "capture").returncode == 0

    assert record(repo) == {CLAUDE: CLAUDE_SET, CODEX: CODEX_SET}


def test_a_later_pick_replaces_the_saved_one(repo):
    saved_both(repo)
    write_claude(repo, model="sonnet")

    assert picks(repo, "capture").returncode == 0
    write_claude(repo)
    assert picks(repo, "restore").returncode == 0

    assert claude(repo)["model"] == "sonnet"


def test_a_partial_pick_is_saved_as_is_and_never_completed(repo):
    write_claude(repo, model="opus", modelSettings={"opus": {"context": "1m"}})
    assert picks(repo, "capture").returncode == 0
    write_claude(repo, model="haiku")

    assert picks(repo, "sync").returncode == 0

    assert record(repo)[CLAUDE] == {"state": "set", "values": {"model": "haiku"}}
    assert "modelSettings" not in claude(repo)


def test_restore_puts_back_both_picks_and_keeps_what_git_stages(repo):
    saved_both(repo)
    write_claude(repo, theme="light")
    (repo / CODEX).write_text(TUI + BASE)
    before = {name: (repo / name).read_text() for name in (CLAUDE, CODEX)}

    result = picks(repo, "restore")

    assert result.returncode == 0, result.stderr
    assert claude(repo) == {"theme": "light", "model": "opus"}
    assert (repo / CODEX).read_text() == PICK + TUI + BASE
    for name in (CLAUDE, CODEX):
        assert clean(repo, name, (repo / name).read_text()) == clean(repo, name, before[name])


def test_restore_never_overwrites_a_pick(repo):
    saved_both(repo)
    write_claude(repo, model="sonnet")
    inode = (repo / CLAUDE).stat().st_ino

    assert picks(repo, "restore").returncode == 0

    assert claude(repo)["model"] == "sonnet"
    assert (repo / CLAUDE).stat().st_ino == inode


def test_restore_prepends_codex_lines_before_a_header_like_string_line(repo):
    save(repo, **{CODEX: CODEX_SET})
    notice = 'notice = """\n[example]\n"""\n'
    (repo / CODEX).write_text(notice + BASE)

    result = picks(repo, "restore")

    assert result.returncode == 0, result.stderr
    assert codex(repo)["notice"] == "[example]\n"
    assert codex(repo)["model"] == "gpt-6.1-sol"


def test_restore_with_no_record_or_a_default_one_writes_nothing(repo):
    assert picks(repo, "restore").returncode == 0
    save(repo, **{CLAUDE: {"state": "default"}})

    assert picks(repo, "restore").returncode == 0

    assert "model" not in claude(repo)


def test_a_sync_that_changes_nothing_writes_nothing(repo):
    write_claude(repo, model="opus")
    (repo / CODEX).write_text(PICK + BASE)
    assert picks(repo, "sync").returncode == 0
    paths = [repo / CLAUDE, repo / CODEX, record_path(repo)]
    before = [(p.stat().st_ino, p.stat().st_mtime_ns) for p in paths]

    assert picks(repo, "sync").returncode == 0

    assert [(p.stat().st_ino, p.stat().st_mtime_ns) for p in paths] == before


@pytest.mark.parametrize("text", [
    "{", "[]", '{"other.json": {"state": "default"}}',
    '{"claude/settings.json": {"state": "maybe"}}',
    '{"claude/settings.json": {"state": "set", "values": {"theme": "x"}}}',
    '{"claude/settings.json": {"state": "default", "values": {}}}',
    '{"codex/config.toml": {"state": "set", "lines": ["theme = 1\\n"]}}',
    '{"codex/config.toml": {"state": "set", "lines": ["model = \\"x\\""]}}',
])
def test_an_invalid_record_is_refused_and_left_alone(repo, text):
    record_path(repo).write_text(text)
    write_claude(repo, model="opus")
    before = (repo / CLAUDE).read_text()

    result = picks(repo, "sync")

    assert result.returncode != 0
    assert "live-picks: local/live-picks.json" in result.stderr
    assert record_path(repo).read_text() == text
    assert (repo / CLAUDE).read_text() == before


def test_an_unparsable_file_is_refused_and_the_other_still_restored(repo):
    saved_both(repo)
    (repo / CLAUDE).write_text("{\n")

    result = picks(repo, "restore")

    assert result.returncode != 0
    assert "claude/settings.json does not parse" in result.stderr
    assert (repo / CLAUDE).read_text() == "{\n"
    assert codex(repo)["model"] == "gpt-6.1-sol"


def test_a_codex_pick_spanning_lines_is_refused(repo):
    (repo / CODEX).write_text('model = """\ngpt\n"""\n' + BASE)

    result = picks(repo, "capture")

    assert result.returncode != 0
    assert "one-line keys" in result.stderr
    assert record(repo) is None


def test_forget_records_the_default_and_removes_the_pick(repo):
    write_claude(repo, model="opus", modelSettings={"x": 1})
    (repo / CODEX).write_text(PICK + BASE)
    assert picks(repo, "capture").returncode == 0
    before = {name: clean(repo, name, (repo / name).read_text()) for name in (CLAUDE, CODEX)}

    for name in (CLAUDE, CODEX):
        result = picks(repo, "forget", name)
        assert result.returncode == 0, result.stderr

    assert record(repo) == {CLAUDE: {"state": "default"}, CODEX: {"state": "default"}}
    assert claude(repo) == {"theme": "dark-ansi"}
    assert (repo / CODEX).read_text() == BASE
    for name in (CLAUDE, CODEX):
        assert clean(repo, name, (repo / name).read_text()) == before[name]
    assert status(repo) == ""


@pytest.mark.parametrize("name", [CLAUDE, CODEX])
def test_forget_survives_a_later_git_rewrite(repo, name):
    write_claude(repo, model="opus")
    (repo / CODEX).write_text(PICK + BASE)
    assert picks(repo, "capture").returncode == 0
    assert picks(repo, "forget", name).returncode == 0
    if name == CLAUDE:
        write_claude(repo, theme="light")
    else:
        (repo / CODEX).write_text(TUI + BASE)

    git(repo, "checkout", "--", name)
    assert picks(repo, "restore").returncode == 0

    assert record(repo)[name] == {"state": "default"}
    live = claude(repo) if name == CLAUDE else codex(repo)
    assert "model" not in live
    assert "modelSettings" not in live
    assert "model_reasoning_effort" not in live


def test_a_filesystem_error_fails_cleanly(repo):
    record_path(repo).mkdir()

    result = picks(repo, "sync")

    assert result.returncode != 0
    assert "live-picks: " in result.stderr
    assert "Traceback" not in result.stderr


def test_forget_of_a_file_it_does_not_own_is_refused(repo):
    result = picks(repo, "forget", "claude/settings.work.json")

    assert result.returncode != 0
    assert "forget takes" in result.stderr


def test_concurrent_syncs_of_both_tools_keep_trust_and_the_pick(repo):
    (repo / "local" / "codex" / "trust.toml").write_text(A)
    save(repo, **{CODEX: CODEX_SET})
    tools = ("codex-trust", "live-picks") * 6
    runs = [subprocess.Popen([str(repo / ".githooks" / tool), "sync"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for tool in tools]

    for run in runs:
        _, err = run.communicate()
        assert run.returncode == 0, err

    text = (repo / CODEX).read_text()
    assert text.count("model = ") == 1
    assert text.count('[projects."/work/a"]') == 1
    assert codex(repo)["model"] == "gpt-6.1-sol"


def test_a_linked_worktree_is_refused(repo, tmp_path):
    other = tmp_path / "other"
    git(repo, "worktree", "add", "-q", "-b", "other", str(other))
    (other / "local").mkdir()

    result = picks(other, "capture")

    assert result.returncode != 0
    assert "linked worktree" in result.stderr


def test_a_missing_local_directory_names_just_setup(repo):
    shutil.rmtree(repo / "local")

    result = picks(repo, "capture")

    assert result.returncode != 0
    assert "just setup" in result.stderr


def test_a_missing_owned_file_is_named(repo):
    (repo / CODEX).unlink()

    result = picks(repo, "capture")

    assert result.returncode != 0
    assert "codex/config.toml is missing" in result.stderr


@pytest.mark.parametrize("args", [(), ("prune",), ("capture", "--all"), ("capture", "--explicit"), ("hook", "pre-push"),
                                  ("forget",)])
def test_bad_usage_prints_the_usage(repo, args):
    result = picks(repo, *args)

    assert result.returncode != 0
    assert "usage: live-picks" in result.stderr


# Review Focus 1-5


def test_restore_keeps_non_ascii_settings(repo):
    save(repo, **{CLAUDE: CLAUDE_SET})
    write_claude(repo, statusLine={"glyph": "café ▸"})
    before = clean(repo, CLAUDE, (repo / CLAUDE).read_text())

    assert picks(repo, "restore").returncode == 0

    assert claude(repo)["statusLine"] == {"glyph": "café ▸"}
    assert clean(repo, CLAUDE, (repo / CLAUDE).read_text()) == before


def test_a_nested_model_settings_round_trips(repo):
    settings = {"opus": {"context": "1m", "betas": ["a", "b"]}}
    write_claude(repo, model="opus", modelSettings=settings)
    assert picks(repo, "capture").returncode == 0
    write_claude(repo)

    assert picks(repo, "restore").returncode == 0

    assert claude(repo)["modelSettings"] == settings


def test_a_codex_pick_with_a_trailing_comment_round_trips(repo):
    line = 'model = "gpt-6.1-sol"  # picked\n'
    (repo / CODEX).write_text(line + BASE)
    assert picks(repo, "capture").returncode == 0
    (repo / CODEX).write_text(BASE)

    assert picks(repo, "restore").returncode == 0

    assert (repo / CODEX).read_text() == line + BASE


def test_restore_into_a_codex_file_with_no_header_or_final_newline(repo):
    save(repo, **{CODEX: CODEX_SET})
    (repo / CODEX).write_text('personality = "p"')
    before = clean(repo, CODEX, 'personality = "p"')

    assert picks(repo, "restore").returncode == 0

    assert codex(repo) == {"model": "gpt-6.1-sol", "model_reasoning_effort": "high",
                           "personality": "p"}
    assert clean(repo, CODEX, (repo / CODEX).read_text()) == before


def test_restore_keeps_a_home_link_and_the_file_mode(repo, tmp_path):
    save(repo, **{CLAUDE: CLAUDE_SET})
    os.chmod(repo / CLAUDE, 0o600)
    home = tmp_path / "home-settings.json"
    home.symlink_to(repo / CLAUDE)

    assert picks(repo, "restore").returncode == 0

    assert home.is_symlink()
    assert json.loads(home.read_text())["model"] == "opus"
    assert (repo / CLAUDE).stat().st_mode & 0o777 == 0o600


def test_capture_keeps_a_new_pick_when_the_other_file_is_missing(repo):
    saved_both(repo)
    write_claude(repo, model="sonnet")
    (repo / CODEX).unlink()

    result = picks(repo, "capture")

    assert result.returncode != 0
    assert CODEX in result.stderr
    assert record(repo)[CLAUDE] == {"state": "set", "values": {"model": "sonnet"}}
    assert record(repo)[CODEX] == CODEX_SET


@pytest.mark.parametrize("damage", ["missing", "bad_utf8"])
def test_restore_handles_the_healthy_file_after_a_live_read_failure(repo, damage):
    saved_both(repo)
    if damage == "missing":
        (repo / CLAUDE).unlink()
    else:
        (repo / CLAUDE).write_bytes(b"\xff")

    result = picks(repo, "restore")

    assert result.returncode != 0
    assert CLAUDE in result.stderr
    assert "Traceback" not in result.stderr
    assert codex(repo)["model"] == "gpt-6.1-sol"
    assert record(repo)[CLAUDE] == CLAUDE_SET


def fail_live_tempfile(repo, name):
    """Inject failure at tempfile creation; every other CLI operation stays real."""
    tool = repo / ".githooks" / "live-picks"
    source = tool.with_name("live-picks-source")
    shutil.copy2(tool, source)
    tool.write_text(f"""#!/usr/bin/env python3
import runpy
from pathlib import Path
import harness_state

here = Path(__file__).resolve().parent
create = harness_state.tempfile.mkstemp

def fail_target(*args, **kwargs):
    if Path(kwargs["dir"]) == (here.parent / {name!r}).parent:
        raise PermissionError("simulated live-file write failure")
    return create(*args, **kwargs)

harness_state.tempfile.mkstemp = fail_target
runpy.run_path(str(here / "live-picks-source"), run_name="__main__")
""")


def test_restore_handles_the_healthy_file_after_a_live_write_failure(repo):
    saved_both(repo)
    fail_live_tempfile(repo, CLAUDE)

    result = picks(repo, "restore")

    assert result.returncode != 0
    assert CLAUDE in result.stderr
    assert claude(repo) == {"theme": "dark-ansi"}
    assert codex(repo)["model"] == "gpt-6.1-sol"


def test_hook_restages_a_restored_file_when_the_other_write_fails(repo):
    saved_both(repo)
    fail_live_tempfile(repo, CODEX)

    result = picks(repo, "hook", "post-merge")

    assert result.returncode == 0
    assert CODEX in result.stderr
    assert "Traceback" not in result.stderr
    assert claude(repo)["model"] == "opus"
    assert "model" not in codex(repo)
    assert git(repo, "diff-files", "--name-only", "--", CLAUDE).stdout == ""
```

- [x] **Step 2: Run them to verify they fail**

Run: `just test`
Expected: FAIL in the direct-operation tests with `live-picks: not implemented`;
the fixtures complete. Usage-error tests may also fail until the CLI is implemented.

- [x] **Step 3: Write the tool**

`.githooks/live-picks` (then `chmod 755`):

```python
#!/usr/bin/env python3
"""Keep the model picks in the live harness configs across git commands that drop them.

The harness-state clean filter keeps the picks out of the index: `model` and
`modelSettings` in claude/settings.json, the top-level `model` and
`model_reasoning_effort` in codex/config.toml. A git command that writes a new blob of
either file over the live one drops the pick, and the harness runs on its default. This
tool saves each file's pick in local/live-picks.json, untracked and carried between
hosts by Dropbox, and puts it back:

    capture               save the pick each file holds; absence never records a reset
    restore               put a saved pick into a file holding none of its fields
    sync                  capture, then restore
    forget <file>         record the file's default and remove its pick from the file
    hook <name>           restore from a git hook, then restage what it wrote

A file's owned fields are one unit. Git drops all of them together, so a file holding
none is the only state a git rewrite leaves; any other state was written by a harness or
a person, and the live file wins. Absence alone cannot tell a rewrite from a return to
the default, so only forget records `default`, for either file. Both harnesses capture
at Stop; picker events are not reliable post-write events. restore never writes a file
that holds any owned field, so a newer pick is never overwritten. It prepends Codex's lines, which are top-level keys
whatever follows, and writes only when the result parses to the live values plus the
saved ones and the filter's output, what git stages, is unchanged.

The record is machine-owned and written whole; an invalid one is refused, never
overwritten. A file that cannot be read is refused alone: the other is still handled.
Every operation holds local/harness-state.lock, the host lock codex-trust also takes. A
hook reports a failure on stderr and exits 0, and skips a linked worktree silently and,
from post-checkout, a rebase in progress; the next turn end retries. Every other
operation refuses a linked worktree, whose configs are not live. Design:
docs/specs/2026-10-10-live-model-preservation-design.md.
"""
import json
import runpy
import sys
import tomllib

import harness_state

CHECKOUT = harness_state.Checkout("live-picks")
fail = CHECKOUT.fail
REPO = harness_state.REPO
RECORD_NAME = "local/live-picks.json"
RECORD = REPO / RECORD_NAME
CLAUDE = "claude/settings.json"
CODEX = "codex/config.toml"
OWNED = (CLAUDE, CODEX)
USAGE = ("usage: live-picks capture | restore | sync | forget <file> | "
         "hook post-checkout|post-merge|post-rewrite")
# The filter decides what a checkout drops; reading its names keeps the owned fields
# exactly the dropped ones.
FILTER = runpy.run_path(str(harness_state.HERE / "harness-state-clean"))
JSON_KEYS = FILTER["JSON_KEYS"]
TOML_KEYS = tuple(name for table, name in FILTER["TOML_KEYS"] if table.fullmatch(""))
TOML_HEADER = FILTER["TOML_HEADER"]
TOML_KEY = FILTER["TOML_KEY"]
CLEAN = {CLAUDE: FILTER["clean_json"], CODEX: FILTER["clean_toml"]}
FIELD = {CLAUDE: "values", CODEX: "lines"}


class Refused(Exception):
    """One file cannot be read or written; the other is still handled."""


def parse(name, text):
    try:
        data = json.loads(text) if name == CLAUDE else tomllib.loads(text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        raise Refused(f"{name} does not parse: {error}")
    if not isinstance(data, dict):
        raise Refused(f"{name} is not an object")
    return data


def codex_lines(text):
    """The owned key lines before the first table header, in file order."""
    lines = []
    for line in text.splitlines(keepends=True):
        if TOML_HEADER.match(line):
            break
        key = TOML_KEY.match(line)
        if key and key.group(1) in TOML_KEYS:
            lines.append(line if line.endswith("\n") else line + "\n")
    return lines


def toml_or_none(text):
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None


def pick(name, text):
    """The owned fields text holds: Claude's values or Codex's lines; empty when none.

    A Codex pick the filter could not drop line by line (a multi-line value, a key after
    a header-like line) is refused.
    """
    data = parse(name, text)
    if name == CLAUDE:
        return {key: data[key] for key in JSON_KEYS if key in data}
    lines = codex_lines(text)
    if toml_or_none("".join(lines)) != {key: data[key] for key in TOML_KEYS if key in data}:
        raise Refused(f"{name}: write {' and '.join(TOML_KEYS)} as one-line keys "
                      "before the first table")
    return lines


def invalid(name, saved):
    """Why a record entry is malformed, or None."""
    if name not in OWNED:
        return "not a file live-picks owns"
    if not isinstance(saved, dict) or saved.get("state") not in ("set", "default"):
        return 'state must be "set" or "default"'
    if saved["state"] == "default":
        return None if set(saved) == {"state"} else "a default entry holds only its state"
    if set(saved) != {"state", FIELD[name]}:
        return f'a set entry holds its state and "{FIELD[name]}"'
    held = saved[FIELD[name]]
    if name == CLAUDE:
        if isinstance(held, dict) and held and set(held) <= set(JSON_KEYS):
            return None
        return f"values must name some of {', '.join(JSON_KEYS)}"
    if isinstance(held, list) and held and all(isinstance(line, str) for line in held):
        text = "".join(held)
        parsed = toml_or_none(text)
        if parsed is not None and set(parsed) <= set(TOML_KEYS) and codex_lines(text) == held:
            return None
    return f"lines must be one-line {' or '.join(TOML_KEYS)} keys"


def read_record():
    if not RECORD.exists():
        return {}
    try:
        record = json.loads(RECORD.read_text())
    except json.JSONDecodeError as error:
        fail(f"{RECORD_NAME} is not valid JSON: {error}; fix or delete it")
    if not isinstance(record, dict):
        fail(f"{RECORD_NAME} is not an object; fix or delete it")
    for name, saved in record.items():
        problem = invalid(name, saved)
        if problem:
            fail(f"{RECORD_NAME}: {name}: {problem}; fix or delete it")
    return record


def write_record(record):
    harness_state.write(RECORD, json.dumps(record, indent=2, ensure_ascii=False) + "\n")


def live(name):
    path = REPO / name
    try:
        if not path.is_file():
            raise Refused(f"{name} is missing")
        return path.read_text()
    except (OSError, UnicodeError) as error:
        raise Refused(f"{name} cannot be read: {error}") from None


def capture():
    """Save the pick each file holds; returns the refusals."""
    record = read_record()
    updated, refusals = dict(record), []
    for name in OWNED:
        try:
            held = pick(name, live(name))
        except Refused as error:
            refusals.append(str(error))
            continue
        if held:
            updated[name] = {"state": "set", FIELD[name]: held}
    if updated != record:
        write_record(updated)
    return refusals


def checked(name, text, result, want):
    """result, when it parses to want and the filter's output is text's; else refused."""
    try:
        got = parse(name, result)
    except Refused:
        got = None
    if got != want or CLEAN[name](result) != CLEAN[name](text):
        raise Refused(f"found no way to change {name} that keeps its other values and what "
                      "git stages; nothing written")
    return result


def with_pick(name, text, saved):
    data = parse(name, text)
    if name == CLAUDE:
        want = {**data, **saved["values"]}
        result = json.dumps(want, indent=2, ensure_ascii=False) + "\n"
    else:
        want = {**data, **tomllib.loads("".join(saved["lines"]))}
        result = "".join(saved["lines"]) + text
    return checked(name, text, result, want)


def without_pick(name, text):
    data = parse(name, text)
    if name == CLAUDE:
        want = {key: value for key, value in data.items() if key not in JSON_KEYS}
        result = json.dumps(want, indent=2, ensure_ascii=False) + "\n"
    else:
        want = {key: value for key, value in data.items() if key not in TOML_KEYS}
        kept, top = [], True
        for line in text.splitlines(keepends=True):
            top = top and not TOML_HEADER.match(line)
            key = top and TOML_KEY.match(line)
            if not (key and key.group(1) in TOML_KEYS):
                kept.append(line)
        result = "".join(kept)
    return checked(name, text, result, want)


def restore():
    """Put each saved pick into a file holding none of its fields.

    Returns the files written and the refusals.
    """
    record = read_record()
    written, refusals = [], []
    for name in OWNED:
        saved = record.get(name)
        if saved is None or saved["state"] != "set":
            continue
        try:
            text = live(name)
            if pick(name, text):
                continue
            result = with_pick(name, text, saved)
            harness_state.write((REPO / name).resolve(), result)
        except Refused as error:
            refusals.append(str(error))
            continue
        except (OSError, UnicodeError) as error:
            refusals.append(f"{name}: {error}")
            continue
        written.append(name)
    return written, refusals


def forget(name):
    record = read_record()
    try:
        text = live(name)
        if pick(name, text):
            harness_state.write((REPO / name).resolve(), without_pick(name, text))
    except Refused as error:
        fail(str(error))
    record[name] = {"state": "default"}
    write_record(record)
    CHECKOUT.restage(name)


def refuse(refusals):
    if refusals:
        fail("; ".join(refusals))


def operate(args):
    """Run the operation args name under the host lock.

    A filesystem or decoding failure (an unreadable record, a directory where a file
    belongs) fails like any refusal, with the tool's name and no traceback.
    """
    try:
        with CHECKOUT.locked():
            if args[0] == "hook":
                written, refusals = restore()
                for name in written:
                    CHECKOUT.restage(name)
            elif args[0] == "forget":
                forget(args[1])
                return
            else:
                refusals = []
                if args[0] in ("capture", "sync"):
                    refusals += capture()
                if args[0] in ("restore", "sync"):
                    refusals += restore()[1]
            refuse(refusals)
    except (OSError, UnicodeError) as error:
        fail(str(error))


def main(argv):
    args = argv[1:]
    if not (args in (["capture"], ["restore"], ["sync"])
            or len(args) == 2 and (args[0] == "forget" or args[0] == "hook"
                                   and args[1] in harness_state.GIT_HOOKS)):
        fail(USAGE)
    if args[0] == "forget" and args[1] not in OWNED:
        fail(f"forget takes {' or '.join(OWNED)}, not {args[1]!r}")
    if CHECKOUT.linked_worktree():
        if args[0] == "hook":
            return
        fail(f"{REPO} is a linked worktree; its harness configs are not live")
    if args[0] != "hook":
        operate(args)
        return
    if args[1] == "post-checkout" and CHECKOUT.rebasing():
        return
    try:
        operate(args)
    except SystemExit as error:
        print(f"{error}\nlive-picks: a pick was not restored; the next turn end retries",
              file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv)
```

- [x] **Step 4: Run the tests**

Run: `just test`
Expected: PASS. A failing case names the behaviour; fix the tool, not the test, unless the test contradicts spec §3.2.

- [x] **Step 5: Commit**

```bash
git add .githooks/live-picks .githooks/test_live_picks.py
git commit -m "feat(hooks): live-picks saves and restores model picks"
```

---

### Task 4: Restore picks from the Git hooks

**Files:**
- Modify: `.githooks/post-checkout`, `.githooks/post-merge`, `.githooks/post-rewrite`
- Modify: `.githooks/test_codex_trust.py` (fixture: copy `live-picks`, add a Claude settings file)
- Test: `.githooks/test_live_picks.py`

**Interfaces:**
- Consumes: `live-picks hook <name>` (Task 3).

- [x] **Step 1: Write the failing tests**

Append to `.githooks/test_live_picks.py`:

```python
def picked(repo):
    """Both harnesses picked and a turn ended: picks live, saved, git's mark clear."""
    write_claude(repo, **{**claude(repo), "model": "opus"})
    (repo / CODEX).write_text(PICK + (repo / CODEX).read_text())
    assert picks(repo, "capture").returncode == 0
    git(repo, "add", "--", CLAUDE, CODEX)


def commit_settings(repo, message, theme="light", codex_text=TUI + BASE):
    write_claude(repo, theme=theme)
    (repo / CODEX).write_text(codex_text)
    git(repo, "add", "--", CLAUDE, CODEX)
    git(repo, "commit", "-q", "-m", message)


def side_with_settings(repo):
    git(repo, "switch", "-q", "-c", "side")
    commit_settings(repo, "side")
    git(repo, "switch", "-q", "main")


def assert_picked(repo, theme="light", codex_text=TUI + BASE):
    assert claude(repo) == {"theme": theme, "model": "opus"}
    assert (repo / CODEX).read_text() == PICK + codex_text


def test_a_merge_that_rewrites_both_configs_keeps_both_picks(repo):
    side_with_settings(repo)
    picked(repo)

    result = git(repo, "merge", "-q", "side")

    assert result.stderr == ""
    assert_picked(repo)
    assert status(repo) == ""


def test_one_merge_restores_trust_and_picks_together(repo):
    side_with_settings(repo)
    picked(repo)
    (repo / "local" / "codex" / "trust.toml").write_text(A)

    git(repo, "merge", "-q", "side")

    assert codex(repo)["projects"] == {"/work/a": {"trust_level": "trusted"}}
    assert codex(repo)["model"] == "gpt-6.1-sol"
    assert status(repo) == ""


def test_a_branch_switch_keeps_the_picks_both_ways(repo):
    side_with_settings(repo)
    picked(repo)

    git(repo, "switch", "-q", "side")
    assert_picked(repo)
    git(repo, "switch", "-q", "main")

    assert_picked(repo, theme="dark-ansi", codex_text=BASE)
    assert status(repo) == ""


@pytest.mark.parametrize("command", [("checkout", "--"), ("restore",)])
def test_a_checkout_of_a_file_keeps_its_pick(repo, command):
    picked(repo)
    write_claude(repo, theme="light", model="opus")

    git(repo, *command, CLAUDE)

    assert claude(repo) == {"theme": "dark-ansi", "model": "opus"}
    assert status(repo) == ""


def test_a_rebase_that_replays_a_settings_commit_keeps_the_picks(repo):
    git(repo, "switch", "-q", "-c", "side")
    (repo / "u").write_text("side\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "side")
    git(repo, "switch", "-q", "main")
    commit_settings(repo, "main settings")
    picked(repo)

    result = git(repo, "rebase", "side", check=False)

    assert result.returncode == 0, result.stderr
    assert_picked(repo)
    assert "model" not in git(repo, "show", "HEAD:" + CLAUDE).stdout
    assert status(repo) == ""


@pytest.mark.parametrize("command", ["checkout --", "switch", "merge"])
def test_hooks_leave_a_linked_worktree_alone(repo, tmp_path, command):
    side_with_settings(repo)
    picked(repo)
    other = tmp_path / "other"
    git(repo, "worktree", "add", "-q", "-b", "mine", str(other), "main")
    if command == "checkout --":
        (other / CLAUDE).write_text('{"theme": "x"}\n')
        result = git(other, "checkout", "-q", "--", CLAUDE)
    elif command == "switch":
        result = git(other, "switch", "-q", "--detach", "side")
    else:
        result = git(other, "merge", "-q", "side")

    assert result.stderr == ""
    assert "model" not in (other / CLAUDE).read_text()
    assert "model" not in (other / CODEX).read_text()
    assert git(other, "status", "--porcelain").stdout == ""


def test_a_filesystem_error_in_a_hook_reports_and_lets_the_git_command_succeed(repo):
    side_with_settings(repo)
    picked(repo)
    record_path(repo).unlink()
    record_path(repo).mkdir()

    result = git(repo, "switch", "-q", "side", check=False)

    assert result.returncode == 0
    assert "live-picks: " in result.stderr
    assert "Traceback" not in result.stderr
    assert git(repo, "branch", "--show-current").stdout.strip() == "side"


def test_a_failing_pick_restore_reports_and_trust_still_returns(repo):
    side_with_settings(repo)
    picked(repo)
    (repo / "local" / "codex" / "trust.toml").write_text(A)
    record_path(repo).write_text("{")

    result = git(repo, "switch", "-q", "side", check=False)

    assert result.returncode == 0
    assert "live-picks: local/live-picks.json" in result.stderr
    assert "the next turn end retries" in result.stderr
    assert "/work/a" in codex(repo)["projects"]
    assert git(repo, "branch", "--show-current").stdout.strip() == "side"
```

- [x] **Step 2: Run them to verify they fail**

Run: `just test`
Expected: FAIL in the new tests: after the Git command, `model` is missing (`assert_picked` / `KeyError: 'model'`).

- [x] **Step 3: Wire the hooks**

`.githooks/post-checkout`:

```sh
#!/bin/sh
# Put back the Codex project trust and the model picks this checkout dropped
# (.githooks/codex-trust, .githooks/live-picks). Each reports its own failure and exits 0.
"$(dirname "$0")/codex-trust" hook post-checkout
exec "$(dirname "$0")/live-picks" hook post-checkout
```

`.githooks/post-merge`:

```sh
#!/bin/sh
# Put back the Codex project trust and the model picks this merge dropped
# (.githooks/codex-trust, .githooks/live-picks). Each reports its own failure and exits 0.
"$(dirname "$0")/codex-trust" hook post-merge
exec "$(dirname "$0")/live-picks" hook post-merge
```

`.githooks/post-rewrite`:

```sh
#!/bin/sh
# Put back the Codex project trust and the model picks this rebase dropped
# (.githooks/codex-trust, .githooks/live-picks). Git feeds the rewritten commits on
# stdin; drain them so it never writes to a closed pipe. Each tool reports its own
# failure and exits 0.
cat >/dev/null
"$(dirname "$0")/codex-trust" hook post-rewrite
exec "$(dirname "$0")/live-picks" hook post-rewrite
```

- [x] **Step 4: Update the trust fixture**

In `.githooks/test_codex_trust.py`, the hooks now run `live-picks`, which needs both owned files. Add `"live-picks"` to `HOOK_FILES`, and in the `repo` fixture, before `git init`:

```python
    (repo / "claude").mkdir()
    (repo / "claude" / "settings.json").write_text('{\n  "theme": "dark-ansi"\n}\n')
```

and change the `.gitattributes` line to:

```python
    (repo / ".gitattributes").write_text("claude/settings*.json filter=harness-state\n"
                                         "codex/config*.toml filter=harness-state\n")
```

No trust assertion changes.

- [x] **Step 5: Run the tests**

Run: `just test`
Expected: PASS, the trust suite included.

- [x] **Step 6: Commit**

```bash
git add .githooks/post-checkout .githooks/post-merge .githooks/post-rewrite .githooks/test_live_picks.py .githooks/test_codex_trust.py
git commit -m "feat(hooks): restore model picks after checkouts, merges and rebases"
```

---

### Task 5: Capture and restore from the refresh hook

Implementation note: examples include the verified launch-failure continuation and
Git/tool diagnostic aggregation fixes and their regression cases.

**Files:**
- Modify: `.githooks/harness-state-refresh`
- Modify: `.githooks/test_harness_state_refresh.py` (fixture)
- Test: `.githooks/test_live_picks.py`

**Interfaces:**
- Consumes: `live-picks capture`, `live-picks restore` (Task 3).
- Produces: `harness-state-refresh` drains stdin without interpreting picker events, runs plain capture before checking `index.lock`, then trust sync, pick restore and staging. It reports all failed tool steps after finishing the other steps.

- [x] **Step 1: Write the failing tests**

Append to `.githooks/test_live_picks.py`:

```python
def refresh(repo):
    """Run the refresh as a harness hook does: from another directory, payload on stdin."""
    return subprocess.run([str(repo / ".githooks" / "harness-state-refresh")],
                          cwd=repo.parent, input=json.dumps({"hook_event_name": "Stop"}),
                          text=True, capture_output=True)


def index_lock(repo):
    return Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path",
                    "index.lock").stdout.strip())


def test_the_stop_hook_saves_a_new_pick(repo):
    write_claude(repo, model="opus")

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert record(repo)[CLAUDE] == CLAUDE_SET
    assert status(repo) == ""


def dirty(repo):
    """Give both files a real change, so a reset or stash rewrites them; picks kept."""
    write_claude(repo, theme="light", model="opus")
    (repo / CODEX).write_text(TUI + (repo / CODEX).read_text())


def test_the_stop_hook_restores_the_picks_after_a_hard_reset(repo):
    picked(repo)
    dirty(repo)
    git(repo, "reset", "-q", "--hard")
    assert "model" not in claude(repo)

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert_picked(repo, theme="dark-ansi", codex_text=BASE)
    assert status(repo) == ""


def test_the_stop_hook_restores_the_picks_after_a_stash_round_trip(repo):
    picked(repo)
    write_claude(repo, theme="light", model="opus")
    git(repo, "stash", "-q")
    git(repo, "stash", "pop", "-q")
    assert "model" not in claude(repo)

    assert refresh(repo).returncode == 0

    assert claude(repo) == {"theme": "light", "model": "opus"}
    assert "model" not in git(repo, "diff", "--", CLAUDE).stdout


def test_the_stop_hook_restores_during_a_merge_stopped_on_a_conflict(repo):
    (repo / "u").write_text("base\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "u")
    git(repo, "switch", "-q", "-c", "side")
    (repo / "u").write_text("side\n")
    git(repo, "add", "u")
    commit_settings(repo, "side")
    git(repo, "switch", "-q", "main")
    (repo / "u").write_text("main\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "-m", "main")
    picked(repo)
    assert git(repo, "merge", "-q", "side", check=False).returncode == 1

    assert refresh(repo).returncode == 0

    assert_picked(repo)
    (repo / "u").write_text("both\n")
    git(repo, "add", "u")
    git(repo, "commit", "-q", "--no-edit")
    assert "model" not in git(repo, "show", "HEAD:" + CLAUDE).stdout
    assert '"theme": "light"' in git(repo, "show", "HEAD:" + CLAUDE).stdout
    assert status(repo) == ""


def test_a_picker_reset_without_forget_is_restored_at_stop(repo):
    picked(repo)
    write_claude(repo)

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert record(repo)[CLAUDE] == CLAUDE_SET
    assert claude(repo)["model"] == "opus"
    assert codex(repo)["model"] == "gpt-6.1-sol"

def test_a_new_claude_pick_after_codex_lost_its_pick_keeps_and_restores_it(repo):
    picked(repo)
    dirty(repo)
    git(repo, "reset", "-q", "--hard")
    write_claude(repo, model="sonnet")

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert record(repo)[CODEX] == CODEX_SET
    assert record(repo)[CLAUDE] == {"state": "set", "values": {"model": "sonnet"}}
    assert codex(repo)["model"] == "gpt-6.1-sol"

@pytest.mark.parametrize("name", [CLAUDE, CODEX])
def test_forget_while_the_index_is_locked_records_a_reset_that_stop_keeps(repo, name):
    picked(repo)
    before_index = git(repo, "write-tree").stdout
    lock = index_lock(repo)
    lock.write_text("")

    result = picks(repo, "forget", name)

    assert result.returncode == 0, result.stderr
    assert lock.read_text() == ""
    assert record(repo)[name] == {"state": "default"}
    assert clean(repo, name, (repo / name).read_text()) == (repo / name).read_text()
    lock.unlink()
    assert git(repo, "write-tree").stdout == before_index
    assert refresh(repo).returncode == 0
    live = claude(repo) if name == CLAUDE else codex(repo)
    assert "model" not in live
    assert record(repo)[name] == {"state": "default"}

@pytest.mark.parametrize("name", [CLAUDE, CODEX])
def test_stop_saves_a_changed_pick_even_while_the_index_is_locked(repo, name):
    picked(repo)
    if name == CLAUDE:
        write_claude(repo, model="sonnet")
        want = {"state": "set", "values": {"model": "sonnet"}}
    else:
        lines = ['model = "gpt-6-astra"\n', 'model_reasoning_effort = "medium"\n']
        (repo / CODEX).write_text("".join(lines) + BASE)
        want = {"state": "set", "lines": lines}
    before_index = git(repo, "write-tree").stdout
    lock = index_lock(repo)
    lock.write_text("")

    result = refresh(repo)

    assert result.returncode == 0, result.stderr
    assert record(repo)[name] == want
    assert lock.exists()
    lock.unlink()
    assert git(repo, "write-tree").stdout == before_index


def test_a_turn_end_with_the_index_locked_saves_but_does_not_restore(repo):
    picked(repo)
    dirty(repo)
    git(repo, "reset", "-q", "--hard")
    lock = index_lock(repo)
    lock.write_text("")

    assert refresh(repo).returncode == 0

    assert "model" not in claude(repo)
    lock.unlink()
    assert refresh(repo).returncode == 0
    assert claude(repo)["model"] == "opus"


def test_a_failed_capture_fails_the_hook_after_the_other_steps(repo):
    picked(repo)
    (repo / "local" / "codex" / "trust.toml").write_text(A)
    dirty(repo)
    git(repo, "reset", "-q", "--hard")
    (repo / CLAUDE).write_text("{\n")

    result = refresh(repo)

    assert result.returncode != 0
    assert "claude/settings.json does not parse" in result.stderr
    assert codex(repo)["model"] == "gpt-6.1-sol"
    assert "/work/a" in codex(repo)["projects"]


def test_a_missing_pick_tool_does_not_prevent_trust_recovery_or_staging(repo):
    write_claude(repo, model="sonnet")
    (repo / "local" / "codex" / "trust.toml").write_text(A)
    (repo / ".githooks" / "live-picks").unlink()

    result = refresh(repo)

    assert result.returncode != 0
    assert "live-picks capture" in result.stderr
    assert "live-picks restore" in result.stderr
    assert "Traceback" not in result.stderr
    assert codex(repo)["projects"] == {"/work/a": {"trust_level": "trusted"}}
    assert claude(repo)["model"] == "sonnet"
    assert git(repo, "diff-files", "--name-only", "--", CLAUDE, CODEX).stdout == ""


@pytest.mark.parametrize("damage", ["missing", "not_executable"])
def test_a_trust_launch_failure_does_not_prevent_pick_restoration(repo, damage):
    picked(repo)
    dirty(repo)
    git(repo, "reset", "-q", "--hard")
    trust = repo / ".githooks" / "codex-trust"
    if damage == "missing":
        trust.unlink()
    else:
        trust.chmod(0o600)

    result = refresh(repo)

    assert result.returncode != 0
    assert "codex-trust sync" in result.stderr
    assert "Traceback" not in result.stderr
    assert_picked(repo, theme="dark-ansi", codex_text=BASE)
    assert git(repo, "diff-files", "--name-only", "--", CLAUDE, CODEX).stdout == ""


def test_a_git_staging_failure_preserves_the_tool_failure_diagnostics(repo, tmp_path, monkeypatch):
    record_path(repo).write_text("{")
    original_git = shutil.which("git")
    commands = tmp_path / "commands"
    commands.mkdir()
    fake = commands / "git"
    fake.write_text(f"""#!/usr/bin/env python3
import os
import sys
if "diff-files" in sys.argv:
    print("simulated index read failure", file=sys.stderr)
    sys.exit(23)
os.execv({original_git!r}, [{original_git!r}, *sys.argv[1:]])
""")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(commands) + os.pathsep + os.environ["PATH"])

    result = refresh(repo)

    assert result.returncode != 0
    assert "local/live-picks.json" in result.stderr
    assert "simulated index read failure" in result.stderr
    assert "Traceback" not in result.stderr
```

In `.githooks/test_harness_state_refresh.py`, add `"live-picks"` to the fixture's copy loop (Task 2 added `"harness_state.py"`).

- [x] **Step 2: Run them to verify they fail**

Run: `just test`
Expected: FAIL in the new `test_live_picks.py` tests (the refresh never runs `live-picks`: no record is written, no pick restored).

- [x] **Step 3: Rewrite the refresh's `main`**

In `.githooks/harness-state-refresh`, replace `TRUST = ...` with:

```python
HERE = Path(__file__).resolve().parent
TRUST = HERE / "codex-trust"
PICKS = HERE / "live-picks"
```

and replace `main` with:

```python
def run(label, *command):
    try:
        result = subprocess.run([str(part) for part in command], text=True, capture_output=True)
    except OSError as error:
        result = subprocess.CompletedProcess(command, 1, stdout="",
                                             stderr=f"harness-state-refresh: {label}: {error}")
    return label, result


def main():
    sys.stdin.read()
    steps = [run("live-picks capture", PICKS, "capture")]
    failed = []
    try:
        lock = Path(checked("rev-parse", "--path-format=absolute", "--git-path", "index.lock").strip())
        if not lock.exists():
            steps.append(run("codex-trust sync", TRUST, "sync"))
            steps.append(run("live-picks restore", PICKS, "restore"))
            marked = checked("diff-files", "--name-only", "--", *PATTERNS).split()
            stale = [path for path in marked if filtered_equal(path)]
            if stale:
                checked("add", "--", *stale)
    except SystemExit as error:
        failed.append(str(error))
    failed += [result.stderr.strip()
               or f"harness-state-refresh: {label} exited {result.returncode} with no message"
               for label, result in steps if result.returncode != 0]
    if failed:
        sys.exit("\n".join(failed))
```

Replace the docstring's last paragraph ("It first runs `codex-trust sync`…") with:

```
It first runs `live-picks capture`, which reads the live configs and writes only
local/live-picks.json, so it runs even while another git process holds the index. At
Stop in both harnesses, capture never records an absence as a reset; only forget
records the default. Then, unless the index is locked, `codex-trust sync` saves and
restores Codex's project trust
and `live-picks restore` puts back a dropped pick; the staging below clears the mark
their inserts leave. A failed step still lets the others run, then fails the hook with
every failing step's message. Design:
docs/specs/2026-10-10-live-model-preservation-design.md §3.3.
```

Keep the existing Stop-only wiring; do not add a refresh command to PostModelSwitch.

- [x] **Step 4: Run the tests**

Run: `just test`
Expected: PASS, including the four existing refresh tests unchanged.

- [x] **Step 5: Commit**

```bash
git add .githooks/harness-state-refresh .githooks/test_harness_state_refresh.py .githooks/test_live_picks.py
git commit -m "feat(hooks): capture picks before the index-lock skip and restore them at turn end"
```

---

### Task 6: Docs

**Files:**
- Modify: `README.md` (Setup: the filter paragraph and the `git stash` sentence)
- Modify: `.githooks/harness-state-clean` (docstring)
- Modify: `AGENTS.md` (Layout, `.githooks/` bullet)
- Modify: `docs/specs/2026-09-29-codex-trust-restore-design.md` (§3.2 lock sentence)

- [x] **Step 1: README**

In `README.md`, replace "The working tree keeps the harness's last pick; a checkout of the file drops it, and the harness runs on its default model until the next pick." with the paragraph below, then start "Codex's project trust, …" as its own paragraph. Confirm the recorded probe with `tools/harness-facts get model-reset-clears-pick codex`; the observed value is false.

```
The working tree keeps the harness's last pick, and a checkout of the file drops it.
`.githooks/live-picks` puts it back. It saves each file's pick in `local/live-picks.json`
at every turn end in both harnesses. The `post-checkout`,
`post-merge` and `post-rewrite` hooks restore it right after a git command drops it, in
the main checkout only, and the next turn end restores it where no hook runs (the
commands listed below for trust). A file holding any of its model fields is never
touched, so a newer pick always wins. A file holding none is ambiguous, so only an
explicit act resets the saved pick: `.githooks/live-picks forget claude/settings.json`
(or `codex/config.toml`), which also removes the pick from the file. Claude's `/model`
Default clears its fields and the next turn end may restore the saved pick; use
`forget` for a deliberate reset. PostModelSwitch fires before the settings write and
may skip a reset to the same resolved model, so it is not a capture point. The tested
Codex picker actions kept both model fields; use `forget` to return it to its default.
A pick in either harness made since the last turn end is not saved yet; a git command
in that window brings back the one before. `local/live-picks.json` is machine-owned: an invalid one is refused,
never overwritten, and deleting it starts over.
```

In the "Do not `git stash` these files…" sentence, replace "so `stash pop` brings back the file without its model pick." with "so `stash pop` brings back the file without its model pick until the next turn end restores it."

- [x] **Step 2: Filter docstring**

In `.githooks/harness-state-clean`, replace "the smudge side is identity, so a checkout simply carries no default model until the next pick." with "the smudge side is identity, so a checkout drops the pick and `live-picks` puts the saved one back."

- [x] **Step 3: AGENTS.md and the trust spec**

In `AGENTS.md` Layout, change "`.githooks/`: config-state filtering, Codex trust preservation and commit checks." to "`.githooks/`: config-state filtering, Codex trust and model pick preservation, and commit checks."

In `docs/specs/2026-09-29-codex-trust-restore-design.md` §3.2, after the sentence beginning "Both operations run under an exclusive `flock` on `local/codex/trust.toml.lock`", add: "(Since 2026-10-10 the lock is `local/harness-state.lock`, shared with `live-picks`: `docs/specs/2026-10-10-live-model-preservation-design.md` §3.3.)"

- [x] **Step 4: Check and commit**

Run: `just test && tools/ops-docs check`
Expected: PASS; `ops-docs check` prints nothing.

```bash
git add README.md AGENTS.md .githooks/harness-state-clean docs/specs/2026-09-29-codex-trust-restore-design.md
git commit -m "docs: model picks return after git rewrites"
```

---

### Task 7: Rollout — tool and hooks into main

Merging activates the hooks in the live main checkout. This is an action the user approves at the time; approving the plan does not grant it.

- [ ] **Step 1: Confirm the branch leaves the live configs alone**

Run, from the main checkout: `git diff main...live-model-preservation -- claude/ codex/`
Expected: no output. Any output stops the rollout: the merge would rewrite a live config before the record exists.

- [ ] **Step 2: Record the live picks the merge must keep**

From the main checkout: `python3 -c 'import json;print(json.load(open("claude/settings.json")).get("model"))'` and `grep -E '^(model|model_reasoning_effort) ' codex/config.toml`. Note both on the task, including any absent owned fields. An absent pick is valid;
initial capture need not create an entry for that file.

- [ ] **Step 3: Review the completed branch, then ask the user to approve the merge**

Before asking, run `just test` in the worktree and obtain the fresh whole-branch review
required by native execution and flow. The reviewer reads the spec, plan, diff and raw
Task 1 evidence. Fix or rule on Critical/Important findings in the required corrective
rounds; keep deferred Minors in this plan's ledger. Record the verified tree and test
results on the task. No live merge occurs during this review.

Name the commits, the hooks it activates, and the two checks below. Wait for approval.

- [ ] **Step 4: Merge and verify**

From the main checkout: `git merge --no-ff live-model-preservation -m "feat(hooks): activate live model preservation (hq-a77096)"`. Then:

1. `git status --porcelain` prints nothing for `claude/` and `codex/`; the picks from Step 2 are unchanged.
2. Seed the record now rather than waiting for a turn end: from the main checkout, run `.githooks/live-picks capture`, then `cat local/live-picks.json`. For each file that held any owned field in Step 2, it must hold `set` with exactly
   that pick: Claude values (including `modelSettings` if present), or Codex source
   lines for the present keys. If a file held none, no entry or an existing `default`
   is valid; capture must not invent a `set` entry. If both held none and no record
   exists, capture succeeding without creating one is valid. Note the result on the task.
3. `rm -f local/codex/trust.toml.lock` (no tool takes it now).

A missing or different record fails the rollout: stop and report. There is no
PostModelSwitch wiring or second merge. Once capture matches, run `just test` from
main and record the combined verification and fresh whole-branch review before
closing the rollout and parent task. Preserve any unrelated main edits.

---
