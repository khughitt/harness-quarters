"""No-replace restore and the release rule (spec §3.4.1)."""
import os
import errno

import pytest

from session_archive.quarantine import (QUARANTINE, inodes, leftovers, quarantine_dir, release,
                                        remove_empty_dirs, rename_noreplace)
from session_archive.testing import write
from session_archive import quarantine


def test_rename_noreplace_moves(tmp_path):
    src = write(tmp_path / "a", b"a")
    rename_noreplace(src, tmp_path / "b")
    assert (tmp_path / "b").read_bytes() == b"a" and not src.exists()


@pytest.mark.parametrize("as_dir", [False, True])
def test_rename_noreplace_refuses_existing_target(tmp_path, as_dir):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    if as_dir:
        write(src / "inner", b"s")
        write(dst / "other", b"d")
    else:
        write(src, b"s")
        write(dst, b"d")
    with pytest.raises(FileExistsError):
        rename_noreplace(src, dst)
    assert src.exists() and dst.exists()
    assert (dst / "other" if as_dir else dst).read_bytes() == b"d"


def test_rename_noreplace_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        rename_noreplace(tmp_path / "absent", tmp_path / "b")


def test_release_rule_a_same_inode(tmp_path):
    live = write(tmp_path / "live", b"x")
    entry = tmp_path / "entry"
    os.link(live, entry)
    assert release(entry, live, lambda path: pytest.fail("preserve must not run"))
    assert not entry.exists() and live.exists()


def test_release_rule_b(tmp_path):
    entry = write(tmp_path / "entry", b"x")
    assert not release(entry, tmp_path / "gone", lambda path: False)
    assert entry.exists()
    assert release(entry, tmp_path / "gone", lambda path: True)
    assert not entry.exists()


def test_release_rule_b_when_live_is_another_file(tmp_path):
    entry = write(tmp_path / "entry", b"x")
    live = write(tmp_path / "live", b"fragment")
    assert not release(entry, live, lambda path: False)
    assert entry.exists()


def test_leftovers_and_cleanup(tmp_path):
    home = tmp_path / "h"
    qdir = quarantine_dir(home, "run1")
    assert leftovers([home]) == []
    (qdir / "p" / "s").mkdir(parents=True)
    assert leftovers([home]) == []          # empty directories are not leftovers
    write(qdir / "p" / "s" / "f", b"x")
    assert leftovers([home, home]) == [home / QUARANTINE]
    (qdir / "p" / "s" / "f").unlink()
    remove_empty_dirs(qdir / "p" / "s", home / QUARANTINE)
    assert (home / QUARANTINE).is_dir() and not qdir.exists()


def test_inodes_cover_directory_members(tmp_path):
    f = write(tmp_path / "d" / "x", b"x")
    info = os.stat(f)
    assert (info.st_dev, info.st_ino) in inodes([tmp_path / "d"])


@pytest.mark.parametrize("through_parent", [False, True])
def test_release_keeps_bytes_reached_only_through_live_symlink(tmp_path, through_parent):
    entry = write(tmp_path / "quarantine" / "entry", b"only copy")
    if through_parent:
        (tmp_path / "live-dir").symlink_to(entry.parent, target_is_directory=True)
        live = tmp_path / "live-dir" / "entry"
    else:
        live = tmp_path / "live"
        live.symlink_to(entry)
    assert not release(entry, live, lambda path: False)
    assert entry.read_bytes() == live.read_bytes() == b"only copy"


@pytest.mark.parametrize("kind", ["symlink", "directory-symlink", "fifo"])
def test_leftovers_include_nonregular_entries(tmp_path, kind):
    home = tmp_path / "h"
    qdir = quarantine_dir(home, "run1")
    qdir.mkdir(parents=True)
    entry = qdir / "entry"
    if kind == "fifo":
        os.mkfifo(entry)
    elif kind == "directory-symlink":
        target = tmp_path / "empty"
        target.mkdir()
        entry.symlink_to(target, target_is_directory=True)
    else:
        entry.symlink_to(tmp_path / "missing")
    assert leftovers([home]) == [home / QUARANTINE]


