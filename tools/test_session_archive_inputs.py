"""Prune inputs: obs's index state, open inodes and unit discovery (spec §3.2, §3.4)."""
import copy
import json
import errno
import os
import subprocess
from contextlib import contextmanager

import pytest

from session_archive import config
from session_archive.inputs import (InspectionFailed, ObsUnavailable, claude_units, codex_units,
                                    load_obs_state, open_inodes)
from session_archive.testing import SID, TID, claude_session, codex_rollout, lenient_open_inodes, write


def source(home, name):
    return next(s for s in config.sources(home) if s.name == name)


def fake_runner(stdout="", returncode=0, calls=None):
    def run(argv, **kw):
        if calls is not None:
            calls.append(argv)
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="boom")
    return run


def test_obs_state_keeps_exact_link_and_target_paths(tmp_path):
    real = write(tmp_path / "real" / "a.jsonl", b"x\n")
    link = tmp_path / "link.jsonl"
    link.symlink_to(real)
    payload = obs_payload()
    entry = payload["files"][0]
    entry["path"] = str(real)
    linked = copy.deepcopy(entry)
    linked.update(path=str(link), missing_since_ms=5, ready=False, not_ready=["missing"])
    payload["files"].append(linked)
    calls = []
    try:
        state = load_obs_state(("python3", "obs.py"), fake_runner(json.dumps(payload), calls=calls))
    except ObsUnavailable as error:
        pytest.fail(f"valid distinct link and target rows were rejected: {error}")
    assert calls == [["python3", "obs.py", "--json", "index-state"]]
    assert set(state) == {str(real), str(link)}
    assert not state[str(real)].missing and state[str(link)].missing


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
    return {"contract": 2, "schema": 9, "observed_at_ms": 10, "files": [{
        "path": "/source/a.jsonl", "harness": "claude-code", "size": 2, "mtime_ms": 5,
        "device": 1, "inode": 2, "byte_offset": 2, "partial_tail": False,
        "indexed_schema": 9, "missing_since_ms": None,
        "indexed_span": {"length": 2, "sha256": "ab" * 32},
        "observed": {"device": 1, "inode": 2, "size": 2, "mtime_ms": 5},
        "observed_error": None, "malformed_lines": 0, "unrecognized_records": 0,
        "identity": None, "ready": True, "not_ready": [],
    }]}


def load(payload):
    return load_obs_state(("obs",), fake_runner(json.dumps(payload)))


@pytest.mark.parametrize("field", ["contract", "schema", "observed_at_ms", "files"])
def test_obs_requires_envelope_fields(field):
    payload = obs_payload()
    del payload[field]
    with pytest.raises(ObsUnavailable):
        load(payload)


@pytest.mark.parametrize("field", tuple(obs_payload()["files"][0]))
def test_obs_requires_every_file_field(field):
    payload = obs_payload()
    del payload["files"][0][field]
    with pytest.raises(ObsUnavailable):
        load(payload)


@pytest.mark.parametrize("payload", [None, [], 5, {"contract": 2, "schema": 9, "observed_at_ms": 1, "files": [None]}])
def test_obs_rejects_malformed_output_shapes(payload):
    with pytest.raises(ObsUnavailable):
        load(payload)


@pytest.mark.parametrize("field,value", [
    ("contract", None), ("contract", True), ("contract", 2.0), ("contract", 1), ("contract", 3),
    ("schema", "9"), ("schema", True), ("schema", -1),
    ("observed_at_ms", False), ("observed_at_ms", -1), ("files", {}),
])
def test_obs_rejects_malformed_envelope(field, value):
    payload = obs_payload()
    payload[field] = value
    with pytest.raises(ObsUnavailable):
        load(payload)


@pytest.mark.parametrize("field,value", [
    ("path", None), ("path", "relative.jsonl"), ("path", "a\x00b"),
    ("path", "/source/./a.jsonl"), ("path", "/source/../a.jsonl"),
    ("path", "/source//a.jsonl"), ("path", "//source/a.jsonl"), ("path", "/source/a.jsonl/"),
    ("harness", None), ("harness", ""), ("harness", 5),
    ("size", True), ("size", -1), ("mtime_ms", "5"), ("mtime_ms", -1),
    ("byte_offset", 3), ("byte_offset", -1), ("byte_offset", True),
    ("device", True), ("device", -1), ("inode", None), ("inode", False), ("inode", -1),
    ("partial_tail", "false"), ("partial_tail", 0), ("partial_tail", 1),
    ("indexed_schema", "9"), ("indexed_schema", True), ("missing_since_ms", False),
    ("indexed_span", []), ("indexed_span", {}),
    ("indexed_span", {"length": 1, "sha256": "ab" * 32}),
    ("indexed_span", {"length": True, "sha256": "ab" * 32}),
    ("indexed_span", {"length": 2, "sha256": "AB" * 32}),
    ("indexed_span", {"length": 2, "sha256": "ab"}),
    ("indexed_span", {"length": 2, "sha256": None}),
    ("observed", {}), ("observed", []), ("observed_error", "ENOENT"),
    ("malformed_lines", True), ("malformed_lines", -1),
    ("unrecognized_records", "0"), ("unrecognized_records", -1),
    ("identity", {}), ("ready", 1), ("ready", "true"),
    ("not_ready", "missing"), ("not_ready", [""]), ("not_ready", [5]),
])
def test_obs_rejects_malformed_file_values(field, value):
    payload = obs_payload()
    payload["files"][0][field] = value
    with pytest.raises(ObsUnavailable):
        load(payload)


