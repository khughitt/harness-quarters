"""Claude deletion protocol and its deletion-window cases (spec §3.4.2)."""
import os
import time

import pytest

from session_archive import config, prune
from session_archive.capture import capture_run, hash_file, mirror_path
from session_archive.inputs import InspectionFailed, claude_units
from session_archive.prune import Context, Hooks, delete_claude_unit, evaluate
from session_archive.quarantine import QUARANTINE
from session_archive.testing import SID, claude_session, lenient_open_inodes, obs_for


@pytest.fixture
def world(home, archive, manifest):
    src = next(s for s in config.sources(home) if s.name == "claude")
    jsonl = claude_session(src.root)
    capture_run(archive, manifest, [src])
    (unit,) = claude_units(src)
    transcripts = [jsonl, src.root / "-p" / SID / "subagents" / "agent-1.jsonl"]
    ctx = Context(archive, manifest, obs_for(*transcripts), lenient_open_inodes, time.time_ns(), "run1")
    assert evaluate(unit, ctx, set()) is None
    return src, unit, jsonl, ctx


def quarantined(src, name=f"{SID}.jsonl"):
    return src.home / QUARANTINE / "run1" / "-p" / SID / name


def test_eligible_unit_is_pruned(world, archive):
    src, unit, jsonl, ctx = world
    assert delete_claude_unit(unit, ctx) == "pruned"
    assert not jsonl.exists() and not (src.root / "-p" / SID).exists()
    assert not (src.home / QUARANTINE / "run1").exists()
    assert mirror_path(archive, "claude", f"-p/{SID}.jsonl").read_bytes() == b'{"a":1}\n'


def test_append_before_quarantine_is_kept_and_archived(world, archive):
    src, unit, jsonl, ctx = world
    with open(jsonl, "ab") as handle:
        handle.write(b'{"late":1}\n')
    assert delete_claude_unit(unit, ctx) == "kept:changed"
    assert jsonl.read_bytes() == b'{"a":1}\n{"late":1}\n'
    assert hash_file(mirror_path(archive, "claude", f"-p/{SID}.jsonl")) == hash_file(jsonl)


def test_open_at_settle_restores(world):
    src, unit, jsonl, ctx = world
    handles = []
    ctx.hooks = Hooks(after_quarantine=lambda u: handles.append(open(quarantined(src), "rb")))
    try:
        assert delete_claude_unit(unit, ctx) == "kept:open"
    finally:
        for handle in handles:
            handle.close()
    assert jsonl.exists() and (src.root / "-p" / SID / "tool-results" / "r.txt").exists()


def test_failed_inspection_restores(world):
    src, unit, jsonl, ctx = world

    def blind():
        raise InspectionFailed([("1", "x", "Permission denied")])

    ctx.held = blind
    assert delete_claude_unit(unit, ctx) == "failed:uninspectable"
    assert jsonl.exists() and (src.root / "-p" / SID / "tool-results" / "r.txt").exists()
    assert not (src.home / QUARANTINE / "run1").exists()


def recreate(jsonl):
    jsonl.write_bytes(b'{"fragment":1}\n')


def test_recreated_after_quarantine_keeps_both(world):
    src, unit, jsonl, ctx = world
    ctx.hooks = Hooks(after_quarantine=lambda u: recreate(jsonl))
    assert delete_claude_unit(unit, ctx) == "failed:recreated"
    assert jsonl.read_bytes() == b'{"fragment":1}\n'
    assert quarantined(src).read_bytes() == b'{"a":1}\n'


def test_recreated_with_holder_keeps_both(world):
    src, unit, jsonl, ctx = world
    handles = []

    def hook(u):
        handles.append(open(quarantined(src), "rb"))
        recreate(jsonl)

    ctx.hooks = Hooks(after_quarantine=hook)
    try:
        assert delete_claude_unit(unit, ctx) == "failed:recreated"
    finally:
        for handle in handles:
            handle.close()
    assert jsonl.read_bytes() == b'{"fragment":1}\n'
    assert quarantined(src).exists()


def test_recreated_with_change_keeps_both_and_archives_change(world, archive):
    src, unit, jsonl, ctx = world

    def hook(u):
        with open(quarantined(src), "ab") as handle:
            handle.write(b'{"late":1}\n')
        recreate(jsonl)

    ctx.hooks = Hooks(after_quarantine=hook)
    assert delete_claude_unit(unit, ctx) == "failed:recreated"
    assert jsonl.read_bytes() == b'{"fragment":1}\n'
    assert quarantined(src).read_bytes() == b'{"a":1}\n{"late":1}\n'
    assert mirror_path(archive, "claude", f"-p/{SID}.jsonl").read_bytes() == b'{"a":1}\n{"late":1}\n'


