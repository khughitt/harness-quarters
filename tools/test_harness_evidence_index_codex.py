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


def leaves(value, prefix):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, prefix + "." + key if prefix else key)
    elif isinstance(value, list):
        for child in value:
            yield from leaves(child, prefix + "[]")
    else:
        yield prefix


def undeclared_fields(out, defaults):
    """Event fact leaves that no provenance declaration names or contains."""
    missing = set()
    for value in out:
        if value["object"] == "index_event":
            facts = {key: value[key] for key in ("native_kind", "at_ms", "eligible", "flush_response",
                "identity", "context", "response", "message", "calls", "injections",
                "execution", "notifications", "compaction", "interruption", "fork_boundary", "turn_end",
                "turn", "occupancy", "rate_limits")}
            for field in leaves(facts, ""):
                if value.get(field) is None and field in {"context", "response", "message", "turn", "occupancy"}:
                    continue
                if not any(field == declared or field.startswith(declared + ".") or field.startswith(declared + "[]")
                           for declared in defaults):
                    missing.add(field)
    return sorted(missing)


def test_all_codex_fields_have_coverage_and_provenance(tmp_path):
    from harness_evidence import index_codex, index_codex_coverage
    defaults = index_codex.provenance_defaults()
    out = decode(tmp_path)
    assert out[0]["provenance_defaults"] == defaults

    assert undeclared_fields(out, defaults) == []
    encode = index_stream._provenance_encoder(defaults, index_codex.PROVENANCE)
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
        index_stream._provenance_encoder({"unknown": next(iter(defaults.values()))}, index_codex.PROVENANCE)
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


def undeclared_reads(monkeypatch, source):
    """Native reads of `source` lines that no WATCHED, UNWATCHED or common path declares."""
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
    place = Place("codex", "file", None, "explicit", "control", Path("control"))
    list(cx.extract(enumerate(source), {}, place=place, text=True))
    missing = []
    for kind, path in reads:
        paths = (*cv.COMMON_READS, *cv.WATCHED.get(kind, {"sources": ()})["sources"],
                 *cv.UNWATCHED.get(kind, {}))
        if not any(path == item or item.startswith(path + ".") or item.startswith(path + "[]") for item in paths):
            missing.append((kind, path))
    return sorted(missing)


@pytest.mark.parametrize("sample", ["codex-basic.jsonl", "codex-context.jsonl", "codex-execution.jsonl",
                                    "codex-compaction.jsonl", "codex-failure.jsonl", "codex-meters.jsonl"])
def test_basic_native_reads_are_declared_without_parent_wildcards(monkeypatch, sample):
    """Original support.tracing read audit, over this step's implemented controls."""
    from harness_evidence import index_codex_coverage as cv
    assert undeclared_reads(monkeypatch, (FIXTURES / sample).read_bytes().splitlines(keepends=True)) == []
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
    assert index_stream._provenance_encoder(defaults, index_codex.PROVENANCE)(event) == event["provenance"]
    proofs = {field: {**proof, "ref": event["ref"], "revision": "test", **event["provenance"].get(field, {})}
              for field, proof in defaults.items()}
    assert index_events._factor_provenance({**event, "provenance": proofs}, defaults) == event["provenance"]


def test_codex_results_carry_a_null_exit_code_declared_absent(tmp_path):
    # Spec §5.2 null-for-absent: a native function output records no exit code of its own;
    # command exits stay on the associated execution facts.
    from harness_evidence import index_codex
    out = decode(tmp_path)
    results = [result for value in out if value["object"] == "index_event" for result in value["results"]]
    assert results and all("exit_code" in result and result["exit_code"] is None for result in results)
    assert index_codex.provenance_defaults()["results[].exit_code"] == {
        "native_paths": [], "coverage_keys": [], "basis": "native", "rule": "absent:not_decoded"}


def lines_of(records):
    return [(json.dumps(record, ensure_ascii=False) + "\n").encode() for record in records]


