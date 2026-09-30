"""promote makes a diverged file's latest version the mirror, deleting nothing (spec §3.3)."""
import json

import pytest

from session_archive import capture
from session_archive.capture import PromoteError, capture_file, mirror_path, promote
from session_archive.manifest import MIRROR
from session_archive.testing import run_tool, write, write_config

REL = "p q/s@x.jsonl"


def diverge(archive, manifest, tmp_path):
    src = write(tmp_path / "live" / REL, b"one\ntwo\n")
    capture_file(archive, manifest, "claude", REL, src)
    src.write_bytes(b"rewritten\n")
    assert capture_file(archive, manifest, "claude", REL, src).action == "diverged"
    return src


def test_promote_swaps_mirror_and_keeps_old(archive, manifest, tmp_path):
    diverge(archive, manifest, tmp_path)
    old = manifest.mirror("claude", REL)
    latest = manifest.latest("claude", REL)
    promoted = promote(archive, manifest, "claude", REL)
    assert promoted.location == MIRROR
    assert mirror_path(archive, "claude", REL).read_bytes() == b"rewritten\n"
    assert mirror_path(archive, "claude", REL).stat().st_mtime_ns == latest.mtime_ns
    assert (archive / latest.location).read_bytes() == b"rewritten\n"
    kept = [v for v in manifest.rows("claude", REL) if v.sha256 == old.sha256]
    assert len(kept) == 1 and kept[0].location.startswith("versions/")
    assert (archive / kept[0].location).read_bytes() == b"one\ntwo\n"
    assert manifest.latest("claude", REL).location == MIRROR
    assert manifest.diverged() == []


def test_promote_refuses_when_not_diverged(archive, manifest, tmp_path):
    src = write(tmp_path / "live" / REL, b"one\n")
    capture_file(archive, manifest, "claude", REL, src)
    with pytest.raises(PromoteError, match="not diverged"):
        promote(archive, manifest, "claude", REL)
    with pytest.raises(PromoteError, match="no archived version"):
        promote(archive, manifest, "claude", "absent")


def test_interrupted_copy_keeps_mirror_and_retry_works(archive, manifest, tmp_path, monkeypatch):
    diverge(archive, manifest, tmp_path)

    def disk_full(*args):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(capture, "copy_hashed", disk_full)
    with pytest.raises(OSError):
        promote(archive, manifest, "claude", REL)
    monkeypatch.undo()
    assert mirror_path(archive, "claude", REL).read_bytes() == b"one\ntwo\n"
    assert len(manifest.rows("claude", REL)) == 2
    promote(archive, manifest, "claude", REL)
    assert mirror_path(archive, "claude", REL).read_bytes() == b"rewritten\n"


def test_interrupted_swap_keeps_old_version_and_retry_works(archive, manifest, tmp_path, monkeypatch):
    diverge(archive, manifest, tmp_path)

    def io_error(*args):
        assert mirror_path(archive, "claude", REL).read_bytes() == b"one\ntwo\n"
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(capture.os, "replace", io_error)
    with pytest.raises(OSError):
        promote(archive, manifest, "claude", REL)
    monkeypatch.undo()
    mirrored = mirror_path(archive, "claude", REL)
    assert mirrored.read_bytes() == b"one\ntwo\n"
    assert not any(p.name.startswith(".capture-") for p in mirrored.parent.iterdir())
    promote(archive, manifest, "claude", REL)
    assert mirrored.read_bytes() == b"rewritten\n"
    old = [v for v in manifest.rows("claude", REL) if v.location.startswith("versions/") and v.size == 8]
    assert len(old) == 1 and (archive / old[0].location).read_bytes() == b"one\ntwo\n"


@pytest.mark.parametrize("step", ["fsync", "manifest"])
def test_interruption_after_swap_is_finished_by_retry(archive, manifest, tmp_path, monkeypatch, step):
    diverge(archive, manifest, tmp_path)
    old = manifest.mirror("claude", REL)
    new = manifest.latest("claude", REL)
    mirror_dir = mirror_path(archive, "claude", REL).parent
    if step == "fsync":
        real_fsync = capture.fsync_dir

        def fsync(path):
            if path == mirror_dir:
                raise OSError(5, "Input/output error")
            real_fsync(path)

        monkeypatch.setattr(capture, "fsync_dir", fsync)
    else:
        real_put = manifest.put

        def put(version):
            if version.location == "mirror" and version.sha256 == new.sha256:
                raise OSError(28, "No space left on device")
            real_put(version)

        monkeypatch.setattr(manifest, "put", put)
    with pytest.raises(OSError):
        promote(archive, manifest, "claude", REL)
    monkeypatch.undo()
    assert mirror_path(archive, "claude", REL).read_bytes() == b"rewritten\n"
    assert manifest.mirror("claude", REL).sha256 == old.sha256          # not yet recorded
    promoted = promote(archive, manifest, "claude", REL)
    assert promoted.sha256 == new.sha256 == manifest.mirror("claude", REL).sha256
    kept = [v for v in manifest.rows("claude", REL) if v.sha256 == old.sha256]
    assert len(kept) == 1 and (archive / kept[0].location).read_bytes() == b"one\ntwo\n"
    assert manifest.diverged() == []


