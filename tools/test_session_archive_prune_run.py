"""The prune run: two phases, dry run, gates, leftovers, repair and divergence (spec §3.4)."""
import json
import os
import sys
import time

import pytest

from session_archive import config, prune
from session_archive.capture import capture_run, hash_file, mirror_path, promote
from session_archive.manifest import Manifest
from session_archive.prune import Context, LeftoverQuarantine, prune_run
from session_archive.quarantine import QUARANTINE
from session_archive.testing import (SID, age, claude_session, codex_rollout, lenient_open_inodes, obs_for,
                                     run_tool, uninspectable_comms, write, write_config)

OTHER = "22222222-2222-4333-8444-555555555555"


@pytest.fixture
def table(home):
    return config.sources(home)


def src(table, name):
    return next(s for s in table if s.name == name)


def ctx_for(archive, manifest, paths, codex_bin="codex"):
    return Context(archive, manifest, obs_for(*paths), lenient_open_inodes, time.time_ns(), "run1",
                   codex_bin=codex_bin)


def run_prune(ctx, table, apply, codex_probed=True):
    report = {}
    ok = prune_run(ctx, table, apply, codex_probed, report)
    return report, ok


def transcripts(root, sid=SID):
    return [root / "-p" / f"{sid}.jsonl", root / "-p" / sid / "subagents" / "agent-1.jsonl"]


def test_dry_run_writes_nothing(table, archive, manifest):
    claude = src(table, "claude")
    jsonl = claude_session(claude.root)
    capture_run(archive, manifest, table)
    report, ok = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, False)
    assert ok and report["claude"]["totals"] == {"eligible": 1}
    assert jsonl.exists() and not (claude.home / QUARANTINE).exists()


def test_apply_prunes_only_eligible(table, archive, manifest):
    claude = src(table, "claude")
    claude_session(claude.root)
    claude_session(claude.root, age_days=1, sid=OTHER)
    capture_run(archive, manifest, table)
    paths = transcripts(claude.root) + transcripts(claude.root, OTHER)
    report, ok = run_prune(ctx_for(archive, manifest, paths), table, True)
    assert ok
    assert report["claude"]["totals"] == {"pruned": 1, "kept:active": 1}
    assert report["claude"]["units"] == [{"unit": f"-p/{SID}", "outcome": "pruned"}]
    assert (claude.root / "-p" / f"{OTHER}.jsonl").exists()


def test_unindexed_is_kept_with_reason(table, archive, manifest):
    claude_session(src(table, "claude").root)
    capture_run(archive, manifest, table)
    report, _ = run_prune(ctx_for(archive, manifest, []), table, True)
    assert report["claude"]["totals"] == {"kept:unindexed": 1}


def test_leftover_quarantine_refuses(table, archive, manifest):
    write(src(table, "claude").home / QUARANTINE / "old" / "f", b"x")
    with pytest.raises(LeftoverQuarantine):
        run_prune(ctx_for(archive, manifest, []), table, True)


def test_damaged_mirror_is_repaired_only_with_apply(table, archive, manifest):
    claude = src(table, "claude")
    claude_session(claude.root)
    capture_run(archive, manifest, table)
    mirrored = mirror_path(archive, "claude", f"-p/{SID}.jsonl")
    mirrored.write_bytes(b"{")
    report, _ = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, False)
    assert report["claude"]["totals"] == {"kept:archive-damaged": 1}
    assert mirrored.read_bytes() == b"{"
    report, ok = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, True)
    assert ok and report["claude"]["totals"] == {"kept:archive-repaired": 1}
    assert hash_file(mirrored) == manifest.mirror("claude", f"-p/{SID}.jsonl").sha256


