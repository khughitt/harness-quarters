"""Protocol framing, privacy, source failures and moved-reader conformance."""
import json
import hashlib
import io
from pathlib import Path
import select
import subprocess
import tomllib

import pytest

from harness_evidence_testing import FIXTURES, path_of
from harness_evidence import records
from harness_evidence.lines import Place, detect_format

TOOLS = Path(__file__).resolve().parent


def environment(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home),
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def entry(source_path, **fields):
    return {"path": str(source_path), "size": source_path.stat().st_size, **fields}


def request(files, **fields):
    return {"id": 1, "files": files, "roots": [], "context": [],
            "cross_file": False, "text": False, "raw": False, **fields}


def run_raw(tmp_path, text):
    return subprocess.run([str(TOOLS / "harness-evidence"), "decode"], input=text,
                          capture_output=True, text=True, env=environment(tmp_path), timeout=60)


def invoke(tmp_path, req):
    proc = run_raw(tmp_path, json.dumps(req) + "\n")
    assert proc.returncode == 0, proc.stderr
    return [strict_json(line) for line in proc.stdout.splitlines()]


def strict_json(value):
    def reject(token):
        raise ValueError("non-JSON numeric token: " + token)
    return json.loads(value, parse_constant=reject)


@pytest.mark.parametrize("number", [float("nan"),float("inf"),float("-inf")])
def test_wire_serializer_refuses_nonfinite_values_even_if_a_producer_regresses(number):
    from harness_evidence.stream import serialized
    with pytest.raises(ValueError):
        serialized({"nested":[number]})


def end(output, file=0):
    return next(o for o in output if o["object"] == "file_end" and o["file"] == file)


@pytest.mark.parametrize("harness,prefix,first,want,rule", [
    ("claude", [{"type":"user","sessionId":"side","isSidechain":True},
                {"type":"user","sessionId":7}], {"type":"user","sessionId":"different"}, "different", "session_id"),
    ("claude", [], {"type":"user","sessionId":""}, "", "session_id"),
    ("codex", [], {"type":"session_meta","payload":{"id":"first"}}, "first", "session_meta"),
    ("codex", [], {"type":"session_meta","payload":{"id":7}}, None, "session_meta"),
    ("codex", [], {"type":"session_meta","payload":[]}, None, "session_meta"),
    ("codex", [], {"type":"session_meta","payload":{"id":""}}, None, "session_meta"),
])
@pytest.mark.parametrize("number", [3, 50, 51])
def test_recorded_identity_preserves_first_native_observation_and_position(tmp_path,harness,prefix,first,want,rule,number):
    source = tmp_path / "c0000000-0000-4000-8000-00000000000a.jsonl"
    before = b"".join((json.dumps(row)+"\n").encode() for row in prefix)
    before += b"bad json\n" * (number-len(prefix)-1)
    raw = (json.dumps(first)+"\n").encode()
    later = {"type":"session_meta","payload":{"id":"later"}} if harness=="codex" \
        else {"type":"user","sessionId":"later"}
    source.write_bytes(before+raw+(json.dumps(later)+"\n").encode())
    output = invoke(tmp_path, request([entry(source)], raw=True))
    header = next(o["header"] for o in output if o["object"]=="session")
    assert header["recorded_identity"] == {"session":want,"line":number,"ref":f"file:{source}#L{number}",
        "sha256":hashlib.sha256(raw).hexdigest(),"basis":"native","rule":rule}
    if harness=="claude":
        assert header["session"] == source.stem
        assert header["identity_basis"] == "file_name_unconfirmed"
    # The historical <=50-line projection belongs to the consumer, not the decoder.
    assert (header["recorded_identity"]["line"] <= 50) == (number <= 50)


@pytest.mark.parametrize("raw", [b'{"type":"session_meta","payload":{"id":"cut"}}',
                                  b'{"type":"user","sessionId":"cut"}'])
def test_recorded_identity_uses_captured_final_physical_line(tmp_path,raw):
    source = tmp_path / "partial.jsonl"
    source.write_bytes(raw)
    output = invoke(tmp_path, request([entry(source)]))
    header = next(o["header"] for o in output if o["object"]=="session")
    assert header["recorded_identity"]["session"] == "cut"
    assert header["recorded_identity"]["sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("content", [b'unknown\n', b'{"type":"user","sessionId":7}\n',
                                       b'{"type":"user","sessionId":"side","isSidechain":true}\n',
                                       b'{"type":"system","session_id":"sdk","subtype":"init"}\n'])
def test_no_qualifying_native_identity_is_explicit_null(tmp_path,content):
    source = tmp_path / "none.jsonl"
    source.write_bytes(content)
    output = invoke(tmp_path, request([entry(source)]))
    assert next(o["header"] for o in output if o["object"]=="session")["recorded_identity"] is None