@pytest.mark.parametrize("field,value", [("device", True), ("inode", -1), ("size", "2"), ("mtime_ms", False)])
def test_obs_rejects_malformed_observed_version(field, value):
    payload = obs_payload()
    payload["files"][0]["observed"][field] = value
    with pytest.raises(ObsUnavailable):
        load(payload)


@pytest.mark.parametrize("field,value", [
    ("ready", False), ("not_ready", ["future_reason"]), ("device", None),
    ("indexed_span", None), ("indexed_schema", 8), ("indexed_schema", None),
    ("partial_tail", True), ("missing_since_ms", 5),
])
def test_obs_rejects_contradictory_ready_claims(field, value):
    payload = obs_payload()
    payload["files"][0][field] = value
    with pytest.raises(ObsUnavailable):
        load(payload)


@pytest.mark.parametrize("field", ["device", "inode", "size", "mtime_ms"])
def test_obs_ready_must_match_observed_version(field):
    payload = obs_payload()
    payload["files"][0]["observed"][field] += 1
    with pytest.raises(ObsUnavailable):
        load(payload)


def test_obs_ready_requires_complete_span():
    payload = obs_payload()
    payload["files"][0].update(byte_offset=1, indexed_span={"length": 1, "sha256": "ab" * 32})
    with pytest.raises(ObsUnavailable):
        load(payload)


@pytest.mark.parametrize("missing", [None, 5])
def test_obs_nonready_null_proof_is_valid(missing):
    payload = obs_payload()
    payload["files"][0].update(ready=False, not_ready=["future_reason"], device=None,
                               indexed_schema=None, indexed_span=None, observed=None,
                               observed_error="ENOENT", missing_since_ms=missing)
    entry = load(payload)["/source/a.jsonl"]
    assert getattr(entry, "ready", None) is False
    assert getattr(entry, "not_ready", None) == ("future_reason",)
    assert not entry.schema_current and entry.missing is (missing is not None)


def test_obs_future_harness_is_opaque_and_diagnostics_do_not_block():
    payload = obs_payload()
    payload["files"][0].update(harness="future-harness", identity={"future": [1]},
                               malformed_lines=3, unrecognized_records=5, extra_field=True)
    entry = load(payload)["/source/a.jsonl"]
    assert getattr(entry, "harness", None) == "future-harness"
    assert getattr(entry, "ready", None) is True


@pytest.mark.parametrize("change", [{}, {"size": 3}])
def test_obs_rejects_any_duplicate_path(change):
    payload = obs_payload()
    duplicate = copy.deepcopy(payload["files"][0])
    duplicate.update(change)
    payload["files"].append(duplicate)
    with pytest.raises(ObsUnavailable):
        load(payload)


def codex_payload():
    payload = obs_payload()
    payload["files"][0].update(
        path=f"/source/rollout-2026-01-01-{TID}.jsonl", harness="codex",
        identity={"thread_id": TID, "filename_id": TID, "ancestors": [SID], "conflicts": []})
    return payload


@pytest.mark.parametrize("field,value", [
    ("thread_id", None), ("filename_id", None), ("thread_id", SID), ("filename_id", SID),
    ("conflicts", [SID]), ("ancestors", [None]), ("conflicts", [""]),
])
def test_obs_rejects_codex_identity_contradictions(field, value):
    payload = codex_payload()
    payload["files"][0]["identity"][field] = value
    with pytest.raises(ObsUnavailable):
        load(payload)


@pytest.mark.parametrize("field", ["thread_id", "filename_id", "ancestors", "conflicts"])
def test_obs_requires_codex_identity_fields(field):
    payload = codex_payload()
    del payload["files"][0]["identity"][field]
    with pytest.raises(ObsUnavailable):
        load(payload)


def test_obs_record_sequences_are_immutable():
    payload = codex_payload()
    entry = load(payload)[payload["files"][0]["path"]]
    assert getattr(entry, "identity_conflicts", None) == ()
    assert getattr(entry, "not_ready", None) == ()
    assert isinstance(hash(entry), int)


@pytest.mark.parametrize("factory", [obs_payload, codex_payload])
def test_diagnostic_counts_do_not_block_ready_known_harnesses(factory):
    payload = factory()
    payload["files"][0].update(malformed_lines=3, unrecognized_records=5)
    assert load(payload)[payload["files"][0]["path"]].ready


def test_run_tool_excludes_parent_secrets(home, monkeypatch):
    from session_archive import testing
    captured = []
    monkeypatch.setattr(testing.os, "environ", {"PATH": os.defpath,
                        "UNRELATED_SECRET": "sentinel", "OPENAI_API_KEY": "parent-sentinel"})
    def run(argv, **kwargs):
        captured.append(kwargs["env"])
        return subprocess.CompletedProcess(argv, 0, "", "")
    monkeypatch.setattr(testing.subprocess, "run", run)
    testing.run_tool("status", home=home)
    environment = captured[0]
    assert "UNRELATED_SECRET" not in environment
    assert environment["OPENAI_API_KEY"] == "test-invalid"
    assert environment["HOME"] == str(home)


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
