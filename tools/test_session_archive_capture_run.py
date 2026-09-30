"""The daily run over every source, and the capture command (spec §3.3)."""
import json
import os

import pytest

from session_archive import capture, config
from session_archive.capture import capture_run, mirror_path
from session_archive.manifest import Manifest
from session_archive.testing import run_tool, write, write_config


def table(home):
    return config.sources(home)


def test_counts_and_mirror(home, archive, manifest):
    write(home / ".claude/projects/p/a.jsonl", b"a\n")
    write(home / ".codex/sessions/2026/01/01/r.jsonl", b"r\n")
    report, ok = capture_run(archive, manifest, table(home))
    assert ok
    assert report["claude"]["copied"] == 1 and report["claude"]["scanned"] == 1
    assert report["codex"]["copied"] == 1
    assert mirror_path(archive, "codex", "2026/01/01/r.jsonl").read_bytes() == b"r\n"
    again, _ = capture_run(archive, manifest, table(home))
    assert again["claude"]["unchanged"] == 1


def test_removed_source_stays_archived(home, archive, manifest):
    src = write(home / ".claude/projects/p/a.jsonl", b"a\n")
    capture_run(archive, manifest, table(home))
    src.unlink()
    capture_run(archive, manifest, table(home))
    assert mirror_path(archive, "claude", "p/a.jsonl").read_bytes() == b"a\n"


def test_symlinks_are_not_followed(home, archive, manifest, tmp_path):
    outside = write(tmp_path / "outside.txt", b"secret")
    link = home / ".claude/projects/p/link.jsonl"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    report, _ = capture_run(archive, manifest, table(home))
    assert report["claude"]["scanned"] == 0
    assert not mirror_path(archive, "claude", "p/link.jsonl").exists()


def test_file_vanishing_mid_walk_is_counted_not_failed(home, archive, manifest, monkeypatch):
    src = write(home / ".claude/projects/p/a.jsonl", b"a\n")
    real = capture.capture_file

    def vanish(root, man, source, relpath, path, **kw):
        path.unlink()
        return real(root, man, source, relpath, path, **kw)

    monkeypatch.setattr(capture, "capture_file", vanish)
    report, ok = capture_run(archive, manifest, table(home))
    assert ok and report["claude"]["vanished"] == 1 and not src.exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable files")
def test_unreadable_file_fails_the_run(home, archive, manifest):
    src = write(home / ".claude/projects/p/a.jsonl", b"a\n")
    src.chmod(0)
    try:
        report, ok = capture_run(archive, manifest, table(home))
    finally:
        src.chmod(0o600)
    assert not ok
    assert report["claude"]["failed"] == 1 and "p/a.jsonl" in report["claude"]["errors"][0]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable directories")
def test_unreadable_directory_fails_the_run(home, archive, manifest):
    write(home / ".claude/projects/p/a.jsonl", b"a\n")
    write(home / ".claude/projects/q/b.jsonl", b"b\n")
    locked = home / ".claude/projects/p"
    locked.chmod(0)
    try:
        report, ok = capture_run(archive, manifest, table(home))
    finally:
        locked.chmod(0o700)
    assert not ok
    assert report["claude"]["failed"] == 1 and report["claude"]["copied"] == 1
    assert report["claude"]["errors"][0].startswith("p: unreadable:")


def test_capture_command_records_the_run(home, archive):
    write(home / ".claude/projects/p/a.jsonl", b"a\n")
    write_config(home, archive)
    result = run_tool("capture", home=home)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["claude"]["copied"] == 1
    opened = Manifest.open(archive)
    assert opened.last_run("capture", ok_only=True).report["claude"]["copied"] == 1
    opened.close()


def test_walk_files_is_sorted_and_excludes_directories_links_and_fifo(tmp_path):
    top = tmp_path / "source"
    write(top / "z/b.txt", b"b")
    write(top / "a/c.txt", b"c")
    write(top / "d.txt", b"d")
    write(top / "b.txt", b"b")
    (top / "alias").symlink_to(top / "a", target_is_directory=True)
    os.mkfifo(top / "pipe")
    assert [p.relative_to(top).as_posix() for p in capture.walk_files(top)] == [
        "b.txt", "d.txt", "a/c.txt", "z/b.txt"]


def test_walk_files_raises_or_reports_missing_directory(tmp_path):
    top = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        list(capture.walk_files(top))
    errors = []
    assert list(capture.walk_files(top, errors)) == []
    assert len(errors) == 1 and errors[0][0] == top
    assert isinstance(errors[0][1], FileNotFoundError)


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads unreadable files")
def test_capture_command_records_failed_run(home, archive):
    src = write(home / ".claude/projects/p/a.jsonl", b"a\n")
    write_config(home, archive)
    src.chmod(0)
    try:
        result = run_tool("capture", home=home)
    finally:
        src.chmod(0o600)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["claude"]["failed"] == 1
    opened = Manifest.open(archive)
    try:
        run = opened.last_run("capture")
        assert not run.ok and run.report == report and run.mode == "apply"
        assert opened.last_run("capture", ok_only=True) is None
    finally:
        opened.close()


