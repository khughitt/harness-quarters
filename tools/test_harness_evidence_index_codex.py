"""Codex native controls from OBS 1e0afad1, independent of consumer policy."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from harness_evidence import index_events, index_stream
from harness_evidence.lines import Place

TOOLS = Path(__file__).resolve().parent
FIXTURES = TOOLS / "fixtures/harness-evidence"


def environment(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home),
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def request(source, **kw):
    info = source.stat()
    return {"id": 1, "extract": "index", "text": True, "cross_file": False,
            "roots": [{"harness": "codex", "path": str(source.parent)}],
            "files": [{"path": str(source), "size": info.st_size,
                       "identity": {"device": info.st_dev, "inode": info.st_ino}}], **kw}


def decode(tmp_path, name="codex-basic.jsonl", **kw):
    source = FIXTURES / name
    proc = subprocess.run([str(TOOLS / "harness-evidence"), "decode"],
                          input=json.dumps(request(source, **kw)) + "\n", text=True,
                          capture_output=True, timeout=60, env=environment(tmp_path))
    assert proc.returncode == 0, proc.stderr
    return [json.loads(line) for line in proc.stdout.splitlines()]


def native(records):
    from harness_evidence import index_codex
    state, lines, offset = {}, [], 0
    for record in records:
        raw = (json.dumps(record, ensure_ascii=False) + "\n").encode()
        lines.append((offset, raw))
        offset += len(raw)
    place = Place("codex", "file", None, "explicit", "control", Path("control"))
    return list(index_codex.extract(lines, state, place=place, text=True)), state


def record(kind, payload, timestamp="2026-09-04T09:38:28.000Z"):
    return {"type": kind, "payload": payload, "timestamp": timestamp}


META = record("session_meta", {"id": "c1"})


def test_codex_profile_frames_native_facts_and_preserves_reader_outputs(tmp_path):
    out = decode(tmp_path)
    assert [v["object"] for v in out][0] == "file_start"
    assert out[-1]["object"] == "request_end"
    assert out[-2]["count"] == len(out) - 3
    assert out[0]["harness"] == "codex" and out[0]["provenance_format"] == "defaults/1"
    rows = [v for v in out if v["object"] == "index_event"]
    response = next(v["response"] for v in rows if v["response"])
    assert response["phase"] == "terminal"
    assert response["usage"] == {"input_uncached": 8292, "cache_read": 11904,
                                  "cache_write": 0, "output": 395, "thinking": 149,
                                  "context_total": 20196, "uncached_total": 8292}
    assert len(response["usage_present"]) == 7
    assert out[-2]["state"]["next_offset"] == (FIXTURES / "codex-basic.jsonl").stat().st_size
    # Ordinary decoding keeps the established reader path and labels.
    source = FIXTURES / "codex-basic.jsonl"
    req = request(source)
    req.pop("extract")
    req["files"][0].pop("identity")
    proc = subprocess.run([str(TOOLS / "harness-evidence"), "decode"],
                          input=json.dumps(req) + "\n", text=True, capture_output=True,
                          timeout=60, env=environment(tmp_path))
    assert proc.returncode == 0, proc.stderr
    reader = [json.loads(line) for line in proc.stdout.splitlines()]
    assert not any(v["object"] == "index_event" for v in reader)
    expected = json.loads((FIXTURES / "codex-controls.json").read_text())["reader_records"]
    actual = [{key: v[key] for key in ("line", "role", "text")} for v in reader if v["object"] == "record"]
    assert actual == expected


def test_missing_and_explicit_null_usage_are_distinct():
    rows, _ = native([META, record("token_usage_record", {"usage": {"cached_input_tokens": 3}})])
    response = rows[1]["response"]
    assert response["id"] is None
    assert response["usage"]["input_uncached"] == -3
    assert response["usage"]["context_total"] is None
    assert response["usage"]["uncached_total"] == -3
    assert response["usage_present"]["context_total"] is False
    assert response["usage_present"]["input_uncached"] is True
    assert response["usage"]["output"] is None
    for usage in ({"input_tokens": None}, {"cached_input_tokens": None},
                  {"input_tokens": "1"}, {"input_tokens": []}):
        with pytest.raises(TypeError):
            native([META, record("token_usage_record", {"usage": usage})])
    for inp, cached, expected in [(True, False, 1), (1.5, 0.25, 1.25), (0, 3, -3)]:
        values, _ = native([META, record("token_usage_record", {"usage": {
            "input_tokens": inp, "cached_input_tokens": cached}})])
        assert values[1]["response"]["usage"]["uncached_total"] == expected


def test_untimed_context_is_not_lost():
    rows, state = native([META, record("turn_context", {"model": "m", "cwd": "/checkout",
                         "collaboration_mode": {"settings": {"reasoning_effort": "low"}}}, None)])
    assert rows[1]["at_ms"] is None and rows[1]["eligible"] is True
    assert rows[1]["context"] == {"model": "m", "effort": "low", "cwd": "/checkout", "context_window": None}
    assert "low" in json.dumps(state)


def test_origin_and_byte_sizes_match_original_blocks():
    rows, state = native([META, record("response_item", {"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": "<pasted_content>x"}, {"type": "input_text", "text": "é"}]}),
        record("response_item", {"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": "a"}, {"type": "output_text", "text": "é"}]}),
        record("response_item", {"type": "function_call", "call_id": "dict", "name": "unknown", "arguments": {"a": 1}}),
        record("response_item", {"type": "custom_tool_call", "call_id": "p", "name": "apply_patch",
                                "input": "*** Update File: ../x.py\n*** Move to: ~/out.py\n"})])
    assert rows[1]["message"]["joined_bytes"] == 20
    assert rows[1]["message"]["origin"]["markers"]
    assert rows[2]["message"]["assistant_output_bytes"] == 3
    assert rows[2]["message"]["joined_bytes"] == 4
    assert rows[3]["calls"][0]["input_bytes"] == 8  # old default JSON spaces
    patch = rows[4]["calls"][0]
    assert patch["patch_paths"] == ["../x.py", "~/out.py"]
    assert patch["paths"] == ["~/out.py"] and patch["paths_complete"] is False
    assert "pasted_content" not in json.dumps(state)


def test_all_codex_fields_have_coverage_and_provenance(tmp_path):
    from harness_evidence import index_codex, index_codex_coverage
    defaults = index_codex.provenance_defaults()
    out = decode(tmp_path)
    assert out[0]["provenance_defaults"] == defaults

    def leaves(value, prefix):
        if isinstance(value, dict):
            for key, child in value.items():
                yield from leaves(child, prefix + "." + key if prefix else key)
        elif isinstance(value, list):
            for child in value:
                yield from leaves(child, prefix + "[]")
        else:
            yield prefix

    for value in out:
        if value["object"] == "index_event":
            facts = {key: value[key] for key in ("native_kind", "at_ms", "eligible", "flush_response",
                "identity", "context", "response", "message", "calls", "injections",
                "execution", "notifications", "compaction", "interruption", "fork_boundary", "turn_end")}
            for field in leaves(facts, ""):
                if value.get(field) is None and field in {"context", "response", "message"}:
                    continue
                assert any(field == declared or field.startswith(declared + ".") or field.startswith(declared + "[]")
                           for declared in defaults), field
    encode = index_stream._provenance_encoder(defaults, profile=index_codex)
    for value in out:
        if value["object"] != "index_event":
            continue
        proofs = {field: {**copy.deepcopy(proof), "ref": value["ref"],
                          "revision": value["decoder"]["revision"],
                          **value["provenance"].get(field, {})} for field, proof in defaults.items()}
        assert index_events._factor_provenance({**value, "provenance": proofs}, defaults) == value["provenance"]
        assert encode(value) == value["provenance"]
        assert value["sha256"] == hashlib.sha256((FIXTURES / "codex-basic.jsonl").read_bytes().splitlines(keepends=True)[value["line"]-1]).hexdigest()
    assert defaults["response.usage.input_uncached"]["coverage_keys"] == [
        "applied:usage/input:input_tokens", "applied:usage/input:cached_input_tokens"]
    assert index_codex_coverage.WATCHED["turn_context"]["inputs"]["effort"] == (
        "payload.effort", "payload.collaboration_mode.settings.reasoning_effort")
    with pytest.raises(Exception, match="fields"):
        index_stream._provenance_encoder({"unknown": next(iter(defaults.values()))}, profile=index_codex)
    coverage = next(v for v in out if v["object"] == "coverage")
    known = {v["record_kind"]: v["known"] for v in coverage["records"]}
    assert known["event_msg:task_started"] == 1 and known["event_msg:brand_new_event"] == 0
    usage = [v for v in coverage["fields"] if v["record_kind"] == "applied:usage" and v["field"] == "input:output_tokens"]
    assert sum(v["present"] for v in usage) == 1


def test_patch_candidates_keep_the_original_serialized_input_boundary():
    # Original calls.codex_patch_paths uses str; call_targets first uses json.dumps.
    values, _ = native([META, record("response_item", {"type": "custom_tool_call", "name": "apply_patch",
                          "call_id": "p", "input": {"input": "*** Update File: /w/é.py\n"}})])
    call = values[1]["calls"][0]
    assert call["patch_paths"] == ["/w/é.py"]
    assert call["paths"] == ["/w/\\u00e9.py"]


def test_counts_deduplicate_without_fabricating_usage_populations():
    count = record("event_msg", {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 10},
                          "last_token_usage": {"input_tokens": 5, "output_tokens": 2}}})
    values, _ = native([META, count, count, record("event_msg", {"type": "token_count", "info": None})])
    assert len([v for v in values if v.get("response")]) == 1
    response = values[1]["response"]
    assert response["id"].startswith("tc:c1:")
    assert response["usage"]["uncached_total"] == 5
    coverage = values[-1]
    assert [(v["seen"], v["present"]) for v in coverage["fields"]
            if v["record_kind"] == "applied:usage" and v["field"] == "input:output_tokens"] == [(1, 1)]


@pytest.mark.parametrize("sample", ["codex-basic.jsonl", "codex-context.jsonl", "codex-execution.jsonl"])
def test_basic_native_reads_are_declared_without_parent_wildcards(monkeypatch, sample):
    """Original support.tracing read audit, over this step's implemented controls."""
    from types import SimpleNamespace
    from harness_evidence import index_codex as cx, index_codex_coverage as cv
    reads = set()
    loads = json.loads

    class TracedDict(dict):
        def __init__(self, data, path, kind):
            super().__init__({key: wrap(value, f"{path}.{key}" if path else key, kind)
                              for key, value in data.items()})
            self.path, self.kind = path, kind

        def get(self, key, default=None):
            reads.add((self.kind, f"{self.path}.{key}" if self.path else key))
            return dict.get(self, key, default)

        def __getitem__(self, key):
            reads.add((self.kind, f"{self.path}.{key}" if self.path else key))
            return dict.__getitem__(self, key)

        def __contains__(self, key):
            reads.add((self.kind, f"{self.path}.{key}" if self.path else key))
            return dict.__contains__(self, key)

    def wrap(value, path, kind):
        if isinstance(value, dict):
            return TracedDict(value, path, kind)
        if isinstance(value, list):
            return [wrap(item, path + "[]", kind) for item in value]
        return value

    def traced(data, **kwargs):
        value = loads(data, **kwargs)
        return wrap(value, "", cv.record_kind(value)) if isinstance(value, dict) and "payload" in value else value

    monkeypatch.setattr(cx, "json", SimpleNamespace(loads=traced, dumps=json.dumps))
    source = (FIXTURES / sample).read_bytes().splitlines(keepends=True)
    place = Place("codex", "file", None, "explicit", "control", Path("control"))
    list(cx.extract(enumerate(source), {}, place=place, text=True))
    missing = []
    for kind, path in reads:
        paths = (*cv.COMMON_READS, *cv.WATCHED.get(kind, {"sources": ()})["sources"],
                 *cv.UNWATCHED.get(kind, {}))
        if not any(path == item or item.startswith(path + ".") or item.startswith(path + "[]") for item in paths):
            missing.append((kind, path))
    assert sorted(missing) == []
    targets = {f"applied:{site}/input:{name}" for site, inputs in cv.APPLIED.items() for name in inputs}
    assert all(path in declaration["sources"] and set(feeds) <= targets
               for declaration in cv.WATCHED.values() for path, feeds in declaration.get("feeds", {}).items())


