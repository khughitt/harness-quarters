"""Native declarations, actual descendant-read audit and historical populations."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness_evidence import index_events
from harness_evidence.lines import Place
from harness_evidence_index_tracing import covered, declared, feeds_valid, reasons_valid, traced_extract
from test_harness_evidence_index import CONTROLS, FIXTURES, POLICY_CONTROLS
from test_harness_evidence_index_stream import coverage, read, request, source


def declarations():
    from harness_evidence import index_coverage
    return index_coverage


def numbered(data):
    offset = 0
    for raw in data.splitlines(keepends=True):
        yield offset, raw
        offset += len(raw)


def test_every_native_read_is_declared(monkeypatch):
    dec = declarations()
    reads = set()
    for name, old in CONTROLS["cases"].items():
        if "error" in old:
            continue
        path = FIXTURES / "index" / name
        place = Place("claude-code", "file", None, "explicit", name, path)
        reads.update(traced_extract(numbered(path.read_bytes()), copy.deepcopy(old["initial_state"]), place=place))
    path = FIXTURES / "index/task2-usage-storage.jsonl"
    reads.update(traced_extract(numbered(path.read_bytes()), place=Place(
        "claude-code", "file", None, "explicit", path.name, path)))
    for name in POLICY_CONTROLS["cases"]:
        path = FIXTURES / "index" / name
        reads.update(traced_extract(numbered(path.read_bytes()), place=Place(
            "claude-code", "file", None, "explicit", path.name, path)))
    missing = sorted((kind, path) for kind, path in reads if not covered(path, declared(dec, kind)))
    assert missing == []
    # A container declaration cannot silently authorize future descendants.
    path = FIXTURES / "index/sizes.jsonl"
    place = Place("claude-code", "file", None, "explicit", path.name, path)
    actual_message = index_events._message
    def new_read(record, kind):
        if kind == "assistant":
            record["message"].get("undeclared_descendant")
        return actual_message(record, kind)
    monkeypatch.setattr(index_events, "_message", new_read)
    reads = traced_extract(numbered(path.read_bytes()), place=place)
    missing = sorted((kind, field) for kind, field in reads if not covered(field, declared(dec, kind)))
    assert ("assistant", "message.undeclared_descendant") in missing
    assert not covered("message.usage.hidden", ["message.usage"])


def test_feeds_and_justifications_are_valid():
    dec = declarations()
    assert feeds_valid(dec) == [] and reasons_valid(dec) == []
    bogus = SimpleNamespace(WATCHED={"x": {"sources": ["a"], "feeds": {"a": ["applied:no/input:no"]}}},
                            APPLIED=dec.APPLIED, UNWATCHED={"x": {"a": "invented reason"}})
    assert feeds_valid(bogus) and reasons_valid(bogus)


def test_missing_renamed_fields_keep_old_applied_population():
    from harness_evidence import index_coverage
    assert index_coverage.APPLIED["usage"] == (*index_coverage.USAGE, "thinking_tokens")
    for name, old in CONTROLS["cases"].items():
        if "error" in old or old["initial_state"]:
            continue
        out = read(request(source(FIXTURES / "index" / name)))
        assert coverage(out)["records"] == old["records"], name
        assert coverage(out)["fields"] == old["fields"], name


def test_truncation_coverage_matches_pending_call_across_slices():
    name = "ownership.jsonl"
    path = FIXTURES / "index" / name
    raw = path.read_bytes().splitlines(keepends=True)
    first = read(request(source(path, size=len(raw[0]))))
    second = read(request(source(path, size=sum(map(len, raw[:2])), state=first[-2]["state"])))
    truncation = [v for v in coverage(second)["fields"] if v["record_kind"] == "applied:truncation"]
    assert truncation == [{"session_id": "agent-kid", "day": "2026-11-12", "record_kind": "applied:truncation", "field": "input:persisted_size", "seen": 1, "present": 1}]
    assert coverage(second)["fields"] == CONTROLS["cases"][name]["replay"][1]["fields"]


def test_orphan_and_duplicate_persisted_results_have_no_truncation_application():
    path = FIXTURES / "index/ownership.jsonl"
    out = read(request(source(path)))
    assert [v for v in coverage(out)["fields"] if v["record_kind"] == "applied:truncation"] == [
        {"session_id": "agent-kid", "day": "2026-11-12", "record_kind": "applied:truncation", "field": "input:persisted_size", "seen": 1, "present": 1}]
    old = json.loads((FIXTURES / "index/task2-old-controls.json").read_text())
    path = FIXTURES / "index/task2-first-result.jsonl"
    state = None
    raw = path.read_bytes().splitlines(keepends=True)
    for cut, expected in zip([1, 2, len(raw)], old["replay"]):
        out = read(request(source(path, size=sum(map(len, raw[:cut])), state=state)))
        assert coverage(out)["fields"] == expected["fields"]
        assert coverage(out)["records"] == expected["records"]
        assert not [v for v in coverage(out)["fields"] if v["record_kind"] == "applied:truncation"]
        state = out[-2]["state"]


@pytest.mark.parametrize("name", ["sizes.jsonl", "native-tools.jsonl", "identities.jsonl", "fragments.jsonl", "fix1-stop-matching.jsonl"])
def test_native_size_origin_duration_identity_state_contract_survives_slicing(name):
    path = FIXTURES / "index" / name
    full = [v for v in read(request(source(path))) if v["object"] == "index_event"]
    raw = path.read_bytes().splitlines(keepends=True)
    state, replay = None, []
    for i in range(1, len(raw) + 1):
        out = read(request(source(path, size=sum(map(len, raw[:i])), state=state)))
        replay.extend(v for v in out if v["object"] == "index_event")
        state = out[-2]["state"]
        assert "guard-sensitive-command" not in json.dumps(state)
        assert not any(token in json.dumps(state) for token in ['Inspect synthetic task', 'echo α'])
    assert replay == full


def test_scoped_provenance_refers_to_real_decoded_fields():
    from harness_evidence.capabilities import build
    fields = build(FIXTURES / "CATALOGUE.toml")["harnesses"]["claude-code"]["fields"]
    # Two contexts of the same real values, rather than consumer-specific aliases.
    for field in ("message.joined_nonempty", "message.joined_bytes"):
        assert fields[field]["coverage_keys"] == ["assistant/input:content", "user/input:content"]
        assert fields[field]["coverage_scopes"] == [
            {"when": {"message.channel": "user"}, "coverage_keys": ["user/input:content"]},
            {"when": {"message.channel": "assistant"}, "coverage_keys": ["assistant/input:content"]}]
    out = read(request(source(FIXTURES / "index/sizes.jsonl")))
    messages = [v["message"] for v in out if v.get("message")]
    assert {m["channel"] for m in messages} == {"user", "assistant"}
    assert all(isinstance(m["joined_bytes"], int) and isinstance(m["joined_nonempty"], bool) for m in messages)


def test_nested_metric_inputs_are_independently_declared():
    from harness_evidence.capabilities import build, _values
    view = build(FIXTURES / "CATALOGUE.toml")["harnesses"]["claude-code"]
    expected = {
        "calls[].questions[].options[].label": ["applied:question/input:labels"],
        "turn_end.id": ["applied:turn_end/input:id"],
        "turn_end.turn": ["applied:turn_end/input:turn"],
        "turn_end.hooks": ["applied:turn_end/input:hooks"],
        "turn_end.blocked": ["applied:turn_end/input:errors"],
        "turn_end.errors_bytes": ["applied:turn_end/input:errors"],
        "turn_end.hooks[].duration_ms": ["applied:hook_run/input:duration"],
        "turn_end.hooks[].blocked": ["applied:stop_block/input:command"],
    }
    events = []
    for name in ("native-tools.jsonl", "fix1-stop-matching.jsonl"):
        events.extend(read(request(source(FIXTURES / "index" / name))))
    for field, keys in expected.items():
        assert view["fields"][field]["coverage_keys"] == keys
        assert any(_values(event, field) for event in events), field
        assert field not in index_events.PROVENANCE
    assert view["index"]["tool_kinds"]["Bash"] == "shell"
    assert view["index"]["tool_kinds"]["AskUserQuestion"] == "question"
    assert view["index"]["features"] == {"native_skill_events": True, "question_option_labels": True}