def test_diverged_file_stays_until_promoted(table, archive, manifest):
    claude = src(table, "claude")
    jsonl = claude_session(claude.root)
    capture_run(archive, manifest, table)
    jsonl.write_bytes(b'{"rewritten":1}\n')
    age(jsonl, 40)
    capture_run(archive, manifest, table)
    report, _ = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, True)
    assert report["claude"]["totals"] == {"kept:diverged": 1} and jsonl.exists()
    old = manifest.mirror("claude", f"-p/{SID}.jsonl")
    promote(archive, manifest, "claude", f"-p/{SID}.jsonl")
    report, ok = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, True)
    assert ok and report["claude"]["totals"] == {"pruned": 1}
    assert any(v.sha256 == old.sha256 and v.location.startswith("versions/")
               for v in manifest.rows("claude", f"-p/{SID}.jsonl"))


def test_unprobed_codex_is_kept_and_fails_the_run(table, archive, manifest, stub_codex):
    codex = src(table, "codex")
    rollout = codex_rollout(codex.root)
    capture_run(archive, manifest, table)
    report, ok = run_prune(ctx_for(archive, manifest, [rollout], str(stub_codex)), table, True, codex_probed=False)
    assert not ok and report["codex"]["totals"] == {"kept:codex-unprobed": 1}
    assert rollout.exists()


def test_deferred_sources_are_not_pruned(table, archive, manifest):
    rollout = codex_rollout(src(table, "codex-archived").root)
    capture_run(archive, manifest, table)
    report, _ = run_prune(ctx_for(archive, manifest, [rollout]), table, True)
    assert "codex-archived" not in report and rollout.exists()


def fake_obs(tmp_path, payload=None, exit_code=0):
    script = tmp_path / "fake_obs.py"
    script.write_text("import json, sys\n"
                      f"print(json.dumps({payload!r}))\n"
                      f"sys.exit({exit_code})\n")
    return (sys.executable, str(script))


def test_prune_command_dry_run_and_obs_failure(home, archive, tmp_path, stub_codex):
    claude_session(home / ".claude" / "projects")
    write_config(home, archive, fake_obs(tmp_path, {"schema": 1, "files": []}), uninspectable_comms())
    assert run_tool("capture", home=home).returncode == 0
    result = run_tool("prune", home=home)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["claude"]["totals"] == {"kept:unindexed": 1}
    write_config(home, archive, fake_obs(tmp_path, {}, exit_code=3), uninspectable_comms())
    result = run_tool("prune", "--apply", home=home)
    assert result.returncode == 1 and "obs index-state exited 3" in json.loads(result.stdout)["error"]
    assert "probe-codex" in json.loads(result.stdout)["codex_gate"]
    opened = Manifest.open(archive)
    assert opened.last_run("prune").mode == "apply" and not opened.last_run("prune").ok
    opened.close()


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable files")
def test_unreadable_transcript_fails_the_run(table, archive, manifest):
    claude = src(table, "claude")
    jsonl = claude_session(claude.root)
    capture_run(archive, manifest, table)
    jsonl.chmod(0)
    try:
        report, ok = run_prune(ctx_for(archive, manifest, transcripts(claude.root)), table, False)
    finally:
        jsonl.chmod(0o600)
    assert not ok and report["claude"]["totals"] == {"failed:unreadable": 1}


def test_io_error_stops_phase_two_and_keeps_the_report(table, archive, manifest, monkeypatch):
    claude = src(table, "claude")
    claude_session(claude.root)
    claude_session(claude.root, sid=OTHER)
    capture_run(archive, manifest, table)

    def broken(unit, ctx):
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(prune, "delete_claude_unit", broken)
    report = {}
    paths = transcripts(claude.root) + transcripts(claude.root, OTHER)
    assert not prune_run(ctx_for(archive, manifest, paths), table, True, True, report)
    assert report["claude"]["totals"] == {"failed:io": 1, "kept:stopped": 1}
    assert "Input/output error" in report["errors"][0]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable files")
def test_filesystem_failure_records_a_failed_prune(home, archive, tmp_path):
    jsonl = claude_session(home / ".claude" / "projects")
    write_config(home, archive, fake_obs(tmp_path, {"schema": 1, "files": []}), uninspectable_comms())
    assert run_tool("capture", home=home).returncode == 0
    assert run_tool("prune", home=home).returncode == 0
    (home / ".claude" / "projects" / "-p").chmod(0)
    try:
        result = run_tool("prune", home=home)
    finally:
        (home / ".claude" / "projects" / "-p").chmod(0o700)
    assert result.returncode == 1 and "PermissionError" in json.loads(result.stdout)["error"]
    opened = Manifest.open(archive)
    try:
        assert not opened.last_run("prune").ok
    finally:
        opened.close()