def test_native_injection_sources_and_compaction_sizes_are_independent_of_policy():
    values, _ = native([META, record("response_item", {"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": " # AGENTS.md instructions"}]}),
        record("compacted", {"replacement_history": [{"x": 1}]})])
    assert values[1]["injections"] == [{"piece": 0, "native_kind": "user_injection:# AGENTS.md",
                                        "source": "# AGENTS.md", "bytes": 25}]
    assert values[2]["injections"] == [{"piece": 0, "native_kind": "compact_summary", "source": None, "bytes": 10}]


@pytest.mark.parametrize("sample", ["codex-basic.jsonl", "codex-execution.jsonl"])
def test_pinned_command_and_import_codex_facts_agree(tmp_path, sample):
    from test_harness_evidence_package import extracted_copy
    root = extracted_copy(tmp_path, revision="f" * 40)
    source = FIXTURES / sample
    req = request(source)
    proc = subprocess.run([str(root / "tools/harness-evidence"), "decode"],
                          input=json.dumps(req) + "\n", text=True, capture_output=True,
                          timeout=60, env=environment(tmp_path))
    assert proc.returncode == 0, proc.stderr
    wire = [json.loads(line) for line in proc.stdout.splitlines()]
    envelope = {"schema": "harness-evidence/1", "decoder": wire[0]["decoder"]}
    assert envelope["decoder"]["revision"] == "f" * 40
    assert wire == list(index_stream.objects(req, envelope))