TURN_RECORDS = [
    record("event_msg", {"type": "task_started", "turn_id": "t1"}),
    record("event_msg", {"type": "turn_started", "turn_id": 7}),
    record("event_msg", {"type": "task_started"}),
    record("turn_context", {"model": "m", "turn_id": "t1"}),
    record("turn_context", {"model": "m"}),
    record("event_msg", {"type": "turn_aborted"}),
]
COMPACTION_USAGE = {"turn_id": "t", "response_id": "c", "usage": {"input_tokens": 216410}}
COMPACTION_RECORDS = [
    record("compacted", {"compaction_response_id": "c", "latest_token_usage_record": COMPACTION_USAGE,
                         "resume_metadata": {"previous_turn_settings": {"model": "m"}},
                         "replacement_history": []}),
    record("compacted", {"replacement_history": [{"x": 1}]}),
    record("compacted", {"compaction_response_id": "c", "latest_token_usage_record": None}),
    record("compacted", {"latest_token_usage_record": "text"}),
    record("compacted", {"latest_token_usage_record": {"usage": {"input_tokens": False}},
                         "resume_metadata": {}}),
]


def token_count(**info):
    return record("event_msg", {"type": "token_count", "info": info})


def test_turn_facts_mark_turn_starts_and_turn_contexts():
    rows, _ = native([META, *TURN_RECORDS])
    assert rows[0]["turn"] is None
    assert [row["turn"] for row in rows[1:-1]] == [
        {"id": "t1", "start": True}, {"id": 7, "start": True}, {"id": None, "start": True},
        {"id": "t1", "start": False}, {"id": None, "start": False}, None]
    sessionless, _ = native(TURN_RECORDS[:1])
    assert sessionless[0]["eligible"] is False and sessionless[0]["turn"] is None


def test_turn_started_is_counted_unknown_and_adds_no_field_presence():
    rows, _ = native([META, *TURN_RECORDS[:2]])
    coverage = rows[-1]
    records = {row["record_kind"]: (row["known"], row["records"]) for row in coverage["records"]}
    assert records["event_msg:turn_started"] == (0, 1)
    assert records["event_msg:task_started"] == (1, 1)
    assert not [row for row in coverage["fields"]
                if row["record_kind"] in ("event_msg:turn_started", "event_msg:task_started")]
    from harness_evidence import index_codex_coverage as cv
    assert cv.UNWATCHED["event_msg:turn_started"] == {"payload.turn_id": "dimension"}
    assert "event_msg:turn_started" not in cv.HANDLED_KINDS | cv.IGNORED_KINDS


def test_occupancy_is_every_token_count_with_info_whatever_the_usage_source():
    recorded, state = native([META, record("token_usage_record", {"response_id": "r", "usage": {"input_tokens": 1}}),
        token_count(total_token_usage={"input_tokens": 1}, last_token_usage={"input_tokens": 9},
                    model_context_window=100),
        token_count(last_token_usage={"input_tokens": True}, model_context_window=None),
        token_count(last_token_usage={"input_tokens": 2.5}, model_context_window=1.5),
        token_count(),
        record("event_msg", {"type": "token_count", "info": None})])
    assert state["usage_source"] == "record"
    assert [row["occupancy"] for row in recorded[2:7]] == [
        {"input_tokens": 9, "context_window": 100}, {"input_tokens": True, "context_window": None},
        {"input_tokens": 2.5, "context_window": 1.5}, {"input_tokens": None, "context_window": None}, None]
    assert all(row["response"] is None for row in recorded[2:7])
    counted, state = native([META, token_count(total_token_usage={"input_tokens": 1},
                                               last_token_usage={"input_tokens": 9}, model_context_window=100)])
    assert state["usage_source"] == "count"
    assert counted[1]["occupancy"] == {"input_tokens": 9, "context_window": 100}
    assert counted[1]["response"]["usage"]["context_total"] == 9
    assert [row["occupancy"] for row in recorded[:2]] == [None, None]


