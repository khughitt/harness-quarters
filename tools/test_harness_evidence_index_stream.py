"""Incremental held-source framing, parity and bounded transport contracts."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from harness_evidence import DECODER_VERSION
from harness_evidence import index_events, index_stream, stream
from test_harness_evidence_index import CONTROLS, FIXTURES, TOOLS, environment, expand_proofs

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
            yield {**proof_event(actual), "key": "E0"}
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
    actual = index_events.extract
    def late(lines, state, **kw):
        for offset, raw in lines:
            consumed.append(offset)
            state.update(next_offset=offset + len(raw), next_line=len(consumed) + 1)
            yield {**proof_event(actual), "key": f"E{offset}"}
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


@pytest.mark.parametrize("name", sorted(p.name for p in (FIXTURES / "index").glob("*.jsonl")))
def test_index_provenance_defaults_round_trip_full_proofs(monkeypatch, name):
    # Dropping any native proof attribute, including optional ones, breaks equality.
    path = FIXTURES / "index" / name
    raw = path.read_bytes().splitlines(keepends=True)
    actual = index_events.extract
    originals = []
    def audited(*args, **kw):
        for value in actual(*args, **kw):
            if value["object"] == "index_event":
                proof = copy.deepcopy(value["provenance"])
                assert set(proof) == set(index_events.PROVENANCE)
                for field in proof.values():
                    field["revision"] = ENVELOPE["decoder"]["revision"]
                originals.append(proof)
            yield value
    monkeypatch.setattr(index_events, "extract", audited)
    state = None
    for size in [0] + [sum(map(len, raw[:i])) for i in range(1, len(raw) + 1)]:
        originals.clear()
        iterator = stream.objects(request(source(path, size=size, state=state)), ENVELOPE)
        header = next(iterator)
        assert header.get("provenance_format") == "defaults/1"
        assert set(header["provenance_defaults"]) == set(index_events.PROVENANCE)
        emitted = []
        try:
            for value in iterator:
                emitted.append(value)
        except (TypeError, ValueError, AttributeError, OverflowError):
            # Existing invalid native fixtures retain their original failure boundary.
            assert not any(v["object"] == "file_end" for v in emitted)
        assert [expand_proofs(v, header["provenance_defaults"]) for v in emitted
                if v["object"] == "index_event"] == originals
        if emitted and emitted[-1]["object"] == "request_end":
            state = emitted[-2]["state"]


def proof_event(extract=None):
    path = FIXTURES / "index/ownership.jsonl"
    raw = path.read_bytes().splitlines(keepends=True)
    from harness_evidence.lines import Place
    place = Place("claude-code", "file", None, "explicit", str(path), path)
    offset = 0
    lines = []
    for line in raw:
        lines.append((offset, line))
        offset += len(line)
    event = next((extract or index_events.extract)(lines, {}, place=place, text=True))
    event["decoder"] = copy.deepcopy(ENVELOPE["decoder"])
    for proof in event["provenance"].values():
        proof["revision"] = event["decoder"]["revision"]
    return event


def test_index_provenance_overrides_preserve_prior_and_path_refs():
    event = proof_event()
    defaults = index_events.provenance_defaults()
    event["provenance"]["identity.subagent"].update(
        ref="archive:prior#L1", basis="heuristic", rule="prior_evidence",
        native_paths=["prior.field"], coverage_keys=["prior/input:field"])
    event["provenance"]["identity.parent"]["ref"] = "archive:path"
    original = copy.deepcopy(event)
    sparse = index_stream._factor_provenance(event, defaults)
    assert sparse["identity.subagent"]["ref"] == "archive:prior#L1"
    assert sparse["identity.parent"]["ref"] == "archive:path"
    assert "ref" not in sparse.get("native_kind", {})
    assert expand_proofs({**event, "provenance": sparse}, defaults) == original["provenance"]
    assert event == original


@pytest.mark.parametrize("change", [
    "missing", "unknown-field", "unknown-attribute", "revision", "missing-revision",
    "missing-source", "null-source", "int-source", "bool-source", "list-source",
    "null-ref", "int-ref", "empty-ref", "basis", "rule", "empty-rule",
    "native_paths", "coverage_keys", "nested-patch", "missing-paths",
])
def test_index_factorization_rejects_missing_or_unrepresentable_proof(change):
    event = proof_event()
    field = event["provenance"]["native_kind"]
    if change == "missing":
        del event["provenance"]["native_kind"]
    elif change == "unknown-field":
        event["provenance"]["future"] = copy.deepcopy(field)
    elif change == "unknown-attribute":
        field["future"] = "must not disappear"
    elif change == "revision":
        field["revision"] = "b" * 40
    elif change == "missing-revision":
        del field["revision"]
    elif change == "missing-source":
        del event["provenance"]["notifications"]["source"]
    elif change.endswith("-source"):
        event["provenance"]["notifications"]["source"] = {
            "null-source": None, "int-source": 0, "bool-source": False, "list-source": []}[change]
    elif change.endswith("-ref"):
        field["ref"] = {"null-ref": None, "int-ref": 0, "empty-ref": ""}[change]
    elif change == "missing-paths":
        del field["native_paths"]
    else:
        key = {"nested-patch": "native_paths", "empty-rule": "rule"}.get(change, change)
        field[key] = {"basis": "unknown", "rule": False, "empty-rule": "",
                      "native_paths": [1], "coverage_keys": "not-list",
                      "nested-patch": {"append": "x"}}[change]
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._factor_provenance(event, index_events.provenance_defaults())


def test_notification_proof_source_presence_survives_encoding():
    event = proof_event()
    defaults = index_events.provenance_defaults()
    assert defaults["notifications"]["source"] == "physical_line"
    assert all("source" not in proof for field, proof in defaults.items() if field != "notifications")
    event["provenance"]["native_kind"]["source"] = ""
    event["provenance"]["notifications"]["source"] = "different"
    sparse = index_stream._factor_provenance(event, defaults)
    assert sparse["native_kind"]["source"] == ""
    assert sparse["notifications"]["source"] == "different"
    assert expand_proofs({**event, "provenance": sparse}, defaults) == event["provenance"]
    event["provenance"]["native_kind"]["source"] = 1
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._factor_provenance(event, defaults)


def test_index_defaults_repeat_per_file_and_resume():
    path = FIXTURES / "index/sizes.jsonl"
    iterator = stream.objects(request(source(path), source(path)), ENVELOPE)
    header = next(iterator)
    pristine = copy.deepcopy(header)
    assert header.get("provenance_format") == "defaults/1"
    header["provenance_defaults"]["native_kind"]["native_paths"].append("caller")
    header["provenance_defaults"]["notifications"].pop("source")
    header["provenance_defaults"] = {}
    rest = list(iterator)
    second = next(v for v in rest if v["object"] == "file_start")
    assert second["provenance_defaults"] == pristine["provenance_defaults"]
    first_event = next(v for v in rest if v["object"] == "index_event")
    assert "native_kind" not in first_event["provenance"]
    assert "notifications" not in first_event["provenance"]
    end = next(v for v in rest if v["object"] == "file_end")
    assert end["count"] == 4  # Three native events plus coverage, declaration is a header field.
    assert "provenance" not in json.dumps(end["state"])
    resumed = read(request(source(path, state=end["state"])))
    assert resumed[0]["provenance_defaults"] == pristine["provenance_defaults"]
    assert resumed[-2]["count"] == 1
    fresh = index_events.provenance_defaults()
    fresh["native_kind"]["native_paths"].clear()
    assert index_events.provenance_defaults()["native_kind"]["native_paths"] == ["type"]


@pytest.mark.parametrize("change", ["unknown-attribute", "revision", "missing-source", "missing-table"])
def test_index_proof_audit_preserves_completed_file(monkeypatch, change):
    actual = index_events.extract
    invocation = 0
    def corrupted(*args, **kw):
        nonlocal invocation
        invocation += 1
        for value in actual(*args, **kw):
            if invocation == 2 and value["object"] == "index_event" and value["line"] == 2:
                if change == "unknown-attribute":
                    value["provenance"]["native_kind"]["future"] = "do not discard"
                elif change == "revision":
                    value["provenance"]["native_kind"]["revision"] = "b" * 40
                elif change == "missing-source":
                    del value["provenance"]["notifications"]["source"]
                else:
                    value.pop("provenance")
            yield value
    monkeypatch.setattr(index_events, "extract", corrupted)
    path = FIXTURES / "index/sizes.jsonl"
    completed, partial = [], []
    with pytest.raises(stream.ProtocolError, match="provenance"):
        for value in stream.objects(request(source(path), source(path)), ENVELOPE):
            partial.append(value)
            if value["object"] == "file_end":
                completed.append(value["file"])
    assert completed == [0]
    assert [v["line"] for v in partial if v.get("file") == 1 and v["object"] == "index_event"] == [1]
    assert not any(v["object"] == "request_end" for v in partial)


def test_index_command_and_import_share_exact_proof_framing(tmp_path):
    path = FIXTURES / "index/native-tools.jsonl"
    req = request(source(path))
    result = subprocess.run([str(TOOLS / "harness-evidence"), "decode"],
                            input=json.dumps(req) + "\n", text=True, capture_output=True,
                            env=environment(tmp_path), timeout=60)
    assert result.returncode == 0, result.stderr
    wire = [json.loads(line) for line in result.stdout.splitlines()]
    envelope = {key: wire[0][key] for key in ("schema", "decoder")}
    assert wire == read(req, envelope)
    assert wire[0]["provenance_format"] == "defaults/1"
    assert all(len(v["provenance"]) < len(wire[0]["provenance_defaults"])
               for v in wire if v["object"] == "index_event")


@pytest.mark.parametrize("changed", [False, True])
def test_equal_builtin_native_proof_avoids_repeated_full_attribute_audit(monkeypatch, changed):
    # Count full auditor visits; the native exact-type traversal is required for safe equality.
    audited_fields = []
    original_audit = index_stream._factor_provenance
    def observed_audit(event, defaults):
        audited_fields.extend(event["provenance"])
        return original_audit(event, defaults)
    monkeypatch.setattr(index_stream, "_factor_provenance", observed_audit)
    actual = index_events.extract
    def observed(*args, **kw):
        for value in actual(*args, **kw):
            if value["object"] == "index_event" and changed:
                value["provenance"]["native_kind"]["rule"] = "changed_rule"
            yield value
    monkeypatch.setattr(index_events, "extract", observed)
    out = read(request(source(FIXTURES / "index/sizes.jsonl")))
    native = [v for v in out if v["object"] == "index_event"]
    assert len(native) == 3
    # One complete declaration audit per file, plus all three changed proofs when applicable.
    assert audited_fields.count("native_kind") == (4 if changed else 1)
    if changed:
        assert all(v["provenance"]["native_kind"] == {"rule": "changed_rule"} for v in native)
    else:
        assert all("native_kind" not in v["provenance"] for v in native)


@pytest.mark.parametrize("attribute,bad", [
    ("native_paths", [False]), ("native_paths", [0]), ("native_paths", ("type",)),
    ("coverage_keys", [False]), ("coverage_keys", [0]), ("coverage_keys", ()),
    ("basis", False), ("basis", 0), ("basis", "unknown"),
    ("rule", False), ("rule", 0), ("rule", ""),
    ("source", False), ("source", 0), ("source", None),
    ("ref", "must-not-be-defaulted"), ("revision", "must-not-be-defaulted"),
    ("future", "do-not-hide"),
])
def test_invalid_proof_defaults_fail_before_header(monkeypatch, attribute, bad):
    # A malformed declaration must never become a reference that validates a matching bad proof.
    defaults = index_events.provenance_defaults()
    defaults["native_kind"][attribute] = bad
    monkeypatch.setattr(index_events, "provenance_defaults", lambda: defaults)
    iterator = stream.objects(request(source(FIXTURES / "index/sizes.jsonl")), ENVELOPE)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        next(iterator)


@pytest.mark.parametrize("attribute,bad", [
    ("native_paths", [False]), ("native_paths", [0]), ("native_paths", ("type",)),
    ("coverage_keys", [False]), ("coverage_keys", [0]), ("coverage_keys", ()),
    ("basis", False), ("basis", 0), ("basis", "unknown"),
    ("rule", False), ("rule", 0), ("rule", ""),
    ("source", False), ("source", 0), ("source", None),
    ("ref", False), ("ref", 0), ("ref", ""),
    ("revision", False), ("revision", 0), ("revision", ""),
    ("future", "do-not-hide"),
])
def test_equality_path_preserves_bad_proof_rejection(monkeypatch, attribute, bad):
    actual = index_events.extract
    def corrupted(*args, **kw):
        for value in actual(*args, **kw):
            if value["object"] == "index_event":
                value["provenance"]["native_kind"][attribute] = bad
            yield value
    monkeypatch.setattr(index_events, "extract", corrupted)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        read(request(source(FIXTURES / "index/sizes.jsonl")))


@pytest.mark.parametrize("attribute,bad", [("ref", False), ("ref", 0), ("ref", ""),
                                           ("revision", False), ("revision", 0)])
def test_equality_path_rejects_invalid_matching_envelope_values(monkeypatch, attribute, bad):
    actual = index_events.extract
    envelope = copy.deepcopy(ENVELOPE)
    if attribute == "revision":
        envelope["decoder"]["revision"] = bad
    def corrupted(*args, **kw):
        for value in actual(*args, **kw):
            if value["object"] == "index_event" and attribute == "ref":
                value["ref"] = bad
                for proof in value["provenance"].values():
                    proof["ref"] = bad
            yield value
    monkeypatch.setattr(index_events, "extract", corrupted)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        read(request(source(FIXTURES / "index/sizes.jsonl")), envelope)


def test_direct_proof_auditor_retains_full_type_validation():
    event = proof_event()
    defaults = index_events.provenance_defaults()
    # bool/int equality must not make a bad array pass when both arguments are malformed.
    defaults["native_kind"]["native_paths"] = [0]
    event["provenance"]["native_kind"]["native_paths"] = [False]
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._factor_provenance(event, defaults)


@pytest.mark.parametrize("attribute", ["ref", "revision"])
def test_equality_path_does_not_trust_overridden_envelope_equality(monkeypatch, attribute):
    class UnusualString(str):
        def __eq__(self, other):
            return True
    actual = index_events.extract
    def corrupted(*args, **kw):
        for value in actual(*args, **kw):
            if value["object"] == "index_event":
                if attribute == "ref":
                    value["ref"] = UnusualString(value["ref"])
                else:
                    value["decoder"] = {**ENVELOPE["decoder"],
                                        "revision": UnusualString(ENVELOPE["decoder"]["revision"])}
                value["provenance"]["native_kind"][attribute] = 0
            yield value
    monkeypatch.setattr(index_events, "extract", corrupted)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        read(request(source(FIXTURES / "index/sizes.jsonl")))


@pytest.mark.parametrize("attribute", ["rule", "source", "native_paths", "coverage_keys"])
def test_equality_path_cannot_inherit_overridden_declaration_equality(monkeypatch, attribute):
    class UnusualString(str):
        def __eq__(self, other):
            return True
    defaults = index_events.provenance_defaults()
    array = attribute in {"native_paths", "coverage_keys"}
    defaults["native_kind"][attribute] = [UnusualString("type")] if array else UnusualString("value")
    monkeypatch.setattr(index_events, "provenance_defaults", lambda: defaults)
    actual = index_events.extract
    def corrupted(*args, **kw):
        for value in actual(*args, **kw):
            if value["object"] == "index_event":
                value["provenance"]["native_kind"][attribute] = [0] if array else 0
            yield value
    monkeypatch.setattr(index_events, "extract", corrupted)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        read(request(source(FIXTURES / "index/sizes.jsonl")))


def complete_default_event(defaults):
    return {"ref": "file#L1", "decoder": {"revision": "a" * 40},
            "provenance": {field: {**copy.deepcopy(proof), "ref": "file#L1", "revision": "a" * 40}
                           for field, proof in defaults.items()}}


def native_equal_override(kind):
    class EqualInt(int):
        def __eq__(self, other):
            return True
        __hash__ = int.__hash__
    class EqualStr(str):
        def __eq__(self, other):
            return True
        __hash__ = str.__hash__
    class EqualList(list):
        def __eq__(self, other):
            return True
    return {"integer": lambda: EqualInt(0), "empty-string": lambda: EqualStr(""),
            "bad-list": lambda: EqualList([0]), "changed-string": lambda: EqualStr("changed_rule")}[kind]()


@pytest.mark.parametrize("field,attribute,kind", [
    ("native_kind", "basis", "integer"), ("native_kind", "basis", "empty-string"),
    ("native_kind", "rule", "integer"), ("native_kind", "rule", "empty-string"),
    ("native_kind", "ref", "integer"), ("native_kind", "ref", "empty-string"),
    ("native_kind", "revision", "integer"), ("native_kind", "revision", "empty-string"),
    ("notifications", "source", "integer"),
    ("native_kind", "native_paths", "bad-list"),
    ("native_kind", "coverage_keys", "bad-list"),
])
def test_native_equality_override_cannot_hide_invalid_proof(field, attribute, kind):
    defaults = index_events.provenance_defaults()
    event = complete_default_event(defaults)
    event["provenance"][field][attribute] = native_equal_override(kind)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._factor_provenance(event, defaults)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._provenance_factor(defaults)(event)


@pytest.mark.parametrize("field,attribute", [("native_kind", "native_paths"),
                                            ("response.id", "coverage_keys")])
def test_native_list_item_equality_override_cannot_hide_invalid_type(field, attribute):
    defaults = index_events.provenance_defaults()
    event = complete_default_event(defaults)
    event["provenance"][field][attribute][0] = native_equal_override("integer")
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._factor_provenance(event, defaults)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._provenance_factor(defaults)(event)


@pytest.mark.parametrize("field,attribute", [("native_kind", "rule"), ("notifications", "source")])
def test_native_valid_string_override_preserves_full_auditor_delta(field, attribute):
    defaults = index_events.provenance_defaults()
    event = complete_default_event(defaults)
    event["provenance"][field][attribute] = native_equal_override("changed-string")
    expected = {field: {attribute: "changed_rule"}}
    full = index_stream._factor_provenance(event, defaults)
    assert json.loads(json.dumps(full)) == expected
    fast = index_stream._provenance_factor(defaults)(event)
    assert json.loads(json.dumps(fast)) == expected


def test_native_proof_dictionary_override_uses_original_auditor():
    class AlteredAccess(dict):
        def __getitem__(self, key):
            return 0 if key == "rule" else super().__getitem__(key)
    defaults = index_events.provenance_defaults()
    event = complete_default_event(defaults)
    event["provenance"]["native_kind"] = AlteredAccess(event["provenance"]["native_kind"])
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._factor_provenance(event, defaults)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._provenance_factor(defaults)(event)
