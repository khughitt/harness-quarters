"""Check Codex's deletion protocol in a throwaway CODEX_HOME (spec §3.4.3, §5).

prune --apply deletes Codex units only on a version that passed these checks.
"""
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
    """The Codex CLI could not report its version."""


@dataclass(frozen=True)
class ProbeResult:
    version: str
    checks: dict

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(self.checks.values())


def codex_version(codex_bin: str, *, env: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run([codex_bin, "--version"], env=env,
                                capture_output=True, text=True, timeout=60)
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

    version = codex_version(codex_bin, env=env)
    # exec creates and holds its thread while retrying before the auth failure.
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
    rows_before_delete = _thread_rows(home / "state_5.sqlite", thread_id)
    deleted = codex("delete", "--force", thread_id)
    checks["archived_delete_removed_file"] = deleted.returncode == 0 and not any(home.rglob(f"*{thread_id}.jsonl"))
    checks["archived_delete_removed_row"] = (
        rows_before_delete == 1 and _thread_rows(home / "state_5.sqlite", thread_id) == 0)
    return ProbeResult(version, checks)
