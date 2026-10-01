"""status: fresh capture, healthy prune, empty quarantines (spec §3.5, §3.4.4)."""
import fcntl
import json
import os

import pytest
from datetime import datetime, timedelta, timezone

from session_archive.capture import capture_file
from session_archive.manifest import FILENAME, Manifest, Run
from session_archive.quarantine import QUARANTINE
from session_archive.status import status_report
from session_archive.testing import run_tool, write, write_config

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def stamp(delta):
    return (NOW - delta).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def run(manifest, kind, ago, ok=True, run_id=None):
    manifest.record_run(Run(run_id or f"{kind}-{ago}", kind, "apply", stamp(ago), stamp(ago), ok, {}))


def test_no_capture_is_unhealthy(manifest, tmp_path):
    report, ok = status_report(manifest, [tmp_path], NOW)
    assert not ok and report["capture"] is None


def test_fresh_capture_is_healthy(manifest, tmp_path):
    run(manifest, "capture", timedelta(hours=3))
    report, ok = status_report(manifest, [tmp_path], NOW)
    assert ok and report["capture"]["finished_at"] == stamp(timedelta(hours=3))


def test_stale_capture_failed_prune_and_quarantine_are_unhealthy(manifest, tmp_path):
    run(manifest, "capture", timedelta(hours=49))
    assert not status_report(manifest, [tmp_path], NOW)[1]
    run(manifest, "capture", timedelta(hours=1))
    run(manifest, "prune", timedelta(hours=2), ok=False)
    assert not status_report(manifest, [tmp_path], NOW)[1]
    run(manifest, "prune", timedelta(minutes=30))
    assert status_report(manifest, [tmp_path], NOW)[1]
    write(tmp_path / QUARANTINE / "r" / "f", b"x")
    report, ok = status_report(manifest, [tmp_path], NOW)
    assert not ok and report["quarantines"] == [str(tmp_path / QUARANTINE)]


def test_diverged_files_are_listed(manifest, archive, tmp_path):
    src = write(tmp_path / "live" / "p.jsonl", b"one\n")
    capture_file(archive, manifest, "claude", "p.jsonl", src)
    src.write_bytes(b"x")
    capture_file(archive, manifest, "claude", "p.jsonl", src)
    report, _ = status_report(manifest, [tmp_path], NOW)
    assert report["diverged"] == ["claude/p.jsonl"] and report["archive_bytes"] == 5


def test_status_command_ignores_the_lock(home, archive, manifest):
    write_config(home, archive)
    fd = os.open(archive / ".lock", os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        result = run_tool("status", home=home)
    finally:
        os.close(fd)
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


@pytest.mark.parametrize("ago, expected", [
    (timedelta(hours=48), True),
    (timedelta(hours=48, microseconds=1), False),
])
def test_capture_freshness_boundary(manifest, tmp_path, ago, expected):
    run(manifest, "capture", ago)
    assert status_report(manifest, [tmp_path], NOW)[1] is expected


def test_failed_capture_does_not_refresh_last_success(manifest, tmp_path):
    run(manifest, "capture", timedelta(hours=49))
    run(manifest, "capture", timedelta(hours=1), ok=False)
    report, ok = status_report(manifest, [tmp_path], NOW)
    assert not ok and report["capture"]["finished_at"] == stamp(timedelta(hours=49))


def test_status_command_is_healthy_and_preserves_manifest(home, archive):
    write_config(home, archive)
    assert run_tool("capture", home=home).returncode == 0
    database = archive / FILENAME
    before = database.read_bytes(), database.stat().st_mtime_ns
    result = run_tool("status", home=home)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True and report["capture"]["ok"] is True
    assert report["capture"]["report"] and report["prune"] is None
    assert (database.read_bytes(), database.stat().st_mtime_ns) == before


def test_status_does_not_initialize_manifest(home, archive):
    write_config(home, archive)
    result = run_tool("status", home=home)
    assert result.returncode == 1 and json.loads(result.stdout)["ok"] is False
    assert not (archive / FILENAME).exists()


def test_failed_prune_record_makes_status_unhealthy(home, archive, manifest):
    # The real prune command records an obs failure; fresh capture isolates prune health.
    write_config(home, archive, obs_command=("false",))
    assert run_tool("capture", home=home).returncode == 0
    assert run_tool("status", home=home).returncode == 0
    result = run_tool("prune", home=home)
    assert result.returncode == 1
    recorded = manifest.last_run("prune")
    assert recorded is not None and not recorded.ok
    result = run_tool("status", home=home)
    report = json.loads(result.stdout)
    assert result.returncode == 1 and report["ok"] is False
    assert report["prune"]["run_id"] == recorded.run_id
    assert report["prune"]["mode"] == "dry-run" and report["prune"]["ok"] is False
    assert report["prune"]["report"]["error"].startswith("ObsUnavailable:")


def test_status_reports_quarantine_io_failure(home, archive, manifest, monkeypatch, capsys):
    from argparse import Namespace
    from session_archive import cli, config, quarantine

    root = home / ".claude" / QUARANTINE
    write(root / "old" / "f", b"x")
    open_nofollow = quarantine.open_nofollow

    def unreadable(path, flags):
        if path == root:
            raise PermissionError("quarantine cannot be read")
        return open_nofollow(path, flags)

    monkeypatch.setattr(quarantine, "open_nofollow", unreadable)
    cfg = config.Config(archive, ("unused-obs",), ())
    assert cli.cmd_status(cfg, config.sources(home), Namespace()) == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == {
        "ok": False, "error": "PermissionError: quarantine cannot be read"}
    assert not output.err


@pytest.mark.parametrize("field, value, error_kind", [
    ("report", "not json", "JSONDecodeError"),
    ("finished_at", "not a timestamp", "ValueError"),
])
def test_status_reports_malformed_manifest(home, archive, manifest, field, value, error_kind):
    write_config(home, archive)
    run(manifest, "capture", timedelta(hours=1))
    with manifest.conn:
        manifest.conn.execute(f"UPDATE runs SET {field} = ? WHERE kind = 'capture'", (value,))
    result = run_tool("status", home=home)
    report = json.loads(result.stdout)
    assert result.returncode == 1 and report["ok"] is False
    assert report["error"].startswith(error_kind + ":")
    assert not result.stderr
