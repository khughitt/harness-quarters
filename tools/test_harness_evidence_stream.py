"""Protocol framing, privacy, source failures and moved-reader conformance."""
import json
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
    return [json.loads(line) for line in proc.stdout.splitlines()]


def end(output, file=0):
    return next(o for o in output if o["object"] == "file_end" and o["file"] == file)


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


@pytest.mark.parametrize("sample", tomllib.loads((FIXTURES / "CATALOGUE.toml").read_text())["sample"],
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
