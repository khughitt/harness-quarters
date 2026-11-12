"""Incremental held-source framing, parity and bounded transport contracts."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from harness_evidence import DECODER_VERSION
from harness_evidence import index_events, stream
from test_harness_evidence_index import CONTROLS, FIXTURES, TOOLS, environment

ENVELOPE = {"schema": "harness-evidence/1", "decoder": {"version": DECODER_VERSION, "revision": "a" * 40}}


def source(path, *, size=None, state=None, logical=None):
    info = path.stat()
    result = {"path": str(logical or path), "read_path": str(path),
              "size": info.st_size if size is None else size,
              "identity": {"device": info.st_dev, "inode": info.st_ino}}
    if state is not None:
        result["state"] = state
    return result


def request(*files, **kw):
    return {"id": 1, "extract": "index", "roots": [], "text": True,
            "cross_file": False, "raw": False, "files": list(files), **kw}


def read(req, envelope=ENVELOPE):
    result = list(stream.objects(stream.validate(req), envelope))
    assert result[-1]["object"] == "request_end"
    for i in range(len(req["files"])):
        values = [v for v in result if v.get("file") == i]
        assert values[0]["object"] == "file_start" and values[-1]["object"] == "file_end"
        assert values[-1]["count"] == len(values) - 2
    return result


def coverage(out):
    return next(v for v in out if v["object"] == "coverage")


@pytest.mark.parametrize("name", ["fragments.jsonl", "native-tools.jsonl", "ownership.jsonl", "fix1-stop-matching.jsonl"])
def test_append_matches_old_schedule_with_response_tool_question_and_hook_pending(name):
    path = FIXTURES / "index" / name
    raw = path.read_bytes().splitlines(keepends=True)
    state, previous = None, 0
    for old in CONTROLS["cases"][name]["replay"]:
        end = sum(map(len, raw[:old["through_line"]]))
        out = read(request(source(path, size=end, state=state)))
        assert out[0]["replaces"] == ("all" if state is None else {"from_line": previous + 1})
        events = [v for v in out if v["object"] == "index_event"]
        assert [v["key"] for v in events] == [f'E{sum(map(len, raw[:n]))}' for n in range(previous, old["through_line"])]
        assert coverage(out)["records"] == old["records"]
        assert coverage(out)["fields"] == old["fields"]
        for event in events:
            line = raw[event["line"] - 1]
            assert event["sha256"] == hashlib.sha256(line).hexdigest()
            assert event["end"] - event["offset"] == len(line)
        state = out[-2]["state"]
        assert state["digest"] == hashlib.sha256(b"".join(raw[:old["through_line"]])).hexdigest()
        assert "guard-sensitive-command" not in json.dumps(state)
        previous = old["through_line"]
    full = coverage(read(request(source(path))))
    old = CONTROLS["cases"][name]
    assert full["fields"] == old["fields"]
    if name == "fragments.jsonl":
        assert coverage(out)["fields"] != full["fields"]  # preserved historical EOF-flush defect
        differences = {r["record_kind"] for r in coverage(out)["fields"] if r not in full["fields"]}
        assert differences == {"applied:usage"}


def test_partial_tail_does_not_advance_or_count_twice(tmp_path):
    path = tmp_path / "tail"
    raw = (FIXTURES / "index/fragments.jsonl").read_bytes().splitlines(keepends=True)
    path.write_bytes(raw[0] + raw[1][:20])
    first = read(request(source(path)))
    state = first[-2]["state"]
    assert state["next_offset"] == len(raw[0]) and state["next_line"] == 2
    assert coverage(first)["partial_tail"]
    path.write_bytes(raw[0] + raw[1])
    second = read(request(source(path, state=state)))
    assert [v["line"] for v in second if v["object"] == "index_event"] == [2]
    full = coverage(read(request(source(path))))
    assert coverage(second)["fields"] == full["fields"]
    assert coverage(second)["records"] == full["records"]


@pytest.mark.parametrize("change", ["prefix", "inode", "revision", "version", "options", "logical", "boundary"])
def test_prefix_rewrite_inode_and_revision_trigger_replacement(tmp_path, change):
    path = tmp_path / "file"
    path.write_bytes((FIXTURES / "index/sizes.jsonl").read_bytes())
    first = read(request(source(path)))
    state = copy.deepcopy(first[-2]["state"])
    envelope, options, logical = ENVELOPE, {}, None
    if change == "prefix":
        path.write_bytes(path.read_bytes().replace(b'first', b'other'))
    elif change == "inode":
        replacement = tmp_path / "replacement"
        replacement.write_bytes(path.read_bytes())
        replacement.replace(path)
    elif change in {"revision", "version"}:
        envelope = copy.deepcopy(ENVELOPE)
        envelope["decoder"][change] = "different"
    elif change == "options":
        options["text"] = False
    elif change == "logical":
        logical = tmp_path / "other-logical"
    else:
        state["next_line"] += 1
    out = read(request(source(path, state=state, logical=logical), **options), envelope)
    assert out[0]["replaces"] == "all"
    assert len([v for v in out if v["object"] == "index_event"]) == 3


def test_logical_identity_reads_physical_archive(tmp_path):
    physical = FIXTURES / "index/original-parent-000.jsonl"
    root = tmp_path / ".claude/projects"
    logical = root / "project" / "path-parent" / "subagents" / "agent-kid.jsonl"
    req = request(source(physical, logical=logical), roots=[{"harness": "claude-code", "path": str(root)}])
    first = read(req)
    assert first[0]["path_facts"]["parent"] == "path-parent"
    event = next(v for v in first if v["object"] == "index_event")
    assert event["identity"]["parent"] == "path-parent" and event["identity"]["index_session"].startswith("agent-")
    assert str(logical) in event["ref"] or logical.name in event["ref"]
    second = read(request(source(physical, logical=logical, state=first[-2]["state"]), roots=req["roots"]))
    assert second[0]["replaces"] == {"from_line": first[-2]["state"]["next_line"]}
    assert not [v for v in second if v["object"] == "index_event"]


def test_restart_seed_clears_old_rows(monkeypatch):
    from harness_evidence import index_stream
    actual = index_events.extract
    def late(lines, state, **kw):
        if not state.pop("restart_mode", False):
            iterator = iter(lines)
            offset, raw = next(iterator)
            state["next_offset"] = offset + len(raw)
            state["next_line"] = 2
            yield {"object": "index_event", "key": "E0"}
            raise index_events.Restart("test invalidation", {"restart_mode": True})
        yield from actual(lines, state, **kw)
    monkeypatch.setattr(index_events, "extract", late)
    path = FIXTURES / "index/sizes.jsonl"
    out = list(index_stream.objects(request(source(path)), ENVELOPE))
    assert "restart" not in out[0] and out[-2]["state"] is None
    terminal = out[-2]
    assert terminal["count"] == 1 and terminal["offset"] == len(path.read_bytes().splitlines(keepends=True)[0])
    seed = terminal["restart"]["seed"]
    assert seed["next_offset"] == 0 and seed["next_line"] == 1
    retry = read(request(source(path, state=seed)))
    assert retry[0]["replaces"] == "all" and retry[-2]["restart"] is None
    assert coverage(retry)["fields"] == CONTROLS["cases"]["sizes.jsonl"]["fields"]


def test_mid_file_restart_is_terminal_and_stream_stays_bounded(monkeypatch, tmp_path):
    from harness_evidence import index_stream
    path = tmp_path / "many-lines"
    path.write_bytes(b'{}\n' * 10000)
    consumed = []
    def late(lines, state, **kw):
        for offset, raw in lines:
            consumed.append(offset)
            state.update(next_offset=offset + len(raw), next_line=len(consumed) + 1)
            yield {"object": "index_event", "key": f"E{offset}"}
            if len(consumed) == 2:
                raise index_events.Restart("test", {"restart_mode": True})
    monkeypatch.setattr(index_events, "extract", late)
    iterator = index_stream.objects(request(source(path)), ENVELOPE)
    assert next(iterator)["object"] == "file_start" and consumed == []
    assert next(iterator)["key"] == "E0" and consumed == [0]
    assert next(iterator)["key"] == "E3" and consumed == [0, 3]
    end = next(iterator)
    assert end["restart"]["reason"] == "test" and end["count"] == 2
    assert next(iterator)["object"] == "request_end"
    assert consumed == [0, 3]


def test_batch_first_complete_file_survives_later_protocol_failure():
    path = FIXTURES / "index/sizes.jsonl"
    broken = source(path)
    broken["identity"]["inode"] += 1
    iterator = stream.objects(stream.validate(request(source(path), broken)), ENVELOPE)
    accepted = []
    with pytest.raises(stream.ProtocolError, match="identity"):
        for value in iterator:
            if value["object"] == "file_end":
                accepted.append(value)
    assert len(accepted) == 1 and accepted[0]["state"]["next_offset"] == path.stat().st_size


def test_twenty_mb_line_and_many_files_do_not_deadlock_or_retain_text(tmp_path):
    path = tmp_path / "large"
    native = {"type": "user", "sessionId": "large", "timestamp": "2026-11-12T00:00:00Z", "message": {"content": "x" * (20 * 1024 * 1024)}}
    path.write_text(json.dumps(native) + "\n")
    small = tmp_path / "small"
    small.write_text('{"type":"unknown"}\n')
    req = request(source(path), *(source(small) for _ in range(100)))
    result = subprocess.run([str(TOOLS / "harness-evidence"), "decode"], input=json.dumps(req) + "\n", text=True,
                            capture_output=True, env=environment(tmp_path), timeout=60)
    assert result.returncode == 0, result.stderr
    ends = [json.loads(v) for v in result.stdout.splitlines() if '"object":"file_end"' in v]
    assert len(ends) == 101
    assert all(len(json.dumps(v["state"])) < 3000 for v in ends)
    assert all(v["count"] == 2 for v in ends)


@pytest.mark.parametrize("payload,status", [(b"", "ok"), (b"not json\n{}", "ok"), (b'{"type":"future"}\n', "ok")])
def test_empty_unknown_malformed_source_stays_evidence(tmp_path, payload, status):
    path = tmp_path / "source"
    path.write_bytes(payload)
    out = read(request(source(path)))
    assert out[-2]["status"] == status
    assert coverage(out)["malformed"] == int(payload.startswith(b'not'))
    assert coverage(out)["partial_tail"] == payload.endswith(b'{}')


@pytest.mark.parametrize("bad", [{"next_offset": 0}, {"next_line": True, "next_offset": 0, "digest": "0" * 64, "index": {}}, {"next_line": 1, "next_offset": 0, "digest": "wrong", "index": {}}])
def test_invalid_checkpoint_is_protocol_error_before_output(bad):
    path = FIXTURES / "index/sizes.jsonl"
    with pytest.raises(stream.ProtocolError):
        stream.validate(request(source(path, state=bad)))


def test_held_handle_reads_original_source_after_path_replacement(tmp_path):
    path = tmp_path / "live-path"
    original = (FIXTURES / "index/sizes.jsonl").read_bytes()
    path.write_bytes(original)
    iterator = stream.objects(stream.validate(request(source(path))), ENVELOPE)
    assert next(iterator)["object"] == "file_start"
    replacement = tmp_path / "new-inode"
    replacement.write_bytes(b'{"type":"replacement"}\n')
    replacement.replace(path)
    out = list(iterator)
    assert out[-2]["state"]["digest"] == hashlib.sha256(original).hexdigest()
    assert [v["native_kind"] for v in out if v["object"] == "index_event"] == ["user", "assistant", "user"]


@pytest.mark.parametrize("truncated", [b"", b"{}\n{"])
def test_short_read_fails_without_file_terminal(tmp_path, truncated):
    path = tmp_path / "truncated"
    path.write_bytes(b"{}\n{}\n")
    iterator = stream.objects(stream.validate(request(source(path))), ENVELOPE)
    assert next(iterator)["object"] == "file_start"
    path.write_bytes(truncated)
    emitted = []
    with pytest.raises(stream.ProtocolError, match="short read"):
        for value in iterator:
            emitted.append(value)
    assert not any(v["object"] in {"file_end", "request_end"} for v in emitted)
    assert [v["object"] for v in emitted] == (["index_event"] if truncated else [])


def test_nonempty_short_read_preserves_previous_file_terminal(tmp_path):
    first = FIXTURES / "index/sizes.jsonl"
    path = tmp_path / "truncated-second"
    path.write_bytes(b"{}\n{}\n")
    iterator = stream.objects(stream.validate(request(source(first), source(path))), ENVELOPE)
    emitted = []
    with pytest.raises(stream.ProtocolError, match="short read"):
        for value in iterator:
            emitted.append(value)
            if value["object"] == "file_start" and value["file"] == 1:
                path.write_bytes(b"{}\n{")
    terminals = [v for v in emitted if v["object"] == "file_end"]
    assert len(terminals) == 1 and terminals[0]["file"] == 0
    assert terminals[0]["offset"] == first.stat().st_size
    assert terminals[0]["state"]["next_offset"] == first.stat().st_size
    assert not any(v["object"] == "request_end" for v in emitted)


def test_vanished_source_is_framed_and_has_no_checkpoint(tmp_path):
    path = tmp_path / "gone"
    path.write_bytes(b"{}\n")
    src = source(path)
    path.unlink()
    out = read(request(src))
    assert out[-2]["status"] == "vanished" and out[-2]["state"] is None


def test_bad_identity_in_batch_exits_nonzero_after_first_terminal(tmp_path):
    path = FIXTURES / "index/sizes.jsonl"
    invalid = source(path)
    invalid["identity"]["inode"] += 1
    result = subprocess.run([str(TOOLS / "harness-evidence"), "decode"],
                            input=json.dumps(request(source(path), invalid)) + "\n", text=True,
                            capture_output=True, timeout=60, env=environment(tmp_path))
    assert result.returncode != 0
    values = [json.loads(line) for line in result.stdout.splitlines()]
    assert len([v for v in values if v["object"] == "file_end"]) == 1
    assert not any(v["object"] == "request_end" for v in values)
    assert "identity" in result.stderr


def test_unencodable_source_path_is_framed_unreadable():
    out = read(request({"path": "\ud800", "size": 0, "identity": {"device": 0, "inode": 0}}))
    assert out[-2]["status"] == "unreadable" and out[-2]["state"] is None