def test_capture_after_recreated_stores_fragment_as_version(world, archive, manifest):
    src, unit, jsonl, ctx = world
    ctx.hooks = Hooks(after_quarantine=lambda u: recreate(jsonl))
    delete_claude_unit(unit, ctx)
    before = hash_file(mirror_path(archive, "claude", f"-p/{SID}.jsonl"))
    report, ok = capture_run(archive, manifest, [src])
    assert ok and report["claude"]["diverged"] == 1
    assert hash_file(mirror_path(archive, "claude", f"-p/{SID}.jsonl")) == before


def test_recapture_failure_keeps_quarantine(world, monkeypatch):
    src, unit, jsonl, ctx = world

    def append(u):
        with open(quarantined(src), "ab") as handle:
            handle.write(b'{"late":1}\n')

    def refuse(*args, **kw):
        raise OSError("archive disk full")

    monkeypatch.setattr(prune, "capture_file", refuse)
    ctx.hooks = Hooks(after_quarantine=append)
    assert delete_claude_unit(unit, ctx) == "failed:recapture"
    assert quarantined(src).exists() and not jsonl.exists()


@pytest.mark.parametrize("kind", ["symlink", "directory-symlink", "fifo"])
def test_nonregular_quarantine_entry_is_kept(world, tmp_path, kind):
    src, unit, jsonl, ctx = world
    external = tmp_path / "external"
    external.mkdir()
    outside = external / "file"
    outside.write_bytes(b"outside")

    def insert(u):
        entry = quarantined(src, SID) / "unexpected"
        if kind == "fifo":
            os.mkfifo(entry)
        elif kind == "directory-symlink":
            entry.symlink_to(external, target_is_directory=True)
        else:
            entry.symlink_to(outside)

    ctx.hooks = Hooks(after_quarantine=insert)
    assert delete_claude_unit(unit, ctx) == "failed:release"
    assert os.path.lexists(quarantined(src, SID) / "unexpected")
    assert outside.read_bytes() == b"outside"


def test_new_file_is_recaptured_and_restored(world, archive):
    src, unit, jsonl, ctx = world
    ctx.hooks = Hooks(after_quarantine=lambda u: (
        quarantined(src, SID) / "new.txt").write_bytes(b"late file"))
    assert delete_claude_unit(unit, ctx) == "kept:changed"
    assert (src.root / "-p" / SID / "new.txt").read_bytes() == b"late file"
    assert mirror_path(archive, "claude", f"-p/{SID}/new.txt").read_bytes() == b"late file"


def test_source_symlink_never_borrows_target_bytes(world):
    src, unit, jsonl, ctx = world
    info = jsonl.stat()
    target = jsonl.parent / "targetxx"
    target.write_bytes(jsonl.read_bytes())
    jsonl.unlink()
    jsonl.symlink_to(target.name)  # Same length as the archived transcript bytes.
    os.utime(jsonl, ns=(info.st_mtime_ns, info.st_mtime_ns), follow_symlinks=False)
    ctx.obs[str(target)] = ctx.obs[str(jsonl)]
    with pytest.raises(OSError):
        evaluate(unit, ctx, set())
    assert target.read_bytes() == b'{"a":1}\n'


def test_swapped_quarantine_file_does_not_borrow_symlink_bytes(world, tmp_path):
    src, unit, jsonl, ctx = world
    target = tmp_path / "external"
    target.write_bytes(jsonl.read_bytes())

    def swap(u):
        entry = quarantined(src)
        entry.unlink()
        entry.symlink_to(target)

    ctx.hooks = Hooks(before_delete=swap)
    assert delete_claude_unit(unit, ctx) == "failed:release"
    assert quarantined(src).is_symlink() and target.read_bytes() == b'{"a":1}\n'


def test_recreated_before_delete_keeps_both(world):
    src, unit, jsonl, ctx = world
    ctx.hooks = Hooks(before_delete=lambda u: recreate(jsonl))
    assert delete_claude_unit(unit, ctx) == "failed:recreated"
    assert jsonl.read_bytes() == b'{"fragment":1}\n'
    assert quarantined(src).read_bytes() == b'{"a":1}\n'