def test_original_context_spawn_and_compaction_control(tmp_path):
    values = decode(tmp_path, "codex-context.jsonl")
    rows = [value for value in values if value["object"] == "index_event"]
    expected = json.loads((FIXTURES / "codex-controls.json").read_text())["context_control"]
    assert rows[0]["identity"]["parent"] == expected["parent"]
    assert rows[0]["identity"]["subagent"] == expected["subagent"]
    assert rows[0]["identity"]["version"] == expected["version"]
    assert [row["context"]["effort"] for row in rows if row["context"]] == expected["efforts"]
    assert rows[0]["injections"][0]["bytes"] == expected["base_bytes"]
    assert rows[-1]["injections"][0]["bytes"] == expected["compaction_bytes"]
    for payload, parent, subagent in [
        ({"id": "child", "source": {"subagent": {"thread_spawn": {"parent_thread_id": "parent"}}}}, "parent", True),
        ({"id": "root"}, None, False),
        ({"id": "review", "parent_thread_id": "parent", "thread_source": "subagent",
          "source": {"subagent": "review"}}, "parent", True),
        ({"id": "root", "source": "cli"}, None, False),
    ]:
        observed, _ = native([record("session_meta", payload)])
        assert observed[0]["identity"]["parent"] == parent
        assert observed[0]["identity"]["subagent"] is subagent


