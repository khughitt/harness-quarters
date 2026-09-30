"""Codex deletion protocol and its deletion-window cases (spec §3.4.3)."""
import fcntl
import json
import os
import time

import pytest

from session_archive import config, prune
from session_archive.capture import capture_run, hash_file, mirror_path
from session_archive.inputs import codex_units
from session_archive.prune import Context, Hooks, delete_codex_unit, evaluate
from session_archive.quarantine import QUARANTINE
from session_archive.testing import TID, codex_rollout, lenient_open_inodes, obs_for


@pytest.fixture
def world(home, archive, manifest, stub_codex):
    src = next(s for s in config.sources(home) if s.name == "codex")
    rollout = codex_rollout(src.root)
    capture_run(archive, manifest, [src])
    (unit,) = codex_units(src)
    ctx = Context(archive, manifest, obs_for(rollout), lenient_open_inodes, time.time_ns(), "run1",
                  codex_bin=str(stub_codex))
    assert evaluate(unit, ctx, set()) is None
    return src, unit, rollout, ctx


def link(src, rollout):
    return src.home / QUARANTINE / "run1" / rollout.name


def append(path, data=b'{"late":1}\n'):
    with open(path, "ab") as handle:
        handle.write(data)


def test_pruned_through_codex_delete(world, tmp_path, archive):
    src, unit, rollout, ctx = world
    assert delete_codex_unit(unit, ctx) == "pruned"
    assert not rollout.exists() and not (src.home / QUARANTINE / "run1").exists()
    calls = [json.loads(line) for line in (tmp_path / "codex.log").read_text().splitlines()]
    assert calls == [{"argv": ["delete", "--force", TID], "codex_home": str(src.home)}]
    assert mirror_path(archive, "codex", unit.files[0]).exists()


def test_held_writer_lock_is_busy(world):
    src, unit, rollout, ctx = world
    lock = src.home / "thread-writer-locks" / f"{TID}.lock"
    lock.parent.mkdir(exist_ok=True)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert delete_codex_unit(unit, ctx) == "kept:busy"
    finally:
        os.close(fd)
    assert rollout.exists()


def test_append_between_lock_and_delete_is_archived(world, archive):
    src, unit, rollout, ctx = world
    ctx.hooks = Hooks(before_delete=lambda u: append(rollout))
    assert delete_codex_unit(unit, ctx) == "failed:changed"
    assert mirror_path(archive, "codex", unit.files[0]).read_bytes().endswith(b'{"late":1}\n')
    assert not link(src, rollout).exists()