def test_late_readback_failure_stops_before_any_deletion(table, archive, manifest, monkeypatch):
    claude = src(table, "claude")
    claude_session(claude.root)
    claude_session(claude.root, sid=OTHER)
    capture_run(archive, manifest, table)
    unreadable = mirror_path(archive, "claude", f"-p/{OTHER}.jsonl")
    read_file = prune._read_file

    def read(path, offset=None):
        if path == unreadable:
            raise PermissionError("backup disk cannot be read")
        return read_file(path, offset)

    monkeypatch.setattr(prune, "_read_file", read)
    paths = transcripts(claude.root) + transcripts(claude.root, OTHER)
    with pytest.raises(prune.ArchiveUnreadable, match="backup disk cannot be read"):
        run_prune(ctx_for(archive, manifest, paths), table, True)
    assert all(path.exists() for path in paths)
    assert not (claude.home / QUARANTINE).exists()


def test_command_records_expected_errors_with_partial_report(home, archive, manifest, monkeypatch, capsys):
    from argparse import Namespace
    from session_archive import cli, inputs, probe

    monkeypatch.setattr(inputs, "load_obs_state", lambda command: {})
    errors = [inputs.ObsUnavailable("obs failed"),
              inputs.InspectionFailed([("1", "writer", "denied")]),
              prune.ArchiveUnreadable("backup failed"),
              LeftoverQuarantine("quarantine not empty"),
              probe.CodexUnavailable("version unavailable"),
              OSError(5, "Input/output error")]
    partial = {"claude": {"totals": {"pruned": 1},
                           "units": [{"unit": f"-p/{SID}", "outcome": "pruned"}]}}
    cfg = config.Config(archive, ("unused-obs",), ())
    for error in errors:
        def failed_run(ctx, sources, apply, codex_probed, report):
            report.update(partial)
            raise error

        monkeypatch.setattr(prune, "prune_run", failed_run)
        assert cli.cmd_prune(cfg, config.sources(home), Namespace(apply=False)) == 1
        report = json.loads(capsys.readouterr().out)
        recorded = manifest.last_run("prune")
        assert not recorded.ok and recorded.mode == "dry-run"
        assert recorded.report == report
        assert report["claude"] == partial["claude"]
        assert report["error"].startswith(type(error).__name__ + ":")


def test_apply_command_reports_unprobed_codex(home, archive, tmp_path, stub_codex):
    rollout = codex_rollout(home / ".codex" / "sessions")
    info = rollout.stat()
    entry = {"path": str(rollout), "size": info.st_size,
             "mtime_ms": info.st_mtime_ns // 1_000_000, "byte_offset": info.st_size,
             "partial_tail": False, "indexed_schema": 1, "missing_since_ms": None}
    write_config(home, archive, fake_obs(tmp_path, {"schema": 1, "files": [entry]}), uninspectable_comms())
    assert run_tool("capture", home=home).returncode == 0
    result = run_tool("prune", "--apply", home=home)
    report = json.loads(result.stdout)
    assert result.returncode == 1 and report["codex"]["totals"] == {"kept:codex-unprobed": 1}
    assert "probe-codex" in report["codex_gate"]
    assert rollout.exists()


def test_repair_failure_keeps_the_live_unit(table, archive, manifest, monkeypatch):
    claude = src(table, "claude")
    claude_session(claude.root)
    capture_run(archive, manifest, table)
    mirror_path(archive, "claude", f"-p/{SID}.jsonl").write_bytes(b"{")

    def failed_copy(*args, **kwargs):
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(prune, "capture_file", failed_copy)
    paths = transcripts(claude.root)
    report, ok = run_prune(ctx_for(archive, manifest, paths), table, True)
    assert not ok and report["claude"]["totals"] == {"failed:archive-repair": 1}
    assert all(path.exists() for path in paths)
