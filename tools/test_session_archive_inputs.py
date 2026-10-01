"""Prune inputs: obs's index state, open inodes and unit discovery (spec §3.2, §3.4)."""
import json
import errno
import os
import subprocess
from contextlib import contextmanager

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


@pytest.mark.parametrize("reference", ["cwd", "root"])
def test_process_directory_references_are_held(tmp_path, reference):
    target = tmp_path / "held-directory"
    target.mkdir()
    proc = fake_proc(tmp_path, tmp_path / "closed-file")
    (proc / "100" / reference).symlink_to(target, target_is_directory=True)
    info = target.stat()
    assert open_inodes(proc=proc) == {(info.st_dev, info.st_ino)}


@pytest.mark.parametrize("reference", ["cwd", "root"])
def test_process_directory_inspection_failure_refuses_unless_allowed(tmp_path, monkeypatch, reference):
    proc = fake_proc(tmp_path, tmp_path / "closed-file")
    original = os.stat

    def denied(path, *args, **kw):
        if path == proc / "100" / reference:
            raise PermissionError(errno.EACCES, "denied")
        return original(path, *args, **kw)

    monkeypatch.setattr(os, "stat", denied)
    with pytest.raises(InspectionFailed, match=reference):
        open_inodes(proc=proc)
    assert open_inodes(allow=("claude",), proc=proc) == set()


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


def obs_payload():
    return {"schema": 9, "files": [{"path": "/source/a.jsonl", "size": 2, "mtime_ms": 5,
            "byte_offset": 2, "partial_tail": 0, "indexed_schema": 9, "missing_since_ms": None}]}


@pytest.mark.parametrize("field,value", [
    ("path", None), ("path", "relative.jsonl"), ("path", "a\x00b"),
    ("size", True), ("size", -1), ("mtime_ms", "5"), ("mtime_ms", -1),
    ("byte_offset", 3), ("byte_offset", -1), ("partial_tail", "false"),
    ("partial_tail", 2), ("indexed_schema", "9"), ("missing_since_ms", False),
])
def test_obs_rejects_malformed_file_values(field, value):
    payload = obs_payload()
    payload["files"][0][field] = value
    with pytest.raises(ObsUnavailable):
        load_obs_state(("obs",), fake_runner(json.dumps(payload)))


@pytest.mark.parametrize("payload", [None, [], {"schema": "9", "files": []},
                                    {"schema": True, "files": []},
                                    {"schema": 9, "files": {}}, {"schema": 9, "files": [None]}])
def test_obs_rejects_malformed_output_shapes(payload):
    with pytest.raises(ObsUnavailable):
        load_obs_state(("obs",), fake_runner(json.dumps(payload)))


def test_obs_null_indexed_schema_is_stale():
    payload = obs_payload()
    payload["files"][0]["indexed_schema"] = None
    state = load_obs_state(("obs",), fake_runner(json.dumps(payload)))
    assert not state["/source/a.jsonl"].schema_current


@pytest.mark.parametrize("field,value", [("size", 3), ("mtime_ms", 6), ("byte_offset", 1),
                                       ("partial_tail", 1), ("indexed_schema", 8),
                                       ("missing_since_ms", 5)])
@pytest.mark.parametrize("alias", [False, True])
def test_obs_rejects_conflicting_canonical_path_rows(tmp_path, field, value, alias):
    real = write(tmp_path / "real" / "a.jsonl", b"x\n")
    (tmp_path / "alias").symlink_to(real.parent, target_is_directory=True)
    payload = obs_payload()
    entry = payload["files"][0]
    entry["path"] = str(real)
    duplicate = {**entry, "path": str(tmp_path / "alias" / real.name) if alias else str(real), field: value}
    payload["files"] = [duplicate, entry]
    with pytest.raises(ObsUnavailable, match="conflicting"):
        load_obs_state(("obs",), fake_runner(json.dumps(payload)))


def test_obs_accepts_identical_canonical_path_rows(tmp_path):
    real = write(tmp_path / "real" / "a.jsonl", b"x\n")
    (tmp_path / "alias").symlink_to(real.parent, target_is_directory=True)
    payload = obs_payload()
    entry = payload["files"][0]
    entry["path"] = str(real)
    payload["files"].append({**entry, "path": str(tmp_path / "alias" / real.name)})
    assert len(load_obs_state(("obs",), fake_runner(json.dumps(payload)))) == 1


@pytest.mark.parametrize("error", [OSError("cannot execute"), subprocess.TimeoutExpired("obs", 900)])
def test_obs_runner_errors_raise(error):
    def run(*args, **kw):
        raise error
    with pytest.raises(ObsUnavailable):
        load_obs_state(("obs",), run)


def test_descriptor_inspection_error_refuses_unless_allowed(tmp_path, monkeypatch):
    target = write(tmp_path / "t", b"x")
    proc = fake_proc(tmp_path, target)
    original = os.stat
    def denied(path, *args, **kw):
        if path == proc / "100" / "fd" / "3":
            raise PermissionError(errno.EACCES, "denied")
        return original(path, *args, **kw)
    monkeypatch.setattr(os, "stat", denied)
    with pytest.raises(InspectionFailed, match=r"100 \(claude\).*fd/3"):
        open_inodes(proc=proc)
    assert open_inodes(allow=("claude",), proc=proc) == set()


def test_missing_fd_directory_of_live_process_refuses(tmp_path):
    proc = fake_proc(tmp_path, write(tmp_path / "t", b"x"))
    (proc / "100" / "fd" / "3").unlink()
    (proc / "100" / "fd").rmdir()
    with pytest.raises(InspectionFailed):
        open_inodes(proc=proc)


def test_proc_listing_failure_refuses(tmp_path):
    with pytest.raises(InspectionFailed):
        open_inodes(proc=tmp_path / "missing-proc")


def test_claude_discovery_ignores_symlink_entries(home, tmp_path):
    src = source(home, "claude")
    target = write(tmp_path / "outside.jsonl", b"keep")
    outside = tmp_path / "outside-dir"
    write(outside / f"{SID}.jsonl", b"keep")
    project = src.root / "-p"
    project.mkdir(parents=True)
    (project / f"{SID}.jsonl").symlink_to(target)
    (project / SID).symlink_to(outside, target_is_directory=True)
    (src.root / "linked-project").symlink_to(outside, target_is_directory=True)
    assert claude_units(src) == []
    (project / SID).unlink()
    write(project / SID / "tool-results" / "r.txt", b"keep")
    (unit,) = claude_units(src)
    assert unit.paths == (project / SID,)
    assert unit.files == (f"-p/{SID}/tool-results/r.txt",)


def test_claude_project_replaced_by_symlink_mid_scan_refuses(home, tmp_path, monkeypatch):
    src = source(home, "claude")
    project = src.root / "-p"
    project.mkdir(parents=True)
    outside = tmp_path / "outside"
    transcript = write(outside / f"{SID}.jsonl", b"outside must stay untouched\n")
    original = os.scandir
    swapped = False

    @contextmanager
    def scan_and_replace(path):
        nonlocal swapped
        with original(path) as scan:
            yield scan
        if not swapped:
            project.rename(tmp_path / "original-project")
            project.symlink_to(outside, target_is_directory=True)
            swapped = True

    monkeypatch.setattr(os, "scandir", scan_and_replace)
    with pytest.raises(OSError):
        claude_units(src)
    assert swapped and project.is_symlink()
    assert transcript.read_bytes() == b"outside must stay untouched\n"
