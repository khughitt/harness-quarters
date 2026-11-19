"""Incremental held-source framing, parity and bounded transport contracts."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from harness_evidence import DECODER_VERSION
from harness_evidence import index_claude, index_events, index_stream, stream
from test_harness_evidence_index import (CONTROLS, FIXTURES, TOOLS, environment, expand_proofs,
                                        PROVENANCE_ORACLE, oracle_hash, oracle_rows, oracle_error,
                                        oracle_native_case, old_claude_defaults, pre_oracle_defaults,
                                        POST_ORACLE_FIXTURES)

ENVELOPE = {"schema": "harness-evidence/1", "decoder": {"version": DECODER_VERSION, "revision": "a" * 40}}


def patch_claude(monkeypatch, name, value):
    """Replace a Claude extractor entry point where both the registry and direct callers see it."""
    monkeypatch.setattr(index_events, name, value)
    monkeypatch.setattr(index_claude, name, value)


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
            yield {**proof_event(actual, complete=False), "key": "E0"}
            raise index_events.Restart("test invalidation", {"restart_mode": True})
        yield from actual(lines, state, **kw)
    patch_claude(monkeypatch, "extract", late)
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
            yield {**proof_event(actual, complete=False), "key": f"E{offset}"}
            if len(consumed) == 2:
                raise index_events.Restart("test", {"restart_mode": True})
    patch_claude(monkeypatch, "extract", late)
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
    # Frozen independent expectations replace the retired full-table interception.
    for case in PROVENANCE_ORACLE["cases"]:
        if case["fixture"] == "index/" + name:
            oracle_native_case(case)


def proof_event(extract=None, *, complete=True):
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
    if complete:
        event["provenance"] = expand_proofs(event, index_events.provenance_defaults())
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


@pytest.mark.parametrize("change", ["unknown-attribute", "revision", "null-source", "missing-table"])
def test_index_proof_audit_preserves_completed_file(monkeypatch, change):
    actual = index_events.extract
    invocation = 0
    def corrupted(*args, **kw):
        nonlocal invocation
        invocation += 1
        for value in actual(*args, **kw):
            if invocation == 2 and value["object"] == "index_event" and value["line"] == 2:
                if change == "unknown-attribute":
                    value["provenance"].setdefault("native_kind", {})["future"] = "do not discard"
                elif change == "revision":
                    value["provenance"].setdefault("native_kind", {})["revision"] = "b" * 40
                elif change == "null-source":
                    value["provenance"].setdefault("notifications", {})["source"] = None
                else:
                    value.pop("provenance")
            yield value
    patch_claude(monkeypatch, "extract", corrupted)
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
def test_unchanged_native_fields_avoid_repeated_attribute_audit(monkeypatch, changed):
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
                value["provenance"].setdefault("native_kind", {})["rule"] = "changed_rule"
            yield value
    patch_claude(monkeypatch, "extract", observed)
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
    patch_claude(monkeypatch, "provenance_defaults", lambda: defaults)
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
def test_supplied_delta_preserves_bad_proof_rejection(monkeypatch, attribute, bad):
    actual = index_events.extract
    def corrupted(*args, **kw):
        for value in actual(*args, **kw):
            if value["object"] == "index_event":
                value["provenance"].setdefault("native_kind", {})[attribute] = bad
            yield value
    patch_claude(monkeypatch, "extract", corrupted)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        read(request(source(FIXTURES / "index/sizes.jsonl")))


@pytest.mark.parametrize("attribute,bad", [("ref", False), ("ref", 0), ("ref", ""),
                                           ("revision", False), ("revision", 0)])
def test_direct_changes_reject_invalid_envelope_values(monkeypatch, attribute, bad):
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
    patch_claude(monkeypatch, "extract", corrupted)
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
def test_changed_values_cannot_hide_behind_envelope_equality(monkeypatch, attribute):
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
                value["provenance"].setdefault("native_kind", {})[attribute] = 0
            yield value
    patch_claude(monkeypatch, "extract", corrupted)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        read(request(source(FIXTURES / "index/sizes.jsonl")))


@pytest.mark.parametrize("attribute", ["rule", "source", "native_paths", "coverage_keys"])
def test_declarations_reject_overridden_native_values(monkeypatch, attribute):
    class UnusualString(str):
        def __eq__(self, other):
            return True
    defaults = index_events.provenance_defaults()
    array = attribute in {"native_paths", "coverage_keys"}
    defaults["native_kind"][attribute] = [UnusualString("type")] if array else UnusualString("value")
    patch_claude(monkeypatch, "provenance_defaults", lambda: defaults)
    actual = index_events.extract
    def corrupted(*args, **kw):
        for value in actual(*args, **kw):
            if value["object"] == "index_event":
                value["provenance"].setdefault("native_kind", {})[attribute] = [0] if array else 0
            yield value
    patch_claude(monkeypatch, "extract", corrupted)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        read(request(source(FIXTURES / "index/sizes.jsonl")))


def complete_default_event(defaults):
    return {"ref": "file#L1", "decoder": {"revision": "a" * 40},
            "provenance": {field: {**copy.deepcopy(proof), "ref": "file#L1", "revision": "a" * 40}
                           for field, proof in defaults.items()}}


def native_changes_for_full_event(event):
    event = copy.deepcopy(event)
    defaults = index_events.provenance_defaults()
    for field, proof in list(event["provenance"].items()):
        if type(proof.get("revision")) is str and proof["revision"] == event["decoder"]["revision"]:
            proof.pop("revision")
        if type(proof) is dict:
            for name, value in list(proof.items()):
                plain = type(value) is str or (type(value) is list and all(type(v) is str for v in value))
                inherited = event["ref"] if name == "ref" else defaults[field].get(name)
                if plain and (name in defaults[field] or name == "ref") and value == inherited:
                    proof.pop(name)
            if not proof:
                event["provenance"].pop(field)
    return event


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
        index_stream._provenance_encoder(defaults, index_events.PROVENANCE)(native_changes_for_full_event(event))


@pytest.mark.parametrize("field,attribute", [("native_kind", "native_paths"),
                                            ("response.id", "coverage_keys")])
def test_native_list_item_equality_override_cannot_hide_invalid_type(field, attribute):
    defaults = index_events.provenance_defaults()
    event = complete_default_event(defaults)
    event["provenance"][field][attribute][0] = native_equal_override("integer")
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._factor_provenance(event, defaults)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._provenance_encoder(defaults, index_events.PROVENANCE)(native_changes_for_full_event(event))


@pytest.mark.parametrize("field,attribute", [("native_kind", "rule"), ("notifications", "source")])
def test_native_valid_string_override_preserves_full_auditor_delta(field, attribute):
    defaults = index_events.provenance_defaults()
    event = complete_default_event(defaults)
    event["provenance"][field][attribute] = native_equal_override("changed-string")
    expected = {field: {attribute: "changed_rule"}}
    full = index_stream._factor_provenance(event, defaults)
    assert json.loads(json.dumps(full)) == expected
    fast = index_stream._provenance_encoder(defaults, index_events.PROVENANCE)(native_changes_for_full_event(event))
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
        index_stream._provenance_encoder(defaults, index_events.PROVENANCE)(native_changes_for_full_event(event))


def normalize_oracle_wire(values):
    # Compare JSON wire values; native checkpoint mappings may have a None key.
    values = json.loads(json.dumps(values, allow_nan=False))
    for value in values:
        value["decoder"]["revision"] = PROVENANCE_ORACLE["proof_revision"]
        if value["object"] == "file_end":
            states = [value.get("state"), (value.get("restart") or {}).get("seed")]
            for state in states:
                if state:
                    state["index"]["decoder"]["revision"] = PROVENANCE_ORACLE["proof_revision"]
    return values


@pytest.mark.parametrize("route", ["import", "command"])
def test_direct_provenance_changes_expand_to_frozen_full_oracle(tmp_path, route):
    assert old_claude_defaults(pre_oracle_defaults(index_events.provenance_defaults())) == PROVENANCE_ORACLE["declarations"]
    assert set(PROVENANCE_ORACLE["fixtures"]) == {
        str(p.relative_to(FIXTURES)) for p in FIXTURES.rglob("*.jsonl")
        if p.relative_to(FIXTURES).parts[0] not in ("agy", "agy-index")} - POST_ORACLE_FIXTURES
    for name, digest in PROVENANCE_ORACLE["fixtures"].items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest
    from harness_evidence import revision
    command_revision = revision() if route == "command" else None
    pending = []
    def check_command(batch):
        requests = copy.deepcopy([req for req, _, _ in batch])
        for req in requests:
            for file in req["files"]:
                if file.get("state"):
                    file["state"]["index"]["decoder"]["revision"] = command_revision
        result = subprocess.run([str(TOOLS / "harness-evidence"), "decode"],
                                input="".join(json.dumps(req) + "\n" for req in requests),
                                text=True, capture_output=True, env=environment(tmp_path), timeout=120)
        error = batch[-1][2]
        assert (result.returncode != 0) == bool(error), result.stderr
        if error:
            last_error = result.stderr.splitlines()[-1]
            assert last_error.split(":", 1)[0] == error["type"]
            if error["message"].startswith("Claude "):
                assert last_error == error["type"] + ": " + error["message"]
        actual = normalize_oracle_wire([json.loads(line) for line in result.stdout.splitlines()])
        expected = [v for _, rows, _ in batch for v in normalize_oracle_wire(rows)]
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            assert left == right, {key: (left.get(key), right.get(key))
                                   for key in left.keys() | right.keys() if left.get(key) != right.get(key)}
    number = 0
    for case in PROVENANCE_ORACLE["cases"]:
        if route == "import":
            oracle_native_case(case)
        state = None
        for old in case["passes"]:
            number += 1
            if case["schedule"] == "prefix":
                state = None
            req = request(source(FIXTURES / case["fixture"], logical=case["logical"],
                                 size=old["size"], state=state), text=case["text"],
                          roots=[{"harness": "claude-code", "path": "/oracle/.claude/projects"}])
            req["id"] = number
            rows = []
            def consume():
                rows.extend(stream.objects(req, ENVELOPE))
            if old["error"]:
                with oracle_error(old["error"]):
                    consume()
                assert not any(v["object"] in {"file_end", "request_end"} for v in rows)
            else:
                consume()
                state = copy.deepcopy(rows[-2]["state"])
                native = {**state["index"]["native"], "next_line": state["next_line"],
                          "next_offset": state["next_offset"]}
                # The transport supplies initial counters that raw extract has not written yet.
                if native["next_line"] == 1 and native["next_offset"] == 0:
                    native.pop("next_line")
                    native.pop("next_offset")
                assert oracle_hash(native) == old["native_state"], (case, old["through_line"])
            assert rows[0]["side_inputs"] is None
            assert old_claude_defaults(pre_oracle_defaults(rows[0]["provenance_defaults"])) == PROVENANCE_ORACLE["declarations"]
            assert oracle_rows([v for v in rows if v["object"] not in
                                {"file_start", "file_end", "request_end"}],
                               rows[0]["provenance_defaults"]) == old["rows"]
            if route == "command":
                if old["error"]:
                    if pending:
                        check_command(pending)
                        pending.clear()
                    check_command([(req, rows, old["error"])])
                else:
                    pending.append((req, rows, None))
                    if len(pending) == 64:
                        check_command(pending)
                        pending.clear()
    if pending:
        check_command(pending)
    assert number == 9552


def test_frozen_oracle_detects_dropped_identity_parent_and_ref_overrides(monkeypatch):
    actual = index_events.extract
    def dropped(*args, **kw):
        for value in actual(*args, **kw):
            if value["object"] == "index_event":
                value["provenance"].pop("identity.index_session", None)
                value["provenance"].pop("identity.parent", None)
                value["provenance"].pop("identity.subagent", None)
            yield value
    patch_claude(monkeypatch, "extract", dropped)
    case = next(c for c in PROVENANCE_ORACLE["cases"] if c["fixture"] == "index/ownership.jsonl"
                and c["layout"] == "subagent" and c["text"] and c["schedule"] == "prefix")
    with pytest.raises(AssertionError):
        oracle_native_case(case)


def test_native_provenance_constructs_declarations_once_and_only_changed_fields_per_event(monkeypatch):
    preparations, audits, native_audits, native, traversals = [], [], [], [], []
    class CountDeclarations(dict):
        def items(self):
            traversals.append(1)
            return super().items()
    monkeypatch.setattr(index_events, "PROVENANCE", CountDeclarations(index_events.PROVENANCE))
    original_defaults, original_audit, original_extract = (
        index_events.provenance_defaults, index_stream._factor_provenance, index_events.extract)
    def declarations():
        preparations.append(1)
        return original_defaults()
    def audit(event, defaults):
        audits.append(set(event["provenance"]))
        return original_audit(event, defaults)
    def extract(*args, **kw):
        for value in original_extract(*args, **kw):
            if value["object"] == "index_event":
                native.append(copy.deepcopy(value["provenance"]))
            yield value
    patch_claude(monkeypatch, "provenance_defaults", declarations)
    monkeypatch.setattr(index_stream, "_factor_provenance", audit)
    def native_audit(event, defaults):
        native_audits.append(set(event["provenance"]))
        return original_audit(event, defaults)
    monkeypatch.setattr(index_events, "_factor_provenance", native_audit)
    patch_claude(monkeypatch, "extract", extract)
    out = read(request(source(FIXTURES / "index/ownership.jsonl")))
    assert len(native) == 6 and len(preparations) == 1 and len(traversals) == 1
    assert all(len(changes) < 6 for changes in native)
    assert audits[0] == set(index_events.PROVENANCE)
    assert all(len(fields) == 1 for fields in audits[1:])
    assert len(audits) == 1 + sum(map(len, native))
    assert len(native_audits) == sum(map(len, native))
    assert all(len(fields) == 1 for fields in native_audits)
    assert all("provenance" not in v["state"]["index"]["native"]
               for v in out if v["object"] == "file_end")


@pytest.mark.parametrize("change", ["missing-ref", "empty-ref", "null-ref", "int-ref", "revision",
                                   "missing-changes", "null-changes", "list-changes"])
def test_empty_changes_still_validate_provenance_envelope(change):
    encode = index_stream._provenance_encoder(index_events.provenance_defaults(), index_events.PROVENANCE)
    event = {"ref": "file#L1", "decoder": {"revision": "a" * 40}, "provenance": {}}
    assert encode(event) == {}
    if change == "missing-ref":
        event.pop("ref")
    elif change.endswith("ref"):
        event["ref"] = {"empty-ref": "", "null-ref": None, "int-ref": 1}[change]
    elif change == "revision":
        event["decoder"]["revision"] = 1
    elif change == "missing-changes":
        event.pop("provenance")
    else:
        event["provenance"] = None if change == "null-changes" else []
    with pytest.raises(stream.ProtocolError, match="provenance"):
        encode(event)


@pytest.mark.parametrize("attribute,bad", [("future", "unknown"), ("revision", "a" * 40),
    ("native_paths", [0]), ("coverage_keys", [False]), ("basis", "unknown"),
    ("rule", ""), ("source", None), ("source", False), ("ref", "")])
def test_declaration_and_delta_faults_fail_before_projection(attribute, bad):
    encode = index_stream._provenance_encoder(index_events.provenance_defaults(), index_events.PROVENANCE)
    event = {"ref": "file#L1", "decoder": {"revision": "a" * 40},
             "provenance": {"notifications": {attribute: bad}}}
    with pytest.raises(stream.ProtocolError, match="provenance"):
        encode(event)
    event["provenance"] = {"unknown": {"rule": "valid"}}
    with pytest.raises(stream.ProtocolError, match="provenance"):
        encode(event)


def test_direct_native_changes_do_not_alias_pending_identity_state():
    from harness_evidence.lines import Place
    path = FIXTURES / "index/ownership.jsonl"
    first = path.read_bytes().splitlines(keepends=True)[0]
    state = {}
    place = Place("claude-code", "file", None, "explicit", "file", path)
    event = next(index_events.extract([(0, first)], state, place=place, text=True))
    pending = state["identity_facts"]["agent-kid"]["subagent"]
    pending["native_paths"] = ["pending.path"]
    saved = copy.deepcopy(pending)
    event = next(index_events.extract([(len(first), first)], state, place=place, text=True))
    event["provenance"]["identity.subagent"]["native_paths"].append("caller mutation")
    event["provenance"]["identity.subagent"]["rule"] = "caller mutation"
    assert pending == saved
    assert state["identity_facts"]["agent-kid"]["subagent"] == saved


def test_unknown_pending_proof_attribute_cannot_disappear(monkeypatch):
    actual = index_events._identity_subagent
    def unknown(*args, **kw):
        label, proof = actual(*args, **kw)
        proof["future"] = "must not disappear"
        return label, proof
    monkeypatch.setattr(index_events, "_identity_subagent", unknown)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        read(request(source(FIXTURES / "index/ownership.jsonl")))


@pytest.mark.parametrize("fault", ["missing-field", "unknown-field", "missing-attribute", "unknown-attribute"])
def test_declaration_completeness_is_checked_before_file_header(monkeypatch, fault):
    defaults = index_events.provenance_defaults()
    if fault == "missing-field":
        defaults.pop("native_kind")
    elif fault == "unknown-field":
        defaults["unknown"] = copy.deepcopy(defaults["native_kind"])
    elif fault == "missing-attribute":
        defaults["native_kind"].pop("native_paths")
    else:
        defaults["native_kind"]["unknown"] = "must not disappear"
    patch_claude(monkeypatch, "provenance_defaults", lambda: defaults)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        next(stream.objects(request(source(FIXTURES / "index/sizes.jsonl")), ENVELOPE))


@pytest.mark.parametrize("route", ["import", "command"])
def test_direct_changes_late_fault_preserves_completed_files_and_checkpoint(monkeypatch, tmp_path, route):
    path = FIXTURES / "index/sizes.jsonl"
    req = request(source(path), source(path), source(path))
    pristine = read(request(source(path), source(path)))
    if route == "import":
        actual = index_events.extract
        invocation = 0
        def broken(*args, **kw):
            nonlocal invocation
            invocation += 1
            for value in actual(*args, **kw):
                if invocation == 3 and value["object"] == "index_event" and value["line"] == 2:
                    value["provenance"].setdefault("native_kind", {})["future"] = "bad"
                yield value
        patch_claude(monkeypatch, "extract", broken)
        rows = []
        with pytest.raises(stream.ProtocolError, match="provenance"):
            rows.extend(stream.objects(req, ENVELOPE))
    else:
        import sys
        code = '''import sys
sys.path.insert(0,sys.argv[1])
from harness_evidence import index_events
from harness_evidence.__main__ import main
actual=index_events.extract
invocation=0
def broken(*args,**kw):
 global invocation
 invocation+=1
 for value in actual(*args,**kw):
  if invocation==3 and value['object']=='index_event' and value['line']==2:
   value['provenance'].setdefault('native_kind',{})['future']='bad'
  yield value
index_events.extract=broken
sys.exit(main(['decode']))
'''
        result = subprocess.run([sys.executable, "-c", code, str(TOOLS)],
                                input=json.dumps(req) + "\n", text=True, capture_output=True,
                                env=environment(tmp_path), timeout=60)
        assert result.returncode != 0 and "provenance" in result.stderr
        rows = [json.loads(line) for line in result.stdout.splitlines()]
    rows = normalize_oracle_wire(rows)
    pristine = normalize_oracle_wire(pristine)
    assert [v for v in rows if v.get("file") in (0, 1)] == pristine[:-1]
    completed = [v for v in rows if v["object"] == "file_end"]
    assert [v["file"] for v in completed] == [0, 1]
    assert all(v["state"]["next_offset"] == path.stat().st_size for v in completed)
    assert [v["line"] for v in rows if v.get("file") == 2 and v["object"] == "index_event"] == [1]
    assert not any(v["object"] == "request_end" for v in rows)


def test_changed_arrays_and_earlier_refs_are_owned_without_checkpoint_encoding():
    encode = index_stream._provenance_encoder(index_events.provenance_defaults(), index_events.PROVENANCE)
    event = {"ref": "file#L2", "decoder": {"revision": "a" * 40},
             "provenance": {"identity.subagent": {"native_paths": ["earlier.path"], "ref": "file#L1"},
                            "identity.parent": {"ref": "archive:file"}}}
    first = encode(event)
    assert first == event["provenance"]
    first["identity.subagent"]["native_paths"].append("caller")
    assert event["provenance"]["identity.subagent"]["native_paths"] == ["earlier.path"]
    assert encode(event)["identity.subagent"]["native_paths"] == ["earlier.path"]


@pytest.mark.parametrize("location", ["key", "scalar", "item", "array", "dictionary"])
def test_direct_delta_metaclass_operators_do_not_bypass_validation(location):
    class Metaclass(type):
        def __eq__(cls, other):
            raise AssertionError("metaclass equality must not run")
        def __hash__(cls):
            raise AssertionError("metaclass hashing must not run")
    class NativeString(str, metaclass=Metaclass):
        pass
    class NativeList(list, metaclass=Metaclass):
        pass
    class NativeDict(dict, metaclass=Metaclass):
        pass
    change = {"rule": "changed_rule"}
    if location == "key":
        change = {NativeString("rule"): "changed_rule"}
    elif location == "scalar":
        change["rule"] = NativeString("changed_rule")
    elif location == "item":
        change = {"native_paths": [NativeString("changed_path")]}
    elif location == "array":
        change = {"native_paths": NativeList(["changed_path"])}
    else:
        change = NativeDict(change)
    event = {"ref": "file#L1", "decoder": {"revision": "a" * 40}, "provenance": {"native_kind": change}}
    encode = index_stream._provenance_encoder(index_events.provenance_defaults(), index_events.PROVENANCE)
    if location in {"key", "dictionary"}:
        with pytest.raises(stream.ProtocolError, match="provenance"):
            encode(event)
    else:
        assert json.loads(json.dumps(encode(event))) == {"native_kind": json.loads(json.dumps(change))}


@pytest.mark.parametrize("location", ["field", "attribute", "scalar", "item", "dictionary", "array"])
def test_declarations_reject_metaclass_values_before_copying(location):
    class Metaclass(type):
        def __hash__(cls):
            raise AssertionError("invalid declaration must not invoke metaclass hashing")
    class NativeString(str, metaclass=Metaclass):
        pass
    class NativeDict(dict, metaclass=Metaclass):
        pass
    class NativeList(list, metaclass=Metaclass):
        pass
    defaults = index_events.provenance_defaults()
    proof = defaults["native_kind"]
    if location == "field":
        defaults[NativeString("native_kind")] = defaults.pop("native_kind")
    elif location == "attribute":
        proof[NativeString("rule")] = proof.pop("rule")
    elif location == "scalar":
        proof["rule"] = NativeString("rule")
    elif location == "item":
        proof["native_paths"] = [NativeString("type")]
    elif location == "dictionary":
        defaults["native_kind"] = NativeDict(proof)
    else:
        proof["native_paths"] = NativeList(["type"])
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._provenance_encoder(defaults, index_events.PROVENANCE)


@pytest.mark.parametrize("fault", ["scalar", "array-item", "dictionary"])
def test_pending_proof_copy_hooks_cannot_hide_supplied_invalid_metadata(monkeypatch, fault):
    class RepairedScalar:
        def __deepcopy__(self, memo):
            return "is_sidechain"
    class FilteredProof(dict):
        def __deepcopy__(self, memo):
            return {name: value for name, value in self.items() if name != "future"}
    actual = index_events._identity_subagent
    def supplied(*args, **kw):
        label, proof = actual(*args, **kw)
        proof = dict(proof)
        if fault == "scalar":
            proof["rule"] = RepairedScalar()
        elif fault == "array-item":
            proof["native_paths"] = [RepairedScalar()]
        else:
            proof = FilteredProof(proof)
            proof["future"] = "must not disappear"
        return label, proof
    monkeypatch.setattr(index_events, "_identity_subagent", supplied)
    with pytest.raises(stream.ProtocolError, match="provenance"):
        read(request(source(FIXTURES / "index/ownership.jsonl")))


def test_pending_valid_string_metaclass_survives_without_copy_operators(monkeypatch):
    class Metaclass(type):
        def __hash__(cls):
            raise AssertionError("native scalar copying must not invoke metaclass hashing")
    class NativeString(str, metaclass=Metaclass):
        pass
    actual = index_events._identity_subagent
    def supplied(*args, **kw):
        label, proof = actual(*args, **kw)
        proof = {**proof, "rule": NativeString("changed_rule")}
        return label, proof
    monkeypatch.setattr(index_events, "_identity_subagent", supplied)
    out = read(request(source(FIXTURES / "index/ownership.jsonl")))
    assert all(v["provenance"]["identity.subagent"]["rule"] == "changed_rule"
               for v in out if v["object"] == "index_event" and v["eligible"])


@pytest.mark.parametrize("fault", ["subclass", "native-message"])
def test_frozen_error_contract_rejects_new_exception_classes_and_native_messages(fault):
    class UnexpectedError(TypeError):
        pass
    error = {"type": "TypeError", "message": "interpreter wording"} if fault == "subclass" else {
        "type": "ValueError", "message": "Claude explicit native error"}
    with pytest.raises(AssertionError):
        with oracle_error(error):
            if fault == "subclass":
                raise UnexpectedError("interpreter wording")
            raise ValueError("Claude explicit native error changed")


@pytest.mark.parametrize("attribute", ["native_paths", "coverage_keys"])
@pytest.mark.parametrize("behavior", ["invalid-iteration", "different-iteration", "suppress-change", "force-change"])
def test_pending_array_behavior_reaches_original_audit_before_copy(monkeypatch, attribute, behavior):
    defaults = index_events.provenance_defaults()
    inherited = defaults["identity.subagent"][attribute]
    class InvalidIteration(list):
        def __iter__(self):
            return iter([0])
    class DifferentIteration(list):
        def __iter__(self):
            return iter(["audited.path"])
    class SuppressChange(DifferentIteration):
        def __ne__(self, other):
            return False
    class ForceChange(list):
        def __ne__(self, other):
            return True
    kind = {"invalid-iteration": InvalidIteration, "different-iteration": DifferentIteration,
            "suppress-change": SuppressChange, "force-change": ForceChange}[behavior]
    supplied_array = kind(inherited if behavior == "force-change" else ["stored.path"])
    actual = index_events._identity_subagent
    pending = []
    def supplied(*args, **kw):
        label, proof = actual(*args, **kw)
        pending.append(supplied_array)
        return label, {**proof, attribute: supplied_array}
    monkeypatch.setattr(index_events, "_identity_subagent", supplied)
    path = FIXTURES / "index/ownership.jsonl"
    if behavior == "invalid-iteration":
        with pytest.raises(stream.ProtocolError, match="arrays must contain strings"):
            read(request(source(path)))
        return
    out = read(request(source(path)))
    native = [v for v in out if v["object"] == "index_event" and v["eligible"]]
    assert native
    for event in native:
        delta = event["provenance"]["identity.subagent"]
        if behavior == "suppress-change":
            assert attribute not in delta
        else:
            assert delta[attribute] == (inherited if behavior == "force-change" else ["audited.path"])
            delta[attribute].append("caller mutation")
    assert all(list.copy(value) == (inherited if behavior == "force-change" else ["stored.path"])
               for value in pending)


@pytest.mark.parametrize("attribute", ["native_paths", "coverage_keys"])
@pytest.mark.parametrize("state_location", ["dictionary", "slots"])
def test_native_array_projection_uses_operator_state_without_copy_hooks(monkeypatch, attribute, state_location):
    class Metaclass(type):
        def __eq__(cls, other):
            raise AssertionError("metaclass equality")
        def __hash__(cls):
            raise AssertionError("metaclass hash")
    class Stateful(list, metaclass=Metaclass):
        def __iter__(self):
            return iter(self.semantic)
        def __ne__(self, other):
            return self.changed
        def __copy__(self):
            raise AssertionError("copy hook")
        def __deepcopy__(self, memo):
            raise AssertionError("deepcopy hook")
        def __reduce_ex__(self, protocol):
            raise AssertionError("reduce hook")
        def __getstate__(self):
            raise AssertionError("state hook")
    class Slotted(Stateful):
        __slots__ = ("semantic", "changed")
    array = (Slotted if state_location == "slots" else Stateful)(["stored.path"])
    array.semantic, array.changed = ["audited.path"], True
    actual = index_events._identity_subagent
    def supplied(*args, **kw):
        label, proof = actual(*args, **kw)
        return label, {**proof, attribute: array}
    monkeypatch.setattr(index_events, "_identity_subagent", supplied)
    from harness_evidence.lines import Place
    path = FIXTURES / "index/ownership.jsonl"
    raw = path.read_bytes().splitlines(keepends=True)[0]
    place = Place("claude-code", "file", None, "explicit", "file", path)
    event = next(index_events.extract([(0, raw)], {}, place=place, text=True))
    snapshot = event["provenance"]["identity.subagent"][attribute]
    assert snapshot is not array and snapshot == ["audited.path"]
    list.append(snapshot, "caller mutation")
    assert list.copy(array) == ["stored.path"]
    event["decoder"] = ENVELOPE["decoder"]
    encoded = index_stream._provenance_encoder(index_events.provenance_defaults(), index_events.PROVENANCE)(event)
    assert encoded["identity.subagent"][attribute] == ["audited.path", "caller mutation"]
    again = next(index_events.extract([(0, raw)], {}, place=place, text=True))
    assert again["provenance"]["identity.subagent"][attribute] == ["audited.path"]


@pytest.mark.parametrize("attribute", ["native_paths", "coverage_keys"])
def test_native_array_identity_sensitive_comparison_precedes_materialization(monkeypatch, attribute):
    class IdentitySensitive(list):
        def __ne__(self, other):
            return self is supplied_array
        def __iter__(self):
            return iter(["audited.path"])
    supplied_array = IdentitySensitive(["stored.path"])
    actual = index_events._identity_subagent
    def supplied(*args, **kw):
        label, proof = actual(*args, **kw)
        return label, {**proof, attribute: supplied_array}
    monkeypatch.setattr(index_events, "_identity_subagent", supplied)
    out = read(request(source(FIXTURES / "index/ownership.jsonl")))
    eligible = [v for v in out if v["object"] == "index_event" and v["eligible"]]
    assert eligible
    assert all(v["provenance"]["identity.subagent"][attribute] == ["audited.path"] for v in eligible)
    assert list.copy(supplied_array) == ["stored.path"]


def test_framing_preserves_explicit_precomputed_updates_without_second_prune():
    defaults = index_events.provenance_defaults()
    event = {"ref": "file#L1", "decoder": {"revision": "a" * 40},
             "provenance": {"identity.subagent": copy.deepcopy(defaults["identity.subagent"])}}
    encode = index_stream._provenance_encoder(defaults, index_events.PROVENANCE)
    actual = encode(event)
    assert actual == event["provenance"]
    actual["identity.subagent"]["native_paths"].append("caller")
    assert event["provenance"]["identity.subagent"]["native_paths"] == defaults["identity.subagent"]["native_paths"]


@pytest.mark.parametrize("attribute", ["basis", "rule"])
def test_native_scalar_comparison_decision_survives_framing(monkeypatch, attribute):
    class IdentitySensitive(str):
        def __ne__(self, other):
            return self is supplied_value
    inherited = index_events.provenance_defaults()["identity.subagent"][attribute]
    supplied_value = IdentitySensitive(inherited)
    actual = index_events._identity_subagent
    def supplied(*args, **kw):
        label, proof = actual(*args, **kw)
        return label, {**proof, attribute: supplied_value}
    monkeypatch.setattr(index_events, "_identity_subagent", supplied)
    out = read(request(source(FIXTURES / "index/ownership.jsonl")))
    eligible = [v for v in out if v["object"] == "index_event" and v["eligible"]]
    assert eligible
    assert all(attribute in v["provenance"]["identity.subagent"]
               and v["provenance"]["identity.subagent"][attribute] == inherited for v in eligible)


def test_framing_validates_owned_values_without_replaying_update_comparison():
    class ComputedArray(list):
        def __iter__(self):
            return iter(["computed.path"])
        def __ne__(self, other):
            raise AssertionError("update presence is already computed")
    event = {"ref": "file#L1", "decoder": {"revision": "a" * 40},
             "provenance": {"identity.subagent": {"native_paths": ComputedArray(["stored.path"])}}}
    encoded = index_stream._provenance_encoder(index_events.provenance_defaults(), index_events.PROVENANCE)(event)
    assert encoded == {"identity.subagent": {"native_paths": ["computed.path"]}}


def test_framing_checks_literal_basis_after_owning_supplied_string():
    class InvalidBasis(str):
        def __hash__(self):
            return hash("native")
        def __eq__(self, other):
            return True
    event = {"ref": "file#L1", "decoder": {"revision": "a" * 40},
             "provenance": {"identity.subagent": {"basis": InvalidBasis("unsupported")}}}
    with pytest.raises(stream.ProtocolError, match="provenance"):
        index_stream._provenance_encoder(index_events.provenance_defaults(), index_events.PROVENANCE)(event)


def test_native_class_spoofed_scalar_fails_literal_framing(monkeypatch):
    class NativeString(str):
        @property
        def __class__(self):
            return list
    value = NativeString("kept_rule")
    defaults = index_events.provenance_defaults()
    proof = {**defaults["identity.subagent"], "ref": "file#L1", "revision": "a" * 40,
             "rule": value}
    event = {"ref": "file#L1", "decoder": {"revision": "a" * 40},
             "provenance": {"identity.subagent": proof}}
    # The original auditor materializes this injected object as an invalid scalar array.
    audited = index_stream._factor_provenance(event, {"identity.subagent": defaults["identity.subagent"]})
    assert audited["identity.subagent"]["rule"] == list("kept_rule")
    actual = index_events._identity_subagent
    def supplied(*args, **kw):
        label, pending = actual(*args, **kw)
        return label, {**pending, "rule": value}
    monkeypatch.setattr(index_events, "_identity_subagent", supplied)
    with pytest.raises(stream.ProtocolError, match="basis, rule, ref or revision"):
        read(request(source(FIXTURES / "index/ownership.jsonl")))