def test_compaction_carries_its_id_and_embedded_usage_record_unrepaired():
    rows, _ = native([META, *COMPACTION_RECORDS])
    base = {"summary": True, "basis": "native", "rule": "codex_compacted", "trigger": None, "reason": None}
    assert rows[1]["compaction"] == {**base, "id": "c", "usage_record": {
        "turn_id": "t", "response_id": "c", "input_tokens": 216410, "model": "m"}}
    assert rows[2]["compaction"] == {**base, "id": None, "usage_record": None}
    assert rows[3]["compaction"] == {**base, "id": "c", "usage_record": None}
    assert rows[4]["compaction"] == {**base, "id": None, "usage_record": None}
    assert rows[5]["compaction"] == {**base, "id": None, "usage_record": {
        "turn_id": None, "response_id": None, "input_tokens": False, "model": None}}
    assert rows[1]["injections"] == [{"piece": 0, "native_kind": "compact_summary", "source": None, "bytes": 2}]


@pytest.mark.parametrize("payload, message", [
    ({"compaction_response_id": 7}, "compaction_response_id is not a string"),
    ({"compaction_response_id": True}, "compaction_response_id is not a string"),
    ({"compaction_response_id": ["c"]}, "compaction_response_id is not a string"),
    ({"compaction_response_id": {"id": "c"}}, "compaction_response_id is not a string"),
    ({"latest_token_usage_record": {"usage": [1]}}, "latest_token_usage_record usage is not an object"),
    ({"latest_token_usage_record": {}, "resume_metadata": "x"}, "resume_metadata is not an object"),
    ({"latest_token_usage_record": {}, "resume_metadata": {"previous_turn_settings": ["m"]}},
     "previous_turn_settings is not an object"),
])
def test_unexpected_compaction_types_fail_the_file_and_are_not_malformed_lines(tmp_path, payload, message):
    with pytest.raises(TypeError, match=f"^Codex compacted {message}$"):
        native([META, record("compacted", payload)])
    source = tmp_path / "rollout.jsonl"
    source.write_bytes(b"".join(lines_of([META, record("compacted", payload)])))
    proc = subprocess.run([str(TOOLS / "harness-evidence"), "decode"],
                          input=json.dumps(request(source)) + "\n", text=True,
                          capture_output=True, timeout=60, env=environment(tmp_path))
    from test_harness_evidence_index import source_failure
    rows = source_failure(proc, "TypeError")
    assert rows[-2]["error"]["message"] == f"Codex compacted {message}"
    assert not any(row["object"] == "unparsed" for row in rows)


def test_own_marks_events_of_the_files_first_session_meta_thread():
    child = record("session_meta", {"id": "child", "parent_thread_id": "parent"})
    parent = record("session_meta", {"id": "parent"})
    context = record("turn_context", {"model": "m"})
    rows, _ = native([context, record("session_meta", {"cwd": "/w"}), child, context, parent,
                      context, child, context])
    assert [row["identity"]["own"] for row in rows[:-1]] == [False, False, True, True, False, False, True, True]
    split, state = native([child])
    assert split[0]["identity"]["own"] is True
    state = json.loads(json.dumps(state))
    raw = lines_of([parent, context])
    place = Place("codex", "file", None, "explicit", "control", Path("control"))
    from harness_evidence import index_codex
    later = list(index_codex.extract([(100, raw[0]), (100 + len(raw[0]), raw[1])], state, place=place, text=True))
    assert [row["identity"]["own"] for row in later[:-1]] == [False, False]


def test_new_compaction_reads_are_declared(monkeypatch):
    assert undeclared_reads(monkeypatch, lines_of([META, *TURN_RECORDS, *COMPACTION_RECORDS,
        token_count(last_token_usage={"input_tokens": 1}, model_context_window=2)])) == []