def test_capture_command_records_run_level_io_error(home, archive, monkeypatch, capsys):
    from session_archive import cli

    def fail(*args):
        raise OSError("archive unavailable")

    write_config(home, archive)
    monkeypatch.setattr(capture, "capture_run", fail)
    assert cli.main(["capture"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report == {"error": "OSError: archive unavailable"}
    opened = Manifest.open(archive)
    try:
        run = opened.last_run("capture")
        assert not run.ok and run.report == report
    finally:
        opened.close()


def test_linked_source_root_fails_without_archiving_outside(home, archive, manifest, tmp_path):
    root = home / ".claude/projects"
    root.rmdir()
    outside = tmp_path / "outside"
    write(outside / "secret.jsonl", b"outside bytes")
    root.symlink_to(outside, target_is_directory=True)
    report, ok = capture_run(archive, manifest, table(home))
    assert not ok and report["claude"]["failed"] == 1
    assert report["claude"]["scanned"] == 0
    assert not (archive / "claude/secret.jsonl").exists()
    with pytest.raises(config.HostGateError):
        config.check_sources(table(home))


def test_queued_directory_replaced_with_link_never_archives_outside(home, archive, manifest,
                                                                    tmp_path, monkeypatch):
    root = home / ".claude/projects"
    write(root / "first.jsonl", b"live")
    queued = root / "queued"
    queued.mkdir()
    outside = tmp_path / "outside"
    write(outside / "secret.jsonl", b"outside bytes")
    real = capture.capture_file

    def replace_directory(*args, **kw):
        if args[4] == root / "first.jsonl":
            queued.rmdir()
            queued.symlink_to(outside, target_is_directory=True)
        return real(*args, **kw)

    monkeypatch.setattr(capture, "capture_file", replace_directory)
    report, ok = capture_run(archive, manifest, table(home))
    assert not ok and report["claude"]["failed"] == 1
    assert report["claude"]["copied"] == 1
    assert not (archive / "claude/queued/secret.jsonl").exists()


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory permissions")
def test_parent_becoming_unsearchable_counts_failed_not_vanished(home, archive, manifest,
                                                                 monkeypatch):
    src = write(home / ".claude/projects/p/a.jsonl", b"live")
    real = capture.capture_file

    def lock_parent(*args, **kw):
        src.parent.chmod(0)
        return real(*args, **kw)

    monkeypatch.setattr(capture, "capture_file", lock_parent)
    try:
        report, ok = capture_run(archive, manifest, table(home))
    finally:
        src.parent.chmod(0o700)
    assert not ok and report["claude"]["failed"] == 1
    assert report["claude"]["vanished"] == 0
    assert "p/a.jsonl" in report["claude"]["errors"][0]
    assert not (archive / "claude/p/a.jsonl").exists()


def test_host_gate_rejects_linked_source_root(home, tmp_path):
    root = home / ".claude/projects"
    root.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(config.HostGateError):
        config.check_sources(table(home))


def test_file_replaced_by_link_after_walk_never_archives_outside(home, archive, manifest,
                                                               tmp_path, monkeypatch):
    src = write(home / ".claude/projects/p/a.jsonl", b"live")
    outside = write(tmp_path / "secret.jsonl", b"outside bytes")
    real = capture.capture_file

    def replace_file(*args, **kw):
        src.unlink()
        src.symlink_to(outside)
        return real(*args, **kw)

    monkeypatch.setattr(capture, "capture_file", replace_file)
    report, ok = capture_run(archive, manifest, table(home))
    assert not ok and report["claude"]["failed"] == 1
    assert report["claude"]["vanished"] == 0
    assert not (archive / "claude/p/a.jsonl").exists()
    assert manifest.latest("claude", "p/a.jsonl") is None
    assert not list(archive.rglob(".capture-*"))


def test_yielded_parent_replaced_by_link_never_archives_outside(home, archive, manifest,
                                                             tmp_path, monkeypatch):
    src = write(home / ".claude/projects/p/a.jsonl", b"live")
    outside = tmp_path / "outside"
    write(outside / "a.jsonl", b"outside bytes")
    real = capture.capture_file

    def replace_parent(*args, **kw):
        src.parent.rename(src.parent.with_name("original"))
        src.parent.symlink_to(outside, target_is_directory=True)
        return real(*args, **kw)

    monkeypatch.setattr(capture, "capture_file", replace_parent)
    report, ok = capture_run(archive, manifest, table(home))
    assert not ok and report["claude"]["failed"] >= 1
    assert not (archive / "claude/p/a.jsonl").exists()
    assert manifest.latest("claude", "p/a.jsonl") is None