@pytest.mark.parametrize("cross_file", [False,True])
@pytest.mark.parametrize("metadata", [{"model":"sonnet"}, {}, {"model":7}, {"model":""}, [], None])
def test_child_sidecar_requested_model_after_copy_settlement(tmp_path,cross_file,metadata):
    root = tmp_path / ".claude/projects"
    directory = root / "project/session/subagents"
    directory.mkdir(parents=True)
    source = directory / "agent-child.jsonl"
    source.write_text('{"type":"assistant","sessionId":"parent","agentId":"child","message":{"model":"runtime","content":"hello"}}\n')
    sidecar = source.with_suffix(".meta.json")
    if metadata is not None:
        sidecar.write_text(json.dumps(metadata))
    output = invoke(tmp_path,request([entry(source)],cross_file=cross_file,
        roots=[{"harness":"claude-code","path":str(root)}]))
    models = next(o["header"]["models"] for o in output if o["object"]=="session")
    expected = [{"value":"runtime","basis":"runtime","ref":"claude:projects/project/session/subagents/agent-child.jsonl#L1"}]
    if metadata == {"model":"sonnet"}:
        expected.append({"value":"sonnet","basis":"requested","ref":"claude:projects/project/session/subagents/agent-child.meta.json"})
    assert models == expected
    # Explicit-store captures cannot consult adjacent metadata.
    explicit = invoke(tmp_path,request([entry(source)]))
    assert [m["basis"] for o in explicit if o["object"]=="session" for m in o["header"]["models"]] == ["runtime"]


@pytest.mark.parametrize("harness", ["claude-code", "codex"])
@pytest.mark.parametrize("content", [b'{}\n', b'{"type":"system","session_id":"sdk","subtype":"init"}\n'])
def test_store_uses_established_harness_while_explicit_uses_signature(tmp_path,harness,content):
    root = tmp_path / "store"
    source = root / "session/subagents/agent-x.jsonl"
    source.parent.mkdir(parents=True)
    source.write_bytes(content)
    output = invoke(tmp_path,request([entry(source)],roots=[{"harness":harness,"path":str(root)}]))
    assert end(output)["status"] == "ok"
    assert output[0]["harness"] == harness
    header = next(o["header"] for o in output if o["object"]=="session")
    if harness == "claude-code":
        assert header["session"] == "agent-x" and header["subagent"]
    else:
        assert header["session"] is None and "subagent" not in header
    assert next(o for o in output if o["object"]=="record")["role"] in {"unknown","metadata"}
    record = next(o for o in output if o["object"]=="record")
    assert record["sha256"] == hashlib.sha256(content).hexdigest()
    assert record["line"] == 1 and record["ref"].endswith("#L1")
    explicit = invoke(tmp_path,request([entry(source)]))
    if content == b'{}\n':
        assert end(explicit)["status"] == "unknown_format"
    else:
        assert end(explicit)["status"] == "ok"
        assert next(o["header"] for o in explicit if o["object"]=="session")["session"] == "sdk"


def test_malformed_child_sidecar_is_optional_and_duplicate_requested_model_keeps_transcript_ref(tmp_path):
    root = tmp_path / "projects"
    source = root / "project/session/subagents/agent-x.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text('{"type":"user","sessionId":"session","requestedModel":"sonnet"}\n')
    req = request([entry(source)],roots=[{"harness":"claude-code","path":str(root)}])
    for metadata in ('invalid json', '{"model":"sonnet"}'):
        source.with_suffix(".meta.json").write_text(metadata)
        output = invoke(tmp_path,req)
        models = next(o["header"]["models"] for o in output if o["object"]=="session")
        assert models == [{"value":"sonnet","basis":"requested",
                           "ref":f"{tmp_path.name}:projects/project/session/subagents/agent-x.jsonl#L1"}]


def test_sidecar_requested_model_survives_duplicate_transcript_settlement(tmp_path):
    roots, sources = [], []
    for home in (".claude", ".claude-work"):
        root = tmp_path / home / "projects"
        source = root / "p/parent/subagents/agent-child.jsonl"
        source.parent.mkdir(parents=True)
        source.write_text('{"type":"assistant","sessionId":"parent","agentId":"child","message":{"model":"runtime","content":"hello"}}\n')
        source.with_suffix(".meta.json").write_text('{"model":"sonnet"}')
        roots.append({"harness":"claude-code","path":str(root)})
        sources.append(entry(source))
    output = invoke(tmp_path,request(sources,roots=roots,cross_file=True))
    assert any(o.get("copy")=="duplicate_file" for o in output)
    copied = next(o["file"] for o in output if o.get("copy")=="duplicate_file")
    header = next(o["header"] for o in output if o["object"]=="session" and o["file"]==copied)
    home = ("claude", "claude-work")[copied]
    assert header["models"] == [{"value":"sonnet","basis":"requested",
        "ref":f"{home}:projects/p/parent/subagents/agent-child.meta.json"}]


def test_each_file_is_framed_and_counted(tmp_path):
    output = invoke(tmp_path, request([entry(FIXTURES / path_of(n)) for n in ("CA", "XA")]))
    for i in (0, 1):
        objects = [o for o in output if o.get("file") == i]
        assert objects[0]["object"] == "file_start"
        assert objects[-1]["object"] == "file_end"
        assert objects[-1]["count"] == len(objects) - 2
        assert objects[-1]["status"] == "ok"
        assert len({o["key"] for o in objects}) == len(objects)
        assert all(o["schema"] == "harness-evidence/1" and o["request"] == 1
                   and all(o["decoder"].values()) for o in objects)
    assert output[-1] == {"schema": "harness-evidence/1", "decoder": output[0]["decoder"],
                          "object": "request_end", "request": 1, "files": 2}


