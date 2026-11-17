"""Native index contracts against controls exported by frozen obs0a09481c.

These checks catch native extraction loss, byte-size changes, coverage population
changes and a reader request accidentally entering the opt-in index path.
"""

import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

import pytest

from harness_evidence import DECODER_VERSION

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


def expand_proofs(event, defaults):
    """Independent wire-contract expansion, compared to complete native proofs."""
    return {field: {**copy.deepcopy(proof), "ref": event["ref"],
                    "revision": event["decoder"]["revision"],
                    **copy.deepcopy(event["provenance"].get(field, {}))}
            for field, proof in defaults.items()}


def events(out):
    defaults = out[0]["provenance_defaults"]
    return [{**v, "provenance": expand_proofs(v, defaults)}
            for v in out if v["object"] == "index_event"]


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
        assert row["decoder"]["version"] == DECODER_VERSION
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
    hooks = next(v for v in resumed if v["object"] == "index_event")["turn_end"]["hooks"]
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


def test_usage_storage_presence_preserves_old_defaults_and_values(tmp_path):
    controls = json.loads((FIXTURES / "index/task2-usage-storage-controls.json").read_text())
    source = FIXTURES / "index" / controls["source"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == controls["sha256"]
    out = decoded(tmp_path, source.name)
    emitted = events(out)
    assert len(emitted) == len(controls["events"]) == 25
    turns = {v["response_id"]: v for v in controls["rows"] if v["table"] == "turns"}
    for event, expected in zip(emitted, controls["events"]):
        response = event["response"]
        assert response["id"] == expected["response"]
        assert response["usage_present"] == expected["usage_present"], expected["label"]
        assert all(type(value) is bool for value in response["usage_present"].values())
        if expected["final_fragment"]:
            old = turns[response["id"]]
            for field in ("output", "thinking"):
                value = response["usage"][field] if response["usage_present"][field] else 0
                assert value == old[field + "_tokens"], expected["label"]
                assert type(value) is type(old[field + "_tokens"]), expected["label"]
    by_id = {v["response"]["id"]: v["response"] for v in emitted}
    assert by_id["absent"]["usage"]["output"] is None
    assert by_id["explicit-null"]["usage"]["output"] is None
    assert by_id["absent"]["usage_present"] == {"output": False, "thinking": False}
    assert by_id["explicit-null"]["usage_present"] == {"output": True, "thinking": True}
    assert by_id["empty-string"]["usage"]["output"] == ""
    assert by_id["empty-containers"]["usage"]["output"] == []
    assert by_id["empty-containers"]["usage"]["thinking"] == {}
    measured = next(v for v in out if v["object"] == "coverage")
    assert measured["records"] == controls["records"]
    assert measured["fields"] == controls["fields"]


def test_usage_presence_is_safe_for_invalid_overwritten_fragments(tmp_path):
    controls = json.loads((FIXTURES / "index/task2-usage-storage-controls.json").read_text())
    emitted = events(decoded(tmp_path, controls["source"]))
    firsts = [(v["response"], expected) for v, expected in zip(emitted, controls["events"])
              if not expected["final_fragment"]]
    assert len(firsts) == 4
    for response, expected in firsts:
        assert response["usage_present"] == expected["usage_present"]
        assert response["usage_present"]["thinking"] is False
    assert firsts[0][0]["native"] == "transient"
    assert firsts[1][0]["native"] == [1]
    assert firsts[2][0]["usage"]["output"] == 7
    assert firsts[3][0]["usage"]["output"] == 7


@pytest.mark.parametrize("name", ["fix1-usage-final-nested.jsonl", "fix1-usage-final-nonmapping.jsonl", "fix1-usage-final-list.jsonl"])
def test_usage_presence_does_not_move_final_invalid_failure_earlier(tmp_path, name):
    proc = command(tmp_path, FIXTURES / "index" / name)
    assert proc.returncode != 0 and CONTROLS["cases"][name]["error"] in proc.stderr
    out = [json.loads(line) for line in proc.stdout.splitlines()]
    response = events(out)[0]["response"]
    assert response["usage_present"] == {"output": False, "thinking": False}
    assert not any(v["object"] in {"file_end", "request_end"} for v in out)


def test_usage_presence_has_native_provenance_and_no_new_populations(tmp_path):
    out = decoded(tmp_path, "task2-usage-storage.jsonl")
    for field, native in [("output", "output_tokens"), ("thinking", "output_tokens_details.thinking_tokens")]:
        provenance = events(out)[0]["provenance"]["response.usage_present." + field]
        assert provenance["native_paths"] == ["message.usage." + native]
        assert provenance["coverage_keys"] == ["applied:usage/input:" + native.rsplit(".", 1)[-1]]
        assert provenance["basis"] == "native" and provenance["rule"] == "claude_native"
    old = json.loads((FIXTURES / "index/task2-usage-storage-controls.json").read_text())
    measured = next(v for v in out if v["object"] == "coverage")
    assert measured["records"] == old["records"] and measured["fields"] == old["fields"]


POLICY_CONTROLS = json.loads((FIXTURES / "index/task2-policy-controls.json").read_text())


@pytest.mark.parametrize("name", sorted(POLICY_CONTROLS["cases"]))
def test_native_question_answer_duration_json_matches_old_controls(tmp_path, name):
    control = POLICY_CONTROLS["cases"][name]
    source = FIXTURES / "index" / name
    assert hashlib.sha256(source.read_bytes()).hexdigest() == control["sha256"]
    assert control["outcome"]["native"] == "success"
    out = decoded(tmp_path, name)
    rows = events(out)
    assert len(rows) == 2
    native = control["native"]
    call = rows[0]["calls"][0]
    if native["pending_question"]:
        assert call["questions"][0]["question"] == native["question"]
        assert type(call["questions"][0]["question"]) is type(native["question"])
        assert call["questions"][0]["options"] == [{"label": "A (Recommended)"}, {"label": "B"}]
    else:
        assert call["kind"] == "shell" and call["questions"] == []
    result = rows[1]["results"][0]
    for field in ("answers", "native_duration_ms"):
        assert result[field] == native[field]
        assert type(result[field]) is type(native[field])
    completed = [v for v in control["rows"] if v["table"] == "tool_calls" and v["duration_ms"] is not None]
    assert completed[-1]["duration_ms"] == native["result_elapsed_ms"] == 2000
    assert control["sessions"]
    measured = next(v for v in out if v["object"] == "coverage")
    assert measured["records"] == control["records"]
    assert measured["fields"] == control["fields"]


def test_policy_controls_distinguish_native_success_from_consumer_failure():
    failures = [v for v in POLICY_CONTROLS["cases"].values() if v["outcome"]["consumer"] == "error"]
    assert {v["label"] for v in failures} == {"pending-truthy-string", "pending-truthy-integer", "pending-truthy-list", "pending-truthy-boolean"}
    for control in failures:
        assert control["error"] == "AttributeError"
        assert control["error_category"] == "consumer_policy" and control["error_site"] == "_score_answers"
        assert control["partial_old_state"] and control["outcome"]["native"] == "success"
        assert control["rows"] and control["sessions"] and control["fields"]
    for label in ("question-null", "question-integer"):
        control = POLICY_CONTROLS["cases"]["task2-policy-" + label + ".jsonl"]
        assert control["outcome"]["consumer"] == "success"
        assert control["sessions"][0]["rec_accepted"] == 1


PROVENANCE_ORACLE = json.loads((TOOLS / "fixtures/harness-evidence/index-provenance-oracle.json").read_text())


def oracle_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


# Shared stream additions made after the frozen oracle (spec rev 2 §4.4). Claude emits
# `results[].exit_code` as null and declares it absent, so the oracle compares without it.
POST_ORACLE_DECLARATIONS = {"results[].exit_code": {
    "native_paths": [], "coverage_keys": [], "basis": "native", "rule": "absent:not_decoded"}}


# Declarations widened after the oracle: the current value, then the oracle's. Claude's
# compaction now also reads the boundary and the idle notice that name one compaction.
POST_ORACLE_CHANGED = {"compaction": (
    {"native_paths": ["isCompactSummary", "subtype", "uuid", "parentUuid", "isMeta",
                      "compactMetadata.trigger", "content"],
     "coverage_keys": [], "basis": "native", "rule": "claude_native"},
    {"native_paths": ["isCompactSummary"], "coverage_keys": [], "basis": "native",
     "rule": "claude_native"})}
# Fixtures added after the oracle; their rows have no frozen counterpart.
POST_ORACLE_FIXTURES = frozenset({"index/compaction-reasons.jsonl"})
# Compaction keys added after the oracle; the oracle's fixtures hold no boundary or notice.
POST_ORACLE_COMPACTION_KEYS = ("id", "trigger", "reason")


def pre_oracle_defaults(defaults):
    assert {field: defaults[field] for field in POST_ORACLE_DECLARATIONS} == POST_ORACLE_DECLARATIONS
    defaults = {field: proof for field, proof in defaults.items() if field not in POST_ORACLE_DECLARATIONS}
    for field, (current, oracle) in POST_ORACLE_CHANGED.items():
        assert defaults[field] == current, field
        defaults[field] = copy.deepcopy(oracle)
    return defaults


def pre_oracle_row(value):
    value = copy.deepcopy(value)
    if value["object"] == "index_event":
        for result in value["results"]:
            assert result.pop("exit_code") is None
        if value["compaction"] is not None:
            for key in POST_ORACLE_COMPACTION_KEYS:
                assert value["compaction"].pop(key) is None, key
        assert not POST_ORACLE_DECLARATIONS.keys() & value["provenance"].keys()
    return value


def oracle_rows(rows, defaults):
    defaults = pre_oracle_defaults(defaults)
    result = []
    for value in rows:
        ordinary = pre_oracle_row(value)
        if ordinary["object"] == "index_event":
            proof = expand_proofs(ordinary, defaults)
            ordinary.pop("provenance")
        else:
            proof = None
        for key in ("schema", "decoder", "request", "file", "harness", "harness_version"):
            ordinary.pop(key, None)
        result.append({"ordinary": oracle_hash(ordinary),
                       "provenance": oracle_hash(proof) if proof is not None else None})
    return result


@contextmanager
def oracle_error(error):
    # Native messages are the contract; interpreter wording varies across Python3.11+.
    import builtins
    kind = getattr(builtins, error["type"])
    with pytest.raises(kind) as observed:
        yield
    assert type(observed.value) is kind
    if error["message"].startswith("Claude "):
        assert str(observed.value) == error["message"]


def oracle_native_case(case):
    from harness_evidence import discover, index_events
    path = FIXTURES / case["fixture"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == PROVENANCE_ORACLE["fixtures"][case["fixture"]]
    defaults = index_events.provenance_defaults()
    assert pre_oracle_defaults(defaults) == PROVENANCE_ORACLE["declarations"]
    place = discover.place_of(Path(case["logical"]), discover.roots(
        explicit=[("claude-code", Path("/oracle/.claude/projects"))]))
    state = {}
    for old in case["passes"]:
        if case["schedule"] == "prefix":
            state = {}
        working = copy.deepcopy(state)
        offset, lines = 0, []
        for raw in path.read_bytes()[:old["size"]].splitlines(keepends=True):
            if offset >= working.get("next_offset", 0):
                lines.append((offset, raw))
            offset += len(raw)
        rows = []
        def consume():
            for value in index_events.extract(lines, working, place=place, text=case["text"]):
                rows.append({**value, "decoder": {"revision": PROVENANCE_ORACLE["proof_revision"]}})
        if old["error"]:
            with oracle_error(old["error"]):
                consume()
        else:
            consume()
            state = working
        assert oracle_rows(rows, defaults) == old["rows"], (case["fixture"], case["layout"], old["through_line"])
        assert oracle_hash(working) == old["native_state"]


COMPACTION_PATHS = ["isCompactSummary", "subtype", "uuid", "parentUuid", "isMeta",
                    "compactMetadata.trigger", "content"]


def compaction_rows(rows):
    return [(row["line"], row["compaction"]) for row in rows if row["compaction"]]


def compaction(id_, summary=False, trigger=None, reason=None, rule="compact_boundary"):
    return {"summary": summary, "id": id_, "trigger": trigger, "reason": reason,
            "basis": "native", "rule": rule}


EXPECTED_COMPACTIONS = [
    (2, compaction("b1", trigger="auto")),
    (3, compaction("b1", summary=True, rule="compact_summary")),
    # An injected (isMeta) user record between the attachments and the notice extends the chain.
    (8, compaction("b1", reason="idle", rule="idle_compaction_notice")),
    (10, compaction("b2", trigger="manual")),
    (11, compaction("b2", summary=True, rule="compact_summary")),
    (14, compaction("b3", trigger="auto")),
    (15, compaction("b3", summary=True, rule="compact_summary")),
    # Typed input closed b3's chain, so this notice names no compaction.
    (17, compaction(None, reason="idle", rule="idle_compaction_notice")),
    # Claude can write attachments between a boundary and its summary.
    (19, compaction("b4", trigger="auto")),
    (21, compaction("b4", summary=True, rule="compact_summary")),
    (22, compaction("b4", reason="idle", rule="idle_compaction_notice")),
]


def test_claude_compaction_reasons_pair_boundary_summary_and_idle_notice(tmp_path):
    rows = events(decoded(tmp_path, "compaction-reasons.jsonl"))
    assert compaction_rows(rows) == EXPECTED_COMPACTIONS
    # One compaction each: only the summary event is the compaction count.
    assert sum(1 for _, value in compaction_rows(rows) if value["summary"]) == 4
    # An unrelated informational notice is not a compaction.
    assert next(row for row in rows if row["line"] == 18)["compaction"] is None
    proof = next(row for row in rows if row["line"] == 8)["provenance"]["compaction"]
    assert proof["native_paths"] == COMPACTION_PATHS and proof["basis"] == "native"


@pytest.mark.parametrize("cut", range(1, 22))
def test_claude_compaction_pairing_survives_every_native_slice_boundary(cut):
    from harness_evidence.index_events import extract
    from harness_evidence.lines import Place

    source = FIXTURES / "index/compaction-reasons.jsonl"
    raw = source.read_bytes().splitlines(keepends=True)
    offsets = [sum(len(line) for line in raw[:n]) for n in range(len(raw))]
    place = Place("claude-code", "file", None, "explicit", str(source), source)
    state = {}
    first = list(extract(list(zip(offsets[:cut], raw[:cut])), state, place=place, text=False))
    state = json.loads(json.dumps(state))  # The checkpoint persists state as JSON.
    second = list(extract(list(zip(offsets[cut:], raw[cut:])), state, place=place, text=False))
    rows = [v for v in first + second if v["object"] == "index_event"]
    assert compaction_rows(rows) == EXPECTED_COMPACTIONS


def test_claude_compaction_state_is_dropped_once_its_chain_closes():
    from harness_evidence.index_events import extract
    from harness_evidence.lines import Place

    source = FIXTURES / "index/compaction-reasons.jsonl"
    raw = source.read_bytes().splitlines(keepends=True)
    offsets = [sum(len(line) for line in raw[:n]) for n in range(len(raw))]
    place = Place("claude-code", "file", None, "explicit", str(source), source)
    state = {}
    list(extract(list(zip(offsets, raw)), state, place=place, text=False))
    assert "compaction_chain" not in state


@pytest.mark.parametrize("metadata, message", [
    ({"trigger": 5}, "trigger is not a string"),
    ({"trigger": ["auto"]}, "trigger is not a string"),
    ("auto", "compactMetadata is not an object"),
])
def test_claude_compaction_refuses_a_malformed_trigger(metadata, message):
    from harness_evidence.index_events import extract
    from harness_evidence.lines import Place

    source = FIXTURES / "index/compaction-reasons.jsonl"
    record = json.loads(source.read_bytes().splitlines()[1])
    record["compactMetadata"] = metadata
    place = Place("claude-code", "file", None, "explicit", str(source), source)
    with pytest.raises(TypeError, match=f"^Claude compact_boundary {message}$"):
        list(extract([(0, (json.dumps(record) + "\n").encode())], {}, place=place, text=False))


def test_claude_compaction_trigger_is_null_only_when_absent():
    from harness_evidence.index_events import extract
    from harness_evidence.lines import Place

    source = FIXTURES / "index/compaction-reasons.jsonl"
    place = Place("claude-code", "file", None, "explicit", str(source), source)
    for absent in ({"preTokens": 1}, {"trigger": None}, None):
        record = json.loads(source.read_bytes().splitlines()[1])
        if absent is None:
            record.pop("compactMetadata")
        else:
            record["compactMetadata"] = absent
        rows = [v for v in extract([(0, (json.dumps(record) + "\n").encode())], {}, place=place,
                                   text=False) if v["object"] == "index_event"]
        assert rows[0]["compaction"]["trigger"] is None