def test_append_then_unlink_then_nonzero_exit(world, archive, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setenv("STUB_CODEX_MODE", "unlink-fail")
    ctx.hooks = Hooks(before_delete=lambda u: append(rollout))
    assert delete_codex_unit(unit, ctx) == "failed:delete"
    assert not rollout.exists()
    assert mirror_path(archive, "codex", unit.files[0]).read_bytes().endswith(b'{"late":1}\n')
    assert not link(src, rollout).exists()


def test_unlink_fail_with_failed_recapture_keeps_link(world, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setenv("STUB_CODEX_MODE", "unlink-fail")

    def refuse(*args, **kw):
        raise OSError("archive disk full")

    monkeypatch.setattr(prune, "capture_file", refuse)
    ctx.hooks = Hooks(before_delete=lambda u: append(rollout))
    assert delete_codex_unit(unit, ctx) == "failed:delete-quarantined"
    assert link(src, rollout).read_bytes().endswith(b'{"late":1}\n')


def test_nonzero_exit_without_unlink_releases_link(world, monkeypatch):
    src, unit, rollout, ctx = world
    before = hash_file(rollout)
    monkeypatch.setenv("STUB_CODEX_MODE", "fail")
    assert delete_codex_unit(unit, ctx) == "failed:delete"
    assert hash_file(rollout) == before and not link(src, rollout).exists()


def test_writer_alive_after_delete_keeps_link(world, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setenv("STUB_CODEX_MODE", "writer-during-delete")
    assert delete_codex_unit(unit, ctx) == "failed:writer-live-quarantined"
    time.sleep(2.5)                                  # the writer appends, then exits
    assert link(src, rollout).read_bytes().endswith(b'{"resumed":1}\n')


def test_writer_alive_after_unlink_then_failure_keeps_link(world, archive, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setenv("STUB_CODEX_MODE", "writer-unlink-fail")
    assert delete_codex_unit(unit, ctx) == "failed:writer-live-quarantined"
    time.sleep(2.5)
    assert link(src, rollout).read_bytes().endswith(b'{"resumed":1}\n')


def test_timeout_is_a_failed_delete(world, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setenv("STUB_CODEX_MODE", "hang")
    ctx.codex_timeout = 1
    assert delete_codex_unit(unit, ctx) == "failed:delete"
    assert rollout.exists()


@pytest.mark.parametrize("kind", ["file", "parent"])
@pytest.mark.parametrize("when", ["after-evaluate", "during-link"])
def test_source_symlink_swap_never_deletes_external_bytes(world, tmp_path, monkeypatch, kind, when):
    import shutil

    src, unit, rollout, ctx = world
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / rollout.name
    target.write_bytes(rollout.read_bytes())
    saved = tmp_path / "saved"

    def swap():
        if kind == "file":
            rollout.rename(saved)
            rollout.symlink_to(target)
        else:
            rollout.parent.rename(saved)
            shutil.copytree(saved, outside, dirs_exist_ok=True, copy_function=shutil.copy2)
            rollout.parent.symlink_to(outside, target_is_directory=True)

    if when == "after-evaluate":
        real_evaluate = prune.evaluate

        def evaluate_then_swap(*args):
            reason = real_evaluate(*args)
            swap()
            return reason

        monkeypatch.setattr(prune, "evaluate", evaluate_then_swap)
    else:
        real_link = os.link

        def swap_then_link(*args, **kw):
            swap()
            return real_link(*args, **kw)

        monkeypatch.setattr(os, "link", swap_then_link)
    assert delete_codex_unit(unit, ctx) == "failed:release"
    assert target.read_bytes() == b'{"type":"session_meta"}\n'
    assert (saved if kind == "file" else saved / rollout.name).read_bytes() == b'{"type":"session_meta"}\n'
    assert not (tmp_path / "codex.log").exists()
    if os.path.lexists(link(src, rollout)):
        assert not link(src, rollout).is_symlink()
        assert link(src, rollout).read_bytes() == b'{"type":"session_meta"}\n'


def test_failed_inspection_after_unlink_keeps_link(world):
    from session_archive.inputs import InspectionFailed

    src, unit, rollout, ctx = world
    real_held = ctx.held

    def blind_after_unlink():
        if not rollout.exists():
            raise InspectionFailed([("1", "writer", "Permission denied")])
        return real_held()

    ctx.held = blind_after_unlink
    assert delete_codex_unit(unit, ctx) == "failed:uninspectable-quarantined"
    assert link(src, rollout).read_bytes() == b'{"type":"session_meta"}\n'


def test_live_path_lost_at_release_with_writer_keeps_link(world, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setenv("STUB_CODEX_MODE", "fail")
    real_release = prune.release
    handles = []

    def unlink_before_release(entry, live, preserve):
        handles.append(open(live, "ab"))
        live.unlink()
        result = real_release(entry, live, preserve)
        handles[0].write(b'{"resumed":1}\n')
        handles[0].flush()
        return result

    monkeypatch.setattr(prune, "release", unlink_before_release)
    try:
        assert delete_codex_unit(unit, ctx) == "failed:writer-live-quarantined"
        assert link(src, rollout).read_bytes().endswith(b'{"resumed":1}\n')
    finally:
        for handle in handles:
            handle.close()


def test_missing_codex_is_failed_delete_without_losing_live_bytes(world):
    src, unit, rollout, ctx = world
    ctx.codex_bin = str(src.home / "missing-codex")
    assert delete_codex_unit(unit, ctx) == "failed:delete"
    assert rollout.read_bytes() == b'{"type":"session_meta"}\n'
    assert not link(src, rollout).exists()


def test_swapped_quarantine_symlink_is_kept(world, tmp_path):
    src, unit, rollout, ctx = world
    target = tmp_path / "outside"
    target.write_bytes(rollout.read_bytes())

    def swap(u):
        link(src, rollout).unlink()
        link(src, rollout).symlink_to(target)

    ctx.hooks = Hooks(before_delete=swap)
    assert delete_codex_unit(unit, ctx) == "failed:release"
    assert link(src, rollout).is_symlink()
    assert target.read_bytes() == b'{"type":"session_meta"}\n'


def test_metadata_changed_after_link_is_reported_changed(world):
    src, unit, rollout, ctx = world

    def touch(u):
        stamp = rollout.stat().st_mtime_ns + 1_000_000
        os.utime(rollout, ns=(stamp, stamp))

    ctx.hooks = Hooks(before_delete=touch)
    assert delete_codex_unit(unit, ctx) == "failed:changed"
    assert not link(src, rollout).exists()


def test_source_symlink_swap_before_delete_never_invokes_codex(world, tmp_path):
    src, unit, rollout, ctx = world
    target = tmp_path / "outside"
    target.write_bytes(rollout.read_bytes())

    def swap(u):
        rollout.unlink()
        rollout.symlink_to(target)

    ctx.hooks = Hooks(before_delete=swap)
    assert delete_codex_unit(unit, ctx) == "failed:release"
    assert not (tmp_path / "codex.log").exists()
    assert link(src, rollout).read_bytes() == b'{"type":"session_meta"}\n'
    assert target.read_bytes() == b'{"type":"session_meta"}\n'


def test_vanished_rollout_is_kept(world):
    src, unit, rollout, ctx = world
    rollout.unlink()
    assert delete_codex_unit(unit, ctx) == "kept:vanished"
    assert not link(src, rollout).exists()


def test_failed_inspection_before_link_is_not_deleted(world):
    from session_archive.inputs import InspectionFailed

    src, unit, rollout, ctx = world

    def blind():
        raise InspectionFailed([("1", "writer", "Permission denied")])

    ctx.held = blind
    assert delete_codex_unit(unit, ctx) == "failed:uninspectable"
    assert rollout.exists() and not link(src, rollout).exists()


def test_zero_exit_with_live_rollout_is_failed_delete(world, monkeypatch):
    src, unit, rollout, ctx = world
    monkeypatch.setattr(prune, "run_codex_delete", lambda *args: True)
    assert delete_codex_unit(unit, ctx) == "failed:delete"
    assert rollout.exists() and not link(src, rollout).exists()


def test_other_thread_quarantine_does_not_change_success(world):
    src, unit, rollout, ctx = world
    other = link(src, rollout).parent / "other-thread.jsonl"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"still quarantined")
    assert delete_codex_unit(unit, ctx) == "pruned"
    assert other.read_bytes() == b"still quarantined"
