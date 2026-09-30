"""Capturing one file: mirror, extension check, versions/, busy and repair (spec §3.3)."""
import os
from pathlib import Path

import pytest

from session_archive import capture
from session_archive.capture import capture_file, hash_file, mirror_path
from session_archive.manifest import MIRROR
from session_archive.testing import write


@pytest.fixture
def live(tmp_path):
    return tmp_path / "live"


def cap(archive, manifest, live, rel, **kw):
    return capture_file(archive, manifest, "claude", rel, live / rel, **kw)


def test_first_capture_mirrors_with_source_mtime(archive, manifest, live):
    src = write(live / "p/s.jsonl", b"one\n")
    out = cap(archive, manifest, live, "p/s.jsonl")
    dest = mirror_path(archive, "claude", "p/s.jsonl")
    assert out.action == "copied"
    assert dest.read_bytes() == b"one\n"
    assert os.stat(dest).st_mtime_ns == os.stat(src).st_mtime_ns
    assert manifest.mirror("claude", "p/s.jsonl").sha256 == hash_file(src)


def test_unchanged_is_skipped(archive, manifest, live):
    write(live / "p/s.jsonl", b"one\n")
    cap(archive, manifest, live, "p/s.jsonl")
    assert cap(archive, manifest, live, "p/s.jsonl").action == "unchanged"


def test_append_replaces_mirror(archive, manifest, live):
    src = write(live / "p/s.jsonl", b"one\n")
    cap(archive, manifest, live, "p/s.jsonl")
    with open(src, "ab") as handle:
        handle.write(b"two\n")
    assert cap(archive, manifest, live, "p/s.jsonl").action == "copied"
    assert mirror_path(archive, "claude", "p/s.jsonl").read_bytes() == b"one\ntwo\n"


@pytest.mark.parametrize("rewrite", [b"on", b"ONE\nmore\n"])
def test_truncated_or_rewritten_goes_to_versions(archive, manifest, live, rewrite):
    rel = "p q/s@x.jsonl"
    src = write(live / rel, b"one\n")
    cap(archive, manifest, live, rel)
    src.write_bytes(rewrite)
    out = cap(archive, manifest, live, rel)
    assert out.action == "diverged"
    assert out.version.location.startswith("versions/claude/p q/s@x.jsonl@")
    assert (archive / out.version.location).read_bytes() == rewrite
    assert mirror_path(archive, "claude", rel).read_bytes() == b"one\n"
    assert manifest.mirror("claude", rel).size == 4


def test_change_during_copy_is_busy(archive, manifest, live, monkeypatch):
    src = write(live / "p/s.jsonl", b"one\n")
    real = capture.copy_hashed

    def copy_then_append(*args):
        copied = real(*args)
        with open(src, "ab") as handle:
            handle.write(b"late\n")
        return copied

    monkeypatch.setattr(capture, "copy_hashed", copy_then_append)
    out = cap(archive, manifest, live, "p/s.jsonl")
    assert out.action == "busy"
    assert manifest.latest("claude", "p/s.jsonl") is None
    assert not any(p.name.startswith(".capture-") for p in (archive / "claude" / "p").iterdir())


def test_missing_mirror_is_repaired(archive, manifest, live):
    write(live / "p/s.jsonl", b"one\n")
    cap(archive, manifest, live, "p/s.jsonl")
    mirror_path(archive, "claude", "p/s.jsonl").unlink()
    assert cap(archive, manifest, live, "p/s.jsonl").action == "repaired"
    assert mirror_path(archive, "claude", "p/s.jsonl").read_bytes() == b"one\n"


def test_truncated_mirror_is_repaired_in_place(archive, manifest, live):
    write(live / "p/s.jsonl", b"one\ntwo\n")
    cap(archive, manifest, live, "p/s.jsonl")
    mirror_path(archive, "claude", "p/s.jsonl").write_bytes(b"on")
    out = cap(archive, manifest, live, "p/s.jsonl")
    assert out.action == "repaired"
    assert out.version.location == MIRROR
    assert hash_file(mirror_path(archive, "claude", "p/s.jsonl")) == manifest.mirror("claude", "p/s.jsonl").sha256
    assert not (archive / "versions").exists()


def test_same_size_corruption_needs_force(archive, manifest, live):
    src = write(live / "p/s.jsonl", b"one\n")
    cap(archive, manifest, live, "p/s.jsonl")
    dest = mirror_path(archive, "claude", "p/s.jsonl")
    dest.write_bytes(b"ONE\n")
    stamp = os.stat(src).st_mtime_ns
    os.utime(dest, ns=(stamp, stamp))
    assert cap(archive, manifest, live, "p/s.jsonl").action == "unchanged"
    assert cap(archive, manifest, live, "p/s.jsonl", force=True).action == "repaired"
    assert dest.read_bytes() == b"one\n"
    assert not (archive / "versions").exists()


def test_source_disappearing_after_copy_removes_temporary_file(archive, manifest, live, monkeypatch):
    src = write(live / "p/s.jsonl", b"one\n")
    real = capture.copy_hashed

    def copy_then_remove(*args):
        copied = real(*args)
        src.unlink()
        return copied

    monkeypatch.setattr(capture, "copy_hashed", copy_then_remove)
    with pytest.raises(FileNotFoundError):
        cap(archive, manifest, live, "p/s.jsonl")
    assert manifest.latest("claude", "p/s.jsonl") is None
    assert not any(p.name.startswith(".capture-") for p in (archive / "claude" / "p").iterdir())