def test_text_and_raw_are_independent_opt_ins(tmp_path):
    path = tmp_path / "rollout.jsonl"
    native = [
        {"type": "session_meta", "payload": {"id": "test"}},
        {"type": "response_item", "payload": {"type": "function_call", "name": "exec_command",
         "call_id": "c", "arguments": '{"cmd":"SECRET_COMMAND"}'}},
        {"type": "event_msg", "payload": {"type": "item_completed", "item": {
         "type": "CommandExecution", "command": "SECRET_COMMAND", "exit_code": 0}}},
        {"type": "event_msg", "payload": {"type": "task_complete",
         "last_agent_message": "SECRET_ANSWER"}},
    ]
    path.write_text("".join(json.dumps(o) + "\n" for o in native))
    output = invoke(tmp_path, request([entry(path)]))
    assert "SECRET" not in json.dumps(output)
    assert all("text" not in o and "raw" not in o and "turn_end_message" not in o
               for o in output if o["object"] == "record")
    output = invoke(tmp_path, request([entry(path)], text=True))
    assert any(o.get("turn_end_message") == "SECRET_ANSWER" for o in output)
    assert "SECRET_COMMAND" in json.dumps(output)
    assert not any("raw" in o for o in output)
    output = invoke(tmp_path, request([entry(path)], raw=True))
    assert any("SECRET_COMMAND" in o.get("raw", "") for o in output)
    assert not any("text" in o for o in output)


@pytest.mark.parametrize("sample", [s for s in tomllib.loads((FIXTURES / "CATALOGUE.toml").read_text())["sample"]
                                    if s.get("profile") != "index"],
                         ids=lambda s: s["path"])
def test_records_equal_moved_readers(tmp_path, sample):
    path = FIXTURES / sample["path"]
    fmt = detect_format(path, path.stat().st_size)
    harness = "codex" if fmt == "codex" else "claude-code"
    place = Place(harness, "file", None, "explicit", str(path), path)
    read = records.codex_read(place, path.stat().st_size, lambda _: None) if fmt == "codex" else \
        (records.sdk_read if fmt == "sdk" else records.claude_read)(place, path.stat().st_size)
    output = invoke(tmp_path, request([entry(path)], text=True))
    assert output[0]["harness_version"] == (None if sample["version"] == "unknown" else sample["version"])
    actual = [o for o in output if o["object"] == "record"]
    expected = [{k: v for k, v in r.items() if not k.startswith("_")} for r in read.records]
    assert [{k: o[k] for k in r} for o, r in zip(actual, expected)] == expected
    assert len(actual) == len(expected)


def test_source_failures_do_not_abort_other_files(tmp_path):
    missing = tmp_path / "missing"
    unknown = tmp_path / "unknown.jsonl"
    unknown.write_text('{"type":"journal"}\n')
    output = invoke(tmp_path, request([{"path": str(missing), "size": 1},
        {"path": str(tmp_path), "size": 1}, entry(unknown), entry(FIXTURES / path_of("CA"))]))
    assert [end(output, i)["status"] for i in range(4)] == ["vanished", "unreadable", "unknown_format", "ok"]


@pytest.mark.parametrize("mutation", [
    {"extra": True}, {"id": True}, {"text": 1}, {"files": [{"path": 3}]},
    {"files": [{"path": "x", "size": -1}]}, {"roots": [{"harness": "agy", "path": "x"}]},
    {"files": [{"path": "x", "size": 1, "state": {}}]},
    {"files": [{"path": "x", "size": 1, "extra": 2}]},
    {"context": [2]}, {"cross_file": None},
])
def test_protocol_faults_exit_2(tmp_path, mutation):
    proc = run_raw(tmp_path, json.dumps({**request([]), **mutation}) + "\n")
    assert proc.returncode == 2 and proc.stdout == ""
    assert len(proc.stderr.splitlines()) == 1


@pytest.mark.parametrize("body", ["{\n", "[]\n", "NaN\n", "\n"])
def test_bad_json_is_protocol_fault(tmp_path, body):
    proc = run_raw(tmp_path, body)
    assert proc.returncode == 2 and len(proc.stderr.splitlines()) == 1


def test_multiple_requests_flush_before_stdin_eof(tmp_path):
    with subprocess.Popen([str(TOOLS / "harness-evidence"), "decode"], env=environment(tmp_path),
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True) as proc:
        try:
            for identity in (7, 8):
                proc.stdin.write(json.dumps(request([], id=identity)) + "\n")
                proc.stdin.flush()
                assert select.select([proc.stdout], [], [], 10)[0], "request response was buffered"
                assert json.loads(proc.stdout.readline())["request"] == identity
            proc.stdin.close()
            assert proc.wait(timeout=10) == 0
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


def test_huge_line_and_lone_surrogate_are_valid_json(tmp_path):
    path = tmp_path / "huge.jsonl"
    path.write_text(json.dumps({"type": "user", "sessionId": "s", "message": {
        "content": "x" * (20 * 1024 * 1024) + "\ud800"}}) + "\n")
    output = invoke(tmp_path, request([entry(path)], text=True, raw=True))
    assert end(output)["status"] == "ok"
    assert len(next(o["text"] for o in output if o["object"] == "record")) > 20 * 1024 * 1024


