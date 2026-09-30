# Session Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `tools/session-archive`, which captures every Claude Code and Codex transcript to a backup disk daily and prunes inactive ones from the live stores only after the archive and obs verifiably hold them.

**Architecture:** A stdlib-only Python package, `tools/session_archive/`, behind a thin `tools/session-archive` launcher. The prune decisions live in pure functions over plain records (`decide.py`). The modules around them gather inputs (`inputs.py`), write the archive (`capture.py`, `manifest.py`) and run the deletion protocols (`quarantine.py`, `prune.py`). Two user systemd timers run `capture` daily and `prune` monthly.

**Tech Stack:** Python 3.14 standard library (`sqlite3`, `tomllib`, `ctypes`, `fcntl`), pytest through `uv run --with pytest`, and systemd user units.

**Spec:** `docs/specs/2026-09-30-session-archive-design.md` (approved 2026-09-30). Read it before any task. Section references below (§3.4.2 and so on) point into it.

## Global Constraints

- Standard library only. `just test` runs the tests as `uv run -q --with pytest pytest .githooks tools -q`, and nothing else may be installed.
- Linux only: `renameat2` through `ctypes` and `/proc/*/fd` are required, not optional.
- Exit codes: `0` ok; `1` a failed file, unit, obs call, read-back, probe or leftover quarantine; `2` the host gate (§3.1); `75` the archive lock is held (`EX_TEMPFAIL`).
- Config: `~/.config/session-archive/config.toml` with the keys `archive_root` (string), `obs_command` (a non-empty list of strings), and the optional `uninspectable_ok` (a list of process `comm` names, default empty). Marker file: `<archive_root>/.session-archive-root`. See spec §3.1 and §3.4.
- A failed inspection of open files never counts as "nothing is open". The scope is processes of this user. A process or descriptor that disappears mid-scan is skipped; any other failure raises `InspectionFailed`, unless the process's `comm` is in `uninspectable_ok`.
- A failure to read a source directory or file is reported and fails the run. It is never skipped silently.
- Sources are the constant table in §3.2: `claude`, `claude-work`, `codex` are pruned; `codex-archived` and `codex-work` are captured only.
- Inactivity is 30 days. Capture runs daily at 04:00 and prune on the 1st at 05:00. The `codex delete` timeout is 120 seconds. `status` goes stale after 48 hours.
- The obs contract is `<obs_command> --json index-state`. It prints one JSON object, `{"schema": <int>, "files": [{"path", "size", "mtime_ms", "byte_offset", "partial_tail", "indexed_schema", "missing_since_ms"}]}`, and exits 0 (recorded on `obs-0bc168`).
- Tests touch only `tmp_path` trees and a stub `codex`, never a live harness store, `/mnt/backup`, or the real `codex` binary.
- No machine-specific absolute paths in code, comments or docs. Use `~`, `%h`, or a placeholder.
- Conventional commits, with no AI attribution.
- Run focused tests with `uv run -q --with pytest pytest <file>::<test> -q`, and `just test` before each commit.

## Review Focus

1. **Claude project directories that are not sessions**, such as the auto-memory directory `projects/<project>/memory/`, must never become prune units. Units are session-UUID-named only. Pinned in Task 8.
2. **A transcript deleted mid-walk** by Claude's own cleanup or by `codex delete` is counted `vanished`, and the capture run still succeeds. Pinned in Task 5.
3. **Symlinks inside a source root** are neither followed nor archived. Pinned in Task 5.
4. **Relative paths with spaces or `@`** round-trip through `versions/` and `promote`. Pinned in Tasks 4 and 6.
5. **The systemd user manager's `PATH` lacks `~/.local/bin`**, where `codex` lives. The prune and capture units set `PATH` explicitly. Pinned in Task 15.

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/session-archive` | Launcher: puts `tools/` on `sys.path` and calls `session_archive.cli.main` |
| `tools/session_archive/__init__.py` | Package docstring |
| `tools/session_archive/config.py` | Host gate, the §3.2 source table, the archive lock |
| `tools/session_archive/manifest.py` | `manifest.sqlite`: file versions, runs, Codex probe results |
| `tools/session_archive/decide.py` | Pure decisions: capture action, extension check, prune eligibility |
| `tools/session_archive/capture.py` | Copying one file, the daily run, `promote` |
| `tools/session_archive/inputs.py` | Prune inputs: obs index state, open inodes, unit discovery |
| `tools/session_archive/quarantine.py` | No-replace rename, the release rule, leftovers |
| `tools/session_archive/prune.py` | Evaluation, the Claude and Codex deletion protocols, the prune run |
| `tools/session_archive/probe.py` | `probe-codex` and the installed Codex version |
| `tools/session_archive/status.py` | The health report |
| `tools/session_archive/cli.py` | argparse, the host gate, the lock, one handler per subcommand |
| `tools/session_archive/testing.py` | Test helpers and the stub `codex` source |
| `tools/conftest.py` | Fixtures: `home`, `archive`, `manifest`, `stub_codex` |
| `tools/test_session_archive_*.py` | One test file per module |
| `systemd/user/session-archive-{capture,prune}.{service,timer}` | Units |
| `links.toml`, `README.md` | Unit links and the layout line |

---

### Task 1: Host gate, sources, lock and launcher

**Files:**
- Create: `tools/session-archive`, `tools/session_archive/__init__.py`, `tools/session_archive/config.py`, `tools/session_archive/cli.py`, `tools/session_archive/testing.py`, `tools/conftest.py`
- Test: `tools/test_session_archive_config.py`

**Interfaces:**
- Produces: `config.MARKER`, `config.EX_HOST = 2`, `config.EX_TEMPFAIL = 75`, `HostGateError`, `LockHeld`, `Source(name, kind, home, root, pruned)`, `sources(home: Path) -> tuple[Source, ...]`, `Config(archive_root: Path, obs_command: tuple[str, ...], uninspectable_ok: tuple[str, ...])`, `load_config(path) -> Config`, `check_sources(sources)`, `archive_lock(root)` context manager; `cli.main(argv) -> int`, `cli.COMMANDS: dict[str, handler]`, `cli.LOCKED`; `testing.write(path, data, age_days=None) -> Path`, `testing.age(path, days)`, `testing.write_config(home, archive, obs_command=("true",), uninspectable_ok=()) -> Path`, `testing.run_tool(*args, home) -> CompletedProcess`; fixtures `home`, `archive`.

- [ ] **Step 1: Write the failing tests**

`tools/test_session_archive_config.py`:

```python
"""The host gate refuses with exit 2 and a named cause; the archive lock refuses with 75."""
import fcntl
import os

import pytest

from session_archive import config
from session_archive.testing import run_tool, write_config


def test_sources_table_matches_spec(tmp_path):
    table = {s.name: (s.kind, s.root.relative_to(tmp_path).as_posix(), s.pruned)
             for s in config.sources(tmp_path)}
    assert table == {
        "claude": ("claude", ".claude/projects", True),
        "claude-work": ("claude", ".claude-work/projects", True),
        "codex": ("codex", ".codex/sessions", True),
        "codex-archived": ("codex", ".codex/archived_sessions", False),
        "codex-work": ("codex", ".codex-work/sessions", False),
    }


def test_unconfigured_host_exits_2(home):
    result = run_tool("capture", home=home)
    assert result.returncode == 2
    assert "not configured on this host" in result.stderr


def test_missing_archive_root_exits_2(home, tmp_path):
    write_config(home, tmp_path / "absent")
    result = run_tool("capture", home=home)
    assert result.returncode == 2
    assert "does not exist" in result.stderr