def test_compaction_turn_and_occupancy_provenance_is_declared():
    from harness_evidence import index_codex
    defaults = index_codex.provenance_defaults()
    assert defaults["identity.own"] == {"native_paths": ["payload.id"], "coverage_keys": ["session_meta/input:session"],
                                        "basis": "convention", "rule": "codex_identity_own"}
    assert defaults["turn.id"]["native_paths"] == ["payload.turn_id"]
    assert defaults["occupancy.context_window"]["coverage_keys"] == ["event_msg:token_count/input:context_window"]
    assert defaults["compaction.id"]["native_paths"] == ["payload.compaction_response_id"]
    assert defaults["compaction.trigger"] == {"native_paths": [], "coverage_keys": [], "basis": "native",
                                              "rule": "absent:not_recorded"}
    assert defaults["compaction.usage_record"]["native_paths"] == [
        "payload.latest_token_usage_record.turn_id", "payload.latest_token_usage_record.response_id",
        "payload.latest_token_usage_record.usage.input_tokens",
        "payload.resume_metadata.previous_turn_settings.model"]


def test_compaction_control_sample_publishes_declared_codex_facts(tmp_path):
    from harness_evidence import index_codex
    out = decode(tmp_path, "codex-compaction.jsonl")
    assert undeclared_fields(out, index_codex.provenance_defaults()) == []
    rows = [value for value in out if value["object"] == "index_event"]
    assert [row["identity"]["own"] for row in rows] == [True] * 7 + [False, False]
    assert [row["turn"] for row in rows[1:3]] == [{"id": "resume", "start": True}] * 2
    assert rows[5]["turn"] == {"id": "resume", "start": False}
    assert rows[3]["occupancy"] == {"input_tokens": 240000, "context_window": 258400}
    assert rows[4]["compaction"]["id"] == "compact-a"
    assert rows[4]["compaction"]["usage_record"] == {"turn_id": "resume", "response_id": "compact-a",
                                                     "input_tokens": 216410, "model": "gpt-6-astra"}
    assert rows[8]["compaction"]["id"] == "compact-p" and rows[8]["compaction"]["usage_record"] is None
    coverage = next(value for value in out if value["object"] == "coverage")
    assert {row["record_kind"]: row["known"] for row in coverage["records"]}["event_msg:turn_started"] == 0


@pytest.mark.parametrize("last", ["text", [1], 7])
def test_occupancy_refuses_a_token_count_usage_that_is_not_an_object(last):
    with pytest.raises(TypeError, match="^Codex token_count last_token_usage is not an object$"):
        native([META, record("token_usage_record", {"usage": {}}),
                token_count(last_token_usage=last, model_context_window=1)])


def meter(rate_limits, timestamp="2026-09-04T09:38:28.000Z"):
    return record("event_msg", {"type": "token_count", "rate_limits": rate_limits}, timestamp)


@pytest.mark.parametrize("rate_limits,want", [
    ({"credits": {"balance": "3.5"}, "primary": {"window_minutes": 10080, "used_percent": 15},
      "secondary": {"window_minutes": 300, "used_percent": 7}}, (3.5, 15.0)),
    ({"credits": {"balance": 0}, "primary": {"window_minutes": 300, "used_percent": 10},
      "secondary": {"window_minutes": 10080, "used_percent": 18.5}}, (0.0, 18.5)),
    ({"primary": {"window_minutes": 300, "used_percent": 10}}, (None, None)),
    ({"credits": {"balance": "3.5"}, "primary": [],
      "secondary": {"window_minutes": 10080, "used_percent": 19}}, (3.5, 19.0)),
    ({"credits": {"balance": "3.5"}, "primary": False, "secondary": 7}, (3.5, None)),
    ({"credits": None, "primary": None, "secondary": None}, (None, None)),
])
def test_codex_meters_are_emitted_even_before_session_metadata(rate_limits, want):
    raw = meter(rate_limits)
    rows, _ = native([raw, META, raw])
    for event, eligible in [(rows[0], False), (rows[2], True)]:
        assert event["eligible"] is eligible
        assert event["rate_limits"] == {"status": "ok", "at_ms": 1788514708000,
                                        "balance": want[0], "weekly_used_percent": want[1],
                                        "basis": "native", "rule": "codex_rate_limits"}
    assert rows[1]["rate_limits"] is None


