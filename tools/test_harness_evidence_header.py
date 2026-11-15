"""Cheap selection preserves the old first-fifty-physical-line policy."""
import hashlib
import io
import json
from pathlib import Path
import subprocess

import pytest

from harness_evidence import DECODER_VERSION, stream
from test_harness_evidence_index import FIXTURES, TOOLS, environment
from test_harness_evidence_index_stream import source

ENVELOPE = {"schema": "harness-evidence/1", "decoder": {"version": DECODER_VERSION, "revision": "a" * 40}}
NATIVE = (FIXTURES / "index/sizes.jsonl").read_bytes().splitlines(keepends=True)[0]


# Unchanged selector body from OBS 99f1b12a:src/obs/harness/stores.py.
def old_peek_cwd(path):
    with open(path, errors="replace") as handle:
        for _, line in zip(range(50), handle):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("cwd"):
                return record["cwd"]
            if record.get("type") == "session_meta":
                return (record.get("payload") or {}).get("cwd")
    return None


def run(*files, roots):
    from harness_evidence import header
    out, err = io.StringIO(), io.StringIO()
    status = header.run(io.StringIO(json.dumps({"id": 7, "files": list(files), "roots": roots}) + "\n"), out, err, ENVELOPE)
    return status, [json.loads(line) for line in out.getvalue().splitlines()], err.getvalue()


def test_header_matches_existing_first_fifty_line_policy(tmp_path):
    paths = []
    for name, data in [("first", NATIVE + b'42\n'), ("fifty", b'bad\n' * 49 + NATIVE),
                       ("fifty-one", b'bad\n' * 50 + NATIVE), ("unterminated", NATIVE.rstrip(b'\n')),
                       ("empty", b'')]:
        path = tmp_path / name
        path.write_bytes(data)
        paths.append(path)
    status, rows, err = run(*(source(p) for p in paths), roots=[{"harness": "claude-code", "path": str(tmp_path)}])
    assert status == 0 and err == ""
    assert rows[-1] == {**ENVELOPE, "request": 7, "object": "request_end", "files": 5}
    assert [(r["file"], r["path"], r["header"]["cwd"]) for r in rows[:-1]] == [
        (i, str(p), None if i in (2, 4) else "/w/project") for i, p in enumerate(paths)]
    for row, number in [(rows[0], 1), (rows[1], 50), (rows[3], 1)]:
        proof = row["provenance"]["cwd"]
        assert proof["line"] == number and proof["basis"] == "native"
        assert proof["ref"].endswith(f'#L{number}')
        raw = NATIVE.rstrip(b'\n') if row is rows[3] else NATIVE
        assert proof["sha256"] == hashlib.sha256(raw).hexdigest()
        assert proof["offset"] == (number - 1) * 4
        assert proof["revision"] == "a" * 40
    assert [r["header"]["cwd"] for r in rows[:-1]] == [old_peek_cwd(path) for path in paths]
    assert rows[0]["header"] == {"session": "control", "cwd": "/w/project", "start_ms": 1794441540000}


def test_header_large_first_line_stays_bounded(tmp_path, monkeypatch):
    from harness_evidence import header
    path = tmp_path / "large"
    raw = b' ' * (2 * 1024 * 1024) + NATIVE
    path.write_bytes(raw + b'42\n' * 100)
    real_open = Path.open
    reads = []

    class Held:
        def __init__(self, handle): self.handle = handle
        def __enter__(self): return self
        def __exit__(self, *args): self.handle.close()
        def fileno(self): return self.handle.fileno()
        def read(self, limit):
            assert 0 < limit <= 65536
            reads.append(limit)
            return self.handle.read(limit)

    def opened(self, *args, **kwargs):
        held = real_open(self, *args, **kwargs)
        return Held(held) if self == path else held

    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(stream, "_read", lambda *_a: pytest.fail("full decoder read"))
    status, rows, err = run(source(path), roots=[{"harness": "claude-code", "path": str(tmp_path)}])
    assert status == 0 and err == "" and rows[0]["header"]["cwd"] == "/w/project"
    assert sum(reads) <= len(raw) + 65536