def test_repeated_timestamp_never_replaces_archived_version(archive, manifest, live):
    src = write(live / "p/s.jsonl", b"one\n")
    cap(archive, manifest, live, "p/s.jsonl")
    src.write_bytes(b"fragment\n")
    stamp = "2100-01-01T00:00:00.000000Z"
    first = cap(archive, manifest, live, "p/s.jsonl", now=lambda: stamp)
    rows = manifest.rows("claude", "p/s.jsonl")
    src.write_bytes(b"another fragment\n")
    with pytest.raises(FileExistsError):
        cap(archive, manifest, live, "p/s.jsonl", now=lambda: stamp)
    assert (archive / first.version.location).read_bytes() == b"fragment\n"
    assert manifest.rows("claude", "p/s.jsonl") == rows
    assert not any(p.name.startswith(".capture-") for p in (archive / "claude" / "p").iterdir())


@pytest.mark.parametrize("diverged", [False, True], ids=["mirror", "versions"])
@pytest.mark.parametrize("existing", [False, True], ids=["new-dirs", "existing-dirs"])
def test_directory_entries_synced_before_manifest(archive, manifest, live, monkeypatch, diverged, existing):
    rel = "p/deep/s.jsonl"
    src = write(live / rel, b"one\n")
    if diverged:
        cap(archive, manifest, live, rel)
        src.write_bytes(b"fragment\n")
    base = archive / "versions" if diverged else archive
    leaf = base / "claude/p/deep"
    if existing:
        leaf.mkdir(parents=True, exist_ok=True)
    events = []
    real_mkdir, real_sync, real_put = Path.mkdir, capture.fsync_dir, manifest.put

    def mkdir(path, *args, **kwargs):
        real_mkdir(path, *args, **kwargs)
        events.append(("mkdir", path.relative_to(archive).as_posix()))

    def sync(path):
        real_sync(path)
        events.append(("sync", path.relative_to(archive).as_posix()))

    def put(version):
        assert (archive / version.location if diverged else leaf / "s.jsonl").read_bytes() == src.read_bytes()
        events.append(("put", None))
        real_put(version)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(capture, "fsync_dir", sync)
    monkeypatch.setattr(manifest, "put", put)
    out = cap(archive, manifest, live, rel)
    assert out.action == ("diverged" if diverged else "copied")
    if existing:
        directories, parents = [], []
    elif diverged:
        directories = ["versions", "versions/claude", "versions/claude/p", "versions/claude/p/deep"]
        parents = [".", "versions", "versions/claude", "versions/claude/p"]
    else:
        directories = ["claude", "claude/p", "claude/p/deep"]
        parents = [".", "claude", "claude/p"]
    expected_leaf = "versions/claude/p/deep" if diverged else "claude/p/deep"
    creation = [event for directory, parent in zip(directories, parents)
                for event in [("mkdir", directory), ("sync", parent)]]
    assert events == creation + [("sync", expected_leaf), ("put", None)]


@pytest.mark.parametrize("linked", [False, True], ids=["replacement-file", "parent-link"])
def test_source_path_replaced_during_copy_is_never_published(archive, manifest, live,
                                                            tmp_path, monkeypatch, linked):
    src = write(live / "p/s.jsonl", b"live")
    outside = tmp_path / "outside"
    write(outside / "s.jsonl", b"outside bytes")
    real = capture.copy_hashed

    def copy_then_replace(*args):
        copied = real(*args)
        if linked:
            src.parent.rename(live / "original")
            src.parent.symlink_to(outside, target_is_directory=True)
        else:
            src.rename(src.with_name("original.jsonl"))
            src.write_bytes(b"live")
            old = src.with_name("original.jsonl").stat()
            os.utime(src, ns=(old.st_atime_ns, old.st_mtime_ns))
        return copied

    monkeypatch.setattr(capture, "copy_hashed", copy_then_replace)
    if linked:
        with pytest.raises(OSError):
            cap(archive, manifest, live, "p/s.jsonl")
    else:
        assert cap(archive, manifest, live, "p/s.jsonl").action == "busy"
    assert manifest.latest("claude", "p/s.jsonl") is None
    assert not (archive / "claude/p/s.jsonl").exists()
    assert not list(archive.rglob(".capture-*"))


def test_copy_reads_held_file_when_parent_is_replaced(archive, manifest, live, tmp_path, monkeypatch):
    src = write(live / "p/s.jsonl", b"live")
    outside = tmp_path / "outside"
    write(outside / "s.jsonl", b"outside bytes")
    real = capture.copy_hashed

    def replace_then_copy(*args):
        src.parent.rename(live / "original")
        src.parent.symlink_to(outside, target_is_directory=True)
        copied = real(*args)
        assert copied.tmp.read_bytes() == b"live"
        return copied

    monkeypatch.setattr(capture, "copy_hashed", replace_then_copy)
    with pytest.raises(OSError):
        cap(archive, manifest, live, "p/s.jsonl")
    assert manifest.latest("claude", "p/s.jsonl") is None
    assert not list(archive.rglob(".capture-*"))