def test_logical_path_controls_identity_refs_and_links(tmp_path):
    logical = tmp_path / ".claude" / "projects" / "project" / "parent" / "subagents" / "agent-child.jsonl"
    physical = tmp_path / "capture.jsonl"
    physical.write_text('{"type":"user","sessionId":"parent","message":{"content":"hello"}}\n')
    root = tmp_path / ".claude" / "projects"
    output = invoke(tmp_path, request([entry(physical, path=str(logical), read_path=str(physical))],
        roots=[{"harness": "claude-code", "path": str(root)}]))
    session = next(o for o in output if o["object"] == "session")
    assert session["header"]["parent"] == "parent"
    assert session["links"][0]["target"] == "parent"
    assert next(o["ref"] for o in output if o["object"] == "record").startswith("claude:projects/")


@pytest.mark.parametrize("cross_file", [False, True])
@pytest.mark.parametrize("fact", ["models", "link"])
@pytest.mark.parametrize("physical_meta,logical_meta", [
    ({"model":"sonnet","toolUseId":"physical-call"}, None),
    ({"model":"sonnet","toolUseId":"physical-call"}, {"model":"opus","toolUseId":"stale-call"}),
    (None, {"model":"opus","toolUseId":"stale-call"}),
    (None, None),
])
def test_replayed_child_metadata_follows_physical_source_with_logical_refs(tmp_path,cross_file,fact,physical_meta,logical_meta):
    root = tmp_path / ".claude/projects"
    logical = root / "project/parent/subagents/agent-child.jsonl"
    physical = tmp_path / "archive/parent/subagents/transcript-copy.jsonl"
    physical.parent.mkdir(parents=True)
    raw = b'{"type":"assistant","sessionId":"parent","agentId":"child","message":{"model":"runtime","content":"hello"}}\n'
    physical.write_bytes(raw)
    for source, metadata in ((logical,logical_meta),(physical,physical_meta)):
        if metadata is not None:
            source.parent.mkdir(parents=True,exist_ok=True)
            (source.parent / "agent-child.meta.json").write_text(json.dumps(metadata))
    assert not logical.exists()
    output = invoke(tmp_path,request([entry(physical,path=str(logical),read_path=str(physical))],
        roots=[{"harness":"claude-code","path":str(root)}],cross_file=cross_file,raw=True))
    assert output[-1]["object"] == "request_end" and end(output)["status"] == "ok"
    session = next(o for o in output if o["object"]=="session")
    header = session["header"]
    assert header["session"] == "agent-child" and header["parent"] == "parent"
    prefix = "claude:projects/project/parent/subagents/agent-child"
    expected = [{"value":"runtime","basis":"runtime","ref":prefix+".jsonl#L1"}]
    if physical_meta:
        expected.append({"value":"sonnet","basis":"requested","ref":prefix+".meta.json"})
    if fact == "models":
        assert header["models"] == expected
    child = next(link for link in session["links"] if link["kind"]=="child_to_parent")
    expected_link = {"kind":"child_to_parent","target":"parent","basis":"convention",
                     "rule":"path","ref":prefix+".jsonl"}
    if physical_meta:
        expected_link["call"] = {"id":"physical-call","ref":None}
    if fact == "link":
        assert child == expected_link
    record = next(o for o in output if o["object"]=="record")
    assert record["ref"] == prefix+".jsonl#L1"
    assert record["raw"].encode() == raw and record["sha256"] == hashlib.sha256(raw).hexdigest()
    # An explicit capture with read_path still cannot consult either sidecar.
    explicit = invoke(tmp_path,request([entry(physical,path=str(logical),read_path=str(physical))]))
    session = next(o for o in explicit if o["object"]=="session")
    assert [m["basis"] for m in session["header"]["models"]] == ["runtime"]
    assert all("call" not in link for link in session["links"])


def test_cross_file_copies_and_context_fork_resolution(tmp_path):
    parent = tmp_path / ".codex" / "sessions" / "parent.jsonl"
    parent.parent.mkdir(parents=True)
    parent.write_text('{"type":"session_meta","payload":{"id":"parent"}}\n'
                      '{"type":"event_msg","payload":{"type":"task_started","turn_id":"inherited"}}\n')
    child = parent.with_name("child.jsonl")
    child.write_text('{"type":"session_meta","payload":{"id":"child"}}\n'
                     '{"type":"session_meta","payload":{"id":"parent"}}\n'
                     '{"type":"event_msg","payload":{"type":"task_started","turn_id":"inherited"}}\n')
    archived = tmp_path / ".codex" / "archived_sessions" / "child.jsonl"
    archived.parent.mkdir()
    archived.write_bytes(child.read_bytes())
    roots = [{"harness": "codex", "path": str(p)} for p in (parent.parent, archived.parent)]
    output = invoke(tmp_path, request([entry(child)], roots=roots))
    assert next(o for o in output if o["object"] == "session")["unresolved_forks"] == ["parent"]
    output = invoke(tmp_path, request([entry(child), entry(archived)], roots=roots,
                                     context=[str(parent)], cross_file=True))
    assert all(o["unresolved_forks"] == [] for o in output if o["object"] == "session")
    copied = [o for o in output if o.get("copy") == "duplicate_file"]
    assert copied and all(set(o["copy_scope"]) == {str(child), str(archived)} for o in copied)
    assert all((o["copy_basis"],o["copy_rule"])==("convention","identity_line_match") for o in copied)
    assert not any(o.get("path") == str(parent) for o in output)
    assert any(o.get("copy") == "fork_history" for o in output)
    state = end(output, 1)["state"]
    reordered = invoke(tmp_path, request([entry(archived, state=state), entry(child)], roots=roots,
                                         context=[str(parent)], cross_file=True))
    assert reordered[0]["replaces"] == {"from_line": state["next_line"]}