@pytest.mark.parametrize("key,field", [("output_tokens", "output"),
                                      ("reasoning_output_tokens", "thinking"),
                                      ("cache_write_input_tokens", "cache_write")])
def test_direct_usage_values_keep_storage_presence_and_raw_json(key, field):
    for value in (None, False, 1.5, "native", [1], {"raw": 1}):
        rows, _ = native([META, record("token_usage_record", {"usage": {key: value}})])
        response = rows[1]["response"]
        assert response["usage"][field] == value
        assert response["usage_present"][field] is True
        assert response["native"] == {key: value}


def test_sessionless_metadata_keeps_empty_session_applied_populations():
    values, state = native([record("session_meta", {"base_instructions": {}, "source": {"subagent": {}}})])
    event, coverage = values
    assert event["eligible"] is False
    assert event["identity"]["session"] is None
    assert event["injections"] == []
    assert "session_id" not in state
    assert coverage["records"] == [{"session_id": "", "day": "2026-09-04",
                                     "record_kind": "session_meta", "known": 1, "records": 1}]
    populations = {(row["record_kind"], row["field"]): row for row in coverage["fields"]}
    for site, field in [("applied:base_instructions", "input:text"),
                        ("applied:spawn", "input:parent_thread_id")]:
        assert populations[(site, field)] == {"session_id": "", "day": "2026-09-04",
                                              "record_kind": site, "field": field, "seen": 1, "present": 0}
    assert populations[("session_meta", "payload.id")]["seen"] == 1
    assert populations[("session_meta", "payload.id")]["present"] == 0


