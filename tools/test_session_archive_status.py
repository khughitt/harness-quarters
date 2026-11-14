"""status: fresh capture, healthy prune, empty quarantines (docs/session-archive.md)."""
import fcntl
import json
import os

import pytest

import harness_stores
from datetime import datetime, timedelta, timezone

from session_archive import replica
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


@pytest.mark.parametrize("success_age, expected", [
    (timedelta(hours=49), False),
    (timedelta(hours=3), True),
])
def test_latest_failed_capture_is_reported_without_refreshing_success(manifest, tmp_path,
                                                                    success_age, expected):
    run(manifest, "capture", success_age)
    run(manifest, "capture", timedelta(hours=1), ok=False)
    report, ok = status_report(manifest, [tmp_path], NOW)
    assert ok is expected
    assert report["capture"]["finished_at"] == stamp(timedelta(hours=1))
    assert report["capture"]["ok"] is False


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
    assert cli.cmd_status(cfg, harness_stores.archive_sources(home), Namespace()) == 1
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


def _seed_healthy_replica(tmp_path, archive, manifest, receipt_ago=timedelta(hours=2)):
    run(manifest, "capture", timedelta(hours=1))
    run(manifest, "replicate", receipt_ago, ok=True)
    run(manifest, "verify-replica", timedelta(days=10), ok=True)
    rep = tmp_path / "replica"
    rep.mkdir(exist_ok=True)
    (rep / replica.MARKER).touch()
    gen_name = "20261001T100000.000000Z"
    gen_dir = rep / "generations" / gen_name
    gen_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "generation": gen_name,
        "archive_root": str(archive),
        "replica_root": str(rep),
        "archive_disks": ["sdc"],
        "replica_disks": ["sdb"],
        "started_at": stamp(receipt_ago),
        "finished_at": stamp(receipt_ago),
        "rows": 0,
        "files_copied": 0,
        "bytes_copied": 0,
        "files_linked": 0,
        "bytes_linked": 0,
        "verified": True,
    }
    (gen_dir / "receipt.json").write_text(json.dumps(receipt))
    current = rep / "current"
    if current.is_symlink() or current.exists():
        current.unlink()
    current.symlink_to(f"generations/{gen_name}")
    return rep, gen_dir


def test_status_unconfigured_replica_omits_replica_key(manifest, tmp_path):
    run(manifest, "capture", timedelta(hours=1))
    report, ok = status_report(manifest, [tmp_path], NOW)
    assert ok is True
    assert "replica" not in report


def test_status_healthy_replica_and_restored_archive_with_no_replicate_rows(
    tmp_path, archive, manifest
):
    rep, _ = _seed_healthy_replica(tmp_path, archive, manifest)
    report, ok = status_report(manifest, [tmp_path], NOW, replica_root=rep)
    assert ok is True
    assert report["replica"]["ok"] is True
    assert report["replica"]["reasons"] == []
    assert report["replica"]["generation"] == "20261001T100000.000000Z"
    assert report["replica"]["receipt"]["verified"] is True
    assert report["replica"]["replicate"]["ok"] is True
    assert report["replica"]["verify_replica"]["ok"] is True

    # Restored archive: no replicate rows in manifest, but fresh receipt and passing verify-replica
    with manifest.conn:
        manifest.conn.execute("DELETE FROM runs WHERE kind = 'replicate'")
    report2, ok2 = status_report(manifest, [tmp_path], NOW, replica_root=rep)
    assert ok2 is True
    assert report2["replica"]["ok"] is True
    assert report2["replica"]["replicate"] is None
    assert report2["replica"]["reasons"] == []


def test_status_replica_each_unhealthy_reason_preserves_archive_report(
    tmp_path, archive, manifest
):
    rep, gen_dir = _seed_healthy_replica(tmp_path, archive, manifest)

    # 1. Missing replica directory
    report, ok = status_report(manifest, [tmp_path], NOW, replica_root=tmp_path / "missing-rep")
    assert not ok and not report["replica"]["ok"]
    assert any("missing" in r for r in report["replica"]["reasons"])
    assert report["capture"]["ok"] is True

    # 2. Missing marker file
    (rep / replica.MARKER).unlink()
    report, ok = status_report(manifest, [tmp_path], NOW, replica_root=rep)
    assert not ok and not report["replica"]["ok"]
    assert any("marker" in r for r in report["replica"]["reasons"])
    assert report["capture"]["ok"] is True
    (rep / replica.MARKER).touch()

    # 3. Missing current symlink
    (rep / "current").unlink()
    report, ok = status_report(manifest, [tmp_path], NOW, replica_root=rep)
    assert not ok and not report["replica"]["ok"]
    assert any("current" in r for r in report["replica"]["reasons"])
    assert report["capture"]["ok"] is True
    (rep / "current").symlink_to(f"generations/{gen_dir.name}")

    # 4. Unreadable/corrupt receipt.json
    saved_receipt = (gen_dir / "receipt.json").read_text()
    (gen_dir / "receipt.json").write_text("{not valid json")
    report, ok = status_report(manifest, [tmp_path], NOW, replica_root=rep)
    assert not ok and not report["replica"]["ok"]
    assert any("receipt" in r for r in report["replica"]["reasons"])
    assert report["capture"]["ok"] is True
    (gen_dir / "receipt.json").write_text(saved_receipt)

    # 5. Receipt finished_at older than 48 hours
    stale_receipt = json.loads(saved_receipt)
    stale_receipt["finished_at"] = stamp(timedelta(hours=48, microseconds=1))
    (gen_dir / "receipt.json").write_text(json.dumps(stale_receipt))
    report, ok = status_report(manifest, [tmp_path], NOW, replica_root=rep)
    assert not ok and not report["replica"]["ok"]
    assert any("48 hours" in r for r in report["replica"]["reasons"])
    (gen_dir / "receipt.json").write_text(saved_receipt)

    # 6. Last replicate run failed (even though receipt is fresh)
    run(manifest, "replicate", timedelta(minutes=30), ok=False, run_id="rep-fail")
    report, ok = status_report(manifest, [tmp_path], NOW, replica_root=rep)
    assert not ok and not report["replica"]["ok"]
    assert any("last replicate" in r for r in report["replica"]["reasons"])
    with manifest.conn:
        manifest.conn.execute("DELETE FROM runs WHERE run_id = 'rep-fail'")

    # 7. Last verify-replica run failed
    run(manifest, "verify-replica", timedelta(days=1), ok=False, run_id="ver-fail")
    report, ok = status_report(manifest, [tmp_path], NOW, replica_root=rep)
    assert not ok and not report["replica"]["ok"]
    assert any("last verify-replica" in r for r in report["replica"]["reasons"])
    with manifest.conn:
        manifest.conn.execute("DELETE FROM runs WHERE run_id = 'ver-fail'")

    # 8. No passing verify-replica within 35 days
    with manifest.conn:
        manifest.conn.execute("DELETE FROM runs WHERE kind = 'verify-replica'")
    run(manifest, "verify-replica", timedelta(days=35, microseconds=1), ok=True, run_id="ver-old")
    report, ok = status_report(manifest, [tmp_path], NOW, replica_root=rep)
    assert not ok and not report["replica"]["ok"]
    assert any("35 days" in r for r in report["replica"]["reasons"])