def test_replaced_file_after_release_is_not_reported_pruned(world, monkeypatch):
    src, unit, jsonl, ctx = world
    real_release = prune.release

    def replace_after_release(entry, live, preserve):
        result = real_release(entry, live, preserve)
        if entry == quarantined(src):
            entry.write_bytes(b"replacement")
        return result

    monkeypatch.setattr(prune, "release", replace_after_release)
    assert delete_claude_unit(unit, ctx) == "failed:release"
    assert quarantined(src).read_bytes() == b"replacement"


def test_stat_change_after_quarantine_is_recaptured_and_restored(world):
    src, unit, jsonl, ctx = world

    def touch(u):
        info = quarantined(src).stat()
        os.utime(quarantined(src), ns=(info.st_mtime_ns + 1_000_000, info.st_mtime_ns + 1_000_000))

    ctx.hooks = Hooks(after_quarantine=touch)
    assert delete_claude_unit(unit, ctx) == "kept:changed"
    assert jsonl.stat().st_mtime_ns == ctx.manifest.mirror("claude", f"-p/{SID}.jsonl").mtime_ns


def test_source_parent_symlink_does_not_move_or_delete_external_files(world, tmp_path):
    import shutil

    src, unit, jsonl, ctx = world
    saved = tmp_path / "saved"
    jsonl.parent.rename(saved)
    outside = tmp_path / "outside"
    shutil.copytree(saved, outside, copy_function=shutil.copy2)
    jsonl.parent.symlink_to(outside, target_is_directory=True)
    assert delete_claude_unit(unit, ctx) == "failed:release"
    assert (outside / jsonl.name).read_bytes() == b'{"a":1}\n'
    assert (outside / SID / "tool-results" / "r.txt").read_bytes() == b"result"
    assert (saved / jsonl.name).read_bytes() == b'{"a":1}\n'


def test_replaced_source_during_hash_is_rejected(world, monkeypatch):
    import hashlib

    src, unit, jsonl, ctx = world
    real_digest = hashlib.file_digest

    def replace(reader, name):
        digest = real_digest(reader, name)
        if reader.name == jsonl.name or os.path.samestat(os.fstat(reader.fileno()), jsonl.stat()):
            info = jsonl.stat()
            replacement = jsonl.with_suffix(".replacement")
            replacement.write_bytes(b'{"a":1}\n')
            os.utime(replacement, ns=(info.st_mtime_ns, info.st_mtime_ns))
            replacement.replace(jsonl)
        return digest

    monkeypatch.setattr(hashlib, "file_digest", replace)
    with pytest.raises(OSError):
        evaluate(unit, ctx, set())
    assert jsonl.read_bytes() == b'{"a":1}\n'


def test_held_nested_directory_restores_before_openat_append(world):
    src, unit, jsonl, ctx = world
    handles = []

    def hold_directory(u):
        handles.append(os.open(quarantined(src, SID) / "tool-results", os.O_RDONLY | os.O_DIRECTORY))

    def open_for_append(u):
        handles.append(os.open("r.txt", os.O_WRONLY | os.O_APPEND, dir_fd=handles[0]))

    ctx.hooks = Hooks(after_quarantine=hold_directory, before_delete=open_for_append)
    try:
        outcome = delete_claude_unit(unit, ctx)
        # A held nested directory can still open original files even after their live names vanish.
        writer = os.open("r.txt", os.O_WRONLY | os.O_APPEND, dir_fd=handles[0]) if len(handles) == 1 else handles[1]
        if len(handles) == 1:
            handles.append(writer)
        os.write(writer, b" late")
        assert outcome == "kept:open"
        assert jsonl.exists()
        assert (src.root / "-p" / SID / "tool-results" / "r.txt").read_bytes() == b"result late"
    finally:
        for fd in reversed(handles):
            os.close(fd)


def test_new_companion_directory_after_transcript_only_discovery_keeps_quarantine(world):
    import shutil

    src, _, jsonl, ctx = world
    shutil.rmtree(src.root / "-p" / SID)
    (unit,) = claude_units(src)

    def recreate_directory(u):
        companion = src.root / "-p" / SID
        companion.mkdir()
        (companion / "new.txt").write_bytes(b"new content")

    ctx.hooks = Hooks(after_quarantine=recreate_directory)
    assert delete_claude_unit(unit, ctx) == "failed:recreated"
    assert quarantined(src).read_bytes() == b'{"a":1}\n'
    assert (src.root / "-p" / SID / "new.txt").read_bytes() == b"new content"