def test_leftovers_refuse_a_symlink_root(tmp_path):
    home = tmp_path / "h"
    home.mkdir()
    empty = tmp_path / "empty"
    empty.mkdir()
    root = home / QUARANTINE
    root.symlink_to(empty, target_is_directory=True)
    assert leftovers([home]) == [root]


def test_cleanup_preserves_stop_when_top_is_stop(tmp_path):
    stop = tmp_path / QUARANTINE
    stop.mkdir()
    remove_empty_dirs(stop, stop)
    assert stop.is_dir()


@pytest.mark.parametrize("path_form", ["sibling", "dotdot", "symlink"])
def test_cleanup_refuses_paths_outside_stop(tmp_path, path_form):
    stop = tmp_path / QUARANTINE
    other = tmp_path / "other"
    stop.mkdir()
    other.mkdir()
    top = other
    if path_form == "dotdot":
        top = stop / ".." / "other"
    elif path_form == "symlink":
        top = stop / "link"
        top.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError):
        remove_empty_dirs(top, stop)
    assert other.is_dir() and stop.is_dir()


def test_release_rule_b_keeps_entry_when_preserver_swaps_parent(tmp_path):
    entry = write(tmp_path / "quarantine" / "entry", b"held")
    outside = write(tmp_path / "outside" / "entry", b"unrelated")
    moved = tmp_path / "moved"

    def preserve(path):
        assert path.read_bytes() == b"held"
        path.parent.rename(moved)
        path.parent.symlink_to(outside.parent, target_is_directory=True)
        return True

    assert not release(entry, tmp_path / "missing", preserve)
    assert outside.read_bytes() == b"unrelated"
    assert (moved / "entry").read_bytes() == b"held"


def test_release_rule_a_unlinks_only_held_parent(tmp_path, monkeypatch):
    entry = write(tmp_path / "quarantine" / "entry", b"held")
    live = tmp_path / "live"
    os.link(entry, live)
    outside = write(tmp_path / "outside" / "entry", b"unrelated")
    moved = tmp_path / "moved"
    real_fstat = os.fstat
    swapped = False

    def fstat(fd):
        nonlocal swapped
        info = real_fstat(fd)
        if not swapped and os.path.samestat(info, live.stat()):
            swapped = True
            entry.parent.rename(moved)
            entry.parent.symlink_to(outside.parent, target_is_directory=True)
        return info

    monkeypatch.setattr(quarantine.os, "fstat", fstat)
    assert release(entry, live, lambda path: pytest.fail("preserve must not run"))
    assert outside.read_bytes() == b"unrelated" and live.read_bytes() == b"held"
    assert not (moved / "entry").exists()


def test_release_does_not_unlink_replacement_entry(tmp_path):
    entry = write(tmp_path / "entry", b"held")
    replacement = write(tmp_path / "replacement", b"new bytes")

    def preserve(path):
        assert path.read_bytes() == b"held"
        replacement.replace(path)
        return True

    assert not release(entry, tmp_path / "missing", preserve)
    assert entry.read_bytes() == b"new bytes"


def test_cleanup_does_not_follow_top_swapped_during_scan(tmp_path, monkeypatch):
    stop = tmp_path / QUARANTINE
    top = stop / "top"
    (top / "inside").mkdir(parents=True)
    outside = tmp_path / "outside"
    (outside / "child").mkdir(parents=True)
    original = top.stat()
    moved = stop / "moved"
    real_scan = os.scandir
    swapped = False

    def scan(path):
        nonlocal swapped
        info = os.fstat(path) if isinstance(path, int) else os.stat(path)
        if not swapped and os.path.samestat(info, original):
            swapped = True
            top.rename(moved)
            top.symlink_to(outside, target_is_directory=True)
        return real_scan(path)

    monkeypatch.setattr(quarantine.os, "scandir", scan)
    error = None
    try:
        remove_empty_dirs(top, stop)
    except OSError as caught:
        error = caught
    assert (outside / "child").is_dir()
    assert isinstance(error, OSError)


def test_cleanup_propagates_traversal_errors(tmp_path, monkeypatch):
    stop = tmp_path / QUARANTINE
    top = stop / "top"
    (top / "child").mkdir(parents=True)
    original = top.stat()
    real_scan = os.scandir

    def scan(path):
        info = os.fstat(path) if isinstance(path, int) else os.stat(path)
        if os.path.samestat(info, original):
            raise PermissionError(errno.EACCES, "unreadable")
        return real_scan(path)

    monkeypatch.setattr(quarantine.os, "scandir", scan)
    with pytest.raises(PermissionError):
        remove_empty_dirs(top, stop)
    assert (top / "child").is_dir()