def test_missing_marker_exits_2(home, tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    write_config(home, bare)
    result = run_tool("capture", home=home)
    assert result.returncode == 2
    assert "lacks the marker file" in result.stderr


def test_missing_source_root_exits_2(home, archive):
    write_config(home, archive)
    (home / ".codex-work" / "sessions").rmdir()
    result = run_tool("capture", home=home)
    assert result.returncode == 2
    assert "source root missing" in result.stderr


@pytest.mark.parametrize("line", ['obs_command = []', 'obs_command = "obs"', ''])
def test_bad_obs_command_is_refused(tmp_path, archive, line):
    path = tmp_path / "config.toml"
    path.write_text(f'archive_root = "{archive}"\n{line}\n')
    with pytest.raises(config.HostGateError):
        config.load_config(path)


def test_uninspectable_ok_is_optional_and_typed(tmp_path, archive):
    path = tmp_path / "config.toml"
    base = f'archive_root = "{archive}"\nobs_command = ["obs"]\n'
    path.write_text(base)
    assert config.load_config(path).uninspectable_ok == ()
    path.write_text(base + 'uninspectable_ok = ["(sd-pam)"]\n')
    assert config.load_config(path).uninspectable_ok == ("(sd-pam)",)
    path.write_text(base + 'uninspectable_ok = "(sd-pam)"\n')
    with pytest.raises(config.HostGateError):
        config.load_config(path)


def test_held_lock_exits_75(home, archive):
    write_config(home, archive)
    fd = os.open(archive / ".lock", os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        result = run_tool("capture", home=home)
    finally:
        os.close(fd)
    assert result.returncode == 75
    assert "holds" in result.stderr
```

`tools/session_archive/testing.py`:

```python
"""Helpers shared by the session-archive tests."""
import os
import subprocess
import sys
import time
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "session-archive"
DAY_NS = 86_400 * 10**9


def write(path: Path, data: bytes, age_days: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if age_days is not None:
        age(path, age_days)
    return path


def age(path: Path, days: float) -> None:
    stamp = time.time_ns() - int(days * DAY_NS)
    os.utime(path, ns=(stamp, stamp))


def write_config(home: Path, archive: Path, obs_command=("true",), uninspectable_ok=()) -> Path:
    path = home / ".config" / "session-archive" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    command = ", ".join(f'"{part}"' for part in obs_command)
    allowed = ", ".join(f'"{name}"' for name in uninspectable_ok)
    path.write_text(f'archive_root = "{archive}"\nobs_command = [{command}]\nuninspectable_ok = [{allowed}]\n')
    return path


def run_tool(*args: str, home: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], env={**os.environ, "HOME": str(home)},
                          capture_output=True, text=True)
```

`tools/conftest.py`:

```python
"""Fixtures for the session-archive tests: a fake HOME holding every source root, and
an archive root with its marker. pytest puts tools/ on sys.path, so the package
imports by name."""
import pytest

from session_archive import config


@pytest.fixture
def home(tmp_path, monkeypatch):
    path = tmp_path / "home"
    for source in config.sources(path):
        source.root.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(path))
    return path


@pytest.fixture
def archive(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    (root / config.MARKER).touch()
    return root
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run -q --with pytest pytest tools/test_session_archive_config.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'session_archive'`.

- [ ] **Step 3: Implement**

`tools/session-archive` (mode 755):

```python
#!/usr/bin/env python3
"""session-archive: daily capture and verified prune of agent session stores.

Design: docs/specs/2026-09-30-session-archive-design.md."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from session_archive.cli import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
```

`tools/session_archive/__init__.py`:

```python
"""Capture agent session transcripts to a backup disk and prune what is verifiably kept.

Design: docs/specs/2026-09-30-session-archive-design.md."""
```

`tools/session_archive/config.py`:

```python
"""Host gate, the fixed source table, and the archive lock (spec §3.1–3.2)."""
import fcntl
import os
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

MARKER = ".session-archive-root"
EX_HOST = 2
EX_TEMPFAIL = 75


class HostGateError(Exception):
    """This host has no usable archive; the command line exits 2 with the message."""


class LockHeld(Exception):
    """Another capture, prune, promote or probe holds the archive lock; exit 75."""


@dataclass(frozen=True)
class Source:
    name: str
    kind: str        # "claude" or "codex"
    home: Path       # the harness home: parent of the quarantine; CODEX_HOME for codex
    root: Path       # the live root the archive mirrors
    pruned: bool     # prune covers it (spec §3.2)


def sources(home: Path) -> tuple[Source, ...]:
    claude, claude_work = home / ".claude", home / ".claude-work"
    codex, codex_work = home / ".codex", home / ".codex-work"
    return (
        Source("claude", "claude", claude, claude / "projects", True),
        Source("claude-work", "claude", claude_work, claude_work / "projects", True),
        Source("codex", "codex", codex, codex / "sessions", True),
        Source("codex-archived", "codex", codex, codex / "archived_sessions", False),
        Source("codex-work", "codex", codex_work, codex_work / "sessions", False),
    )


@dataclass(frozen=True)
class Config:
    archive_root: Path
    obs_command: tuple[str, ...]
    uninspectable_ok: tuple[str, ...]   # comm names whose open files may go uninspected


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise HostGateError(f"session-archive is not configured on this host ({path} is missing)")
    data = tomllib.loads(path.read_text())
    for key in ("archive_root", "obs_command"):
        if key not in data:
            raise HostGateError(f"{path}: missing key {key!r}")
    command = data["obs_command"]
    if not (isinstance(command, list) and command and all(isinstance(part, str) for part in command)):
        raise HostGateError(f"{path}: obs_command must be a non-empty list of strings")
    root = Path(os.path.expanduser(data["archive_root"]))
    if not root.is_dir():
        raise HostGateError(f"archive_root {root} does not exist (is the backup disk mounted?)")
    if not (root / MARKER).is_file():
        raise HostGateError(f"archive_root {root} lacks the marker file {MARKER}")
    allowed = data.get("uninspectable_ok", [])
    if not (isinstance(allowed, list) and all(isinstance(name, str) for name in allowed)):
        raise HostGateError(f"{path}: uninspectable_ok must be a list of strings")
    return Config(root, tuple(os.path.expanduser(part) for part in command), tuple(allowed))


def check_sources(table) -> None:
    missing = [str(source.root) for source in table if not source.root.is_dir()]
    if missing:
        raise HostGateError("source root missing: " + ", ".join(missing))


@contextmanager
def archive_lock(root: Path):
    fd = os.open(root / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LockHeld(f"another session-archive run holds {root / '.lock'}") from None
        yield
    finally:
        os.close(fd)
```

`tools/session_archive/cli.py`:

```python
"""session-archive command line (spec docs/specs/2026-09-30-session-archive-design.md)."""
import argparse
import sys
from contextlib import nullcontext
from pathlib import Path

from . import config

LOCKED = frozenset({"capture", "prune", "promote", "probe-codex"})


def config_path() -> Path:
    return Path.home() / ".config" / "session-archive" / "config.toml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="session-archive")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capture", help="copy every transcript into the archive")
    prune = sub.add_parser("prune", help="report eligible units; delete them with --apply")
    prune.add_argument("--apply", action="store_true")
    sub.add_parser("status", help="print archive health as JSON")
    promote = sub.add_parser("promote", help="make a diverged file's latest version the mirror")
    promote.add_argument("source")
    promote.add_argument("relpath")
    sub.add_parser("probe-codex", help="check Codex lock and delete behaviour in a throwaway home")
    return parser


# command name -> handler(cfg, sources, args) -> exit code; later tasks add entries.
COMMANDS = {}


def main(argv) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = config.load_config(config_path())
        table = config.sources(Path.home())
        config.check_sources(table)
        with config.archive_lock(cfg.archive_root) if args.command in LOCKED else nullcontext():
            return COMMANDS[args.command](cfg, table, args)
    except config.HostGateError as error:
        print(f"session-archive: {error}", file=sys.stderr)
        return config.EX_HOST
    except config.LockHeld as error:
        print(f"session-archive: {error}", file=sys.stderr)
        return config.EX_TEMPFAIL
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_config.py -q`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
chmod +x tools/session-archive
just test
git add tools/session-archive tools/session_archive tools/conftest.py tools/test_session_archive_config.py
git commit -m "feat(session-archive): host gate, source table and archive lock"
```

---

### Task 2: Manifest

**Files:**
- Create: `tools/session_archive/manifest.py`
- Modify: `tools/conftest.py` (add the `manifest` fixture)
- Test: `tools/test_session_archive_manifest.py`

**Interfaces:**
- Produces: `MIRROR = "mirror"`, `utc_now() -> str` (sortable `YYYY-MM-DDTHH:MM:SS.ffffffZ`), `Version(source, relpath, location, size, mtime_ns, sha256, captured_at)`, `Run(run_id, kind, mode, started_at, finished_at, ok: bool, report: dict)`, and `Manifest.open(archive_root)` with `.put(Version)`, `.rows(source, relpath) -> list[Version]` (newest first), `.mirror(source, relpath)`, `.latest(source, relpath)`, `.diverged() -> list[Version]`, `.total_size() -> int`, `.record_run(Run)`, `.last_run(kind, ok_only=False) -> Run | None`, `.record_probe(version, passed_at)`, `.probe_passed(version) -> bool`, `.close()`.

- [ ] **Step 1: Write the failing tests**

Add to `tools/conftest.py`:

```python
from session_archive.manifest import Manifest


@pytest.fixture
def manifest(archive):
    opened = Manifest.open(archive)
    yield opened
    opened.close()
```

`tools/test_session_archive_manifest.py`:

```python
"""The manifest orders versions newest first, prefers the mirror on a tie, and keeps logs."""
from dataclasses import replace

from session_archive.manifest import MIRROR, Manifest, Run, Version

V = Version("claude", "p/s.jsonl", MIRROR, 10, 1, "aa", "2026-01-01T00:00:00.000000Z")


def test_put_and_read_back(manifest):
    manifest.put(V)
    assert manifest.mirror("claude", "p/s.jsonl") == V
    assert manifest.latest("claude", "p/s.jsonl") == V
    assert manifest.mirror("claude", "other") is None


def test_latest_is_newest_and_diverged_lists_it(manifest):
    manifest.put(V)
    newer = replace(V, location="versions/claude/p/s.jsonl@2026-02-01T00:00:00.000000Z", size=4,
                    sha256="bb", captured_at="2026-02-01T00:00:00.000000Z")
    manifest.put(newer)
    assert manifest.latest("claude", "p/s.jsonl") == newer
    assert manifest.rows("claude", "p/s.jsonl") == [newer, V]
    assert manifest.diverged() == [newer]


def test_tie_prefers_mirror(manifest):
    version = replace(V, location="versions/claude/p/s.jsonl@x")
    manifest.put(version)
    manifest.put(V)
    assert manifest.latest("claude", "p/s.jsonl") == V
    assert manifest.diverged() == []


def test_total_size_counts_every_stored_version(manifest):
    manifest.put(V)
    manifest.put(replace(V, location="versions/x", size=5))
    assert manifest.total_size() == 15


def test_runs_and_probe(manifest):
    manifest.record_run(Run("r1", "capture", "apply", "2026-01-01T00:00:00.000000Z",
                            "2026-01-01T00:01:00.000000Z", True, {"claude": {"copied": 1}}))
    manifest.record_run(Run("r2", "capture", "apply", "2026-01-02T00:00:00.000000Z",
                            "2026-01-02T00:01:00.000000Z", False, {}))
    assert manifest.last_run("capture").run_id == "r2"
    assert manifest.last_run("capture", ok_only=True).report == {"claude": {"copied": 1}}
    assert manifest.last_run("prune") is None
    assert not manifest.probe_passed("codex-cli 1.0")
    manifest.record_probe("codex-cli 1.0", "2026-01-01T00:00:00.000000Z")
    assert manifest.probe_passed("codex-cli 1.0")


def test_persists_across_open(archive):
    first = Manifest.open(archive)
    first.put(V)
    first.close()
    second = Manifest.open(archive)
    assert second.mirror("claude", "p/s.jsonl") == V
    second.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run -q --with pytest pytest tools/test_session_archive_manifest.py -q`
Expected: `ModuleNotFoundError: No module named 'session_archive.manifest'`.

- [ ] **Step 3: Implement** `tools/session_archive/manifest.py`:

```python
"""The archive manifest: one row per archived file version, plus the run and Codex probe
logs (spec §3.3, §3.5)."""
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MIRROR = "mirror"
FILENAME = "manifest.sqlite"
SCHEMA = """
CREATE TABLE IF NOT EXISTS versions (
  source TEXT NOT NULL, relpath TEXT NOT NULL, location TEXT NOT NULL,
  size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, sha256 TEXT NOT NULL,
  captured_at TEXT NOT NULL, PRIMARY KEY (source, relpath, location));
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, kind TEXT NOT NULL, mode TEXT NOT NULL, started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL, ok INTEGER NOT NULL, report TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS codex_probe (version TEXT PRIMARY KEY, passed_at TEXT NOT NULL);
"""
COLUMNS = "source, relpath, location, size, mtime_ns, sha256, captured_at"
NEWEST = "ORDER BY captured_at DESC, location = 'mirror' DESC"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(frozen=True)
class Version:
    source: str
    relpath: str
    location: str      # MIRROR, or a path under versions/ relative to the archive root
    size: int
    mtime_ns: int
    sha256: str
    captured_at: str


@dataclass(frozen=True)
class Run:
    run_id: str
    kind: str          # "capture" or "prune"
    mode: str          # "apply" or "dry-run"
    started_at: str
    finished_at: str
    ok: bool
    report: dict


class Manifest:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @classmethod
    def open(cls, archive_root: Path) -> "Manifest":
        conn = sqlite3.connect(archive_root / FILENAME)
        conn.executescript(SCHEMA)
        return cls(conn)

    def close(self) -> None:
        self.conn.close()

    def put(self, version: Version) -> None:
        with self.conn:
            self.conn.execute(f"INSERT OR REPLACE INTO versions ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (version.source, version.relpath, version.location, version.size,
                               version.mtime_ns, version.sha256, version.captured_at))

    def rows(self, source: str, relpath: str) -> list[Version]:
        cursor = self.conn.execute(
            f"SELECT {COLUMNS} FROM versions WHERE source = ? AND relpath = ? {NEWEST}", (source, relpath))
        return [Version(*row) for row in cursor]

    def mirror(self, source: str, relpath: str) -> Version | None:
        row = self.conn.execute(
            f"SELECT {COLUMNS} FROM versions WHERE source = ? AND relpath = ? AND location = ?",
            (source, relpath, MIRROR)).fetchone()
        return Version(*row) if row else None

    def latest(self, source: str, relpath: str) -> Version | None:
        row = self.conn.execute(
            f"SELECT {COLUMNS} FROM versions WHERE source = ? AND relpath = ? {NEWEST} LIMIT 1",
            (source, relpath)).fetchone()
        return Version(*row) if row else None

    def diverged(self) -> list[Version]:
        """Files whose newest version is not the mirrored one (spec §3.3)."""
        cursor = self.conn.execute(f"""
            SELECT {COLUMNS} FROM (
              SELECT *, ROW_NUMBER() OVER (PARTITION BY source, relpath {NEWEST}) AS n FROM versions)
            WHERE n = 1 AND location != 'mirror' ORDER BY source, relpath""")
        return [Version(*row) for row in cursor]

    def total_size(self) -> int:
        return self.conn.execute("SELECT COALESCE(SUM(size), 0) FROM versions").fetchone()[0]

    def record_run(self, run: Run) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (run.run_id, run.kind, run.mode, run.started_at, run.finished_at,
                               int(run.ok), json.dumps(run.report, sort_keys=True)))

    def last_run(self, kind: str, ok_only: bool = False) -> Run | None:
        row = self.conn.execute(
            "SELECT run_id, kind, mode, started_at, finished_at, ok, report FROM runs "
            f"WHERE kind = ? {'AND ok = 1' if ok_only else ''} ORDER BY finished_at DESC LIMIT 1",
            (kind,)).fetchone()
        if row is None:
            return None
        return Run(*row[:5], bool(row[5]), json.loads(row[6]))

    def record_probe(self, version: str, passed_at: str) -> None:
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO codex_probe VALUES (?, ?)", (version, passed_at))

    def probe_passed(self, version: str) -> bool:
        return self.conn.execute("SELECT 1 FROM codex_probe WHERE version = ?", (version,)).fetchone() is not None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_manifest.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive/manifest.py tools/conftest.py tools/test_session_archive_manifest.py
git commit -m "feat(session-archive): manifest of archived versions, runs and probes"
```

---

### Task 3: Pure capture decisions

**Files:**
- Create: `tools/session_archive/decide.py`
- Test: `tools/test_session_archive_decide.py`

**Interfaces:**
- Consumes: `manifest.MIRROR`, `manifest.Version`.
- Produces: `Stat(size, mtime_ns)`; `capture_action(live: Stat, latest: Version | None, stored: Stat | None) -> "skip" | "repair" | "copy"`; `extends(size: int, prefix_sha256: str | None, mirror: Version | None) -> bool`.

- [ ] **Step 1: Write the failing tests** in `tools/test_session_archive_decide.py`:

```python
"""Pure decisions: capture action and the extension check (spec §3.3)."""
from session_archive.decide import Stat, capture_action, extends
from session_archive.manifest import MIRROR, Version


def version(size=10, mtime_ns=5, sha="d", location=MIRROR):
    return Version("claude", "p/s.jsonl", location, size, mtime_ns, sha, "2026-01-01T00:00:00.000000Z")


def test_first_sight_copies():
    assert capture_action(Stat(10, 5), None, None) == "copy"


def test_changed_file_copies():
    assert capture_action(Stat(12, 6), version(), Stat(10, 5)) == "copy"


def test_unchanged_with_intact_copy_skips():
    assert capture_action(Stat(10, 5), version(), Stat(10, 5)) == "skip"


def test_unchanged_with_missing_or_damaged_copy_repairs():
    assert capture_action(Stat(10, 5), version(), None) == "repair"
    assert capture_action(Stat(10, 5), version(), Stat(3, 5)) == "repair"


def test_extends_without_mirror():
    assert extends(4, None, None)


def test_extends_when_prefix_matches_recorded_digest():
    assert extends(15, "d", version(size=10, sha="d"))
    assert extends(10, "d", version(size=10, sha="d"))


def test_does_not_extend_when_shorter_or_different():
    assert not extends(9, None, version(size=10, sha="d"))
    assert not extends(15, "x", version(size=10, sha="d"))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_decide.py -q`
Expected: `ModuleNotFoundError: No module named 'session_archive.decide'`.

- [ ] **Step 3: Implement** `tools/session_archive/decide.py`:

```python
"""Pure decisions over plain records: what capture does with a file, and (Task 7) whether
a prune unit is eligible. Nothing here touches the filesystem (spec §3)."""
from dataclasses import dataclass

from .manifest import MIRROR, Version


@dataclass(frozen=True)
class Stat:
    size: int
    mtime_ns: int


def capture_action(live: Stat, latest: Version | None, stored: Stat | None) -> str:
    """"skip" when the newest archived version is this one and its copy is intact on disk,
    "repair" when it is this one but the copy is missing or differs, else "copy"."""
    if latest is None or (latest.size, latest.mtime_ns) != (live.size, live.mtime_ns):
        return "copy"
    return "skip" if stored == live else "repair"


def extends(size: int, prefix_sha256: str | None, mirror: Version | None) -> bool:
    """Whether a new version of `size` bytes, whose first mirror.size bytes hash to
    `prefix_sha256`, contains the recorded mirror version (spec §3.3 step 4). N and D
    come from the manifest row, never from the mirrored file."""
    if mirror is None:
        return True
    return size >= mirror.size and prefix_sha256 == mirror.sha256
```

(`MIRROR` is imported now for Task 7.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_decide.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive/decide.py tools/test_session_archive_decide.py
git commit -m "feat(session-archive): pure capture decisions and extension check"
```

---

### Task 4: Capturing one file

**Files:**
- Create: `tools/session_archive/capture.py`
- Test: `tools/test_session_archive_capture.py`

**Interfaces:**
- Consumes: `decide.Stat`, `capture_action`, `extends`; `manifest.MIRROR`, `Manifest`, `Version`, `utc_now`.
- Produces: `CHUNK`, `stat_of(path) -> Stat`, `hash_file(path) -> str`, `mirror_path(root, source, relpath) -> Path`, `version_location(source, relpath, captured_at) -> str`, `archived_file(root, version) -> Path`, `stored_stat(root, version) -> Stat | None`, `Copied(tmp, size, sha256, prefix_sha256)`, `copy_hashed(src, dest_dir, prefix) -> Copied`, `fsync_dir(path)`, `Outcome(action, version)`, `capture_file(root, manifest, source, relpath, path, *, force=False, now=utc_now) -> Outcome`. `action` is one of `unchanged`, `copied`, `repaired`, `diverged`, `busy`.

- [ ] **Step 1: Write the failing tests** in `tools/test_session_archive_capture.py`:

```python
"""Capturing one file: mirror, extension check, versions/, busy and repair (spec §3.3)."""
import os

import pytest

from session_archive import capture
from session_archive.capture import capture_file, hash_file, mirror_path
from session_archive.manifest import MIRROR
from session_archive.testing import write


@pytest.fixture
def live(tmp_path):
    return tmp_path / "live"


def cap(archive, manifest, live, rel, **kw):
    return capture_file(archive, manifest, "claude", rel, live / rel, **kw)


def test_first_capture_mirrors_with_source_mtime(archive, manifest, live):
    src = write(live / "p/s.jsonl", b"one\n")
    out = cap(archive, manifest, live, "p/s.jsonl")
    dest = mirror_path(archive, "claude", "p/s.jsonl")
    assert out.action == "copied"
    assert dest.read_bytes() == b"one\n"
    assert os.stat(dest).st_mtime_ns == os.stat(src).st_mtime_ns
    assert manifest.mirror("claude", "p/s.jsonl").sha256 == hash_file(src)


def test_unchanged_is_skipped(archive, manifest, live):
    write(live / "p/s.jsonl", b"one\n")
    cap(archive, manifest, live, "p/s.jsonl")
    assert cap(archive, manifest, live, "p/s.jsonl").action == "unchanged"


def test_append_replaces_mirror(archive, manifest, live):
    src = write(live / "p/s.jsonl", b"one\n")
    cap(archive, manifest, live, "p/s.jsonl")
    with open(src, "ab") as handle:
        handle.write(b"two\n")
    assert cap(archive, manifest, live, "p/s.jsonl").action == "copied"
    assert mirror_path(archive, "claude", "p/s.jsonl").read_bytes() == b"one\ntwo\n"


@pytest.mark.parametrize("rewrite", [b"on", b"ONE\nmore\n"])
def test_truncated_or_rewritten_goes_to_versions(archive, manifest, live, rewrite):
    rel = "p q/s@x.jsonl"
    src = write(live / rel, b"one\n")
    cap(archive, manifest, live, rel)
    src.write_bytes(rewrite)
    out = cap(archive, manifest, live, rel)
    assert out.action == "diverged"
    assert out.version.location.startswith("versions/claude/p q/s@x.jsonl@")
    assert (archive / out.version.location).read_bytes() == rewrite
    assert mirror_path(archive, "claude", rel).read_bytes() == b"one\n"
    assert manifest.mirror("claude", rel).size == 4


def test_change_during_copy_is_busy(archive, manifest, live, monkeypatch):
    src = write(live / "p/s.jsonl", b"one\n")
    real = capture.copy_hashed

    def copy_then_append(*args):
        copied = real(*args)
        with open(src, "ab") as handle:
            handle.write(b"late\n")
        return copied

    monkeypatch.setattr(capture, "copy_hashed", copy_then_append)
    out = cap(archive, manifest, live, "p/s.jsonl")
    assert out.action == "busy"
    assert manifest.latest("claude", "p/s.jsonl") is None
    assert not any(p.name.startswith(".capture-") for p in (archive / "claude" / "p").iterdir())


def test_missing_mirror_is_repaired(archive, manifest, live):
    write(live / "p/s.jsonl", b"one\n")
    cap(archive, manifest, live, "p/s.jsonl")
    mirror_path(archive, "claude", "p/s.jsonl").unlink()
    assert cap(archive, manifest, live, "p/s.jsonl").action == "repaired"
    assert mirror_path(archive, "claude", "p/s.jsonl").read_bytes() == b"one\n"


def test_truncated_mirror_is_repaired_in_place(archive, manifest, live):
    write(live / "p/s.jsonl", b"one\ntwo\n")
    cap(archive, manifest, live, "p/s.jsonl")
    mirror_path(archive, "claude", "p/s.jsonl").write_bytes(b"on")
    out = cap(archive, manifest, live, "p/s.jsonl")
    assert out.action == "repaired"
    assert out.version.location == MIRROR
    assert hash_file(mirror_path(archive, "claude", "p/s.jsonl")) == manifest.mirror("claude", "p/s.jsonl").sha256
    assert not (archive / "versions").exists()


def test_same_size_corruption_needs_force(archive, manifest, live):
    src = write(live / "p/s.jsonl", b"one\n")
    cap(archive, manifest, live, "p/s.jsonl")
    dest = mirror_path(archive, "claude", "p/s.jsonl")
    dest.write_bytes(b"ONE\n")
    stamp = os.stat(src).st_mtime_ns
    os.utime(dest, ns=(stamp, stamp))
    assert cap(archive, manifest, live, "p/s.jsonl").action == "unchanged"
    assert cap(archive, manifest, live, "p/s.jsonl", force=True).action == "repaired"
    assert dest.read_bytes() == b"one\n"
    assert not (archive / "versions").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_capture.py -q`
Expected: `ModuleNotFoundError: No module named 'session_archive.capture'`.

- [ ] **Step 3: Implement** `tools/session_archive/capture.py`:

```python
"""Capturing files into the archive (spec §3.3): the mirror, versions/, and the manifest."""
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .decide import Stat, capture_action, extends
from .manifest import MIRROR, Manifest, Version, utc_now

CHUNK = 1 << 20


def stat_of(path: Path) -> Stat:
    info = os.stat(path, follow_symlinks=False)
    return Stat(info.st_size, info.st_mtime_ns)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def mirror_path(root: Path, source: str, relpath: str) -> Path:
    return root / source / relpath


def version_location(source: str, relpath: str, captured_at: str) -> str:
    return f"versions/{source}/{relpath}@{captured_at}"


def archived_file(root: Path, version: Version) -> Path:
    if version.location == MIRROR:
        return mirror_path(root, version.source, version.relpath)
    return root / version.location


def stored_stat(root: Path, version: Version | None) -> Stat | None:
    if version is None:
        return None
    try:
        return stat_of(archived_file(root, version))
    except FileNotFoundError:
        return None


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class Copied:
    tmp: Path
    size: int
    sha256: str
    prefix_sha256: str | None   # digest of the first `prefix` bytes; None when shorter


def copy_hashed(src: Path, dest_dir: Path, prefix: int | None) -> Copied:
    """Copy src to an fsynced temporary file in dest_dir. One pass hashes the whole file and,
    when prefix is given, its first prefix bytes."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=dest_dir, prefix=".capture-")
    whole, head, seen = hashlib.sha256(), hashlib.sha256(), 0
    try:
        with os.fdopen(fd, "wb") as writer, open(src, "rb") as reader:
            while chunk := reader.read(CHUNK):
                if prefix is not None and seen < prefix:
                    head.update(chunk[: prefix - seen])
                whole.update(chunk)
                writer.write(chunk)
                seen += len(chunk)
            writer.flush()
            os.fsync(writer.fileno())
    except BaseException:
        os.unlink(name)
        raise
    prefix_sha256 = head.hexdigest() if prefix is not None and seen >= prefix else None
    return Copied(Path(name), seen, whole.hexdigest(), prefix_sha256)


@dataclass(frozen=True)
class Outcome:
    action: str              # unchanged | copied | repaired | diverged | busy
    version: Version | None


def capture_file(root: Path, manifest: Manifest, source: str, relpath: str, path: Path, *,
                 force: bool = False, now=utc_now) -> Outcome:
    """Capture `path` as `source`/`relpath`. `path` is normally the live file; prune passes a
    quarantined one. With force, an unchanged file is copied again (read-back repair)."""
    live = stat_of(path)
    latest = manifest.latest(source, relpath)
    action = capture_action(live, latest, stored_stat(root, latest))
    if action == "skip" and not force:
        return Outcome("unchanged", latest)
    mirror = manifest.mirror(source, relpath)
    mirrored = mirror_path(root, source, relpath)
    copied = copy_hashed(path, mirrored.parent, mirror.size if mirror else None)
    if stat_of(path) != live:
        copied.tmp.unlink()
        return Outcome("busy", None)
    captured_at = now()
    if extends(copied.size, copied.prefix_sha256, mirror):
        location, dest = MIRROR, mirrored
    else:
        location = version_location(source, relpath, captured_at)
        dest = root / location
        dest.parent.mkdir(parents=True, exist_ok=True)
    os.utime(copied.tmp, ns=(live.mtime_ns, live.mtime_ns))
    os.replace(copied.tmp, dest)
    fsync_dir(dest.parent)
    version = Version(source, relpath, location, copied.size, live.mtime_ns, copied.sha256, captured_at)
    manifest.put(version)
    if location != MIRROR:
        return Outcome("diverged", version)
    return Outcome("copied" if action == "copy" else "repaired", version)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_capture.py -q`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive/capture.py tools/test_session_archive_capture.py
git commit -m "feat(session-archive): capture one file with extension check and repair"
```

---

### Task 5: Capture run and the `capture` command

**Files:**
- Modify: `tools/session_archive/capture.py` (add `COUNTS`, `walk_files`, `capture_run`), `tools/session_archive/cli.py` (add `cmd_capture`)
- Test: `tools/test_session_archive_capture_run.py`

**Interfaces:**
- Consumes: `capture_file`, `config.Source`, `Manifest`, `Run`.
- Produces: `COUNTS` (`scanned copied repaired diverged unchanged busy vanished failed`); `walk_files(top, errors=None) -> Iterator[Path]` (sorted, regular files only, no symlinks). An unreadable directory or entry raises, or, when an `errors` list is given, is appended there as `(path, error)` and the walk continues. Also `capture_run(root, manifest, sources) -> tuple[dict, bool]` and `cli.cmd_capture`. The report is `{source: {count: n, ..., "errors": [..] when any}}`, or `{"error": ...}` when the run stops on an I/O error outside a single file.

- [ ] **Step 1: Write the failing tests** in `tools/test_session_archive_capture_run.py`:

```python
"""The daily run over every source, and the capture command (spec §3.3)."""
import json
import os

import pytest

from session_archive import capture, config
from session_archive.capture import capture_run, mirror_path
from session_archive.manifest import Manifest
from session_archive.testing import run_tool, write, write_config


def table(home):
    return config.sources(home)


def test_counts_and_mirror(home, archive, manifest):
    write(home / ".claude/projects/p/a.jsonl", b"a\n")
    write(home / ".codex/sessions/2026/01/01/r.jsonl", b"r\n")
    report, ok = capture_run(archive, manifest, table(home))
    assert ok
    assert report["claude"]["copied"] == 1 and report["claude"]["scanned"] == 1
    assert report["codex"]["copied"] == 1
    assert mirror_path(archive, "codex", "2026/01/01/r.jsonl").read_bytes() == b"r\n"
    again, _ = capture_run(archive, manifest, table(home))
    assert again["claude"]["unchanged"] == 1


def test_removed_source_stays_archived(home, archive, manifest):
    src = write(home / ".claude/projects/p/a.jsonl", b"a\n")
    capture_run(archive, manifest, table(home))
    src.unlink()
    capture_run(archive, manifest, table(home))
    assert mirror_path(archive, "claude", "p/a.jsonl").read_bytes() == b"a\n"


def test_symlinks_are_not_followed(home, archive, manifest, tmp_path):
    outside = write(tmp_path / "outside.txt", b"secret")
    link = home / ".claude/projects/p/link.jsonl"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    report, _ = capture_run(archive, manifest, table(home))
    assert report["claude"]["scanned"] == 0
    assert not mirror_path(archive, "claude", "p/link.jsonl").exists()


def test_file_vanishing_mid_walk_is_counted_not_failed(home, archive, manifest, monkeypatch):
    src = write(home / ".claude/projects/p/a.jsonl", b"a\n")
    real = capture.capture_file

    def vanish(root, man, source, relpath, path, **kw):
        path.unlink()
        return real(root, man, source, relpath, path, **kw)

    monkeypatch.setattr(capture, "capture_file", vanish)
    report, ok = capture_run(archive, manifest, table(home))
    assert ok and report["claude"]["vanished"] == 1 and not src.exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable files")
def test_unreadable_file_fails_the_run(home, archive, manifest):
    src = write(home / ".claude/projects/p/a.jsonl", b"a\n")
    src.chmod(0)
    try:
        report, ok = capture_run(archive, manifest, table(home))
    finally:
        src.chmod(0o600)
    assert not ok
    assert report["claude"]["failed"] == 1 and "p/a.jsonl" in report["claude"]["errors"][0]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable directories")
def test_unreadable_directory_fails_the_run(home, archive, manifest):
    write(home / ".claude/projects/p/a.jsonl", b"a\n")
    write(home / ".claude/projects/q/b.jsonl", b"b\n")
    locked = home / ".claude/projects/p"
    locked.chmod(0)
    try:
        report, ok = capture_run(archive, manifest, table(home))
    finally:
        locked.chmod(0o700)
    assert not ok
    assert report["claude"]["failed"] == 1 and report["claude"]["copied"] == 1
    assert report["claude"]["errors"][0].startswith("p: unreadable:")


def test_capture_command_records_the_run(home, archive):
    write(home / ".claude/projects/p/a.jsonl", b"a\n")
    write_config(home, archive)
    result = run_tool("capture", home=home)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["claude"]["copied"] == 1
    opened = Manifest.open(archive)
    assert opened.last_run("capture", ok_only=True).report["claude"]["copied"] == 1
    opened.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_capture_run.py -q`
Expected: `ImportError: cannot import name 'capture_run'`.

- [ ] **Step 3: Implement.** Append to `tools/session_archive/capture.py`:

```python
COUNTS = ("scanned", "copied", "repaired", "diverged", "unchanged", "busy", "vanished", "failed")


def walk_files(top: Path, errors: list | None = None):
    """Every regular file under top, depth first in sorted order, never following or
    yielding symlinks. A directory or entry that cannot be read raises; with `errors`
    given, it is appended there as (path, error) and the walk goes on."""
    stack = [Path(top)]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as scan:
                entries = sorted(scan, key=lambda entry: entry.name)
        except OSError as error:
            if errors is None:
                raise
            errors.append((directory, error))
            continue
        subdirectories = []
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    subdirectories.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)
            except OSError as error:
                if errors is None:
                    raise
                errors.append((Path(entry.path), error))
        stack.extend(reversed(subdirectories))


def capture_run(root: Path, manifest: Manifest, sources) -> tuple[dict, bool]:
    report = {}
    for source in sources:
        counts = dict.fromkeys(COUNTS, 0)
        errors, unreadable = [], []
        for path in walk_files(source.root, unreadable):
            relpath = path.relative_to(source.root).as_posix()
            counts["scanned"] += 1
            try:
                counts[capture_file(root, manifest, source.name, relpath, path).action] += 1
            except OSError as error:
                if not os.path.lexists(path):
                    counts["vanished"] += 1
                else:
                    counts["failed"] += 1
                    errors.append(f"{relpath}: {error}")
        for path, error in unreadable:
            counts["failed"] += 1
            errors.append(f"{path.relative_to(source.root).as_posix()}: unreadable: {error}")
        report[source.name] = {**counts, "errors": errors} if errors else counts
    return report, all(entry["failed"] == 0 for entry in report.values())
```

In `tools/session_archive/cli.py`, add these imports at the top:

```python
import json
import uuid

from . import capture
from .manifest import Manifest, Run, utc_now
```

Then add the handler above `COMMANDS`, and register it:

```python
def cmd_capture(cfg, table, args) -> int:
    manifest = Manifest.open(cfg.archive_root)
    try:
        started = utc_now()
        try:
            report, ok = capture.capture_run(cfg.archive_root, manifest, table)
        except OSError as error:
            report, ok = {"error": f"{type(error).__name__}: {error}"}, False
        manifest.record_run(Run(uuid.uuid4().hex, "capture", "apply", started, utc_now(), ok, report))
    finally:
        manifest.close()
    print(json.dumps(report, sort_keys=True))
    return 0 if ok else 1


COMMANDS = {"capture": cmd_capture}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_capture_run.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive tools/test_session_archive_capture_run.py
git commit -m "feat(session-archive): daily capture run and capture command"
```

---

### Task 6: Promote

**Files:**
- Modify: `tools/session_archive/capture.py` (add `PromoteError`, `promote`), `tools/session_archive/cli.py` (add `cmd_promote`)
- Test: `tools/test_session_archive_promote.py`

**Interfaces:**
- Consumes: `copy_hashed`, `hash_file`, `mirror_path`, `version_location`, `fsync_dir`, `Manifest`.
- Produces: `PromoteError`, `promote(root, manifest, source, relpath) -> Version` (the new mirror row), `cli.cmd_promote`. The mirror path is never absent. The replacement is prepared first, the old mirror is kept under `versions/` by a hard link, and a single `os.replace` swaps it in, so an interrupted promote can be rerun.

- [ ] **Step 1: Write the failing tests** in `tools/test_session_archive_promote.py`:

```python
"""promote makes a diverged file's latest version the mirror, deleting nothing (spec §3.3)."""
import os

import pytest

from session_archive import capture
from session_archive.capture import PromoteError, capture_file, mirror_path, promote
from session_archive.manifest import MIRROR
from session_archive.testing import run_tool, write, write_config

REL = "p q/s@x.jsonl"


def diverge(archive, manifest, tmp_path):
    src = write(tmp_path / "live" / REL, b"one\ntwo\n")
    capture_file(archive, manifest, "claude", REL, src)
    src.write_bytes(b"rewritten\n")
    assert capture_file(archive, manifest, "claude", REL, src).action == "diverged"
    return src


def test_promote_swaps_mirror_and_keeps_old(archive, manifest, tmp_path):
    diverge(archive, manifest, tmp_path)
    old = manifest.mirror("claude", REL)
    promoted = promote(archive, manifest, "claude", REL)
    assert promoted.location == MIRROR
    assert mirror_path(archive, "claude", REL).read_bytes() == b"rewritten\n"
    kept = [v for v in manifest.rows("claude", REL) if v.sha256 == old.sha256]
    assert len(kept) == 1 and kept[0].location.startswith("versions/")
    assert (archive / kept[0].location).read_bytes() == b"one\ntwo\n"
    assert manifest.latest("claude", REL).location == MIRROR
    assert manifest.diverged() == []


def test_promote_refuses_when_not_diverged(archive, manifest, tmp_path):
    src = write(tmp_path / "live" / REL, b"one\n")
    capture_file(archive, manifest, "claude", REL, src)
    with pytest.raises(PromoteError, match="not diverged"):
        promote(archive, manifest, "claude", REL)
    with pytest.raises(PromoteError, match="no archived version"):
        promote(archive, manifest, "claude", "absent")


def test_interrupted_copy_keeps_mirror_and_retry_works(archive, manifest, tmp_path, monkeypatch):
    diverge(archive, manifest, tmp_path)

    def disk_full(*args):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(capture, "copy_hashed", disk_full)
    with pytest.raises(OSError):
        promote(archive, manifest, "claude", REL)
    monkeypatch.undo()
    assert mirror_path(archive, "claude", REL).read_bytes() == b"one\ntwo\n"
    assert len(manifest.rows("claude", REL)) == 2
    promote(archive, manifest, "claude", REL)
    assert mirror_path(archive, "claude", REL).read_bytes() == b"rewritten\n"


def test_interrupted_swap_keeps_old_version_and_retry_works(archive, manifest, tmp_path, monkeypatch):
    diverge(archive, manifest, tmp_path)

    def io_error(*args):
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(capture.os, "replace", io_error)
    with pytest.raises(OSError):
        promote(archive, manifest, "claude", REL)
    monkeypatch.undo()
    mirrored = mirror_path(archive, "claude", REL)
    assert mirrored.read_bytes() == b"one\ntwo\n"
    assert not any(p.name.startswith(".capture-") for p in mirrored.parent.iterdir())
    promote(archive, manifest, "claude", REL)
    assert mirrored.read_bytes() == b"rewritten\n"
    old = [v for v in manifest.rows("claude", REL) if v.location.startswith("versions/") and v.size == 8]
    assert len(old) == 1 and (archive / old[0].location).read_bytes() == b"one\ntwo\n"


def test_promote_command(home, archive, manifest):
    src = write(home / ".claude/projects" / REL, b"one\n")
    capture_file(archive, manifest, "claude", REL, src)
    src.write_bytes(b"x\n")
    capture_file(archive, manifest, "claude", REL, src)
    write_config(home, archive)
    result = run_tool("promote", "claude", REL, home=home)
    assert result.returncode == 0, result.stderr
    assert run_tool("promote", "claude", REL, home=home).returncode == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_promote.py -q`
Expected: `ImportError: cannot import name 'PromoteError'`.

- [ ] **Step 3: Implement.** Append to `capture.py` (also add `from dataclasses import replace` to its imports):

```python
class PromoteError(Exception):
    pass


def promote(root: Path, manifest: Manifest, source: str, relpath: str) -> Version:
    """Make the newest captured version the mirror. The replacement is prepared first; the
    old mirror is kept under versions/ by a hard link, so the mirror path never goes away;
    one rename swaps the new version in. An interrupted promote can simply be rerun."""
    latest = manifest.latest(source, relpath)
    if latest is None:
        raise PromoteError(f"{source}/{relpath} has no archived version")
    if latest.location == MIRROR:
        raise PromoteError(f"{source}/{relpath} is not diverged")
    stored = root / latest.location
    dest = mirror_path(root, source, relpath)
    copied = copy_hashed(stored, dest.parent, None)
    try:
        if copied.sha256 != latest.sha256:
            raise PromoteError(f"{stored} does not match its manifest sha256")
        mirror = manifest.mirror(source, relpath)
        if mirror is not None:
            if hash_file(dest) != mirror.sha256:
                raise PromoteError(f"{dest} is damaged; run capture to repair it first")
            old = version_location(source, relpath, mirror.captured_at)
            (root / old).parent.mkdir(parents=True, exist_ok=True)
            if not (root / old).exists():
                os.link(dest, root / old)
                fsync_dir((root / old).parent)
            elif hash_file(root / old) != mirror.sha256:
                raise PromoteError(f"{root / old} exists with other content")
            manifest.put(replace(mirror, location=old))
        os.utime(copied.tmp, ns=(latest.mtime_ns, latest.mtime_ns))
        os.replace(copied.tmp, dest)
    except BaseException:
        copied.tmp.unlink(missing_ok=True)
        raise
    fsync_dir(dest.parent)
    promoted = replace(latest, location=MIRROR)
    manifest.put(promoted)
    return promoted
```

In `cli.py`, add `from dataclasses import asdict` and:

```python
def cmd_promote(cfg, table, args) -> int:
    manifest = Manifest.open(cfg.archive_root)
    try:
        promoted = capture.promote(cfg.archive_root, manifest, args.source, args.relpath)
    except capture.PromoteError as error:
        print(f"session-archive: {error}", file=sys.stderr)
        return 1
    finally:
        manifest.close()
    print(json.dumps(asdict(promoted), sort_keys=True))
    return 0


COMMANDS = {"capture": cmd_capture, "promote": cmd_promote}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_promote.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive tools/test_session_archive_promote.py
git commit -m "feat(session-archive): promote a diverged version into the mirror"
```

---

### Task 7: Pure prune eligibility

**Files:**
- Modify: `tools/session_archive/decide.py`
- Test: `tools/test_session_archive_eligibility.py`

**Interfaces:**
- Produces: `INACTIVE_NS`, `ObsFile(size, mtime_ms, byte_offset, partial_tail, schema_current, missing)`, `FileFacts(relpath, live, live_sha256, mirror, latest, mirror_sha256, transcript, obs, tail_has_newline, open)`, `is_transcript(kind, relpath) -> bool`, `file_reason(facts, now_ns) -> str | None`, `unit_reason(files, now_ns) -> str | None`. Reasons, in check order: `active`, `diverged`, `uncaptured`, `archive-damaged`, `unindexed`, `index-stale`, `open`; plus `empty` for a unit with no files.

- [ ] **Step 1: Write the failing tests** in `tools/test_session_archive_eligibility.py`:

```python
"""One case per prune condition (spec §3.4), over constructed records only."""
from dataclasses import replace

import pytest

from session_archive.decide import FileFacts, ObsFile, Stat, file_reason, is_transcript, unit_reason
from session_archive.manifest import MIRROR, Version

DAY = 86_400 * 10**9
NOW = 400 * DAY
OLD = NOW - 40 * DAY


def version(location=MIRROR, size=10, sha="a"):
    return Version("claude", "p/s.jsonl", location, size, OLD, sha, "2026-01-01T00:00:00.000000Z")


PASSING = FileFacts(
    relpath="p/s.jsonl", live=Stat(10, OLD), live_sha256="a", mirror=version(), latest=version(),
    mirror_sha256="a", transcript=True, obs=ObsFile(10, OLD // 1_000_000, 10, False, True, False),
    tail_has_newline=False, open=False)


def test_passing_file():
    assert file_reason(PASSING, NOW) is None


@pytest.mark.parametrize("change, reason", [
    (dict(live=Stat(10, NOW - 29 * DAY)), "active"),
    (dict(latest=version(location="versions/x", sha="b"), mirror=version(size=4)), "diverged"),
    (dict(mirror=None, latest=None), "uncaptured"),
    (dict(live_sha256="b"), "uncaptured"),
    (dict(mirror_sha256="z"), "archive-damaged"),
    (dict(mirror_sha256=None), "archive-damaged"),
    (dict(obs=None), "unindexed"),
    (dict(obs=ObsFile(10, OLD // 1_000_000, 10, False, True, True)), "unindexed"),
    (dict(obs=ObsFile(9, OLD // 1_000_000, 9, False, True, False)), "index-stale"),
    (dict(obs=ObsFile(10, OLD // 1_000_000, 10, False, False, False)), "index-stale"),
    (dict(obs=ObsFile(10, OLD // 1_000_000, 8, False, True, False)), "index-stale"),
    (dict(obs=ObsFile(10, OLD // 1_000_000, 8, True, True, False), tail_has_newline=True), "index-stale"),
    (dict(open=True), "open"),
])
def test_each_condition(change, reason):
    assert file_reason(replace(PASSING, **change), NOW) == reason


def test_partial_tail_without_newline_passes():
    facts = replace(PASSING, obs=ObsFile(10, OLD // 1_000_000, 8, True, True, False))
    assert file_reason(facts, NOW) is None


def test_non_transcript_needs_no_index():
    assert file_reason(replace(PASSING, transcript=False, obs=None), NOW) is None


def test_unit_takes_first_failure_and_keeps_empty():
    assert unit_reason([PASSING, replace(PASSING, open=True), replace(PASSING, obs=None)], NOW) == "open"
    assert unit_reason([PASSING], NOW) is None
    assert unit_reason([], NOW) == "empty"


@pytest.mark.parametrize("kind, rel, expected", [
    ("claude", "p/s.jsonl", True),
    ("claude", "p/s/subagents/agent-1.jsonl", True),
    ("claude", "p/s/tool-results/r.txt", False),
    ("claude", "p/s/tool-results/r.jsonl", False),
    ("codex", "2026/01/01/rollout-x.jsonl", True),
    ("codex", "2026/01/01/notes.txt", False),
])
def test_is_transcript(kind, rel, expected):
    assert is_transcript(kind, rel) is expected
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_eligibility.py -q`
Expected: `ImportError: cannot import name 'FileFacts'`.

- [ ] **Step 3: Implement.** Append to `decide.py`:

```python
INACTIVE_NS = 30 * 86_400 * 10**9


@dataclass(frozen=True)
class ObsFile:
    size: int
    mtime_ms: int
    byte_offset: int
    partial_tail: bool
    schema_current: bool
    missing: bool


@dataclass(frozen=True)
class FileFacts:
    relpath: str
    live: Stat
    live_sha256: str
    mirror: Version | None       # the manifest's mirror row
    latest: Version | None       # the manifest's newest row, mirror or versions/
    mirror_sha256: str | None    # the mirrored copy as read back now; None when absent
    transcript: bool             # obs is expected to index this file
    obs: ObsFile | None
    tail_has_newline: bool       # the bytes after obs.byte_offset contain a newline
    open: bool                   # some process holds this inode open


def is_transcript(kind: str, relpath: str) -> bool:
    """The files obs indexes: Claude `<project>/<id>.jsonl` and
    `<project>/<id>/subagents/*.jsonl`, and every Codex `*.jsonl`."""
    if not relpath.endswith(".jsonl"):
        return False
    if kind == "codex":
        return True
    parts = relpath.split("/")
    return len(parts) == 2 or (len(parts) == 4 and parts[2] == "subagents")


def file_reason(f: FileFacts, now_ns: int) -> str | None:
    """The first prune condition (spec §3.4) this file fails, or None when it passes them all."""
    if now_ns - f.live.mtime_ns <= INACTIVE_NS:
        return "active"
    live_key = (f.live.size, f.live.mtime_ns)
    if f.latest is not None and f.latest.location != MIRROR and (f.latest.size, f.latest.mtime_ns) == live_key:
        return "diverged"
    if f.mirror is None or (f.mirror.size, f.mirror.mtime_ns) != live_key or f.live_sha256 != f.mirror.sha256:
        return "uncaptured"
    if f.mirror_sha256 != f.mirror.sha256:
        return "archive-damaged"
    if f.transcript:
        o = f.obs
        if o is None or o.missing:
            return "unindexed"
        read_all = o.byte_offset == f.live.size or (
            o.partial_tail and o.byte_offset < f.live.size and not f.tail_has_newline)
        if (o.size, o.mtime_ms) != (f.live.size, f.live.mtime_ns // 1_000_000) or not o.schema_current or not read_all:
            return "index-stale"
    if f.open:
        return "open"
    return None


def unit_reason(files: list[FileFacts], now_ns: int) -> str | None:
    """The first failure across a unit's files; a unit with no files is kept."""
    if not files:
        return "empty"
    for facts in files:
        reason = file_reason(facts, now_ns)
        if reason:
            return reason
    return None
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_eligibility.py -q`
Expected: 23 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive/decide.py tools/test_session_archive_eligibility.py
git commit -m "feat(session-archive): pure prune eligibility over file facts"
```

---

### Task 8: Prune inputs: obs state, open inodes, units

**Files:**
- Create: `tools/session_archive/inputs.py`
- Modify: `tools/session_archive/testing.py` (add `obs_for`, `SID`, `TID`, `claude_session`, `codex_rollout`)
- Test: `tools/test_session_archive_inputs.py`

**Interfaces:**
- Consumes: `decide.ObsFile`, `capture.walk_files`, `config.Source`.
- Produces: `ObsUnavailable`, `load_obs_state(command, runner=subprocess.run) -> dict[str, ObsFile]` (keyed by `os.path.realpath`), `InspectionFailed`, `open_inodes(allow=(), proc=Path("/proc"), uid=None) -> set[tuple[int, int]]` (this user's processes; raises `InspectionFailed` unless every uninspectable one's `comm` is in `allow`), `comm(pid_dir) -> str`, `tail_has_newline(path, offset) -> bool`, `SESSION_RE`, `ROLLOUT_RE`, `Unit(source, key, paths, files, thread_id=None)`, `claude_units(source) -> list[Unit]`, `codex_units(source) -> list[Unit]`; `testing.obs_for(*paths) -> dict`, `testing.SID`, `testing.TID`, `testing.claude_session(root, age_days=40, project="-p", sid=SID) -> Path` (the session's `.jsonl`), `testing.codex_rollout(root, age_days=40, tid=TID, data=...) -> Path`, `testing.uninspectable_comms() -> tuple[str, ...]`, `testing.lenient_open_inodes() -> set` (the real `/proc`, allowing what this host cannot inspect, for tests that need processes they start).

- [ ] **Step 1: Write the failing tests.** Append to `testing.py`:

```python
SID = "11111111-2222-4333-8444-555555555555"
TID = "019e0000-0000-7000-8000-000000000001"


def obs_for(*paths: Path) -> dict:
    """An obs index state in which each path is fully indexed at its current version."""
    from session_archive.decide import ObsFile
    state = {}
    for path in paths:
        info = os.stat(path)
        state[os.path.realpath(path)] = ObsFile(info.st_size, info.st_mtime_ns // 1_000_000,
                                                info.st_size, False, True, False)
    return state


def claude_session(root: Path, age_days: float = 40, project: str = "-p", sid: str = SID) -> Path:
    """A session with a transcript, a subagent transcript and a tool result, all aged."""
    write(root / project / sid / "subagents" / "agent-1.jsonl", b'{"sub":1}\n', age_days)
    write(root / project / sid / "tool-results" / "r.txt", b"result", age_days)
    return write(root / project / f"{sid}.jsonl", b'{"a":1}\n', age_days)


def codex_rollout(root: Path, age_days: float = 40, tid: str = TID,
                  data: bytes = b'{"type":"session_meta"}\n') -> Path:
    return write(root / "2026" / "01" / "01" / f"rollout-2026-01-01T00-00-00-{tid}.jsonl", data, age_days)


def uninspectable_comms() -> tuple[str, ...]:
    """comm names of this user's processes whose descriptors this host cannot read (on
    titan: systemd and (sd-pam)); tests allow them so they can watch processes they start."""
    from session_archive.inputs import InspectionFailed, open_inodes
    try:
        open_inodes()
    except InspectionFailed as failure:
        return tuple(sorted({name for _pid, name, _reason in failure.processes}))
    return ()


def lenient_open_inodes() -> set:
    from session_archive.inputs import open_inodes
    return open_inodes(allow=uninspectable_comms())
```

`tools/test_session_archive_inputs.py`:

```python
"""Prune inputs: obs's index state, open inodes and unit discovery (spec §3.2, §3.4)."""
import json
import os
import subprocess

import pytest

from session_archive import config
from session_archive.inputs import (InspectionFailed, ObsUnavailable, claude_units, codex_units,
                                    load_obs_state, open_inodes, tail_has_newline)
from session_archive.testing import SID, TID, claude_session, codex_rollout, lenient_open_inodes, write


def source(home, name):
    return next(s for s in config.sources(home) if s.name == name)


def fake_runner(stdout="", returncode=0, calls=None):
    def run(argv, **kw):
        if calls is not None:
            calls.append(argv)
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="boom")
    return run


def test_obs_state_is_keyed_by_real_path(tmp_path):
    real = write(tmp_path / "real" / "a.jsonl", b"x\n")
    (tmp_path / "alias").symlink_to(tmp_path / "real")
    payload = {"schema": 9, "files": [
        {"path": str(tmp_path / "alias" / "a.jsonl"), "size": 2, "mtime_ms": 5, "byte_offset": 2,
         "partial_tail": 0, "indexed_schema": 8, "missing_since_ms": None}]}
    calls = []
    state = load_obs_state(("python3", "obs.py"), fake_runner(json.dumps(payload), calls=calls))
    assert calls == [["python3", "obs.py", "--json", "index-state"]]
    entry = state[os.path.realpath(real)]
    assert entry.size == 2 and not entry.schema_current and not entry.missing


@pytest.mark.parametrize("runner", [fake_runner(returncode=1), fake_runner("not json"),
                                    fake_runner(json.dumps({"files": []}))])
def test_obs_failures_raise(runner):
    with pytest.raises(ObsUnavailable):
        load_obs_state(("obs",), runner)


def fake_proc(tmp_path, target):
    """A /proc with one process of this user holding `target` open, plus a non-pid entry."""
    proc = tmp_path / "proc"
    (proc / "100" / "fd").mkdir(parents=True)
    (proc / "100" / "comm").write_text("claude\n")
    (proc / "100" / "fd" / "3").symlink_to(target)
    (proc / "self").mkdir()
    return proc


def test_open_inodes_reads_this_users_processes(tmp_path):
    target = write(tmp_path / "t", b"x")
    info = os.stat(target)
    assert open_inodes(proc=fake_proc(tmp_path, target)) == {(info.st_dev, info.st_ino)}


def test_descriptor_closed_mid_scan_is_skipped(tmp_path):
    target = write(tmp_path / "t", b"x")
    proc = fake_proc(tmp_path, target)
    target.unlink()
    assert open_inodes(proc=proc) == set()


def test_other_users_are_out_of_scope(tmp_path):
    proc = fake_proc(tmp_path, write(tmp_path / "t", b"x"))
    assert open_inodes(proc=proc, uid=os.getuid() + 1) == set()


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable directories")
def test_uninspectable_process_refuses_unless_allowed(tmp_path):
    proc = fake_proc(tmp_path, write(tmp_path / "t", b"x"))
    (proc / "100" / "fd").chmod(0)
    try:
        with pytest.raises(InspectionFailed, match=r"100 \(claude\)"):
            open_inodes(proc=proc)
        assert open_inodes(allow=("claude",), proc=proc) == set()
    finally:
        (proc / "100" / "fd").chmod(0o700)


def test_real_proc_sees_our_descriptor(tmp_path):
    path = write(tmp_path / "held", b"x")
    with open(path) as handle:
        info = os.fstat(handle.fileno())
        assert (info.st_dev, info.st_ino) in lenient_open_inodes()


def test_tail_has_newline(tmp_path):
    path = write(tmp_path / "t", b"line\npartial")
    assert not tail_has_newline(path, 5)
    assert tail_has_newline(path, 0)


def test_claude_units_are_sessions_only(home):
    src = source(home, "claude")
    claude_session(src.root)
    write(src.root / "-p" / "memory" / "MEMORY.md", b"keep", 90)
    write(src.root / "-p" / "notes.jsonl", b"keep", 90)
    orphan = "99999999-2222-4333-8444-555555555555"
    write(src.root / "-p" / orphan / "tool-results" / "r.txt", b"x", 90)
    units = {u.key: u for u in claude_units(src)}
    assert set(units) == {f"-p/{SID}", f"-p/{orphan}"}
    session = units[f"-p/{SID}"]
    assert session.paths == (src.root / "-p" / f"{SID}.jsonl", src.root / "-p" / SID)
    assert sorted(session.files) == sorted([f"-p/{SID}.jsonl", f"-p/{SID}/subagents/agent-1.jsonl",
                                            f"-p/{SID}/tool-results/r.txt"])
    assert units[f"-p/{orphan}"].paths == (src.root / "-p" / orphan,)


def test_codex_units_carry_thread_ids(home):
    src = source(home, "codex")
    rollout = codex_rollout(src.root)
    write(src.root / "2026" / "01" / "01" / "notes.txt", b"x")
    (unit,) = codex_units(src)
    assert unit.thread_id == TID and unit.paths == (rollout,)
    assert unit.files == (rollout.relative_to(src.root).as_posix(),)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_inputs.py -q`
Expected: `ModuleNotFoundError: No module named 'session_archive.inputs'`.

- [ ] **Step 3: Implement** `tools/session_archive/inputs.py`:

```python
"""What prune reads: obs's index state, the inodes any process holds open, and the units
it may delete (spec §3.2, §3.4)."""
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .capture import walk_files
from .config import Source
from .decide import ObsFile

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
SESSION_RE = re.compile(rf"^{UUID}$")
ROLLOUT_RE = re.compile(rf"^rollout-.*-({UUID})\.jsonl$")


class ObsUnavailable(Exception):
    """obs could not report its index state; prune stops before deleting anything."""


def load_obs_state(command, runner=subprocess.run) -> dict[str, ObsFile]:
    """obs's per-file index state (obs-0bc168), keyed by real path."""
    argv = [*command, "--json", "index-state"]
    try:
        result = runner(argv, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ObsUnavailable(f"obs index-state could not run: {error}") from error
    if result.returncode != 0:
        raise ObsUnavailable(f"obs index-state exited {result.returncode}: {result.stderr.strip()[:500]}")
    try:
        data = json.loads(result.stdout)
        schema = data["schema"]
        return {os.path.realpath(entry["path"]): ObsFile(
                    size=entry["size"], mtime_ms=entry["mtime_ms"], byte_offset=entry["byte_offset"],
                    partial_tail=bool(entry["partial_tail"]), schema_current=entry["indexed_schema"] == schema,
                    missing=entry["missing_since_ms"] is not None)
                for entry in data["files"]}
    except (ValueError, KeyError, TypeError) as error:
        raise ObsUnavailable(f"obs index-state output does not match the contract: {error!r}") from error


class InspectionFailed(Exception):
    """Processes of this user could not be inspected; prune must not read that as "nothing is
    open" (spec §3.4). `processes` lists (pid, comm, reason), one entry per process."""

    def __init__(self, processes: list[tuple[str, str, str]]):
        self.processes = processes
        super().__init__("cannot inspect open files of: "
                         + "; ".join(f"{pid} ({name}): {reason}" for pid, name, reason in processes))


def comm(pid_dir: Path) -> str:
    try:
        return (pid_dir / "comm").read_text().strip()
    except OSError:
        return "?"


def open_inodes(allow: tuple[str, ...] = (), proc: Path = Path("/proc"), uid: int | None = None) -> set[tuple[int, int]]:
    """(device, inode) of every file held open by a process of this user. A process or
    descriptor that disappears mid-scan is skipped. Any other failure to read a process of
    this user raises InspectionFailed, unless that process's comm is in `allow`."""
    uid = os.getuid() if uid is None else uid
    held, blocked = set(), []
    for pid_dir in proc.iterdir():
        if not pid_dir.name.isdigit():
            continue
        failure = None
        try:
            if pid_dir.stat().st_uid != uid:
                continue
            entries = list((pid_dir / "fd").iterdir())
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError as error:
            entries, failure = [], error.strerror
        for entry in entries:
            try:
                info = os.stat(entry)
            except (FileNotFoundError, ProcessLookupError):
                continue
            except OSError as error:
                failure = failure or f"fd {entry.name}: {error.strerror}"
                continue
            held.add((info.st_dev, info.st_ino))
        if failure and comm(pid_dir) not in allow:
            blocked.append((pid_dir.name, comm(pid_dir), failure))
    if blocked:
        raise InspectionFailed(blocked)
    return held


def tail_has_newline(path: Path, offset: int) -> bool:
    with open(path, "rb") as handle:
        handle.seek(offset)
        return b"\n" in handle.read()


@dataclass(frozen=True)
class Unit:
    source: Source
    key: str                   # claude: "<project>/<session id>"; codex: the rollout's relpath
    paths: tuple[Path, ...]    # what the protocol moves or links
    files: tuple[str, ...]     # every regular file in the unit, relative to source.root
    thread_id: str | None = None


def claude_units(source: Source) -> list[Unit]:
    """One unit per session id: `<id>.jsonl` and the `<id>/` directory beside it. Only
    UUID-named entries are sessions; `memory/` and other project files are never units."""
    units = []
    for project in sorted(p for p in source.root.iterdir() if p.is_dir() and not p.is_symlink()):
        ids = {p.stem for p in project.glob("*.jsonl") if SESSION_RE.match(p.stem) and p.is_file()}
        ids |= {d.name for d in project.iterdir() if SESSION_RE.match(d.name) and d.is_dir() and not d.is_symlink()}
        for sid in sorted(ids):
            paths = tuple(p for p in (project / f"{sid}.jsonl", project / sid) if os.path.lexists(p))
            files = []
            for path in paths:
                members = walk_files(path) if path.is_dir() else [path]
                files += [member.relative_to(source.root).as_posix() for member in members]
            units.append(Unit(source, f"{project.name}/{sid}", paths, tuple(files)))
    return units


def codex_units(source: Source) -> list[Unit]:
    units = []
    for path in walk_files(source.root):
        match = ROLLOUT_RE.match(path.name)
        if match:
            relpath = path.relative_to(source.root).as_posix()
            units.append(Unit(source, relpath, (path,), (relpath,), match.group(1)))
    return units
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_inputs.py -q`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive/inputs.py tools/session_archive/testing.py tools/test_session_archive_inputs.py
git commit -m "feat(session-archive): prune inputs from obs, /proc and the stores"
```

---

### Task 9: Quarantine primitives

**Files:**
- Create: `tools/session_archive/quarantine.py`
- Test: `tools/test_session_archive_quarantine.py`

**Interfaces:**
- Consumes: `capture.walk_files`.
- Produces: `QUARANTINE = "session-archive-quarantine"`, `rename_noreplace(src, dst)` (raises `FileExistsError` and `FileNotFoundError` like `os.rename`), `quarantine_dir(home, run_id) -> Path`, `leftovers(homes) -> list[Path]`, `inodes(paths) -> set[tuple[int, int]]`, `release(entry, live_path, preserve: Callable[[Path], bool]) -> bool`, `remove_empty_dirs(top, stop)`.

- [ ] **Step 1: Write the failing tests** in `tools/test_session_archive_quarantine.py`:

```python
"""No-replace restore and the release rule (spec §3.4.1)."""
import os

import pytest

from session_archive.quarantine import (QUARANTINE, inodes, leftovers, quarantine_dir, release,
                                        remove_empty_dirs, rename_noreplace)
from session_archive.testing import write


def test_rename_noreplace_moves(tmp_path):
    src = write(tmp_path / "a", b"a")
    rename_noreplace(src, tmp_path / "b")
    assert (tmp_path / "b").read_bytes() == b"a" and not src.exists()


@pytest.mark.parametrize("as_dir", [False, True])
def test_rename_noreplace_refuses_existing_target(tmp_path, as_dir):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    if as_dir:
        write(src / "inner", b"s")
        write(dst / "other", b"d")
    else:
        write(src, b"s")
        write(dst, b"d")
    with pytest.raises(FileExistsError):
        rename_noreplace(src, dst)
    assert src.exists() and dst.exists()
    assert (dst / "other" if as_dir else dst).read_bytes() == b"d"


def test_rename_noreplace_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        rename_noreplace(tmp_path / "absent", tmp_path / "b")


def test_release_rule_a_same_inode(tmp_path):
    live = write(tmp_path / "live", b"x")
    entry = tmp_path / "entry"
    os.link(live, entry)
    assert release(entry, live, lambda path: pytest.fail("preserve must not run"))
    assert not entry.exists() and live.exists()


def test_release_rule_b(tmp_path):
    entry = write(tmp_path / "entry", b"x")
    assert not release(entry, tmp_path / "gone", lambda path: False)
    assert entry.exists()
    assert release(entry, tmp_path / "gone", lambda path: True)
    assert not entry.exists()


def test_release_rule_b_when_live_is_another_file(tmp_path):
    entry = write(tmp_path / "entry", b"x")
    live = write(tmp_path / "live", b"fragment")
    assert not release(entry, live, lambda path: False)
    assert entry.exists()


def test_leftovers_and_cleanup(tmp_path):
    home = tmp_path / "h"
    qdir = quarantine_dir(home, "run1")
    assert leftovers([home]) == []
    (qdir / "p" / "s").mkdir(parents=True)
    assert leftovers([home]) == []          # empty directories are not leftovers
    write(qdir / "p" / "s" / "f", b"x")
    assert leftovers([home, home]) == [home / QUARANTINE]
    (qdir / "p" / "s" / "f").unlink()
    remove_empty_dirs(qdir / "p" / "s", home / QUARANTINE)
    assert (home / QUARANTINE).is_dir() and not qdir.exists()


def test_inodes_cover_directory_members(tmp_path):
    f = write(tmp_path / "d" / "x", b"x")
    info = os.stat(f)
    assert (info.st_dev, info.st_ino) in inodes([tmp_path / "d"])
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_quarantine.py -q`
Expected: `ModuleNotFoundError: No module named 'session_archive.quarantine'`.

- [ ] **Step 3: Implement** `tools/session_archive/quarantine.py`:

```python
"""The quarantine rules of spec §3.4.1: restore never replaces, and an entry is released
only when its bytes are preserved."""
import ctypes
import os
from pathlib import Path
from typing import Callable

from .capture import walk_files

QUARANTINE = "session-archive-quarantine"
AT_FDCWD = -100
RENAME_NOREPLACE = 1
_libc = ctypes.CDLL(None, use_errno=True)


def rename_noreplace(src: Path, dst: Path) -> None:
    """renameat2(RENAME_NOREPLACE): atomic, and fails with EEXIST instead of replacing dst."""
    if _libc.renameat2(AT_FDCWD, os.fsencode(src), AT_FDCWD, os.fsencode(dst), RENAME_NOREPLACE) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), str(dst))


def quarantine_dir(home: Path, run_id: str) -> Path:
    return home / QUARANTINE / run_id


def leftovers(homes) -> list[Path]:
    """Quarantine roots holding any file; each one stops the next prune (spec §3.4.4)."""
    found = []
    for home in sorted(set(homes)):
        root = home / QUARANTINE
        if root.is_dir() and any(True for _ in walk_files(root)):
            found.append(root)
    return found


def inodes(paths) -> set[tuple[int, int]]:
    found = set()
    for path in paths:
        for member in ([path, *walk_files(path)] if path.is_dir() else [path]):
            info = os.stat(member, follow_symlinks=False)
            found.add((info.st_dev, info.st_ino))
    return found


def release(entry: Path, live_path: Path, preserve: Callable[[Path], bool]) -> bool:
    """Remove a quarantined file only when (a) its inode is still reachable at live_path or
    (b) preserve(entry) confirms the archive holds its exact bytes. False keeps it."""
    held = os.stat(entry)
    try:
        live = os.stat(live_path)
    except FileNotFoundError:
        live = None
    if live is not None and (live.st_dev, live.st_ino) == (held.st_dev, held.st_ino):
        os.unlink(entry)
        return True
    if preserve(entry):
        os.unlink(entry)
        return True
    return False


def remove_empty_dirs(top: Path, stop: Path) -> None:
    """Remove empty directories under and including top, then empty parents up to stop."""
    if top.is_dir():
        for dirpath, _dirnames, _filenames in os.walk(top, topdown=False):
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
    parent = top.parent
    while parent != stop and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_quarantine.py -q`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive/quarantine.py tools/test_session_archive_quarantine.py
git commit -m "feat(session-archive): no-replace rename and the quarantine release rule"
```

---

### Task 10: Claude deletion protocol

**Files:**
- Create: `tools/session_archive/prune.py`
- Test: `tools/test_session_archive_prune_claude.py`

**Interfaces:**
- Consumes: `capture.archived_file`, `capture_file`, `hash_file`, `mirror_path`, `stat_of`, `walk_files`; `decide.FileFacts`, `INACTIVE_NS`, `ObsFile`, `Stat`, `is_transcript`, `unit_reason`; `inputs.Unit`, `tail_has_newline`; `quarantine.*`; `manifest.MIRROR`, `Manifest`.
- Produces: `ArchiveUnreadable`, `LeftoverQuarantine`, `Hooks(after_precheck, after_quarantine, before_delete)`, `Context(archive_root, manifest, obs, held, now_ns, run_id, codex_bin="codex", codex_timeout=120, hooks=Hooks())`, `evaluate(unit, ctx, held) -> str | None`, `preserver(ctx, source, relpath) -> Callable[[Path], bool]`, `delete_claude_unit(unit, ctx) -> str`. Outcomes: `pruned`, `kept:vanished`, `kept:open`, `kept:changed`, `failed:recreated`, `failed:recapture`, `failed:release`, `failed:uninspectable` (restored).

- [ ] **Step 1: Write the failing tests** in `tools/test_session_archive_prune_claude.py`:

```python
"""Claude deletion protocol and its deletion-window cases (spec §3.4.2)."""
import os
import time

import pytest

from session_archive import config, prune
from session_archive.capture import capture_run, hash_file, mirror_path
from session_archive.inputs import InspectionFailed, claude_units
from session_archive.prune import Context, Hooks, delete_claude_unit, evaluate
from session_archive.quarantine import QUARANTINE
from session_archive.testing import SID, claude_session, lenient_open_inodes, obs_for


@pytest.fixture
def world(home, archive, manifest):
    src = next(s for s in config.sources(home) if s.name == "claude")
    jsonl = claude_session(src.root)
    capture_run(archive, manifest, [src])
    (unit,) = claude_units(src)
    transcripts = [jsonl, src.root / "-p" / SID / "subagents" / "agent-1.jsonl"]
    ctx = Context(archive, manifest, obs_for(*transcripts), lenient_open_inodes, time.time_ns(), "run1")
    assert evaluate(unit, ctx, set()) is None
    return src, unit, jsonl, ctx


def quarantined(src, name=f"{SID}.jsonl"):
    return src.home / QUARANTINE / "run1" / "-p" / SID / name


def test_eligible_unit_is_pruned(world, archive):
    src, unit, jsonl, ctx = world
    assert delete_claude_unit(unit, ctx) == "pruned"
    assert not jsonl.exists() and not (src.root / "-p" / SID).exists()
    assert not (src.home / QUARANTINE / "run1").exists()
    assert mirror_path(archive, "claude", f"-p/{SID}.jsonl").read_bytes() == b'{"a":1}\n'


def test_append_before_quarantine_is_kept_and_archived(world, archive):
    src, unit, jsonl, ctx = world
    with open(jsonl, "ab") as handle:
        handle.write(b'{"late":1}\n')
    assert delete_claude_unit(unit, ctx) == "kept:changed"
    assert jsonl.read_bytes() == b'{"a":1}\n{"late":1}\n'
    assert hash_file(mirror_path(archive, "claude", f"-p/{SID}.jsonl")) == hash_file(jsonl)


def test_open_at_settle_restores(world):
    src, unit, jsonl, ctx = world
    handles = []
    ctx.hooks = Hooks(after_quarantine=lambda u: handles.append(open(quarantined(src), "rb")))
    try:
        assert delete_claude_unit(unit, ctx) == "kept:open"
    finally:
        for handle in handles:
            handle.close()
    assert jsonl.exists() and (src.root / "-p" / SID / "tool-results" / "r.txt").exists()


def test_failed_inspection_restores(world):
    src, unit, jsonl, ctx = world

    def blind():
        raise InspectionFailed([("1", "x", "Permission denied")])

    ctx.held = blind
    assert delete_claude_unit(unit, ctx) == "failed:uninspectable"
    assert jsonl.exists() and (src.root / "-p" / SID / "tool-results" / "r.txt").exists()
    assert not (src.home / QUARANTINE / "run1").exists()


def recreate(jsonl):
    jsonl.write_bytes(b'{"fragment":1}\n')


def test_recreated_after_quarantine_keeps_both(world):
    src, unit, jsonl, ctx = world
    ctx.hooks = Hooks(after_quarantine=lambda u: recreate(jsonl))
    assert delete_claude_unit(unit, ctx) == "failed:recreated"
    assert jsonl.read_bytes() == b'{"fragment":1}\n'
    assert quarantined(src).read_bytes() == b'{"a":1}\n'


def test_recreated_with_holder_keeps_both(world):
    src, unit, jsonl, ctx = world
    handles = []

    def hook(u):
        handles.append(open(quarantined(src), "rb"))
        recreate(jsonl)

    ctx.hooks = Hooks(after_quarantine=hook)
    try:
        assert delete_claude_unit(unit, ctx) == "failed:recreated"
    finally:
        for handle in handles:
            handle.close()
    assert jsonl.read_bytes() == b'{"fragment":1}\n'
    assert quarantined(src).exists()


def test_recreated_with_change_keeps_both_and_archives_change(world, archive):
    src, unit, jsonl, ctx = world

    def hook(u):
        with open(quarantined(src), "ab") as handle:
            handle.write(b'{"late":1}\n')
        recreate(jsonl)

    ctx.hooks = Hooks(after_quarantine=hook)
    assert delete_claude_unit(unit, ctx) == "failed:recreated"
    assert jsonl.read_bytes() == b'{"fragment":1}\n'
    assert quarantined(src).read_bytes() == b'{"a":1}\n{"late":1}\n'
    assert mirror_path(archive, "claude", f"-p/{SID}.jsonl").read_bytes() == b'{"a":1}\n{"late":1}\n'


def test_capture_after_recreated_stores_fragment_as_version(world, archive, manifest):
    src, unit, jsonl, ctx = world
    ctx.hooks = Hooks(after_quarantine=lambda u: recreate(jsonl))
    delete_claude_unit(unit, ctx)
    before = hash_file(mirror_path(archive, "claude", f"-p/{SID}.jsonl"))
    report, ok = capture_run(archive, manifest, [src])
    assert ok and report["claude"]["diverged"] == 1
    assert hash_file(mirror_path(archive, "claude", f"-p/{SID}.jsonl")) == before


def test_recapture_failure_keeps_quarantine(world, monkeypatch):
    src, unit, jsonl, ctx = world

    def append(u):
        with open(quarantined(src), "ab") as handle:
            handle.write(b'{"late":1}\n')

    def refuse(*args, **kw):
        raise OSError("archive disk full")

    monkeypatch.setattr(prune, "capture_file", refuse)
    ctx.hooks = Hooks(after_quarantine=append)
    assert delete_claude_unit(unit, ctx) == "failed:recapture"
    assert quarantined(src).exists() and not jsonl.exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_prune_claude.py -q`
Expected: `ModuleNotFoundError: No module named 'session_archive.prune'`.

- [ ] **Step 3: Implement** `tools/session_archive/prune.py`:

```python
"""Prune (spec §3.4): evaluate units against the manifest and obs, then delete eligible ones
only through the quarantine protocols."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .capture import archived_file, capture_file, hash_file, mirror_path, stat_of, walk_files
from .decide import INACTIVE_NS, FileFacts, ObsFile, Stat, is_transcript, unit_reason
from .inputs import InspectionFailed, Unit, tail_has_newline
from .manifest import MIRROR, Manifest
from .quarantine import QUARANTINE, inodes, quarantine_dir, release, remove_empty_dirs, rename_noreplace


class ArchiveUnreadable(Exception):
    """An archived copy could not be read back; the run stops before deleting anything."""


class LeftoverQuarantine(Exception):
    """A quarantine holds files from an earlier run; a person looks first (spec §3.4.4)."""


def _noop(unit):
    pass


@dataclass
class Hooks:
    """Seams between protocol steps for the deletion-window tests; no-ops in production."""
    after_precheck: Callable[[Unit], None] = _noop
    after_quarantine: Callable[[Unit], None] = _noop
    before_delete: Callable[[Unit], None] = _noop


@dataclass
class Context:
    archive_root: Path
    manifest: Manifest
    obs: dict[str, ObsFile]
    held: Callable[[], set[tuple[int, int]]]   # fresh snapshot of open inodes
    now_ns: int
    run_id: str
    codex_bin: str = "codex"
    codex_timeout: float = 120
    hooks: Hooks = field(default_factory=Hooks)


def _read_back(path: Path) -> str | None:
    try:
        return hash_file(path)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ArchiveUnreadable(f"cannot read back {path}: {error}") from error


def _mirror_sha(ctx: Context, source, relpath: str) -> str | None:
    mirror = ctx.manifest.mirror(source.name, relpath)
    return mirror.sha256 if mirror else None


def _facts(source, relpath: str, ctx: Context, held) -> FileFacts:
    path = source.root / relpath
    info = os.stat(path, follow_symlinks=False)
    mirror = ctx.manifest.mirror(source.name, relpath)
    obs = ctx.obs.get(os.path.realpath(path))
    return FileFacts(
        relpath=relpath,
        live=Stat(info.st_size, info.st_mtime_ns),
        live_sha256=hash_file(path),
        mirror=mirror,
        latest=ctx.manifest.latest(source.name, relpath),
        mirror_sha256=_read_back(mirror_path(ctx.archive_root, source.name, relpath)) if mirror else None,
        transcript=is_transcript(source.kind, relpath),
        obs=obs,
        tail_has_newline=tail_has_newline(path, obs.byte_offset) if obs else False,
        open=(info.st_dev, info.st_ino) in held)


def evaluate(unit: Unit, ctx: Context, held) -> str | None:
    """The first condition the unit fails, or None. An active unit is rejected on its stat
    alone, before any hashing."""
    for relpath in unit.files:
        if ctx.now_ns - stat_of(unit.source.root / relpath).mtime_ns <= INACTIVE_NS:
            return "active"
    return unit_reason([_facts(unit.source, relpath, ctx, held) for relpath in unit.files], ctx.now_ns)


def preserver(ctx: Context, source, relpath: str) -> Callable[[Path], bool]:
    """Rule (b) for one file: true once the archive holds the entry's exact bytes, verified by
    read-back, recapturing the entry first when it does not."""
    def preserve(entry: Path) -> bool:
        try:
            sha = hash_file(entry)
            if any(v.sha256 == sha and _read_back(archived_file(ctx.archive_root, v)) == sha
                   for v in ctx.manifest.rows(source.name, relpath)):
                return True
            outcome = capture_file(ctx.archive_root, ctx.manifest, source.name, relpath, entry, force=True)
            return (outcome.version is not None and outcome.version.sha256 == sha
                    and _read_back(archived_file(ctx.archive_root, outcome.version)) == sha)
        except (OSError, ArchiveUnreadable):
            return False
    return preserve


def _restore(moved, qdir: Path, stop: Path, outcome: str) -> str:
    recreated = False
    for live, quarantined in moved:
        try:
            rename_noreplace(quarantined, live)
        except FileExistsError:
            recreated = True
    remove_empty_dirs(qdir, stop)
    return "failed:recreated" if recreated else outcome


def delete_claude_unit(unit: Unit, ctx: Context) -> str:
    """Spec §3.4.2: quarantine, settle, re-verify, recreation check, remove."""
    stop = unit.source.home / QUARANTINE
    qdir = quarantine_dir(unit.source.home, ctx.run_id) / unit.key
    qdir.mkdir(parents=True)
    moved = []
    for live in unit.paths:
        quarantined = qdir / live.name
        try:
            rename_noreplace(live, quarantined)
        except FileNotFoundError:
            return _restore(moved, qdir, stop, "kept:vanished")
        moved.append((live, quarantined))
    ctx.hooks.after_quarantine(unit)
    try:
        holders = ctx.held()
    except InspectionFailed:
        return _restore(moved, qdir, stop, "failed:uninspectable")
    if inodes([q for _, q in moved]) & holders:
        return _restore(moved, qdir, stop, "kept:open")
    project = unit.key.split("/")[0]
    present = {f"{project}/{p.relative_to(qdir).as_posix()}": p for p in walk_files(qdir)}
    changed = [rel for rel, p in sorted(present.items()) if _mirror_sha(ctx, unit.source, rel) != hash_file(p)]
    if changed:
        for rel in changed:
            if not preserver(ctx, unit.source, rel)(present[rel]):
                return "failed:recapture"
        return _restore(moved, qdir, stop, "kept:changed")
    if any(os.path.lexists(live) for live, _ in moved):
        return "failed:recreated"
    for rel, quarantined in sorted(present.items()):
        if not release(quarantined, unit.source.root / rel, preserver(ctx, unit.source, rel)):
            return "failed:release"
    remove_empty_dirs(qdir, stop)
    return "pruned"
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_prune_claude.py -q`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive/prune.py tools/test_session_archive_prune_claude.py
git commit -m "feat(session-archive): Claude deletion protocol with no-replace restore"
```

---

### Task 11: Codex deletion protocol and the stub `codex`

**Files:**
- Modify: `tools/session_archive/prune.py` (add `run_codex_delete`, `delete_codex_unit`), `tools/session_archive/testing.py` (add `STUB_CODEX`), `tools/conftest.py` (add the `stub_codex` fixture)
- Test: `tools/test_session_archive_prune_codex.py`

**Interfaces:**
- Consumes: Task 10's `Context`, `evaluate`, `preserver`, `_mirror_sha`; `quarantine.release`, `remove_empty_dirs`.
- Produces: `run_codex_delete(codex_bin, home, thread_id, timeout) -> bool`, `delete_codex_unit(unit, ctx) -> str`. Outcomes: `pruned`, `kept:busy`, `kept:vanished`, `kept:<reason>`, `failed:uninspectable`, `failed:delete`, `failed:changed`, `failed:delete-quarantined`, `failed:changed-quarantined`, `failed:writer-live-quarantined`, `failed:uninspectable-quarantined`, `failed:release`.
- The `stub_codex` fixture returns the stub's path. The stub honours `STUB_CODEX_MODE`:
  - `ok`;
  - `fail`;
  - `unlink-fail`;
  - `hang`;
  - `ignore-lock`;
  - `writer-closes`: `exec` closes its rollout at once;
  - `writer-during-delete`: `delete` leaves a detached writer holding the unlinked rollout, which appends after 0.5 s and exits after 2 s. This is the early-lock-release case.

  It also honours `STUB_CODEX_VERSION` and `STUB_CODEX_WRITER_SECONDS` (how long `exec` holds its lock and rollout, default 1). It logs argv plus `CODEX_HOME` to `$STUB_CODEX_LOG`.

The protocol's safety after `codex delete` rests on the freeze check (spec §3.4.3 step 3): no path, and no process holding the linked inode. It does not rest on how long `codex delete` holds the writer lock. The `writer-during-delete` test pins that: a delete that lets a writer in still loses nothing.

- [ ] **Step 1: Write the failing tests.** Append `STUB_CODEX` to `testing.py`:

```python
STUB_CODEX = r'''#!/usr/bin/env python3
"""A stand-in for the codex CLI with the behaviour session-archive relies on.

STUB_CODEX_MODE: ok (default), fail (exit 1, touch nothing), unlink-fail (unlink, then
exit 1), hang (sleep past any timeout), ignore-lock (resume and delete ignore the writer
lock), writer-closes (exec closes its rollout at once), writer-during-delete (delete leaves
a detached writer appending to the unlinked rollout). STUB_CODEX_LOG, when set, receives
one JSON line per call."""
import fcntl, json, os, sqlite3, sys, time, uuid
from pathlib import Path

home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
mode = os.environ.get("STUB_CODEX_MODE", "ok")
args = sys.argv[1:]
if os.environ.get("STUB_CODEX_LOG"):
    with open(os.environ["STUB_CODEX_LOG"], "a") as log:
        log.write(json.dumps({"argv": args, "codex_home": str(home)}) + "\n")


def db():
    conn = sqlite3.connect(home / "state_5.sqlite")
    conn.execute("CREATE TABLE IF NOT EXISTS threads (id TEXT PRIMARY KEY)")
    return conn


def rollouts(tid):
    return [p for d in ("sessions", "archived_sessions") for p in (home / d).rglob(f"rollout-*-{tid}.jsonl")]


def locked(tid):
    if mode == "ignore-lock":
        return False
    path = home / "thread-writer-locks" / f"{tid}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(fd)
    return False


if args == ["--version"]:
    print(os.environ.get("STUB_CODEX_VERSION", "codex-cli 0.0.0-stub"))
elif args[:1] == ["exec"] and "resume" in args:
    tid = args[args.index("resume") + 1]
    if locked(tid):
        sys.exit(f"Error: thread/resume failed: thread {tid} already has an active writer")
    sys.exit("Error: 401 Unauthorized")
elif args[:1] == ["exec"]:
    tid = str(uuid.uuid4())
    lock = home / "thread-writer-locks" / f"{tid}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock, os.O_RDWR | os.O_CREAT)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)          # a writer holds its lock while it runs
    day = home / "sessions" / "2026" / "01" / "01"
    day.mkdir(parents=True, exist_ok=True)
    rollout = open(day / f"rollout-2026-01-01T00-00-00-{tid}.jsonl", "a")
    rollout.write('{"type":"session_meta"}\n')
    rollout.flush()
    if mode == "writer-closes":
        rollout.close()
    with db() as conn:
        conn.execute("INSERT INTO threads VALUES (?)", (tid,))
    time.sleep(float(os.environ.get("STUB_CODEX_WRITER_SECONDS", "1")))
    sys.exit("Error: 401 Unauthorized")
elif args[:1] == ["archive"]:
    tid = args[1]
    (home / "archived_sessions").mkdir(exist_ok=True)
    for path in rollouts(tid):
        path.rename(home / "archived_sessions" / path.name)
    print(f"Archived session {tid}.")
elif args[:2] == ["delete", "--force"]:
    tid = args[2]
    if mode == "hang":
        time.sleep(60)
    if mode == "fail" or locked(tid):
        sys.exit("Error: failed to delete session")
    if mode == "writer-during-delete":
        handles = [open(path, "ab") for path in rollouts(tid)]
        ready_r, ready_w = os.pipe()
        if os.fork() == 0:
            devnull = os.open(os.devnull, os.O_RDWR)
            for stream in (0, 1, 2):
                os.dup2(devnull, stream)
            os.write(ready_w, b"1")
            time.sleep(0.5)
            for handle in handles:
                handle.write(b'{"resumed":1}\n')
                handle.flush()
            time.sleep(1.5)
            os._exit(0)
        os.read(ready_r, 1)
    for path in rollouts(tid):
        path.unlink()
    with db() as conn:
        conn.execute("DELETE FROM threads WHERE id = ?", (tid,))
    if mode == "unlink-fail":
        sys.exit("Error: failed to delete session")
    print(f"Deleted session {tid}.")
else:
    sys.exit(f"stub codex: unsupported arguments {args}")
'''
```

Add to `tools/conftest.py`:

```python
import os

from session_archive.testing import STUB_CODEX


@pytest.fixture
def stub_codex(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "codex"
    stub.write_text(STUB_CODEX)
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("STUB_CODEX_LOG", str(tmp_path / "codex.log"))
    return stub
```

`tools/test_session_archive_prune_codex.py`:

```python
"""Codex deletion protocol and its deletion-window cases (spec §3.4.3)."""
import fcntl
import json
import os
import time

import pytest

from session_archive import config, prune
from session_archive.capture import capture_run, hash_file, mirror_path
from session_archive.inputs import codex_units
from session_archive.prune import Context, Hooks, delete_codex_unit, evaluate
from session_archive.quarantine import QUARANTINE
from session_archive.testing import TID, codex_rollout, lenient_open_inodes, obs_for


@pytest.fixture
def world(home, archive, manifest, stub_codex):
    src = next(s for s in config.sources(home) if s.name == "codex")
    rollout = codex_rollout(src.root)
    capture_run(archive, manifest, [src])
    (unit,) = codex_units(src)
    ctx = Context(archive, manifest, obs_for(rollout), lenient_open_inodes, time.time_ns(), "run1",
                  codex_bin=str(stub_codex))
    assert evaluate(unit, ctx, set()) is None
    return src, unit, rollout, ctx


def link(src, rollout):
    return src.home / QUARANTINE / "run1" / rollout.name


def append(path, data=b'{"late":1}\n'):
    with open(path, "ab") as handle:
        handle.write(data)


def test_pruned_through_codex_delete(world, tmp_path, archive):
    src, unit, rollout, ctx = world
    assert delete_codex_unit(unit, ctx) == "pruned"
    assert not rollout.exists() and not (src.home / QUARANTINE / "run1").exists()
    calls = [json.loads(line) for line in (tmp_path / "codex.log").read_text().splitlines()]
    assert calls == [{"argv": ["delete", "--force", TID], "codex_home": str(src.home)}]
    assert mirror_path(archive, "codex", unit.files[0]).exists()


def test_held_writer_lock_is_busy(world):
    src, unit, rollout, ctx = world
    lock = src.home / "thread-writer-locks" / f"{TID}.lock"
    lock.parent.mkdir(exist_ok=True)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert delete_codex_unit(unit, ctx) == "kept:busy"
    finally:
        os.close(fd)
    assert rollout.exists()


def test_append_between_lock_and_delete_is_archived(world, archive):
    src, unit, rollout, ctx = world
    ctx.hooks = Hooks(before_delete=lambda u: append(rollout))
    assert delete_codex_unit(unit, ctx) == "failed:changed"
    assert mirror_path(archive, "codex", unit.files[0]).read_bytes().endswith(b'{"late":1}\n')
    assert not link(src, rollout).exists()


def test_append_then_unlink_then_nonzero_exit(world, archive, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setenv("STUB_CODEX_MODE", "unlink-fail")
    ctx.hooks = Hooks(before_delete=lambda u: append(rollout))
    assert delete_codex_unit(unit, ctx) == "failed:delete"
    assert not rollout.exists()
    assert mirror_path(archive, "codex", unit.files[0]).read_bytes().endswith(b'{"late":1}\n')
    assert not link(src, rollout).exists()


def test_unlink_fail_with_failed_recapture_keeps_link(world, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setenv("STUB_CODEX_MODE", "unlink-fail")

    def refuse(*args, **kw):
        raise OSError("archive disk full")

    monkeypatch.setattr(prune, "capture_file", refuse)
    ctx.hooks = Hooks(before_delete=lambda u: append(rollout))
    assert delete_codex_unit(unit, ctx) == "failed:delete-quarantined"
    assert link(src, rollout).read_bytes().endswith(b'{"late":1}\n')


def test_nonzero_exit_without_unlink_releases_link(world, monkeypatch):
    src, unit, rollout, ctx = world
    before = hash_file(rollout)
    monkeypatch.setenv("STUB_CODEX_MODE", "fail")
    assert delete_codex_unit(unit, ctx) == "failed:delete"
    assert hash_file(rollout) == before and not link(src, rollout).exists()


def test_writer_alive_after_delete_keeps_link(world, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setenv("STUB_CODEX_MODE", "writer-during-delete")
    assert delete_codex_unit(unit, ctx) == "failed:writer-live-quarantined"
    time.sleep(2.5)                                  # the writer appends, then exits
    assert link(src, rollout).read_bytes().endswith(b'{"resumed":1}\n')


def test_timeout_is_a_failed_delete(world, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setenv("STUB_CODEX_MODE", "hang")
    ctx.codex_timeout = 1
    assert delete_codex_unit(unit, ctx) == "failed:delete"
    assert rollout.exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_prune_codex.py -q`
Expected: `ImportError: cannot import name 'delete_codex_unit'`.

- [ ] **Step 3: Implement.** Add `import fcntl` and `import subprocess` to the imports of `prune.py`, then append:

```python
def run_codex_delete(codex_bin: str, home: Path, thread_id: str, timeout: float) -> bool:
    """True only for exit 0 within the timeout; the caller also checks the rollout is gone."""
    try:
        result = subprocess.run([codex_bin, "delete", "--force", thread_id],
                                env={**os.environ, "CODEX_HOME": str(home)}, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def delete_codex_unit(unit: Unit, ctx: Context) -> str:
    """Spec §3.4.3: lock and link, delete, freeze check, re-verify, release."""
    rollout, relpath, home = unit.paths[0], unit.files[0], unit.source.home
    stop = home / QUARANTINE
    qdir = quarantine_dir(home, ctx.run_id)
    link = qdir / rollout.name
    lock_path = home / "thread-writer-locks" / f"{unit.thread_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "kept:busy"
        if not os.path.lexists(rollout):
            return "kept:vanished"
        try:
            reason = evaluate(unit, ctx, ctx.held())
        except InspectionFailed:
            return "failed:uninspectable"
        if reason:
            return f"kept:{reason}"
        qdir.mkdir(parents=True, exist_ok=True)
        os.link(rollout, link)
    finally:
        os.close(fd)
    ctx.hooks.before_delete(unit)
    deleted = run_codex_delete(ctx.codex_bin, home, unit.thread_id, ctx.codex_timeout)
    if not deleted or os.path.lexists(rollout):
        outcome = "failed:delete"
    else:
        # Freeze check: no path is left, so only an open descriptor could still write.
        try:
            holders = ctx.held()
        except InspectionFailed:
            return "failed:uninspectable-quarantined"
        if inodes([link]) & holders:
            return "failed:writer-live-quarantined"
        outcome = "failed:changed" if hash_file(link) != _mirror_sha(ctx, unit.source, relpath) else "pruned"
    if not release(link, rollout, preserver(ctx, unit.source, relpath)):
        return "failed:release" if outcome == "pruned" else f"{outcome}-quarantined"
    remove_empty_dirs(qdir, stop)
    return outcome
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_prune_codex.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive tools/conftest.py tools/test_session_archive_prune_codex.py
git commit -m "feat(session-archive): Codex deletion protocol behind the writer lock"
```

---

### Task 12: `probe-codex`

**Files:**
- Create: `tools/session_archive/probe.py`
- Modify: `tools/session_archive/cli.py` (add `CODEX = "codex"`, `cmd_probe_codex`)
- Test: `tools/test_session_archive_probe.py`

**Interfaces:**
- Consumes: `inputs.ROLLOUT_RE`, `inputs.open_inodes`, `inputs.InspectionFailed`; `Manifest.record_probe`.
- Produces: `CodexUnavailable`, `codex_version(codex_bin) -> str`, `ProbeResult(version, checks)` with `.passed`, `probe_codex(codex_bin, workdir, held) -> ProbeResult`, where `held` is the same open-inode callable prune uses. The check keys:
  - `thread_created`;
  - `writer_holds_lock` and `writer_holds_rollout_open`, both sampled while `exec` is alive; they are the evidence the freeze check rests on;
  - `resume_refused_while_locked`;
  - `delete_refused_while_locked`;
  - `archive_moved`;
  - `archived_delete_removed_file`;
  - `archived_delete_removed_row`.

  Also `cli.CODEX` and `cli.cmd_probe_codex`.

- [ ] **Step 1: Write the failing tests** in `tools/test_session_archive_probe.py`:

```python
"""probe-codex checks the Codex behaviour the protocol relies on (spec §3.4.3, §5)."""
import json

from session_archive.manifest import Manifest
from session_archive.probe import codex_version, probe_codex
from session_archive.testing import lenient_open_inodes, run_tool, uninspectable_comms, write_config


def test_probe_passes_against_conforming_codex(stub_codex, tmp_path):
    result = probe_codex(str(stub_codex), tmp_path / "work", lenient_open_inodes)
    assert result.passed, result.checks
    assert result.version == "codex-cli 0.0.0-stub"


def test_probe_fails_when_lock_is_ignored(stub_codex, tmp_path, monkeypatch):
    monkeypatch.setenv("STUB_CODEX_MODE", "ignore-lock")
    result = probe_codex(str(stub_codex), tmp_path / "work", lenient_open_inodes)
    assert not result.passed
    assert result.checks["resume_refused_while_locked"] is False
    assert result.checks["delete_refused_while_locked"] is False


def test_probe_fails_when_writer_does_not_hold_its_rollout(stub_codex, tmp_path, monkeypatch):
    monkeypatch.setenv("STUB_CODEX_MODE", "writer-closes")
    result = probe_codex(str(stub_codex), tmp_path / "work", lenient_open_inodes)
    assert not result.passed
    assert result.checks["writer_holds_lock"] is True
    assert result.checks["writer_holds_rollout_open"] is False


def test_codex_version(stub_codex, monkeypatch):
    monkeypatch.setenv("STUB_CODEX_VERSION", "codex-cli 9.9.9")
    assert codex_version(str(stub_codex)) == "codex-cli 9.9.9"


def test_probe_command_records_passing_version(home, archive, stub_codex):
    write_config(home, archive, uninspectable_ok=uninspectable_comms())
    result = run_tool("probe-codex", home=home)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["passed"] is True
    opened = Manifest.open(archive)
    assert opened.probe_passed("codex-cli 0.0.0-stub")
    opened.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_probe.py -q`
Expected: `ModuleNotFoundError: No module named 'session_archive.probe'`.

- [ ] **Step 3: Implement** `tools/session_archive/probe.py`:

```python
"""probe-codex: check, in a throwaway CODEX_HOME, the Codex behaviour the deletion protocol
relies on (spec §3.4.3, §5). prune --apply deletes Codex units only on a version that passed."""
import fcntl
import os
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .inputs import ROLLOUT_RE

PROMPT = "reply ok"


class CodexUnavailable(Exception):
    pass


@dataclass(frozen=True)
class ProbeResult:
    version: str
    checks: dict

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())


def codex_version(codex_bin: str) -> str:
    try:
        result = subprocess.run([codex_bin, "--version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CodexUnavailable(f"{codex_bin} --version: {error}") from error
    if result.returncode != 0:
        raise CodexUnavailable(f"{codex_bin} --version exited {result.returncode}")
    return result.stdout.strip()


def _thread_rows(db: Path, thread_id: str) -> int | None:
    if not db.is_file():
        return None
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT COUNT(*) FROM threads WHERE id = ?", (thread_id,)).fetchone()[0]
    finally:
        conn.close()


def _lock_held(path: Path) -> bool:
    try:
        fd = os.open(path, os.O_RDWR)
    except FileNotFoundError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(fd)
    return False


def _await_rollout(home: Path, writer: subprocess.Popen, timeout: float = 60) -> Path | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = sorted((home / "sessions").rglob("rollout-*.jsonl")) if (home / "sessions").is_dir() else []
        if found or writer.poll() is not None:
            return found[0] if len(found) == 1 and ROLLOUT_RE.match(found[0].name) else None
        time.sleep(0.05)
    return None


def probe_codex(codex_bin: str, workdir: Path, held) -> ProbeResult:
    home, cwd = workdir / "home", workdir / "cwd"
    home.mkdir(parents=True)
    cwd.mkdir()
    (home / "config.toml").touch()
    env = {**os.environ, "CODEX_HOME": str(home)}

    def codex(*args):
        return subprocess.run([codex_bin, *args], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=180)

    version = codex_version(codex_bin)
    # exec fails at auth, but first creates the thread and writes it while it retries.
    writer = subprocess.Popen([codex_bin, "exec", "--skip-git-repo-check", PROMPT], cwd=cwd, env=env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        rollout = _await_rollout(home, writer)
        checks = {"thread_created": rollout is not None}
        if rollout is not None:
            thread_id = ROLLOUT_RE.match(rollout.name).group(1)
            time.sleep(0.2)
            info = os.stat(rollout)
            lock_held = _lock_held(home / "thread-writer-locks" / f"{thread_id}.lock")
            rollout_open = (info.st_dev, info.st_ino) in held()
            alive = writer.poll() is None
            checks["writer_holds_lock"] = alive and lock_held
            checks["writer_holds_rollout_open"] = alive and rollout_open
    finally:
        try:
            writer.wait(timeout=180)
        except subprocess.TimeoutExpired:
            writer.kill()
            writer.wait()
    if rollout is None:
        return ProbeResult(version, checks)
    lock = home / "thread-writer-locks" / f"{thread_id}.lock"
    lock.parent.mkdir(exist_ok=True)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        resumed = codex("exec", "--skip-git-repo-check", "resume", thread_id, PROMPT)
        checks["resume_refused_while_locked"] = "already has an active writer" in resumed.stdout + resumed.stderr
        deleted = codex("delete", "--force", thread_id)
        checks["delete_refused_while_locked"] = deleted.returncode != 0 and rollout.exists()
    finally:
        os.close(fd)
    codex("archive", thread_id)
    archived = list((home / "archived_sessions").rglob(f"*{thread_id}.jsonl"))
    checks["archive_moved"] = len(archived) == 1 and not rollout.exists()
    deleted = codex("delete", "--force", thread_id)
    checks["archived_delete_removed_file"] = deleted.returncode == 0 and not any(home.rglob(f"*{thread_id}.jsonl"))
    checks["archived_delete_removed_row"] = _thread_rows(home / "state_5.sqlite", thread_id) == 0
    return ProbeResult(version, checks)
```

In `cli.py`, add `import tempfile`, `from . import inputs, probe`, `CODEX = "codex"`, and:

```python
def cmd_probe_codex(cfg, table, args) -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="session-archive-probe-") as workdir:
            result = probe.probe_codex(CODEX, Path(workdir), lambda: inputs.open_inodes(allow=cfg.uninspectable_ok))
    except (probe.CodexUnavailable, inputs.InspectionFailed) as error:
        print(f"session-archive: {error}", file=sys.stderr)
        return 1
    if result.passed:
        manifest = Manifest.open(cfg.archive_root)
        try:
            manifest.record_probe(result.version, utc_now())
        finally:
            manifest.close()
    print(json.dumps({"version": result.version, "checks": result.checks, "passed": result.passed},
                     sort_keys=True))
    return 0 if result.passed else 1


COMMANDS = {"capture": cmd_capture, "promote": cmd_promote, "probe-codex": cmd_probe_codex}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_probe.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive tools/test_session_archive_probe.py
git commit -m "feat(session-archive): probe-codex records the Codex versions that pass"
```

---

### Task 13: Prune run and the `prune` command

**Files:**
- Modify: `tools/session_archive/prune.py` (add `repair_archive`, `prune_run`), `tools/session_archive/cli.py` (add `cmd_prune`)
- Test: `tools/test_session_archive_prune_run.py`

**Interfaces:**
- Consumes: everything from Tasks 7–12; `inputs.claude_units`, `codex_units`, `load_obs_state`, `open_inodes`, `ObsUnavailable`, `InspectionFailed`; `quarantine.leftovers`; `probe.codex_version`, `CodexUnavailable`.
- Produces: `repair_archive(unit, ctx) -> str` (`kept:archive-repaired` or `failed:archive-repair`), and `prune_run(ctx, sources, apply, codex_probed, report) -> bool`, which fills the caller's `report` as it goes, so an error still leaves what was done. The report is `{source: {"totals": {outcome: n}, "units": [{"unit", "outcome"}]}}`, listing every unit except `kept:active` ones, plus `errors` when phase two stopped.
  - A live file prune cannot read is `failed:unreadable`.
  - An unexpected `OSError` in phase two records `failed:io` for that unit, and `kept:stopped` for every unit after it.
  - `cli.cmd_prune` records every expected failure as a failed run with the partial report: obs, inspection, read-back, leftovers, Codex, and any `OSError`. When `--apply` meets an unprobed Codex version, the report carries `codex_gate`.

- [ ] **Step 1: Write the failing tests** in `tools/test_session_archive_prune_run.py`:

```python
"""The prune run: two phases, dry run, gates, leftovers, repair and divergence (spec §3.4)."""
import json
import os
import sys
import time

import pytest

from session_archive import config, prune
from session_archive.capture import capture_run, hash_file, mirror_path, promote
from session_archive.manifest import Manifest
from session_archive.prune import Context, LeftoverQuarantine, prune_run
from session_archive.quarantine import QUARANTINE
from session_archive.testing import (SID, age, claude_session, codex_rollout, lenient_open_inodes, obs_for,
                                     run_tool, uninspectable_comms, write, write_config)

OTHER = "22222222-2222-4333-8444-555555555555"


@pytest.fixture
def table(home):
    return config.sources(home)


def src(table, name):
    return next(s for s in table if s.name == name)


def ctx_for(archive, manifest, paths, codex_bin="codex"):
    return Context(archive, manifest, obs_for(*paths), lenient_open_inodes, time.time_ns(), "run1",
                   codex_bin=codex_bin)


def run_prune(ctx, table, apply, codex_probed=True):
    report = {}
    ok = prune_run(ctx, table, apply, codex_probed, report)
    return report, ok


def transcripts(root, sid=SID):
    return [root / "-p" / f"{sid}.jsonl", root / "-p" / sid / "subagents" / "agent-1.jsonl"]


def test_dry_run_writes_nothing(table, archive, manifest):
    claude = src(table, "claude")
    jsonl = claude_session(claude.root)
    capture_run(archive, manifest, table)
    report, ok = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, False)
    assert ok and report["claude"]["totals"] == {"eligible": 1}
    assert jsonl.exists() and not (claude.home / QUARANTINE).exists()


def test_apply_prunes_only_eligible(table, archive, manifest):
    claude = src(table, "claude")
    claude_session(claude.root)
    claude_session(claude.root, age_days=1, sid=OTHER)
    capture_run(archive, manifest, table)
    paths = transcripts(claude.root) + transcripts(claude.root, OTHER)
    report, ok = run_prune(ctx_for(archive, manifest, paths), table, True)
    assert ok
    assert report["claude"]["totals"] == {"pruned": 1, "kept:active": 1}
    assert report["claude"]["units"] == [{"unit": f"-p/{SID}", "outcome": "pruned"}]
    assert (claude.root / "-p" / f"{OTHER}.jsonl").exists()


def test_unindexed_is_kept_with_reason(table, archive, manifest):
    claude_session(src(table, "claude").root)
    capture_run(archive, manifest, table)
    report, _ = run_prune(ctx_for(archive, manifest, []), table, True)
    assert report["claude"]["totals"] == {"kept:unindexed": 1}


def test_leftover_quarantine_refuses(table, archive, manifest):
    write(src(table, "claude").home / QUARANTINE / "old" / "f", b"x")
    with pytest.raises(LeftoverQuarantine):
        run_prune(ctx_for(archive, manifest, []), table, True)


def test_damaged_mirror_is_repaired_only_with_apply(table, archive, manifest):
    claude = src(table, "claude")
    claude_session(claude.root)
    capture_run(archive, manifest, table)
    mirrored = mirror_path(archive, "claude", f"-p/{SID}.jsonl")
    mirrored.write_bytes(b"{")
    report, _ = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, False)
    assert report["claude"]["totals"] == {"kept:archive-damaged": 1}
    assert mirrored.read_bytes() == b"{"
    report, ok = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, True)
    assert ok and report["claude"]["totals"] == {"kept:archive-repaired": 1}
    assert hash_file(mirrored) == manifest.mirror("claude", f"-p/{SID}.jsonl").sha256


def test_diverged_file_stays_until_promoted(table, archive, manifest):
    claude = src(table, "claude")
    jsonl = claude_session(claude.root)
    capture_run(archive, manifest, table)
    jsonl.write_bytes(b'{"rewritten":1}\n')
    age(jsonl, 40)
    capture_run(archive, manifest, table)
    report, _ = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, True)
    assert report["claude"]["totals"] == {"kept:diverged": 1} and jsonl.exists()
    old = manifest.mirror("claude", f"-p/{SID}.jsonl")
    promote(archive, manifest, "claude", f"-p/{SID}.jsonl")
    report, ok = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, True)
    assert ok and report["claude"]["totals"] == {"pruned": 1}
    assert any(v.sha256 == old.sha256 and v.location.startswith("versions/")
               for v in manifest.rows("claude", f"-p/{SID}.jsonl"))


def test_unprobed_codex_is_kept_and_fails_the_run(table, archive, manifest, stub_codex):
    codex = src(table, "codex")
    rollout = codex_rollout(codex.root)
    capture_run(archive, manifest, table)
    report, ok = run_prune(ctx_for(archive, manifest, [rollout], str(stub_codex)), table, True, codex_probed=False)
    assert not ok and report["codex"]["totals"] == {"kept:codex-unprobed": 1}
    assert rollout.exists()


def test_deferred_sources_are_not_pruned(table, archive, manifest):
    rollout = codex_rollout(src(table, "codex-archived").root)
    capture_run(archive, manifest, table)
    report, _ = run_prune(ctx_for(archive, manifest, [rollout]), table, True)
    assert "codex-archived" not in report and rollout.exists()


def fake_obs(tmp_path, payload=None, exit_code=0):
    script = tmp_path / "fake_obs.py"
    script.write_text("import json, sys\n"
                      f"print(json.dumps({payload!r}))\n"
                      f"sys.exit({exit_code})\n")
    return (sys.executable, str(script))


def test_prune_command_dry_run_and_obs_failure(home, archive, tmp_path, stub_codex):
    claude_session(home / ".claude" / "projects")
    write_config(home, archive, fake_obs(tmp_path, {"schema": 1, "files": []}), uninspectable_comms())
    assert run_tool("capture", home=home).returncode == 0
    result = run_tool("prune", home=home)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["claude"]["totals"] == {"kept:unindexed": 1}
    write_config(home, archive, fake_obs(tmp_path, {}, exit_code=3), uninspectable_comms())
    result = run_tool("prune", "--apply", home=home)
    assert result.returncode == 1 and "obs index-state exited 3" in json.loads(result.stdout)["error"]
    opened = Manifest.open(archive)
    assert opened.last_run("prune").mode == "apply" and not opened.last_run("prune").ok
    opened.close()


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable files")
def test_unreadable_transcript_fails_the_run(table, archive, manifest):
    claude = src(table, "claude")
    jsonl = claude_session(claude.root)
    capture_run(archive, manifest, table)
    jsonl.chmod(0)
    try:
        report, ok = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, False)
    finally:
        jsonl.chmod(0o600)
    assert not ok and report["claude"]["totals"] == {"failed:unreadable": 1}


def test_io_error_stops_phase_two_and_keeps_the_report(table, archive, manifest, monkeypatch):
    claude = src(table, "claude")
    claude_session(claude.root)
    claude_session(claude.root, sid=OTHER)
    capture_run(archive, manifest, table)

    def broken(unit, ctx):
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(prune, "delete_claude_unit", broken)
    report = {}
    paths = transcripts(claude.root) + transcripts(claude.root, OTHER)
    assert not prune_run(ctx_for(archive, manifest, paths), table, True, True, report)
    assert report["claude"]["totals"] == {"failed:io": 1, "kept:stopped": 1}
    assert "Input/output error" in report["errors"][0]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable files")
def test_filesystem_failure_is_recorded_and_status_turns_red(home, archive, tmp_path):
    jsonl = claude_session(home / ".claude" / "projects")
    write_config(home, archive, fake_obs(tmp_path, {"schema": 1, "files": []}), uninspectable_comms())
    assert run_tool("capture", home=home).returncode == 0
    assert run_tool("prune", home=home).returncode == 0
    (home / ".claude" / "projects" / "-p").chmod(0)
    try:
        result = run_tool("prune", home=home)
    finally:
        (home / ".claude" / "projects" / "-p").chmod(0o700)
    assert result.returncode == 1 and "PermissionError" in json.loads(result.stdout)["error"]
    assert run_tool("status", home=home).returncode == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_prune_run.py -q`
Expected: `ImportError: cannot import name 'prune_run'`.

- [ ] **Step 3: Implement.** In `prune.py`, change the inputs import to `from .inputs import InspectionFailed, Unit, claude_units, codex_units, tail_has_newline` and the quarantine import to also import `leftovers`, then append:

```python
def repair_archive(unit: Unit, ctx: Context) -> str:
    """Recapture every file whose mirrored copy no longer reads back to its recorded hash."""
    for relpath in unit.files:
        mirror = ctx.manifest.mirror(unit.source.name, relpath)
        mirrored = mirror_path(ctx.archive_root, unit.source.name, relpath)
        if mirror is None or _read_back(mirrored) == mirror.sha256:
            continue
        try:
            outcome = capture_file(ctx.archive_root, ctx.manifest, unit.source.name, relpath,
                                   unit.source.root / relpath, force=True)
        except OSError:
            return "failed:archive-repair"
        if outcome.version is None or outcome.version.location != MIRROR or _read_back(mirrored) != mirror.sha256:
            return "failed:archive-repair"
    return "kept:archive-repaired"


def _precheck(unit: Unit, ctx: Context, held) -> str | None:
    try:
        return evaluate(unit, ctx, held)
    except FileNotFoundError:
        return "vanished"
    except OSError:
        return "unreadable"


def _decide(unit: Unit, reason: str | None, ctx: Context, apply: bool, codex_probed: bool) -> str:
    if reason == "unreadable":
        return "failed:unreadable"
    if reason == "archive-damaged":
        return repair_archive(unit, ctx) if apply else "kept:archive-damaged"
    if reason:
        return f"kept:{reason}"
    if not apply:
        return "eligible"
    if unit.source.kind == "codex" and not codex_probed:
        return "kept:codex-unprobed"
    ctx.hooks.after_precheck(unit)
    return delete_claude_unit(unit, ctx) if unit.source.kind == "claude" else delete_codex_unit(unit, ctx)


def prune_run(ctx: Context, sources, apply: bool, codex_probed: bool, report: dict) -> bool:
    """Fill `report` as the run goes, so a caller that catches an error keeps what was done.
    Phase one pre-checks every unit, reading the archive back, before anything is deleted:
    ArchiveUnreadable, InspectionFailed and unit discovery errors stop the run there. Phase
    two applies the protocols; an unexpected OSError stops it, and later units are kept."""
    left = leftovers([source.home for source in sources])
    if left:
        raise LeftoverQuarantine("quarantine not empty: " + ", ".join(str(path) for path in left))
    pruned = [source for source in sources if source.pruned]
    held = ctx.held()
    plan = [(unit, _precheck(unit, ctx, held))
            for source in pruned
            for unit in (claude_units(source) if source.kind == "claude" else codex_units(source))]
    for source in pruned:
        report[source.name] = {"totals": {}, "units": []}
    ok, stopped = True, False
    for unit, reason in plan:
        if stopped:
            outcome = "kept:stopped"
        else:
            try:
                outcome = _decide(unit, reason, ctx, apply, codex_probed)
            except OSError as error:
                outcome, stopped = "failed:io", True
                report.setdefault("errors", []).append(f"{unit.source.name}/{unit.key}: {error}")
        if outcome.startswith("failed") or outcome == "kept:codex-unprobed":
            ok = False
        entry = report[unit.source.name]
        entry["totals"][outcome] = entry["totals"].get(outcome, 0) + 1
        if outcome != "kept:active":
            entry["units"].append({"unit": unit.key, "outcome": outcome})
    return ok
```

In `cli.py`, add `import time`, `from . import prune`, and:

```python
def cmd_prune(cfg, table, args) -> int:
    manifest = Manifest.open(cfg.archive_root)
    run_id, started = uuid.uuid4().hex, utc_now()
    report = {}
    try:
        try:
            codex_probed = (not args.apply) or manifest.probe_passed(probe.codex_version(CODEX))
            ctx = prune.Context(cfg.archive_root, manifest, inputs.load_obs_state(cfg.obs_command),
                                lambda: inputs.open_inodes(allow=cfg.uninspectable_ok), time.time_ns(),
                                run_id, codex_bin=CODEX)
            ok = prune.prune_run(ctx, table, args.apply, codex_probed, report)
            if not codex_probed:
                report["codex_gate"] = "the installed codex has not passed probe-codex; run `session-archive probe-codex`"
        except (inputs.ObsUnavailable, inputs.InspectionFailed, prune.ArchiveUnreadable,
                prune.LeftoverQuarantine, probe.CodexUnavailable, OSError) as error:
            report["error"] = f"{type(error).__name__}: {error}"
            ok = False
        manifest.record_run(Run(run_id, "prune", "apply" if args.apply else "dry-run", started, utc_now(), ok, report))
    finally:
        manifest.close()
    print(json.dumps(report, sort_keys=True))
    return 0 if ok else 1


COMMANDS = {"capture": cmd_capture, "promote": cmd_promote, "probe-codex": cmd_probe_codex,
            "prune": cmd_prune}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_prune_run.py -q`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive tools/test_session_archive_prune_run.py
git commit -m "feat(session-archive): two-phase prune run and prune command"
```

---

### Task 14: `status`

**Files:**
- Create: `tools/session_archive/status.py`
- Modify: `tools/session_archive/cli.py` (add `cmd_status`)
- Test: `tools/test_session_archive_status.py`

**Interfaces:**
- Consumes: `Manifest.last_run`, `diverged`, `total_size`; `quarantine.leftovers`.
- Produces: `STALE = timedelta(hours=48)`, `status_report(manifest, homes, now: datetime) -> tuple[dict, bool]`, `cli.cmd_status`. `status` does not take the archive lock.

- [ ] **Step 1: Write the failing tests** in `tools/test_session_archive_status.py`:

```python
"""status: fresh capture, healthy prune, empty quarantines (spec §3.5, §3.4.4)."""
import fcntl
import json
import os
from datetime import datetime, timedelta, timezone

from session_archive.capture import capture_file
from session_archive.manifest import Run
from session_archive.quarantine import QUARANTINE
from session_archive.status import status_report
from session_archive.testing import run_tool, write, write_config

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def stamp(delta):
    return (NOW - delta).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def run(manifest, kind, ago, ok=True, run_id=None):
    manifest.record_run(Run(run_id or f"{kind}-{ago}", kind, "apply", stamp(ago), stamp(ago), ok, {}))


def test_no_capture_is_unhealthy(manifest, tmp_path):
    report, ok = status_report(manifest, [tmp_path], NOW)
    assert not ok and report["capture"] is None


def test_fresh_capture_is_healthy(manifest, tmp_path):
    run(manifest, "capture", timedelta(hours=3))
    report, ok = status_report(manifest, [tmp_path], NOW)
    assert ok and report["capture"]["finished_at"] == stamp(timedelta(hours=3))


def test_stale_capture_failed_prune_and_quarantine_are_unhealthy(manifest, tmp_path):
    run(manifest, "capture", timedelta(hours=49))
    assert not status_report(manifest, [tmp_path], NOW)[1]
    run(manifest, "capture", timedelta(hours=1))
    run(manifest, "prune", timedelta(hours=2), ok=False)
    assert not status_report(manifest, [tmp_path], NOW)[1]
    run(manifest, "prune", timedelta(minutes=30))
    assert status_report(manifest, [tmp_path], NOW)[1]
    write(tmp_path / QUARANTINE / "r" / "f", b"x")
    report, ok = status_report(manifest, [tmp_path], NOW)
    assert not ok and report["quarantines"] == [str(tmp_path / QUARANTINE)]


def test_diverged_files_are_listed(manifest, archive, tmp_path):
    src = write(tmp_path / "live" / "p.jsonl", b"one\n")
    capture_file(archive, manifest, "claude", "p.jsonl", src)
    src.write_bytes(b"x")
    capture_file(archive, manifest, "claude", "p.jsonl", src)
    report, _ = status_report(manifest, [tmp_path], NOW)
    assert report["diverged"] == ["claude/p.jsonl"] and report["archive_bytes"] == 5


def test_status_command_ignores_the_lock(home, archive):
    write_config(home, archive)
    fd = os.open(archive / ".lock", os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        result = run_tool("status", home=home)
    finally:
        os.close(fd)
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_status.py -q`
Expected: `ModuleNotFoundError: No module named 'session_archive.status'`.

- [ ] **Step 3: Implement** `tools/session_archive/status.py`:

```python
"""status: one JSON object on archive health; unhealthy exits 1 (spec §3.5)."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .manifest import Manifest
from .quarantine import leftovers

STALE = timedelta(hours=48)


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def status_report(manifest: Manifest, homes, now: datetime) -> tuple[dict, bool]:
    capture = manifest.last_run("capture", ok_only=True)
    prune = manifest.last_run("prune")
    quarantines = [str(path) for path in leftovers(homes)]
    fresh = capture is not None and now - _parse(capture.finished_at) <= STALE
    ok = fresh and (prune is None or prune.ok) and not quarantines
    report = {
        "capture": asdict(capture) if capture else None,
        "prune": asdict(prune) if prune else None,
        "archive_bytes": manifest.total_size(),
        "diverged": [f"{v.source}/{v.relpath}" for v in manifest.diverged()],
        "quarantines": quarantines,
        "ok": ok,
    }
    return report, ok
```

In `cli.py`, add `from datetime import datetime, timezone`, `from . import status`, and:

```python
def cmd_status(cfg, table, args) -> int:
    manifest = Manifest.open(cfg.archive_root)
    try:
        report, ok = status.status_report(manifest, [source.home for source in table],
                                          datetime.now(timezone.utc))
    finally:
        manifest.close()
    print(json.dumps(report, sort_keys=True))
    return 0 if ok else 1


COMMANDS = {"capture": cmd_capture, "promote": cmd_promote, "probe-codex": cmd_probe_codex,
            "prune": cmd_prune, "status": cmd_status}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_status.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add tools/session_archive tools/test_session_archive_status.py
git commit -m "feat(session-archive): status reports capture age, prune health and leftovers"
```

---

### Task 15: Units, links and README

**Files:**
- Create: `systemd/user/session-archive-capture.service`, `systemd/user/session-archive-capture.timer`, `systemd/user/session-archive-prune.service`, `systemd/user/session-archive-prune.timer`
- Modify: `links.toml` (`[required]`), `README.md` (Layout)
- Test: `tools/test_session_archive_units.py`

**Interfaces:**
- Consumes: the `tools/session-archive` subcommands.
- Produces: four linked unit files. The prune service runs a dry run until Task 17 switches it to `--apply`.

- [ ] **Step 1: Write the failing test** in `tools/test_session_archive_units.py`:

```python
"""The units call the tool with PATH set, on the spec's schedule, and links.toml links them."""
import configparser
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "systemd" / "user"


def unit(name):
    parser = configparser.ConfigParser(strict=False, interpolation=None, delimiters=("=",))
    parser.optionxform = str
    parser.read(UNITS / name)
    return parser


@pytest.mark.parametrize("name, command", [("capture", "capture"), ("prune", "prune")])
def test_service_runs_tool_with_path(name, command):
    service = unit(f"session-archive-{name}.service")["Service"]
    assert service["Type"] == "oneshot"
    assert service["ExecStart"] == f"/usr/bin/python3 %h/d/tack/tools/session-archive {command}"
    assert service["Environment"] == "PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin"


@pytest.mark.parametrize("name, calendar", [("capture", "*-*-* 04:00:00"), ("prune", "*-*-01 05:00:00")])
def test_timer_schedule(name, calendar):
    timer = unit(f"session-archive-{name}.timer")["Timer"]
    assert timer["OnCalendar"] == calendar and timer["Persistent"] == "true"


def test_units_are_linked():
    required = tomllib.loads((ROOT / "links.toml").read_text())["required"]
    for path in sorted(UNITS.glob("session-archive-*")):
        assert required[f"~/.config/systemd/user/{path.name}"] == f"systemd/user/{path.name}"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run -q --with pytest pytest tools/test_session_archive_units.py -q`
Expected: FAIL, a `KeyError` on `'Service'` (the unit files do not exist yet).

- [ ] **Step 3: Implement.** `systemd/user/session-archive-capture.service`:

```ini
[Unit]
Description=Capture agent session transcripts into the session archive
Documentation=file://%h/d/tack/docs/specs/2026-09-30-session-archive-design.md

[Service]
Type=oneshot
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python3 %h/d/tack/tools/session-archive capture
Nice=10
IOSchedulingClass=idle
```

`systemd/user/session-archive-capture.timer`:

```ini
[Unit]
Description=Daily session archive capture

[Timer]
OnCalendar=*-*-* 04:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

`systemd/user/session-archive-prune.service`:

```ini
[Unit]
Description=Prune archived, inactive agent sessions (dry run until the rollout gate)
Documentation=file://%h/d/tack/docs/specs/2026-09-30-session-archive-design.md

[Service]
Type=oneshot
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python3 %h/d/tack/tools/session-archive prune
Nice=10
IOSchedulingClass=idle
```

`systemd/user/session-archive-prune.timer`:

```ini
[Unit]
Description=Monthly session archive prune

[Timer]
OnCalendar=*-*-01 05:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Append to `links.toml` under `[required]`:

```toml
"~/.config/systemd/user/session-archive-capture.service" = "systemd/user/session-archive-capture.service"
"~/.config/systemd/user/session-archive-capture.timer" = "systemd/user/session-archive-capture.timer"
"~/.config/systemd/user/session-archive-prune.service" = "systemd/user/session-archive-prune.service"
"~/.config/systemd/user/session-archive-prune.timer" = "systemd/user/session-archive-prune.timer"
```

Add to the `README.md` Layout list, before `docs/`:

```markdown
- `tools/session-archive` and `systemd/user/`: daily capture of agent transcripts to a
  backup disk, and a monthly prune of what the archive and obs verifiably hold
  (`docs/specs/2026-09-30-session-archive-design.md`). Linked on every host; the
  timers are enabled only on a host with `~/.config/session-archive/config.toml`.
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run -q --with pytest pytest tools/test_session_archive_units.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add systemd links.toml README.md tools/test_session_archive_units.py
git commit -m "feat(session-archive): systemd units and their links"
```

---

### Task 16: Capture rollout on titan

This task acts outside the repository: it writes to the backup disk, adds host config, links units and enables a timer. Ask the user for the go-ahead before Step 1, naming the archive root and the size of the first run (about 25G).

**Files:** none tracked. Host state only; each step's result goes into a task note.

- [ ] **Step 1: Merge and link.** After the branch merges to main, run `just link` from the main checkout. It should report the four new links. Then run `just link --apply`, and `just link-check` (expect exit 0).
- [ ] **Step 2: Create the archive.** Make `<backup mount>/agent-sessions` (the user confirms the path), then `touch <root>/.session-archive-root`. Write `~/.config/session-archive/config.toml` with `archive_root` and `obs_command = ["python3", "~/d/obs/obs.py"]`.
- [ ] **Step 3: Pilot.** Run `~/d/tack/tools/session-archive status`: expect exit 1 and `"capture": null`, which proves the gate passes and the manifest opens. Then run `~/d/tack/tools/session-archive capture` in the foreground with a timeout covering the first copy. Record the counts per source, the wall time, and `failed == 0` in a note, in the `run:` form the tasks skill defines.
- [ ] **Step 4: Verify.** Run `status` (expect exit 0). Spot-check that `sha256sum` of one Claude and one Codex mirrored file equals its live file. Run `capture` a second time and expect it to report mostly `unchanged`.
- [ ] **Step 5: Enable.** Run `systemctl --user daemon-reload && systemctl --user enable --now session-archive-capture.timer`, then `systemctl --user list-timers session-archive-capture.timer`. Note that the prune timer stays disabled. After two scheduled runs, `status` shows them; the owner of the next session checks.

---

### Task 17: Prune rollout (blocked on obs)

Blocked until `obs-0bc168` (index state) lands, and, for Step 3, until `obs-de84cb` (archive re-read acceptance) passes. Carries spec §4 steps 3–5.

**Files:**
- Modify: `systemd/user/session-archive-prune.service` (ExecStart gains `--apply`, Description drops "dry run")
- Test: `tools/test_session_archive_units.py` (the prune `ExecStart` expectation gains `--apply`)

- [ ] **Step 1: Contract check.** Run `python3 ~/d/obs/obs.py --json index-state`. Confirm it matches the contract in Global Constraints, fed through `inputs.load_obs_state`. Any difference means fixing obs or amending the contract in both places before continuing.
- [ ] **Step 2: Dry run.** Run `~/d/tack/tools/session-archive prune` and save the report. If it stops with `InspectionFailed`, it names the processes it could not inspect. On titan that is expected to be `(sd-pam)`, which is non-dumpable, and `systemd`, the user manager, whose descriptors can be listed but not followed. Whether to list a process in `uninspectable_ok` is the user's decision, never the agent's. Review it with the user: totals per source, every `kept:` reason other than `active`, and the eligible units. This is a review gate: park with `--waiting-on user --reason review`.
- [ ] **Step 3: Gate.** Confirm `obs-de84cb` is done and its note records a re-read of this archive with no duplicate sessions and no live file marked missing. If it isn't done, stop here.
- [ ] **Step 4: Probe and first apply.** Run `~/d/tack/tools/session-archive probe-codex` (expect exit 0), then `~/d/tack/tools/session-archive prune --apply` once by hand. Check three things:
  - obs still lists the pruned files, as missing with their rows kept;
  - `codex resume --all` no longer lists the deleted threads;
  - `status` exits 0.
- [ ] **Step 5: Switch the unit.** Change the prune `ExecStart` to `... session-archive prune --apply` and update the unit test to match. Run `just test`, commit (`feat(session-archive): prune timer applies`), run `systemctl --user daemon-reload && systemctl --user enable --now session-archive-prune.timer`, then `list-timers`.
