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


STUB_CODEX = r'''#!/usr/bin/env python3
"""A stand-in for the codex CLI with the behaviour session-archive relies on.

STUB_CODEX_MODE: ok (default), fail (exit 1, touch nothing), unlink-fail (unlink, then
exit 1), hang (sleep past any timeout), ignore-lock (resume and delete ignore the writer
lock), writer-closes (exec closes its rollout at once), writer-during-delete (delete leaves
a detached writer appending to the unlinked rollout), writer-unlink-fail (the same, then
exit 1), no-thread-row (never insert or delete a thread row). STUB_CODEX_LOG, when set,
receives one JSON line per call."""
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
        if mode != "no-thread-row":
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
    if mode in ("writer-during-delete", "writer-unlink-fail"):
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
        if mode != "no-thread-row":
            conn.execute("DELETE FROM threads WHERE id = ?", (tid,))
    if mode in ("unlink-fail", "writer-unlink-fail"):
        sys.exit("Error: failed to delete session")
    print(f"Deleted session {tid}.")
else:
    sys.exit(f"stub codex: unsupported arguments {args}")
'''