@pytest.mark.parametrize("error", [errno.EACCES, errno.EIO])
def test_cleanup_propagates_removal_errors(tmp_path, monkeypatch, error):
    stop = tmp_path / QUARANTINE
    top = stop / "top"
    top.mkdir(parents=True)
    real_rmdir = os.rmdir

    def rmdir(path, *, dir_fd=None):
        if path in (top, str(top), top.name):
            raise OSError(error, "cannot remove")
        return real_rmdir(path, dir_fd=dir_fd)

    monkeypatch.setattr(quarantine.os, "rmdir", rmdir)
    with pytest.raises(OSError) as caught:
        remove_empty_dirs(top, stop)
    assert caught.value.errno == error and top.is_dir()


@pytest.mark.parametrize("same_live", [False, True])
def test_release_keeps_basename_replaced_after_final_stat(tmp_path, monkeypatch, same_live):
    home = tmp_path / "h"
    qdir = quarantine_dir(home, "run1")
    entry = write(qdir / "entry", b"held")
    live = tmp_path / "live"
    if same_live:
        os.link(entry, live)
    replacement = write(tmp_path / "replacement", b"unrelated")
    held = entry.stat()
    real_stat = os.stat
    swapped = False

    def stat(path, *, dir_fd=None, follow_symlinks=True):
        nonlocal swapped
        info = real_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
        if dir_fd is not None and not swapped and os.path.samestat(info, held):
            swapped = True
            replacement.replace(entry)
        return info

    def preserve(path):
        assert not same_live and path.read_bytes() == b"held"
        return True

    monkeypatch.setattr(quarantine.os, "stat", stat)
    assert release(entry, live, preserve)
    assert swapped and entry.read_bytes() == b"unrelated"
    assert leftovers([home]) == [home / QUARANTINE]


@pytest.mark.parametrize("same_live", [False, True])
@pytest.mark.parametrize("recreated", [False, True])
def test_release_restores_or_keeps_mismatched_claim(tmp_path, monkeypatch, same_live, recreated):
    home = tmp_path / "h"
    qdir = quarantine_dir(home, "run1")
    entry = write(qdir / "entry", b"held")
    live = tmp_path / "live"
    if same_live:
        os.link(entry, live)
    replacement = write(tmp_path / "replacement", b"unrelated")
    saved = tmp_path / "original"
    real_rename = quarantine._libc.renameat2
    swapped = False

    def rename(src_fd, src, dst_fd, dst, flags):
        nonlocal swapped
        claiming = src_fd != quarantine.AT_FDCWD and os.fsdecode(src) == entry.name
        if claiming and not swapped:
            swapped = True
            entry.rename(saved)
            replacement.replace(entry)
        result = real_rename(src_fd, src, dst_fd, dst, flags)
        if claiming and recreated and result == 0:
            write(entry, b"recreated")
        return result

    def preserve(path):
        assert not same_live and path.read_bytes() == b"held"
        return True

    monkeypatch.setattr(quarantine._libc, "renameat2", rename)
    assert not release(entry, live, preserve)
    assert swapped and saved.read_bytes() == b"held"
    expected = [b"recreated", b"unrelated"] if recreated else [b"unrelated"]
    assert sorted(path.read_bytes() for path in qdir.iterdir()) == sorted(expected)
    assert entry.read_bytes() == (b"recreated" if recreated else b"unrelated")
    assert leftovers([home]) == [home / QUARANTINE]


def test_inodes_include_nested_directories_without_following_symlinks(tmp_path):
    root = tmp_path / "unit"
    nested = root / "tool-results" / "empty"
    nested.mkdir(parents=True)
    external = tmp_path / "outside"
    external.mkdir()
    link = root / "linked"
    link.symlink_to(external, target_is_directory=True)
    found = inodes([root])
    for path in (root, nested.parent, nested, link):
        info = path.lstat()
        assert (info.st_dev, info.st_ino) in found
    outside = external.stat()
    assert (outside.st_dev, outside.st_ino) not in found
