"""Whole-prefix replay equals a fresh decode through incomplete and appended lines."""
import hashlib
import json

import pytest

from harness_evidence_testing import FIXTURES, path_of
from test_harness_evidence_stream import entry, request, invoke, end


def payload(obj):
    return {k: v for k, v in obj.items() if k not in {"schema", "decoder", "request", "file"}}


def apply(held, output, file=0):
    objects = [payload(o) for o in output if o.get("file") == file and o["object"] != "file_end"]
    replacement = objects[0]["replaces"]
    held = {} if replacement == "all" else {k: v for k, v in held.items()
        if "line" not in v or v["line"] < replacement["from_line"]}
    held.update((o["key"], o) for o in objects)
    # Transport replacement instruction describes this response, not persistent content.
    held["file"].pop("replaces")
    return held


@pytest.mark.parametrize("name", ["CA", "XA", "XF", "SDK", "ESM"])
def test_slices_equal_whole(tmp_path, name):
    path = FIXTURES / path_of(name)
    raw = path.read_bytes()
    cuts = {0, len(raw)}
    offset = 0
    for n, line in enumerate(raw.splitlines(keepends=True)):
        if n % 3 == 0:
            cuts.update({offset + len(line) // 2, offset + len(line)})
        offset += len(line)
    state, held = None, {}
    for size in sorted(cuts):
        output = invoke(tmp_path, request([entry(path, size=size, state=state)]))
        held = apply(held, output)
        state = end(output)["state"]
    assert held == apply({}, invoke(tmp_path, request([entry(path)])))


def test_checkpoint_boundaries_and_digest(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_bytes(b"")
    output = invoke(tmp_path, request([entry(path)]))
    assert end(output)["state"] == {"next_line": 1, "next_offset": 0,
                                      "digest": hashlib.sha256(b"").hexdigest()}
    path.write_bytes(b'{"sessionId":"s","type":"user","message":{"content":"x"}}\n{')
    output = invoke(tmp_path, request([entry(path)]))
    tail = next(o for o in output if o["object"] == "unparsed")
    assert tail["provisional"] and tail["reason"] == "truncated"
    assert end(output)["state"]["next_line"] == 2
    assert end(output)["offset"] == tail["offset"] == len(path.read_bytes()) - 1
    digest = hashlib.sha256()
    for obj in output:
        if obj["object"] == "record":
            digest.update((json.dumps(payload(obj), ensure_ascii=True, separators=(",", ":"),
                                      sort_keys=True) + "\n").encode("ascii"))
    assert end(output)["state"]["digest"] == digest.hexdigest()
    path.write_bytes(path.read_bytes()[:-1])
    state = end(invoke(tmp_path, request([entry(path)])))["state"]
    assert (state["next_line"], state["next_offset"]) == (2, path.stat().st_size)


def test_transport_identity_does_not_change_digest(tmp_path):
    path = FIXTURES / path_of("CA")
    first = invoke(tmp_path, request([entry(path)]))
    state = end(first)["state"]
    second = invoke(tmp_path, request([entry(path), entry(path, state=state)], id=999))
    start = next(o for o in second if o.get("file") == 1)
    assert start["replaces"] == {"from_line": state["next_line"]}
    assert not any(o["object"] == "record" and o["file"] == 1 for o in second)


@pytest.mark.parametrize("append", [
    {"type": "user", "sessionId": "s", "message": {"content": [{"type": "tool_result", "tool_use_id": "call", "content": "ok"}]}},
    {"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "t", "last_agent_message": "answer"}},
    {"type": "session_meta", "payload": {"id": "parent"}},
])
def test_appended_results_turn_end_and_headers_replay(tmp_path, append):
    path = tmp_path / "growth.jsonl"
    claude = append.get("type") == "user"
    prefix = [{"type": "assistant", "sessionId": "s", "message": {"content": [{"type": "tool_use", "id": "call", "name": "Bash", "input": {"command": "true"}}]}}] if claude else [
        {"type": "session_meta", "payload": {"id": "child"}},
        {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "t"}}]
    path.write_text("".join(json.dumps(o) + "\n" for o in prefix))
    first = invoke(tmp_path, request([entry(path)], text=True))
    with path.open("a") as handle:
        handle.write(json.dumps(append) + "\n")
    second = invoke(tmp_path, request([entry(path, state=end(first)["state"])], text=True))
    assert apply(apply({}, first), second) == apply({}, invoke(tmp_path, request([entry(path)], text=True)))
    if claude:
        assert second[0]["replaces"] == "all"


@pytest.mark.parametrize("state", [
    {"next_line": True, "next_offset": 0, "digest": "a" * 64},
    {"next_line": 1, "next_offset": -1, "digest": "a" * 64},
    {"next_line": 1, "next_offset": 0, "digest": "bad"},
    {"next_line": 1, "next_offset": 0, "digest": "a" * 64, "extra": 1},
])
def test_malformed_state_fails_explicitly(tmp_path, state):
    from test_harness_evidence_stream import run_raw
    proc = run_raw(tmp_path, json.dumps(request([{"path": "x", "size": 0, "state": state}])) + "\n")
    assert proc.returncode == 2 and not proc.stdout


def test_digest_revision_independence_and_option_change(tmp_path):
    from harness_evidence.stream import objects, validate
    path = FIXTURES / path_of("CA")
    req = validate(request([entry(path)]))
    first = list(objects(req, {"schema": "harness-evidence/1", "decoder": {"version": "1", "revision": "a"}}))
    state = end(first)["state"]
    req = validate(request([entry(path, state=state)], id=88))
    second = list(objects(req, {"schema": "harness-evidence/1", "decoder": {"version": "1", "revision": "b"}}))
    assert second[0]["replaces"] == {"from_line": state["next_line"]}
    assert end(second)["state"]["digest"] == state["digest"]
    output = invoke(tmp_path, request([entry(path, state=state)], text=True))
    assert output[0]["replaces"] == "all"


def test_modified_or_shrunk_committed_source_restarts(tmp_path):
    path = tmp_path / "changed.jsonl"
    path.write_text('{"type":"user","sessionId":"s","message":{"content":"before"}}\n')
    first = invoke(tmp_path, request([entry(path)]))
    path.write_text('{"type":"user","sessionId":"s","message":{"content":"after"}}\n')
    output = invoke(tmp_path, request([entry(path, state=end(first)["state"])]))
    assert output[0]["replaces"] == "all"
    path.write_bytes(b"")
    output = invoke(tmp_path, request([entry(path, state=end(first)["state"])]))
    assert output[0]["replaces"] == "all"