@pytest.mark.parametrize("base,exception", [({"text": "native"}, TypeError), ("malformed", AttributeError)])
def test_sessionless_metadata_keeps_original_instruction_rejections(base, exception):
    with pytest.raises(exception):
        native([record("session_meta", {"base_instructions": base})])


@pytest.mark.parametrize("name", ["exec_command", "shell_command", "shell"])
@pytest.mark.parametrize("command", [42, 1.5, True, False, {"bad": 1}, ["echo", 42], [None]])
def test_malformed_direct_commands_are_rejected_before_wire_emission(name, command):
    with pytest.raises((TypeError, KeyError)):
        native([META, record("response_item", {"type": "function_call", "call_id": "c",
                 "name": name, "arguments": json.dumps({"cmd": command})})])


@pytest.mark.parametrize("name", ["exec_command", "shell_command", "shell"])
@pytest.mark.parametrize("arguments,want", [({}, None), ({"cmd": None}, None),
    ({"cmd": ""}, ""), ({"cmd": []}, ""), ({"cmd": {}}, ""), ({"command": {}}, ""), ({"cmd": ["echo", "ok"]}, "echo ok"),
    ({"command": "echo fallback"}, "echo fallback"),
    ({"cmd": None, "command": "not selected"}, None)])
def test_direct_command_wire_shape_keeps_absence_null_and_joined_lists(name, arguments, want):
    values, _ = native([META, record("response_item", {"type": "function_call", "call_id": "c",
                       "name": name, "arguments": json.dumps(arguments)})])
    call = values[1]["calls"][0]
    assert call["command"] == want
    assert call["commands"] == [{"command": want, "cwd": None}]
    assert call["command"] is None or isinstance(call["command"], str)


@pytest.mark.parametrize("name", ["exec_command", "shell_command", "shell"])
def test_accepted_empty_command_object_has_named_inferred_provenance(name):
    values, _ = native([META, record("response_item", {"type": "function_call", "call_id": "c",
                       "name": name, "arguments": '{"cmd": {}}'})])
    event = values[1]
    call = event["calls"][0]
    assert call["command"] == ""
    assert call["commands"] == [{"command": "", "cwd": None}]
    assert call["input_text"] == '{"cmd": {}}'
    assert call["input_bytes"] == 11
    assert event["provenance"] == {
        "calls[].command": {"basis": "convention", "rule": "codex_empty_command_object"},
        "calls[].commands": {"rule": "codex_empty_command_object"},
    }
    from harness_evidence import index_codex
    defaults = index_codex.provenance_defaults()
    event["decoder"] = {"revision": "test"}
    assert index_stream._provenance_encoder(defaults, profile=index_codex)(event) == event["provenance"]
    proofs = {field: {**proof, "ref": event["ref"], "revision": "test", **event["provenance"].get(field, {})}
              for field, proof in defaults.items()}
    assert index_events._factor_provenance({**event, "provenance": proofs}, defaults) == event["provenance"]
