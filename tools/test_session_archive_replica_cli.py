"""CLI tests for session-archive replicate and verify-replica (spec §3, §3.1, §3.5, §5)."""
import fcntl
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import harness_stores
from session_archive import cli, config, replica
from session_archive.testing import claude_session, codex_rollout, run_tool, write_config


def _set_home_env(monkeypatch, home: Path) -> None:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local/share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local/state"))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))


def _seed_live_sources(home: Path) -> dict[str, Path]:
    sources = {s.name: s.root for s in harness_stores.archive_sources(home)}
    claude_session(sources["claude"])
    codex_rollout(sources["codex"])
    return sources


def test_cli_in_process_e2e_capture_replicate_verify_and_status(
    tmp_path, home, archive, monkeypatch, capsys
):
    _set_home_env(monkeypatch, home)
    _seed_live_sources(home)

    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()
    write_config(home, archive, replica=rep)

    monkeypatch.setattr(
        cli,
        "DISKS",
        lambda p: frozenset({"sdc"}) if Path(p) == archive else frozenset({"sdb"}),
    )

    assert cli.main(["capture"]) == 0
    cap_out = json.loads(capsys.readouterr().out)
    assert cap_out["claude"]["copied"] == 3
    assert cap_out["codex"]["copied"] == 1

    assert cli.main(["replicate"]) == 0
    rep_out = json.loads(capsys.readouterr().out)
    assert rep_out["verified"] is True
    assert rep_out["rows"] == 4
    assert rep_out["files_copied"] == 4
    assert rep_out["files_linked"] == 0

    assert cli.main(["verify-replica"]) == 0
    ver_out = json.loads(capsys.readouterr().out)
    assert ver_out["generation"] == rep_out["generation"]
    assert ver_out["rows"] == rep_out["rows"]
    assert ver_out["bytes_read"] == rep_out["bytes_copied"]
    assert ver_out["failures"] == []

    assert cli.main(["status"]) == 0
    st_out = json.loads(capsys.readouterr().out)
    assert st_out["ok"] is True
    assert st_out["archive_bytes"] == rep_out["bytes_copied"]
    assert st_out["replica"]["ok"] is True
    assert st_out["replica"]["generation"] == rep_out["generation"]
    assert st_out["replica"]["receipt"]["rows"] == rep_out["rows"]
    assert st_out["replica"]["replicate"]["ok"] is True
    assert st_out["replica"]["verify_replica"]["ok"] is True
    assert st_out["replica"]["reasons"] == []


def test_cli_subprocess_same_disk_refused(tmp_path, home, archive):
    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()
    write_config(home, archive, replica=rep)

    result = run_tool("replicate", home=home)
    assert result.returncode == config.EX_HOST
    assert "same physical disk" in result.stderr
    assert not (rep / "generations").exists()


def test_cli_boundaries_missing_replica_and_missing_live_source(
    tmp_path, home, archive, monkeypatch, capsys
):
    _set_home_env(monkeypatch, home)
    sources = _seed_live_sources(home)

    # 1. With replica_root pointing at a missing directory, capture still exits 0
    absent_rep = tmp_path / "absent-replica"
    write_config(home, archive, replica=absent_rep)
    assert cli.main(["capture"]) == 0
    capsys.readouterr()

    # 2. With a valid replica and a required live source root removed, capture exits 2
    #    while replicate and verify-replica exit 0
    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()
    write_config(home, archive, replica=rep)
    monkeypatch.setattr(
        cli,
        "DISKS",
        lambda p: frozenset({"sdc"}) if Path(p) == archive else frozenset({"sdb"}),
    )

    shutil.rmtree(sources["claude"])
    assert cli.main(["capture"]) == config.EX_HOST
    err = capsys.readouterr().err
    assert "claude" in err

    t0 = datetime(2026, 11, 8, 6, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(cli, "CLOCK", lambda: t0)
    assert cli.main(["replicate"]) == 0
    rep_out = json.loads(capsys.readouterr().out)
    assert rep_out["rows"] == 4

    assert cli.main(["verify-replica"]) == 0
    ver_out = json.loads(capsys.readouterr().out)
    assert ver_out["rows"] == 4
    assert ver_out["failures"] == []


def test_cli_replicate_lock_timeout_exits_75(
    tmp_path, home, archive, monkeypatch, capsys
):
    _set_home_env(monkeypatch, home)
    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()
    write_config(home, archive, replica=rep)
    monkeypatch.setattr(
        cli,
        "DISKS",
        lambda p: frozenset({"sdc"}) if Path(p) == archive else frozenset({"sdb"}),
    )
    monkeypatch.setattr(cli, "REPLICA_LOCK_WAIT", 0.05)

    fd = os.open(archive / ".lock", os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert cli.main(["replicate"]) == config.EX_TEMPFAIL
        err = capsys.readouterr().err
        assert "another session-archive run holds" in err

        assert cli.main(["verify-replica"]) == config.EX_TEMPFAIL
        err2 = capsys.readouterr().err
        assert "another session-archive run holds" in err2
    finally:
        os.close(fd)


def test_cli_records_failed_replicate_and_verify_runs_and_exits_1(
    tmp_path, home, archive, manifest, monkeypatch, capsys
):
    _set_home_env(monkeypatch, home)
    _seed_live_sources(home)
    rep = tmp_path / "replica"
    rep.mkdir()
    (rep / replica.MARKER).touch()
    write_config(home, archive, replica=rep)
    monkeypatch.setattr(
        cli,
        "DISKS",
        lambda p: frozenset({"sdc"}) if Path(p) == archive else frozenset({"sdb"}),
    )

    assert cli.main(["capture"]) == 0
    capsys.readouterr()

    t0 = datetime(2026, 11, 8, 6, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(cli, "CLOCK", lambda: t0)
    assert cli.main(["replicate"]) == 0
    r1 = json.loads(capsys.readouterr().out)

    # Corrupt an archive file so next day's replicate fails with exit 1 and records ok=False
    for f in (archive / "claude").rglob("*.jsonl"):
        f.write_bytes(b"corrupted-archive-bytes\n")
        break
    t1 = t0 + timedelta(days=1)
    monkeypatch.setattr(cli, "CLOCK", lambda: t1)
    assert cli.main(["replicate"]) == 1
    fail_rep = json.loads(capsys.readouterr().out)
    assert fail_rep["verified"] is False
    last_rep = manifest.last_run("replicate")
    assert last_rep is not None and last_rep.ok is False

    # Corrupt a file in current generation so verify-replica exits 1 and records ok=False
    gen_dir = rep / "generations" / r1["generation"]
    for f in gen_dir.rglob("*.jsonl"):
        f.write_bytes(b"corrupt")
        break
    t2 = t1 + timedelta(minutes=5)
    monkeypatch.setattr(cli, "CLOCK", lambda: t2)
    assert cli.main(["verify-replica"]) == 1
    fail_ver = json.loads(capsys.readouterr().out)
    assert fail_ver["failures"]
    last_ver = manifest.last_run("verify-replica")
    assert last_ver is not None and last_ver.ok is False