def test_header_partial_malformed_vanished_and_archive_sources(tmp_path):
    physical = tmp_path / "archive"
    physical.write_bytes(b'bad\n' + NATIVE.rstrip(b'\n'))
    logical = tmp_path / "projects/p/session.jsonl"
    valid = source(physical, logical=logical)
    vanished = {**valid, "path": str(tmp_path / "projects/p/vanished.jsonl"), "read_path": str(tmp_path / "missing")}
    status, rows, err = run(valid, vanished, roots=[{"harness": "claude-code", "path": str(tmp_path / "projects")}])
    assert status == 0 and not err
    assert rows[0]["path"] == str(logical) and rows[0]["header"]["cwd"] == "/w/project"
    assert rows[0]["provenance"]["cwd"]["offset"] == 4
    assert "session.jsonl#L2" in rows[0]["provenance"]["cwd"]["ref"]
    assert rows[1]["status"] == "vanished" and rows[1]["error"]["type"] == "FileNotFoundError"
    for data, expected in [(b'{"cwd":', None), (b'42\n', "invalid_source"),
                           (b'{"cwd":["finite",2]}', ["finite", 2])]:
        physical.write_bytes(data)
        status, rows, err = run(source(physical), roots=[{"harness": "claude-code", "path": str(tmp_path)}])
        assert status == 0 and not err
        if expected == "invalid_source":
            assert rows[0]["status"] == expected and rows[0]["error"] is not None
        else:
            assert rows[0]["status"] == "ok" and rows[0]["header"]["cwd"] == expected


def test_header_wrong_identity_and_missing_terminal_fail(tmp_path):
    path = tmp_path / "source"
    path.write_bytes(NATIVE)
    roots = [{"harness": "claude-code", "path": str(tmp_path)}]
    wrong = source(path)
    wrong["identity"]["inode"] += 1
    status, rows, err = run(wrong, roots=roots)
    assert status == 2 and "identity" in err and not rows
    status, rows, err = run(source(path), roots=[{"harness": "codex", "path": str(tmp_path)}])
    assert status == 2 and "no index adapter for codex" in err and not rows
    from harness_evidence import header
    for request in [{"id": 1, "files": [source(path)]},
                    {"id": 1, "files": [source(path), source(path)], "roots": roots},
                    {"id": 1, "files": [source(path)], "roots": roots, "unknown": True}]:
        out, err = io.StringIO(), io.StringIO()
        assert header.run(io.StringIO(json.dumps(request) + "\n"), out, err, ENVELOPE) == 2
        assert out.getvalue() == "" and err.getvalue()
    result = subprocess.run([str(TOOLS / "harness-evidence"), "header"],
        input=json.dumps({"id": 1, "files": [wrong], "roots": roots}) + "\n",
        env=environment(tmp_path), capture_output=True, text=True, timeout=30)
    assert result.returncode == 2 and not result.stdout and result.stderr


@pytest.mark.parametrize("newline", [b"\r", b"\r\n"])
def test_header_universal_physical_newlines_and_session_meta_stop(tmp_path, newline):
    path = tmp_path / "newlines"
    path.write_bytes(newline.join([b"bad"] * 49 + [NATIVE.rstrip(b"\n"), b"42"]))
    status, rows, err = run(source(path), roots=[{"harness": "claude-code", "path": str(tmp_path)}])
    assert status == 0 and not err and rows[0]["header"]["cwd"] == "/w/project"
    proof = rows[0]["provenance"]["cwd"]
    assert proof["line"] == 50 and proof["offset"] == 49 * (3 + len(newline))
    for payload, expected in [(None, None), ({}, None), ({"cwd": False}, False), ({"cwd": 0}, 0)]:
        path.write_bytes(json.dumps({"type": "session_meta", "payload": payload}).encode() + newline + NATIVE)
        status, rows, err = run(source(path), roots=[{"harness": "claude-code", "path": str(tmp_path)}])
        assert status == 0 and not err and rows[0]["header"]["cwd"] == expected
        assert rows[0]["header"]["cwd"] == old_peek_cwd(path)
        assert rows[0]["header"]["session"] is None
    path.write_bytes(b'{"type":"session_meta","payload":[1]}' + newline + NATIVE)
    status, rows, err = run(source(path), roots=[{"harness": "claude-code", "path": str(tmp_path)}])
    assert status == 0 and not err and rows[0]["status"] == "invalid_source"