@pytest.mark.parametrize("step", ["link", "fsync", "manifest", "utime"])
def test_interruption_before_swap_keeps_mirror_and_retry_works(
        archive, manifest, tmp_path, monkeypatch, step):
    diverge(archive, manifest, tmp_path)
    old = manifest.mirror("claude", REL)
    kept_path = archive / capture.version_location("claude", REL, old.captured_at)

    def io_error(*args, **kwargs):
        raise OSError(5, "Input/output error")

    if step in {"link", "utime"}:
        monkeypatch.setattr(capture.os, step, io_error)
    elif step == "fsync":
        real_fsync = capture.fsync_dir

        def fsync(path):
            if path == kept_path.parent:
                io_error()
            real_fsync(path)

        monkeypatch.setattr(capture, "fsync_dir", fsync)
    else:
        real_put = manifest.put

        def put(version):
            if version.location.startswith("versions/") and version.sha256 == old.sha256:
                io_error()
            real_put(version)

        monkeypatch.setattr(manifest, "put", put)
    with pytest.raises(OSError):
        promote(archive, manifest, "claude", REL)
    monkeypatch.undo()
    mirrored = mirror_path(archive, "claude", REL)
    assert mirrored.read_bytes() == b"one\ntwo\n"
    assert not any(p.name.startswith(".capture-") for p in mirrored.parent.iterdir())
    promote(archive, manifest, "claude", REL)
    assert mirrored.read_bytes() == b"rewritten\n"
    assert kept_path.read_bytes() == b"one\ntwo\n"
    assert manifest.diverged() == []


@pytest.mark.parametrize("damage", ["latest", "mirror", "preserved"])
def test_promote_refuses_damaged_versions(archive, manifest, tmp_path, damage):
    diverge(archive, manifest, tmp_path)
    old = manifest.mirror("claude", REL)
    mirrored = mirror_path(archive, "claude", REL)
    if damage == "latest":
        (archive / manifest.latest("claude", REL).location).write_bytes(b"damaged\n")
    elif damage == "mirror":
        mirrored.write_bytes(b"damaged\n")
    else:
        kept_path = archive / capture.version_location("claude", REL, old.captured_at)
        write(kept_path, b"unrelated content\n")
    before = mirrored.read_bytes()
    with pytest.raises(PromoteError):
        promote(archive, manifest, "claude", REL)
    assert mirrored.read_bytes() == before
    assert manifest.mirror("claude", REL) == old
    assert len(manifest.rows("claude", REL)) == 2
    assert not any(p.name.startswith(".capture-") for p in mirrored.parent.iterdir())


def test_retry_after_swap_refuses_without_preserved_mirror(archive, manifest, tmp_path, monkeypatch):
    diverge(archive, manifest, tmp_path)
    old = manifest.mirror("claude", REL)
    new = manifest.latest("claude", REL)
    real_put = manifest.put

    def put(version):
        if version.location == MIRROR:
            raise OSError(28, "No space left on device")
        real_put(version)

    monkeypatch.setattr(manifest, "put", put)
    with pytest.raises(OSError):
        promote(archive, manifest, "claude", REL)
    monkeypatch.undo()
    (archive / capture.version_location("claude", REL, old.captured_at)).unlink()
    with pytest.raises(PromoteError, match="old one is not preserved"):
        promote(archive, manifest, "claude", REL)
    assert mirror_path(archive, "claude", REL).read_bytes() == b"rewritten\n"
    assert manifest.mirror("claude", REL) == old
    assert manifest.latest("claude", REL) == new


def test_promote_command(home, archive, manifest):
    src = write(home / ".claude/projects" / REL, b"one\n")
    capture_file(archive, manifest, "claude", REL, src)
    src.write_bytes(b"x\n")
    capture_file(archive, manifest, "claude", REL, src)
    write_config(home, archive)
    result = run_tool("promote", "claude", REL, home=home)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["location"] == MIRROR
    assert run_tool("promote", "claude", REL, home=home).returncode == 1
