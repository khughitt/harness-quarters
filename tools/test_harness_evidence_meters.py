"""Contract for line-resilient Codex meter scans through the decoder command."""
import json
import subprocess

import pytest

from test_harness_evidence_index_codex import TOOLS, environment, meter


def run(tmp_path, request):
    return subprocess.run([str(TOOLS / "harness-evidence"), "decode"], text=True,
                          input=json.dumps(request) + "\n", capture_output=True,
                          env=environment(tmp_path), timeout=60)


def test_meters_scan_mixed_records_with_physical_offsets(tmp_path):
    path = tmp_path / "rollout.jsonl"
    lines = [(json.dumps(meter(limits, timestamp)) + "\n").encode()
             for limits, timestamp in [
                 ({"credits": {"balance": "3.5"}}, "2026-09-04T09:38:28.000Z"),
                 ({}, "yesterday"),
                 ({"credits": {"balance": True}}, "2026-09-04T09:38:28.000Z"),
             ]]
    lines[2:2] = [b'["rate_limits"]\n',
                  b'{"type":"response_item","payload":{"type":"not-a-meter","rate_limits":[]}}\n',
                  b'{"unrelated":\n']
    lines.append((json.dumps(meter({"secondary": {"window_minutes": 10080, "used_percent": 17}}))
                  + "\n").encode())
    lines.append(b'{"rate_limits":')
    data = b"".join(lines)
    path.write_bytes(data + b'{} }\n')
    gone, unreadable = tmp_path / "vanished", tmp_path / "directory"
    unreadable.mkdir()
    request = {"id": 7, "extract": "meters", "roots": [{"harness": "codex", "path": str(tmp_path)}],
               "files": [{"path": str(path), "size": len(data)},
                         {"path": str(gone), "size": 1}, {"path": str(unreadable), "size": 1}]}
    proc = run(tmp_path, request)
    assert proc.returncode == 0 and not proc.stderr, proc.stderr
    rows = [json.loads(line) for line in proc.stdout.splitlines()]
    assert all(row["schema"] == "harness-evidence/1" and row["request"] == 7 for row in rows)
    assert [row["object"] for row in rows] == ["file_start", "meter_reading", "meter_reading",
        "file_end", "file_start", "file_end", "file_start", "file_end", "request_end"]
    assert [(row["key"], row["harness"], row["path"]) for row in rows if row["object"] == "file_start"] == [
        ("file", "codex", str(source)) for source in (path, gone, unreadable)]
    assert [(row["key"], row["line"], row["offset"], row["at_ms"], row["balance"], row["weekly_used_percent"])
            for row in rows if row["object"] == "meter_reading"] == [
        ("M1", 1, 0, 1788514708000, 3.5, None),
        ("M7", 7, sum(map(len, lines[:6])), 1788514708000, None, 17.0)]
    assert [(row["key"], row["status"], row["count"], row["malformed_lines"])
            for row in rows if row["object"] == "file_end"] == [
        ("end", "ok", 2, 3), ("end", "vanished", 0, 0), ("end", "unreadable", 0, 0)]
    assert rows[-1]["files"] == 3


@pytest.mark.parametrize("fields", [{"cross_file": True}, {"raw": True}, {"text": True},
                                    {"context": ["/file.jsonl"]}])
def test_meters_rejects_request_options_before_emitting_frames(tmp_path, fields):
    proc = run(tmp_path, {"id": 1, "extract": "meters", "files": [], **fields})
    assert proc.returncode == 2 and not proc.stdout
    assert "meters extraction requires" in proc.stderr