def test_requested_text_preserves_nested_native_public_values(tmp_path):
    path = tmp_path / "native.jsonl"
    native = {"nested": {"_native": "kept", "text": "content"}}
    path.write_text(json.dumps({"type": "user", "sessionId": "s", "promptSource": native,
                               "message": {"content": "hello"}}) + "\n")
    output = invoke(tmp_path, request([entry(path)], text=True))
    assert next(o["prompt_source"] for o in output if o["object"] == "record") == native


def test_unencodable_source_path_is_framed_unreadable(tmp_path):
    output = invoke(tmp_path, request([{"path": str(tmp_path / "\ud800"), "size": 1}]))
    assert end(output)["status"] == "unreadable"
    assert output[-1]["object"] == "request_end"


def test_byte_bound_larger_than_machine_integer_reads_available_prefix(tmp_path):
    path = FIXTURES / path_of("CA")
    whole = invoke(tmp_path, request([entry(path)]))
    output = invoke(tmp_path, request([entry(path, size=10**100)]))
    assert output == whole


def test_live_duplicate_copy_original_uses_root_priority_then_logical_relpath(tmp_path):
    first_root = tmp_path / ".codex-work" / "sessions"
    second_root = tmp_path / ".codex" / "sessions"
    first_root.mkdir(parents=True)
    second_root.mkdir(parents=True)
    source = '{"type":"session_meta","payload":{"id":"same"}}\n'
    a = first_root / "a.jsonl"
    b = first_root / "b.jsonl"
    c = second_root / "0.jsonl"
    for path in (a, b, c):
        path.write_text(source)
    roots = [{"harness": "codex", "path": str(p)} for p in (first_root, second_root)]
    initial = invoke(tmp_path, request([entry(c), entry(b), entry(a)], roots=roots, cross_file=True))
    originals = [o for o in initial if o["object"] == "record" and "copy" not in o]
    assert len(originals) == 1 and originals[0]["file"] == 2
    state = end(initial, 1)["state"]
    reordered = invoke(tmp_path, request([entry(b, state=state), entry(a), entry(c)], roots=roots,
                                         cross_file=True))
    assert reordered[0]["replaces"] == {"from_line": state["next_line"]}


@pytest.mark.parametrize("sidechain,path_child,expected", [
    (False, True, "convention"), (True, False, "native"), (False, False, "heuristic"),
    (True, True, "native"),
])
def test_claude_header_subagent_basis_from_raw_evidence(tmp_path, sidechain, path_child, expected):
    path = tmp_path / ("subagents/agent-child.jsonl" if path_child else "session.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type":"user", "sessionId":"s", "timestamp":"2026-01-01",
                               "isSidechain":sidechain, "message":{"content":"hello"}}) + "\n")
    place = Place("claude-code", "file", None, "explicit", str(path), path)
    direct = records.claude_read(place, path.stat().st_size).header
    assert direct["subagent_basis"] == expected
    assert direct["subagent"] == (sidechain or path_child)
    output = invoke(tmp_path, request([entry(path)]))
    assert next(o["header"] for o in output if o["object"] == "session")["subagent_basis"] == expected


@pytest.mark.parametrize("metadata,child,basis", [
    ({"parent_thread_id":"parent"}, True, "native"),
    ({"source":{"subagent":{"thread_spawn":{"parent_thread_id":"parent"}}}}, True, "native"),
    ({"thread_source":"user"}, False, "native"),
    ({}, False, "heuristic"),
])
def test_codex_header_child_basis_from_raw_evidence(tmp_path, metadata, child, basis):
    path = tmp_path / "rollout.jsonl"
    path.write_text(json.dumps({"type":"session_meta", "payload":{"id":"thread", **metadata}}) + "\n")
    place = Place("codex", "file", None, "explicit", str(path), path)
    direct = records.codex_read(place, path.stat().st_size, lambda _: None).header
    assert direct["child_basis"] == basis and direct["child"] == child
    output = invoke(tmp_path, request([entry(path)]))
    header = next(o["header"] for o in output if o["object"] == "session")
    assert header["child_basis"] == basis and header["child"] == child


