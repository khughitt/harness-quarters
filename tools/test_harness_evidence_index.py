"""Native index contracts against controls exported by frozen obs0a09481c.

These checks catch native extraction loss, byte-size changes, coverage population
changes and a reader request accidentally entering the opt-in index path.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

import pytest

TOOLS = Path(__file__).resolve().parent
FIXTURES = TOOLS / "fixtures/session-logs"
CONTROLS = json.loads((FIXTURES / "index/old-controls.json").read_text())


def environment(tmp_path):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def command(tmp_path, source, *, text=True, **overrides):
    info = source.stat()
    req = {
        "id": 1,
        "extract": "index",
        "roots": [],
        "cross_file": False,
        "text": text,
        "raw": False,
        "files": [
            {
                "path": str(source),
                "size": info.st_size,
                "identity": {"device": info.st_dev, "inode": info.st_ino},
            }
        ],
        **overrides,
    }
    result = subprocess.run(
        [str(TOOLS / "harness-evidence"), "decode"],
        input=json.dumps(req) + "\n",
        capture_output=True,
        text=True,
        timeout=60,
        env=environment(tmp_path),
    )
    return result


def decoded(tmp_path, name, **kw):
    source = FIXTURES / "index" / name
    parent = CONTROLS["cases"].get(name, {}).get("initial_state", {}).get("parent_session")
    if parent:
        root = tmp_path / ".claude/projects"
        logical = root / "project" / parent / "subagents" / source.name
        info = source.stat()
        kw.update(
            roots=[{"harness": "claude-code", "path": str(root)}],
            files=[
                {
                    "path": str(logical),
                    "read_path": str(source),
                    "size": info.st_size,
                    "identity": {"device": info.st_dev, "inode": info.st_ino},
                }
            ],
        )
    result = command(tmp_path, source, **kw)
    assert result.returncode == 0, result.stderr
    out = [json.loads(line) for line in result.stdout.splitlines()]
    assert out[0]["object"] == "file_start"
    assert out[-1]["object"] == "request_end"
    end = out[-2]
    assert end["object"] == "file_end" and end["restart"] is None
    assert end["count"] == len(out) - 3
    assert end["offset"] == source.stat().st_size
    assert end["state"]["next_offset"] == end["offset"]
    assert end["state"]["next_line"] == len(source.read_bytes().splitlines()) + 1
    return out


def events(out):
    return [v for v in out if v["object"] == "index_event"]


def test_index_events_preserve_fragments_and_missing_usage(tmp_path):
    out = decoded(tmp_path, "fragments.jsonl")
    rows = events(out)
    assert len(rows) == 7
    first, later, complete = [v["response"] for v in rows if v["response"]]
    assert first["id"] == later["id"] == "r1"
    assert first["native"] == {"input_tokens": 0}
    assert first["usage"] == {
        "input_uncached": 0,
        "cache_write": None,
        "cache_read": None,
        "output": None,
        "thinking": None,
        "context_total": None,
        "uncached_total": None,
    }
    assert later["usage"]["input_uncached"] is None
    assert complete["usage"] == {
        "input_uncached": 1,
        "cache_write": 2,
        "cache_read": 3,
        "output": 4,
        "thinking": 0,
        "context_total": 6,
        "uncached_total": 3,
    }
    assert rows[0]["message"]["text"] == "α\n\nβ"
    assert [b["text"] for b in rows[0]["message"]["blocks"]] == ["α", "", "β"]
    assert rows[0]["message"]["joined_bytes"] == 6
    assert rows[1]["message"]["assistant_output_bytes"] == 6
    assert rows[1]["message"]["joined_bytes"] == 7
    assert not rows[4]["eligible"] and rows[4]["at_ms"] is None
    assert not rows[-1]["message"]["joined_nonempty"]
    assert not rows[-2]["message"]["joined_nonempty"]


def test_index_events_cover_native_tools_results_attachments_hooks(tmp_path):
    rows = events(decoded(tmp_path, "native-tools.jsonl"))
    calls = rows[2]["calls"]
    assert [v["kind"] for v in calls] == [
        "shell",
        "file_read",
        "file_edit",
        "file_edit",
        "file_edit",
        "file_edit",
        "dispatch",
        "dispatch",
        "question",
        "skill",
        "file_read",
        "file_read",
        "other",
    ]
    assert [v["block"] for v in calls] == list(range(13))
    assert calls[0]["native_name"] == "Bash" and calls[0]["command"] == "echo α"
    assert calls[0]["background"] is True
    assert calls[8]["questions"][0]["options"][0]["label"] == "A (Recommended)"
    assert calls[9]["skill"] == "sample"
    assert calls[10]["paths"] == [] and calls[10]["paths_complete"]
    assert calls[-1]["input_bytes"] == 28  # default-separator JSON, not compact wire JSON
    assert rows[0]["injections"][0] == {
        "piece": 0,
        "native_kind": "prompt_snapshot",
        "source": "section:0",
        "bytes": 21,
    }
    result = rows[3]["results"][0]
    assert result["native_duration_ms"] == 999
    assert rows[3]["at_ms"] - rows[2]["at_ms"] == 5000
    assert result["truncation"] == {
        "kind": "persisted",
        "original_tokens": None,
        "original_bytes": 42,
    }
    assert result["background_id"] == "bg"
    assert rows[4]["results"][0]["child_session"] == "agent-child"
    assert rows[5]["results"][0]["answers"] == {"Q?": "A (Recommended)"}
    end = rows[7]["turn_end"]
    assert end["id"] == "end" and end["blocked"]
    assert end["errors_bytes"] == 23
    assert end["hooks"] == [
        {"command": "guard", "duration_ms": None, "blocked": True, "reason_bytes": 21},
        {"command": "other", "duration_ms": 3, "blocked": False, "reason_bytes": None},
    ]
    assert rows[-1]["notifications"] == [{"call_id": "0", "status": "completed", "exit_code": -2}]


def test_index_events_preserve_origin_disagreements(tmp_path):
    samples = tomllib.loads((FIXTURES / "CATALOGUE.toml").read_text())["sample"]
    for sample in samples:
        if sample["harness"] != "claude-code" or "expected" not in sample:
            continue
        result = command(tmp_path, FIXTURES / sample["path"])
        assert result.returncode == 0, result.stderr
        row = events([json.loads(line) for line in result.stdout.splitlines()])[0]
        evidence = row["message"]["origin"]
        expected = sample["expected"]["evidence"]
        expected = {
            **expected,
            "markers": [{"lead": None, "joined": None, **m} for m in expected["markers"]],
        }
        assert evidence == {"native_kind": None, **expected}, sample["path"]
        # The decoder records both signals; it does not decide the old human metric.
        assert "human" not in row and "human_turns" not in row


def test_index_evidence_has_sources_and_text_is_opt_in(tmp_path):
    source = FIXTURES / "index/native-tools.jsonl"
    raw = source.read_bytes().splitlines(keepends=True)
    full = events(decoded(tmp_path, source.name))
    hidden = events(decoded(tmp_path, source.name, text=False))
    offset = 0
    for number, (line, row, private) in enumerate(zip(raw, full, hidden), 1):
        assert row["key"] == f"E{offset}" and row["offset"] == offset
        assert row["line"] == number and row["end"] == offset + len(line)
        assert row["sha256"] == hashlib.sha256(line).hexdigest()
        assert row["ref"] == f"file:{source}#L{number}"
        assert row["decoder"]["version"] == "13"
        for provenance in row["provenance"].values():
            assert provenance["basis"] in {"native", "convention", "heuristic"}
            assert provenance["rule"] and provenance["ref"] == row["ref"]
            assert provenance["revision"] == row["decoder"]["revision"]
        if private["message"]:
            assert "text" not in private["message"]
            assert all("text" not in b for b in private["message"]["blocks"])
        for call in private["calls"]:
            assert (
                not {"command", "paths", "raw_path", "prompt", "questions", "skill"} & call.keys()
            )
        for item in private["results"]:
            assert "answers" not in item
        offset += len(line)
    assert full[2]["provenance"]["calls[].raw_path"]["native_paths"] == [
        "message.content[].input.file_path",
        "message.content[].input.notebook_path",
    ]
    assert not any("table" in row for row in full)


def test_reader_request_remains_unchanged(tmp_path):
    from harness_evidence.stream import objects
    from harness_evidence import records
    from harness_evidence.lines import Place

    source = FIXTURES / "index/fragments.jsonl"
    req = {
        "id": 1,
        "files": [{"path": str(source), "size": source.stat().st_size}],
        "roots": [],
        "cross_file": False,
        "text": True,
        "raw": False,
    }
    out = list(
        objects(
            req, {"schema": "harness-evidence/1", "decoder": {"version": "11", "revision": "test"}}
        )
    )
    read = records.claude_read(
        Place("claude-code", "file", None, "explicit", str(source), source), source.stat().st_size
    )
    assert not any(o["object"] in {"index_event", "coverage"} for o in out)
    assert set(out[-2]["state"]) == {"next_line", "next_offset", "digest"}
    projected = [o for o in out if o["object"] == "record"]
    for old, new in zip(read.records, projected):
        assert {k: v for k, v in old.items() if not k.startswith("_")} == {
            k: v
            for k, v in new.items()
            if k
            not in {
                "schema",
                "decoder",
                "request",
                "file",
                "object",
                "key",
                "offset",
                "end",
                "copy_scope",
            }
        }


@pytest.mark.parametrize("name", sorted(CONTROLS["cases"]))
def test_native_coverage_matches_frozen_oracle(tmp_path, name):
    control = CONTROLS["cases"][name]
    source = FIXTURES / "index" / name
    assert hashlib.sha256(source.read_bytes()).hexdigest() == control["sha256"]
    if "error" in control:
        proc = command(tmp_path, source)
        assert proc.returncode != 0
        assert control["error"] in proc.stderr
        return
    out = decoded(tmp_path, name)
    coverage = next(o for o in out if o["object"] == "coverage")
    assert coverage["records"] == control["records"]
    assert coverage["fields"] == control["fields"]
    assert coverage["malformed"] == control["malformed"]


def test_raw_write_paths_are_distinct_from_candidate_paths(tmp_path):
    out = events(decoded(tmp_path, "write-paths.jsonl"))
    calls = {c["id"]: c for row in out for c in row["calls"]}
    for expected in CONTROLS["paths"]:
        actual = calls[expected["id"]]
        assert actual["raw_path"] == expected["raw_path"]
        assert actual["paths"] == expected["paths"]
        assert actual["paths_complete"] == expected["parsed"]
    assert calls["read"]["kind"] == "file_read" and calls["read"]["raw_path"] is None
    old_writes = [
        r for r in CONTROLS["cases"]["write-paths.jsonl"]["rows"] if r["table"] == "file_writes"
    ]
    assert len(old_writes) == len(CONTROLS["paths"])
    assert all(calls[r["call_id"]]["raw_path"] == r["path"] for r in old_writes)
    assert not any(r["call_id"] == "read" for r in old_writes)


@pytest.mark.parametrize(
    "fields",
    [
        {"cross_file": True},
        {"raw": True},
        {"extract": "unknown"},
        {
            "files": [
                {
                    "path": "x",
                    "size": 0,
                    "identity": {"device": 1, "inode": 2},
                    "state": {"next_line": 1, "next_offset": 0, "digest": "0" * 64, "index": []},
                }
            ]
        },
    ],
)
def test_index_rejects_unsupported_requests_before_output(tmp_path, fields):
    proc = command(tmp_path, FIXTURES / "index/fragments.jsonl", **fields)
    assert proc.returncode == 2 and not proc.stdout


def test_index_malformed_tail_identity_and_fixed_span(tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_bytes(b'{"type":"user","sessionId":"s"}\nno json\n{"type":')
    proc = command(tmp_path, source)
    assert proc.returncode == 0, proc.stderr
    out = [json.loads(line) for line in proc.stdout.splitlines()]
    problems = [o for o in out if o["object"] == "unparsed"]
    assert [p["reason"] for p in problems] == ["malformed", "truncated"]
    end = out[-2]
    assert end["offset"] == 40 and end["state"]["next_line"] == 3
    coverage = next(o for o in out if o["object"] == "coverage")
    assert coverage["malformed"] == 1 and coverage["partial_tail"]
    for size, identity in [
        (source.stat().st_size + 1, source.stat().st_ino),
        (source.stat().st_size, 1),
    ]:
        proc = command(
            tmp_path,
            source,
            files=[
                {
                    "path": str(source),
                    "size": size,
                    "identity": {"device": source.stat().st_dev, "inode": identity},
                }
            ],
        )
        assert proc.returncode != 0 and not proc.stdout


def test_native_sizes_and_identity_conventions_match_old_rows(tmp_path):
    rows = events(decoded(tmp_path, "sizes.jsonl"))
    old = CONTROLS["cases"]["sizes.jsonl"]["rows"]
    turn = next(r for r in old if r["table"] == "turns")
    call = next(r for r in old if r["table"] == "tool_calls")
    assert rows[0]["message"]["text"] == "first\n\né"
    assert rows[0]["message"]["joined_bytes"] == turn["prompt_bytes"] == 9
    assert rows[1]["message"]["assistant_output_bytes"] == turn["output_text_bytes"] == 26
    assert rows[1]["calls"][0]["input_bytes"] == call["input_bytes"] == 23
    assert rows[2]["results"][0]["bytes"] == call["result_bytes"] == 23
    identities = [r["identity"] for r in events(decoded(tmp_path, "identities.jsonl"))]
    assert [(i["session"], i["index_session"], i["parent"], i["subagent"]) for i in identities] == [
        ("control", "control", None, False),
        ("control", "agent-kid", "control", True),
        ("sdk", "sdk", None, True),
        ("bare", "bare", None, True),
    ]


def test_truncation_coverage_uses_popped_call_owner_and_result_day(tmp_path):
    out = decoded(tmp_path, "ownership.jsonl")
    fields = next(r["fields"] for r in out if r["object"] == "coverage")
    applied = [r for r in fields if r["record_kind"] == "applied:truncation"]
    assert applied == [
        {
            "session_id": "agent-kid",
            "day": "2026-11-12",
            "record_kind": "applied:truncation",
            "field": "input:persisted_size",
            "seen": 1,
            "present": 1,
        }
    ]
    copied = [r for r in events(out) if r["response"] and r["response"]["id"] == "copied"]
    assert copied[0]["fork_boundary"]["copied_response"]


def test_index_logical_path_supplies_parent_for_archive_bytes(tmp_path):
    source = tmp_path / "archive.jsonl"
    source.write_text(
        '{"type":"user","sessionId":"recorded-parent","agentId":"kid","timestamp":"2026-11-11T00:00:00Z","message":{"content":"child"}}\n'
    )
    root = tmp_path / ".claude/projects"
    logical = root / "project/path-parent/subagents/agent-kid.jsonl"
    info = source.stat()
    result = command(
        tmp_path,
        source,
        roots=[{"harness": "claude-code", "path": str(root)}],
        files=[
            {
                "path": str(logical),
                "read_path": str(source),
                "size": info.st_size,
                "identity": {"device": info.st_dev, "inode": info.st_ino},
            }
        ],
    )
    assert result.returncode == 0, result.stderr
    out = [json.loads(line) for line in result.stdout.splitlines()]
    row = events(out)[0]
    assert row["identity"]["session"] == "recorded-parent"
    assert row["identity"]["index_session"] == "agent-kid"
    assert row["identity"]["parent"] == "path-parent" and row["identity"]["subagent"]
    assert row["ref"] == "claude:projects/project/path-parent/subagents/agent-kid.jsonl#L1"
    assert out[0]["path_facts"]["parent"] == "path-parent"


@pytest.mark.parametrize(
    "tool,value,complete,prompt,skill",
    [
        ("Read", "not JSON", False, None, None),
        ("Glob", '{"pattern":"x"}', True, None, None),
        ("Agent", {}, False, None, None),
        ("Task", {"prompt": 7}, False, None, None),
        ("Skill", {"skill": 7}, True, None, None),
    ],
)
def test_invalid_and_optional_native_call_inputs_preserve_old_contract(
    tmp_path, tool, value, complete, prompt, skill
):
    source = tmp_path / "input.jsonl"
    source.write_text(
        json.dumps(
            {
                "type": "assistant",
                "sessionId": "s",
                "timestamp": "2026-11-11T00:00:00Z",
                "requestId": "r",
                "message": {
                    "content": [{"type": "tool_use", "id": "c", "name": tool, "input": value}]
                },
            }
        )
        + "\n"
    )
    proc = command(tmp_path, source)
    assert proc.returncode == 0, proc.stderr
    call = events([json.loads(line) for line in proc.stdout.splitlines()])[0]["calls"][0]
    assert (
        call["paths_complete"] == complete and call["prompt"] == prompt and call["skill"] == skill
    )


def test_invalid_optional_origin_is_unknown_without_changing_index_eligibility(tmp_path):
    source = tmp_path / "origin.jsonl"
    source.write_text(
        '{"type":"user","sessionId":"s","timestamp":"2026-11-11T00:00:00Z","origin":"invalid","message":{"content":"plain"}}\n'
    )
    proc = command(tmp_path, source)
    assert proc.returncode == 0, proc.stderr
    row = events([json.loads(line) for line in proc.stdout.splitlines()])[0]
    assert row["eligible"] and row["message"]["origin"]["native_kind"] is None


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e10000"])
def test_non_json_numbers_are_unparsed_source_evidence(tmp_path, number):
    source = tmp_path / "malformed.jsonl"
    source.write_text('{"type":"user","sessionId":"s","extra":' + number + "}\n")
    proc = command(tmp_path, source)
    assert proc.returncode == 0, proc.stderr
    out = [json.loads(line) for line in proc.stdout.splitlines()]
    assert not events(out)
    problem = next(v for v in out if v["object"] == "unparsed")
    assert problem["reason"] == "malformed" and not problem["provisional"]
    assert next(v for v in out if v["object"] == "coverage")["malformed"] == 1


def test_assistant_string_content_is_not_an_old_text_block(tmp_path):
    source = tmp_path / "assistant-string.jsonl"
    source.write_text(
        '{"type":"assistant","sessionId":"s","timestamp":"2026-11-11T00:00:00Z","requestId":"r","message":{"content":"synthetic text"}}\n'
    )
    proc = command(tmp_path, source)
    assert proc.returncode == 0, proc.stderr
    row = events([json.loads(line) for line in proc.stdout.splitlines()])[0]
    assert row["message"]["assistant_output_bytes"] == 0
    assert row["message"]["blocks"] == []


@pytest.mark.parametrize("kind", [None, 7, [], {}])
def test_unrecognized_native_kind_retains_old_unknown_coverage(tmp_path, kind):
    source = tmp_path / "unknown.jsonl"
    source.write_text(
        json.dumps({"type": kind, "sessionId": "s", "timestamp": "2026-11-11T00:00:00Z"}) + "\n"
    )
    proc = command(tmp_path, source)
    assert proc.returncode == 0, proc.stderr
    out = [json.loads(line) for line in proc.stdout.splitlines()]
    assert events(out)[0]["native_kind"] == str(kind)
    assert next(v for v in out if v["object"] == "coverage")["records"] == [
        {"session_id": "s", "day": "2026-11-11", "record_kind": str(kind), "known": 0, "records": 1}
    ]


@pytest.mark.parametrize("name", ["cli-sdk", "sdk-cli", "empty-sdk", "sidechain"])
def test_first_entrypoint_precedence_and_later_sidechain_match_old(tmp_path, name):
    name = "fix1-entrypoint-" + name + ".jsonl"
    old = CONTROLS["cases"][name]
    rows = events(decoded(tmp_path, name))
    expected = [sessions[0]["subagent"] for sessions in old["prefix_sessions"]]
    assert [row["identity"]["subagent"] for row in rows] == expected
    native = [json.loads(line) for line in (FIXTURES / "index" / name).read_text().splitlines()]
    assert [r["identity"]["entrypoint"] for r in rows] == [r["entrypoint"] for r in native]
    assert rows[-1]["identity"]["subagent"] == old["sessions"][0]["subagent"]


@pytest.mark.parametrize("variant", ["arithmetic", "nested", "nonmapping", "list"])
def test_overwritten_invalid_usage_is_opaque_until_old_flush(tmp_path, variant):
    name = "fix1-usage-overwritten-" + variant + ".jsonl"
    old = CONTROLS["cases"][name]
    rows = events(decoded(tmp_path, name))
    native = json.loads((FIXTURES / "index" / name).read_text().splitlines()[0])["message"]["usage"]
    assert rows[0]["response"]["native"] == native
    assert all(
        v is None or isinstance(v, (int, float)) for v in rows[0]["response"]["usage"].values()
    )
    turn = next(row for row in old["rows"] if row["table"] == "turns")
    assert rows[-1]["response"]["usage"]["context_total"] == turn["context_tokens"] == 1
    assert rows[-1]["response"]["native"] == turn["native"]
    invalid = "fix1-usage-final-" + variant + ".jsonl"
    proc = command(tmp_path, FIXTURES / "index" / invalid)
    assert proc.returncode != 0 and CONTROLS["cases"][invalid]["error"] in proc.stderr


@pytest.mark.parametrize(
    "name", ["fix1-result-ignored-text.jsonl", "fix1-attachment-ignored-message.jsonl"]
)
def test_native_skip_branches_do_not_read_ignored_message_data(tmp_path, name):
    rows = events(decoded(tmp_path, name))
    assert rows[0]["message"] is None
    if name.startswith("fix1-result"):
        assert rows[0]["results"][0]["call_id"] == "orphan"
        assert rows[0]["results"][0]["bytes"] == 2
    else:
        expected = next(
            row for row in CONTROLS["cases"][name]["rows"] if row["table"] == "injections"
        )
        assert rows[0]["injections"] == [
            {
                "piece": 0,
                "native_kind": "hook_success",
                "source": "guard",
                "bytes": expected["bytes"],
            }
        ]
    for invalid in [
        "errors-text.jsonl",
        "fix1-compact-invalid-text.jsonl",
        "fix1-system-invalid-message.jsonl",
    ]:
        proc = command(tmp_path, FIXTURES / "index" / invalid)
        assert proc.returncode != 0 and CONTROLS["cases"][invalid]["error"] in proc.stderr


def test_text_disabled_stop_boundary_omits_command_from_whole_response(tmp_path):
    source = FIXTURES / "index/fix1-stop-matching.jsonl"
    first = source.read_bytes().splitlines(keepends=True)[0]
    info = source.stat()
    proc = command(
        tmp_path,
        source,
        text=False,
        files=[
            {
                "path": str(source),
                "size": len(first),
                "identity": {"device": info.st_dev, "inode": info.st_ino},
            }
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert "guard-sensitive-command" not in proc.stdout and "/private/path" not in proc.stdout
    assert "--token=fake" not in proc.stdout
    out = [json.loads(line) for line in proc.stdout.splitlines()]
    assert out[-2]["offset"] == len(first)
    # The same pending-stop case retains its exact event text only when requested.
    requested = command(
        tmp_path,
        source,
        text=True,
        files=[
            {
                "path": str(source),
                "size": len(first),
                "identity": {"device": info.st_dev, "inode": info.st_ino},
            }
        ],
    )
    assert requested.returncode == 0 and "guard-sensitive-command" in requested.stdout


def test_nontext_pending_stop_matching_survives_native_slice_boundary():
    from harness_evidence.index_events import extract
    from harness_evidence.lines import Place

    source = FIXTURES / "index/fix1-stop-matching.jsonl"
    raw = source.read_bytes().splitlines(keepends=True)
    place = Place("claude-code", "file", None, "explicit", str(source), source)
    state = {}
    list(extract([(0, raw[0])], state, place=place, text=False))
    assert "guard-sensitive-command" not in json.dumps(state)
    resumed = list(extract([(len(raw[0]), raw[1])], state, place=place, text=False))
    hooks = events(resumed)[0]["turn_end"]["hooks"]
    old = CONTROLS["cases"][source.name]["replay"][-1]
    expected = [r for r in old["rows"] if r["table"] == "hook_runs"]
    assert hooks == [
        {k: r[k] for k in ["duration_ms", "blocked", "reason_bytes"]} for r in expected
    ]
    assert resumed[-1]["fields"] == old["fields"]


def test_nontext_stop_keys_preserve_old_json_command_equality(tmp_path):
    out = decoded(tmp_path, "fix1-stop-equality.jsonl", text=False)
    hooks = next(row["turn_end"]["hooks"] for row in events(out) if row["turn_end"])
    old = [
        row
        for row in CONTROLS["cases"]["fix1-stop-equality.jsonl"]["rows"]
        if row["table"] == "hook_runs"
    ]
    assert hooks == [{k: row[k] for k in ["duration_ms", "blocked", "reason_bytes"]} for row in old]
    assert all(hook["blocked"] for hook in hooks)


@pytest.mark.parametrize("variant", ["finite-overflow", "mixed-overflow", "large-integer"])
def test_overwritten_numeric_overflow_keeps_raw_components_until_old_flush(tmp_path, variant):
    name = "fix2-usage-overwritten-" + variant + ".jsonl"
    out = decoded(tmp_path, name)
    rows = events(out)
    native = json.loads((FIXTURES / "index" / name).read_text().splitlines()[0])["message"]["usage"]
    first = rows[0]["response"]
    assert first["native"] == native
    for decoded_name, native_name in [
        ("input_uncached", "input_tokens"),
        ("cache_write", "cache_creation_input_tokens"),
        ("cache_read", "cache_read_input_tokens"),
    ]:
        assert first["usage"][decoded_name] == native[native_name]
    if variant != "large-integer":
        assert first["usage"]["context_total"] is None
        assert first["usage"]["uncached_total"] is None
    else:
        assert first["usage"]["context_total"] == 10**400 + 1
    old = next(row for row in CONTROLS["cases"][name]["rows"] if row["table"] == "turns")
    assert rows[-1]["response"]["usage"]["context_total"] == old["context_tokens"] == 1
    assert rows[-1]["response"]["native"] == old["native"]


@pytest.mark.parametrize("variant", ["finite-overflow", "mixed-overflow", "large-integer"])
def test_surviving_numeric_overflow_retains_old_flush_outcome(tmp_path, variant):
    import math

    name = "fix2-usage-surviving-" + variant + ".jsonl"
    old = CONTROLS["cases"][name]
    if "error" in old:
        proc = command(tmp_path, FIXTURES / "index" / name)
        assert (
            proc.returncode != 0 and old["error"] == "OverflowError" and old["error"] in proc.stderr
        )
        assert "in _flush" in proc.stderr
        return
    row = events(decoded(tmp_path, name))[0]["response"]
    turn = next(item for item in old["rows"] if item["table"] == "turns")
    assert row["native"] == turn["native"]
    usage = row["usage"]
    reconstructed = usage["input_uncached"] + usage["cache_write"] + usage["cache_read"]
    if variant == "finite-overflow":
        assert turn["context_tokens"] == turn["uncached_tokens"] == {"$old_float": "inf"}
        assert usage["context_total"] is None and usage["uncached_total"] is None
        # Null aggregate means wire-unavailable; components still reproduce old arithmetic.
        assert math.isinf(reconstructed) and reconstructed > 0
    else:
        assert usage["context_total"] == reconstructed == turn["context_tokens"] == 10**400 + 1