def test_header_optional_evidence_cannot_change_selection_and_fixed_span(tmp_path):
    path = tmp_path / "source"
    raw = b'{"cwd":"/selected","sessionId":42,"timestamp":"bad"}\n'
    path.write_bytes(raw + NATIVE)
    descriptor = source(path, size=len(raw))
    roots = [{"harness": "claude-code", "path": str(tmp_path)}]
    status, rows, err = run(descriptor, roots=roots)
    assert status == 0 and not err
    assert rows[0]["header"] == {"session": None, "cwd": "/selected", "start_ms": None}
    assert set(rows[0]["provenance"]) == {"cwd"}
    path.write_bytes(raw[:-1])
    status, rows, err = run(descriptor, roots=roots)
    assert status == 2 and not rows and "shorter" in err
    path.write_bytes(b'{"cwd":"/repl\xff"}\n')
    status, rows, err = run(source(path), roots=roots)
    assert status == 0 and not err and rows[0]["header"]["cwd"] == "/repl\ufffd"


@pytest.mark.parametrize("newline", [b"\r", b"\r\n"])
def test_header_newline_at_chunk_boundary_preserves_source_bytes(tmp_path, newline):
    path = tmp_path / "boundary"
    first = b" " * 65535 + newline
    path.write_bytes(first + NATIVE)
    status, rows, err = run(source(path), roots=[{"harness": "claude-code", "path": str(tmp_path)}])
    assert status == 0 and not err and rows[0]["header"]["cwd"] == "/w/project"
    assert rows[0]["provenance"]["cwd"]["line"] == 2
    assert rows[0]["provenance"]["cwd"]["offset"] == len(first)
    assert rows[0]["provenance"]["cwd"]["sha256"] == hashlib.sha256(NATIVE).hexdigest()


def test_header_unrelated_nonfinite_native_values_do_not_change_selected_cwd(tmp_path):
    path = tmp_path / "source"
    path.write_bytes(b'{"cwd":"/selected","sessionId":NaN,"timestamp":Infinity,"unused":1e400}\n42\n')
    status, rows, err = run(source(path), roots=[{"harness": "claude-code", "path": str(tmp_path)}])
    assert old_peek_cwd(path) == "/selected"
    assert status == 0 and not err
    assert rows[0]["header"] == {"session": None, "cwd": "/selected", "start_ms": None}
    for data in [b'{"cwd":NaN}', b'{"cwd":{"nested":Infinity}}',
                 b'{"type":"session_meta","payload":{"cwd":1e400}}']:
        path.write_bytes(data)
        status, rows, err = run(source(path), roots=[{"harness": "claude-code", "path": str(tmp_path)}])
        assert status == 0 and not err and rows[0]["status"] == "invalid_source"
        assert rows[0]["error"] is not None


@pytest.mark.parametrize("archive", [False, True])
@pytest.mark.parametrize("relative", ["project/session.jsonl", "project/parent/subagents/agent-child.jsonl"])
def test_discovered_directory_fails_header_and_both_decode_profiles(tmp_path, archive, relative):
    from harness_evidence import discover
    from test_harness_evidence_discover import old_paths
    physical_root = tmp_path / ("archive" if archive else "live") / ".claude/projects"
    logical_root = tmp_path / "live/.claude/projects"
    physical = physical_root / relative
    physical.parent.mkdir(parents=True)
    physical.write_bytes((FIXTURES / "index/sizes.jsonl").read_bytes())
    physical.unlink()
    physical.mkdir()
    found = discover.list_files(discover.roots(explicit=[("claude-code", physical_root)]), None).files
    assert found == old_paths("claude-code", [physical_root]) == [physical]
    descriptor = source(found[0], logical=logical_root / relative)
    roots = [{"harness": "claude-code", "path": str(logical_root)}]
    status, rows, err = run(descriptor, roots=roots)
    assert status == 0 and not err
    assert rows[0]["path"] == str(logical_root / relative)
    assert rows[0]["status"] == "unreadable" and rows[0]["error"]["type"] == "IsADirectoryError"
    assert rows[-1]["object"] == "request_end" and rows[-1]["files"] == 1
    for profile in (None, "index"):
        request = {"id": 9, "roots": roots, "files": [dict(descriptor)]}
        if profile is None:
            del request["files"][0]["identity"]
        else:
            request["extract"] = profile
        out, err = io.StringIO(), io.StringIO()
        assert stream.run(io.StringIO(json.dumps(request) + "\n"), out, err, ENVELOPE) == 0
        values = [json.loads(line) for line in out.getvalue().splitlines()]
        assert not err.getvalue()
        end = next(v for v in values if v["object"] == "file_end")
        assert end["status"] == "unreadable" and end["offset"] == 0
        assert values[-1]["object"] == "request_end" and values[-1]["files"] == 1
        if profile == "index":
            assert end["state"] is None and end["restart"] is None