def test_codex_missing_metadata_keeps_heuristic_negative_only_in_typed_reader(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('{"type":"event_msg","payload":{"type":"task_started","turn_id":"t"}}\n')
    place = Place("codex", "file", None, "explicit", str(path), path)
    header = records.codex_read(place, path.stat().st_size, lambda _: None).header
    assert header["child"] is False and header["child_basis"] == "heuristic"
    output = invoke(tmp_path, request([entry(path)]))
    header = next(o["header"] for o in output if o["object"] == "session")
    assert "child" not in header and "child_basis" not in header


def test_abort_reason_is_metadata_when_text_is_disabled(tmp_path):
    path = tmp_path / "abort.jsonl"
    path.write_text('{"type":"session_meta","payload":{"id":"thread"}}\n'
                    '{"type":"event_msg","payload":{"type":"turn_aborted","reason":"interrupt"}}\n')
    output = invoke(tmp_path, request([entry(path)]))
    abort = next(o for o in output if o.get("kind") == "event_msg/turn_aborted")
    assert abort["abort_reason"] == "interrupt" and "text" not in abort


def test_text_opt_out_preserves_native_metadata_dictionary_keys(tmp_path):
    path = tmp_path / "uuid-keys.jsonl"
    ids = ["_native", "text", "command"]
    path.write_text("".join(json.dumps({"type":"user", "sessionId":"s", "uuid":uuid,
                                       "message":{"content":"hello"}}) + "\n" for uuid in ids))
    output = invoke(tmp_path, request([entry(path)]))
    header = next(o["header"] for o in output if o["object"] == "session")
    assert header["uuids"] == {uuid:i for i,uuid in enumerate(ids,1)}


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
@pytest.mark.parametrize("location", ["exit", "nested_execution", "call_id", "prompt_source"])
@pytest.mark.parametrize("cross_file", [False, True])
def test_nonfinite_source_numbers_are_unparsed_and_batch_continues(tmp_path, token, location, cross_file):
    if location in {"exit", "nested_execution"}:
        first = {"type":"session_meta", "payload":{"id":"s"}}
        item = {"type":"CommandExecution", "exit_code":"NUMBER" if location=="exit" else 0}
        if location=="nested_execution":
            item["cwd"] = {"nested":["NUMBER"]}
        bad = {"type":"event_msg", "payload":{"type":"item_completed", "item":item}}
    else:
        first = {"type":"user", "sessionId":"s", "message":{"content":"hello"}}
        bad = {"type":"assistant", "sessionId":"s", "message":{"content":[{
            "type":"tool_use", "id":{"nested":["NUMBER"]}, "name":"Bash", "input":{}}]}} \
            if location=="call_id" else {"type":"user", "sessionId":"s",
                "promptSource":{"nested":["NUMBER"]}, "message":{"content":"hello"}}
    raw = (json.dumps(bad).replace('"NUMBER"', token) + "\n").encode()
    source = tmp_path / "bad-number.jsonl"
    source.write_bytes((json.dumps(first) + "\n").encode() + raw)
    healthy = tmp_path / "healthy.jsonl"
    healthy.write_text('{"type":"session_meta","payload":{"id":"healthy"}}\n')
    output = invoke(tmp_path, request([entry(source),entry(healthy)], cross_file=cross_file, text=True, raw=True))
    bad_line = next(o for o in output if o.get("file")==0 and o.get("line")==2)
    assert bad_line["object"]=="unparsed" and bad_line["reason"]=="malformed"
    assert bad_line["raw"].encode()==raw and bad_line["sha256"]==hashlib.sha256(raw).hexdigest()
    assert end(output,0)["status"]==end(output,1)["status"]=="ok"
    assert output[-1]["object"]=="request_end"


@pytest.mark.parametrize("kind", [[], {}, 1, None])
@pytest.mark.parametrize("cross_file", [False, True])
def test_nested_codex_block_type_is_source_contained(tmp_path, kind, cross_file):
    source = tmp_path / "nested-shape.jsonl"
    raw = json.dumps({"type": "response_item", "payload": {"type": "message", "role": "user",
                      "content": [{"type": kind, "text": "<unrecognized>sample"}]}}) + "\n"
    source.write_text('{"type":"session_meta","payload":{"id":"shape"}}\n' + raw)
    healthy = tmp_path / "healthy.jsonl"
    healthy.write_text('{"type":"session_meta","payload":{"id":"healthy"}}\n')
    output = invoke(tmp_path, request([entry(source), entry(healthy)],
                                     cross_file=cross_file, text=True, raw=True))
    record = next(o for o in output if o.get("file") == 0 and o.get("line") == 2 and o["object"] == "record")
    assert record.get("block_type") is None and record["role"] == "unknown"
    assert record["origin"]["native_kind"] is None
    assert record["origin"]["unrecognized_tag"] == {"lead": True, "joined": False}
    assert record["raw"] == raw and strict_json(record["raw"])["payload"]["content"][0]["type"] == kind
    assert record["sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert record["line"] == 2 and record["ref"] == f"file:{source}#L2#0"
    for i in (0, 1):
        framed = [o for o in output if o.get("file") == i]
        assert framed[0]["object"] == "file_start" and framed[-1]["object"] == "file_end"
        assert end(output, i)["status"] == "ok"
        assert end(output, i)["count"] == len(framed) - 2
    assert output[-1]["object"] == "request_end" and output[-1]["files"] == 2


@pytest.mark.parametrize("kind", [[], {}, 1, None])
@pytest.mark.parametrize("harness", ["claude", "codex", "sdk"])
@pytest.mark.parametrize("cross_file", [False, True])
def test_non_string_native_kind_before_signature_is_source_contained(tmp_path, kind, harness, cross_file):
    signature = {"claude":{"type":"user","sessionId":"s","message":{"content":"hello"}},
                 "codex":{"type":"session_meta","payload":{"id":"s"}},
                 "sdk":{"type":"system","session_id":"s","subtype":"init"}}[harness]
    source = tmp_path / "shape.jsonl"
    source.write_text(json.dumps({"type":kind}) + "\n" + json.dumps(signature) + "\n")
    healthy = tmp_path / "healthy.jsonl"
    healthy.write_text('{"type":"session_meta","payload":{"id":"healthy"}}\n')
    output = invoke(tmp_path, request([entry(source),entry(healthy)],cross_file=cross_file,text=True,raw=True))
    unknown = next(o for o in output if o.get("file")==0 and o.get("line")==1)
    assert unknown["object"]=="record" and unknown["role"]=="unknown" and unknown["kind"] is None
    assert strict_json(unknown["raw"])["type"]==kind
    assert end(output,0)["status"]==end(output,1)["status"]=="ok"
    assert output[-1]["files"]==2


@pytest.mark.parametrize("rewrite", [
    b'{"type":"session_meta","payload":{"id":"new"}}\n',
    b'{"type":"session_meta","payload":{"id":"a"}}\n',
    b'{"type":"session_meta","payload":{"id":"a-much-longer-new-session"}}\n',
])
@pytest.mark.parametrize("cross_file", [False, True])
def test_rewritten_source_has_one_consistent_byte_observation(tmp_path, monkeypatch, rewrite, cross_file):
    from harness_evidence import stream
    source = tmp_path / "mutable.jsonl"
    first = b'{"type":"session_meta","payload":{"id":"old"}}\n'
    source.write_bytes(first)
    healthy = tmp_path / "healthy.jsonl"
    healthy.write_text('{"type":"session_meta","payload":{"id":"healthy"}}\n')
    original_open = Path.open
    opens = []
    def changing_open(path, *args, **kwargs):
        if path==source:
            opens.append(path)
            return io.BytesIO(first if len(opens)<=2 else rewrite)
        return original_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,"open",changing_open)
    stdout, stderr = io.StringIO(), io.StringIO()
    req=request([entry(source),entry(healthy)],cross_file=cross_file,text=True,raw=True)
    rc=stream.run(io.StringIO(json.dumps(req)+"\n"),stdout,stderr,
                  {"schema":"harness-evidence/1","decoder":{"version":"test","revision":"test"}})
    assert rc==0 and not stderr.getvalue()
    output=[strict_json(line) for line in stdout.getvalue().splitlines()]
    emitted=[o for o in output if o.get("file")==0 and o["object"]=="record"]
    if end(output,0)["status"]=="ok":
        assert emitted
        header=next(o["header"] for o in output if o.get("file")==0 and o["object"]=="session")
        for record in emitted:
            assert record["sha256"]==hashlib.sha256(record["raw"].encode()).hexdigest()
            assert record["end"]-record["offset"]==len(record["raw"].encode())
            assert strict_json(record["raw"])["payload"]["id"]==record["session"]==header["session"]
            assert header["recorded_identity"]["session"] == header["session"]
            assert header["recorded_identity"]["sha256"] == record["sha256"]
    else:
        assert end(output,0)["status"]=="unreadable" and not emitted
    assert end(output,1)["status"]=="ok" and output[-1]["object"]=="request_end"


@pytest.mark.parametrize("name,copy,basis,rule", [
    ("CA","request_blob","native","api_request_blob"),
    ("XE","event_mirror","convention","event_mirror"),
])
def test_intrinsic_copy_provenance_is_separate_from_role(tmp_path,name,copy,basis,rule):
    output=invoke(tmp_path,request([entry(FIXTURES/path_of(name))]))
    copied=[o for o in output if o.get("copy")==copy]
    assert copied
    assert all((o["copy_basis"],o["copy_rule"])==(basis,rule) for o in copied)


@pytest.mark.parametrize("harness,copy,basis,rule", [
    ("claude","fork_history","native","fork_context_ref"),
    ("codex","compaction_history","native","replacement_history"),
])
def test_explicit_native_history_constructs_keep_their_copy_provenance(tmp_path,harness,copy,basis,rule):
    source=tmp_path/"history.jsonl"
    rows=[{"type":"fork-context-ref","sessionId":"s"},
          {"type":"assistant","sessionId":"s","message":{"id":"m","content":[{"type":"text","text":"old"}]}}] \
        if harness=="claude" else [{"type":"session_meta","payload":{"id":"s"}},
          {"type":"compacted","payload":{"replacement_history":[{"type":"message","role":"user",
              "content":[{"type":"input_text","text":"old"}]}]}}]
    source.write_text("".join(json.dumps(row)+"\n" for row in rows))
    output=invoke(tmp_path,request([entry(source)]))
    copied=[o for o in output if o.get("copy")==copy]
    assert copied and all((o["copy_basis"],o["copy_rule"])==(basis,rule) for o in copied)


@pytest.mark.parametrize("reason", [[], {}])
def test_non_string_native_stop_reason_is_data_and_does_not_abort(tmp_path,reason):
    source=tmp_path/"reason.jsonl"
    source.write_text(json.dumps({"type":"assistant","sessionId":"s","message":{
        "stop_reason":reason,"content":[{"type":"text","text":"hello"}]}})+"\n")
    output=invoke(tmp_path,request([entry(source)]))
    record=next(o for o in output if o["object"]=="record")
    assert record["stop_reason"]==reason and record["stop_class"]=="other"
    assert end(output)["status"]=="ok"


@pytest.mark.parametrize("raw", [
    b'{"type":"user","sessionId":"s","message":{"content":"bad\xff"}}\n',
    b'\xffnot-json\n',
    '{"type":"user","sessionId":"s","message":{"content":"caf\u00e9"}}\n'.encode(),
    b'{"type":"user","sessionId":"s","message":{"content":"\\ud800"}}\n',
])
def test_raw_bytes_are_lossless_with_replacement_only_in_typed_text(tmp_path,raw):
    header=b'{"type":"user","sessionId":"s","message":{"content":"header"}}\n'
    source=tmp_path/"raw.jsonl"
    source.write_bytes(header+raw)
    output=invoke(tmp_path,request([entry(source)],text=True,raw=True))
    observed=next(o for o in output if o.get("line")==2)
    assert observed["raw"].encode("utf-8",errors="surrogateescape")==raw
    assert observed["sha256"]==hashlib.sha256(raw).hexdigest()
    assert (observed["offset"],observed["end"])==(len(header),len(header)+len(raw))
    if observed["object"]=="record":
        assert observed["text"]==strict_json(raw.decode("utf-8",errors="replace"))["message"]["content"]
    else:
        assert observed["reason"]=="malformed"


@pytest.mark.parametrize("context,basis,rule,copy", [
    (False,"heuristic","unresolved_fork","ambiguous"),
    (True,"convention","inherited_turn_ids","fork_history"),
])
def test_codex_fork_copy_provenance(tmp_path,context,basis,rule,copy):
    parent=tmp_path/"parent.jsonl"
    parent.write_text('{"type":"session_meta","payload":{"id":"parent"}}\n'
                      '{"type":"event_msg","payload":{"type":"task_started","turn_id":"t"}}\n')
    child=tmp_path/"child.jsonl"
    child.write_text('{"type":"session_meta","payload":{"id":"child"}}\n'
                     '{"type":"session_meta","payload":{"id":"parent"}}\n'
                     '{"type":"event_msg","payload":{"type":"task_started","turn_id":"t"}}\n')
    output=invoke(tmp_path,request([entry(child)],context=[str(parent)] if context else []))
    copied=[o for o in output if o.get("copy")==copy]
    assert copied and all((o["copy_basis"],o["copy_rule"])==(basis,rule) for o in copied)


@pytest.mark.parametrize("mode,basis,rule", [
    ("native","native","continued_in"),
    ("reverse_native","native","continued_in"),
    ("timing","heuristic","timestamp_order"),
    ("ambiguous","heuristic","timing_ambiguity"),
    ("both_native","heuristic","timestamp_order"),
    ("ambiguous_native","heuristic","timing_ambiguity"),
])
def test_cross_file_resume_copy_records_actual_recognition_path(tmp_path,mode,basis,rule):
    root=tmp_path/".claude"/"projects"
    directory=root/"project"
    directory.mkdir(parents=True)
    ids=["c0000000-0000-4000-8000-0000000000a1","c0000000-0000-4000-8000-0000000000b1"]
    paths=[directory/(ident+".jsonl") for ident in ids]
    def user(ident,uuid,hour):
        return {"type":"user","sessionId":ident,"uuid":uuid,"timestamp":f"2026-01-01T{hour}:00:00Z",
                "message":{"content":"hello"}}
    a=[user(ids[0],"shared","09")]
    if mode in {"native","both_native","ambiguous_native"}:
        a.append({"type":"continued-in","sessionId":ids[0],"continuedInSessionId":ids[1]})
    a.append(user(ids[0],"a","10" if mode in {"ambiguous","ambiguous_native"} else "11"))
    b=[user(ids[1],"shared","09")]
    if mode in {"reverse_native","both_native","ambiguous_native"}:
        b.append({"type":"continued-in","sessionId":ids[1],"continuedInSessionId":ids[0]})
    b.append(user(ids[1],"b","10"))
    for path,rows in zip(paths,(a,b)):
        path.write_text("".join(json.dumps(row)+"\n" for row in rows))
    output=invoke(tmp_path,request([entry(p) for p in paths],cross_file=True,
        roots=[{"harness":"claude-code","path":str(root)}]))
    copied=[o for o in output if "copy" in o]
    assert copied and all((o["copy_basis"],o["copy_rule"])==(basis,rule) for o in copied)


def test_link_provenance_is_normalized_and_keeps_recognition_rule(tmp_path):
    roots=[{"harness":"claude-code","path":str(FIXTURES/"home/.claude/projects")},
           {"harness":"codex","path":str(FIXTURES/"home/.codex/sessions")}]
    output=invoke(tmp_path,request([entry(FIXTURES/path_of(n)) for n in ("CA","AG","XC")],roots=roots))
    links=[link for o in output if o["object"]=="session" for link in o["links"]]
    assert {link["rule"] for link in links}=={"native_metadata","path"}
    assert all(link["basis"]=={"native_metadata":"native","path":"convention"}[link["rule"]] for link in links)


@pytest.mark.parametrize("cross_file", [False,True])
def test_ambiguous_link_copy_provenance_keeps_request_scope(tmp_path,cross_file):
    source=tmp_path/"fork.jsonl"
    source.write_text('{"type":"session_meta","payload":{"id":"child"}}\n'
        '{"type":"session_meta","payload":{"id":"parent"}}\n'
        '{"type":"response_item","payload":{"type":"function_call","name":"spawn_agent","call_id":"c","arguments":"{}"}}\n'
        '{"type":"event_msg","payload":{"type":"item_completed","item":{"type":"SubAgentActivity","id":"c","agent_thread_id":"sub"}}}\n')
    output=invoke(tmp_path,request([entry(source)],cross_file=cross_file))
    copied=[link for obj in output if obj["object"]=="session" for link in obj["links"] if "copy" in link]
    assert copied and all((link["copy_basis"],link["copy_rule"],link["copy_scope"])==
        ("heuristic","unresolved_fork",[str(source)]) for link in copied)
