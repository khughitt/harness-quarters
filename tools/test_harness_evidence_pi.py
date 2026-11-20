"""Pi v3 index evidence through discovery and held-source framing."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from harness_evidence import DECODER_VERSION, SCHEMA, discover, index_stream


TOOLS = Path(__file__).resolve().parent
FIXTURE = TOOLS / "fixtures/session-logs/pi/session.jsonl"
ENVELOPE = {"schema": SCHEMA, "decoder": {"version": DECODER_VERSION, "revision": "test"}}


@pytest.fixture
def session(tmp_path):
    path = tmp_path / "isolated" / "session.jsonl"
    path.parent.mkdir()
    path.write_bytes(FIXTURE.read_bytes())
    return path


def frame(path, *, state=None, text=False):
    info = path.stat()
    request = {"id": 1, "extract": "index", "text": text,
               "roots": [{"harness": "pi", "path": str(path.parent)}],
               "files": [{"path": str(path), "size": info.st_size, "state": state,
                          "identity": {"device": info.st_dev, "inode": info.st_ino}}]}
    values = list(index_stream.objects(request, ENVELOPE))
    assert values[-1]["object"] == "request_end"
    return values[:-1]


def responses(rows):
    return [row for row in rows if row.get("response") is not None]


def write(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_pi_discovery_isolated_root(session, tmp_path):
    home = tmp_path / "home"
    default = home / ".pi" / "agent" / "sessions" / "project"
    default.mkdir(parents=True)
    (default / "other.jsonl").write_bytes(FIXTURE.read_bytes())
    assert any(root.harness == "pi" and root.path == default.parent for root in discover.roots(home))
    result = subprocess.run(
        [sys.executable, str(TOOLS / "harness-evidence"), "discover", "--root", f"pi={session.parent}"],
        cwd=tmp_path, env={"PATH": os.defpath, "HOME": str(home), "GIT_CONFIG_GLOBAL": os.devnull,
                           "GIT_CONFIG_NOSYSTEM": "1"}, text=True, capture_output=True, check=True,
    )
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert [(row["harness"], row["path"]) for row in rows if row["object"] == "file"] == [("pi", str(session))]
    assert rows[-1]["roots"] == 1


def test_pi_usage_and_effective_changes(session):
    events = responses(frame(session))
    first, retry = [event["response"] for event in events[:2]]
    assert events[0]["identity"]["index_session"] == "pi-example"
    assert events[0]["at_ms"] == 1767225604000
    assert (first["model"], first["effort"]) == ("kimi-k3.1-pro", None)
    assert (retry["model"], retry["effort"]) == ("glm-5.3", "high")
    assert first["native"]["requestedThinkingLevel"] == "high"  # Branch selection.
    assert retry["native"]["requestedThinkingLevel"] == "high"  # Per-response request.
    assert events[0]["provenance"]["response.model"]["rule"] == "pi_requested_model"
    assert first["usage"] == {"input_uncached": 100, "cache_read": 900, "cache_write": None,
                              "output": 50, "thinking": None, "context_total": 1000,
                              "uncached_total": 100}
    assert retry["usage"]["context_total"] == 104
    assert retry["usage"]["output"] == 15
    assert "Example answer" not in json.dumps(frame(session))
    assert "Example answer" in json.dumps(frame(session, text=True))


def test_pi_resume_fork_charge_identity(session):
    records = [json.loads(line) for line in session.read_text().splitlines()]
    original = frame(session)
    original_ids = [event["response"]["id"] for event in responses(original)]
    fork = session.with_name("fork.jsonl")
    duplicate = {**records[4], "parentId": "00000002"}  # Native branch can rechain copied entries.
    retry = {**records[4], "id": "0000000d", "parentId": records[4]["id"],
             "timestamp": "2026-01-01T00:00:21.000Z"}
    header = {**records[0], "id": "pi-fork", "parentSession": str(session),
              "timestamp": "2026-01-01T00:00:20.000Z"}
    write(fork, [header, *records[1:3], duplicate, retry])
    fork_rows = frame(fork)
    copied, fresh = responses(fork_rows)
    assert copied["identity"]["parent"] == "pi-example"
    assert copied["response"]["id"] == original_ids[0]
    assert copied["fork_boundary"]["copied_response"]
    assert fresh["response"]["id"] not in original_ids
    with fork.open("a") as handle:
        handle.write(json.dumps({**retry, "id": "0000000e"}) + "\n")
    resumed = frame(fork, state=fork_rows[-1]["state"])
    assert len(responses(resumed)) == 1
    assert resumed[0]["replaces"] == {"from_line": 6}
    session.unlink()
    degraded = frame(fork, state=resumed[-1]["state"])
    assert degraded[0]["replaces"] == "all"
    assert "unresolved" in responses(degraded)[0]["provenance"]["response.id"]["rule"]


def test_pi_auxiliary_usage(session):
    rows = {row["native_kind"]: row["response"] for row in responses(frame(session))}
    assert [rows[k]["usage"]["output"] for k in ("usage", "compaction", "branch_summary")] == [None, 2, 3]
    assert rows["usage"]["native"]["kind"] == "cache_warm"
    assert rows["usage"]["model"] == "glm-5.3"


def test_pi_partial_missing_and_unknown(session):
    data = session.read_bytes()
    records = data.splitlines(keepends=True)
    session.write_bytes(b"".join(records[:-1]) + records[-1][:-4])
    first = frame(session)
    assert first[-2]["partial_tail"]
    assert responses(first)[-1]["response"]["usage_present"]["output"] is False
    assert responses(first)[-1]["response"]["usage"]["input_uncached"] is None
    with session.open("ab") as handle:
        handle.write(records[-1][-4:])
    resumed = frame(session, state=first[-1]["state"])
    assert not resumed[-2]["partial_tail"] and not responses(resumed)
    assert any(row["record_kind"] == "future_record" and row["known"] == 0
               for row in resumed[-2]["records"])
    session.write_bytes(data.replace(b"Example answer", b"Changed answer"))
    assert frame(session, state=resumed[-1]["state"])[0]["replaces"] == "all"


@pytest.mark.parametrize("extra", [{}, {"reasoning": 0, "cacheWrite": 0}, {"reasoning": 3, "cacheWrite": 2}])
@pytest.mark.parametrize("blocks", [[], [{"type": "thinking", "thinking": "Invisible"}]])
def test_pi_openai_zero_breakdowns_are_unrecorded(session, extra, blocks):
    raw = [json.loads(line) for line in session.read_text().splitlines()]
    message = raw[4]["message"]
    message.update(content=blocks, usage={"input": 10, "cacheRead": 90, "output": 5, **extra})
    write(session, raw[:5])
    response = responses(frame(session))[0]["response"]
    assert response["usage_present"] == {"output": True, "thinking": False}
    assert response["usage"]["cache_write"] is response["usage"]["thinking"] is None
    for key in ("reasoning", "cacheWrite"):
        assert response["native"].get(key) == extra.get(key)
    catalogue = json.loads((TOOLS / "harness_evidence/capabilities.json").read_text())
    absent = catalogue["harnesses"]["pi"]["index"]["absent"]
    assert absent["response.usage.thinking"] == absent["response.usage.cache_write"] == "not_recorded"


def test_pi_parent_evidence_stays_in_the_selected_store(session, tmp_path):
    rows = [json.loads(line) for line in session.read_text().splitlines()]
    foreign = tmp_path / "foreign.jsonl"
    write(foreign, rows)
    outside = session.with_name("outside.jsonl")
    outside.symlink_to(foreign)
    child = session.with_name("child.jsonl")
    for path in (foreign, outside):
        write(child, [{**rows[0], "id": "pi-child", "parentSession": str(path),
                      "timestamp": "2026-01-01T00:00:20Z"}, *rows[1:5]])
        frames = frame(child)
        copy = responses(frames)[0]
        assert frames[0]["path_facts"]["reason"] == "parent_unavailable"
        assert copy["response"]["id"] == "pi-child:00000004"
        assert copy["identity"]["parent"] is None
        assert copy["provenance"]["response.id"]["rule"] == "unresolved:pi_fork_origin"


def test_pi_held_header_and_reader_boundary(session, tmp_path):
    from io import StringIO
    from harness_evidence import header
    from harness_evidence._protocol import ProtocolError
    from harness_evidence import stream

    info = session.stat()
    request = {"id": 1, "roots": [{"harness": "pi", "path": str(session.parent)}],
               "files": [{"path": str(session), "size": info.st_size,
                          "identity": {"device": info.st_dev, "inode": info.st_ino}}]}
    stdout, stderr = StringIO(), StringIO()
    assert header.run(StringIO(json.dumps(request) + "\n"), stdout, stderr, ENVELOPE) == 0
    first, last = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert first["status"] == "ok" and first["header"]["session"] == "pi-example"
    assert first["provenance"]["session"]["native_paths"] == ["id"]
    assert last["object"] == "request_end"
    request["files"][0].pop("identity")
    with pytest.raises(ProtocolError, match="supports only extract:index"):
        list(stream.objects(request, ENVELOPE))


def test_pi_sanitized_observed_transport_sample(session):
    session.write_bytes(FIXTURE.with_name("sanitized-observed.jsonl").read_bytes())
    response = responses(frame(session))[0]["response"]
    message = json.loads(session.read_text().splitlines()[1])["message"]
    assert response["native"]["api"] == message["api"]
    assert response["native"]["input"] == message["usage"]["input"]
    assert response["usage"]["output"] == message["usage"]["output"]


def test_pi_partial_usage_defaults_and_summary_population(session):
    rows = [json.loads(line) for line in session.read_text().splitlines()]
    partial = {**rows[4], "message": {**rows[4]["message"], "stopReason": "aborted",
               "usage": {"input": 100, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 100}}}
    empty_compaction = {**rows[9], "usage": {"input": 0, "cacheRead": 0, "output": 0}}
    no_usage_summary = {key: value for key, value in rows[10].items() if key != "usage"}
    hook_summary = {**no_usage_summary, "id": "0000000f", "fromHook": True}
    write(session, [*rows[:4], partial, empty_compaction, no_usage_summary, hook_summary])
    observed = responses(frame(session))
    assert observed[0]["response"]["usage"]["input_uncached"] == 100
    assert observed[0]["response"]["usage"]["output"] is None
    assert observed[0]["response"]["usage_present"]["output"] is False
    assert observed[0]["response"]["native"]["output"] == 0
    assert [row["native_kind"] for row in observed] == ["message", "compaction", "branch_summary"]
    for row in observed[1:]:
        assert not row["response"]["usage_present"]["output"]
        assert not any(value is not None for value in row["response"]["usage"].values())
    output_coverage = next(row for row in frame(session)[-2]["fields"]
                           if row["record_kind"] == "applied:usage" and row["field"] == "input:output")
    assert (output_coverage["seen"], output_coverage["present"]) == (3, 0)


def test_pi_retains_served_model_and_effective_effort(session):
    rows = [json.loads(line) for line in session.read_text().splitlines()]
    rows[4]["message"].update(responseModel="kimi-served-revision", providerThinkingLevel="max", thinkingLevel="high")
    write(session, rows[:5])
    response = responses(frame(session))[0]["response"]
    assert (response["model"], response["effort"]) == ("kimi-served-revision", "max")
    assert response["native"]["requestedModel"] == "kimi-k3.1-pro"
    assert response["native"]["requestedThinkingLevel"] == "high"


def test_pi_copied_entry_proof_survives_clock_regression(session):
    rows = [json.loads(line) for line in session.read_text().splitlines()]
    root = responses(frame(session))[0]["response"]["id"]
    fork = session.with_name("skewed-fork.jsonl")
    write(fork, [{**rows[0], "id": "pi-fork", "parentSession": str(session),
                  "timestamp": "2025-12-31T23:59:00Z"},
                 *rows[1:5],
                 {**rows[4], "id": "ff00ff00", "parentId": rows[4]["id"],
                  "timestamp": "2025-12-31T23:59:02Z"}])
    copied, retry = responses(frame(fork))
    assert copied["response"]["id"] == root
    assert retry["response"]["id"] == "pi-fork:ff00ff00"