def test_codex_meter_uses_payload_timestamp_when_record_timestamp_is_absent():
    raw = meter({})
    raw["payload"]["timestamp"] = raw.pop("timestamp")
    rows, _ = native([raw])
    assert rows[0]["rate_limits"]["at_ms"] == 1788514708000
    assert rows[0]["at_ms"] == 1788514708000


@pytest.mark.parametrize("rate_limits,timestamp", [
    ([], "2026-09-04T09:38:28.000Z"), ({"credits": []}, "2026-09-04T09:38:28.000Z"),
    ({"credits": {"balance": True}}, "2026-09-04T09:38:28.000Z"),
    ({"credits": {"balance": "NaN"}}, "2026-09-04T09:38:28.000Z"),
    ({"credits": {"balance": "none"}}, "2026-09-04T09:38:28.000Z"),
    ({"secondary": {"window_minutes": 10080, "used_percent": False}}, "2026-09-04T09:38:28.000Z"),
    ({"secondary": {"window_minutes": 10080, "used_percent": "Infinity"}}, "2026-09-04T09:38:28.000Z"),
    ({}, None), ({}, ""),
])
def test_codex_meter_defects_are_malformed_readings(rate_limits, timestamp):
    raw = meter(rate_limits, timestamp)
    if timestamp is None:
        del raw["timestamp"]
    rows, _ = native([raw])
    reading = rows[0]["rate_limits"]
    assert reading.keys() == {"status", "reason", "basis", "rule"}
    assert reading["status"] == "malformed" and reading["reason"]
    assert reading["basis"] == "native" and reading["rule"] == "codex_rate_limits"


def test_codex_meter_parser_ignores_non_meter_records_and_rejects_nonfinite_numbers():
    from harness_evidence import index_codex

    for raw in (["rate_limits"], {"type": "event_msg", "payload": "s"},
                record("event_msg", {"type": "other", "rate_limits": {}}), meter(None)):
        assert index_codex.codex_rate_limits(raw) is None
    for timestamp in ("yesterday", 17):
        assert index_codex.codex_rate_limits(meter({}, timestamp))["status"] == "malformed"
    for limits in ({"credits": {"balance": float("inf")}},
                   {"primary": {"window_minutes": 10080, "used_percent": float("nan")}}):
        assert index_codex.codex_rate_limits(meter(limits))["status"] == "malformed"


def test_codex_meter_native_reads_are_declared_without_adding_coverage(monkeypatch):
    from harness_evidence import index_codex, index_codex_coverage
    raw = meter({"credits": {"balance": "3.5"}, "primary": {"window_minutes": 300, "used_percent": 7},
                 "secondary": {"window_minutes": 10080, "used_percent": 16}})
    item = record("event_msg", {"type": "item_completed", "item": {
        "type": "CommandExecution", "id": "command-1", "command": "true",
        "aggregated_output": "", "exit_code": 0, "process_id": "123"},
        "started_at_ms": 1788514708000, "completed_at_ms": 1788514709000})
    plain = copy.deepcopy(raw)
    del plain["payload"]["rate_limits"]
    before, _ = native([META, item, plain])
    after, _ = native([META, item, raw])
    assert before[-1] == after[-1]
    assert {row["field"] for row in before[-1]["fields"] if row["record_kind"] == "applied:command_item"} >= {
        "input:id", "input:exit_code", "input:command", "input:output"}
    assert index_codex.provenance_defaults()["rate_limits"]["rule"] == "codex_rate_limits"
    assert index_codex_coverage.UNWATCHED["event_msg:token_count"]["payload.rate_limits"] == "dimension"
    assert undeclared_reads(monkeypatch, lines_of([META, raw, item])) == []
